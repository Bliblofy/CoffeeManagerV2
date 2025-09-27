#!/bin/bash
# Switch Pi back to home WiFi
# This script restores the original WiFi configuration for home network

echo "Switching to home WiFi mode..."

# Restore original dhcpcd configuration
sudo cp /etc/dhcpcd.conf.backup /etc/dhcpcd.conf

# Restart networking
sudo systemctl restart dhcpcd

# Wait for connection
echo "Waiting for home WiFi connection..."
sleep 10

# Start WiFi manager for automatic network management
sudo systemctl start coffee-wifi-manager.service

# Check connection status
if iwconfig wlan0 | grep -q "Not-Associated"; then
    echo "Warning: Not connected to any network"
else
    echo "Connected to network"
fi

# Show current IP
CURRENT_IP=$(ip a show wlan0 | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
echo "Current IP: $CURRENT_IP"

echo "✅ Pi should now connect to home WiFi automatically"
echo "WiFi manager is running for automatic network management"
