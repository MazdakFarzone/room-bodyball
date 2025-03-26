#!/bin/bash

current_dir=$(basename "$(pwd)")
expected_dir="setup"

# Read the version from /etc/os-release
os_version=$(grep VERSION_CODENAME /etc/os-release | cut -d '=' -f 2)

# Check if the current directory name matches the expected directory name
if [ "$current_dir" != "$expected_dir" ]; then
    echo "Please run this script from the $expected_dir directory."
    exit 1
fi

echo "Updating and downloading libraries ..."
sudo apt-get update
sudo apt-get install -y libsdl2-mixer-2.0-0 xterm

# Check if it's bullseye or bookworm
if [ "$os_version" == "bullseye" ]; then
    echo "This system is running Bullseye."
    python3 -m pip install -r requirements.txt
    sudo python3 -m pip install -r requirements.txt
elif [ "$os_version" == "bookworm" ]; then
    echo "This system is running Bookworm."
    sudo apt-get install -y python3-paho-mqtt python3-netifaces python3-apscheduler python3-zeroconf python3-pygame python3-transitions
else
    echo "Unknown version: $os_version"
    exit 1
fi

echo "Setting up global variables for git"
git config --global user.name "Mazdak Farzone"
git config --global user.email "mazdak.farzone@gmail.com"

#echo "Setting up RPI stuff"
#sudo systemctl enable pigpiod
#sudo systemctl start pigpiod

echo "Setting up shutdown/reboot logic ..."
mkdir -p $HOME/system-handler/utils
cp ../constants.py ../ServerCommunicator.py $HOME/system-handler/utils
cp systemhandler.py $HOME/system-handler/
sudo cp system-condition.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable system-condition.service
sudo systemctl start system-condition.service

# Extract the parent folder name dynamically
parent_folder=$(basename "$(dirname "$(dirname "$(pwd)")")")

echo "Setting up game autostart logic ..."
mkdir -p $HOME/.config/autostart
cat <<EOL > $HOME/.config/autostart/game.desktop
[Desktop Entry]
Type=Application
Name=Game
Exec=/bin/bash -c "sleep 5; xterm -hold -e '/usr/bin/python3 /home/uh/$parent_folder/main.py'"
EOL

# Prompt user to block Wi-Fi
read -p "Do you want to block Wi-Fi on this system? (y/n): " wifi_choice
if [[ "$wifi_choice" =~ ^[Yy]$ ]]; then
    echo "Blocking Wi-Fi ..."
    sudo rfkill block wifi
    echo "Wi-Fi has been blocked."
else
    echo "Wi-Fi remains enabled."
fi

# echo "Removing cached keys:"
# rm -r ~/.ssh/*;

echo "Setup complete."
