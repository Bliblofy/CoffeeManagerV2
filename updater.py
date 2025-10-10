#!/usr/bin/env python3
"""
Coffee Manager Auto-Update Script
Checks GitHub for updates, applies them, validates, and rolls back if needed
"""

import os
import sys
import subprocess
import sqlite3
from datetime import datetime
from pathlib import Path

# Configuration
GITHUB_REPO = "https://github.com/Bliblofy/CoffeeManagerV2"
GITHUB_API = "https://api.github.com/repos/Bliblofy/CoffeeManagerV2/commits/main"
PROJECT_ROOT = Path(__file__).parent.absolute()
DB_PATH = PROJECT_ROOT / "database" / "coffee_manager.db"
TEST_SCRIPT = PROJECT_ROOT / "tests" / "test_system_validation.py"

def log(message):
    """Print timestamped log message"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

def check_internet_connection():
    """Test if GitHub API is accessible"""
    log("Checking internet connectivity to GitHub...")
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "--connect-timeout", "10", GITHUB_API],
            capture_output=True,
            text=True,
            timeout=15
        )
        if result.returncode == 0 and result.stdout.strip() in ["200", "304"]:
            log("✓ GitHub is reachable")
            return True
        else:
            log(f"✗ GitHub not reachable (HTTP {result.stdout.strip()})")
            return False
    except Exception as e:
        log(f"✗ Internet check failed: {e}")
        return False

def get_current_commit():
    """Get current local HEAD commit hash"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            log(f"Current commit: {commit[:8]}")
            return commit
        else:
            log(f"✗ Failed to get current commit: {result.stderr}")
            return None
    except Exception as e:
        log(f"✗ Error getting current commit: {e}")
        return None

def get_remote_commit():
    """Fetch latest commit hash from GitHub master branch"""
    log("Fetching latest commit from GitHub...")
    try:
        # Fetch remote changes without merging
        subprocess.run(
            ["git", "fetch", "origin", "main"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            timeout=30,
            check=True
        )
        
        # Get remote commit hash
        result = subprocess.run(
            ["git", "rev-parse", "origin/main"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            commit = result.stdout.strip()
            log(f"Remote commit: {commit[:8]}")
            return commit
        else:
            log(f"✗ Failed to get remote commit: {result.stderr}")
            return None
    except Exception as e:
        log(f"✗ Error fetching remote commit: {e}")
        return None

def apply_update():
    """Execute git pull to apply updates"""
    log("Applying updates via git pull...")
    try:
        result = subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            log("✓ Git pull successful")
            log(f"Output: {result.stdout.strip()}")
            return True
        else:
            log(f"✗ Git pull failed: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ Error during git pull: {e}")
        return False

def run_validation_tests():
    """Execute validation test suite"""
    log("Running validation tests...")
    try:
        result = subprocess.run(
            [sys.executable, str(TEST_SCRIPT)],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # Print test output
        if result.stdout:
            for line in result.stdout.split('\n'):
                if line.strip():
                    log(f"  TEST: {line}")
        
        if result.returncode == 0:
            log("✓ All validation tests passed")
            return True
        else:
            log(f"✗ Validation tests failed (exit code {result.returncode})")
            if result.stderr:
                log(f"  Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        log("✗ Validation tests timed out")
        return False
    except Exception as e:
        log(f"✗ Error running validation tests: {e}")
        return False

def rollback_update(previous_commit):
    """Revert to previous commit using git reset"""
    log(f"Rolling back to previous commit: {previous_commit[:8]}")
    try:
        result = subprocess.run(
            ["git", "reset", "--hard", previous_commit],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=30
        )
        if result.returncode == 0:
            log("✓ Rollback successful")
            return True
        else:
            log(f"✗ Rollback failed: {result.stderr}")
            return False
    except Exception as e:
        log(f"✗ Error during rollback: {e}")
        return False

def update_version_info(current_version, previous_version, status, message):
    """Store version and update status in database"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cursor.execute(
            "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'current_version'",
            (current_version,)
        )
        cursor.execute(
            "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'previous_version'",
            (previous_version,)
        )
        cursor.execute(
            "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_update_check'",
            (timestamp,)
        )
        
        if status in ['success', 'rollback']:
            cursor.execute(
                "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_update_time'",
                (timestamp,)
            )
        
        cursor.execute(
            "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_update_status'",
            (status,)
        )
        cursor.execute(
            "UPDATE settings SET value = ?, updated_at = CURRENT_TIMESTAMP WHERE key = 'last_update_message'",
            (message,)
        )
        
        conn.commit()
        conn.close()
        log("✓ Version info updated in database")
        return True
    except Exception as e:
        log(f"✗ Failed to update version info: {e}")
        return False

def main():
    """Main update process"""
    log("=" * 70)
    log("Coffee Manager Auto-Update Started")
    log("=" * 70)
    
    # Check internet connectivity
    if not check_internet_connection():
        log("No internet connection - skipping update check")
        update_version_info("unknown", "unknown", "no_internet", "No internet connection available")
        return 0
    
    # Get current commit
    current_commit = get_current_commit()
    if not current_commit:
        log("✗ Cannot determine current version")
        update_version_info("unknown", "unknown", "error", "Failed to determine current version")
        return 1
    
    # Get remote commit
    remote_commit = get_remote_commit()
    if not remote_commit:
        log("✗ Cannot fetch remote version")
        update_version_info(current_commit, current_commit, "error", "Failed to fetch remote version")
        return 1
    
    # Check if update is needed
    if current_commit == remote_commit:
        log("✓ Already up to date")
        update_version_info(current_commit, current_commit, "up_to_date", "No updates available")
        return 0
    
    log(f"Update available: {current_commit[:8]} → {remote_commit[:8]}")
    
    # Apply update
    if not apply_update():
        log("✗ Update failed - keeping current version")
        update_version_info(current_commit, current_commit, "error", "Git pull failed")
        return 1
    
    # Verify new commit
    new_commit = get_current_commit()
    if not new_commit or new_commit != remote_commit:
        log("✗ Update verification failed")
        rollback_update(current_commit)
        update_version_info(current_commit, current_commit, "error", "Update verification failed")
        return 1
    
    # Run validation tests
    if not run_validation_tests():
        log("✗ Validation failed - rolling back")
        if rollback_update(current_commit):
            update_version_info(current_commit, remote_commit, "rollback", 
                              f"Validation tests failed, rolled back from {remote_commit[:8]}")
            log("✓ Successfully rolled back to previous version")
        else:
            update_version_info(new_commit, current_commit, "error", 
                              "Validation failed and rollback failed - manual intervention required")
            log("✗ CRITICAL: Rollback failed - manual intervention required")
            return 2
        return 1
    
    # Success!
    log("✓ Update completed successfully")
    update_version_info(new_commit, current_commit, "success", 
                       f"Successfully updated from {current_commit[:8]} to {new_commit[:8]}")
    
    log("=" * 70)
    log("Update Complete - Services will restart on next power cycle")
    log("=" * 70)
    
    return 0

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except Exception as e:
        log(f"✗ FATAL ERROR: {e}")
        try:
            update_version_info("unknown", "unknown", "error", f"Fatal error: {str(e)}")
        except:
            pass
        sys.exit(3)


