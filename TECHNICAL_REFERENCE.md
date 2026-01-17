# CoffeeManager - Technical Reference for AI Agents

> **Purpose**: This document provides a comprehensive technical overview for AI agents and developers working on this codebase.

---

## Project Summary

CoffeeManager is an RFID-based coffee machine access control system running on a Raspberry Pi Zero W. It locks a DeLonghi Magnifica S coffee machine until a valid NFC token is presented. The system provides a Flask-based web UI for user management, usage tracking, and invoicing.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Hardware Layer                            │
│  RC522 NFC Reader ─→ Raspberry Pi Zero W ─→ 4-Channel Relay     │
│                              ↓                                   │
│                         GPIO Control                             │
│                     (LEDs: Red/Green Status)                     │
└─────────────────────────────────────────────────────────────────┘
                               ↓
┌─────────────────────────────────────────────────────────────────┐
│                      Application Layer                           │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │ CoffeeController │  │  Flask Web UI    │  │   Updater     │  │
│  │ (coffee_         │  │  (app.py)        │  │ (updater.py)  │  │
│  │  controller.py)  │  │  Port: 8080      │  │ Git-based     │  │
│  └────────┬─────────┘  └────────┬─────────┘  └───────────────┘  │
│           │                     │                                │
│           └──────────┬──────────┘                                │
│                      ↓                                           │
│           ┌──────────────────────┐                               │
│           │  CoffeeDatabaseManager│                               │
│           │  (database_manager.py)│                               │
│           └──────────┬───────────┘                               │
│                      ↓                                           │
│           ┌──────────────────────┐                               │
│           │  SQLite Database     │                               │
│           │  (coffee_manager.db) │                               │
│           └──────────────────────┘                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## File Structure

```
CoffeeManager/
├── controller/
│   └── coffee_controller.py    # Main NFC reading loop, GPIO control, relay logic
├── database/
│   ├── __init__.py
│   ├── database_manager.py     # CoffeeDatabaseManager class - all DB operations
│   ├── init_database.py        # Database schema creation script
│   ├── coffee_manager.db       # SQLite database (created at runtime)
│   └── requirements.txt        # Python dependencies for database module
├── ui/
│   ├── app.py                  # Flask application factory and routes
│   ├── static/
│   │   └── styles.css          # CSS styles (CSS custom properties based)
│   └── templates/
│       ├── base.html           # Jinja2 base template with navigation
│       ├── administration.html # User management, scan mode toggle
│       ├── invoice_detail.html # Single invoice view
│       ├── invoice_settings.html
│       ├── invoicing.html      # Invoice list and creation
│       ├── leaderboard.html    # Usage leaderboard
│       ├── message.html        # Generic message display
│       ├── placeholder.html
│       ├── scan_mode.html      # Token registration mode
│       ├── settings.html       # System settings (price, email templates)
│       └── transactions.html   # Usage history with filters
├── tests/
│   └── test_system_validation.py  # Validation tests for auto-updater
├── systemd/
│   ├── coffee-updater.service  # Oneshot service for updates
│   └── coffee-updater.timer    # Timer: 10min after boot, daily 2:00 AM
├── updater.py                  # Auto-update script with rollback
├── README.md                   # User-facing documentation
├── TECHNICAL_REFERENCE.md      # This file
└── secrets.txt                 # Credentials (gitignored)
```

---

## Dependencies

### Python Packages

| Package | Version | Purpose |
|---------|---------|---------|
| `flask` | Built-in (system) | Web UI framework |
| `sqlite3` | Built-in (Python stdlib) | Database operations |
| `python-dateutil` | >=2.8.0 | Date/time parsing (optional) |
| `pydantic` | >=1.8.0 | Data validation (optional) |
| `colorama` | >=0.4.4 | Colored terminal output (optional) |
| `RPi.GPIO` | System package | GPIO control on Raspberry Pi |
| `spidev` | System package | SPI communication for NFC reader |
| `mfrc522` | pip | RC522 NFC reader library |

### System Packages (Raspberry Pi OS)

```bash
python3-pip python3-venv python3-dev python3-spidev python3-rpi.gpio python3-flask hostapd
```

### Hardware Requirements

- **Raspberry Pi Zero W** (or compatible Pi with GPIO)
- **RC522 NFC/RFID Module** (SPI interface)
- **4-Channel 5V Relay Module** (Active LOW)
- **2x LEDs** with current-limiting resistors (Red + Green)
- **DeLonghi Magnifica S ECAM22.110** (or compatible machine)

---

## GPIO Pin Mapping

### RC522 NFC Reader (SPI)

| Pin | GPIO | Function |
|-----|------|----------|
| 19 | 10 | MOSI |
| 21 | 9 | MISO |
| 23 | 11 | SCLK |
| 24 | 8 | SDA (CE0) |
| 22 | 25 | RST |

### Relay Module (Active LOW)

| Relay | Pin | GPIO | Function |
|-------|-----|------|----------|
| IN1 | 11 | 17 | Power Button |
| IN2 | 13 | 27 | Single Coffee |
| IN3 | 15 | 22 | Double Coffee |
| IN4 | 16 | 23 | Steam/Hot Water |

### LED Status Indicators (Active HIGH)

| LED | Pin | GPIO | Status |
|-----|-----|------|--------|
| Red | 29 | 5 | Ready/Standby |
| Green | 31 | 6 | Active/Valid Card |

---

## Database Schema

### Tables

```sql
-- Users table
CREATE TABLE users (
    token_id TEXT PRIMARY KEY,        -- NFC card UID (hex string, lowercase, no separators)
    user_name TEXT NOT NULL,          -- Login/display name
    name TEXT NOT NULL,               -- Full name
    email_address TEXT,               -- For invoicing
    phone_number TEXT,
    barred BOOLEAN DEFAULT 0,         -- 1 = blocked from access
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP,
    active BOOLEAN DEFAULT 1          -- 0 = pending registration
);

-- Usage tracking
CREATE TABLE usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_id TEXT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    coffee_type TEXT DEFAULT 'unknown',
    FOREIGN KEY(token_id) REFERENCES users(token_id)
);

-- Invoices
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

-- Invoice line items
CREATE TABLE invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    usage_id INTEGER NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY(invoice_id) REFERENCES invoices(id),
    FOREIGN KEY(usage_id) REFERENCES usage_log(id),
    UNIQUE(usage_id)  -- Prevents double-invoicing
);

-- System settings (key-value store)
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Important Settings Keys

| Key | Description |
|-----|-------------|
| `scan_mode` | '1' = registration mode, '0' = normal |
| `master_token_id` | UID of master override card |
| `price_per_coffee` | Decimal price for invoicing |
| `invoice_subject` | Email subject template |
| `invoice_body` | Email body template (supports placeholders) |
| `current_version` | Git commit hash |
| `last_update_status` | 'success', 'rollback', 'error', 'up_to_date', 'no_internet' |
| `last_scanned_token` | Last token scanned in scan mode |
| `last_scanned_at` | Timestamp of last scan |

### Data Immutability

Database has triggers preventing DELETE operations on `users`, `usage_log`, `invoices`, `invoice_items` tables. Use UPDATE with `barred=1` or `active=0` to "disable" records.

---

## Flask Web UI Routes

### Pages

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Redirects to transactions |
| `/transactions` | GET | Usage history with filters |
| `/invoicing` | GET | Invoice list and user uninvoiced counts |
| `/invoicing/create/<token_id>` | POST | Create invoice for user |
| `/leaderboard` | GET | Usage ranking (7/30 days or custom) |
| `/administration` | GET | User management, scan mode toggle |
| `/settings` | GET/POST | Configure pricing and email templates |
| `/scan-mode` | GET | Redirects to administration |

### API Endpoints

| Route | Method | Returns |
|-------|--------|---------|
| `/api/scan-mode/status` | GET | `{"scan_mode": bool}` |
| `/api/scan-mode/last` | GET | `{"token": "...", "timestamp": "..."}` (fresh scans only) |
| `/api/scan-mode/pending` | GET | List of pending users |
| `/api/scan-mode/user/<token_id>` | POST | Update user fields |
| `/api/admin/users` | GET | All users list |
| `/api/admin/user` | POST | Create/update user |
| `/api/admin/user/<token_id>` | DELETE | Delete user and data |
| `/api/admin/version` | GET | Version and update status |
| `/scan-mode/toggle` | POST | Toggle scan mode on/off |
| `/invoicing/<id>/toggle` | POST | Toggle invoice paid status |

---

## Key Classes

### `CoffeeDatabaseManager` (database/database_manager.py)

Central database abstraction. Key methods:

```python
# User management
add_user(token_id, user_name, name, email_address=None, phone_number=None) -> bool
add_pending_user(token_id) -> bool  # Creates barred placeholder
get_user(token_id) -> Optional[Dict]
get_all_users() -> List[Dict]
update_user(token_id, **kwargs) -> bool
bar_user(token_id, barred=True) -> bool
delete_user(token_id) -> bool

# Usage tracking
log_coffee_usage(token_id, coffee_type='unknown') -> bool
get_usage_history(token_id=None, limit=100) -> List[Dict]
get_last_usage_timestamp() -> Optional[datetime]
get_user_statistics(token_id) -> Dict

# Invoicing
get_last_invoice_end(token_id) -> Optional[str]
get_uninvoiced_usage(token_id, start_ts, end_ts) -> List[Dict]
create_invoice_for_user(token_id, period_start, period_end) -> Optional[int]
list_invoices(token_id=None) -> List[Dict]
get_invoice(invoice_id) -> Optional[Dict]
set_invoice_paid(invoice_id, paid) -> bool

# Settings
get_setting(key) -> Optional[str]
set_setting(key, value) -> bool

# Maintenance
cleanup_old_records(retention_years=5) -> int
get_database_stats() -> Dict
```

### `CoffeeController` (controller/coffee_controller.py)

Hardware control and main loop. Key behaviors:

- **Token Validation**: Checks `active=1` AND `barred=0`
- **Master Mode**: Master token toggles always-on state
- **Activation Duration**: 90s if unused >180min, else 30s
- **Brute-force Protection**: 10 invalid attempts in 60s → 5min lockout
- **Scan Mode**: Creates pending users instead of granting access
- **LED States**: `ready` (red), `active` (green), `master` (both), `off`

---

## Timing Behavior

| Scenario | Duration |
|----------|----------|
| Normal activation (used within 180min) | 30 seconds |
| Extended wake-up (unused >180min) | 90 seconds |
| Security lockout trigger | 10 invalid attempts in 60s |
| Security lockout duration | 5 minutes |
| Scan freshness window (API) | 5 seconds |

---

## Systemd Services

### coffee-controller.service
- **Type**: simple (long-running)
- **User**: coffeelover
- **Restart**: always (10s delay)
- **WorkingDirectory**: /home/coffeelover/CoffeeManager
- **Exec**: `/usr/bin/python3 controller/coffee_controller.py`

### coffee-webui.service
- **Type**: simple (long-running)
- **Port**: 8080
- **Host**: 0.0.0.0
- **Exec**: `/usr/bin/python3 ui/app.py`

### coffee-updater.timer
- **Schedule**: 10min after boot + daily at 2:00 AM
- **Persistent**: true (catches up missed runs)

---

## Auto-Updater Workflow

1. Check GitHub connectivity via API
2. Compare local HEAD vs `origin/main`
3. If different: `git pull origin main`
4. Run validation tests (`tests/test_system_validation.py`)
5. If tests fail: `git reset --hard <previous_commit>`
6. Update version info in database settings

---

## Token ID Format

- **Format**: Hex string, lowercase, no separators
- **Example**: `a1b2c3d4` (not `A1:B2:C3:D4`)
- **Normalization function**: `normalize_token_id()` in app.py removes colons/hyphens

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MASTER_TOKEN_ID` | None | Override master token (takes priority over DB) |
| `FLASK_HOST` | 0.0.0.0 | Web UI bind address |
| `FLASK_PORT` | 8080 | Web UI port |
| `FLASK_DEBUG` | 0 | Debug mode (set to 1 to enable) |

---

## Testing

### Validation Tests (tests/test_system_validation.py)

Used by auto-updater to verify system health:

1. `test_database_exists` - Check DB file presence
2. `test_database_schema` - Verify all tables exist
3. `test_database_manager_import` - Import and basic operation
4. `test_flask_app_initialization` - Flask app creation
5. `test_controller_imports` - Module import (with GPIO mocks)
6. `test_critical_files_exist` - Key files present

Run manually:
```bash
python3 tests/test_system_validation.py
```

---

## Common Patterns

### Adding a New Setting

1. Add to `init_database.py` in the INSERT OR IGNORE block
2. Access via `db.get_setting('key')` / `db.set_setting('key', 'value')`

### User State Flow

```
New Token Scanned (scan mode) → add_pending_user() → active=0, barred=1
                                      ↓
           Admin fills in details → update_user(user_name=..., name=...)
                                      ↓
                              active=1, barred=0 (automatically)
                                      ↓
                              Token now grants access
```

### Invoice Creation Flow

```
User has uninvoiced usage → create_invoice_for_user() →
  1. SELECT uninvoiced usage_log rows
  2. INSERT into invoices
  3. INSERT into invoice_items (links usage_id)
  4. All linked usage is now "invoiced"
```

---

## Network Configuration

- **Default IP**: 192.168.1.142
- **SSH User**: coffeelover
- **Web UI**: http://192.168.1.142:8080
- **GitHub Repo**: https://github.com/Bliblofy/CoffeeManagerV2

---

## Troubleshooting Commands

```bash
# Check service status
sudo systemctl status coffee-controller.service coffee-webui.service

# View logs
sudo journalctl -u coffee-controller.service -n 50
sudo journalctl -u coffee-webui.service -n 50

# Restart services
sudo systemctl restart coffee-controller.service coffee-webui.service

# Test web interface
curl -I http://localhost:8080

# Check update status
sudo journalctl -u coffee-updater.service | tail -20
```

---

## Security Considerations

1. **Master token** should be kept physically secure
2. **Brute-force protection** engages after 10 invalid attempts
3. **Database triggers** prevent accidental data deletion
4. **Offline operation** - no internet required for normal use
5. **SSH key authentication** recommended over passwords

---

*Last updated: January 2026*

