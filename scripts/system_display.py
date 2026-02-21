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
            not any(addr.get('addr', '') == '192.168.5.1' 
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
            subprocess.run(['sudo', 'ip', 'addr', 'add', '192.168.5.1/24', 'dev', 'wlan0'], check=False)
            
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
        url_text = f"Hotspot NRWCup: http://192.168.5.1:{port}"
        flask_url = f"http://192.168.5.1:{port}"
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
