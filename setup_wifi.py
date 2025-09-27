#!/usr/bin/env python3
"""
WiFi Configuration Setup Script
Run this script to configure known WiFi networks and AP settings
"""

import json
import os
import sys
from pathlib import Path

def create_wifi_config():
    """Interactive WiFi configuration setup"""
    print("=== Coffee Pi WiFi Configuration ===")
    print("This script will help you configure WiFi networks and Access Point settings.")
    print()
    
    # Create config directory
    config_dir = Path("/etc/coffee-pi")
    config_dir.mkdir(exist_ok=True)
    
    config = {
        "known_networks": [],
        "ap_config": {}
    }
    
    # Configure known networks
    print("1. Configure known WiFi networks (networks to connect to automatically)")
    while True:
        add_network = input("Add a known WiFi network? (y/n): ").lower().strip()
        if add_network != 'y':
            break
            
        ssid = input("Enter WiFi SSID: ").strip()
        password = input("Enter WiFi password: ").strip()
        
        if ssid and password:
            config["known_networks"].append({
                "ssid": ssid,
                "password": password
            })
            print(f"Added network: {ssid}")
        else:
            print("SSID and password are required")
    
    # Configure Access Point
    print("\n2. Configure Access Point (fallback when no known networks found)")
    ap_ssid = input("Enter AP SSID (default: CoffeePIWIFI): ").strip() or "CoffeePIWIFI"
    ap_password = input("Enter AP password (default: CoffeePI2024!): ").strip() or "CoffeePI2024!"
    ap_ip = input("Enter AP IP address (default: 10.10.10.1): ").strip() or "10.10.10.1"
    country = input("Enter country code (default: CH): ").strip() or "CH"
    
    config["ap_config"] = {
        "ssid": ap_ssid,
        "password": ap_password,
        "ip": ap_ip,
        "country": country,
        "channel": "6",
        "dhcp_start": "10.10.10.50",
        "dhcp_end": "10.10.10.150"
    }
    
    # Save configuration
    config_file = config_dir / "wifi_config.json"
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"\nConfiguration saved to {config_file}")
    print("\nKnown networks:")
    for network in config["known_networks"]:
        print(f"  - {network['ssid']}")
    
    print(f"\nAccess Point settings:")
    print(f"  - SSID: {config['ap_config']['ssid']}")
    print(f"  - Password: {config['ap_config']['password']}")
    print(f"  - IP: {config['ap_config']['ip']}")
    
    return config

def main():
    if os.geteuid() != 0:
        print("This script must be run as root (use sudo)")
        sys.exit(1)
    
    try:
        create_wifi_config()
        print("\nWiFi configuration completed successfully!")
        print("The WiFi manager will start automatically on next boot.")
    except KeyboardInterrupt:
        print("\nConfiguration cancelled.")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
