#!/usr/bin/env python3
"""
Auto WiFi Manager for Coffee Pi
Automatically switches between home WiFi and iPhone hotspot
"""

import subprocess
import time
import os
import sys
import json
import logging
from pathlib import Path

class AutoWiFiManager:
    def __init__(self):
        self.config_file = Path("/etc/coffee-pi/wifi_config.json")
        self.hotspot_script = Path("/home/coffeelover/CoffeeManager/switch_to_hotspot.sh")
        self.home_wifi_script = Path("/home/coffeelover/CoffeeManager/switch_to_home_wifi.sh")
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/coffee-pi-auto-wifi.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def load_config(self):
        """Load WiFi configuration from JSON file"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.logger.error(f"Error loading config: {e}")
        return {"known_networks": [], "ap_config": {}}
    
    def is_connected_to_wifi(self):
        """Check if Pi is connected to any WiFi network"""
        try:
            result = subprocess.run(['iwconfig', 'wlan0'], capture_output=True, text=True)
            if 'ESSID:' in result.stdout and 'Not-Associated' not in result.stdout:
                return True
        except Exception as e:
            self.logger.error(f"Error checking WiFi connection: {e}")
        return False
    
    def get_current_ip(self):
        """Get current IP address of wlan0"""
        try:
            result = subprocess.run(['ip', 'a', 'show', 'wlan0'], capture_output=True, text=True)
            for line in result.stdout.split('\n'):
                if 'inet ' in line and '127.0.0.1' not in line:
                    ip = line.split()[1].split('/')[0]
                    return ip
        except Exception as e:
            self.logger.error(f"Error getting IP: {e}")
        return None
    
    def scan_for_known_networks(self):
        """Scan for known WiFi networks"""
        try:
            result = subprocess.run(['iwlist', 'wlan0', 'scan'], 
                                  capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            self.logger.error(f"Error scanning networks: {e}")
        return ""
    
    def is_known_network_available(self, known_networks):
        """Check if any known network is available"""
        scan_output = self.scan_for_known_networks()
        for network in known_networks:
            if network.get('ssid') in scan_output:
                self.logger.info(f"Found known network: {network['ssid']}")
                return True
        return False
    
    def switch_to_home_wifi(self):
        """Switch to home WiFi configuration"""
        try:
            self.logger.info("Switching to home WiFi mode...")
            result = subprocess.run(['sudo', str(self.home_wifi_script)], 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self.logger.info("Successfully switched to home WiFi")
                return True
            else:
                self.logger.error(f"Failed to switch to home WiFi: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error switching to home WiFi: {e}")
            return False
    
    def switch_to_hotspot(self):
        """Switch to iPhone hotspot configuration"""
        try:
            self.logger.info("Switching to iPhone hotspot mode...")
            result = subprocess.run(['sudo', str(self.hotspot_script)], 
                                  capture_output=True, text=True, timeout=60)
            if result.returncode == 0:
                self.logger.info("Successfully switched to hotspot")
                return True
            else:
                self.logger.error(f"Failed to switch to hotspot: {result.stderr}")
                return False
        except Exception as e:
            self.logger.error(f"Error switching to hotspot: {e}")
            return False
    
    def run(self):
        """Main auto WiFi management logic"""
        self.logger.info("Starting Auto WiFi Manager")
        
        # Load configuration
        config = self.load_config()
        known_networks = config.get('known_networks', [])
        
        # Wait for system to stabilize
        self.logger.info("Waiting for system to stabilize...")
        time.sleep(30)
        
        # Check if already connected
        if self.is_connected_to_wifi():
            current_ip = self.get_current_ip()
            self.logger.info(f"Already connected to WiFi with IP: {current_ip}")
            
            # If connected to hotspot (192.168.1.100), try to switch to home WiFi
            if current_ip == "192.168.1.100":
                self.logger.info("Currently on hotspot, attempting to switch to home WiFi...")
                if self.is_known_network_available(known_networks):
                    self.switch_to_home_wifi()
                else:
                    self.logger.info("No known networks available, staying on hotspot")
            else:
                self.logger.info("Connected to home WiFi, starting WiFi manager")
                # Start the regular WiFi manager for ongoing management
                subprocess.run(['sudo', 'systemctl', 'start', 'coffee-wifi-manager.service'], 
                             check=False)
            return
        
        # Not connected - try to connect to known networks first
        self.logger.info("Not connected to WiFi, scanning for known networks...")
        
        if known_networks and self.is_known_network_available(known_networks):
            self.logger.info("Known networks available, switching to home WiFi...")
            if self.switch_to_home_wifi():
                # Wait and check if connection successful
                time.sleep(30)
                if self.is_connected_to_wifi():
                    self.logger.info("Successfully connected to home WiFi")
                    # Start WiFi manager for ongoing management
                    subprocess.run(['sudo', 'systemctl', 'start', 'coffee-wifi-manager.service'], 
                                 check=False)
                    return
        
        # No known networks or failed to connect - switch to hotspot
        self.logger.info("No known networks found or connection failed, switching to hotspot...")
        self.switch_to_hotspot()
        
        # Wait and verify hotspot connection
        time.sleep(30)
        current_ip = self.get_current_ip()
        if current_ip == "192.168.1.100":
            self.logger.info("Successfully connected to iPhone hotspot")
        else:
            self.logger.warning(f"Hotspot connection may have failed. Current IP: {current_ip}")

def main():
    if os.geteuid() != 0:
        print("This script must be run as root (use sudo)")
        sys.exit(1)
    
    auto_wifi_manager = AutoWiFiManager()
    auto_wifi_manager.run()

if __name__ == "__main__":
    main()
