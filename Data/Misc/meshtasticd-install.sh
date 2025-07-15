#!/bin/bash

#set -e

# Banner
clear

# Set green text
GREEN='\033[1;32m'
RESET='\033[0m'

# Hide cursor for cleaner look
tput civis

# Function to draw frame at top-left corner
draw_frame() {
    tput cup 0 0
    echo -e "${GREEN}$1${RESET}"
}

# Define frames
frame1=$(cat << 'EOF'

 __       __                   __        __                         __     __          
|  \     /  \                 |  \      |  \                       |  \   |  \         
| $$\   /  $$ ______   _______| $$____ _| $$_    ______   _______ _| $$_   \$$ _______ 
| $$$\ /  $$$/      \ /       | $$    |   $$ \  |      \ /       |   $$ \ |  \/       \
| $$$$\  $$$|  $$$$$$|  $$$$$$| $$$$$$$\$$$$$$   \$$$$$$|  $$$$$$$\$$$$$$ | $|  $$$$$$$
| $$\$$ $$ $| $$    $$\$$    \| $$  | $$| $$ __ /      $$\$$    \  | $$ __| $| $$      
| $$ \$$$| $| $$$$$$$$_\$$$$$$| $$  | $$| $$|  |  $$$$$$$_\$$$$$$\ | $$|  | $| $$_____ 
| $$  \$ | $$\$$     |       $| $$  | $$ \$$  $$\$$    $|       $$  \$$  $| $$\$$     \
 \$$      \$$ \$$$$$$$\$$$$$$$ \$$   \$$  \$$$$  \$$$$$$$\$$$$$$$    \$$$$ \$$ \$$$$$$$
                                                                                       
                                                                                       
                                                                                       
 ______                     __              __ __                                      
|      \                   |  \            |  |  \                                     
 \$$$$$$_______   _______ _| $$_    ______ | $| $$ ______   ______                     
  | $$ |       \ /       |   $$ \  |      \| $| $$/      \ /      \                    
  | $$ | $$$$$$$|  $$$$$$$\$$$$$$   \$$$$$$| $| $|  $$$$$$|  $$$$$$\                   
  | $$ | $$  | $$\$$    \  | $$ __ /      $| $| $| $$    $| $$   \$$                   
 _| $$_| $$  | $$_\$$$$$$\ | $$|  |  $$$$$$| $| $| $$$$$$$| $$                         
|   $$ | $$  | $|       $$  \$$  $$\$$    $| $| $$\$$     | $$                         
 \$$$$$$\$$   \$$\$$$$$$$    \$$$$  \$$$$$$$\$$\$$ \$$$$$$$\$$                         
                                                                                       
                                                                                       
                                                                                       
EOF
)

frame2=$(cat << 'EOF'

 __       __                   __         __                         __     __          
/  \     /  |                 /  |       /  |                       /  |   /  |         
$$  \   /$$ | ______   _______$$ |____  _$$ |_    ______   _______ _$$ |_  $$/  _______ 
$$$  \ /$$$ |/      \ /       $$      \/ $$   |  /      \ /       / $$   | /  |/       |
$$$$  /$$$$ /$$$$$$  /$$$$$$$/$$$$$$$  $$$$$$/   $$$$$$  /$$$$$$$/$$$$$$/  $$ /$$$$$$$/ 
$$ $$ $$/$$ $$    $$ $$      \$$ |  $$ | $$ | __ /    $$ $$      \  $$ | __$$ $$ |      
$$ |$$$/ $$ $$$$$$$$/ $$$$$$  $$ |  $$ | $$ |/  /$$$$$$$ |$$$$$$  | $$ |/  $$ $$ \_____ 
$$ | $/  $$ $$       /     $$/$$ |  $$ | $$  $$/$$    $$ /     $$/  $$  $$/$$ $$       |
$$/      $$/ $$$$$$$/$$$$$$$/ $$/   $$/   $$$$/  $$$$$$$/$$$$$$$/    $$$$/ $$/ $$$$$$$/ 
                                                                                        
                                                                                        
                                                                                        
 ______                     __              __ __                                       
/      |                   /  |            /  /  |                                      
$$$$$$/ _______   _______ _$$ |_    ______ $$ $$ | ______   ______                      
  $$ | /       \ /       / $$   |  /      \$$ $$ |/      \ /      \                     
  $$ | $$$$$$$  /$$$$$$$/$$$$$$/   $$$$$$  $$ $$ /$$$$$$  /$$$$$$  |                    
  $$ | $$ |  $$ $$      \  $$ | __ /    $$ $$ $$ $$    $$ $$ |  $$/                     
 _$$ |_$$ |  $$ |$$$$$$  | $$ |/  /$$$$$$$ $$ $$ $$$$$$$$/$$ |                          
/ $$   $$ |  $$ /     $$/  $$  $$/$$    $$ $$ $$ $$       $$ |                          
$$$$$$/$$/   $$/$$$$$$$/    $$$$/  $$$$$$$/$$/$$/ $$$$$$$/$$/                           
                                                                                        
                                                                                        
                                                                                        
EOF
)

# Store frames in array
frames=("$frame1" "$frame2")

# Loop animation
for i in {1..8}; do
    draw_frame "${frames[$((i % 2))]}"
    sleep 0.4
done

# Reset terminal
tput cnorm
tput cup $(tput lines) 0

clear


echo "------------------------------------------------------------------"
echo ""
echo ""
echo -e "----------------\e[32mMeshtastic Installer Helper Script\e[0m----------------"
echo ""
echo ""
echo "------------------------------------------------------------------"

REPO_DIR="/etc/apt/sources.list.d"
GPG_DIR="/etc/apt/trusted.gpg.d"
OS_VERSION="Raspbian_12"
REPO_PREFIX="network:Meshtastic"
PKG_NAME="meshtasticd"

echo "Checking for existing Meshtastic repository..."

if ls $REPO_DIR/${REPO_PREFIX}:*.list &>/dev/null; then
    CURRENT_REPO=$(basename $(ls $REPO_DIR/${REPO_PREFIX}:*.list) .list | cut -d: -f3)
    echo "Found existing Meshtastic repository: $CURRENT_REPO"
    echo "Do you want to remove it and uninstall $PKG_NAME? (y/N)"
    read -r REMOVE_CONFIRM
    if [[ "$REMOVE_CONFIRM" =~ ^[Yy]$ ]]; then
        echo "Uninstalling $PKG_NAME..."
        sudo apt remove -y "$PKG_NAME"

        echo "Removing APT source and GPG key..."
        sudo rm -f "$REPO_DIR/${REPO_PREFIX}:${CURRENT_REPO}.list"
        sudo rm -f "$GPG_DIR/network_Meshtastic_${CURRENT_REPO}.gpg"
    else
        echo "Keeping existing repo and installation. Exiting."
        exit 0
    fi
else
    echo "No existing Meshtastic repo found."
fi




# Check for existing /etc/meshtasticd folder, ask to delete

DIR_PATH="/etc/meshtasticd" 

if [ -d "$DIR_PATH" ]; then
    echo ""
    echo "--------------------------------------------------------------------------------------------"
    echo "Directory '$DIR_PATH' still exists, this contains all the config files for meshtastic."
    echo "Do you want to delete it? (y/N)"
    read -r CONFIRM
    if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
        sudo rm -r "$DIR_PATH"
        echo "Directory deleted."
    else
        echo "Directory was not deleted."
    fi
else
    # Silent if the directory doesn't exist
    :
fi



# Prompt user for which meshtastic channel to add
while true; do
    echo "---------------------------------------------------------------------"
    echo "Which channel do you want to install? Please type: (beta/alpha/daily)"
    echo ""
    echo "Beta  = Safe"
    echo "Alpha = Might be safe, might not"
    echo "Daily = Are you mAd MAn?"
    read -r CHANNEL
    CHANNEL=$(echo "$CHANNEL" | tr '[:upper:]' '[:lower:]')  # normalize to lowercase
    if [[ "$CHANNEL" == "alpha" || "$CHANNEL" == "beta" || "$CHANNEL" == "daily" ]]; then
        break
    else
        echo "Invalid choice. Please type 'alpha', 'beta', or 'daily'."
    fi
done



# Add the new repo and gpg

REPO_URL="http://download.opensuse.org/repositories/network:/Meshtastic:/${CHANNEL}/${OS_VERSION}/"
LIST_FILE="$REPO_DIR/${REPO_PREFIX}:${CHANNEL}.list"
GPG_FILE="$GPG_DIR/network_Meshtastic_${CHANNEL}.gpg"

echo "Adding $CHANNEL repository..."
echo "deb $REPO_URL /" | sudo tee "$LIST_FILE"

echo "Fetching and installing GPG key..."
curl -fsSL "${REPO_URL}Release.key" | gpg --dearmor | sudo tee "$GPG_FILE" > /dev/null

echo "Updating APT and installing $PKG_NAME..."
sudo apt update
sudo apt install -y $PKG_NAME

echo "DONE! $PKG_NAME installed from $CHANNEL channel."



# Ask to enable the systemd service at boot

echo ""
echo "-------------------------------------------------------------------------"
echo "Would you like to enable the meshtasticd systemd service at boot? (y/N)"
read -r CONFIRM

if [[ "$CONFIRM" =~ ^[Yy]$ ]]; then
    echo "Enabling meshtasticd to start on boot..."
    sudo systemctl enable meshtasticd

    echo "Starting meshtasticd now..."
    sudo systemctl start meshtasticd
else
    echo "Skipped enabling systemd service."
fi

