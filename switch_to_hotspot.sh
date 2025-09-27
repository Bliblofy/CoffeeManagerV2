#!/bin/bash
# Switch Pi to iPhone hotspot with fixed IP
# This script configures the Pi to connect to iPhone hotspot with a fixed IP

echo "Switching to iPhone hotspot mode..."

# Stop WiFi manager to prevent conflicts
sudo systemctl stop coffee-wifi-manager.service 2>/dev/null || true

# Apply hotspot configuration
sudo cp /etc/dhcpcd.conf.hotspot /etc/dhcpcd.conf

# Restart networking
sudo systemctl restart dhcpcd

# Wait for connection
echo "Waiting for hotspot connection..."
sleep 15

# Check connection status
if iwconfig wlan0 | grep -q "Not-Associated"; then
    echo "Warning: Not connected to any network"
else
    echo "Connected to network"
fi

# Show current IP
CURRENT_IP=$(ip a show wlan0 | grep "inet " | awk '{print $2}' | cut -d'/' -f1)
echo "Current IP: $CURRENT_IP"

if [ "$CURRENT_IP" = "192.168.1.100" ]; then
    echo "✅ Successfully connected to iPhone hotspot at 192.168.1.100"
    echo "Connect your laptop to the same iPhone hotspot"
    echo "Then SSH: ssh coffeelover@192.168.1.100"
    echo "Web interface: http://192.168.1.100:8080"
else
    echo "⚠️  IP not as expected. Current IP: $CURRENT_IP"
fi
