#!/usr/bin/env python3
"""
Meshtastic GUI Installer for Raspberry Pi OS
Provides graphical interface for Meshtastic installation and configuration
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import os
import sys
import subprocess
import json
import shutil
import logging
import re
import threading
import queue
import time
import select
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Tuple, List

# Configuration constants
REPO_DIR = "/etc/apt/sources.list.d"
GPG_DIR = "/etc/apt/trusted.gpg.d"
OS_VERSION = "Raspbian_12"
REPO_PREFIX = "network:Meshtastic"
PKG_NAME = "meshtasticd"
CONFIG_DIR = "/etc/meshtasticd"
BACKUP_DIR = "/etc/meshtasticd_backups"
LOG_FILE = "/var/log/meshtastic_installer.log"

class MeshtasticGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Meshtastic Configuration Tool")
        self.root.geometry("1000x800")  # Increased height from 700 to 800
        
        # Initialize threading first
        self.output_queue = queue.Queue()
        
        # Setup logging
        self.setup_logging()
        
        # Hardware detection
        self.pi_model = None
        self.hat_info = None
        self.current_channel = None
        
        # Detect hardware on startup
        self.detect_hardware()
        
        # Create GUI
        self.create_gui()
        
        # Start checking for output updates
        self.check_output_queue()
        
        # Update status indicators
        self.update_status_indicators()
        
    def setup_logging(self):
        """Setup logging with queue handler for GUI"""
        # Create a custom handler that writes to queue
        class QueueHandler(logging.Handler):
            def __init__(self, queue):
                super().__init__()
                self.queue = queue
                
            def emit(self, record):
                try:
                    # Format message without timestamp for GUI
                    msg = record.getMessage()
                    self.queue.put(msg)
                except Exception:
                    pass
        
        # Clear any existing handlers
        logging.getLogger().handlers.clear()
        
        # Setup logging with queue handler
        queue_handler = QueueHandler(self.output_queue)
        queue_handler.setLevel(logging.INFO)
        
        # Try to add file handler too (with full format for file)
        handlers = [queue_handler]
        try:
            os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
            file_handler = logging.FileHandler(LOG_FILE)
            file_handler.setLevel(logging.INFO)
            file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            handlers.append(file_handler)
        except:
            pass
        
        logging.basicConfig(
            level=logging.INFO,
            handlers=handlers,
            force=True
        )
        
        # Test that logging works
        logging.info("Meshtastic GUI started - logging system initialized")
            
    def create_gui(self):
        """Create the main GUI interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=0)  # Buttons column - fixed width
        main_frame.columnconfigure(1, weight=1)  # Output column - expandable
        main_frame.rowconfigure(2, weight=1)     # Make buttons/output row expandable
        
        # Title
        title_label = ttk.Label(main_frame, text="Meshtastic Configuration Tool", 
                               font=("TkDefaultFont", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Hardware info
        self.create_hardware_info(main_frame, row=1)
        
        # Control buttons
        self.create_control_buttons(main_frame, start_row=2)
        
        # Actions frame
        self.create_actions_buttons(main_frame, start_row=3)
        
        # Output text area (to the right of buttons)
        self.create_output_area(main_frame, row=2, column=1)
        
    def create_hardware_info(self, parent, row):
        """Create hardware information display"""
        info_frame = ttk.LabelFrame(parent, text="Hardware Information", padding="10")
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Pi model
        pi_text = self.pi_model if self.pi_model else "Unknown"
        ttk.Label(info_frame, text=f"Raspberry Pi: {pi_text}").grid(row=0, column=0, sticky=tk.W)
        
        # HAT info
        if self.hat_info:
            hat_text = f"{self.hat_info.get('vendor', 'Unknown')} {self.hat_info.get('product', 'Unknown')}"
            ttk.Label(info_frame, text=f"HAT Detected: {hat_text}").grid(row=1, column=0, sticky=tk.W)
        else:
            ttk.Label(info_frame, text="HAT Detected: None").grid(row=1, column=0, sticky=tk.W)
            
    def create_control_buttons(self, parent, start_row):
        """Create control buttons with status indicators"""
        button_frame = ttk.LabelFrame(parent, text="Configuration Options", padding="10")
        button_frame.grid(row=start_row, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        
        # Button 1: Install/Remove meshtasticd
        row = 0
        ttk.Button(button_frame, text="Install/Remove meshtasticd", 
                  command=self.handle_install_remove, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status1 = ttk.Label(button_frame, text="Checking...", foreground="orange")
        self.status1.grid(row=row, column=1, padx=(10, 0))
        
        # Button 2: Enable SPI
        row += 1
        ttk.Button(button_frame, text="Enable SPI", 
                  command=self.handle_enable_spi, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status2 = ttk.Label(button_frame, text="Checking...", foreground="orange")
        self.status2.grid(row=row, column=1, padx=(10, 0))
        
        # Button 3: Enable I2C
        row += 1
        ttk.Button(button_frame, text="Enable I2C", 
                  command=self.handle_enable_i2c, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status3 = ttk.Label(button_frame, text="Checking...", foreground="orange")
        self.status3.grid(row=row, column=1, padx=(10, 0))
        
        # Button 3.5: Enable GPS/UART
        row += 1
        ttk.Button(button_frame, text="Enable GPS/UART", 
                  command=self.handle_enable_gps_uart, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status3_5 = ttk.Label(button_frame, text="Checking...", foreground="orange")
        self.status3_5.grid(row=row, column=1, padx=(10, 0))
        
        # Button 4: Enable HAT Specific Options
        row += 1
        ttk.Button(button_frame, text="Enable HAT Specific Options", 
                  command=self.handle_hat_specific, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status4 = ttk.Label(button_frame, text="Checking...", foreground="orange")
        self.status4.grid(row=row, column=1, padx=(10, 0))
        
        # Button 5: Set HAT Config
        row += 1
        ttk.Button(button_frame, text="Set HAT Config", 
                  command=self.handle_hat_config, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status5 = ttk.Label(button_frame, text="Checking...", foreground="orange")
        self.status5.grid(row=row, column=1, padx=(10, 0))
        
        # Button 6: Edit Config
        row += 1
        ttk.Button(button_frame, text="Edit Config", 
                  command=self.handle_edit_config, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status6 = ttk.Label(button_frame, text="Checking...", foreground="orange")
        self.status6.grid(row=row, column=1, padx=(10, 0))
                  
    def create_actions_buttons(self, parent, start_row):
        """Create actions buttons"""
        actions_frame = ttk.LabelFrame(parent, text="Actions", padding="10")
        actions_frame.grid(row=start_row, column=0, sticky=(tk.W, tk.E, tk.N), padx=(0, 10), pady=(10, 0))
        
        # Enable meshtasticd on boot button
        row = 0
        ttk.Button(actions_frame, text="Enable meshtasticd on boot", 
                  command=self.handle_enable_boot, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status_boot = ttk.Label(actions_frame, text="Checking...", foreground="orange")
        self.status_boot.grid(row=row, column=1, padx=(10, 0))
        
        # Start/Stop meshtasticd button
        row += 1
        ttk.Button(actions_frame, text="Start/Stop meshtasticd", 
                  command=self.handle_start_stop, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status_service = ttk.Label(actions_frame, text="Checking...", foreground="orange")
        self.status_service.grid(row=row, column=1, padx=(10, 0))
        
        # Install Python CLI button
        row += 1
        ttk.Button(actions_frame, text="Install Python CLI", 
                  command=self.handle_install_python_cli, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status_python_cli = ttk.Label(actions_frame, text="Checking...", foreground="orange")
        self.status_python_cli.grid(row=row, column=1, padx=(10, 0))
        
        # Send Message button
        row += 1
        ttk.Button(actions_frame, text="Send Message", 
                  command=self.handle_send_message, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status_send_message = ttk.Label(actions_frame, text="CLI Required", foreground="orange")
        self.status_send_message.grid(row=row, column=1, padx=(10, 0))
        
        # Set Region button
        row += 1
        ttk.Button(actions_frame, text="Set Region", 
                  command=self.handle_set_region, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status_region = ttk.Label(actions_frame, text="Checking...", foreground="orange")
        self.status_region.grid(row=row, column=1, padx=(10, 0))
        
        # Enable/Disable Avahi button
        row += 1
        ttk.Button(actions_frame, text="Enable/Disable Avahi", 
                  command=self.handle_enable_disable_avahi, width=25).grid(row=row, column=0, pady=5, sticky=tk.W)
        self.status_avahi = ttk.Label(actions_frame, text="Checking...", foreground="orange")
        self.status_avahi.grid(row=row, column=1, padx=(10, 0))
        
    def create_refresh_button(self, parent, row):
        """Create refresh button at bottom"""
        refresh_frame = ttk.Frame(parent)
        refresh_frame.grid(row=row, column=0, columnspan=2, pady=(20, 0))
        
        ttk.Button(refresh_frame, text="Refresh Status", 
                  command=self.update_status_indicators, width=25).pack()
                  
    def create_output_area(self, parent, row, column=0):
        """Create output text area"""
        output_frame = ttk.LabelFrame(parent, text="Output", padding="10")
        output_frame.grid(row=row, column=column, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0), rowspan=3)
        output_frame.columnconfigure(0, weight=1)
        output_frame.rowconfigure(0, weight=1)
        
        # Text widget with scrollbar
        self.output_text = scrolledtext.ScrolledText(output_frame, height=20, state=tk.DISABLED)
        self.output_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Clear button
        ttk.Button(output_frame, text="Clear Output", 
                  command=self.clear_output).grid(row=1, column=0, pady=(5, 0), sticky=tk.E)
                  
    def check_python_cli_status(self):
        """Check if Meshtastic Python CLI is installed"""
        try:
            # Check if meshtastic command is available via pipx
            result = subprocess.run(["meshtastic", "--version"], capture_output=True, text=True)
            return result.returncode == 0
        except:
            try:
                # Fallback: check if pipx has meshtastic installed
                result = subprocess.run(["pipx", "list"], capture_output=True, text=True)
                return "meshtastic" in result.stdout
            except:
                return False

    def check_lora_region_status(self):
        """Check current LoRa region setting"""
        try:
            if not self.check_python_cli_status():
                return "CLI Not Available"
                
            result = subprocess.run(
                ["meshtastic", "--host", "localhost", "--get", "lora.region"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                
                # Log the raw output for debugging
                logging.info(f"Raw CLI output for region: '{output}'")
                
                # Define region mapping for numeric values
                region_map = {
                    "0": "UNSET",
                    "1": "US", 
                    "2": "EU_433",
                    "3": "EU_868",
                    "4": "CN",
                    "5": "JP",
                    "6": "ANZ",
                    "7": "KR",
                    "8": "TW",
                    "9": "RU",
                    "10": "IN",
                    "11": "NZ_865",
                    "12": "TH",
                    "13": "UA_433",
                    "14": "UA_868",
                    "15": "MY_433",
                    "16": "MY_919",
                    "17": "SG_923"
                }
                
                # Valid region codes
                valid_regions = ["UNSET", "US", "EU_868", "EU_433", "ANZ", "CN", "IN", "JP", "KR", 
                               "MY_433", "MY_919", "RU", "SG_923", "TH", "TW", "UA_433", "UA_868"]
                
                lines = output.split('\n')
                for line in lines:
                    line = line.strip()
                    
                    # Skip empty lines and connection messages
                    if not line or any(skip in line.lower() for skip in ['connected', 'requesting', 'node info']):
                        continue
                    
                    # Check if line is just a region code
                    if line in valid_regions:
                        logging.info(f"Found direct region code: {line}")
                        return line
                    
                    # Check for "lora.region: X" format
                    if "lora.region:" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            value = parts[1].strip()
                            logging.info(f"Found lora.region value: '{value}'")
                            
                            # Check if it's a direct region code
                            if value in valid_regions:
                                return value
                            
                            # Check if it's a numeric value to map
                            if value in region_map:
                                mapped_region = region_map[value]
                                logging.info(f"Mapped numeric value {value} to {mapped_region}")
                                return mapped_region
                    
                    # Check for any numeric value that might be a region
                    if line.isdigit() and line in region_map:
                        mapped_region = region_map[line]
                        logging.info(f"Found standalone numeric region {line} -> {mapped_region}")
                        return mapped_region
                
                # If we get here, log what we couldn't parse
                logging.warning(f"Could not parse region from output: '{output}'")
                return "Unknown"
            else:
                logging.error(f"CLI command failed with return code {result.returncode}")
                return "Error"
        except Exception as e:
            logging.error(f"Exception checking region status: {e}")
            return "Error"

    def check_avahi_status(self):
        """Check if Avahi is installed and configured"""
        try:
            # Check if avahi-daemon is installed
            result = subprocess.run(["dpkg", "-l", "avahi-daemon"], capture_output=True, text=True)
            avahi_installed = result.returncode == 0 and "ii" in result.stdout
            
            if not avahi_installed:
                return False
                
            # Check if meshtastic service file exists
            service_file = "/etc/avahi/services/meshtastic.service"
            return os.path.exists(service_file)
            
        except:
            return False
        """Check if Avahi is installed and configured"""
        try:
            # Check if avahi-daemon is installed
            result = subprocess.run(["dpkg", "-l", "avahi-daemon"], capture_output=True, text=True)
            avahi_installed = result.returncode == 0 and "ii" in result.stdout
            
            if not avahi_installed:
                return False
                
            # Check if meshtastic service file exists
            service_file = "/etc/avahi/services/meshtastic.service"
            return os.path.exists(service_file)
            
        except:
            return False
            
    def check_meshtasticd_boot_status(self):
        """Check if meshtasticd is enabled to start on boot"""
        try:
            result = subprocess.run(["systemctl", "is-enabled", PKG_NAME], capture_output=True, text=True)
            return result.returncode == 0 and result.stdout.strip() == "enabled"
        except:
            return False
            
    def check_meshtasticd_service_status(self):
        """Check if meshtasticd service is currently running"""
        try:
            result = subprocess.run(["systemctl", "is-active", PKG_NAME], capture_output=True, text=True)
            return result.returncode == 0 and result.stdout.strip() == "active"
        except:
            return False
                  
    def append_output(self, text):
        """Append text to output area"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.insert(tk.END, text + "\n")
        self.output_text.see(tk.END)
        self.output_text.config(state=tk.DISABLED)
        
    def clear_output(self):
        """Clear output area"""
        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete(1.0, tk.END)
        self.output_text.config(state=tk.DISABLED)
        
    def check_output_queue(self):
        """Check for new output messages"""
        try:
            # Process all messages in queue
            while True:
                try:
                    message = self.output_queue.get_nowait()
                    self.append_output(message)
                except queue.Empty:
                    break
                    
        except Exception as e:
            print(f"Error processing output queue: {e}")
        finally:
            # Schedule next check
            self.root.after(100, self.check_output_queue)
            
    def run_command_async(self, cmd: List[str], callback=None):
        """Run command in background thread"""
        def worker():
            try:
                logging.info(f"Running command: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, check=False)
                
                if result.returncode == 0:
                    if result.stdout.strip():
                        logging.info(f"Command output: {result.stdout.strip()}")
                else:
                    logging.error(f"Command failed with code {result.returncode}")
                    if result.stderr.strip():
                        logging.error(f"Error: {result.stderr.strip()}")
                        
                if callback:
                    self.root.after(0, callback, result.returncode == 0)
                    
            except Exception as e:
                logging.error(f"Command exception: {e}")
                if callback:
                    self.root.after(0, callback, False)
                    
        threading.Thread(target=worker, daemon=True).start()
        
    def detect_hardware(self):
        """Detect Pi model and HAT"""
        # Detect Pi model
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    self.pi_model = f.read().strip().replace('\x00', '')
        except:
            pass
            
        # Detect HAT
        try:
            hat_info = {}
            if os.path.exists("/proc/device-tree/hat/product"):
                with open("/proc/device-tree/hat/product", "r") as f:
                    hat_info["product"] = f.read().strip().replace('\x00', '')
            if os.path.exists("/proc/device-tree/hat/vendor"):
                with open("/proc/device-tree/hat/vendor", "r") as f:
                    hat_info["vendor"] = f.read().strip().replace('\x00', '')
            if hat_info:
                self.hat_info = hat_info
        except:
            pass
            
    def is_pi5(self) -> bool:
        """Check if this is a Raspberry Pi 5"""
        if self.pi_model:
            return "Raspberry Pi 5" in self.pi_model
        return False
        
    def check_meshtasticd_status(self):
        """Check if meshtasticd is installed"""
        try:
            # First check with dpkg
            result = subprocess.run(["dpkg", "-l", PKG_NAME], capture_output=True, text=True)
            dpkg_installed = result.returncode == 0 and "ii" in result.stdout
            
            # Also check if the binary exists
            binary_exists = os.path.exists("/usr/sbin/meshtasticd") or os.path.exists("/usr/bin/meshtasticd")
            
            # Check with which command as fallback
            which_found = False
            try:
                result = subprocess.run(["which", PKG_NAME], capture_output=True, text=True)
                which_found = result.returncode == 0
            except:
                pass
            
            return dpkg_installed or binary_exists or which_found
        except:
            return False
            
    def check_spi_status(self):
        """Check if SPI is enabled in config and devices exist"""
        # Check if devices exist
        devices_exist = os.path.exists("/dev/spidev0.0") or os.path.exists("/dev/spidev0.1")
        
        # Check if configured in boot config
        config_enabled = False
        try:
            with open("/boot/firmware/config.txt", "r") as f:
                config_content = f.read()
            # Check for both SPI parameters
            has_spi_param = "dtparam=spi=on" in config_content
            has_spi_overlay = "dtoverlay=spi0-0cs" in config_content
            config_enabled = has_spi_param and has_spi_overlay
        except:
            pass
            
        return devices_exist and config_enabled
        
    def check_i2c_status(self):
        """Check if I2C is enabled in config and devices exist"""
        # Check if devices exist
        devices_exist = any(os.path.exists(f"/dev/i2c-{i}") for i in range(0, 10))
        
        # Check if configured in boot config
        config_enabled = False
        try:
            with open("/boot/firmware/config.txt", "r") as f:
                config_content = f.read()
            config_enabled = "dtparam=i2c_arm=on" in config_content
        except:
            pass
            
        return devices_exist and config_enabled
        
    def check_gps_uart_status(self):
        """Check if GPS/UART is enabled in config"""
        try:
            with open("/boot/firmware/config.txt", "r") as f:
                config_content = f.read()
            
            # Check for enable_uart=1 (required for all Pi models)
            has_uart_enabled = "enable_uart=1" in config_content
            
            # For Pi 5, also check for uart0 overlay
            if self.is_pi5():
                has_uart0_overlay = "dtoverlay=uart0" in config_content
                return has_uart_enabled and has_uart0_overlay
            else:
                # For Pi 4 and earlier, only enable_uart=1 is needed
                return has_uart_enabled
                
        except:
            return False
        
    def check_hat_specific_status(self):
        """Check if HAT specific options are configured"""
        if not self.hat_info or self.hat_info.get('product') != 'MeshAdv Mini':
            return False
            
        # Check for GPIO and PPS configuration
        try:
            # Check if GPIO pins are configured in config.txt
            with open("/boot/firmware/config.txt", "r") as f:
                config_content = f.read()
                
            # Look for MeshAdv Mini specific configurations
            has_gpio_config = "gpio=4=op,dh" in config_content
            has_pps_config = "pps-gpio,gpiopin=17" in config_content
            
            return has_gpio_config and has_pps_config
        except:
            return False
            
    def check_hat_config_status(self):
        """Check if HAT config file exists in config.d"""
        config_d_dir = f"{CONFIG_DIR}/config.d"
        if not os.path.exists(config_d_dir):
            return False
            
        try:
            # Check if any config files exist in config.d
            config_files = list(Path(config_d_dir).glob("*.yaml"))
            return len(config_files) > 0
        except:
            return False
            
    def check_config_exists(self):
        """Check if config file exists"""
        return (os.path.exists(f"{CONFIG_DIR}/config.yaml") or 
                os.path.exists(f"{CONFIG_DIR}/config.json"))
                
    def update_status_indicators(self):
        """Update all status indicators"""
        # Status 1: meshtasticd
        if self.check_meshtasticd_status():
            self.status1.config(text="Installed", foreground="green")
        else:
            self.status1.config(text="Not Installed", foreground="red")
            
        # Status 2: SPI
        if self.check_spi_status():
            self.status2.config(text="Enabled", foreground="green")
        else:
            self.status2.config(text="Disabled", foreground="red")
            
        # Status 3: I2C
        if self.check_i2c_status():
            self.status3.config(text="Enabled", foreground="green")
        else:
            self.status3.config(text="Disabled", foreground="red")
            
        # Status 3.5: GPS/UART
        if self.check_gps_uart_status():
            self.status3_5.config(text="Enabled", foreground="green")
        else:
            self.status3_5.config(text="Disabled", foreground="red")
            
        # Status 4: HAT Specific
        if self.check_hat_specific_status():
            self.status4.config(text="Configured", foreground="green")
        else:
            self.status4.config(text="Not Configured", foreground="red")
            
        # Status 5: HAT Config
        if self.check_hat_config_status():
            self.status5.config(text="Set", foreground="green")
        else:
            self.status5.config(text="Not Set", foreground="red")
            
        # Status 6: Config exists
        if self.check_config_exists():
            self.status6.config(text="Exists", foreground="green")
        else:
            self.status6.config(text="Missing", foreground="red")
            
        # Status Python CLI: Python CLI installation
        if self.check_python_cli_status():
            self.status_python_cli.config(text="Installed", foreground="green")
            # Update send message status when CLI is available
            self.status_send_message.config(text="Ready", foreground="green")
        else:
            self.status_python_cli.config(text="Not Installed", foreground="red")
            self.status_send_message.config(text="CLI Required", foreground="red")
            
        # Status Region: LoRa region setting
        region_status = self.check_lora_region_status()
        if region_status == "UNSET":
            self.status_region.config(text="UNSET", foreground="red")
        elif region_status in ["US", "EU_868", "EU_433", "ANZ", "CN", "IN", "JP", "KR", 
                               "MY_433", "MY_919", "RU", "SG_923", "TH", "TW", "UA_433", "UA_868"]:
            self.status_region.config(text=region_status, foreground="green")
        elif region_status == "CLI Not Available":
            self.status_region.config(text="CLI Required", foreground="red")
        elif region_status == "Error":
            self.status_region.config(text="Error", foreground="orange")
        else:
            # Show the actual region code even if it's not in our common list
            self.status_region.config(text=region_status, foreground="blue")
            
        # Status Avahi: Avahi service
        if self.check_avahi_status():
            self.status_avahi.config(text="Enabled", foreground="green")
        else:
            self.status_avahi.config(text="Disabled", foreground="red")
            
        # Status Boot: meshtasticd boot enable
        if self.check_meshtasticd_boot_status():
            self.status_boot.config(text="Enabled", foreground="green")
        else:
            self.status_boot.config(text="Disabled", foreground="red")
            
        # Status Service: meshtasticd service running
        if self.check_meshtasticd_service_status():
            self.status_service.config(text="Running", foreground="green")
        else:
            self.status_service.config(text="Stopped", foreground="red")

    # APT Lock Handling Methods
    def check_and_fix_apt_locks(self):
        """Check for and attempt to fix apt lock issues"""
        try:
            logging.info("Checking for apt lock issues...")
            
            # Check if dpkg is interrupted
            result = subprocess.run(["sudo", "dpkg", "--audit"], capture_output=True, text=True)
            if result.returncode != 0 or result.stdout.strip():
                logging.warning("⚠️ dpkg appears to be interrupted, attempting to fix...")
                # Try to configure any interrupted packages
                result = subprocess.run(["sudo", "dpkg", "--configure", "-a"], 
                                      capture_output=True, text=True, 
                                      input="n\n", timeout=60)  # Default to keep current config
                if result.returncode == 0:
                    logging.info("✅ dpkg configuration completed")
                else:
                    logging.warning(f"⚠️ dpkg configure had issues: {result.stderr}")
            
            # Check for lock files and processes
            lock_files = [
                "/var/lib/dpkg/lock",
                "/var/lib/dpkg/lock-frontend", 
                "/var/cache/apt/archives/lock"
            ]
            
            locks_found = []
            for lock_file in lock_files:
                if os.path.exists(lock_file):
                    try:
                        # Try to see if the lock is actually held
                        result = subprocess.run(["sudo", "lsof", lock_file], 
                                              capture_output=True, text=True)
                        if result.returncode == 0 and result.stdout.strip():
                            locks_found.append(lock_file)
                            logging.warning(f"⚠️ Lock file {lock_file} is held by process")
                    except:
                        pass
            
            if locks_found:
                logging.info("Attempting to kill apt-related processes...")
                # Kill any hanging apt processes
                subprocess.run(["sudo", "killall", "-9", "apt", "apt-get", "dpkg"], 
                             capture_output=True, text=True)
                
                # Wait a moment for processes to die
                time.sleep(2)
                
                # Remove stale lock files if no processes are using them
                for lock_file in locks_found:
                    try:
                        result = subprocess.run(["sudo", "lsof", lock_file], 
                                              capture_output=True, text=True)
                        if result.returncode != 0:  # No process using the lock
                            subprocess.run(["sudo", "rm", "-f", lock_file], check=True)
                            logging.info(f"✅ Removed stale lock file: {lock_file}")
                    except:
                        pass
            
            return True
            
        except Exception as e:
            logging.error(f"Error checking/fixing apt locks: {e}")
            return False

    def safe_apt_command(self, cmd_args, timeout=300, interactive_input=None):
        """Run apt command with better error handling and lock detection"""
        max_retries = 3
        retry_delay = 10
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logging.info(f"Retry attempt {attempt + 1}/{max_retries} for apt command...")
                    # Check and fix locks before retry
                    self.check_and_fix_apt_locks()
                    time.sleep(retry_delay)
                
                # Run the command
                if interactive_input:
                    result = subprocess.run(cmd_args, capture_output=True, text=True, 
                                          timeout=timeout, input=interactive_input)
                else:
                    result = subprocess.run(cmd_args, capture_output=True, text=True, 
                                          timeout=timeout)
                
                # Check for lock-related errors
                if "Could not get lock" in result.stderr or "dpkg was interrupted" in result.stderr:
                    if attempt < max_retries - 1:
                        logging.warning(f"⚠️ Lock detected on attempt {attempt + 1}, will retry...")
                        continue
                    else:
                        logging.error("❌ Failed to acquire apt lock after all retries")
                        return result
                
                return result
                
            except subprocess.TimeoutExpired:
                logging.warning(f"⚠️ Command timed out on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    # Kill any hanging processes
                    subprocess.run(["sudo", "killall", "-9", "apt", "apt-get", "dpkg"], 
                                 capture_output=True, text=True)
                    continue
                else:
                    logging.error("❌ Command timed out after all retries")
                    raise
                    
            except Exception as e:
                logging.error(f"Error running apt command: {e}")
                if attempt < max_retries - 1:
                    continue
                else:
                    raise
        
        return None

    def get_config_file_choice(self):
        """Get user's choice for config file handling during installation"""
        choice_made = threading.Event()
        user_choice = {'value': 'n'}  # Default to keep current config
        
        def show_config_dialog():
            config_window = tk.Toplevel(self.root)
            config_window.title("Configuration File Conflict")
            config_window.geometry("500x400")
            config_window.transient(self.root)
            config_window.grab_set()
            
            # Make window modal and bring to front
            config_window.focus_force()
            config_window.lift()
            
            # Main message
            ttk.Label(config_window, 
                     text="Configuration File Conflict Detected",
                     font=("TkDefaultFont", 14, "bold")).pack(pady=10)
            
            ttk.Label(config_window, 
                     text="A newer version of the configuration file is available.",
                     font=("TkDefaultFont", 11)).pack(pady=5)
            
            # Explanation text
            explanation_text = """The package maintainer has provided an updated version of the configuration file, but you have a locally modified version.

Choose what to do:"""
            
            ttk.Label(config_window, text=explanation_text, 
                     wraplength=450, justify=tk.LEFT).pack(pady=10, padx=20)
            
            # Radio button selection
            selected_choice = tk.StringVar(value="n")
            
            # Frame for radio buttons
            radio_frame = ttk.Frame(config_window)
            radio_frame.pack(pady=20, padx=40, fill=tk.BOTH, expand=True)
            
            # Option N: Keep current version (recommended)
            ttk.Radiobutton(radio_frame, 
                           text="Keep your current configuration (Recommended)",
                           variable=selected_choice, 
                           value="n").pack(anchor=tk.W, pady=5)
            
            ttk.Label(radio_frame, 
                     text="• Preserves your existing settings and customizations",
                     foreground="green", font=("TkDefaultFont", 9)).pack(anchor=tk.W, padx=20)
            
            # Option Y: Install new version
            ttk.Radiobutton(radio_frame, 
                           text="Install the package maintainer's version",
                           variable=selected_choice, 
                           value="y").pack(anchor=tk.W, pady=(15, 5))
            
            ttk.Label(radio_frame, 
                     text="• Replaces your config with the new default version",
                     foreground="orange", font=("TkDefaultFont", 9)).pack(anchor=tk.W, padx=20)
            
            ttk.Label(radio_frame, 
                     text="• Your current settings will be lost",
                     foreground="red", font=("TkDefaultFont", 9)).pack(anchor=tk.W, padx=20)
            
            # Option D: Show differences
            ttk.Radiobutton(radio_frame, 
                           text="Show differences between versions",
                           variable=selected_choice, 
                           value="d").pack(anchor=tk.W, pady=(15, 5))
            
            ttk.Label(radio_frame, 
                     text="• View what has changed before deciding",
                     foreground="blue", font=("TkDefaultFont", 9)).pack(anchor=tk.W, padx=20)
            
            # Buttons
            button_frame = ttk.Frame(config_window)
            button_frame.pack(pady=20)
            
            def apply_choice():
                user_choice['value'] = selected_choice.get()
                choice_made.set()
                config_window.destroy()
            
            def cancel_install():
                user_choice['value'] = 'cancel'
                choice_made.set()
                config_window.destroy()
            
            ttk.Button(button_frame, text="Apply Choice", 
                      command=apply_choice).pack(side=tk.LEFT, padx=10)
            ttk.Button(button_frame, text="Cancel Installation", 
                      command=cancel_install).pack(side=tk.LEFT, padx=10)
        
        # Show dialog in main thread
        self.root.after(0, show_config_dialog)
        
        # Wait for user choice (with timeout)
        if choice_made.wait(timeout=300):  # 5 minute timeout
            return user_choice['value']
        else:
            logging.warning("Config choice dialog timed out, using default (keep current)")
            return 'n'
            
    # Button handlers
    def handle_install_remove(self):
        """Handle install/remove meshtasticd"""
        if self.check_meshtasticd_status():
            # Show remove dialog
            if messagebox.askyesno("Remove Meshtasticd", 
                                 "Meshtasticd is currently installed. Do you want to remove it?"):
                self.remove_meshtasticd()
        else:
            # Show install dialog
            self.install_meshtasticd()
            
    def handle_enable_spi(self):
        """Handle SPI enable/disable"""
        if self.check_spi_status():
            logging.info("SPI is already enabled")
        else:
            logging.info("Enabling SPI interface...")
            def worker():
                try:
                    # Enable SPI via raspi-config
                    subprocess.run(["sudo", "raspi-config", "nonint", "do_spi", "0"], check=False)
                    
                    # Add SPI configurations to config.txt
                    config_file = "/boot/firmware/config.txt"
                    backup_file = f"{config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # Backup original
                    subprocess.run(["sudo", "cp", config_file, backup_file], check=True)
                    logging.info(f"Backed up config.txt to {backup_file}")
                    
                    # Read current config
                    result = subprocess.run(["sudo", "cat", config_file], capture_output=True, text=True, check=True)
                    config_content = result.stdout
                    
                    # Check and add SPI parameter
                    config_updated = False
                    if "dtparam=spi=on" not in config_content:
                        config_content += "\n# SPI Configuration\ndtparam=spi=on\n"
                        config_updated = True
                        logging.info("Added SPI parameter to config.txt")
                    
                    # Check and add SPI overlay
                    if "dtoverlay=spi0-0cs" not in config_content:
                        if not config_updated:
                            config_content += "\n# SPI Configuration\n"
                        config_content += "dtoverlay=spi0-0cs\n"
                        config_updated = True
                        logging.info("Added SPI overlay to config.txt")
                    
                    if config_updated:
                        # Write updated config using sudo
                        subprocess.run(["sudo", "tee", config_file], input=config_content, text=True, check=True)
                        logging.info("SPI configuration updated in config.txt")
                    else:
                        logging.info("SPI configuration already present in config.txt")
                    
                    logging.info("SPI configuration complete. Reboot may be required.")
                    self.root.after(0, self.update_status_indicators)
                    
                except Exception as e:
                    logging.error(f"SPI configuration error: {e}")
                    
            threading.Thread(target=worker, daemon=True).start()
            
    def handle_enable_i2c(self):
        """Handle I2C enable/disable"""
        if self.check_i2c_status():
            logging.info("I2C is already enabled")
        else:
            logging.info("Enabling I2C interface...")
            def worker():
                try:
                    # Enable I2C via raspi-config
                    subprocess.run(["sudo", "raspi-config", "nonint", "do_i2c", "0"], check=False)
                    
                    # Add I2C ARM parameter to config.txt
                    config_file = "/boot/firmware/config.txt"
                    backup_file = f"{config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # Backup original if not already backed up recently
                    backup_file = f"{config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    subprocess.run(["sudo", "cp", config_file, backup_file], check=True)
                    logging.info(f"Backed up config.txt to {backup_file}")
                    
                    # Read current config
                    result = subprocess.run(["sudo", "cat", config_file], capture_output=True, text=True, check=True)
                    config_content = result.stdout
                    
                    # Add I2C ARM parameter if not present
                    if "dtparam=i2c_arm=on" not in config_content:
                        config_content += "\n# I2C Configuration\ndtparam=i2c_arm=on\n"
                        
                        # Write updated config using sudo
                        subprocess.run(["sudo", "tee", config_file], input=config_content, text=True, check=True)
                            
                        logging.info("Added I2C ARM parameter to config.txt")
                    else:
                        logging.info("I2C ARM parameter already present in config.txt")
                    
                    logging.info("I2C configuration complete. Reboot may be required.")
                    self.root.after(0, self.update_status_indicators)
                    
                except Exception as e:
                    logging.error(f"I2C configuration error: {e}")
                    
            threading.Thread(target=worker, daemon=True).start()
            
    def handle_enable_gps_uart(self):
        """Handle GPS/UART enable"""
        if self.check_gps_uart_status():
            logging.info("GPS/UART is already enabled")
        else:
            logging.info("Enabling GPS/UART interface...")
            def worker():
                try:
                    # Configure GPS/UART in config.txt
                    config_file = "/boot/firmware/config.txt"
                    backup_file = f"{config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    # Backup original
                    subprocess.run(["sudo", "cp", config_file, backup_file], check=True)
                    logging.info(f"Backed up config.txt to {backup_file}")
                    
                    # Read current config
                    result = subprocess.run(["sudo", "cat", config_file], capture_output=True, text=True, check=True)
                    config_content = result.stdout
                    
                    config_updated = False
                    
                    # Check and add enable_uart=1
                    if "enable_uart=1" not in config_content:
                        config_content += "\n# GPS/UART Configuration\nenable_uart=1\n"
                        config_updated = True
                        logging.info("Added enable_uart=1 to config.txt")
                    else:
                        logging.info("enable_uart=1 already present in config.txt")
                    
                    # Check and add uart0 overlay for Pi 5
                    if self.is_pi5() and "dtoverlay=uart0" not in config_content:
                        if not config_updated:
                            config_content += "\n# GPS/UART Configuration\n"
                        config_content += "dtoverlay=uart0\n"
                        config_updated = True
                        logging.info("Added uart0 overlay for Pi 5 to config.txt")
                    elif self.is_pi5():
                        logging.info("uart0 overlay already present in config.txt")
                    
                    if config_updated:
                        # Write updated config using sudo
                        subprocess.run(["sudo", "tee", config_file], input=config_content, text=True, check=True)
                        logging.info("GPS/UART configuration written to config.txt")
                    else:
                        logging.info("No GPS/UART configuration changes needed")
                    
                    # Disable serial console to prevent conflicts with UART
                    logging.info("Disabling serial console to prevent UART conflicts...")
                    result = subprocess.run(["sudo", "raspi-config", "nonint", "do_serial_cons", "1"], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("✅ Serial console disabled successfully")
                    else:
                        logging.warning("⚠️ Failed to disable serial console")
                    
                    logging.info("GPS/UART configuration complete. Reboot required for changes to take effect")
                    self.root.after(0, self.update_status_indicators)
                    
                except Exception as e:
                    logging.error(f"GPS/UART configuration error: {e}")
                    
            threading.Thread(target=worker, daemon=True).start()
                                 
    def handle_hat_specific(self):
        """Handle HAT specific configuration for MeshAdv Mini"""
        if not self.hat_info or self.hat_info.get('product') != 'MeshAdv Mini':
            messagebox.showwarning("No Compatible HAT", 
                                 "MeshAdv Mini HAT not detected. This function is specific to MeshAdv Mini.")
            return
            
        logging.info("Configuring MeshAdv Mini specific options...")
        
        # Configure GPIO and PPS settings
        self.configure_meshadv_mini()
        
    def handle_hat_config(self):
        """Handle HAT configuration in meshtasticd config.d"""
        try:
            available_dir = f"{CONFIG_DIR}/available.d"
            config_d_dir = f"{CONFIG_DIR}/config.d"
            
            # Create directories if they don't exist
            subprocess.run(["sudo", "mkdir", "-p", available_dir], check=True)
            subprocess.run(["sudo", "mkdir", "-p", config_d_dir], check=True)
            
            # Check for existing configs in config.d
            existing_configs = list(Path(config_d_dir).glob("*.yaml"))
            if existing_configs:
                config_names = [f.name for f in existing_configs]
                logging.info(f"Found existing configs in config.d: {', '.join(config_names)}")
                
                replace_result = messagebox.askyesno(
                    "Existing Configuration", 
                    f"Found existing configuration(s): {', '.join(config_names)}\n"
                    "Do you want to replace them?"
                )
                
                if not replace_result:
                    logging.info("User chose not to replace existing configuration")
                    return
                
                # Remove existing configs
                for config_file in existing_configs:
                    subprocess.run(["sudo", "rm", str(config_file)], check=True)
                    logging.info(f"Removed existing config: {config_file.name}")
            
            # Look for available configs (both .yaml files and folders)
            available_configs = []
            
            # Add .yaml files
            yaml_files = list(Path(available_dir).glob("*.yaml"))
            available_configs.extend(yaml_files)
            
            # Add folders (which contain configs)
            folders = [d for d in Path(available_dir).iterdir() if d.is_dir()]
            available_configs.extend(folders)
            
            if not available_configs:
                logging.warning("No configuration files or folders found in available.d")
                messagebox.showwarning(
                    "No Configurations Available",
                    f"No configuration files or folders found in {available_dir}"
                )
                return
            
            # Find matching configs for detected HAT
            matching_configs = []
            if self.hat_info:
                hat_product = self.hat_info.get('product', '').lower()
                hat_vendor = self.hat_info.get('vendor', '').lower()
                
                for config_item in available_configs:
                    config_name = config_item.name.lower()
                    if (hat_product in config_name or 
                        hat_vendor in config_name or
                        'meshadv' in config_name):
                        matching_configs.append(config_item)
            
            if len(matching_configs) == 1:
                # Show confirmation dialog for auto-selected config
                selected_config = matching_configs[0]
                
                hat_product = self.hat_info.get('product', 'Unknown') if self.hat_info else 'None'
                hat_vendor = self.hat_info.get('vendor', 'Unknown') if self.hat_info else 'Unknown'
                
                config_type = "Folder" if selected_config.is_dir() else "File"
                
                result = messagebox.askyesnocancel(
                    "Confirm HAT Configuration",
                    f"Detected HAT: {hat_vendor} {hat_product}\n\n"
                    f"Auto-selected configuration:\n{selected_config.name} ({config_type})\n\n"
                    f"Is this correct?\n\n"
                    f"Yes = Use this configuration\n"
                    f"No = Show all available options\n"
                    f"Cancel = Abort"
                )
                
                if result is True:  # Yes - use auto-selected
                    self.copy_config_item(selected_config, config_d_dir)
                elif result is False:  # No - show all options
                    self.show_all_available_configs(available_configs, config_d_dir)
                # Cancel - do nothing
                
            elif len(matching_configs) > 1:
                # Show selection dialog for multiple matches
                self.show_multiple_matches_dialog(matching_configs, available_configs, config_d_dir)
                
            else:
                # No matches or no HAT detected - show all available configs
                self.show_all_available_configs(available_configs, config_d_dir)
                
        except Exception as e:
            logging.error(f"HAT configuration error: {e}")
            messagebox.showerror("Error", f"HAT configuration failed: {e}")
        
        # Update status after operation
        self.update_status_indicators()
        
    def show_multiple_matches_dialog(self, matching_configs, available_configs, config_d_dir):
        """Show dialog for multiple matching configurations"""
        hat_product = self.hat_info.get('product', 'Unknown') if self.hat_info else 'None'
        hat_vendor = self.hat_info.get('vendor', 'Unknown') if self.hat_info else 'Unknown'
        
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Select HAT Configuration")
        selection_window.geometry("450x350")
        selection_window.transient(self.root)
        selection_window.grab_set()
        
        ttk.Label(selection_window, 
                 text=f"Detected HAT: {hat_vendor} {hat_product}",
                 font=("TkDefaultFont", 11, "bold")).pack(pady=5)
        
        ttk.Label(selection_window, 
                 text="Multiple matching configurations found:",
                 font=("TkDefaultFont", 10, "bold")).pack(pady=5)
        
        selected_var = tk.StringVar()
        
        for config in matching_configs:
            config_type = "Folder" if config.is_dir() else "File"
            ttk.Radiobutton(selection_window, 
                          text=f"{config.name} ({config_type})",
                          variable=selected_var, 
                          value=str(config)).pack(pady=2, anchor='w', padx=20)
        
        button_frame = ttk.Frame(selection_window)
        button_frame.pack(pady=20)
        
        def apply_selection():
            if selected_var.get():
                selected_config = Path(selected_var.get())
                selection_window.destroy()
                self.copy_config_item(selected_config, config_d_dir)
        
        def show_all():
            selection_window.destroy()
            self.show_all_available_configs(available_configs, config_d_dir)
        
        ttk.Button(button_frame, text="Use Selected", 
                  command=apply_selection).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Show All Options", 
                  command=show_all).pack(side=tk.LEFT, padx=5)
                  
    def show_all_available_configs(self, available_configs, config_d_dir):
        """Show all available configurations for user selection"""
        hat_product = self.hat_info.get('product', 'Unknown') if self.hat_info else 'None'
        hat_vendor = self.hat_info.get('vendor', 'Unknown') if self.hat_info else 'Unknown'
        
        selection_window = tk.Toplevel(self.root)
        selection_window.title("Select Configuration")
        selection_window.geometry("450x450")
        selection_window.transient(self.root)
        selection_window.grab_set()
        
        ttk.Label(selection_window, 
                 text=f"Detected HAT: {hat_vendor} {hat_product}",
                 font=("TkDefaultFont", 11, "bold")).pack(pady=5)
        
        if self.hat_info:
            ttk.Label(selection_window, 
                     text="No matching configs found for your HAT.",
                     foreground="orange").pack(pady=2)
        else:
            ttk.Label(selection_window, 
                     text="No HAT detected.",
                     foreground="orange").pack(pady=2)
        
        ttk.Label(selection_window, 
                 text="Select a configuration to use:",
                 font=("TkDefaultFont", 10, "bold")).pack(pady=5)
        
        selected_var = tk.StringVar()
        
        # Create scrollable frame for configs
        canvas = tk.Canvas(selection_window)
        scrollbar = ttk.Scrollbar(selection_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        for config in available_configs:
            config_type = "Folder" if config.is_dir() else "File"
            ttk.Radiobutton(scrollable_frame, 
                          text=f"{config.name} ({config_type})",
                          variable=selected_var, 
                          value=str(config)).pack(pady=2, anchor='w', padx=20)
        
        canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=10)
        scrollbar.pack(side="right", fill="y", pady=10)
        
        def apply_selection():
            if selected_var.get():
                selected_config = Path(selected_var.get())
                selection_window.destroy()
                self.copy_config_item(selected_config, config_d_dir)
        
        ttk.Button(selection_window, text="Apply Selected", 
                  command=apply_selection).pack(pady=20)
                  
    def copy_config_item(self, source_item, config_d_dir):
        """Copy the correct configuration file from available.d to config.d"""
        try:
            if source_item.is_file():
                # Copy single YAML file directly
                dest_path = Path(config_d_dir) / source_item.name
                subprocess.run(["sudo", "cp", str(source_item), str(dest_path)], check=True)
                logging.info(f"Copied {source_item.name} to config.d")
                
            else:
                # If it's a folder, look for a config file inside it
                config_files = list(source_item.glob("*.yaml"))
                if not config_files:
                    raise Exception(f"No YAML config files found in folder {source_item.name}")
                
                if len(config_files) == 1:
                    # Single config file in folder - copy it
                    config_file = config_files[0]
                    dest_path = Path(config_d_dir) / config_file.name
                    subprocess.run(["sudo", "cp", str(config_file), str(dest_path)], check=True)
                    logging.info(f"Copied {config_file.name} from folder {source_item.name} to config.d")
                    
                else:
                    # Multiple config files in folder - ask user to select
                    def show_file_selection():
                        file_window = tk.Toplevel(self.root)
                        file_window.title(f"Select Config from {source_item.name}")
                        file_window.geometry("350x250")
                        file_window.transient(self.root)
                        file_window.grab_set()
                        
                        ttk.Label(file_window, 
                                 text=f"Multiple config files found in {source_item.name}:",
                                 font=("TkDefaultFont", 10, "bold")).pack(pady=10)
                        
                        selected_file = tk.StringVar()
                        
                        for config_file in config_files:
                            ttk.Radiobutton(file_window, 
                                          text=config_file.name,
                                          variable=selected_file, 
                                          value=str(config_file)).pack(pady=2, anchor='w', padx=20)
                        
                        def copy_selected_file():
                            if selected_file.get():
                                config_file = Path(selected_file.get())
                                dest_path = Path(config_d_dir) / config_file.name
                                subprocess.run(["sudo", "cp", str(config_file), str(dest_path)], check=True)
                                logging.info(f"Copied {config_file.name} from folder {source_item.name} to config.d")
                                file_window.destroy()
                                
                                messagebox.showinfo(
                                    "Configuration Applied",
                                    f"Configuration '{config_file.name}' has been applied.\n"
                                    "Restart meshtasticd service for changes to take effect."
                                )
                                
                                self.update_status_indicators()
                        
                        ttk.Button(file_window, text="Copy Selected", 
                                  command=copy_selected_file).pack(pady=20)
                    
                    show_file_selection()
                    return
            
            messagebox.showinfo(
                "Configuration Applied",
                f"Configuration '{source_item.name}' has been applied.\n"
                "Restart meshtasticd service for changes to take effect."
            )
            
            self.update_status_indicators()
            
        except Exception as e:
            logging.error(f"Failed to copy config item: {e}")
            messagebox.showerror(
                "Configuration Error",
                f"Failed to copy configuration: {e}"
            )
            
    def handle_edit_config(self):
        """Handle config file editing with nano in terminal"""
        config_file = f"{CONFIG_DIR}/config.yaml"
        
        try:
            # Check if config file exists
            if not os.path.exists(config_file):
                if messagebox.askyesno("Create Config File", 
                                     f"Config file {config_file} does not exist.\n"
                                     "Create it now?"):
                    # Create basic config file
                    os.makedirs(CONFIG_DIR, exist_ok=True)
                    with open(config_file, 'w') as f:
                        f.write("# Meshtastic Configuration\n")
                        f.write("# Edit this file to configure your device\n\n")
                    logging.info(f"Created new config file: {config_file}")
                else:
                    return
            
            # Open nano in a new terminal window
            logging.info(f"Opening config file in nano: {config_file}")
            
            # Try different terminal emulators
            terminal_commands = [
                ["x-terminal-emulator", "-e", "sudo", "nano", config_file],
                ["gnome-terminal", "--", "sudo", "nano", config_file],
                ["xterm", "-e", "sudo", "nano", config_file],
                ["lxterminal", "-e", "sudo", "nano", config_file],
                ["mate-terminal", "-e", "sudo", "nano", config_file],
                ["konsole", "-e", "sudo", "nano", config_file],
            ]
            
            success = False
            for cmd in terminal_commands:
                try:
                    if shutil.which(cmd[0]):
                        subprocess.Popen(cmd)
                        success = True
                        logging.info(f"Opened nano with: {cmd[0]}")
                        break
                except Exception as e:
                    logging.warning(f"Failed to open with {cmd[0]}: {e}")
                    continue
            
            if not success:
                # Fallback: show instructions
                messagebox.showinfo(
                    "Edit Config File",
                    f"Could not open terminal automatically.\n\n"
                    f"Please run this command manually:\n"
                    f"sudo nano {config_file}\n\n"
                    f"Or edit the file with your preferred editor."
                )
                logging.warning("Could not open terminal automatically")
                
        except Exception as e:
            logging.error(f"Failed to edit config file: {e}")
            messagebox.showerror("Error", f"Failed to edit config file: {e}")
            
    def install_meshtasticd(self):
        """Install meshtasticd with channel selection"""
        # Channel selection dialog
        channel_window = tk.Toplevel(self.root)
        channel_window.title("Select Channel")
        channel_window.geometry("300x250")  # Increased height from 200 to 250
        channel_window.transient(self.root)
        channel_window.grab_set()
        
        selected_channel = tk.StringVar(value="beta")
        
        ttk.Label(channel_window, text="Select Meshtastic Channel:", 
                 font=("TkDefaultFont", 12, "bold")).pack(pady=10)
        
        ttk.Radiobutton(channel_window, text="Beta (Safe)", 
                       variable=selected_channel, value="beta").pack(pady=5)
        ttk.Radiobutton(channel_window, text="Alpha (Might be safe, might not)", 
                       variable=selected_channel, value="alpha").pack(pady=5)
        ttk.Radiobutton(channel_window, text="Daily (Are you mAd MAn?)", 
                       variable=selected_channel, value="daily").pack(pady=5)
        
        def install_with_channel():
            channel = selected_channel.get()
            channel_window.destroy()
            self.perform_installation(channel)
            
        ttk.Button(channel_window, text="Install", 
                  command=install_with_channel).pack(pady=20)
                  
    def perform_installation(self, channel):
        """Perform the actual installation with improved error handling"""
        def worker():
            try:
                logging.info("="*50)
                logging.info(f"STARTING MESHTASTIC INSTALLATION - {channel.upper()} CHANNEL")
                logging.info("="*50)
                
                # Pre-check for apt issues
                logging.info("Step 0/5: Checking for apt lock issues...")
                self.check_and_fix_apt_locks()
                
                # Add repository
                repo_url = f"http://download.opensuse.org/repositories/network:/Meshtastic:/{channel}/{OS_VERSION}/"
                list_file = f"{REPO_DIR}/{REPO_PREFIX}:{channel}.list"
                gpg_file = f"{GPG_DIR}/network_Meshtastic_{channel}.gpg"
                
                # Create repository file
                logging.info(f"Step 1/5: Creating repository configuration...")
                repo_content = f"deb {repo_url} /\n"
                result = subprocess.run(["sudo", "tee", list_file], input=repo_content, text=True, capture_output=True)
                if result.returncode != 0:
                    logging.error(f"❌ Failed to create repository file")
                    return
                logging.info(f"✅ Repository file created successfully")
                
                # Fetch GPG key
                logging.info(f"Step 2/5: Downloading GPG key from {channel} repository...")
                result = subprocess.run(["curl", "-fsSL", f"{repo_url}Release.key"], 
                                      capture_output=True, text=True)
                
                if result.returncode != 0:
                    logging.error(f"❌ Failed to download GPG key")
                    return
                logging.info(f"✅ GPG key downloaded successfully")
                
                # Process GPG key
                logging.info(f"Step 3/5: Processing and installing GPG key...")
                gpg_process = subprocess.Popen(
                    ["gpg", "--dearmor"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                
                gpg_output, gpg_error = gpg_process.communicate(input=result.stdout.encode('utf-8'))
                
                if gpg_process.returncode != 0:
                    logging.error(f"❌ GPG key processing failed")
                    return
                
                # Write GPG key
                write_result = subprocess.run(["sudo", "tee", gpg_file], input=gpg_output, capture_output=True)
                if write_result.returncode != 0:
                    logging.error(f"❌ Failed to install GPG key")
                    return
                logging.info(f"✅ GPG key installed successfully")
                
                # Update package list with safe apt command
                logging.info(f"Step 4/5: Updating package database...")
                result = self.safe_apt_command(["sudo", "apt", "update"], timeout=120)
                if result and result.returncode != 0:
                    logging.warning(f"⚠️ Package update had some issues, continuing anyway")
                else:
                    logging.info(f"✅ Package database updated successfully")
                
                # Check if config file exists (might need user input during install)
                config_exists = os.path.exists(f"{CONFIG_DIR}/config.yaml")
                
                # Install package with smart config handling
                logging.info(f"Step 5/5: Installing meshtasticd package...")
                logging.info(f"This may take a few minutes depending on your internet connection...")
                
                if config_exists:
                    logging.info("Existing configuration detected - handling potential config file prompts...")
                    
                    # Use DEBIAN_FRONTEND=noninteractive with a fallback for prompts
                    env = os.environ.copy()
                    env['DEBIAN_FRONTEND'] = 'noninteractive'
                    env['APT_LISTCHANGES_FRONTEND'] = 'none'
                    
                    # Try non-interactive first
                    logging.info("Attempting non-interactive installation...")
                    result = subprocess.run(
                        ["sudo", "-E", "apt", "install", "-y", "-o", "Dpkg::Options::=--force-confdef", 
                         "-o", "Dpkg::Options::=--force-confold", PKG_NAME],
                        capture_output=True, text=True, timeout=300, env=env
                    )
                    
                    if result.returncode == 0:
                        logging.info(f"✅ Package installed successfully (non-interactive)")
                    else:
                        # Non-interactive failed, try with user interaction
                        logging.warning("Non-interactive installation failed, trying interactive mode...")
                        logging.info(f"Non-interactive error: {result.stderr}")
                        
                        # Get more detailed error information first
                        logging.info("Checking dpkg status for more details...")
                        dpkg_result = subprocess.run(["sudo", "dpkg", "--configure", "-a"], 
                                                   capture_output=True, text=True, input="n\n")
                        if dpkg_result.stdout.strip():
                            logging.info(f"dpkg configure output: {dpkg_result.stdout}")
                        if dpkg_result.stderr.strip():
                            logging.warning(f"dpkg configure warnings: {dpkg_result.stderr}")
                        
                        # Now try interactive installation
                        logging.info("Starting interactive installation process...")
                        install_process = subprocess.Popen(
                            ["sudo", "apt", "install", "-y", PKG_NAME],
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,  # Combine stderr with stdout
                            text=True,
                            bufsize=1,  # Line buffered
                            universal_newlines=True
                        )
                        
                        # Monitor output for config prompts
                        output_lines = []
                        config_prompt_detected = False
                        
                        try:
                            # Read output line by line with timeout
                            timeout_count = 0
                            max_timeout = 60  # 60 seconds to detect prompt
                            
                            while install_process.poll() is None and timeout_count < max_timeout:
                                # Check if there's output ready
                                ready, _, _ = select.select([install_process.stdout], [], [], 1.0)
                                
                                if ready:
                                    line = install_process.stdout.readline()
                                    if line:
                                        output_lines.append(line.strip())
                                        logging.info(f"Install output: {line.strip()}")
                                        
                                        # Check for config file prompt indicators
                                        if any(indicator in line.lower() for indicator in [
                                            "configuration file", "config.yaml", "what would you like to do",
                                            "package distributor", "modified", "your options are"
                                        ]):
                                            config_prompt_detected = True
                                            logging.info("🔍 Configuration file prompt detected!")
                                            break
                                    timeout_count = 0  # Reset timeout if we got output
                                else:
                                    timeout_count += 1
                            
                            if config_prompt_detected:
                                # Get user's choice through dialog
                                user_choice = self.get_config_file_choice()
                                
                                if user_choice == 'cancel':
                                    install_process.terminate()
                                    logging.info("Installation cancelled by user")
                                    return
                                
                                logging.info(f"User chose: {user_choice}")
                                
                                # Send the choice to the process
                                install_process.stdin.write(f"{user_choice}\n")
                                install_process.stdin.flush()
                                
                                # Wait for completion
                                stdout, _ = install_process.communicate(timeout=300)
                                result_code = install_process.returncode
                                
                                # Log remaining output
                                if stdout:
                                    for line in stdout.split('\n'):
                                        if line.strip():
                                            logging.info(f"Install output: {line.strip()}")
                                
                            else:
                                # No prompt detected, wait for completion
                                stdout, _ = install_process.communicate(timeout=300)
                                result_code = install_process.returncode
                                
                                # Log all output
                                if stdout:
                                    for line in stdout.split('\n'):
                                        if line.strip():
                                            logging.info(f"Install output: {line.strip()}")
                            
                            if result_code == 0:
                                logging.info(f"✅ Package installed successfully (interactive mode)")
                            else:
                                logging.error(f"❌ Interactive installation also failed with code: {result_code}")
                                # Log the captured output for debugging
                                logging.error("Complete installation output:")
                                for line in output_lines:
                                    logging.error(f"  {line}")
                                return
                                
                        except subprocess.TimeoutExpired:
                            install_process.kill()
                            logging.error("❌ Installation timed out")
                            return
                        except Exception as e:
                            install_process.kill()
                            logging.error(f"❌ Installation error: {e}")
                            return
                else:
                    # No existing config, should install without prompts
                    env = os.environ.copy()
                    env['DEBIAN_FRONTEND'] = 'noninteractive'
                    
                    result = subprocess.run(
                        ["sudo", "-E", "apt", "install", "-y", PKG_NAME],
                        capture_output=True, text=True, timeout=600, env=env
                    )
                    
                    if result.returncode == 0:
                        logging.info(f"✅ Package installed successfully")
                    else:
                        logging.error(f"❌ Installation failed")
                        if result.stderr.strip():
                            logging.error(f"Error details: {result.stderr}")
                        if result.stdout.strip():
                            logging.error(f"Output: {result.stdout}")
                        return
                
                logging.info(f"✅ INSTALLATION COMPLETED SUCCESSFULLY!")
                logging.info(f"Meshtasticd {channel} channel has been installed")
                logging.info(f"You can now configure and start the service")
                logging.info("="*50)
                
                # Force status update after a brief delay to ensure package is registered
                def delayed_update():
                    self.update_status_indicators()
                    
                self.root.after(2000, delayed_update)  # Wait 2 seconds then update
                    
            except Exception as e:
                logging.error(f"❌ INSTALLATION ERROR: {e}")
                logging.info("="*50)
                
        threading.Thread(target=worker, daemon=True).start()
        
    def remove_meshtasticd(self):
        """Remove meshtasticd with improved error handling"""
        def worker():
            try:
                logging.info("="*50)
                logging.info("STARTING MESHTASTIC REMOVAL")
                logging.info("="*50)
                
                # Pre-check for apt issues
                logging.info("Step 0/4: Checking for apt lock issues...")
                self.check_and_fix_apt_locks()
                
                # Stop service
                logging.info("Step 1/4: Stopping meshtasticd service...")
                result = subprocess.run(["sudo", "systemctl", "stop", PKG_NAME], capture_output=True, text=True)
                if result.returncode == 0:
                    logging.info("✅ Service stopped successfully")
                else:
                    logging.info("ℹ️ Service was not running or already stopped")
                
                logging.info("Step 2/4: Disabling meshtasticd service...")
                result = subprocess.run(["sudo", "systemctl", "disable", PKG_NAME], capture_output=True, text=True)
                if result.returncode == 0:
                    logging.info("✅ Service disabled successfully")
                else:
                    logging.info("ℹ️ Service was not enabled or already disabled")
                
                # Remove package with improved error handling
                logging.info("Step 3/4: Removing meshtasticd package...")
                logging.info("This may take a moment...")
                
                # Use the safe apt command with automatic "n" response for config questions
                result = self.safe_apt_command(["sudo", "apt", "remove", "-y", PKG_NAME], 
                                             timeout=300, interactive_input="n\n")
                
                if result and result.returncode == 0:
                    logging.info("✅ Package removed successfully")
                    
                    # Remove repository files
                    logging.info("Step 4/4: Cleaning up repository files...")
                    try:
                        repo_files = list(Path(REPO_DIR).glob(f"{REPO_PREFIX}:*.list"))
                        gpg_files = list(Path(GPG_DIR).glob("network_Meshtastic_*.gpg"))
                        
                        files_removed = 0
                        for repo_file in repo_files:
                            result = subprocess.run(["sudo", "rm", str(repo_file)], capture_output=True, text=True)
                            if result.returncode == 0:
                                logging.info(f"✅ Removed repository file: {repo_file.name}")
                                files_removed += 1
                            else:
                                logging.warning(f"⚠️ Could not remove {repo_file.name}")
                            
                        for gpg_file in gpg_files:
                            result = subprocess.run(["sudo", "rm", str(gpg_file)], capture_output=True, text=True)
                            if result.returncode == 0:
                                logging.info(f"✅ Removed GPG key: {gpg_file.name}")
                                files_removed += 1
                            else:
                                logging.warning(f"⚠️ Could not remove {gpg_file.name}")
                                
                        if files_removed > 0:
                            logging.info(f"✅ Cleaned up {files_removed} repository files")
                        else:
                            logging.info("ℹ️ No repository files found to clean up")
                            
                    except Exception as e:
                        logging.warning(f"⚠️ Repository cleanup had issues: {e}")
                        
                    logging.info("✅ REMOVAL COMPLETED SUCCESSFULLY!")
                    logging.info("Meshtasticd has been completely uninstalled")
                    self.root.after(0, self.update_status_indicators)
                else:
                    logging.error("❌ REMOVAL FAILED!")
                    logging.error("Package removal encountered errors")
                    if result and result.stderr:
                        logging.error(f"Error details: {result.stderr}")
                    
                logging.info("="*50)
                    
            except Exception as e:
                logging.error(f"❌ REMOVAL ERROR: {e}")
                logging.info("="*50)
                
        threading.Thread(target=worker, daemon=True).start()
        
    def handle_enable_boot(self):
        """Handle enabling meshtasticd on boot"""
        if self.check_meshtasticd_boot_status():
            logging.info("meshtasticd is already enabled on boot")
        else:
            logging.info("Enabling meshtasticd to start on boot...")
            def worker():
                try:
                    result = subprocess.run(["sudo", "systemctl", "enable", PKG_NAME], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("✅ meshtasticd enabled to start on boot")
                    else:
                        logging.error(f"❌ Failed to enable meshtasticd on boot: {result.stderr}")
                    
                    self.root.after(0, self.update_status_indicators)
                    
                except Exception as e:
                    logging.error(f"Error enabling meshtasticd on boot: {e}")
                    
            threading.Thread(target=worker, daemon=True).start()
            
    def handle_install_python_cli(self):
        """Handle Python CLI installation"""
        if self.check_python_cli_status():
            # Already installed, offer to reinstall or show version
            if messagebox.askyesno("Python CLI Installed", 
                                 "Meshtastic Python CLI is already installed.\n"
                                 "Do you want to reinstall/upgrade it?"):
                self.install_python_cli()
            else:
                # Just show version info
                self.show_python_cli_version()
        else:
            # Not installed, install it
            self.install_python_cli()
    
    def show_python_cli_version(self):
        """Show current Python CLI version"""
        def worker():
            try:
                logging.info("Checking Meshtastic Python CLI version...")
                result = subprocess.run(["meshtastic", "--version"], capture_output=True, text=True)
                if result.returncode == 0:
                    logging.info(f"✅ Meshtastic Python CLI version: {result.stdout.strip()}")
                else:
                    logging.error("❌ Failed to get Python CLI version")
            except Exception as e:
                logging.error(f"Error checking Python CLI version: {e}")
                
        threading.Thread(target=worker, daemon=True).start()
    
    def install_python_cli(self):
        """Install Meshtastic Python CLI"""
        def worker():
            try:
                logging.info("="*50)
                logging.info("STARTING MESHTASTIC PYTHON CLI INSTALLATION")
                logging.info("="*50)
                
                # Step 1: Install python3-full
                logging.info("Step 1/5: Installing python3-full...")
                result = self.safe_apt_command(["sudo", "apt", "install", "-y", "python3-full"], timeout=300)
                if result and result.returncode == 0:
                    logging.info("✅ python3-full installed successfully")
                else:
                    logging.warning("⚠️ python3-full installation had issues, continuing...")
                
                # Step 2: Install pytap2 via pip3
                logging.info("Step 2/5: Installing pytap2 via pip3...")
                try:
                    result = subprocess.run(
                        ["pip3", "install", "--upgrade", "pytap2", "--break-system-packages"],
                        capture_output=True, text=True, timeout=300
                    )
                    if result.returncode == 0:
                        logging.info("✅ pytap2 installed successfully")
                    else:
                        logging.warning(f"⚠️ pytap2 installation warning: {result.stderr}")
                        logging.info("Continuing with installation...")
                except Exception as e:
                    logging.warning(f"⚠️ pytap2 installation issue: {e}, continuing...")
                
                # Step 3: Install pipx
                logging.info("Step 3/5: Installing pipx...")
                result = self.safe_apt_command(["sudo", "apt", "install", "-y", "pipx"], timeout=300)
                if result and result.returncode == 0:
                    logging.info("✅ pipx installed successfully")
                else:
                    logging.error("❌ Failed to install pipx")
                    return
                
                # Step 4: Install meshtastic CLI via pipx
                logging.info("Step 4/5: Installing Meshtastic CLI via pipx...")
                logging.info("This may take several minutes as it downloads and compiles dependencies...")
                try:
                    result = subprocess.run(
                        ["pipx", "install", "meshtastic[cli]"],
                        capture_output=True, text=True, timeout=600  # 10 minute timeout
                    )
                    if result.returncode == 0:
                        logging.info("✅ Meshtastic CLI installed successfully via pipx")
                    else:
                        logging.error(f"❌ Failed to install Meshtastic CLI: {result.stderr}")
                        return
                except subprocess.TimeoutExpired:
                    logging.error("❌ Meshtastic CLI installation timed out")
                    return
                except Exception as e:
                    logging.error(f"❌ Meshtastic CLI installation error: {e}")
                    return
                
                # Step 5: Ensure pipx path
                logging.info("Step 5/5: Ensuring pipx PATH configuration...")
                try:
                    result = subprocess.run(
                        ["pipx", "ensurepath"],
                        capture_output=True, text=True, timeout=60
                    )
                    if result.returncode == 0:
                        logging.info("✅ pipx PATH configured successfully")
                        if result.stdout.strip():
                            logging.info(f"pipx ensurepath output: {result.stdout.strip()}")
                    else:
                        logging.warning(f"⚠️ pipx ensurepath warning: {result.stderr}")
                except Exception as e:
                    logging.warning(f"⚠️ pipx ensurepath issue: {e}")
                
                # Step 6: Verify installation
                logging.info("Step 6/6: Verifying Meshtastic CLI installation...")
                try:
                    # Try to run meshtastic --version
                    result = subprocess.run(
                        ["meshtastic", "--version"],
                        capture_output=True, text=True, timeout=30
                    )
                    if result.returncode == 0:
                        version_info = result.stdout.strip()
                        logging.info(f"✅ INSTALLATION COMPLETED SUCCESSFULLY!")
                        logging.info(f"Meshtastic CLI version: {version_info}")
                        logging.info("You can now use 'meshtastic' command from the terminal")
                        
                        # Show success message
                        self.root.after(0, lambda: messagebox.showinfo(
                            "Installation Complete - Restart Required",
                            f"Meshtastic Python CLI installed successfully!\n\n"
                            f"Version: {version_info}\n\n"
                            f"IMPORTANT: To use the CLI commands, you need to:\n"
                            f"1. Close this application\n"
                            f"2. Close your terminal\n"
                            f"3. Open a new terminal\n"
                            f"4. Test with: meshtastic --version\n\n"
                            f"The PATH environment needs to be refreshed."
                        ))
                    else:
                        logging.warning("⚠️ Installation completed but version check failed")
                        logging.warning("You may need to restart your terminal or update your PATH")
                        logging.warning("Try running: source ~/.bashrc")
                        
                        self.root.after(0, lambda: messagebox.showwarning(
                            "Installation Complete - Restart Required",
                            "Meshtastic CLI was installed but may not be in your PATH yet.\n\n"
                            "IMPORTANT: To use the CLI commands, you need to:\n"
                            "1. Close this application\n"
                            "2. Close your terminal\n"
                            "3. Open a new terminal\n"
                            "4. Test with: meshtastic --version\n\n"
                            "If it still doesn't work, try running:\n"
                            "source ~/.bashrc"
                        ))
                        
                except Exception as e:
                    logging.warning(f"⚠️ Version check failed: {e}")
                    logging.info("Installation may have succeeded but verification failed")
                
                logging.info("="*50)
                
                # Update status indicators
                self.root.after(0, self.update_status_indicators)
                    
            except Exception as e:
                logging.error(f"❌ PYTHON CLI INSTALLATION ERROR: {e}")
                logging.info("="*50)
                
        threading.Thread(target=worker, daemon=True).start()
            
    def handle_send_message(self):
        """Handle sending a message via Meshtastic CLI"""
        if not self.check_python_cli_status():
            messagebox.showerror("Python CLI Required", 
                               "Meshtastic Python CLI is not installed.\n"
                               "Please install it first using the 'Install Python CLI' button.")
            return
            
        # Create message input dialog
        message_window = tk.Toplevel(self.root)
        message_window.title("Send Meshtastic Message")
        message_window.geometry("450x250")  # Increased height from 200 to 250
        message_window.transient(self.root)
        message_window.grab_set()
        
        # Make window modal and bring to front
        message_window.focus_force()
        message_window.lift()
        
        # Instructions
        ttk.Label(message_window, 
                 text="Send Message to Mesh Network",
                 font=("TkDefaultFont", 14, "bold")).pack(pady=10)
        
        ttk.Label(message_window, 
                 text="Enter the message you want to send to the mesh:",
                 font=("TkDefaultFont", 10)).pack(pady=5)
        
        # Message input
        message_var = tk.StringVar()
        message_entry = ttk.Entry(message_window, textvariable=message_var, width=50)
        message_entry.pack(pady=10, padx=20)
        message_entry.focus()
        
        # Character counter
        char_label = ttk.Label(message_window, text="0/200 characters", foreground="gray")
        char_label.pack()
        
        def update_char_count(*args):
            count = len(message_var.get())
            char_label.config(text=f"{count}/200 characters")
            if count > 200:
                char_label.config(foreground="red")
            else:
                char_label.config(foreground="gray")
        
        message_var.trace('w', update_char_count)
        
        # Buttons
        button_frame = ttk.Frame(message_window)
        button_frame.pack(pady=20)
        
        def send_message():
            message_text = message_var.get().strip()
            if not message_text:
                messagebox.showwarning("Empty Message", "Please enter a message to send.")
                return
            if len(message_text) > 200:
                messagebox.showwarning("Message Too Long", "Message must be 200 characters or less.")
                return
                
            message_window.destroy()
            self.send_mesh_message(message_text)
        
        def cancel_message():
            message_window.destroy()
        
        # Bind Enter key to send
        message_window.bind('<Return>', lambda e: send_message())
        message_window.bind('<Escape>', lambda e: cancel_message())
        
        ttk.Button(button_frame, text="Send Message", 
                  command=send_message).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", 
                  command=cancel_message).pack(side=tk.LEFT, padx=10)
    
    def send_mesh_message(self, message_text):
        """Send message to mesh network"""
        def worker():
            try:
                logging.info(f"Sending message to mesh: '{message_text}'")
                result = subprocess.run(
                    ["meshtastic", "--host", "localhost", "--sendtext", message_text],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    logging.info("✅ Message sent successfully!")
                    if result.stdout.strip():
                        logging.info(f"Response: {result.stdout.strip()}")
                    
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Message Sent",
                        f"Message sent successfully to the mesh network!\n\n"
                        f"Message: '{message_text}'"
                    ))
                else:
                    error_msg = result.stderr.strip() if result.stderr.strip() else "Unknown error"
                    logging.error(f"❌ Failed to send message: {error_msg}")
                    
                    self.root.after(0, lambda: messagebox.showerror(
                        "Message Failed",
                        f"Failed to send message to mesh network.\n\n"
                        f"Error: {error_msg}\n\n"
                        f"Make sure meshtasticd is running and a device is connected."
                    ))
                    
            except subprocess.TimeoutExpired:
                logging.error("❌ Message sending timed out")
                self.root.after(0, lambda: messagebox.showerror(
                    "Timeout",
                    "Message sending timed out.\n"
                    "Check if meshtasticd is running and device is connected."
                ))
            except Exception as e:
                logging.error(f"❌ Message sending error: {e}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Error sending message: {e}"
                ))
                
        threading.Thread(target=worker, daemon=True).start()
    
    def handle_set_region(self):
        """Handle setting LoRa region"""
        if not self.check_python_cli_status():
            messagebox.showerror("Python CLI Required", 
                               "Meshtastic Python CLI is not installed.\n"
                               "Please install it first using the 'Install Python CLI' button.")
            return
        
        # Get current region first
        current_region = self.check_lora_region_status()
        
        # Create region selection dialog
        region_window = tk.Toplevel(self.root)
        region_window.title("Set LoRa Region")
        region_window.geometry("800x650")  # Increased width from 700 to 800
        region_window.transient(self.root)
        region_window.grab_set()
        
        # Make window modal and bring to front
        region_window.focus_force()
        region_window.lift()
        
        # Title and current status
        ttk.Label(region_window, 
                 text="Set LoRa Region",
                 font=("TkDefaultFont", 14, "bold")).pack(pady=10)
        
        ttk.Label(region_window, 
                 text=f"Current Region: {current_region}",
                 font=("TkDefaultFont", 11)).pack(pady=5)
        
        if current_region == "UNSET":
            ttk.Label(region_window, 
                     text="⚠️ Region is UNSET - This must be configured!",
                     foreground="red", font=("TkDefaultFont", 10, "bold")).pack(pady=5)
        
        # Instructions
        ttk.Label(region_window, 
                 text="Select your region (most common options at top):",
                 font=("TkDefaultFont", 10)).pack(pady=10)
        
        # Region selection with scrollable frame
        canvas = tk.Canvas(region_window, height=300)
        scrollbar = ttk.Scrollbar(region_window, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Define regions (common ones first, then alphabetical)
        regions = [
            ("US", "United States (902-928 MHz)"),
            ("EU_868", "Europe 868 MHz"),
            ("ANZ", "Australia/New Zealand (915-928 MHz)"),
            ("", "─── Other Regions ───"),  # Separator
            ("CN", "China (470-510 MHz)"),
            ("EU_433", "Europe 433 MHz"),
            ("IN", "India (865-867 MHz)"),
            ("JP", "Japan (920-923 MHz)"),
            ("KR", "Korea (920-923 MHz)"),
            ("MY_433", "Malaysia 433 MHz"),
            ("MY_919", "Malaysia 919-924 MHz"),
            ("RU", "Russia (868-870 MHz)"),
            ("SG_923", "Singapore 920-925 MHz"),
            ("TH", "Thailand (920-925 MHz)"),
            ("TW", "Taiwan (920-925 MHz)"),
            ("UA_433", "Ukraine 433 MHz"),
            ("UA_868", "Ukraine 868 MHz"),
            ("UNSET", "Unset (must be configured)")
        ]
        
        selected_region = tk.StringVar(value=current_region if current_region != "UNSET" else "US")
        
        for region_code, region_name in regions:
            if region_code == "":  # Separator
                ttk.Separator(scrollable_frame, orient='horizontal').pack(fill='x', pady=5)
                ttk.Label(scrollable_frame, text=region_name, 
                         font=("TkDefaultFont", 9, "bold")).pack(pady=2)
                continue
                
            frame = ttk.Frame(scrollable_frame)
            frame.pack(fill='x', padx=10, pady=1)
            
            radio = ttk.Radiobutton(frame, text=f"{region_code} - {region_name}",
                                  variable=selected_region, value=region_code)
            radio.pack(anchor='w')
            
            # Highlight current region
            if region_code == current_region:
                radio.configure(style='Selected.TRadiobutton')
        
        canvas.pack(side="left", fill="both", expand=True, padx=10)
        scrollbar.pack(side="right", fill="y")
        
        # Warning for UNSET
        if current_region == "UNSET":
            warning_frame = ttk.Frame(region_window)
            warning_frame.pack(fill='x', padx=20, pady=10)
            ttk.Label(warning_frame, 
                     text="⚠️ Important: Setting the wrong region may violate local regulations!",
                     foreground="red", font=("TkDefaultFont", 9, "bold")).pack()
            ttk.Label(warning_frame, 
                     text="Make sure to select the correct region for your location.",
                     foreground="red", font=("TkDefaultFont", 9)).pack()
        
        # Buttons
        button_frame = ttk.Frame(region_window)
        button_frame.pack(pady=20)
        
        def apply_region():
            new_region = selected_region.get()
            if new_region == current_region:
                messagebox.showinfo("No Change", f"Region is already set to {new_region}")
                region_window.destroy()
                return
                
            region_window.destroy()
            self.set_lora_region(new_region, current_region)
        
        def cancel_region():
            region_window.destroy()
        
        ttk.Button(button_frame, text="Apply Region", 
                  command=apply_region).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Cancel", 
                  command=cancel_region).pack(side=tk.LEFT, padx=10)
    
    def set_lora_region(self, new_region, old_region):
        """Set the LoRa region"""
        def worker():
            try:
                logging.info(f"Changing LoRa region from {old_region} to {new_region}...")
                result = subprocess.run(
                    ["meshtastic", "--host", "localhost", "--set", "lora.region", new_region],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    logging.info("✅ LoRa region updated successfully!")
                    if result.stdout.strip():
                        logging.info(f"Response: {result.stdout.strip()}")
                    
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Region Updated",
                        f"LoRa region updated successfully!\n\n"
                        f"Changed from: {old_region}\n"
                        f"Changed to: {new_region}\n\n"
                        f"The device may need to restart for changes to take full effect."
                    ))
                    
                    # Update status indicator
                    self.root.after(0, self.update_status_indicators)
                else:
                    error_msg = result.stderr.strip() if result.stderr.strip() else "Unknown error"
                    logging.error(f"❌ Failed to set LoRa region: {error_msg}")
                    
                    self.root.after(0, lambda: messagebox.showerror(
                        "Region Update Failed",
                        f"Failed to update LoRa region.\n\n"
                        f"Error: {error_msg}\n\n"
                        f"Make sure meshtasticd is running and a device is connected."
                    ))
                    
            except subprocess.TimeoutExpired:
                logging.error("❌ Region setting timed out")
                self.root.after(0, lambda: messagebox.showerror(
                    "Timeout",
                    "Region setting timed out.\n"
                    "Check if meshtasticd is running and device is connected."
                ))
            except Exception as e:
                logging.error(f"❌ Region setting error: {e}")
                self.root.after(0, lambda: messagebox.showerror(
                    "Error",
                    f"Error setting region: {e}"
                ))
                
        threading.Thread(target=worker, daemon=True).start()
            
    def handle_start_stop(self):
        """Handle starting/stopping meshtasticd service"""
        if self.check_meshtasticd_service_status():
            # Service is running, offer to stop it
            logging.info("Stopping meshtasticd service...")
            def worker():
                try:
                    result = subprocess.run(["sudo", "systemctl", "stop", PKG_NAME], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("✅ meshtasticd service stopped")
                    else:
                        logging.error(f"❌ Failed to stop meshtasticd: {result.stderr}")
                    
                    self.root.after(0, self.update_status_indicators)
                    
                except Exception as e:
                    logging.error(f"Error stopping meshtasticd: {e}")
                    
            threading.Thread(target=worker, daemon=True).start()
        else:
            # Service is stopped, offer to start it
            logging.info("Starting meshtasticd service...")
            def worker():
                try:
                    result = subprocess.run(["sudo", "systemctl", "start", PKG_NAME], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("✅ meshtasticd service started")
                    else:
                        logging.error(f"❌ Failed to start meshtasticd: {result.stderr}")
                    
                    self.root.after(0, self.update_status_indicators)
                    
                except Exception as e:
                    logging.error(f"Error starting meshtasticd: {e}")
                    
            threading.Thread(target=worker, daemon=True).start()
            
    def handle_enable_disable_avahi(self):
        """Handle Avahi setup/removal for auto-discovery"""
        if self.check_avahi_status():
            # Show disable dialog
            if messagebox.askyesno("Disable Avahi", 
                                 "Avahi is currently enabled. Do you want to disable it?\n\n"
                                 "This will:\n"
                                 "• Remove the Meshtastic service file\n"
                                 "• Stop the avahi-daemon service\n"
                                 "• Disable avahi-daemon from starting on boot"):
                self.disable_avahi()
        else:
            # Show enable dialog
            self.enable_avahi()
            
    def enable_avahi(self):
        """Enable Avahi for auto-discovery"""
        logging.info("Setting up Avahi for Meshtastic auto-discovery...")
        def worker():
            try:
                logging.info("="*50)
                logging.info("STARTING AVAHI SETUP")
                logging.info("="*50)
                
                # Check if avahi-daemon is installed
                logging.info("Step 1/4: Checking if avahi-daemon is installed...")
                result = subprocess.run(["dpkg", "-l", "avahi-daemon"], capture_output=True, text=True)
                avahi_installed = result.returncode == 0 and "ii" in result.stdout
                
                if not avahi_installed:
                    logging.info("Step 1/4: Installing avahi-daemon...")
                    logging.info("This may take a few minutes...")
                    
                    # Use safe apt command for update
                    result = self.safe_apt_command(["sudo", "apt", "update"], timeout=120)
                    if result and result.returncode != 0:
                        logging.warning("⚠️ APT update had issues, continuing anyway")
                    
                    # Use safe apt command for install
                    result = self.safe_apt_command(["sudo", "apt", "install", "-y", "avahi-daemon"], 
                                                 timeout=300)
                    
                    if result and result.returncode == 0:
                        logging.info("✅ avahi-daemon installed successfully")
                    else:
                        logging.error("❌ Failed to install avahi-daemon")
                        return
                else:
                    logging.info("✅ avahi-daemon is already installed")
                
                # Check if service file already exists
                service_file = "/etc/avahi/services/meshtastic.service"
                logging.info("Step 2/4: Checking for existing Meshtastic service file...")
                
                if os.path.exists(service_file):
                    logging.info("ℹ️ Meshtastic service file already exists")
                    replace = messagebox.askyesno(
                        "Service File Exists",
                        f"Avahi service file already exists at:\n{service_file}\n\n"
                        "Do you want to replace it with a fresh copy?"
                    )
                    if not replace:
                        logging.info("User chose not to replace existing service file")
                        # Still need to enable the service
                        logging.info("Step 3/4: Enabling avahi-daemon service...")
                        subprocess.run(["sudo", "systemctl", "enable", "avahi-daemon"], check=False)
                        logging.info("Step 4/4: Starting avahi-daemon service...")
                        subprocess.run(["sudo", "systemctl", "start", "avahi-daemon"], check=False)
                        logging.info("✅ AVAHI SETUP COMPLETED (using existing file)")
                        logging.info("="*50)
                        self.root.after(0, self.update_status_indicators)
                        return
                
                # Create the Avahi service file
                logging.info("Step 3/4: Creating Meshtastic service file...")
                
                service_content = """<?xml version="1.0" standalone="no"?><!--*-nxml-*-->
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
<n>Meshtastic</n>
<service protocol="ipv4">
<type>_meshtastic._tcp</type>
<port>4403</port>
</service>
</service-group>"""
                
                # Create avahi services directory if it doesn't exist
                subprocess.run(["sudo", "mkdir", "-p", "/etc/avahi/services"], check=True)
                
                # Write the service file
                result = subprocess.run(["sudo", "tee", service_file], 
                                      input=service_content, text=True, capture_output=True)
                
                if result.returncode == 0:
                    logging.info("✅ Meshtastic service file created successfully")
                    
                    # Enable and start avahi-daemon service
                    logging.info("Step 4/4: Enabling and starting avahi-daemon service...")
                    
                    result = subprocess.run(["sudo", "systemctl", "enable", "avahi-daemon"], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("✅ avahi-daemon enabled to start on boot")
                    else:
                        logging.warning("⚠️ Failed to enable avahi-daemon")
                    
                    result = subprocess.run(["sudo", "systemctl", "start", "avahi-daemon"], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("✅ avahi-daemon started successfully")
                    else:
                        logging.warning("⚠️ Failed to start avahi-daemon")
                    
                    logging.info("✅ AVAHI SETUP COMPLETED SUCCESSFULLY!")
                    logging.info("Android clients can now auto-discover this device")
                    logging.info("The device will advertise as 'Meshtastic' on port 4403")
                else:
                    logging.error("❌ Failed to create service file")
                    
                logging.info("="*50)
                self.root.after(0, self.update_status_indicators)
                
            except Exception as e:
                logging.error(f"❌ AVAHI SETUP ERROR: {e}")
                logging.info("="*50)
                
        threading.Thread(target=worker, daemon=True).start()
        
    def disable_avahi(self):
        """Disable Avahi and remove Meshtastic service"""
        logging.info("Disabling Avahi...")
        def worker():
            try:
                logging.info("="*50)
                logging.info("STARTING AVAHI REMOVAL")
                logging.info("="*50)
                
                # Stop avahi-daemon service
                logging.info("Step 1/3: Stopping avahi-daemon service...")
                result = subprocess.run(["sudo", "systemctl", "stop", "avahi-daemon"], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logging.info("✅ avahi-daemon service stopped")
                else:
                    logging.info("ℹ️ avahi-daemon was not running or already stopped")
                
                # Disable avahi-daemon from starting on boot
                logging.info("Step 2/3: Disabling avahi-daemon from starting on boot...")
                result = subprocess.run(["sudo", "systemctl", "disable", "avahi-daemon"], 
                                      capture_output=True, text=True)
                if result.returncode == 0:
                    logging.info("✅ avahi-daemon disabled from starting on boot")
                else:
                    logging.info("ℹ️ avahi-daemon was not enabled or already disabled")
                
                # Remove Meshtastic service file
                logging.info("Step 3/3: Removing Meshtastic service file...")
                service_file = "/etc/avahi/services/meshtastic.service"
                
                if os.path.exists(service_file):
                    result = subprocess.run(["sudo", "rm", service_file], 
                                          capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("✅ Meshtastic service file removed")
                    else:
                        logging.warning("⚠️ Failed to remove Meshtastic service file")
                else:
                    logging.info("ℹ️ Meshtastic service file was not found")
                
                logging.info("✅ AVAHI REMOVAL COMPLETED SUCCESSFULLY!")
                logging.info("Android clients will no longer auto-discover this device")
                logging.info("avahi-daemon service has been stopped and disabled")
                logging.info("="*50)
                
                self.root.after(0, self.update_status_indicators)
                
            except Exception as e:
                logging.error(f"❌ AVAHI REMOVAL ERROR: {e}")
                logging.info("="*50)
                
        threading.Thread(target=worker, daemon=True).start()
            
    def configure_meshadv_mini(self):
        """Configure MeshAdv Mini specific settings"""
        def worker():
            try:
                logging.info("Configuring MeshAdv Mini GPIO and PPS settings...")
                
                # Read current config.txt
                config_file = "/boot/firmware/config.txt"
                backup_file = f"{config_file}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                # Backup original
                subprocess.run(["sudo", "cp", config_file, backup_file], check=True)
                logging.info(f"Backed up config.txt to {backup_file}")
                
                # Read current config
                result = subprocess.run(["sudo", "cat", config_file], capture_output=True, text=True, check=True)
                config_content = result.stdout
                
                # MeshAdv Mini specific configurations
                meshadv_config = """
# MeshAdv Mini Configuration
# GPIO 4 configuration - turn on at boot
gpio=4=op,dh

# PPS configuration for GPS on GPIO 17
dtoverlay=pps-gpio,gpiopin=17
"""
                
                # Check if already configured
                if "MeshAdv Mini Configuration" not in config_content:
                    # Add configuration
                    config_content += meshadv_config
                    
                    # Write updated config using sudo
                    subprocess.run(["sudo", "tee", config_file], input=config_content, text=True, check=True)
                        
                    logging.info("MeshAdv Mini configuration added to config.txt")
                    logging.info("Reboot required for changes to take effect")
                    
                    self.root.after(0, lambda: messagebox.showinfo(
                        "Configuration Complete", 
                        "MeshAdv Mini configuration added.\nReboot required for changes to take effect."
                    ))
                else:
                    logging.info("MeshAdv Mini configuration already present")
                    
                self.root.after(0, self.update_status_indicators)
                
            except Exception as e:
                logging.error(f"MeshAdv Mini configuration error: {e}")
                
        threading.Thread(target=worker, daemon=True).start()

def main():
    """Main entry point"""
    # No longer require root - we'll use sudo for individual commands
    
    # Check for required dependencies
    try:
        import yaml
    except ImportError:
        if messagebox.askyesno("Missing Dependency", 
                             "PyYAML is required for YAML configuration support.\n"
                             "Install it now? (sudo apt install python3-yaml)"):
            try:
                subprocess.run(["sudo", "apt", "install", "-y", "python3-yaml"], check=True)
                messagebox.showinfo("Success", "PyYAML installed successfully!")
            except subprocess.CalledProcessError:
                messagebox.showwarning("Installation Failed", 
                                     "Could not install PyYAML automatically.\n"
                                     "Please install manually: sudo apt install python3-yaml")
    
    # Create and run GUI
    root = tk.Tk()
    app = MeshtasticGUI(root)
    
    try:
        root.mainloop()
    except KeyboardInterrupt:
        print("\nApplication terminated by user")
        sys.exit(0)

if __name__ == "__main__":
    main()