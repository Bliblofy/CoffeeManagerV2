# Update: NFC Reader Reset Fix
**Date**: 2026-02-01

## Summary
Fixes NFC reader lockup issue where scanner stops functioning and requires system restart. Adds proactive periodic reset every 30 minutes via hardware RST pin toggle.

## Changes
- `controller/coffee_controller.py` - NFC reset logic with hardware RST pin control
- `TECHNICAL_REFERENCE.md` - Updated documentation
- `README.md` - Added NFC maintenance section

---

## Terminal-Only Update Instructions

### 1. SSH into Raspberry Pi
```bash
ssh coffeelover@192.168.1.142
```

### 2. Create Backup
```bash
cd ~
tar -czvf CoffeeManager_backup_$(date +%Y%m%d_%H%M%S).tar.gz CoffeeManager/
ls -lh CoffeeManager_backup_*.tar.gz
```

### 3. Exit SSH
```bash
exit
```

### 4. Transfer Files from Mac
Run this from your **Mac terminal** (not SSH):

```bash
rsync -avz \
  --exclude='database/*.db' \
  --exclude='.git' \
  --exclude='__pycache__' \
  /Users/tobiashauptmann/Documents/development/Coding_Projects/CoffeeManager/ \
  coffeelover@192.168.1.142:~/CoffeeManager/
```

### 5. Restart Controller Service
```bash
ssh coffeelover@192.168.1.142 "sudo systemctl restart coffee-controller.service"
```

### 6. Verify Update
```bash
ssh coffeelover@192.168.1.142

# Check service is running
sudo systemctl status coffee-controller.service

# Verify NFC reset config in logs (should show new timing)
sudo journalctl -u coffee-controller.service -n 20 | grep -i "NFC reset"

exit
```

---

## Expected Log Output After Update

On startup, you should see:
```
Coffee Controller Started
NFC reset: periodic every 30 min, watchdog after 15 min idle
Present NFC/RFID card to reader...
```

After 30 minutes of uptime:
```
Periodic NFC reset triggered (last reset 30.0 min ago)
NFC Reset (periodic): Reinitializing NFC reader with hardware reset...
NFC reader reinitialized successfully (periodic)
```

---

## Rollback (if needed)
```bash
ssh coffeelover@192.168.1.142

# Stop service
sudo systemctl stop coffee-controller.service

# Restore backup
rm -rf ~/CoffeeManager/
tar -xzvf ~/CoffeeManager_backup_YYYYMMDD_HHMMSS.tar.gz -C ~

# Restart service
sudo systemctl start coffee-controller.service

exit
```

---

## No Action Required
- Database: No schema changes, data is preserved
- Web UI: No changes, no restart needed
- Hardware: RST pin (GPIO 25) already wired per existing documentation
