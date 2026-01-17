# CoffeeManager Update Instructions

## Quick Update (Recommended)

```bash
cd /Users/tobiashauptmann/Documents/development/Coding_Projects/CoffeeManager
python3 updater.py
```

This runs the auto-updater which:
- Fetches latest version from GitHub
- Applies update via `git pull`
- Runs validation tests
- Auto-rollback if tests fail

---

## Manual Update

```bash
cd /Users/tobiashauptmann/Documents/development/Coding_Projects/CoffeeManager
git pull origin main
```

---

## Optional: Backup Database First

```bash
cp database/coffee_manager.db database/coffee_manager_backup_$(date +%Y%m%d).db
```

---

## Notes

- **Database is safe**: `coffee_manager.db` is not tracked in git—updates won't delete your data
- **Rollback**: If issues occur after manual update: `git reset --hard HEAD~1`
- **Source**: Updates pulled from `https://github.com/Bliblofy/CoffeeManagerV2`

---

# Terminal-Only Update (Without GitHub)

Use this method to update the Raspberry Pi deployment without git.

## Raspberry Pi Connection

```
Host: coffeelover@192.168.1.142
Project Path: ~/CoffeeManager/
```

---

## 1. Backup on Pi (via SSH)

```bash
# SSH into Pi
ssh coffeelover@192.168.1.142

# Create full backup with timestamp
cd ~
tar -czvf CoffeeManager_backup_$(date +%Y%m%d_%H%M%S).tar.gz CoffeeManager/

# Verify backup was created
ls -lh CoffeeManager_backup_*.tar.gz

# Exit SSH
exit
```

---

## 2. Transfer Updated Files from Mac → Pi

Run these commands **from your Mac terminal** (not SSH'd into Pi):

```bash
# Sync updated code, preserving database files
rsync -avz \
  --exclude='database/*.db' \
  --exclude='.git' \
  --exclude='__pycache__' \
  /Users/tobiashauptmann/Documents/development/Coding_Projects/CoffeeManager/ \
  coffeelover@192.168.1.142:~/CoffeeManager/
```

**Note**: The `--exclude='database/*.db'` ensures all database files (including any future batch databases) are preserved on the Pi.

---

## 3. Verify Deployment on Pi

```bash
ssh coffeelover@192.168.1.142

# Check files were updated
ls -la ~/CoffeeManager/

# Verify database is intact
ls -la ~/CoffeeManager/database/

# Restart service if applicable
sudo systemctl restart coffeemanager  # adjust service name as needed

exit
```

---

## 4. Rollback if Needed

```bash
ssh coffeelover@192.168.1.142

# Remove broken deployment
rm -rf ~/CoffeeManager/

# Restore from backup
tar -xzvf ~/CoffeeManager_backup_YYYYMMDD_HHMMSS.tar.gz -C ~

exit
```

---

## 5. Download Pi Version to Mac (Optional)

```bash
# From Mac terminal - pull current Pi version locally
scp -r coffeelover@192.168.1.142:~/CoffeeManager/ /path/to/local/backup/
```

---

# Time Pre-Sync Setup (For Timed Power Plug)

The system loses time when power is cut at 18:00. This setup pre-adjusts the clock at 17:55 to 6:55 of the next power-on day.

**Schedule:**
- Mon-Thu 17:55 → Set to next day 6:55
- Fri 17:55 → Set to Monday 6:55
- Sat/Sun → System off

## 1. Allow Passwordless Date Command

```bash
ssh coffeelover@192.168.1.142

# Add sudoers rule for date command
echo 'coffeelover ALL=(ALL) NOPASSWD: /bin/date' | sudo tee /etc/sudoers.d/time-presync
sudo chmod 440 /etc/sudoers.d/time-presync
```

## 2. Make Script Executable

```bash
chmod +x ~/CoffeeManager/scripts/time_presync.sh
```

## 3. Install Systemd Timer

```bash
# Copy service and timer files
sudo cp ~/CoffeeManager/systemd/time-presync.service /etc/systemd/system/
sudo cp ~/CoffeeManager/systemd/time-presync.timer /etc/systemd/system/

# Enable and start timer
sudo systemctl daemon-reload
sudo systemctl enable time-presync.timer
sudo systemctl start time-presync.timer

# Verify timer is active
sudo systemctl list-timers | grep time-presync
```

## 4. Manual Test

```bash
# Test script manually
sudo ~/CoffeeManager/scripts/time_presync.sh

# Check current time
date
```

## 5. Alternative: Cron Setup (if systemd unavailable)

```bash
# Edit crontab
crontab -e

# Add line (runs at 17:55 Mon-Fri):
55 17 * * 1-5 /home/coffeelover/CoffeeManager/scripts/time_presync.sh >> /var/log/time_presync.log 2>&1
```
