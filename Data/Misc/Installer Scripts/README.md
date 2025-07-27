# Installer Scripts 
  
  A collection of helper scripts designed to make your life easier

  ---
## 1. Meshtastic Configuration Tool (Python GUI)

This is a python tool that can do it all, install meshtasticd, setup all the needed /boot/firmware/config.txt options, choose your hat config file, edit /etc/meshtasticd/config.yaml, even help you install other helpful tools like Meshtastic Python CLI. This tool will help get you from fresh install to sending a test message. Designed for Raspberry Pi OS (Bookworm). Tested on Pi 4 and Pi 5. 


  ![](https://github.com/chrismyers2000/MeshAdv-Mini/blob/91b49a7bfb1313022056c8d00c86d2c37b2c1c62/Data/Misc/ConfigTool1.png)
- Installation

  - Copy the python script to your pi
  ```bash
  wget https://raw.githubusercontent.com/chrismyers2000/MeshAdv-Mini/refs/heads/main/Data/Misc/Installer%20Scripts/meshtasticd_config_tool_V2.py
  ```

  - Change permissions to executable
  ```bash
  sudo chmod +x meshtasticd_config_tool_V2.py
  ```

  - Run the script
  ```bash
  ./meshtasticd_config_tool_V2.py
  ```
  - Please note, you will need to reboot a few times for everything to be fully functional
  - After installing Meshtastic CLI, you need to close the GUI and terminal window so the CLI can show up in the proper PATH.
  ---
## 2. Text based installer - Minimal at this point

This is a helper script designed to help you choose which channel (beta/alpha/daily) of meshtasticd to install for raspberry pi OS.
It is especially helpful if you've already installed the beta and are struggling to figure out how to update to alpha. This script will handle most of that for you.
This is experimental at this point. You may need to check your config files in case they've been overwritten. Right now, it only installs meshtasticd, you will still need to enable SPI, add the proper dtoverlays, etc.

  - Copy the script to your pi
  ```bash
  wget https://raw.githubusercontent.com/chrismyers2000/MeshAdv-Mini/refs/heads/main/Data/Misc/Installer%20Scripts/meshtasticd-install.sh
  ```

  - Change permissions to executable
  ```bash
  sudo chmod +x meshtasticd-install.sh
  ```

  - Run the script
  ```bash
  ./meshtasticd-install.sh
  ```
