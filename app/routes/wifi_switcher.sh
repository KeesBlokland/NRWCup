#!/usr/bin/env python3
import os
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import psutil
import time
import netifaces
import qrcode
from PIL import Image, ImageTk
import logging
import subprocess
import configparser

# Configuration file for WiFi credentials
CONFIG_FILE = os.path.expanduser('~/.system_monitor_config')

def load_wifi_config():
    """Load WiFi configuration from config file."""
    config = configparser.ConfigParser()
    if os.path.exists(CONFIG_FILE):
        config.read(CONFIG_FILE)
        return {
            'ssid': config.get('WiFi', 'ssid', fallback=''),
            'password': config.get('WiFi', 'password', fallback='')
        }
    return {'ssid': '', 'password': ''}


def save_wifi_config(ssid, password):
    """Save WiFi configuration to config file."""
    config = configparser.ConfigParser()
    config['WiFi'] = {
        'ssid': 'WLAN-237755',
        'password': '0495324052510510'
    }
    
    # Ensure the config directory exists
    config_dir = os.path.dirname(CONFIG_FILE)
    os.makedirs(config_dir, exist_ok=True)
    
    # Write the config file
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    
    # Change file permissions to 600 (readable/writable only by owner)
    os.chmod(CONFIG_FILE, 0o600)
    
    # Change file ownership to the current user
    current_user = os.getlogin()
    import pwd
    user_info = pwd.getpwnam(current_user)
    os.chown(CONFIG_FILE, user_info.pw_uid, user_info.pw_gid)

class SystemDisplay:
    def __init__(self):
        if 'DISPLAY' not in os.environ:
            os.environ['DISPLAY'] = ':0'
        # Screen setup
        os.system('xset s 60')
        os.system('xset +dpms')
        os.system('xset dpms 60 60 60')

        # Load WiFi configuration
        self.wifi_config = load_wifi_config()

        self.root = tk.Tk()
        self.root.title("System Monitor")
        self.root.attributes('-fullscreen', True)
        self.root.config(cursor="none")
        
        # Style configuration with improved colors
        self.style = ttk.Style()
        self.style.configure('TFrame', background='#1E1E1E')  # Dark gray background
        self.style.configure('TLabel', background='#1E1E1E', foreground='#00FF00')  # Bright green text
        self.style.configure('TButton', background='#333333', foreground='white')
        self.style.configure('Stats.TLabel', font=('Helvetica', 10))
        self.style.configure('Network.TLabel', font=('Helvetica', 18))
        self.style.configure('BigExit.TButton', font=('Helvetica', 20), background='#FF3333', foreground='white')
        
        self.root.configure(bg='#1E1E1E')
        self.main_frame = ttk.Frame(self.root, padding="5", style='TFrame')
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        
        # Title with explicit touch event handling
        self.title = tk.Label(self.main_frame, text="Pi4 System Status", 
                            font=('Helvetica', 16), bg='#1E1E1E', fg='#00FF00')
        self.title.grid(row=0, column=0, columnspan=3, pady=5)
        
        # Prevent touch events from triggering unintended actions
        self.title.bind('<Button-1>', self.on_title_touch)
        
        # Network toggle buttons with safer subprocess execution
        self.hotspot_button = ttk.Button(self.main_frame, text="Enable Hotspot", 
                                         command=self.enable_hotspot)
        self.hotspot_button.grid(row=1, column=0, pady=10, ipadx=20, ipady=10, sticky="w")
        
        self.wifi_button = ttk.Button(self.main_frame, text="Enable WiFi", 
                                      command=self.enable_wifi)
        self.wifi_button.grid(row=1, column=1, pady=10, ipadx=20, ipady=10)
        
        # WiFi Config button
        self.wifi_config_button = ttk.Button(self.main_frame, text="WiFi Config", 
                                             command=self.configure_wifi)
        self.wifi_config_button.grid(row=1, column=2, pady=10, ipadx=20, ipady=10, sticky="e")
        
        # Shutdown button with confirmation
        self.shutdown_button = ttk.Button(self.main_frame, text="Shutdown", 
                                          command=self.confirm_shutdown, 
                                          style='BigExit.TButton')
        self.shutdown_button.grid(row=2, column=0, columnspan=3, pady=10, ipadx=20, ipady=10)
        
        self.ip_label = ttk.Label(self.main_frame, text="IP: ---", style='Network.TLabel')
        self.ip_label.grid(row=3, column=0, pady=5, padx=5, sticky="w")
        
        self.qr_label = ttk.Label(self.main_frame)
        self.qr_label.grid(row=3, column=1, pady=5, padx=5)
        
        # WiFi Status Label
        self.wifi_status_label = ttk.Label(self.main_frame, 
                                           text=f"WiFi: {self.wifi_config['ssid'] or 'Not Configured'}",
                                           style='Network.TLabel')
        self.wifi_status_label.grid(row=3, column=2, pady=5, padx=5, sticky="e")
        
        self.stats_frame = ttk.Frame(self.main_frame, style='TFrame')
        self.stats_frame.grid(row=4, column=0, columnspan=3, sticky="w", padx=5)
        
        self.cpu_label = ttk.Label(self.stats_frame, text="CPU: ---%", style='Stats.TLabel')
        self.cpu_label.grid(row=0, column=0, pady=5)
        
        self.mem_label = ttk.Label(self.stats_frame, text="Memory: ---%", style='Stats.TLabel')
        self.mem_label.grid(row=1, column=0, pady=5)
        
        self.disk_label = ttk.Label(self.stats_frame, text="Disk: ---%", style='Stats.TLabel')
        self.disk_label.grid(row=2, column=0, pady=5)
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_columnconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(2, weight=1)
        
        self.update_stats()
        self.update_ip()

    def on_title_touch(self, event):
        # Log touch events to debug unexpected behaviors
        logging.debug(f"Title touched at coordinates: {event.x}, {event.y}")

    def configure_wifi(self):
        """Open a dialog to configure WiFi credentials."""
        # Create a custom dialog
        config_dialog = tk.Toplevel(self.root)
        config_dialog.title("WiFi Configuration")
        config_dialog.geometry("300x200")
        config_dialog.transient(self.root)
        config_dialog.grab_set()

        # SSID Label and Entry
        ssid_label = tk.Label(config_dialog, text="WiFi Network Name (SSID):")
        ssid_label.pack(pady=(10,0))
        ssid_entry = tk.Entry(config_dialog, width=30)
        ssid_entry.pack(pady=(0,10))
        ssid_entry.insert(0, self.wifi_config.get('ssid', ''))

        # Password Label and Entry
        pass_label = tk.Label(config_dialog, text="WiFi Password:")
        pass_label.pack(pady=(0,0))
        pass_entry = tk.Entry(config_dialog, show="*", width=30)
        pass_entry.pack(pady=(0,10))
        pass_entry.insert(0, self.wifi_config.get('password', ''))

        def save_wifi_config():
            """Save the WiFi configuration."""
            ssid = ssid_entry.get().strip()
            password = pass_entry.get().strip()

            if not ssid:
                tk.messagebox.showerror("Error", "SSID cannot be empty")
                return

            try:
                # Save configuration
                save_wifi_config(ssid, password)
                
                # Update local configuration
                self.wifi_config = {'ssid': ssid, 'password': password}
                
                # Update WiFi status label
                self.wifi_status_label.config(text=f"WiFi: {ssid}")
                
                # Optional: Write to wpa_supplicant configuration
                self.update_wpa_supplicant(ssid, password)
                
                tk.messagebox.showinfo("Success", "WiFi configuration saved!")
                config_dialog.destroy()
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

        def cancel_config():
            """Close the configuration dialog."""
            config_dialog.destroy()

        # Buttons frame
        button_frame = tk.Frame(config_dialog)
        button_frame.pack(pady=10)

        save_button = tk.Button(button_frame, text="Save", command=save_wifi_config)
        save_button.pack(side=tk.LEFT, padx=5)

        cancel_button = tk.Button(button_frame, text="Cancel", command=cancel_config)
        cancel_button.pack(side=tk.LEFT, padx=5)

    def update_wpa_supplicant(self, ssid, password):
        """Update wpa_supplicant configuration file."""
        wpa_config = f"""
country=DE
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}
"""
        try:
            # Write to wpa_supplicant configuration
            with open('/etc/wpa_supplicant/wpa_supplicant.conf', 'w') as f:
                f.write(wpa_config)
            
            # Reconfigure wpa_supplicant
            subprocess.run(['sudo', 'wpa_cli', '-i', 'wlan0', 'reconfigure'], check=True)
            
            logging.info("WiFi configuration updated successfully")
        except Exception as e:
            logging.error(f"Failed to update WiFi configuration: {e}")
            raise

    def enable_hotspot(self):
        try:
            # Use subprocess for safer command execution
            subprocess.run(['sudo', '/home/pi/wifi_switcher.sh', 'hotspot'], check=True)
            logging.info("Hotspot mode enabled")
            
            # Update WiFi status
            self.wifi_status_label.config(text="WiFi: Hotspot Mode")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to enable hotspot: {e}")
            tk.messagebox.showerror("Error", "Failed to enable hotspot mode")

    def enable_wifi(self):
        # Check if WiFi is configured
        if not self.wifi_config.get('ssid'):
            tk.messagebox.showwarning("WiFi Not Configured", 
                                      "Please configure WiFi network first!")
            self.configure_wifi()
            return

        try:
            # Use subprocess for safer command execution
            subprocess.run(['sudo', '/home/pi/wifi_switcher.sh', 'wifi'], check=True)
            logging.info("WiFi mode enabled")
            
            # Update WiFi status
            self.wifi_status_label.config(text=f"WiFi: {self.wifi_config['ssid']}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to enable WiFi: {e}")
            tk.messagebox.showerror("Error", "Failed to enable WiFi mode")
        config
        # Create a confirmation dialog
        confirm = tk.Toplevel(self.root)
        confirm.title("Confirm Shutdown")
        confirm.geometry("300x150")
        confirm.transient(self.root)
        confirm.grab_set()

        label = tk.Label(confirm, text="Are you sure you want to shutdown?", 
                         font=('Helvetica', 12), wraplength=250)
        label.pack(pady=20)

        def do_shutdown():
            try:
                subprocess.run(['sudo', 'shutdown', 'now'], check=True)
            except subprocess.CalledProcessError as e:
                logging.error(f"Shutdown failed: {e}")
            confirm.destroy()

        def cancel_shutdown():
            confirm.destroy()

        # Buttons for confirmation
        frame = tk.Frame(confirm)
        frame.pack(pady=10)
        
        yes_button = tk.Button(frame, text="Yes, Shutdown", command=do_shutdown, bg='red', fg='white')
        yes_button.pack(side=tk.LEFT, padx=10)
        
        no_button = tk.Button(frame, text="Cancel", command=cancel_shutdown)
        no_button.pack(side=tk.LEFT)

    def update_stats(self):
        cpu_percent = psutil.cpu_percent(interval=1)
        self.cpu_label.config(text=f"CPU: {cpu_percent:0.1f}%")
        
        memory = psutil.virtual_memory()
        self.mem_label.config(text=f"Memory: {memory.percent:0.1f}%")
        
        disk = psutil.disk_usage('/')
        self.disk_label.config(text=f"Disk: {disk.percent:0.1f}%")
        
        self.root.after(5000, self.update_stats)

    def update_ip(self):
        try:
            iface = netifaces.gateways()['default'][netifaces.AF_INET][1]
            ip = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']
        except KeyError:
            ip = "Not Connected"
        
        self.ip_label.config(text=f"IP: {ip}")
        
        qr = qrcode.make(f"http://{ip}")
        qr = qr.resize((100, 100))
        self.qr_img = ImageTk.PhotoImage(qr)
        self.qr_label.config(image=self.qr_img)
        
        self.root.after(30000, self.update_ip)  # Update every 30 seconds

if __name__ == "__main__":
    app = SystemDisplay()
    app.root.mainloop()
