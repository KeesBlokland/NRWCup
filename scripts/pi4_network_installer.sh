#!/bin/bash
# pi4_nrwcup_complete_installer.sh - Complete NRWCup System Setup
# Updated 22 May 2025 
#==============================================================
# USER CONFIGURATION - Edit these settings as needed
#==============================================================
# WiFi Settings
WIFI_SSID=""    # Your preferred WiFi network name
WIFI_PASSWORD=""  # Your WiFi password

# Hotspot Settings
HOTSPOT_SSID="NRWCup"       # Name for your hotspot
HOTSPOT_PASSWORD="Schlepp4FUN" # Password for your hotspot

# IP and Network Settings
HOTSPOT_IP="192.168.4.1"
DHCP_RANGE="192.168.4.2,192.168.4.100,255.255.255.0,24h"

# NRWCup Flask App Settings
FLASK_APP_PATH="/home/pi/NRWCup"
FLASK_VENV_PATH="/home/pi/NRWCup/venv"
FLASK_SCRIPT="app_main.py"

#==============================================================
# End of user configuration - No need to edit below this line
#==============================================================

# Make sure we're running as root
if [ "$(id -u)" != "0" ]; then
   echo "This script must be run as root" 1>&2
   exit 1
fi

# Create log directory if it doesn't exist
mkdir -p /var/log
INSTALL_LOG="/var/log/nrwcup_install.log"

# Define log function
log() {
    echo "$(date) - $1" | tee -a $INSTALL_LOG
}

echo "======================================================"
echo "NRWCup Complete System Installer"
echo "======================================================"
echo "This script will set up your Raspberry Pi with:"
echo "- Network switching (LAN/WiFi/Hotspot)"
echo "- System status display"
echo "- Flask app autostart"
echo "======================================================"
sleep 2

log "Beginning installation"

# Update system
log "Updating system package lists..."
apt update >> $INSTALL_LOG 2>&1

# Install required packages
log "Installing required packages..."
apt install -y hostapd dnsmasq python3-pip python3-tk python3-netifaces >> $INSTALL_LOG 2>&1

# Install Python packages
log "Installing Python packages..."
pip3 install psutil qrcode pillow >> $INSTALL_LOG 2>&1

# Create and run network setup script - FIXED VERSION with proper variable expansion
log "Creating and running network setup script..."
cat > /usr/local/bin/nrwcup-network-setup.sh << EOF
#!/bin/bash
# /usr/local/bin/nrwcup-network-setup.sh

# Hotspot configuration from installer - these variables are now properly set
HOTSPOT_SSID="$HOTSPOT_SSID"
HOTSPOT_PASSWORD="$HOTSPOT_PASSWORD"
DHCP_RANGE="$DHCP_RANGE"
HOTSPOT_IP="$HOTSPOT_IP"

# Create log file
LOG_FILE="/var/log/nrwcup-network.log"

log() {
    echo "\$(date) - \$1" >> \$LOG_FILE
    echo "\$1"
}

# Make directory for flag files
mkdir -p /home/pi/Projekte

# Check test mode
is_test_mode() {
    [ -f "/home/pi/Projekte/HotspotYes.txt" ]
}

# Configure hostapd
setup_hostapd() {
    log "Setting up hostapd with SSID: \$HOTSPOT_SSID"
    
    # Create config using the variables from user configuration
    cat > /etc/hostapd/hostapd.conf << EOHOSTAPD
interface=wlan0
driver=nl80211
ssid=\$HOTSPOT_SSID
hw_mode=g
channel=7
macaddr_acl=0
auth_algs=1
ignore_broadcast_ssid=0
wpa=2
wpa_passphrase=\$HOTSPOT_PASSWORD
wpa_key_mgmt=WPA-PSK
wpa_pairwise=TKIP
rsn_pairwise=CCMP
country_code=DE
wmm_enabled=0
ieee80211n=1
EOHOSTAPD
    
    # Configure default
    echo 'DAEMON_CONF="/etc/hostapd/hostapd.conf"' > /etc/default/hostapd
    
    # Enable service
    systemctl unmask hostapd
    systemctl enable hostapd
}

# Configure dnsmasq
setup_dnsmasq() {
    log "Setting up dnsmasq..."
    
    # Create config using variables
    cat > /etc/dnsmasq.conf << EODNSMASQ
interface=wlan0
dhcp-range=\$DHCP_RANGE
domain=wlan
address=/gw.wlan/\$HOTSPOT_IP
EODNSMASQ
    
    # Enable service
    systemctl enable dnsmasq
}

# Setup dhcpcd for AP mode
setup_dhcpcd() {
    log "Setting up dhcpcd for AP mode..."
    
    # Add AP configuration to dhcpcd.conf if not already there
    if ! grep -q "^interface wlan0" /etc/dhcpcd.conf; then
        cat >> /etc/dhcpcd.conf << EODHCPCD

# NRWCup AP mode configuration
interface wlan0
    static ip_address=\$HOTSPOT_IP/24
    nohook wpa_supplicant
EODHCPCD
    fi
}

# Setup network interfaces
setup_interfaces() {
    log "Setting up network interfaces..."
    
    # Create WPA supplicant config
    cat > /etc/wpa_supplicant/wpa_supplicant.conf << EOWPA
country=DE
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
EOWPA
}

# Apply test mode if enabled
apply_test_mode() {
    if is_test_mode; then
        log "Test mode detected - applying special configuration"
        
        # Create required directories
        mkdir -p /lib/dhcpcd/dhcpcd-hooks/
        
        # Create a dhcpcd hook script to ensure AP mode
        cat > /lib/dhcpcd/dhcpcd-hooks/99-nrwcup-test << EOHOOK
# NRWCup Test Mode hook
if [ -f "/home/pi/Projekte/HotspotYes.txt" ]; then
    # Force static IP for AP mode
    if [ "\\\$interface" = "wlan0" ]; then
        ip addr flush dev wlan0
        ip addr add \$HOTSPOT_IP/24 dev wlan0
    fi
fi
EOHOOK
        
        # Create systemd override for hostapd to make it wait for network
        mkdir -p /etc/systemd/system/hostapd.service.d/
        cat > /etc/systemd/system/hostapd.service.d/override.conf << EOOVERRIDE
[Unit]
After=dhcpcd.service
[Service]
ExecStartPre=/bin/sleep 5
EOOVERRIDE
        
        # Create startup script
        cat > /etc/rc.local << EORCLOCAL
#!/bin/bash
# rc.local for NRWCup

# Create status file
echo "test_mode" > /tmp/network_mode

# Configure network for AP mode
if [ -f "/home/pi/Projekte/HotspotYes.txt" ]; then
    # Ensure wlan0 is properly configured
    ip link set wlan0 down
    ip addr flush dev wlan0
    ip link set wlan0 up
    ip addr add \$HOTSPOT_IP/24 dev wlan0
    
    # Restart services
    systemctl restart hostapd
    systemctl restart dnsmasq
fi

exit 0
EORCLOCAL
        chmod +x /etc/rc.local
        
        log "Test mode configuration applied"
    else
        log "Standard mode - no special configuration applied"
    fi
}

# Run the configuration
log "Starting NRWCup network configuration"
setup_hostapd
setup_dnsmasq
setup_dhcpcd
setup_interfaces
apply_test_mode
log "Network configuration complete"

exit 0
EOF
chmod +x /usr/local/bin/nrwcup-network-setup.sh

# Run the network setup script
log "Running network setup script..."
/usr/local/bin/nrwcup-network-setup.sh

# Create a simplified network manager script
log "Creating and installing network manager script..."
cat > /usr/local/bin/network_manager.sh << 'EOF'
#!/bin/bash
# network_manager.sh - Simple WiFi/Hotspot manager

LOG_FILE="/var/log/network_manager.log"

log() {
    echo "$(date) - $1" >> $LOG_FILE
    echo "$1"
}

# Create directories if needed
mkdir -p /home/pi/Projekte

# Check if test mode is enabled
is_test_mode() {
    [ -f "/home/pi/Projekte/HotspotYes.txt" ]
}

# Is service active?
is_service_active() {
    systemctl is-active --quiet "$1"
    return $?
}

# Enable hotspot mode
enable_hotspot() {
    log "Enabling hotspot mode..."
    
    # Stop wpa_supplicant
    systemctl stop wpa_supplicant.service
    
    # Reset interface
    ip link set wlan0 down
    ip addr flush dev wlan0
    
    # Make sure WiFi isn't blocked
    rfkill unblock wifi
    
    # Configure interface
    ip link set wlan0 up
    ip addr add 192.168.4.1/24 dev wlan0
    
    # Start hotspot services
    systemctl start hostapd
    systemctl start dnsmasq
    
    log "Hotspot mode activated"
    echo "hotspot" > /tmp/network_mode
}

# Enable WiFi client mode
enable_wifi() {
    log "Enabling WiFi client mode..."
    
    # If in test mode, don't stop hotspot
    if ! is_test_mode; then
        systemctl stop hostapd
        systemctl stop dnsmasq
    fi
    
    # Start WiFi client service
    systemctl start wpa_supplicant.service
    
    # Wait for connection
    log "Waiting for WiFi connection..."
    sleep 5
    
    if iwconfig wlan0 | grep -q "ESSID:\""; then
        ssid=$(iwconfig wlan0 | grep ESSID | cut -d'"' -f2)
        log "Connected to WiFi: $ssid"
        echo "wifi" > /tmp/network_mode
    else
        log "Failed to connect to WiFi"
        if is_test_mode; then
            # Keep hotspot in test mode
            enable_hotspot
        fi
    fi
}

# Auto-select best mode
auto_select_mode() {
    log "Auto-selecting network mode..."
    
    # If in test mode, ensure hotspot
    if is_test_mode; then
        log "Test mode detected - enabling hotspot"
        enable_hotspot
        return
    fi
    
    # Try WiFi first if configured
    if [ -n "$(grep -o "ssid=" /etc/wpa_supplicant/wpa_supplicant.conf)" ]; then
        log "WiFi configured, attempting connection"
        enable_wifi
    else
        log "No WiFi configured, enabling hotspot"
        enable_hotspot
    fi
}

# Print current status
show_status() {
    if is_service_active hostapd; then
        echo "Hotspot mode active"
    elif iwconfig wlan0 | grep -q "ESSID:\""; then
        ssid=$(iwconfig wlan0 | grep ESSID | cut -d'"' -f2)
        echo "Connected to WiFi: $ssid"
    else
        echo "No WiFi connection"
    fi
}

# Main commands
case "$1" in
    hotspot)
        enable_hotspot
        ;;
    wifi)
        enable_wifi
        ;;
    auto)
        auto_select_mode
        ;;
    status)
        show_status
        ;;
    *)
        echo "Usage: $0 {hotspot|wifi|auto|status}"
        exit 1
        ;;
esac

exit 0
EOF
chmod +x /usr/local/bin/network_manager.sh

# Create system display script - with backup and forced update
log "Creating and installing system display script..."
if [ -f "/usr/local/bin/system_display.py" ]; then
    log "Backing up existing system_display.py..."
    cp /usr/local/bin/system_display.py /usr/local/bin/system_display.py.bak.$(date +%Y%m%d%H%M%S)
    log "Backup created. Updating system_display.py..."
fi

# Now create the new file (will overwrite any existing file)
cat > /usr/local/bin/system_display.py << 'EOF'
#!/usr/bin/env python3
import os
import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import netifaces
import psutil
import time
import socket
import threading
import qrcode
from PIL import Image, ImageTk

os.environ['DISPLAY'] = ':0'

# Global variables to track state
hotspot_activation_in_progress = False
last_activation_time = 0

def is_service_running(service_name):
    """Thorough check if a service is actually running."""
    try:
        result = subprocess.run(['systemctl', 'is-active', service_name], 
                             capture_output=True, text=True)
        return result.stdout.strip() == "active"
    except:
        return False

def get_ethernet_status():
    """Check if Ethernet (LAN) is connected with IP."""
    if 'eth0' not in netifaces.interfaces():
        return False, "Not available"
    
    try:
        # Check physical connection
        with open('/sys/class/net/eth0/carrier', 'r') as f:
            if f.read().strip() != '1':
                return False, "Disconnected"
                
        # Check IP address
        addresses = netifaces.ifaddresses('eth0')
        if netifaces.AF_INET in addresses:
            return True, addresses[netifaces.AF_INET][0]['addr']
    except:
        pass
    
    return False, "No IP"

def is_hotspot_active():
    """Verify hotspot is working properly."""
    # Check if hostapd is running
    if not is_service_running("hostapd"):
        return False
        
    # Check if wlan0 has the correct IP
    try:
        addresses = netifaces.ifaddresses('wlan0')
        if (netifaces.AF_INET not in addresses or 
            not any(addr.get('addr', '') == '192.168.4.1' 
                  for addr in addresses[netifaces.AF_INET])):
            return False
    except:
        return False
        
    return True

def activate_hotspot():
    """Activate WiFi hotspot with verification."""
    global hotspot_activation_in_progress, last_activation_time
    
    if hotspot_activation_in_progress:
        return False
    
    hotspot_activation_in_progress = True
    hotspot_button.config(text="ACTIVATING...", state=tk.DISABLED)
    
    def activate_thread():
        global hotspot_activation_in_progress
        try:
            # Clean state
            subprocess.run(['sudo', 'systemctl', 'stop', 'hostapd'], check=False)
            subprocess.run(['sudo', 'systemctl', 'stop', 'dnsmasq'], check=False)
            
            # Configure interface
            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'down'], check=False)
            subprocess.run(['sudo', 'ip', 'addr', 'flush', 'dev', 'wlan0'], check=False)
            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'], check=False)
            subprocess.run(['sudo', 'ip', 'addr', 'add', '192.168.4.1/24', 'dev', 'wlan0'], check=False)
            
            # Start services
            subprocess.run(['sudo', 'systemctl', 'start', 'hostapd'], check=False)
            subprocess.run(['sudo', 'systemctl', 'start', 'dnsmasq'], check=False)
            
            # Wait for services
            time.sleep(2)
        except:
            pass
        
        hotspot_activation_in_progress = False
        last_activation_time = time.time()
    
    threading.Thread(target=activate_thread).start()
    return True

def deactivate_hotspot():
    """Turn off the hotspot."""
    global hotspot_activation_in_progress
    
    if hotspot_activation_in_progress:
        return False
    
    hotspot_activation_in_progress = True
    hotspot_button.config(text="DEACTIVATING...", state=tk.DISABLED)
    
    def deactivate_thread():
        global hotspot_activation_in_progress
        try:
            # Stop services
            subprocess.run(['sudo', 'systemctl', 'stop', 'hostapd'], check=False)
            subprocess.run(['sudo', 'systemctl', 'stop', 'dnsmasq'], check=False)
            
            # Clear interface configuration
            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'down'], check=False)
            subprocess.run(['sudo', 'ip', 'addr', 'flush', 'dev', 'wlan0'], check=False)
            subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'], check=False)
        except:
            pass
        
        hotspot_activation_in_progress = False
    
    threading.Thread(target=deactivate_thread).start()
    return True

def get_flask_port():
    """Get Flask port number."""
    try:
        result = subprocess.run(['/usr/local/bin/detect_flask_port.sh'], 
                             capture_output=True, text=True)
        port = result.stdout.strip()
        return port if port and port.isdigit() else "5000"
    except:
        return "5000"

def confirm_shutdown():
    confirm = tk.Toplevel(root)
    confirm.title("Confirm Shutdown")
    confirm.geometry("300x150")
    confirm.transient(root)
    confirm.grab_set()
    confirm.configure(bg="#1E1E1E")

    label = tk.Label(confirm, text="Are you sure you want to shutdown?", 
                     font=('Helvetica', 12), wraplength=250, bg="#1E1E1E", fg="#00FF00")
    label.pack(pady=20)

    def do_shutdown():
        try:
            subprocess.run(['sudo', 'shutdown', 'now'], check=True)
        except:
            pass
        confirm.destroy()

    def cancel_shutdown():
        confirm.destroy()

    frame = tk.Frame(confirm, bg="#1E1E1E")
    frame.pack(pady=10)
    
    yes_button = tk.Button(frame, text="Yes, Shutdown", command=do_shutdown, bg='red', fg='white')
    yes_button.pack(side=tk.LEFT, padx=10)
    
    no_button = tk.Button(frame, text="Cancel", command=cancel_shutdown, bg='#333333', fg='white')
    no_button.pack(side=tk.LEFT)

def confirm_reboot():
    confirm = tk.Toplevel(root)
    confirm.title("Confirm Reboot")
    confirm.geometry("300x150")
    confirm.transient(root)
    confirm.grab_set()
    confirm.configure(bg="#1E1E1E")

    label = tk.Label(confirm, text="Are you sure you want to reboot?", 
                     font=('Helvetica', 12), wraplength=250, bg="#1E1E1E", fg="#00FF00")
    label.pack(pady=20)

    def do_reboot():
        try:
            subprocess.run(['sudo', 'reboot'], check=True)
        except:
            pass
        confirm.destroy()

    def cancel_reboot():
        confirm.destroy()

    frame = tk.Frame(confirm, bg="#1E1E1E")
    frame.pack(pady=10)
    
    yes_button = tk.Button(frame, text="Yes, Reboot", command=do_reboot, bg='orange', fg='white')
    yes_button.pack(side=tk.LEFT, padx=10)
    
    no_button = tk.Button(frame, text="Cancel", command=cancel_reboot, bg='#333333', fg='white')
    no_button.pack(side=tk.LEFT)

# UI setup
root = tk.Tk()
root.title("NRWCup")
root.attributes('-fullscreen', True)
root.config(cursor="none", bg="#1E1E1E")

# Get screen dimensions
screen_width = root.winfo_screenwidth()
screen_height = root.winfo_screenheight()

# Main frame
main_frame = tk.Frame(root, bg="#1E1E1E")
main_frame.pack(fill="both", expand=True)

# Header
header = tk.Label(main_frame, text="NRWCup System", 
                font=('Helvetica', 14, 'bold'), 
                bg="#1E1E1E", fg="#00FF00")
header.pack(pady=(5, 0))

# URL display
url_label = tk.Label(main_frame, text="Checking connection...", 
                   font=('Helvetica', 14, 'bold'), 
                   bg="#1E1E1E", fg="#FFFF00",
                   anchor="center")
url_label.pack(fill="x")

# Add a separator
separator = ttk.Separator(main_frame, orient='horizontal')
separator.pack(fill='x')

# Middle area with QR and stats side by side
middle_frame = tk.Frame(main_frame, bg="#1E1E1E")
middle_frame.pack(fill="both", expand=True, padx=5, pady=5)

# QR code on the left
qr_frame = tk.Frame(middle_frame, bg="#1E1E1E")
qr_frame.pack(side=tk.LEFT, padx=5)

qr_label = tk.Label(qr_frame, bg="#1E1E1E")
qr_label.pack()

# Stats on the right
info_frame = tk.Frame(middle_frame, bg="#1E1E1E")
info_frame.pack(side=tk.RIGHT, fill="both", expand=True, padx=5)

# System stats combined in one line
system_stats_label = tk.Label(info_frame, text="System: CPU: ---, MEM: ---, DISK: ---", 
                            font=('Helvetica', 10), 
                            bg="#1E1E1E", fg="#00FF00",
                            anchor="w")
system_stats_label.pack(fill="x")

# Services status
services_label = tk.Label(info_frame, text="Services: ---", 
                        font=('Helvetica', 10), 
                        bg="#1E1E1E", fg="#00FF00",
                        anchor="w")
services_label.pack(fill="x")

# Help text under system stats on the right
help_label = tk.Label(info_frame, 
                     text="\n\n Connect to 'NRWCup' Hotspot\n Password: Schlepp4FUN\n Scan QR code or use URL above", 
                     font=('Helvetica', 14), 
                     bg="#1E1E1E", fg="#FFFFFF",
                     justify=tk.LEFT)
help_label.pack(pady=(5, 0), anchor="w")

# Buttons at bottom of main frame
button_frame = tk.Frame(main_frame, bg="#1E1E1E")
button_frame.pack(side=tk.BOTTOM, fill="x", pady=5)

# Use grid for equal button sizing
button_frame.columnconfigure(0, weight=1)
button_frame.columnconfigure(1, weight=1)
button_frame.columnconfigure(2, weight=1)

reboot_button = tk.Button(button_frame, text="REBOOT", 
                        command=confirm_reboot, 
                        bg="#FF9900", fg="white",
                        font=('Helvetica', 14, 'bold'),
                        height=2)
reboot_button.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

# Create hotspot button with toggle functionality
hotspot_button = tk.Button(button_frame, text="HOTSPOT", 
                         command=lambda: None,  # Will be assigned in update_display
                         bg="#3366FF", fg="white",
                         font=('Helvetica', 14, 'bold'),
                         height=2)
hotspot_button.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

shutdown_button = tk.Button(button_frame, text="SHUTDOWN", 
                          command=confirm_shutdown, 
                          bg="#FF3333", fg="white",
                          font=('Helvetica', 14, 'bold'),
                          height=2)
shutdown_button.grid(row=0, column=2, sticky="nsew", padx=5, pady=5)

# Track previous states
prev_lan_status = False
prev_hotspot_status = False

# Update display function
def update_display():
    global prev_lan_status, prev_hotspot_status
    
    # Get current status
    lan_connected, lan_ip = get_ethernet_status()
    hotspot_active = is_hotspot_active()
    
    # Update tracking variables
    prev_lan_status = lan_connected
    prev_hotspot_status = hotspot_active
    
    # Get Flask port
    port = get_flask_port()
    
    # Determine the URL to display and QR code
    if hotspot_active:
        url_text = f"Hotspot NRWCup: http://192.168.4.1:{port}"
        flask_url = f"http://192.168.4.1:{port}"
        url_label.config(text=url_text, fg="#FFFF00")
        
        # Update hotspot button to allow turning it OFF
        hotspot_button.config(
            text="STOP HOTSPOT", 
            bg="#3366FF",
            state=tk.NORMAL if not hotspot_activation_in_progress else tk.DISABLED,
            command=deactivate_hotspot
        )
        
        # Make help_label visible when hotspot is active
        help_label.config(fg="#FFFFFF")
    elif lan_connected:
        url_text = f"LAN NRWCup: http://{lan_ip}:{port}"
        flask_url = f"http://{lan_ip}:{port}"
        url_label.config(text=url_text, fg="#FFFF00")
        
        # Update hotspot button to allow turning it ON
        hotspot_button.config(
            text="START HOTSPOT", 
            bg="#3366FF",
            state=tk.NORMAL if not hotspot_activation_in_progress else tk.DISABLED,
            command=activate_hotspot
        )
        
        # Dim the help text when not in hotspot mode
        help_label.config(fg="#555555")
    else:
        url_text = "No connection available"
        flask_url = None
        url_label.config(text=url_text, fg="#FF6666")
        
        # Auto-activate hotspot if needed
        if not hotspot_active and not hotspot_activation_in_progress:
            current_time = time.time()
            if current_time - last_activation_time > 10:
                activate_hotspot()
                
        # Dim the help text when not in hotspot mode
        help_label.config(fg="#555555")
    
    # Update QR code - smaller size for constrained screen
    if flask_url:
        try:
            qr = qrcode.make(flask_url, box_size=4)  # Smaller box size
            qr = qr.resize((120, 120))  # Smaller overall size
            img = ImageTk.PhotoImage(qr)
            qr_label.config(image=img)
            qr_label.image = img  # Keep reference
        except Exception as e:
            print(f"QR code error: {e}")
            qr_label.config(image='')
    else:
        qr_label.config(image='')
    
    # Update service status
    services_text = f"Services: hostapd: {'active' if hotspot_active else 'inactive'}"
    services_label.config(text=services_text)
    
    # System stats
    cpu_percent = psutil.cpu_percent()
    mem_percent = psutil.virtual_memory().percent
    disk_percent = psutil.disk_usage('/').percent
    
    system_stats_label.config(text=f"System: CPU: {cpu_percent}%, MEM: {mem_percent}%, DISK: {disk_percent}%")
    
    # Schedule next update
    root.after(3000, update_display)

# Start updates
root.after(1000, update_display)

# Run the app
root.mainloop()
EOF
chmod +x /usr/local/bin/system_display.py

# Create and install service files
log "Creating and installing service files..."
# Create network service file
cat > /etc/systemd/system/network-manager.service << EOF
[Unit]
Description=Network Manager Service
After=network.target
Before=system-display.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/network_manager.sh auto
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

# Create system display service file
cat > /etc/systemd/system/system-display.service << EOF
[Unit]
Description=System Status Display
After=network-manager.service
Wants=network-manager.service

[Service]
Type=simple
User=pi
Environment="DISPLAY=:0"
ExecStart=/usr/bin/python3 /usr/local/bin/system_display.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=graphical.target
EOF

# Create NRWCup flask service file
cat > /etc/systemd/system/nrwcup-flask.service << EOF
[Unit]
Description=NRWCup Flask Application
After=network-manager.service
Wants=network-manager.service

[Service]
Type=simple
User=pi
WorkingDirectory=$FLASK_APP_PATH
ExecStart=$FLASK_VENV_PATH/bin/python3 $FLASK_SCRIPT
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create Flask port detector script
log "Creating and installing Flask port detector script..."
cat > /usr/local/bin/detect_flask_port.sh << 'EOF'
#!/bin/bash
# detect_flask_port.sh - Detect the port used by the Flask application

# Check if the app is running and get the port
detect_flask_port() {
   # First try using netstat
   if command -v netstat &> /dev/null; then
       port=$(netstat -tlnp 2>/dev/null | grep python | grep -oE ':[0-9]+' | grep -oE '[0-9]+' | head -1)
   
   # If netstat fails or returns nothing, try using ss
   elif command -v ss &> /dev/null; then
       port=$(ss -tlnp 2>/dev/null | grep python | grep -oE ':[0-9]+' | grep -oE '[0-9]+' | head -1)
   
   # Last resort, try lsof
   elif command -v lsof &> /dev/null; then
       port=$(lsof -i -P -n 2>/dev/null | grep python | grep LISTEN | grep -oE ':[0-9]+' | grep -oE '[0-9]+' | head -1)
   fi
   
   # If port is found, return it, otherwise return 5000 (Flask default)
   if [ -n "$port" ]; then
       echo "$port"
   else
       # Check app_main.py for port configuration
       if [ -f "/home/pi/NRWCup/app_main.py" ]; then
           port=$(grep -oE 'port\s*=\s*[0-9]+' /home/pi/NRWCup/app_main.py | grep -oE '[0-9]+' | head -1)
           if [ -n "$port" ]; then
               echo "$port"
               return
           fi
       fi
       # Default Flask port
       echo "5000"
   fi
}

# Get the port and store it in a file for other applications to use
flask_port=$(detect_flask_port)
echo "$flask_port" > /tmp/flask_port

# Output the port
echo "$flask_port"
EOF
chmod +x /usr/local/bin/detect_flask_port.sh

# Enable and start services
log "Enabling and starting services..."
systemctl daemon-reload
systemctl enable network-manager.service
systemctl enable system-display.service
systemctl enable nrwcup-flask.service

# Create test mode file if requested
if [ ! -z "$1" ] && [ "$1" = "test" ]; then
   log "Creating test mode file..."
   mkdir -p /home/pi/Projekte
   echo "Test mode enabled" > /home/pi/Projekte/HotspotYes.txt
fi

# Ensure system display service is properly stopped and started to apply new version
log "Restarting system display service to apply changes..."
systemctl stop system-display.service
sleep 2
systemctl start system-display.service

log "Installation completed successfully"
echo "======================================================"
echo "Installation completed successfully!"
echo "The system will use the following network configuration:"
echo "- Use LAN/WAN if available"
echo "- Create hotspot if no other connection is available"
echo "- If /home/pi/Projekte/HotspotYes.txt exists, always create hotspot"
echo "======================================================"
echo "Reboot the system to apply changes? (y/n)"
read -n 1 -r
echo    # move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
   log "Rebooting system..."
   reboot
fi

exit 0