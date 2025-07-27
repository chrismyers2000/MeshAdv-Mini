#!/usr/bin/env python3

"""
Meshtastic GTK Configuration Tool for Raspberry Pi OS (Refactored)
Provides graphical interface for Meshtastic installation and configuration
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib, Gdk, Pango

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
from typing import Optional, Dict, Tuple, List, Callable
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, Future
import contextlib

# Configuration Management
@dataclass
class AppConfig:
    """Centralized configuration for the application"""
    # Repository settings
    REPO_DIR: str = "/etc/apt/sources.list.d"
    GPG_DIR: str = "/etc/apt/trusted.gpg.d"
    OS_VERSION: str = "Raspbian_12"
    REPO_PREFIX: str = "network:Meshtastic"
    
    # Package settings
    PKG_NAME: str = "meshtasticd"
    CONFIG_DIR: str = "/etc/meshtasticd"
    BACKUP_DIR: str = "/etc/meshtasticd_backups"
    LOG_FILE: str = "/var/log/meshtastic_installer.log"
    
    # Boot configuration
    BOOT_CONFIG_FILE: str = "/boot/firmware/config.txt"
    
    # Timeouts (seconds)
    DEFAULT_TIMEOUT: int = 300
    APT_TIMEOUT: int = 600
    CLI_TIMEOUT: int = 30
    
    # GUI settings
    WINDOW_WIDTH: int = 1000
    WINDOW_HEIGHT: int = 800
    BUTTON_WIDTH: int = 250
    MAX_RETRIES: int = 3
    
    # Status update interval (milliseconds)
    STATUS_UPDATE_INTERVAL: int = 100

class StatusType(Enum):
    """Status types for indicators"""
    CHECKING = "checking"
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

class OperationResult:
    """Result of an operation with success status and message"""
    def __init__(self, success: bool, message: str = "", details: str = ""):
        self.success = success
        self.message = message
        self.details = details

# Error Management
class MeshtasticError(Exception):
    """Base exception for Meshtastic operations"""
    pass

class ConfigurationError(MeshtasticError):
    """Configuration related errors"""
    pass

class InstallationError(MeshtasticError):
    """Installation related errors"""
    pass

class HardwareError(MeshtasticError):
    """Hardware detection errors"""
    pass

# Hardware Detection
class HardwareDetector:
    """Handles hardware detection for Pi model and HATs"""
    
    def __init__(self):
        self.pi_model: Optional[str] = None
        self.hat_info: Optional[Dict[str, str]] = None
        self._detect_hardware()
    
    def _detect_hardware(self):
        """Detect Pi model and HAT information"""
        try:
            self._detect_pi_model()
            self._detect_hat()
        except Exception as e:
            logging.warning(f"Hardware detection error: {e}")
    
    def _detect_pi_model(self):
        """Detect Raspberry Pi model"""
        try:
            if os.path.exists("/proc/device-tree/model"):
                with open("/proc/device-tree/model", "r") as f:
                    self.pi_model = f.read().strip().replace('\x00', '')
        except Exception as e:
            logging.warning(f"Failed to detect Pi model: {e}")
    
    def _detect_hat(self):
        """Detect HAT information"""
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
        except Exception as e:
            logging.warning(f"Failed to detect HAT: {e}")
    
    def is_pi5(self) -> bool:
        """Check if this is a Raspberry Pi 5"""
        return self.pi_model and "Raspberry Pi 5" in self.pi_model
    
    def get_hardware_info(self) -> Dict[str, str]:
        """Get formatted hardware information"""
        return {
            "pi_model": self.pi_model or "Unknown",
            "hat_vendor": self.hat_info.get("vendor", "Unknown") if self.hat_info else "None",
            "hat_product": self.hat_info.get("product", "Unknown") if self.hat_info else "None",
            "meshtasticd_version": self._get_meshtasticd_version()
        }
    
    def _get_meshtasticd_version(self) -> str:
        """Get meshtasticd version using dpkg-query"""
        try:
            result = subprocess.run(["dpkg-query", "-W", "-f=${Version}", "meshtasticd"], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                return version if version else "Not installed"
            else:
                return "Not installed"
        except (subprocess.TimeoutExpired, FileNotFoundError, Exception):
            return "Not installed"

# Thread Management
class ThreadManager:
    """Manages background operations with proper cleanup"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="MeshtasticWorker")
        self.active_futures: List[Future] = []
    
    def submit_task(self, func: Callable, *args, **kwargs) -> Future:
        """Submit a task to the thread pool"""
        future = self.executor.submit(func, *args, **kwargs)
        self.active_futures.append(future)
        
        # Clean up completed futures
        self.active_futures = [f for f in self.active_futures if not f.done()]
        
        return future
    
    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool"""
        self.executor.shutdown(wait=wait)

# System Operations Manager
class SystemManager:
    """Handles all system-level operations"""
    
    def __init__(self, config: AppConfig):
        self.config = config
    
    @contextlib.contextmanager
    def safe_file_operation(self, filepath: str, mode: str = 'r'):
        """Context manager for safe file operations"""
        file_handle = None
        try:
            file_handle = open(filepath, mode)
            yield file_handle
        except Exception as e:
            raise ConfigurationError(f"File operation failed for {filepath}: {e}")
        finally:
            if file_handle:
                file_handle.close()
    
    def run_command(self, cmd: List[str], timeout: int = None, input_text: str = None) -> subprocess.CompletedProcess:
        """Run a command with proper error handling"""
        timeout = timeout or self.config.DEFAULT_TIMEOUT
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=timeout,
                input=input_text
            )
            return result
        except subprocess.TimeoutExpired as e:
            raise MeshtasticError(f"Command timed out: {' '.join(cmd)}")
        except Exception as e:
            raise MeshtasticError(f"Command failed: {e}")
    
    def run_sudo_command(self, cmd: List[str], timeout: int = None, input_text: str = None) -> subprocess.CompletedProcess:
        """Run a command with sudo"""
        sudo_cmd = ["sudo"] + cmd
        return self.run_command(sudo_cmd, timeout, input_text)
    
    def check_package_installed(self, package_name: str) -> bool:
        """Check if a package is installed via dpkg"""
        try:
            result = self.run_command(["dpkg", "-l", package_name])
            return result.returncode == 0 and "ii" in result.stdout
        except:
            return False
    
    def check_service_enabled(self, service_name: str) -> bool:
        """Check if a service is enabled"""
        try:
            result = self.run_command(["systemctl", "is-enabled", service_name])
            return result.returncode == 0 and result.stdout.strip() == "enabled"
        except:
            return False
    
    def check_service_active(self, service_name: str) -> bool:
        """Check if a service is active"""
        try:
            result = self.run_command(["systemctl", "is-active", service_name])
            return result.returncode == 0 and result.stdout.strip() == "active"
        except:
            return False
    
    def backup_file(self, filepath: str) -> str:
        """Create a backup of a file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_path = f"{filepath}.backup_{timestamp}"
        
        try:
            self.run_sudo_command(["cp", filepath, backup_path])
            return backup_path
        except Exception as e:
            raise ConfigurationError(f"Failed to backup {filepath}: {e}")

# Status Checking
class StatusChecker:
    """Handles all status checking operations"""
    
    def __init__(self, config: AppConfig, system_manager: SystemManager, hardware: HardwareDetector):
        self.config = config
        self.system = system_manager
        self.hardware = hardware
    
    def check_meshtasticd_status(self) -> bool:
        """Check if meshtasticd is installed"""
        try:
            # Check via dpkg
            dpkg_installed = self.system.check_package_installed(self.config.PKG_NAME)
            
            # Check if binary exists
            binary_paths = ["/usr/sbin/meshtasticd", "/usr/bin/meshtasticd"]
            binary_exists = any(os.path.exists(path) for path in binary_paths)
            
            # Check with which command
            which_found = False
            try:
                result = self.system.run_command(["which", self.config.PKG_NAME])
                which_found = result.returncode == 0
            except:
                pass
            
            return dpkg_installed or binary_exists or which_found
        except:
            return False
    
    def check_spi_status(self) -> bool:
        """Check if SPI is enabled"""
        # Check if devices exist
        devices_exist = os.path.exists("/dev/spidev0.0") or os.path.exists("/dev/spidev0.1")
        
        # Check if configured in boot config
        config_enabled = False
        try:
            with open(self.config.BOOT_CONFIG_FILE, "r") as f:
                config_content = f.read()
            has_spi_param = "dtparam=spi=on" in config_content
            has_spi_overlay = "dtoverlay=spi0-0cs" in config_content
            config_enabled = has_spi_param and has_spi_overlay
        except:
            pass
            
        return devices_exist and config_enabled
    
    def check_i2c_status(self) -> bool:
        """Check if I2C is enabled"""
        devices_exist = any(os.path.exists(f"/dev/i2c-{i}") for i in range(0, 10))
        
        config_enabled = False
        try:
            with open(self.config.BOOT_CONFIG_FILE, "r") as f:
                config_content = f.read()
            config_enabled = "dtparam=i2c_arm=on" in config_content
        except:
            pass
            
        return devices_exist and config_enabled
    
    def check_gps_uart_status(self) -> bool:
        """Check if GPS/UART is enabled"""
        try:
            with open(self.config.BOOT_CONFIG_FILE, "r") as f:
                config_content = f.read()
            
            has_uart_enabled = "enable_uart=1" in config_content
            
            if self.hardware.is_pi5():
                has_uart0_overlay = "dtoverlay=uart0" in config_content
                return has_uart_enabled and has_uart0_overlay
            else:
                return has_uart_enabled
        except:
            return False
    
    def check_hat_specific_status(self) -> bool:
        """Check if HAT specific options are configured"""
        if not self.hardware.hat_info or self.hardware.hat_info.get('product') != 'MeshAdv Mini':
            return False
            
        try:
            with open(self.config.BOOT_CONFIG_FILE, "r") as f:
                config_content = f.read()
                
            has_gpio_config = "gpio=4=op,dh" in config_content
            has_pps_config = "pps-gpio,gpiopin=17" in config_content
            
            return has_gpio_config and has_pps_config
        except:
            return False
    
    def check_hat_config_status(self) -> bool:
        """Check if HAT config file exists"""
        config_d_dir = f"{self.config.CONFIG_DIR}/config.d"
        if not os.path.exists(config_d_dir):
            return False
            
        try:
            config_files = list(Path(config_d_dir).glob("*.yaml"))
            return len(config_files) > 0
        except:
            return False
    
    def check_config_exists(self) -> bool:
        """Check if config file exists"""
        return (os.path.exists(f"{self.config.CONFIG_DIR}/config.yaml") or 
                os.path.exists(f"{self.config.CONFIG_DIR}/config.json"))
    
    def check_python_cli_status(self) -> bool:
        """Check if Meshtastic Python CLI is installed"""
        try:
            result = self.system.run_command(["meshtastic", "--version"])
            return result.returncode == 0
        except:
            try:
                result = self.system.run_command(["pipx", "list"])
                return "meshtastic" in result.stdout
            except:
                return False
    
    def check_lora_region_status(self) -> str:
        """Check current LoRa region setting"""
        try:
            if not self.check_python_cli_status():
                return "CLI Not Available"
                
            result = self.system.run_command(
                ["meshtastic", "--host", "localhost", "--get", "lora.region"],
                timeout=10
            )
            
            if result.returncode == 0:
                output = result.stdout.strip()
                logging.info(f"Raw CLI output for region: '{output}'")
                
                region_map = {
                    "0": "UNSET", "1": "US", "2": "EU_433", "3": "EU_868",
                    "4": "CN", "5": "JP", "6": "ANZ", "7": "KR", "8": "TW",
                    "9": "RU", "10": "IN", "11": "NZ_865", "12": "TH",
                    "13": "UA_433", "14": "UA_868", "15": "MY_433",
                    "16": "MY_919", "17": "SG_923"
                }
                
                valid_regions = ["UNSET", "US", "EU_868", "EU_433", "ANZ", "CN", "IN", "JP", "KR", 
                               "MY_433", "MY_919", "RU", "SG_923", "TH", "TW", "UA_433", "UA_868"]
                
                lines = output.split('\n')
                for line in lines:
                    line = line.strip()
                    
                    if not line or any(skip in line.lower() for skip in ['connected', 'requesting', 'node info']):
                        continue
                    
                    if line in valid_regions:
                        return line
                    
                    if "lora.region:" in line:
                        parts = line.split(":", 1)
                        if len(parts) > 1:
                            value = parts[1].strip()
                            if value in valid_regions:
                                return value
                            if value in region_map:
                                return region_map[value]
                    
                    if line.isdigit() and line in region_map:
                        return region_map[line]
                
                return "Unknown"
            else:
                return "Error"
        except Exception as e:
            logging.error(f"Exception checking region status: {e}")
            return "Error"
    
    def check_avahi_status(self) -> bool:
        """Check if Avahi is installed and configured"""
        try:
            avahi_installed = self.system.check_package_installed("avahi-daemon")
            if not avahi_installed:
                return False
                
            service_file = "/etc/avahi/services/meshtastic.service"
            return os.path.exists(service_file)
        except:
            return False
    
    def check_meshtasticd_boot_status(self) -> bool:
        """Check if meshtasticd is enabled to start on boot"""
        return self.system.check_service_enabled(self.config.PKG_NAME)
    
    def check_meshtasticd_service_status(self) -> bool:
        """Check if meshtasticd service is currently running"""
        return self.system.check_service_active(self.config.PKG_NAME)

# Progress Indicator
class ProgressIndicator:
    """Manages progress indicators and spinners"""
    
    def __init__(self, parent_widget: Gtk.Widget):
        self.parent = parent_widget
        self.spinner = None
        self.progress_bar = None
        self.is_active = False
    
    def show_spinner(self, message: str = "Processing..."):
        """Show a spinner with optional message"""
        if self.is_active:
            return
            
        self.is_active = True
        
        # Create overlay container
        overlay = Gtk.Overlay()
        
        # Create spinner box
        spinner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        spinner_box.set_halign(Gtk.Align.CENTER)
        spinner_box.set_valign(Gtk.Align.CENTER)
        
        # Add spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(32, 32)
        self.spinner.start()
        spinner_box.pack_start(self.spinner, False, False, 0)
        
        # Add message label
        label = Gtk.Label(label=message)
        label.get_style_context().add_class("dim-label")
        spinner_box.pack_start(label, False, False, 0)
        
        # Add semi-transparent background
        event_box = Gtk.EventBox()
        event_box.add(spinner_box)
        event_box.get_style_context().add_class("overlay-background")
        
        overlay.add_overlay(event_box)
        
        # Store reference and show
        self.overlay = overlay
        overlay.show_all()
        
        return overlay
    
    def hide_spinner(self):
        """Hide the spinner"""
        if self.spinner:
            self.spinner.stop()
            self.spinner = None
        
        self.is_active = False
    
    def show_progress_bar(self, message: str = "Processing..."):
        """Show a progress bar"""
        if self.progress_bar:
            return self.progress_bar
            
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        
        label = Gtk.Label(label=message)
        box.pack_start(label, False, False, 0)
        
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_pulse_step(0.1)
        box.pack_start(self.progress_bar, False, False, 0)
        
        return box
    
    def pulse_progress(self):
        """Pulse the progress bar"""
        if self.progress_bar:
            self.progress_bar.pulse()
            return True
        return False

# Logging Manager
class LoggingManager:
    """Manages logging with queue-based GUI updates"""
    
    def __init__(self, config: AppConfig):
        self.config = config
        self.output_queue = queue.Queue()
        self.setup_logging()
    
    def setup_logging(self):
        """Setup logging with queue handler for GUI"""
        class QueueHandler(logging.Handler):
            def __init__(self, queue):
                super().__init__()
                self.queue = queue
                
            def emit(self, record):
                try:
                    msg = record.getMessage()
                    self.queue.put(msg)
                except Exception:
                    pass
        
        # Clear any existing handlers
        logging.getLogger().handlers.clear()
        
        # Setup logging with queue handler
        queue_handler = QueueHandler(self.output_queue)
        queue_handler.setLevel(logging.INFO)
        
        # Try to add file handler too
        handlers = [queue_handler]
        try:
            os.makedirs(os.path.dirname(self.config.LOG_FILE), exist_ok=True)
            file_handler = logging.FileHandler(self.config.LOG_FILE)
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
        
        logging.info("Meshtastic GTK GUI started - logging system initialized")
    
    def get_messages(self) -> List[str]:
        """Get all pending log messages"""
        messages = []
        try:
            while True:
                try:
                    message = self.output_queue.get_nowait()
                    messages.append(message)
                except queue.Empty:
                    break
        except Exception as e:
            print(f"Error processing output queue: {e}")
        
        return messages

# Dependency Manager
class DependencyManager:
    """Manages application dependencies"""
    
    def __init__(self, system_manager: SystemManager):
        self.system = system_manager
    
    def check_and_install_dependencies(self) -> bool:
        """Check and install required dependencies"""
        try:
            self._check_pygobject()
            self._check_pyyaml()
            return True
        except Exception as e:
            print(f"Dependency check failed: {e}")
            return False
    
    def _check_pygobject(self):
        """Check if PyGObject is available"""
        try:
            import gi
        except ImportError:
            print("Installing PyGObject (python3-gi)...")
            try:
                self.system.run_sudo_command(["apt", "update"])
                self.system.run_sudo_command(["apt", "install", "-y", "python3-gi", "python3-gi-cairo"])
                print("PyGObject installed successfully!")
            except Exception as e:
                raise MeshtasticError("Failed to install PyGObject")
    
    def _check_pyyaml(self):
        """Check for PyYAML"""
        try:
            import yaml
        except ImportError:
            print("Installing PyYAML...")
            try:
                self.system.run_sudo_command(["apt", "install", "-y", "python3-yaml"])
                print("PyYAML installed successfully!")
            except Exception as e:
                raise MeshtasticError("Failed to install PyYAML")

# Main GUI Class
class MeshtasticGTK:
    """Main GUI application class"""
    
    def __init__(self):
        # Initialize core components
        self.config = AppConfig()
        self.system_manager = SystemManager(self.config)
        self.thread_manager = ThreadManager()
        self.hardware = HardwareDetector()
        self.status_checker = StatusChecker(self.config, self.system_manager, self.hardware)
        self.logging_manager = LoggingManager(self.config)
        
        # Check dependencies
        dependency_manager = DependencyManager(self.system_manager)
        if not dependency_manager.check_and_install_dependencies():
            sys.exit(1)
        
        # GUI components
        self.window = None
        self.status_labels = {}
        self.output_textview = None
        self.status_bar = None
        self.status_context_id = None
        
        # Progress indicators
        self.active_operations = {}
        
        # Initialize GUI
        self._create_window()
        self._apply_styles()
        self._create_gui()
        
        # Start periodic updates
        GLib.timeout_add(self.config.STATUS_UPDATE_INTERVAL, self._check_output_queue)
        
        # Initial status update
        self.update_status_indicators()
    
    def _create_window(self):
        """Create the main window"""
        self.window = Gtk.Window()
        self.window.set_title("Meshtasticd Configuration Tool - by Frequency Labs")
        self.window.set_default_size(self.config.WINDOW_WIDTH, self.config.WINDOW_HEIGHT)
        self.window.connect("destroy", self._on_window_destroy)
    
    def _on_window_destroy(self, widget):
        """Handle window destruction"""
        self.thread_manager.shutdown(wait=False)
        Gtk.main_quit()
    
    def _apply_styles(self):
        """Apply custom styles"""
        settings = Gtk.Settings.get_default()
        settings.set_property("gtk-application-prefer-dark-theme", True)
        
        css_provider = Gtk.CssProvider()
        css_data = """
        .status-green {
            color: #4CAF50;
            font-weight: bold;
        }
        .status-red {
            color: #F44336;
            font-weight: bold;
        }
        .status-orange {
            color: #FF9800;
            font-weight: bold;
        }
        .status-blue {
            color: #2196F3;
            font-weight: bold;
        }
        .title-large {
            font-size: 18px;
            font-weight: bold;
        }
        .subtitle {
            font-size: 12px;
            font-weight: bold;
        }
        .overlay-background {
            background-color: rgba(0, 0, 0, 0.5);
        }
        .dim-label {
            opacity: 0.8;
        }
        """
        css_provider.load_from_data(css_data.encode())
        Gtk.StyleContext.add_provider_for_screen(
            Gdk.Screen.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
    
    def _create_gui(self):
        """Create the main GUI interface"""
        # Main container
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        main_box.set_margin_start(10)
        main_box.set_margin_end(10)
        main_box.set_margin_top(10)
        main_box.set_margin_bottom(10)
        self.window.add(main_box)
        
        # Hardware info
        self._create_hardware_info(main_box)
        
        # Main content area
        content_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        main_box.pack_start(content_box, True, True, 0)
        
        # Left side - buttons
        left_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        left_box.set_size_request(350, -1)
        content_box.pack_start(left_box, False, False, 0)
        
        # Control buttons
        self._create_control_buttons(left_box)
        
        # Actions frame
        self._create_actions_buttons(left_box)
        
        # Right side - output
        self._create_output_area(content_box)
        
        # Status bar
        self._create_status_bar(main_box)
    
    def _create_hardware_info(self, parent):
        """Create hardware information display"""
        frame = Gtk.Frame()
        frame.set_label("Hardware Information")
        parent.pack_start(frame, False, False, 0)
        
        info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        info_box.set_margin_start(10)
        info_box.set_margin_end(10)
        info_box.set_margin_top(10)
        info_box.set_margin_bottom(10)
        frame.add(info_box)
        
        hardware_info = self.hardware.get_hardware_info()
        
        # Pi model
        pi_label = Gtk.Label(label=f"Raspberry Pi: {hardware_info['pi_model']}")
        pi_label.set_halign(Gtk.Align.START)
        info_box.pack_start(pi_label, False, False, 0)
        
        # HAT info
        if hardware_info['hat_vendor'] != "None":
            hat_text = f"{hardware_info['hat_vendor']} {hardware_info['hat_product']}"
            hat_label = Gtk.Label(label=f"HAT Detected: {hat_text}")
        else:
            hat_label = Gtk.Label(label="HAT Detected: None")
        hat_label.set_halign(Gtk.Align.START)
        info_box.pack_start(hat_label, False, False, 0)
        
        # Meshtasticd version (will be updated dynamically)
        self.version_label = Gtk.Label(label=f"Meshtasticd Version: {hardware_info['meshtasticd_version']}")
        self.version_label.set_halign(Gtk.Align.START)
        info_box.pack_start(self.version_label, False, False, 0)
    
    def _create_control_buttons(self, parent):
        """Create control buttons with status indicators"""
        frame = Gtk.Frame()
        frame.set_label("Configuration Options")
        parent.pack_start(frame, False, False, 0)
        
        grid = Gtk.Grid()
        grid.set_row_spacing(5)
        grid.set_column_spacing(10)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        frame.add(grid)
        
        buttons_config = [
            ("Install/Remove meshtasticd", "handle_install_remove", "status1", "Install or remove Meshtastic daemon package via apt repositories"),
            ("Enable SPI", "handle_enable_spi", "status2", "Enable SPI interface in /boot/firmware/config.txt for LoRa radio communication"),
            ("Enable I2C", "handle_enable_i2c", "status3", "Enable I2C interface in /boot/firmware/config.txt for sensors and displays"),
            ("Enable GPS/UART", "handle_enable_gps_uart", "status3_5", "Enable UART in /boot/firmware/config.txt for GPS module communication"),
            ("Enable HAT Specific Options", "handle_hat_specific", "status4", "Configure GPIO and PPS settings in /boot/firmware/config.txt for detected HAT"),
            ("Set HAT Config", "handle_hat_config", "status5", "Copy HAT-specific YAML config from available.d to config.d directory"),
            ("Edit Config", "handle_edit_config", "status6", "Open /etc/meshtasticd/config.yaml in nano text editor"),
        ]
        
        for row, (button_text, handler_name, status_key, tooltip) in enumerate(buttons_config):
            # Button
            button = Gtk.Button.new_with_label(button_text)
            button.set_size_request(self.config.BUTTON_WIDTH, -1)
            button.connect("clicked", getattr(self, handler_name))
            button.connect("enter-notify-event", lambda w, e, tip=tooltip: self._set_status_tooltip(tip))
            button.connect("leave-notify-event", lambda w, e: self._set_status_tooltip(""))
            grid.attach(button, 0, row, 1, 1)
            
            # Status label
            status_label = Gtk.Label(label="Checking...")
            status_label.get_style_context().add_class("status-orange")
            status_label.set_halign(Gtk.Align.START)
            grid.attach(status_label, 1, row, 1, 1)
            self.status_labels[status_key] = status_label
    
    def _create_actions_buttons(self, parent):
        """Create actions buttons"""
        frame = Gtk.Frame()
        frame.set_label("Actions")
        parent.pack_start(frame, False, False, 0)
        
        grid = Gtk.Grid()
        grid.set_row_spacing(5)
        grid.set_column_spacing(10)
        grid.set_margin_start(10)
        grid.set_margin_end(10)
        grid.set_margin_top(10)
        grid.set_margin_bottom(10)
        frame.add(grid)
        
        actions_config = [
            ("Enable meshtasticd on boot", "handle_enable_boot", "status_boot", "Configure systemctl to start meshtasticd service automatically at boot"),
            ("Start/Stop meshtasticd", "handle_start_stop", "status_service", "Start or stop the meshtasticd systemd service"),
            ("Install Python CLI", "handle_install_python_cli", "status_python_cli", "Install Meshtastic Python CLI via pipx for command-line access"),
            ("Send Message", "handle_send_message", "status_send_message", "Send text message to mesh network using Python CLI"),
            ("Set Region", "handle_set_region", "status_region", "Configure LoRa frequency region setting via Python CLI"),
            ("Enable/Disable Avahi", "handle_enable_disable_avahi", "status_avahi", "Configure Avahi service file for Android client auto-discovery"),
        ]
        
        for row, (button_text, handler_name, status_key, tooltip) in enumerate(actions_config):
            # Button
            button = Gtk.Button.new_with_label(button_text)
            button.set_size_request(self.config.BUTTON_WIDTH, -1)
            button.connect("clicked", getattr(self, handler_name))
            button.connect("enter-notify-event", lambda w, e, tip=tooltip: self._set_status_tooltip(tip))
            button.connect("leave-notify-event", lambda w, e: self._set_status_tooltip(""))
            grid.attach(button, 0, row, 1, 1)
            
            # Status label
            status_label = Gtk.Label(label="Checking...")
            status_label.get_style_context().add_class("status-orange")
            status_label.set_halign(Gtk.Align.START)
            grid.attach(status_label, 1, row, 1, 1)
            self.status_labels[status_key] = status_label
    
    def _create_output_area(self, parent):
        """Create output text area"""
        frame = Gtk.Frame()
        frame.set_label("Output")
        parent.pack_start(frame, True, True, 0)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        frame.add(vbox)
        
        # Scrolled window for text view
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(400, 400)
        vbox.pack_start(scrolled, True, True, 0)
        
        # Text view
        self.output_textview = Gtk.TextView()
        self.output_textview.set_editable(False)
        self.output_textview.set_cursor_visible(False)
        self.output_textview.set_wrap_mode(Gtk.WrapMode.WORD)
        
        # Set monospace font
        css_provider = Gtk.CssProvider()
        css_data = "textview { font-family: monospace; font-size: 10pt; }"
        css_provider.load_from_data(css_data.encode())
        context = self.output_textview.get_style_context()
        context.add_provider(css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        
        scrolled.add(self.output_textview)
        
        # Clear button
        clear_button = Gtk.Button.new_with_label("Clear Output")
        clear_button.connect("clicked", self._clear_output)
        clear_button.connect("enter-notify-event", lambda w, e: self._set_status_tooltip("Clear all text from the output display area"))
        clear_button.connect("leave-notify-event", lambda w, e: self._set_status_tooltip(""))
        clear_button.set_halign(Gtk.Align.END)
        vbox.pack_start(clear_button, False, False, 0)
    
    def _create_status_bar(self, parent):
        """Create status bar"""
        self.status_bar = Gtk.Statusbar()
        self.status_context_id = self.status_bar.get_context_id("tooltip")
        parent.pack_start(self.status_bar, False, False, 0)
    
    def _set_status_tooltip(self, message):
        """Set status bar message"""
        self.status_bar.remove_all(self.status_context_id)
        if message:
            self.status_bar.push(self.status_context_id, message)
    
    def _append_output(self, text):
        """Append text to output area"""
        buffer = self.output_textview.get_buffer()
        end_iter = buffer.get_end_iter()
        buffer.insert(end_iter, text + "\n")
        
        # Auto-scroll to bottom
        mark = buffer.get_insert()
        self.output_textview.scroll_mark_onscreen(mark)
    
    def _clear_output(self, widget=None):
        """Clear output area"""
        buffer = self.output_textview.get_buffer()
        buffer.set_text("")
    
    def _check_output_queue(self):
        """Check for new output messages"""
        messages = self.logging_manager.get_messages()
        for message in messages:
            self._append_output(message)
        return True  # Continue the timeout
    
    def _show_error_dialog(self, title, message):
        """Show error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    def _show_info_dialog(self, title, message):
        """Show info dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            flags=0,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text=title
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()
    
    def _show_question_dialog(self, title, message):
        """Show question dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self.window,
            flags=0,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=title
        )
        dialog.format_secondary_text(message)
        response = dialog.run()
        dialog.destroy()
        return response == Gtk.ResponseType.YES
    
    def _set_status_label(self, key, text, status_type: StatusType):
        """Set status label text and color"""
        if key in self.status_labels:
            label = self.status_labels[key]
            label.set_text(text)
            
            # Remove old color classes
            context = label.get_style_context()
            context.remove_class("status-green")
            context.remove_class("status-red")
            context.remove_class("status-orange")
            context.remove_class("status-blue")
            
            # Add new color class based on status type
            color_map = {
                StatusType.SUCCESS: "status-green",
                StatusType.ERROR: "status-red",
                StatusType.WARNING: "status-orange",
                StatusType.INFO: "status-blue",
                StatusType.CHECKING: "status-orange"
            }
            
            context.add_class(color_map.get(status_type, "status-orange"))
    
    def _show_progress_spinner(self, operation_id: str, message: str = "Processing..."):
        """Show a progress spinner for an operation"""
        if operation_id in self.active_operations:
            return
        
        # Create a modal dialog with spinner instead of overlay for better visibility
        dialog = Gtk.Dialog(title="Operation in Progress", parent=self.window, 
                           modal=True, destroy_with_parent=True)
        dialog.set_default_size(300, 150)
        dialog.set_resizable(False)
        dialog.set_deletable(False)  # Prevent closing during operation
        
        content_area = dialog.get_content_area()
        content_area.set_spacing(20)
        content_area.set_margin_start(20)
        content_area.set_margin_end(20)
        content_area.set_margin_top(20)
        content_area.set_margin_bottom(20)
        
        # Create spinner
        spinner = Gtk.Spinner()
        spinner.set_size_request(32, 32)
        spinner.start()
        content_area.pack_start(spinner, False, False, 0)
        
        # Add message label
        label = Gtk.Label(label=message)
        label.set_line_wrap(True)
        label.set_justify(Gtk.Justification.CENTER)
        content_area.pack_start(label, False, False, 0)
        
        # Show dialog
        dialog.show_all()
        
        # Store reference
        self.active_operations[operation_id] = {
            'dialog': dialog,
            'spinner': spinner
        }
    
    def _hide_progress_spinner(self, operation_id: str):
        """Hide a progress spinner"""
        if operation_id in self.active_operations:
            operation = self.active_operations[operation_id]
            if 'spinner' in operation:
                operation['spinner'].stop()
            if 'dialog' in operation:
                operation['dialog'].destroy()
            del self.active_operations[operation_id]
    
    def _run_operation_with_progress(self, operation_id: str, operation_func: Callable, 
                                   progress_message: str = "Processing...", 
                                   success_callback: Callable = None,
                                   error_callback: Callable = None):
        """Run an operation with progress indication"""
        
        def worker():
            try:
                GLib.idle_add(self._show_progress_spinner, operation_id, progress_message)
                result = operation_func()
                
                GLib.idle_add(self._hide_progress_spinner, operation_id)
                
                if success_callback:
                    GLib.idle_add(success_callback, result)
                    
            except Exception as e:
                GLib.idle_add(self._hide_progress_spinner, operation_id)
                
                if error_callback:
                    GLib.idle_add(error_callback, e)
                else:
                    GLib.idle_add(self._show_error_dialog, "Operation Failed", str(e))
                
                logging.error(f"Operation {operation_id} failed: {e}")
        
        self.thread_manager.submit_task(worker)
    
    def update_status_indicators(self):
        """Update all status indicators"""
        # Status 1: meshtasticd
        if self.status_checker.check_meshtasticd_status():
            self._set_status_label("status1", "Installed", StatusType.SUCCESS)
        else:
            self._set_status_label("status1", "Not Installed", StatusType.ERROR)
            
        # Status 2: SPI
        if self.status_checker.check_spi_status():
            self._set_status_label("status2", "Enabled", StatusType.SUCCESS)
        else:
            self._set_status_label("status2", "Disabled", StatusType.ERROR)
            
        # Status 3: I2C
        if self.status_checker.check_i2c_status():
            self._set_status_label("status3", "Enabled", StatusType.SUCCESS)
        else:
            self._set_status_label("status3", "Disabled", StatusType.ERROR)
            
        # Status 3.5: GPS/UART
        if self.status_checker.check_gps_uart_status():
            self._set_status_label("status3_5", "Enabled", StatusType.SUCCESS)
        else:
            self._set_status_label("status3_5", "Disabled", StatusType.ERROR)
            
        # Status 4: HAT Specific
        if self.status_checker.check_hat_specific_status():
            self._set_status_label("status4", "Configured", StatusType.SUCCESS)
        else:
            self._set_status_label("status4", "Not Configured", StatusType.ERROR)
            
        # Status 5: HAT Config
        if self.status_checker.check_hat_config_status():
            self._set_status_label("status5", "Set", StatusType.SUCCESS)
        else:
            self._set_status_label("status5", "Not Set", StatusType.ERROR)
            
        # Status 6: Config exists
        if self.status_checker.check_config_exists():
            self._set_status_label("status6", "Exists", StatusType.SUCCESS)
        else:
            self._set_status_label("status6", "Missing", StatusType.ERROR)
            
        # Status Python CLI
        if self.status_checker.check_python_cli_status():
            self._set_status_label("status_python_cli", "Installed", StatusType.SUCCESS)
            self._set_status_label("status_send_message", "Ready", StatusType.SUCCESS)
        else:
            self._set_status_label("status_python_cli", "Not Installed", StatusType.ERROR)
            self._set_status_label("status_send_message", "CLI Required", StatusType.ERROR)
            
        # Status Region
        region_status = self.status_checker.check_lora_region_status()
        if region_status == "UNSET":
            self._set_status_label("status_region", "UNSET", StatusType.ERROR)
        elif region_status in ["US", "EU_868", "EU_433", "ANZ", "CN", "IN", "JP", "KR", 
                               "MY_433", "MY_919", "RU", "SG_923", "TH", "TW", "UA_433", "UA_868"]:
            self._set_status_label("status_region", region_status, StatusType.SUCCESS)
        elif region_status == "CLI Not Available":
            self._set_status_label("status_region", "CLI Required", StatusType.ERROR)
        elif region_status == "Error":
            self._set_status_label("status_region", "Error", StatusType.WARNING)
        else:
            self._set_status_label("status_region", region_status, StatusType.INFO)
            
        # Status Avahi
        if self.status_checker.check_avahi_status():
            self._set_status_label("status_avahi", "Enabled", StatusType.SUCCESS)
        else:
            self._set_status_label("status_avahi", "Disabled", StatusType.ERROR)
            
        # Status Boot
        if self.status_checker.check_meshtasticd_boot_status():
            self._set_status_label("status_boot", "Enabled", StatusType.SUCCESS)
        else:
            self._set_status_label("status_boot", "Disabled", StatusType.ERROR)
            
        # Status Service
        if self.status_checker.check_meshtasticd_service_status():
            self._set_status_label("status_service", "Running", StatusType.SUCCESS)
        else:
            self._set_status_label("status_service", "Stopped", StatusType.ERROR)
        
        # Update meshtasticd version display
        current_version = self.hardware._get_meshtasticd_version()
        self.version_label.set_text(f"Meshtasticd Version: {current_version}")
    
    def _update_version_display(self):
        """Update just the version display"""
        current_version = self.hardware._get_meshtasticd_version()
        self.version_label.set_text(f"Meshtasticd Version: {current_version}")
        return False  # Don't repeat this timeout
    
    # Button Handler Methods
    def handle_install_remove(self, widget):
        """Handle install/remove meshtasticd"""
        if self.status_checker.check_meshtasticd_status():
            if self._show_question_dialog("Remove Meshtasticd", 
                                        "Meshtasticd is currently installed. Do you want to remove it?"):
                self._remove_meshtasticd()
        else:
            self._install_meshtasticd()
    
    def handle_enable_spi(self, widget):
        """Handle SPI enable/disable"""
        if self.status_checker.check_spi_status():
            logging.info("SPI is already enabled")
        else:
            self._run_operation_with_progress(
                "enable_spi",
                self._enable_spi,
                "Enabling SPI interface...",
                lambda result: self.update_status_indicators()
            )
    
    def handle_enable_i2c(self, widget):
        """Handle I2C enable/disable"""
        if self.status_checker.check_i2c_status():
            logging.info("I2C is already enabled")
        else:
            self._run_operation_with_progress(
                "enable_i2c",
                self._enable_i2c,
                "Enabling I2C interface...",
                lambda result: self.update_status_indicators()
            )
    
    def handle_enable_gps_uart(self, widget):
        """Handle GPS/UART enable"""
        if self.status_checker.check_gps_uart_status():
            logging.info("GPS/UART is already enabled")
        else:
            self._run_operation_with_progress(
                "enable_gps_uart",
                self._enable_gps_uart,
                "Enabling GPS/UART interface...",
                lambda result: self.update_status_indicators()
            )
    
    def handle_hat_specific(self, widget):
        """Handle HAT specific configuration"""
        if not self.hardware.hat_info or self.hardware.hat_info.get('product') != 'MeshAdv Mini':
            self._show_error_dialog("No Compatible HAT", 
                                 "MeshAdv Mini HAT not detected. This function is specific to MeshAdv Mini.")
            return
            
        self._run_operation_with_progress(
            "configure_hat",
            self._configure_meshadv_mini,
            "Configuring MeshAdv Mini...",
            lambda result: self.update_status_indicators()
        )
    
    def handle_hat_config(self, widget):
        """Handle HAT configuration in meshtasticd config.d"""
        # This needs to be handled synchronously with dialogs, so we don't use the progress wrapper
        try:
            available_dir = f"{self.config.CONFIG_DIR}/available.d"
            config_d_dir = f"{self.config.CONFIG_DIR}/config.d"
            
            # Create directories if they don't exist
            self.system_manager.run_sudo_command(["mkdir", "-p", available_dir])
            self.system_manager.run_sudo_command(["mkdir", "-p", config_d_dir])
            
            # Check for existing configs in config.d
            existing_configs = list(Path(config_d_dir).glob("*.yaml"))
            if existing_configs:
                config_names = [f.name for f in existing_configs]
                logging.info(f"Found existing configs in config.d: {', '.join(config_names)}")
                
                if not self._show_question_dialog("Existing Configuration", 
                    f"Found existing configuration(s): {', '.join(config_names)}\nDo you want to replace them?"):
                    logging.info("User chose not to replace existing configuration")
                    return
                
                # Remove existing configs
                for config_file in existing_configs:
                    self.system_manager.run_sudo_command(["rm", str(config_file)])
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
                self._show_error_dialog("No Configurations Available",
                    f"No configuration files or folders found in {available_dir}")
                return
            
            # Find matching configs for detected HAT
            matching_configs = []
            if self.hardware.hat_info:
                hat_product = self.hardware.hat_info.get('product', '').lower()
                hat_vendor = self.hardware.hat_info.get('vendor', '').lower()
                
                for config_item in available_configs:
                    config_name = config_item.name.lower()
                    if (hat_product in config_name or 
                        hat_vendor in config_name or
                        'meshadv' in config_name):
                        matching_configs.append(config_item)
            
            if len(matching_configs) == 1:
                # Show confirmation dialog for auto-selected config
                selected_config = matching_configs[0]
                
                hat_product = self.hardware.hat_info.get('product', 'Unknown') if self.hardware.hat_info else 'None'
                hat_vendor = self.hardware.hat_info.get('vendor', 'Unknown') if self.hardware.hat_info else 'Unknown'
                
                config_type = "Folder" if selected_config.is_dir() else "File"
                
                result = self._show_confirmation_dialog_with_options(
                    "Confirm HAT Configuration",
                    f"Detected HAT: {hat_vendor} {hat_product}\n\nAuto-selected configuration:\n{selected_config.name} ({config_type})\n\nIs this correct?",
                    ["Use This Config", "Show All Options", "Cancel"]
                )
                
                if result == 0:  # Use this config
                    self._copy_config_item_with_dialogs(selected_config, config_d_dir)
                elif result == 1:  # Show all options
                    self._show_all_available_configs_dialog(available_configs, config_d_dir)
                # Cancel - do nothing
                
            elif len(matching_configs) > 1:
                # Show selection dialog for multiple matches
                self._show_multiple_matches_dialog(matching_configs, available_configs, config_d_dir)
                
            else:
                # No matches or no HAT detected - show all available configs
                self._show_all_available_configs_dialog(available_configs, config_d_dir)
                
        except Exception as e:
            logging.error(f"HAT configuration error: {e}")
            self._show_error_dialog("Error", f"HAT configuration failed: {e}")
        
        # Update status after operation
        self.update_status_indicators()
    
    def _show_confirmation_dialog_with_options(self, title: str, message: str, options: List[str]) -> int:
        """Show a confirmation dialog with custom options, returns index of selected option or -1 for cancel"""
        dialog = Gtk.Dialog(title=title, parent=self.window, flags=0)
        
        # Add buttons in reverse order (GTK displays them right to left)
        for i, option in enumerate(reversed(options)):
            dialog.add_button(option, len(options) - 1 - i)
        
        dialog.set_default_size(450, 200)
        
        content_area = dialog.get_content_area()
        
        label = Gtk.Label(label=message)
        label.set_line_wrap(True)
        label.set_margin_start(20)
        label.set_margin_end(20)
        label.set_margin_top(20)
        label.set_margin_bottom(20)
        content_area.pack_start(label, True, True, 0)
        
        content_area.show_all()
        response = dialog.run()
        dialog.destroy()
        
        # Return the index of the selected option, or -1 for cancel/close
        if response >= 0 and response < len(options):
            return response
        return -1
    
    def _show_multiple_matches_dialog(self, matching_configs, available_configs, config_d_dir):
        """Show dialog for multiple matching configurations"""
        dialog = Gtk.Dialog(title="Select HAT Configuration", parent=self.window, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                          "Use Selected", Gtk.ResponseType.OK,
                          "Show All Options", Gtk.ResponseType.APPLY)
        dialog.set_default_size(450, 350)
        
        content_area = dialog.get_content_area()
        
        hat_product = self.hardware.hat_info.get('product', 'Unknown') if self.hardware.hat_info else 'None'
        hat_vendor = self.hardware.hat_info.get('vendor', 'Unknown') if self.hardware.hat_info else 'Unknown'
        
        label = Gtk.Label(label=f"Detected HAT: {hat_vendor} {hat_product}\n\nMultiple matching configurations found:")
        label.get_style_context().add_class("subtitle")
        label.set_margin_start(10)
        label.set_margin_end(10)
        label.set_margin_top(10)
        content_area.pack_start(label, False, False, 0)
        
        # Scrolled window for radio buttons
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(400, 200)
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)
        content_area.pack_start(scrolled, True, True, 5)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        scrolled.add(vbox)
        
        # Radio buttons for configs
        group = None
        selected_config = None
        
        for config in matching_configs:
            config_type = "Folder" if config.is_dir() else "File"
            radio = Gtk.RadioButton.new_with_label_from_widget(group, f"{config.name} ({config_type})")
            if group is None:
                group = radio
                selected_config = config
            vbox.pack_start(radio, False, False, 0)
            radio.config_path = config
            radio.connect("toggled", lambda btn: setattr(self, '_selected_config_path', btn.config_path) if btn.get_active() else None)
        
        self._selected_config_path = selected_config
        
        content_area.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK and hasattr(self, '_selected_config_path'):
            dialog.destroy()
            self._copy_config_item_with_dialogs(self._selected_config_path, config_d_dir)
        elif response == Gtk.ResponseType.APPLY:
            dialog.destroy()
            self._show_all_available_configs_dialog(available_configs, config_d_dir)
        else:
            dialog.destroy()
    
    def _show_all_available_configs_dialog(self, available_configs, config_d_dir):
        """Show all available configurations for user selection with folder navigation"""
        self._show_config_browser_dialog(available_configs, config_d_dir)
    
    def _show_config_browser_dialog(self, available_configs, config_d_dir, current_path=None):
        """Show a file browser-style dialog for configuration selection"""
        if current_path is None:
            current_path = Path(f"{self.config.CONFIG_DIR}/available.d")
        
        dialog = Gtk.Dialog(title="Select Configuration", parent=self.window, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                          "Apply Selected", Gtk.ResponseType.OK)
        dialog.set_default_size(500, 500)
        
        content_area = dialog.get_content_area()
        
        # Header with current path and HAT info
        header_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        header_box.set_margin_start(10)
        header_box.set_margin_end(10)
        header_box.set_margin_top(10)
        content_area.pack_start(header_box, False, False, 0)
        
        hat_product = self.hardware.hat_info.get('product', 'Unknown') if self.hardware.hat_info else 'None'
        hat_vendor = self.hardware.hat_info.get('vendor', 'Unknown') if self.hardware.hat_info else 'Unknown'
        
        hat_label = Gtk.Label(label=f"Detected HAT: {hat_vendor} {hat_product}")
        hat_label.get_style_context().add_class("subtitle")
        header_box.pack_start(hat_label, False, False, 0)
        
        # Current path display
        path_label = Gtk.Label(label=f"Current folder: {current_path}")
        path_label.get_style_context().add_class("status-blue")
        header_box.pack_start(path_label, False, False, 0)
        
        # Navigation buttons
        nav_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        nav_box.set_margin_start(10)
        nav_box.set_margin_end(10)
        content_area.pack_start(nav_box, False, False, 5)
        
        # Back button (only show if not in root)
        available_d_path = Path(f"{self.config.CONFIG_DIR}/available.d")
        if current_path != available_d_path:
            back_button = Gtk.Button(label="← Back")
            back_button.connect("clicked", lambda btn: self._go_back_folder(dialog, current_path.parent, config_d_dir))
            nav_box.pack_start(back_button, False, False, 0)
        
        # Home button (go to available.d root)
        if current_path != available_d_path:
            home_button = Gtk.Button(label="🏠 Root")
            home_button.connect("clicked", lambda btn: self._go_to_root_folder(dialog, config_d_dir))
            nav_box.pack_start(home_button, False, False, 0)
        
        instruction_label = Gtk.Label(label="Double-click folders to open, select files to apply:")
        instruction_label.get_style_context().add_class("subtitle")
        instruction_label.set_margin_start(10)
        instruction_label.set_margin_end(10)
        content_area.pack_start(instruction_label, False, False, 5)
        
        # Scrolled window for file/folder list
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(450, 300)
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)
        content_area.pack_start(scrolled, True, True, 0)
        
        # Create tree view for better file browsing
        self._create_file_tree_view(scrolled, current_path, dialog, config_d_dir)
        
        content_area.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            selection = self.file_tree_view.get_selection()
            model, tree_iter = selection.get_selected()
            if tree_iter:
                file_path_str = model.get_value(tree_iter, 2)  # Full path column
                file_path = Path(file_path_str)
                is_folder = model.get_value(tree_iter, 3)  # Is folder column
                
                if not is_folder:  # Only apply if it's a file
                    dialog.destroy()
                    self._copy_config_item_with_dialogs(file_path, config_d_dir)
                    return
        
        dialog.destroy()
    
    def _create_file_tree_view(self, parent, current_path, dialog, config_d_dir):
        """Create a tree view for file/folder browsing"""
        # Create list store: filename, type, full_path, is_folder
        self.file_store = Gtk.ListStore(str, str, str, bool)
        
        # Populate the store
        self._populate_file_store(current_path)
        
        # Create tree view
        self.file_tree_view = Gtk.TreeView(model=self.file_store)
        self.file_tree_view.set_headers_visible(True)
        
        # Filename column
        filename_renderer = Gtk.CellRendererText()
        filename_column = Gtk.TreeViewColumn("Name", filename_renderer, text=0)
        filename_column.set_sort_column_id(0)
        self.file_tree_view.append_column(filename_column)
        
        # Type column
        type_renderer = Gtk.CellRendererText()
        type_column = Gtk.TreeViewColumn("Type", type_renderer, text=1)
        type_column.set_sort_column_id(1)
        self.file_tree_view.append_column(type_column)
        
        # Handle double-click for folders
        self.file_tree_view.connect("row-activated", self._on_row_activated, dialog, config_d_dir)
        
        parent.add(self.file_tree_view)
    
    def _populate_file_store(self, current_path):
        """Populate the file store with contents of current path"""
        self.file_store.clear()
        
        try:
            # Get all items in current directory
            items = list(current_path.iterdir())
            
            # Sort: folders first, then files
            folders = [item for item in items if item.is_dir()]
            files = [item for item in items if item.is_file() and item.suffix.lower() == '.yaml']
            
            # Add folders
            for folder in sorted(folders):
                self.file_store.append([
                    f"📁 {folder.name}",
                    "Folder",
                    str(folder),
                    True  # is_folder
                ])
            
            # Add YAML files
            for file in sorted(files):
                self.file_store.append([
                    f"📄 {file.name}",
                    "YAML Config",
                    str(file),
                    False  # is_folder
                ])
                
            # If no items found
            if not folders and not files:
                self.file_store.append([
                    "(Empty folder)",
                    "---",
                    "",
                    False
                ])
                
        except Exception as e:
            logging.error(f"Error reading directory {current_path}: {e}")
            self.file_store.append([
                f"Error reading folder: {e}",
                "Error",
                "",
                False
            ])
    
    def _on_row_activated(self, tree_view, path, column, dialog, config_d_dir):
        """Handle double-click on tree view rows"""
        model = tree_view.get_model()
        tree_iter = model.get_iter(path)
        
        file_path_str = model.get_value(tree_iter, 2)  # Full path
        is_folder = model.get_value(tree_iter, 3)  # Is folder
        
        if is_folder and file_path_str:  # Double-clicked on a folder
            folder_path = Path(file_path_str)
            dialog.destroy()
            # Open the folder by creating a new dialog
            self._show_config_browser_dialog([], config_d_dir, folder_path)
    
    def _go_back_folder(self, current_dialog, parent_path, config_d_dir):
        """Navigate back to parent folder"""
        current_dialog.destroy()
        self._show_config_browser_dialog([], config_d_dir, parent_path)
    
    def _go_to_root_folder(self, current_dialog, config_d_dir):
        """Navigate back to available.d root"""
        current_dialog.destroy()
        available_d_path = Path(f"{self.config.CONFIG_DIR}/available.d")
        self._show_config_browser_dialog([], config_d_dir, available_d_path)
    
    def _copy_config_item_with_dialogs(self, source_item: Path, config_d_dir: str):
        """Copy configuration item with proper dialog handling for multiple files"""
        try:
            if source_item.is_file():
                # Copy single YAML file directly
                dest_path = Path(config_d_dir) / source_item.name
                self.system_manager.run_sudo_command(["cp", str(source_item), str(dest_path)])
                logging.info(f"Copied {source_item.name} to config.d")
                
            else:
                # If it's a folder, look for config files inside it
                config_files = list(source_item.glob("*.yaml"))
                if not config_files:
                    raise ConfigurationError(f"No YAML config files found in folder {source_item.name}")
                
                if len(config_files) == 1:
                    # Single config file in folder - copy it
                    config_file = config_files[0]
                    dest_path = Path(config_d_dir) / config_file.name
                    self.system_manager.run_sudo_command(["cp", str(config_file), str(dest_path)])
                    logging.info(f"Copied {config_file.name} from folder {source_item.name} to config.d")
                    
                else:
                    # Multiple config files in folder - ask user to select
                    self._show_file_selection_dialog(config_files, source_item.name, config_d_dir)
                    return  # Return early since dialog will handle the rest
            
            self._show_info_dialog("Configuration Applied",
                f"Configuration '{source_item.name}' has been applied.\nRestart meshtasticd service for changes to take effect.")
            
            self.update_status_indicators()
            
        except Exception as e:
            logging.error(f"Failed to copy config item: {e}")
            self._show_error_dialog("Configuration Error", f"Failed to copy configuration: {e}")
    
    def _show_file_selection_dialog(self, config_files: List[Path], folder_name: str, config_d_dir: str):
        """Show dialog to select from multiple config files in a folder"""
        dialog = Gtk.Dialog(title=f"Select Config from {folder_name}", parent=self.window, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                          "Copy Selected", Gtk.ResponseType.OK)
        dialog.set_default_size(350, 250)
        
        content_area = dialog.get_content_area()
        
        label = Gtk.Label(label=f"Multiple config files found in {folder_name}:")
        label.get_style_context().add_class("subtitle")
        label.set_margin_start(10)
        label.set_margin_end(10)
        label.set_margin_top(10)
        content_area.pack_start(label, False, False, 0)
        
        # Scrolled window for file selection
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(300, 150)
        scrolled.set_margin_start(10)
        scrolled.set_margin_end(10)
        content_area.pack_start(scrolled, True, True, 5)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        scrolled.add(vbox)
        
        # Radio buttons for files
        group = None
        selected_file = None
        
        for config_file in config_files:
            radio = Gtk.RadioButton.new_with_label_from_widget(group, config_file.name)
            if group is None:
                group = radio
                selected_file = config_file
            vbox.pack_start(radio, False, False, 0)
            radio.config_file = config_file
            radio.connect("toggled", lambda btn: setattr(self, '_selected_config_file', btn.config_file) if btn.get_active() else None)
        
        self._selected_config_file = selected_file
        
        content_area.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK and hasattr(self, '_selected_config_file'):
            config_file = self._selected_config_file
            dest_path = Path(config_d_dir) / config_file.name
            self.system_manager.run_sudo_command(["cp", str(config_file), str(dest_path)])
            logging.info(f"Copied {config_file.name} from folder {folder_name} to config.d")
            
            dialog.destroy()
            
            self._show_info_dialog("Configuration Applied",
                f"Configuration '{config_file.name}' has been applied.\nRestart meshtasticd service for changes to take effect.")
            
            self.update_status_indicators()
        else:
            dialog.destroy()
    
    def handle_edit_config(self, widget):
        """Handle config file editing"""
        self._edit_config_file()
    
    def handle_enable_boot(self, widget):
        """Handle enabling meshtasticd on boot"""
        if self.status_checker.check_meshtasticd_boot_status():
            logging.info("meshtasticd is already enabled on boot")
        else:
            self._run_operation_with_progress(
                "enable_boot",
                self._enable_boot_service,
                "Enabling meshtasticd on boot...",
                lambda result: self.update_status_indicators()
            )
    
    def handle_start_stop(self, widget):
        """Handle starting/stopping meshtasticd service"""
        if self.status_checker.check_meshtasticd_service_status():
            self._run_operation_with_progress(
                "stop_service",
                self._stop_service,
                "Stopping meshtasticd service...",
                lambda result: self.update_status_indicators()
            )
        else:
            self._run_operation_with_progress(
                "start_service",
                self._start_service,
                "Starting meshtasticd service...",
                lambda result: self.update_status_indicators()
            )
    
    def handle_install_python_cli(self, widget):
        """Handle Python CLI installation"""
        if self.status_checker.check_python_cli_status():
            if self._show_question_dialog("Python CLI Installed", 
                                       "Meshtastic Python CLI is already installed.\nDo you want to reinstall/upgrade it?"):
                self._install_python_cli()
            else:
                self._show_python_cli_version()
        else:
            self._install_python_cli()
    
    def handle_send_message(self, widget):
        """Handle sending a message via Meshtastic CLI"""
        if not self.status_checker.check_python_cli_status():
            self._show_error_dialog("Python CLI Required", 
                               "Meshtastic Python CLI is not installed.\nPlease install it first using the 'Install Python CLI' button.")
            return
        
        self._show_send_message_dialog()
    
    def handle_set_region(self, widget):
        """Handle setting LoRa region"""
        if not self.status_checker.check_python_cli_status():
            self._show_error_dialog("Python CLI Required", 
                               "Meshtastic Python CLI is not installed.\nPlease install it first using the 'Install Python CLI' button.")
            return
        
        self._show_region_selection_dialog()
    
    def handle_enable_disable_avahi(self, widget):
        """Handle Avahi setup/removal for auto-discovery"""
        if self.status_checker.check_avahi_status():
            if self._show_question_dialog("Disable Avahi", 
                                       "Avahi is currently enabled. Do you want to disable it?\n\nThis will:\n• Remove the Meshtastic service file\n• Stop the avahi-daemon service\n• Disable avahi-daemon from starting on boot"):
                self._run_operation_with_progress(
                    "disable_avahi",
                    self._disable_avahi,
                    "Disabling Avahi...",
                    lambda result: self.update_status_indicators()
                )
        else:
            self._run_operation_with_progress(
                "enable_avahi",
                self._enable_avahi,
                "Enabling Avahi...",
                lambda result: self.update_status_indicators()
            )
    
    # Operation Implementation Methods
    def _enable_spi(self) -> OperationResult:
        """Enable SPI interface"""
        try:
            logging.info("Enabling SPI interface...")
            
            # Enable SPI via raspi-config
            self.system_manager.run_sudo_command(["raspi-config", "nonint", "do_spi", "0"])
            
            # Backup and modify config file
            backup_path = self.system_manager.backup_file(self.config.BOOT_CONFIG_FILE)
            logging.info(f"Backed up config.txt to {backup_path}")
            
            # Read current config
            result = self.system_manager.run_sudo_command(["cat", self.config.BOOT_CONFIG_FILE])
            config_content = result.stdout
            
            # Add SPI configurations
            config_updated = False
            if "dtparam=spi=on" not in config_content:
                config_content += "\n# SPI Configuration\ndtparam=spi=on\n"
                config_updated = True
                logging.info("Added SPI parameter to config.txt")
            
            if "dtoverlay=spi0-0cs" not in config_content:
                if not config_updated:
                    config_content += "\n# SPI Configuration\n"
                config_content += "dtoverlay=spi0-0cs\n"
                config_updated = True
                logging.info("Added SPI overlay to config.txt")
            
            if config_updated:
                self.system_manager.run_sudo_command(["tee", self.config.BOOT_CONFIG_FILE], 
                                                   input_text=config_content)
                logging.info("SPI configuration updated in config.txt")
            else:
                logging.info("SPI configuration already present in config.txt")
            
            logging.info("SPI configuration complete. Reboot may be required.")
            return OperationResult(True, "SPI enabled successfully")
            
        except Exception as e:
            raise ConfigurationError(f"SPI configuration failed: {e}")
    
    def _enable_i2c(self) -> OperationResult:
        """Enable I2C interface"""
        try:
            logging.info("Enabling I2C interface...")
            
            # Enable I2C via raspi-config
            self.system_manager.run_sudo_command(["raspi-config", "nonint", "do_i2c", "0"])
            
            # Backup and modify config file
            backup_path = self.system_manager.backup_file(self.config.BOOT_CONFIG_FILE)
            logging.info(f"Backed up config.txt to {backup_path}")
            
            # Read current config
            result = self.system_manager.run_sudo_command(["cat", self.config.BOOT_CONFIG_FILE])
            config_content = result.stdout
            
            # Add I2C configuration
            if "dtparam=i2c_arm=on" not in config_content:
                config_content += "\n# I2C Configuration\ndtparam=i2c_arm=on\n"
                self.system_manager.run_sudo_command(["tee", self.config.BOOT_CONFIG_FILE], 
                                                   input_text=config_content)
                logging.info("Added I2C ARM parameter to config.txt")
            else:
                logging.info("I2C ARM parameter already present in config.txt")
            
            logging.info("I2C configuration complete. Reboot may be required.")
            return OperationResult(True, "I2C enabled successfully")
            
        except Exception as e:
            raise ConfigurationError(f"I2C configuration failed: {e}")
    
    def _enable_gps_uart(self) -> OperationResult:
        """Enable GPS/UART interface"""
        try:
            logging.info("Enabling GPS/UART interface...")
            
            # Backup and modify config file
            backup_path = self.system_manager.backup_file(self.config.BOOT_CONFIG_FILE)
            logging.info(f"Backed up config.txt to {backup_path}")
            
            # Read current config
            result = self.system_manager.run_sudo_command(["cat", self.config.BOOT_CONFIG_FILE])
            config_content = result.stdout
            
            config_updated = False
            
            # Add enable_uart=1
            if "enable_uart=1" not in config_content:
                config_content += "\n# GPS/UART Configuration\nenable_uart=1\n"
                config_updated = True
                logging.info("Added enable_uart=1 to config.txt")
            
            # Add uart0 overlay for Pi 5
            if self.hardware.is_pi5() and "dtoverlay=uart0" not in config_content:
                if not config_updated:
                    config_content += "\n# GPS/UART Configuration\n"
                config_content += "dtoverlay=uart0\n"
                config_updated = True
                logging.info("Added uart0 overlay for Pi 5 to config.txt")
            
            if config_updated:
                self.system_manager.run_sudo_command(["tee", self.config.BOOT_CONFIG_FILE], 
                                                   input_text=config_content)
                logging.info("GPS/UART configuration written to config.txt")
            
            # Disable serial console
            logging.info("Disabling serial console to prevent UART conflicts...")
            result = self.system_manager.run_sudo_command(["raspi-config", "nonint", "do_serial_cons", "1"])
            if result.returncode == 0:
                logging.info("✅ Serial console disabled successfully")
            else:
                logging.warning("⚠️ Failed to disable serial console")
            
            logging.info("GPS/UART configuration complete. Reboot required.")
            return OperationResult(True, "GPS/UART enabled successfully")
            
        except Exception as e:
            raise ConfigurationError(f"GPS/UART configuration failed: {e}")
    
    def _configure_meshadv_mini(self) -> OperationResult:
        """Configure MeshAdv Mini specific settings"""
        try:
            logging.info("Configuring MeshAdv Mini GPIO and PPS settings...")
            
            # Backup config file
            backup_path = self.system_manager.backup_file(self.config.BOOT_CONFIG_FILE)
            logging.info(f"Backed up config.txt to {backup_path}")
            
            # Read current config
            result = self.system_manager.run_sudo_command(["cat", self.config.BOOT_CONFIG_FILE])
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
                config_content += meshadv_config
                self.system_manager.run_sudo_command(["tee", self.config.BOOT_CONFIG_FILE], 
                                                   input_text=config_content)
                logging.info("MeshAdv Mini configuration added to config.txt")
                logging.info("Reboot required for changes to take effect")
                
                GLib.idle_add(self._show_info_dialog, "Configuration Complete", 
                            "MeshAdv Mini configuration added.\nReboot required for changes to take effect.")
            else:
                logging.info("MeshAdv Mini configuration already present")
            
            return OperationResult(True, "MeshAdv Mini configured successfully")
            
        except Exception as e:
            raise ConfigurationError(f"MeshAdv Mini configuration failed: {e}")

    
    def _edit_config_file(self):
        """Handle config file editing"""
        config_file = f"{self.config.CONFIG_DIR}/config.yaml"
        
        try:
            if not os.path.exists(config_file):
                if self._show_question_dialog("Create Config File", 
                                           f"Config file {config_file} does not exist.\nCreate it now?"):
                    os.makedirs(self.config.CONFIG_DIR, exist_ok=True)
                    with open(config_file, 'w') as f:
                        f.write("# Meshtastic Configuration\n")
                        f.write("# Edit this file to configure your device\n\n")
                    logging.info(f"Created new config file: {config_file}")
                else:
                    return
            
            logging.info(f"Opening config file in nano: {config_file}")
            
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
                self._show_info_dialog("Edit Config File",
                    f"Could not open terminal automatically.\n\nPlease run this command manually:\nsudo nano {config_file}\n\nOr edit the file with your preferred editor.")
                logging.warning("Could not open terminal automatically")
                
        except Exception as e:
            logging.error(f"Failed to edit config file: {e}")
            self._show_error_dialog("Error", f"Failed to edit config file: {e}")
    
    def _enable_boot_service(self) -> OperationResult:
        """Enable meshtasticd to start on boot"""
        try:
            logging.info("Enabling meshtasticd to start on boot...")
            result = self.system_manager.run_sudo_command(["systemctl", "enable", self.config.PKG_NAME])
            
            if result.returncode == 0:
                logging.info("✅ meshtasticd enabled to start on boot")
                return OperationResult(True, "Boot service enabled")
            else:
                raise MeshtasticError(f"Failed to enable boot service: {result.stderr}")
                
        except Exception as e:
            raise MeshtasticError(f"Boot service configuration failed: {e}")
    
    def _start_service(self) -> OperationResult:
        """Start meshtasticd service"""
        try:
            logging.info("Starting meshtasticd service...")
            result = self.system_manager.run_sudo_command(["systemctl", "start", self.config.PKG_NAME])
            
            if result.returncode == 0:
                logging.info("✅ meshtasticd service started")
                return OperationResult(True, "Service started")
            else:
                raise MeshtasticError(f"Failed to start service: {result.stderr}")
                
        except Exception as e:
            raise MeshtasticError(f"Service start failed: {e}")
    
    def _stop_service(self) -> OperationResult:
        """Stop meshtasticd service"""
        try:
            logging.info("Stopping meshtasticd service...")
            result = self.system_manager.run_sudo_command(["systemctl", "stop", self.config.PKG_NAME])
            
            if result.returncode == 0:
                logging.info("✅ meshtasticd service stopped")
                return OperationResult(True, "Service stopped")
            else:
                raise MeshtasticError(f"Failed to stop service: {result.stderr}")
                
        except Exception as e:
            raise MeshtasticError(f"Service stop failed: {e}")
    
    def _install_python_cli(self):
        """Install Meshtastic Python CLI with progress"""
        self._run_operation_with_progress(
            "install_cli",
            self._perform_python_cli_install,
            "Installing Meshtastic Python CLI...",
            lambda result: self._on_cli_install_success(result),
            lambda error: self._show_error_dialog("Installation Failed", str(error))
        )
    
    def _perform_python_cli_install(self) -> OperationResult:
        """Perform the actual Python CLI installation"""
        try:
            logging.info("="*50)
            logging.info("STARTING MESHTASTIC PYTHON CLI INSTALLATION")
            logging.info("="*50)
            
            # Step 1: Install python3-full
            logging.info("Step 1/5: Installing python3-full...")
            result = self.system_manager.run_sudo_command(["apt", "install", "-y", "python3-full"], 
                                                        timeout=self.config.DEFAULT_TIMEOUT)
            if result.returncode == 0:
                logging.info("✅ python3-full installed successfully")
            else:
                logging.warning("⚠️ python3-full installation had issues, continuing...")
            
            # Step 2: Install pytap2 via pip3
            logging.info("Step 2/5: Installing pytap2 via pip3...")
            try:
                result = self.system_manager.run_command(
                    ["pip3", "install", "--upgrade", "pytap2", "--break-system-packages"],
                    timeout=self.config.DEFAULT_TIMEOUT
                )
                if result.returncode == 0:
                    logging.info("✅ pytap2 installed successfully")
                else:
                    logging.warning(f"⚠️ pytap2 installation warning, continuing...")
            except Exception as e:
                logging.warning(f"⚠️ pytap2 installation issue: {e}, continuing...")
            
            # Step 3: Install pipx
            logging.info("Step 3/5: Installing pipx...")
            result = self.system_manager.run_sudo_command(["apt", "install", "-y", "pipx"], 
                                                        timeout=self.config.DEFAULT_TIMEOUT)
            if result.returncode != 0:
                raise InstallationError("Failed to install pipx")
            logging.info("✅ pipx installed successfully")
            
            # Step 4: Install meshtastic CLI via pipx
            logging.info("Step 4/5: Installing Meshtastic CLI via pipx...")
            logging.info("This may take several minutes...")
            result = self.system_manager.run_command(
                ["pipx", "install", "meshtastic[cli]"],
                timeout=600  # 10 minute timeout
            )
            if result.returncode != 0:
                raise InstallationError(f"Failed to install Meshtastic CLI: {result.stderr}")
            logging.info("✅ Meshtastic CLI installed successfully via pipx")
            
            # Step 5: Ensure pipx path
            logging.info("Step 5/5: Ensuring pipx PATH configuration...")
            try:
                result = self.system_manager.run_command(["pipx", "ensurepath"], timeout=60)
                if result.returncode == 0:
                    logging.info("✅ pipx PATH configured successfully")
                else:
                    logging.warning(f"⚠️ pipx ensurepath warning")
            except Exception as e:
                logging.warning(f"⚠️ pipx ensurepath issue: {e}")
            
            # Step 6: Verify installation
            logging.info("Step 6/6: Verifying installation...")
            try:
                result = self.system_manager.run_command(["meshtastic", "--version"], timeout=30)
                if result.returncode == 0:
                    version_info = result.stdout.strip()
                    logging.info(f"✅ INSTALLATION COMPLETED SUCCESSFULLY!")
                    logging.info(f"Meshtastic CLI version: {version_info}")
                    return OperationResult(True, f"CLI installed: {version_info}")
                else:
                    logging.warning("⚠️ Installation completed but version check failed")
                    return OperationResult(True, "CLI installed (restart required)")
            except Exception as e:
                logging.warning(f"⚠️ Version check failed: {e}")
                return OperationResult(True, "CLI installed (verification failed)")
                
        except Exception as e:
            raise InstallationError(f"Python CLI installation failed: {e}")
    
    def _on_cli_install_success(self, result: OperationResult):
        """Handle successful CLI installation"""
        self.update_status_indicators()
        self._show_info_dialog(
            "Installation Complete - Restart Required",
            f"Meshtastic Python CLI installed successfully!\n\n"
            f"IMPORTANT: To use the CLI commands, you need to:\n"
            f"1. Close this application\n"
            f"2. Close your terminal\n"
            f"3. Open a new terminal\n"
            f"4. Test with: meshtastic --version\n\n"
            f"The PATH environment needs to be refreshed."
        )
    
    def _show_python_cli_version(self):
        """Show current Python CLI version"""
        def worker():
            try:
                logging.info("Checking Meshtastic Python CLI version...")
                result = self.system_manager.run_command(["meshtastic", "--version"])
                if result.returncode == 0:
                    logging.info(f"✅ Meshtastic Python CLI version: {result.stdout.strip()}")
                else:
                    logging.error("❌ Failed to get Python CLI version")
            except Exception as e:
                logging.error(f"Error checking Python CLI version: {e}")
                
        self.thread_manager.submit_task(worker)
    
    def _show_send_message_dialog(self):
        """Show dialog for sending messages"""
        dialog = Gtk.Dialog(title="Send Meshtastic Message", parent=self.window, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                          "Send Message", Gtk.ResponseType.OK)
        dialog.set_default_size(450, 250)
        
        content_area = dialog.get_content_area()
        
        # Title
        title_label = Gtk.Label(label="Send Message to Mesh Network")
        title_label.get_style_context().add_class("subtitle")
        content_area.pack_start(title_label, False, False, 10)
        
        # Instructions
        instruction_label = Gtk.Label(label="Enter the message you want to send to the mesh:")
        content_area.pack_start(instruction_label, False, False, 5)
        
        # Message input
        message_entry = Gtk.Entry()
        message_entry.set_max_length(200)
        message_entry.set_activates_default(True)
        content_area.pack_start(message_entry, False, False, 10)
        
        # Character counter
        char_label = Gtk.Label(label="0/200 characters")
        char_label.get_style_context().add_class("status-orange")
        content_area.pack_start(char_label, False, False, 0)
        
        # Update character count on text change
        def update_char_count(entry):
            count = len(entry.get_text())
            char_label.set_text(f"{count}/200 characters")
            if count > 200:
                char_label.get_style_context().remove_class("status-orange")
                char_label.get_style_context().add_class("status-red")
            else:
                char_label.get_style_context().remove_class("status-red")
                char_label.get_style_context().add_class("status-orange")
        
        message_entry.connect("changed", update_char_count)
        
        # Set default button
        dialog.set_default_response(Gtk.ResponseType.OK)
        
        content_area.show_all()
        message_entry.grab_focus()
        
        response = dialog.run()
        message_text = message_entry.get_text().strip()
        dialog.destroy()
        
        if response == Gtk.ResponseType.OK:
            if not message_text:
                self._show_error_dialog("Empty Message", "Please enter a message to send.")
                return
            if len(message_text) > 200:
                self._show_error_dialog("Message Too Long", "Message must be 200 characters or less.")
                return
            
            self._send_mesh_message(message_text)
    
    def _send_mesh_message(self, message_text: str):
        """Send message to mesh network"""
        def send_operation():
            try:
                logging.info(f"Sending message to mesh: '{message_text}'")
                result = self.system_manager.run_command(
                    ["meshtastic", "--host", "localhost", "--sendtext", message_text],
                    timeout=self.config.CLI_TIMEOUT
                )
                
                if result.returncode == 0:
                    logging.info("✅ Message sent successfully!")
                    if result.stdout.strip():
                        logging.info(f"Response: {result.stdout.strip()}")
                    return OperationResult(True, "Message sent successfully")
                else:
                    error_msg = result.stderr.strip() if result.stderr.strip() else "Unknown error"
                    raise MeshtasticError(f"Failed to send message: {error_msg}")
                    
            except Exception as e:
                raise MeshtasticError(f"Message sending failed: {e}")
        
        def on_success(result):
            self._show_info_dialog("Message Sent", 
                                 f"Message sent successfully to the mesh network!\n\nMessage: '{message_text}'")
        
        def on_error(error):
            self._show_error_dialog("Message Failed", 
                                  f"Failed to send message to mesh network.\n\nError: {str(error)}\n\nMake sure meshtasticd is running and a device is connected.")
        
        self._run_operation_with_progress(
            "send_message",
            send_operation,
            "Sending message...",
            on_success,
            on_error
        )
    
    def _show_region_selection_dialog(self):
        """Show dialog for region selection"""
        current_region = self.status_checker.check_lora_region_status()
        
        dialog = Gtk.Dialog(title="Set LoRa Region", parent=self.window, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                          "Apply Region", Gtk.ResponseType.OK)
        dialog.set_default_size(800, 650)
        
        content_area = dialog.get_content_area()
        
        # Title and current status
        title_label = Gtk.Label(label="Set LoRa Region")
        title_label.get_style_context().add_class("subtitle")
        content_area.pack_start(title_label, False, False, 10)
        
        current_label = Gtk.Label(label=f"Current Region: {current_region}")
        content_area.pack_start(current_label, False, False, 5)
        
        if current_region == "UNSET":
            warning_label = Gtk.Label(label="⚠️ Region is UNSET - This must be configured!")
            warning_label.get_style_context().add_class("status-red")
            content_area.pack_start(warning_label, False, False, 5)
        
        # Instructions
        instruction_label = Gtk.Label(label="Select your region (most common options at top):")
        content_area.pack_start(instruction_label, False, False, 10)
        
        # Scrolled window for region selection
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_size_request(750, 300)
        content_area.pack_start(scrolled, True, True, 0)
        
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        scrolled.add(vbox)
        
        # Define regions
        regions = [
            ("US", "United States (902-928 MHz)"),
            ("EU_868", "Europe 868 MHz"),
            ("ANZ", "Australia/New Zealand (915-928 MHz)"),
            ("", "─── Other Regions ───"),
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
        
        # Radio buttons for regions
        group = None
        selected_region = current_region if current_region != "UNSET" else "US"
        
        for region_code, region_name in regions:
            if region_code == "":  # Separator
                separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
                vbox.pack_start(separator, False, False, 5)
                sep_label = Gtk.Label(label=region_name)
                sep_label.get_style_context().add_class("subtitle")
                vbox.pack_start(sep_label, False, False, 2)
                continue
            
            radio = Gtk.RadioButton.new_with_label_from_widget(group, f"{region_code} - {region_name}")
            if group is None:
                group = radio
            
            if region_code == selected_region:
                radio.set_active(True)
            
            radio.region_code = region_code
            radio.connect("toggled", lambda btn: setattr(self, 'selected_region_code', btn.region_code) if btn.get_active() else None)
            vbox.pack_start(radio, False, False, 0)
            
            # Highlight current region
            if region_code == current_region:
                radio.get_style_context().add_class("status-green")
        
        self.selected_region_code = selected_region
        
        # Warning for UNSET
        if current_region == "UNSET":
            warning_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            warning_box.set_margin_start(20)
            warning_box.set_margin_end(20)
            
            warning1 = Gtk.Label(label="⚠️ Important: Setting the wrong region may violate local regulations!")
            warning1.get_style_context().add_class("status-red")
            warning_box.pack_start(warning1, False, False, 0)
            
            warning2 = Gtk.Label(label="Make sure to select the correct region for your location.")
            warning2.get_style_context().add_class("status-red")
            warning_box.pack_start(warning2, False, False, 0)
            
            content_area.pack_start(warning_box, False, False, 10)
        
        content_area.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            new_region = self.selected_region_code
            dialog.destroy()
            
            if new_region == current_region:
                self._show_info_dialog("No Change", f"Region is already set to {new_region}")
                return
            
            self._set_lora_region(new_region, current_region)
        else:
            dialog.destroy()
    
    def _set_lora_region(self, new_region: str, old_region: str):
        """Set the LoRa region"""
        def set_region_operation():
            try:
                logging.info(f"Changing LoRa region from {old_region} to {new_region}...")
                result = self.system_manager.run_command(
                    ["meshtastic", "--host", "localhost", "--set", "lora.region", new_region],
                    timeout=self.config.CLI_TIMEOUT
                )
                
                if result.returncode == 0:
                    logging.info("✅ LoRa region updated successfully!")
                    if result.stdout.strip():
                        logging.info(f"Response: {result.stdout.strip()}")
                    return OperationResult(True, f"Region changed from {old_region} to {new_region}")
                else:
                    error_msg = result.stderr.strip() if result.stderr.strip() else "Unknown error"
                    raise MeshtasticError(f"Failed to set LoRa region: {error_msg}")
                    
            except Exception as e:
                raise MeshtasticError(f"Region setting failed: {e}")
        
        def on_success(result):
            self.update_status_indicators()
            self._show_info_dialog("Region Updated",
                f"LoRa region updated successfully!\n\nChanged from: {old_region}\nChanged to: {new_region}\n\nThe device may need to restart for changes to take full effect.")
        
        def on_error(error):
            self._show_error_dialog("Region Update Failed",
                f"Failed to update LoRa region.\n\nError: {str(error)}\n\nMake sure meshtasticd is running and a device is connected.")
        
        self._run_operation_with_progress(
            "set_region",
            set_region_operation,
            "Setting LoRa region...",
            on_success,
            on_error
        )
    
    def _enable_avahi(self) -> OperationResult:
        """Enable Avahi for auto-discovery"""
        try:
            logging.info("="*50)
            logging.info("STARTING AVAHI SETUP")
            logging.info("="*50)
            
            # Check if avahi-daemon is installed
            logging.info("Step 1/4: Checking if avahi-daemon is installed...")
            avahi_installed = self.system_manager.check_package_installed("avahi-daemon")
            
            if not avahi_installed:
                logging.info("Installing avahi-daemon...")
                self.system_manager.run_sudo_command(["apt", "update"], timeout=120)
                result = self.system_manager.run_sudo_command(["apt", "install", "-y", "avahi-daemon"], 
                                                            timeout=300)
                if result.returncode != 0:
                    raise InstallationError("Failed to install avahi-daemon")
                logging.info("✅ avahi-daemon installed successfully")
            else:
                logging.info("✅ avahi-daemon is already installed")
            
            # Create service file
            logging.info("Step 2/4: Creating Meshtastic service file...")
            service_file = "/etc/avahi/services/meshtastic.service"
            service_content = """<?xml version="1.0" standalone="no"?><!--*-nxml-*-->
<!DOCTYPE service-group SYSTEM "avahi-service.dtd">
<service-group>
<n>Meshtastic</n>
<service protocol="ipv4">
<type>_meshtastic._tcp</type>
<port>4403</port>
</service>
</service-group>"""
            
            self.system_manager.run_sudo_command(["mkdir", "-p", "/etc/avahi/services"])
            result = self.system_manager.run_sudo_command(["tee", service_file], 
                                                        input_text=service_content)
            
            if result.returncode == 0:
                logging.info("✅ Meshtastic service file created successfully")
            else:
                raise ConfigurationError("Failed to create service file")
            
            # Enable and start service
            logging.info("Step 3/4: Enabling avahi-daemon service...")
            self.system_manager.run_sudo_command(["systemctl", "enable", "avahi-daemon"])
            
            logging.info("Step 4/4: Starting avahi-daemon service...")
            self.system_manager.run_sudo_command(["systemctl", "start", "avahi-daemon"])
            
            logging.info("✅ AVAHI SETUP COMPLETED SUCCESSFULLY!")
            logging.info("Android clients can now auto-discover this device")
            
            return OperationResult(True, "Avahi enabled successfully")
            
        except Exception as e:
            raise ConfigurationError(f"Avahi setup failed: {e}")
    
    def _disable_avahi(self) -> OperationResult:
        """Disable Avahi and remove Meshtastic service"""
        try:
            logging.info("="*50)
            logging.info("STARTING AVAHI REMOVAL")
            logging.info("="*50)
            
            # Stop service
            logging.info("Step 1/3: Stopping avahi-daemon service...")
            self.system_manager.run_sudo_command(["systemctl", "stop", "avahi-daemon"])
            logging.info("✅ avahi-daemon service stopped")
            
            # Disable service
            logging.info("Step 2/3: Disabling avahi-daemon...")
            self.system_manager.run_sudo_command(["systemctl", "disable", "avahi-daemon"])
            logging.info("✅ avahi-daemon disabled")
            
            # Remove service file
            logging.info("Step 3/3: Removing Meshtastic service file...")
            service_file = "/etc/avahi/services/meshtastic.service"
            
            if os.path.exists(service_file):
                self.system_manager.run_sudo_command(["rm", service_file])
                logging.info("✅ Meshtastic service file removed")
            else:
                logging.info("ℹ️ Meshtastic service file was not found")
            
            logging.info("✅ AVAHI REMOVAL COMPLETED SUCCESSFULLY!")
            
            return OperationResult(True, "Avahi disabled successfully")
            
        except Exception as e:
            raise ConfigurationError(f"Avahi removal failed: {e}")
    
    def _install_meshtasticd(self):
        """Install meshtasticd with channel selection"""
        # Show channel selection dialog
        dialog = Gtk.Dialog(title="Select Channel", parent=self.window, flags=0)
        dialog.add_buttons(Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL,
                          "Install", Gtk.ResponseType.OK)
        dialog.set_default_size(300, 250)
        
        content_area = dialog.get_content_area()
        
        title_label = Gtk.Label(label="Select Meshtastic Channel:")
        title_label.get_style_context().add_class("subtitle")
        content_area.pack_start(title_label, False, False, 10)
        
        # Radio buttons for channels
        group = None
        selected_channel = "beta"
        
        channels = [
            ("beta", "Beta (Safe)"),
            ("alpha", "Alpha (Might be safe, might not)"),
            ("daily", "Daily (Are you mAd MAn?)")
        ]
        
        for channel_code, channel_name in channels:
            radio = Gtk.RadioButton.new_with_label_from_widget(group, channel_name)
            if group is None:
                group = radio
                radio.set_active(True)
            
            radio.channel_code = channel_code
            radio.connect("toggled", lambda btn: setattr(self, 'selected_channel_code', btn.channel_code) if btn.get_active() else None)
            content_area.pack_start(radio, False, False, 5)
        
        self.selected_channel_code = selected_channel
        
        content_area.show_all()
        response = dialog.run()
        
        if response == Gtk.ResponseType.OK:
            channel = self.selected_channel_code
            dialog.destroy()
            
            self._run_operation_with_progress(
                "install_meshtasticd",
                lambda: self._perform_installation(channel),
                f"Installing meshtasticd ({channel} channel)...",
                lambda result: self._on_install_success(),
                lambda error: self._show_error_dialog("Installation Failed", str(error))
            )
        else:
            dialog.destroy()
    
    def _perform_installation(self, channel: str) -> OperationResult:
        """Perform the actual installation"""
        try:
            logging.info("="*50)
            logging.info(f"STARTING MESHTASTIC INSTALLATION - {channel.upper()} CHANNEL")
            logging.info("="*50)
            
            # Step 1: Create repository configuration
            repo_url = f"http://download.opensuse.org/repositories/network:/Meshtastic:/{channel}/{self.config.OS_VERSION}/"
            list_file = f"{self.config.REPO_DIR}/{self.config.REPO_PREFIX}:{channel}.list"
            gpg_file = f"{self.config.GPG_DIR}/network_Meshtastic_{channel}.gpg"
            
            logging.info(f"Step 1/5: Creating repository configuration...")
            repo_content = f"deb {repo_url} /\n"
            result = self.system_manager.run_sudo_command(["tee", list_file], input_text=repo_content)
            if result.returncode != 0:
                raise InstallationError("Failed to create repository file")
            logging.info(f"✅ Repository file created successfully")
            
            # Step 2: Download GPG key
            logging.info(f"Step 2/5: Downloading GPG key...")
            result = self.system_manager.run_command(["curl", "-fsSL", f"{repo_url}Release.key"])
            if result.returncode != 0:
                raise InstallationError("Failed to download GPG key")
            logging.info(f"✅ GPG key downloaded successfully")
            
            # Step 3: Process and install GPG key
            logging.info(f"Step 3/5: Processing GPG key...")
            gpg_process = subprocess.Popen(
                ["gpg", "--dearmor"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            gpg_output, gpg_error = gpg_process.communicate(input=result.stdout.encode('utf-8'))
            
            if gpg_process.returncode != 0:
                raise InstallationError("GPG key processing failed")
            
            # Write GPG key (binary data, so we need to write it directly)
            try:
                # Use a different approach to write binary data
                with open('/tmp/temp_gpg_key', 'wb') as temp_file:
                    temp_file.write(gpg_output)
                
                # Move the temporary file to the final location using sudo
                write_result = self.system_manager.run_sudo_command(["mv", "/tmp/temp_gpg_key", gpg_file])
                if write_result.returncode != 0:
                    raise InstallationError("Failed to install GPG key")
                
                # Set proper permissions
                self.system_manager.run_sudo_command(["chmod", "644", gpg_file])
                
            except Exception as e:
                # Clean up temp file if it exists
                try:
                    os.remove('/tmp/temp_gpg_key')
                except:
                    pass
                raise InstallationError(f"Failed to write GPG key: {e}")
            
            logging.info(f"✅ GPG key installed successfully")
            
            # Step 4: Update package database
            logging.info(f"Step 4/5: Updating package database...")
            result = self.system_manager.run_sudo_command(["apt", "update"], timeout=120)
            if result.returncode != 0:
                logging.warning(f"⚠️ Package update had issues, continuing anyway")
            else:
                logging.info(f"✅ Package database updated successfully")
            
            # Step 5: Install package
            logging.info(f"Step 5/5: Installing meshtasticd package...")
            
            # Set non-interactive environment
            env = os.environ.copy()
            env['DEBIAN_FRONTEND'] = 'noninteractive'
            
            install_cmd = ["sudo", "-E", "apt", "install", "-y", 
                          "-o", "Dpkg::Options::=--force-confdef", 
                          "-o", "Dpkg::Options::=--force-confold", 
                          self.config.PKG_NAME]
            
            result = subprocess.run(
                install_cmd,
                capture_output=True, 
                text=True, 
                timeout=self.config.APT_TIMEOUT, 
                env=env
            )
            
            if result.returncode == 0:
                logging.info(f"✅ INSTALLATION COMPLETED SUCCESSFULLY!")
                logging.info(f"Meshtasticd {channel} channel has been installed")
                return OperationResult(True, f"Meshtasticd {channel} installed successfully")
            else:
                logging.error(f"❌ Installation failed")
                if result.stderr.strip():
                    logging.error(f"Error details: {result.stderr}")
                raise InstallationError(f"Package installation failed: {result.stderr}")
            
        except Exception as e:
            logging.error(f"❌ INSTALLATION ERROR: {e}")
            raise InstallationError(f"Installation failed: {e}")
    
    def _on_install_success(self):
        """Handle successful installation"""
        # Update status after a brief delay to ensure package is registered
        GLib.timeout_add(2000, self.update_status_indicators)
        # Force immediate version update
        GLib.timeout_add(2000, self._update_version_display)
        self._show_info_dialog("Installation Complete", 
                             "Meshtasticd has been installed successfully!\nYou can now configure and start the service.")
    
    def _remove_meshtasticd(self):
        """Remove meshtasticd"""
        self._run_operation_with_progress(
            "remove_meshtasticd",
            self._perform_removal,
            "Removing meshtasticd...",
            lambda result: self._on_removal_success(),
            lambda error: self._show_error_dialog("Removal Failed", str(error))
        )
    
    def _perform_removal(self) -> OperationResult:
        """Perform the actual removal"""
        try:
            logging.info("="*50)
            logging.info("STARTING MESHTASTIC REMOVAL")
            logging.info("="*50)
            
            # Step 1: Stop service
            logging.info("Step 1/4: Stopping meshtasticd service...")
            result = self.system_manager.run_sudo_command(["systemctl", "stop", self.config.PKG_NAME])
            if result.returncode == 0:
                logging.info("✅ Service stopped successfully")
            else:
                logging.info("ℹ️ Service was not running or already stopped")
            
            # Step 2: Disable service
            logging.info("Step 2/4: Disabling meshtasticd service...")
            result = self.system_manager.run_sudo_command(["systemctl", "disable", self.config.PKG_NAME])
            if result.returncode == 0:
                logging.info("✅ Service disabled successfully")
            else:
                logging.info("ℹ️ Service was not enabled or already disabled")
            
            # Step 3: Remove package
            logging.info("Step 3/4: Removing meshtasticd package...")
            result = self.system_manager.run_sudo_command(["apt", "remove", "--purge", "-y", self.config.PKG_NAME], 
                                                        timeout=300, input_text="n\n")
            
            if result.returncode != 0:
                raise InstallationError("Package removal failed")
            logging.info("✅ Package removed successfully")
            
            # Step 4: Clean up repository files
            logging.info("Step 4/4: Cleaning up repository files...")
            try:
                repo_files = list(Path(self.config.REPO_DIR).glob(f"{self.config.REPO_PREFIX}:*.list"))
                gpg_files = list(Path(self.config.GPG_DIR).glob("network_Meshtastic_*.gpg"))
                
                files_removed = 0
                for repo_file in repo_files:
                    result = self.system_manager.run_sudo_command(["rm", str(repo_file)])
                    if result.returncode == 0:
                        logging.info(f"✅ Removed repository file: {repo_file.name}")
                        files_removed += 1
                    
                for gpg_file in gpg_files:
                    result = self.system_manager.run_sudo_command(["rm", str(gpg_file)])
                    if result.returncode == 0:
                        logging.info(f"✅ Removed GPG key: {gpg_file.name}")
                        files_removed += 1
                        
                if files_removed > 0:
                    logging.info(f"✅ Cleaned up {files_removed} repository files")
                else:
                    logging.info("ℹ️ No repository files found to clean up")
                    
            except Exception as e:
                logging.warning(f"⚠️ Repository cleanup had issues: {e}")
            
            logging.info("✅ REMOVAL COMPLETED SUCCESSFULLY!")
            return OperationResult(True, "Meshtasticd removed successfully")
            
        except Exception as e:
            logging.error(f"❌ REMOVAL ERROR: {e}")
            raise InstallationError(f"Removal failed: {e}")
    
    def _on_removal_success(self):
        """Handle successful removal"""
        self.update_status_indicators()
        # Force immediate version update
        GLib.idle_add(self._update_version_display)
        self._show_info_dialog("Removal Complete", 
                             "Meshtasticd has been completely uninstalled.")
    
    def run(self):
        """Run the application"""
        self.window.show_all()
        try:
            Gtk.main()
        except KeyboardInterrupt:
            print("\nApplication terminated by user")
            self.thread_manager.shutdown(wait=False)
            sys.exit(0)

def main():
    """Main entry point"""
    try:
        app = MeshtasticGTK()
        app.run()
    except Exception as e:
        print(f"Application failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()