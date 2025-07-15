# Installer Scripts 

This is a helper script designed to help you choose which channel (beta/alpha/daily) of meshtasticd to install for raspberry pi OS.
It is especially helpful if you've already installed the beta and are struggling to figure out how to update to alpha. This script will handle most of that for you.
This is experimental at this point. You may need to check your config files in case they've been overwritten. Right now, it only installs meshtasticd, you will still need to enable SPI, add the proper dtoverlays, etc.

  ---

  ## How to use

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
