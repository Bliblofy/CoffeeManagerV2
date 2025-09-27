#!/usr/bin/env python3
"""
WiFi Manager for Coffee Pi
Handles automatic WiFi connection with fallback to AP mode
"""

import subprocess
import time
import os
import sys
import json
import logging
from pathlib import Path

class WiFiManager:
    def __init__(self):
        self.config_file = Path("/etc/coffee-pi/wifi_config.json")
        self.wpa_supplicant_conf = Path("/etc/wpa_supplicant/wpa_supplicant.conf")
        self.hostapd_conf = Path("/etc/hostapd/hostapd.conf")
        self.dnsmasq_conf = Path("/etc/dnsmasq.conf")
        self.dhcpcd_conf = Path("/etc/dhcpcd.conf")
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('/var/log/coffee-pi-wifi.log'),
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
    
    def save_config(self, config):
        """Save WiFi configuration to JSON file"""
        try:
            os.makedirs(self.config_file.parent, exist_ok=True)
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving config: {e}")
    
    def scan_networks(self):
        """Scan for available WiFi networks"""
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
        scan_output = self.scan_networks()
        for network in known_networks:
            if network.get('ssid') in scan_output:
                self.logger.info(f"Found known network: {network['ssid']}")
                return network
        return None
    
    def connect_to_wifi(self, network):
        """Connect to a specific WiFi network"""
        try:
            # Create wpa_supplicant configuration
            wpa_config = f"""country=CH
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{network['ssid']}"
    psk="{network['password']}"
    key_mgmt=WPA-PSK
}}
"""
            
            # Write wpa_supplicant config
            with open(self.wpa_supplicant_conf, 'w') as f:
                f.write(wpa_config)
            
            # Restart networking
            subprocess.run(['systemctl', 'restart', 'dhcpcd'], check=True)
            subprocess.run(['systemctl', 'restart', 'wpa_supplicant'], check=True)
            
            # Wait for connection
            time.sleep(10)
            
            # Check if connected
            result = subprocess.run(['iwconfig', 'wlan0'], capture_output=True, text=True)
            if 'ESSID:' in result.stdout and 'Not-Associated' not in result.stdout:
                self.logger.info(f"Successfully connected to {network['ssid']}")
                return True
                
        except Exception as e:
            self.logger.error(f"Error connecting to WiFi: {e}")
        
        return False
    
    def setup_access_point(self, ap_config):
        """Setup WiFi access point mode"""
        try:
            # Stop wpa_supplicant
            subprocess.run(['systemctl', 'stop', 'wpa_supplicant'], check=False)
            
            # Configure static IP
            dhcpcd_config = f"""
interface wlan0
  static ip_address={ap_config.get('ip', '10.10.10.1')}/24
  nohook wpa_supplicant
"""
            
            with open(self.dhcpcd_conf, 'a') as f:
                f.write(dhcpcd_config)
            
            # Configure dnsmasq
            dnsmasq_config = f"""interface=wlan0
dhcp-range={ap_config.get('dhcp_start', '10.10.10.50')},{ap_config.get('dhcp_end', '10.10.10.150')},255.255.255.0,24h
domain-needed
bogus-priv
"""
            
            with open(self.dnsmasq_conf, 'w') as f:
                f.write(dnsmasq_config)
            
            # Configure hostapd
            hostapd_config = f"""country_code={ap_config.get('country', 'CH')}
interface=wlan0
driver=nl80211
ssid={ap_config.get('ssid', 'CoffeePIWIFI')}
ignore_broadcast_ssid=1
hw_mode=g
channel={ap_config.get('channel', '6')}
ieee80211n=1
wmm_enabled=1
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
rsn_pairwise=CCMP
wpa_passphrase={ap_config.get('password', 'CoffeePI2024!')}
"""
            
            with open(self.hostapd_conf, 'w') as f:
                f.write(hostapd_config)
            
            # Update hostapd default config
            subprocess.run(['sed', '-i', 's|^#DAEMON_CONF=.*|DAEMON_CONF="/etc/hostapd/hostapd.conf"|', 
                          '/etc/default/hostapd'], check=True)
            
            # Enable and start services
            subprocess.run(['systemctl', 'unmask', 'hostapd'], check=True)
            subprocess.run(['systemctl', 'enable', 'dnsmasq', 'hostapd'], check=True)
            subprocess.run(['systemctl', 'restart', 'dhcpcd'], check=True)
            subprocess.run(['systemctl', 'start', 'dnsmasq', 'hostapd'], check=True)
            
            self.logger.info("Access Point mode activated")
            return True
            
        except Exception as e:
            self.logger.error(f"Error setting up access point: {e}")
            return False
    
    def wait_for_connection(self, timeout=120):
        """Wait for WiFi connection with timeout"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                result = subprocess.run(['iwconfig', 'wlan0'], capture_output=True, text=True)
                if 'ESSID:' in result.stdout and 'Not-Associated' not in result.stdout:
                    return True
            except:
                pass
            time.sleep(5)
        return False
    
    def run(self):
        """Main WiFi management logic"""
        self.logger.info("Starting WiFi Manager")
        
        # Load configuration
        config = self.load_config()
        known_networks = config.get('known_networks', [])
        ap_config = config.get('ap_config', {})
        
        # Wait 2 minutes for known networks
        self.logger.info("Scanning for known networks...")
        start_time = time.time()
        
        while time.time() - start_time < 120:  # 2 minutes
            available_network = self.is_known_network_available(known_networks)
            if available_network:
                self.logger.info(f"Attempting to connect to {available_network['ssid']}")
                if self.connect_to_wifi(available_network):
                    if self.wait_for_connection(30):
                        self.logger.info("Successfully connected to WiFi network")
                        return
                else:
                    self.logger.warning(f"Failed to connect to {available_network['ssid']}")
            
            time.sleep(10)  # Check every 10 seconds
        
        # Fallback to AP mode
        self.logger.info("No known networks found, switching to Access Point mode")
        self.setup_access_point(ap_config)

def main():
    if os.geteuid() != 0:
        print("This script must be run as root (use sudo)")
        sys.exit(1)
    
    wifi_manager = WiFiManager()
    wifi_manager.run()

if __name__ == "__main__":
    main()
