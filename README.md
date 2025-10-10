# DeLonghi Magnifica S RFID Payment System - Developer README

## Project Overview
This Project allows a standard DeLonghi Magnicifica S to be transformed into an office-worthy Coffee station. To do so the machine is locked which means the buttons can not be pushed before a valid NFC Token is presented to its reader. The Tokens are registerd and linked to a user. This will trigger the Raspberry PI which in turn sets the relay to closed. The NFC Token is registered with a time-stamp into a database on the PI itself. 
The PI doesn't have to be connected to the internet since it is common in offices that the connection of unmanaged devices is prohibited. To access the data and to create reportings about the consumtion of coffee for each and every user, the PI productes a hidden Wifi Network to connect to. On the network and endpoint is exposed to access a small Web-UI, which can be used to manage the relation of NFC Token to User, lock NFC tokens for future use, create an invoice and send it via eMail and manage the payment state of invoices. Additionally it is possible. Additionally the Web-UI allows for the NFC reader to be set in to the registration state, which allows for new tokens to be registerd into the database. 

The system has to differnent database tables, one for the user to token realtion and one for the useage per token. The UI is capable of merging this infroamtion into a report to view the useage of a certain user. 

The system handles:

- User authentication with NFC/RFID cards  
- Coffee machine control via relays (simulate button presses)  
- Data persistence and logging  
- Web-based administration via WiFi  

### Timing Behavior

The system implements intelligent activation timing based on usage patterns to optimize machine wake-up performance:

**Normal Operation (30 seconds)**
- When a valid token is scanned and the last usage was within 25 minutes, the machine activates for 30 seconds
- This provides sufficient time for coffee preparation during regular usage periods

**Extended Wake-up (2 minutes)**  
- When no valid token has been used for more than 25 minutes, the next scan triggers a 2-minute activation
- This extended duration accounts for the machine's energy-saving mode, which requires additional time to fully wake up and reach optimal brewing temperature

**Time Accuracy for Offline Operation**
- The system uses the Raspberry Pi's system clock for timing calculations
- While offline, clock drift may occur without NTP synchronization
- For extended offline periods, consider using an RTC (Real-Time Clock) module
- The 25-minute threshold provides sufficient tolerance for typical clock drift scenarios

**Security Features**
- Brute-force protection: After 10 invalid token attempts within 60 seconds, the system locks for 5 minutes
- Master token can always bypass security lockouts and toggle master mode
- All timing calculations work across multiple days and system restarts

---

## Database schema
User Information
TokenID, UserName, Name, Email-adress, Phone-Number, Barred

Useage information
TokenID, TimeStamp

### Core Functionality
1. **User Authentication**: Card/Token tap identifies user  
2. **User Management**: Userregistration to tokens with name and mail-adress   
3. **Machine Control**: Relay simulates disconnects buttons of control panel when no Token is presented  
5. **Data Persistence**: Store transaction logs in SQLite and store user to token relation 
6. **Remote Management**: Flask web interface for admin  

### Operation Flow
1. User taps card on RC522 reader  
2. System validates token validity.  
3. LED switches from red (ready) to green (active) and timer starts (30s normal / 2min if >25min since last use)
4. One coffee registered and logged in database with timestamp. 
5. Coffee type selected through native buttons on the machine. 
6. Coffee machine brews  
7. Relay opens and disconnects the connection to the front panel buttons.
8. LED switches back to red (ready)  

---

## Hardware Requirements

- Raspberry Pi Zero W  
- RC522 NFC/RFID module (SPI)  
- 4-Channel 5V Relay Module (Active LOW)  
- 2x LEDs (Red and Green) with current limiting resistors
- 5V 2A power supply  
- DeLonghi Magnifica S ECAM22.110  

---

## GPIO Mapping

Gerneral Raspberry PI Mapping
Pin #	Function	GPIO
1	3.3V Power	-
2	5V Power	-
3	SDA	GPIO 2
4	5V Power	-
5	SCL	GPIO 3
6	Ground	-
7	GPCLK0	GPIO 4
8	TXD	GPIO 14
9	Ground	-
10	RXD	GPIO 15
11	-	GPIO 17
12	PCM_CLK	GPIO 18
13	-	GPIO 27
14	Ground	-
15	-	GPIO 22
16	-	GPIO 23
17	3.3V Power	-
18	-	GPIO 24
19	MOSI	GPIO 10
20	Ground	-
21	MISO	GPIO 9
22	-	GPIO 25
23	SCLK	GPIO 11
24	CE0	GPIO 8
25	Ground	-
26	CE1	GPIO 7
27	ID_SD	GPIO 0
28	ID_SC	GPIO 1
29	-	GPIO 5
30	Ground	-
31	-	GPIO 6
32	PWM0	GPIO 12
33	PWM1	GPIO 13
34	Ground	-
35	PCM_FS	GPIO 19
36	-	GPIO 16
37	-	GPIO 26
38	PCM_DIN	GPIO 20
39	Ground	-
40	PCM_DOUT	GPIO 21


### RC522 NFC (SPI)
| Pin | GPIO | Function |
|-----|------|---------|
| 19 | 10 | MOSI (SPI Master Out) |
| 21 | 9 | MISO (SPI Master In) |
| 23 | 11 | SCLK (SPI Clock) |
| 24 | 8 | SDA (Chip Select CE0) |
| 22 | 25 | RST (Reset) |

### 4-Channel Relay
| Relay | Pin | GPIO | Function | Notes |
|-------|-----|------|---------|-------|
| IN1 | 11 | 17 | Power Button | Active LOW |
| IN2 | 13 | 27 | Single Coffee | Active LOW |
| IN3 | 15 | 22 | Double Coffee | Active LOW |
| IN4 | 16 | 23 | Steam/Hot Water | Active LOW |

### LED Status Indicators
| LED | Pin | GPIO | Function | Notes |
|-----|-----|------|---------|-------|
| Red | 29 | 5 | System Ready/Standby | Active HIGH |
| Green | 31 | 6 | Valid Card/Active | Active HIGH |

### Coffee Machine Interface
| Pin | Relay | Function |
|-----|-------|----------|
| 5 | IN4 | connection to panel |

---

## Software Setup

### SSH Access Configuration
```bash
# SSH connection to Raspberry Pi
ssh coffeelover@192.168.1.142

# Note: Uses security key authentication
# IP Address: 192.168.1.142
# Username: coffeelover
```

### Enable SPI
```bash
sudo raspi-config
# Interface Options > SPI > Enable
sudo reboot
```

## **Streamlined Setup Guide - Eliminated Redundancies**

### **1. Initial System Setup (One-time)**
```bash
# Connect to Pi
ssh coffeelover@192.168.1.142

# Enable SPI interface
sudo raspi-config
# Interface Options > SPI > Enable
sudo reboot

# Install all dependencies in one command
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-pip python3-venv python3-dev python3-spidev python3-rpi.gpio python3-flask hostapd dnsmasq

# Navigate to project directory
cd /home/coffeelover/CoffeeManager
```

### **2. Database and Master Token Setup**
```bash
# Initialize database
python3 database/init_database.py

# Set master token (choose one method)
export MASTER_TOKEN_ID="your_master_token_uid_here"
# OR via database:
python3 -c "
from database.database_manager import CoffeeDatabaseManager
db = CoffeeDatabaseManager()
db.set_setting('master_token_id', '<MASTER_TOKEN_ID>')
print('Master token set')
"
```

### **3. Auto-Start Services Setup (Fixed)**
```bash
# Create coffee controller service
sudo tee /etc/systemd/system/coffee-controller.service > /dev/null << 'EOF'
[Unit]
Description=Coffee Manager Controller
After=network.target
Wants=network.target

[Service]
Type=simple
User=coffeelover
Group=coffeelover
WorkingDirectory=/home/coffeelover/CoffeeManager
ExecStart=/usr/bin/python3 /home/coffeelover/CoffeeManager/controller/coffee_controller.py
Restart=always
RestartSec=10
Environment=MASTER_TOKEN_ID=<MASTER_TOKEN_ID>
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Create web UI service
sudo tee /etc/systemd/system/coffee-webui.service > /dev/null << 'EOF'
[Unit]
Description=Coffee Manager Web UI
After=network.target
Wants=network.target

[Service]
Type=simple
User=coffeelover
Group=coffeelover
WorkingDirectory=/home/coffeelover/CoffeeManager
ExecStart=/usr/bin/python3 /home/coffeelover/CoffeeManager/ui/app.py
Restart=always
RestartSec=10
Environment=FLASK_HOST=0.0.0.0
Environment=FLASK_PORT=8080
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start services
sudo systemctl daemon-reload
sudo systemctl enable coffee-controller.service coffee-webui.service
sudo systemctl start coffee-controller.service coffee-webui.service
```

sudo systemctl daemon-reload
sudo systemctl enable coffee-webui.service
sudo systemctl start coffee-webui.service


### **4. WiFi Management Setup (Smart WiFi with Fallback)**
```bash
# Install WiFi management dependencies (corrected package)
sudo apt install -y wireless-tools

# Make WiFi manager scripts executable
sudo chmod +x wifi_manager.py setup_wifi.py

# Configure WiFi networks and AP settings
sudo python3 setup_wifi.py

# Create WiFi manager systemd service (fixed command)
sudo tee /etc/systemd/system/coffee-wifi-manager.service > /dev/null << 'EOF'
[Unit]
Description=Coffee Pi WiFi Manager
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/home/coffeelover/CoffeeManager
ExecStart=/usr/bin/python3 /home/coffeelover/CoffeeManager/wifi_manager.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Enable and start WiFi manager
sudo systemctl daemon-reload
sudo systemctl enable coffee-wifi-manager.service
sudo systemctl start coffee-wifi-manager.service
```

### **5. WiFi Management Commands**
```bash
# Check WiFi manager status
sudo systemctl status coffee-wifi-manager.service

# View WiFi manager logs
sudo journalctl -u coffee-wifi-manager.service -f

# Reconfigure WiFi settings
sudo python3 setup_wifi.py

# Manually switch to AP mode
sudo systemctl stop coffee-wifi-manager.service
sudo python3 wifi_manager.py

# Check current WiFi status
iwconfig wlan0
ip a show wlan0
```

### **6. Auto-Update System Setup (Optional)**

The Coffee Manager includes an automatic update system that checks GitHub for updates, applies them, validates the system, and rolls back if tests fail.

#### New Installation
```bash
# Install the auto-updater service and timer
sudo cp /home/coffeelover/CoffeeManager/systemd/coffee-updater.service /etc/systemd/system/
sudo cp /home/coffeelover/CoffeeManager/systemd/coffee-updater.timer /etc/systemd/system/

# Enable and start the updater timer
sudo systemctl daemon-reload
sudo systemctl enable coffee-updater.timer
sudo systemctl start coffee-updater.timer

# Verify timer is active
sudo systemctl status coffee-updater.timer
sudo systemctl list-timers coffee-updater.timer
```

#### Upgrading to Auto-Updater if System was Setup Before 10th Oct. 2025

If your Coffee Manager was installed before the auto-updater feature was added, you need to update the database schema to include version tracking fields.

```bash
# Navigate to project directory
cd /home/coffeelover/CoffeeManager

# Pull latest changes from GitHub
git pull origin main

# Add version tracking fields to existing database
python3 << 'EOF'
import sqlite3
import os

db_path = os.path.join('database', 'coffee_manager.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Add version tracking settings if they don't exist
version_settings = [
    ('current_version', 'unknown'),
    ('previous_version', 'unknown'),
    ('last_update_check', '1970-01-01 00:00:00'),
    ('last_update_time', '1970-01-01 00:00:00'),
    ('last_update_status', 'never'),
    ('last_update_message', 'No updates performed yet')
]

for key, value in version_settings:
    cursor.execute(
        "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
        (key, value)
    )

conn.commit()
conn.close()
print("✓ Database upgraded successfully with version tracking fields")
EOF

# Set current version to current commit
CURRENT_COMMIT=$(git rev-parse HEAD)
python3 -c "
from database.database_manager import CoffeeDatabaseManager
db = CoffeeDatabaseManager()
db.set_setting('current_version', '$CURRENT_COMMIT')
db.set_setting('previous_version', '$CURRENT_COMMIT')
print('✓ Current version set to: $CURRENT_COMMIT')
"

# Install the auto-updater service and timer
sudo cp /home/coffeelover/CoffeeManager/systemd/coffee-updater.service /etc/systemd/system/
sudo cp /home/coffeelover/CoffeeManager/systemd/coffee-updater.timer /etc/systemd/system/

# Enable and start the updater timer
sudo systemctl daemon-reload
sudo systemctl enable coffee-updater.timer
sudo systemctl start coffee-updater.timer

# Verify timer is active
sudo systemctl status coffee-updater.timer

echo "✓ Auto-updater installed and activated"
echo "✓ Version info will appear in Administration page"
```

**Verification:**
1. Open the web interface at `http://192.168.1.142:8080/administration`
2. Scroll to the bottom - you should see version information
3. Check updater logs: `sudo journalctl -u coffee-updater.timer -f`

#### Auto-Update Features
- **Scheduled Updates**: Runs 10 minutes after boot and daily at 2:00 AM
- **Network Resilient**: Gracefully handles no internet connection
- **Validation Tests**: Runs comprehensive tests after updates
- **Automatic Rollback**: Reverts to previous version if tests fail
- **Version Tracking**: View current version and update status in Admin UI

#### Manual Update Commands
```bash
# Check for updates manually
sudo systemctl start coffee-updater.service

# View update logs
sudo journalctl -u coffee-updater.service -n 50

# Check last update status
sudo journalctl -u coffee-updater.service | tail -20

# Disable auto-updates
sudo systemctl stop coffee-updater.timer
sudo systemctl disable coffee-updater.timer

# Re-enable auto-updates
sudo systemctl enable coffee-updater.timer
sudo systemctl start coffee-updater.timer
```

#### Update Status Indicators
The Administration page displays version information at the bottom:
- **✓ (Green)**: Update successful or system up to date
- **⟲ (Yellow)**: Update was rolled back due to test failures
- **✗ (Red)**: Update error occurred
- **○ (Gray)**: No internet connection or no updates performed

### **7. Verification**
```bash
# Check all services are running
sudo systemctl status coffee-controller.service coffee-webui.service coffee-wifi-manager.service

# Test web interface
curl http://localhost:8080

# Check WiFi connection
iwconfig wlan0
ip a show wlan0

# Check auto-updater timer (if enabled)
sudo systemctl status coffee-updater.timer
```

## **Key Redundancies Eliminated:**

1. **Multiple SSH connections** - Consolidated into single connection
2. **Repeated `sudo apt update`** - Combined all package installations
3. **Duplicate service creation** - Used `tee` instead of `nano` for automation
4. **Separate service enable/start** - Combined into single commands
5. **Redundant path specifications** - Used absolute paths consistently
6. **Multiple systemctl commands** - Combined related operations
7. **Repeated hostapd configuration** - Eliminated duplicate config sections
8. **Separate locale configuration** - Removed unnecessary locale setup

## **Summary of Changes:**
- **Reduced from ~50 commands to ~25 commands**
- **Eliminated 3 redundant SSH connections**
- **Combined 6 separate package installations into 1**
- **Streamlined service creation from manual editing to automated**
- **Removed duplicate WiFi configuration sections**
- **Fixed systemd service paths and configurations**

The streamlined guide maintains all functionality while being much more efficient and less error-prone.

### System Operation

#### Coffee Controller Features
- **Token Validation**: Only registered, active, non-barred users can access
- **Master Mode**: Special token toggles always-on state for maintenance
- **Usage Logging**: All coffee usage automatically logged with timestamps
- **LED Status**: Red (ready), Green (active), Off (inactive)

#### Web Interface Features
- **Transactions**: View usage history with filtering by user, date, time
- **Invoicing**: Create invoices for billing periods, mark as paid/unpaid
- **Scan Mode**: Register new tokens and assign to users
- **User Management**: Add, update, bar/unbar users

#### Database Schema
```sql
-- Users table
CREATE TABLE users (
    token_id TEXT PRIMARY KEY,
    user_name TEXT NOT NULL,
    name TEXT NOT NULL,
    email_address TEXT,
    phone_number TEXT,
    barred BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP,
    active BOOLEAN DEFAULT 1
);

-- Usage tracking
CREATE TABLE usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    coffee_type TEXT DEFAULT 'unknown',
    FOREIGN KEY(token_id) REFERENCES users(token_id)
);

-- Invoicing
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id TEXT NOT NULL,
    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    total_items INTEGER NOT NULL DEFAULT 0,
    paid BOOLEAN NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(token_id) REFERENCES users(token_id)
);

CREATE TABLE invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    usage_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY(usage_id) REFERENCES usage_log(id) ON DELETE CASCADE,
    UNIQUE(usage_id)
);
```

### Testing Checklist
- [ ] NFC card detection 3–5cm
- [ ] Relay channels activate reliably  
- [ ] Database persists after reboot
- [ ] Web interface accessible via WiFi
- [ ] Transaction logging correct
- [ ] System recovers from power loss
- [ ] Master mode toggle works
- [ ] Invoice creation and email generation

### Safety Notes
- Test relays without coffee machine first
- Keep electronics dry
- Secure wiring and verify connections
- Use correct wire gauge
- Master token should be kept secure

## **Check Service Status**
```bash
<code_block_to_apply_changes_from>
```

## **Check Service Logs**
```bash
# Check recent logs for any errors
sudo journalctl -u coffee-controller.service -n 20
sudo journalctl -u coffee-webui.service -n 20

# Check for any Python import errors
sudo journalctl -u coffee-controller.service | grep -i "error\|exception\|import"
sudo journalctl -u coffee-webui.service | grep -i "error\|exception\|import"
```

## **Test Web Interface**
```bash
# Test if web interface is accessible
curl -I http://localhost:8080

# Check if port 8080 is listening
sudo netstat -tlnp | grep :8080
```

## **Check Service Files**
```bash
# Verify service files exist and have correct content
sudo cat /etc/systemd/system/coffee-controller.service
sudo cat /etc/systemd/system/coffee-webui.service
```

## **Quick Status Check**
```bash
# One-liner to check everything at once
echo "=== Service Status ===" && \
sudo systemctl status coffee-controller.service coffee-webui.service --no-pager && \
echo -e "\n=== Enabled Status ===" && \
sudo systemctl is-enabled coffee-controller.service coffee-webui.service && \
echo -e "\n=== Web Interface Test ===" && \
curl -s -o /dev/null -w "%{http_code}" http://localhost:8080
```

If any service shows as "inactive" or "failed", you can restart just that service:
```bash
# Restart individual services if needed
sudo systemctl restart coffee-controller.service
sudo systemctl restart coffee-webui.service
```

This way you can verify everything is working without a full system restart.
