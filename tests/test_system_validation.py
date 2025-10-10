#!/usr/bin/env python3
"""
System Validation Test Suite for Coffee Manager
Used by auto-updater to verify system health after updates
"""

import sys
import os
import sqlite3
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_database_exists():
    """Verify database file exists"""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'coffee_manager.db')
    if not os.path.exists(db_path):
        raise AssertionError(f"Database file not found at {db_path}")
    print("✓ Database file exists")

def test_database_schema():
    """Validate all required tables exist"""
    db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'coffee_manager.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    required_tables = ['users', 'usage_log', 'settings', 'invoices', 'invoice_items']
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    for table in required_tables:
        if table not in tables:
            conn.close()
            raise AssertionError(f"Required table '{table}' not found in database")
    
    conn.close()
    print("✓ Database schema valid")

def test_database_manager_import():
    """Test database manager can be imported"""
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'database'))
        from database_manager import CoffeeDatabaseManager
        db = CoffeeDatabaseManager()
        # Test basic operation
        _ = db.get_setting('cleanup_enabled')
        print("✓ Database manager import successful")
    except Exception as e:
        raise AssertionError(f"Failed to import database manager: {e}")

def test_flask_app_initialization():
    """Verify Flask app can initialize without errors"""
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'ui'))
        from app import create_app
        app = create_app()
        # Test basic configuration
        if app is None:
            raise AssertionError("Flask app creation returned None")
        print("✓ Flask app initialization successful")
    except Exception as e:
        raise AssertionError(f"Failed to initialize Flask app: {e}")

def test_controller_imports():
    """Verify coffee controller imports succeed"""
    try:
        # Mock GPIO for testing environment
        sys.modules['RPi'] = type(sys)('RPi')
        sys.modules['RPi.GPIO'] = type(sys)('GPIO')
        sys.modules['spidev'] = type(sys)('spidev')
        sys.modules['mfrc522'] = type(sys)('mfrc522')
        
        # Create mock classes
        class MockGPIO:
            BCM = 0
            OUT = 1
            IN = 0
            HIGH = 1
            LOW = 0
            @staticmethod
            def setmode(mode): pass
            @staticmethod
            def setwarnings(flag): pass
            @staticmethod
            def setup(pin, mode): pass
            @staticmethod
            def output(pin, state): pass
            @staticmethod
            def cleanup(): pass
        
        class MockMFRC522:
            PICC_REQIDL = 0x26
            MI_OK = 0
            def __init__(self): pass
            def MFRC522_Request(self, mode): return (1, None)
            def MFRC522_Anticoll(self): return (1, None)
        
        sys.modules['RPi.GPIO'] = MockGPIO
        sys.modules['mfrc522'].MFRC522 = MockMFRC522
        
        # Now try to import controller module (not instantiate)
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'controller'))
        import coffee_controller
        print("✓ Controller imports successful")
    except Exception as e:
        raise AssertionError(f"Failed to import controller: {e}")

def test_critical_files_exist():
    """Verify critical files exist"""
    base_path = os.path.join(os.path.dirname(__file__), '..')
    critical_files = [
        'database/database_manager.py',
        'database/init_database.py',
        'controller/coffee_controller.py',
        'ui/app.py',
        'ui/templates/base.html',
        'ui/templates/administration.html'
    ]
    
    for file_path in critical_files:
        full_path = os.path.join(base_path, file_path)
        if not os.path.exists(full_path):
            raise AssertionError(f"Critical file not found: {file_path}")
    
    print("✓ All critical files exist")

def run_all_tests():
    """Run all validation tests and return exit code"""
    tests = [
        ("Database Exists", test_database_exists),
        ("Database Schema", test_database_schema),
        ("Database Manager Import", test_database_manager_import),
        ("Flask App Initialization", test_flask_app_initialization),
        ("Controller Imports", test_controller_imports),
        ("Critical Files", test_critical_files_exist)
    ]
    
    print("=" * 60)
    print("Running Coffee Manager System Validation Tests")
    print("=" * 60)
    
    failed_tests = []
    
    for test_name, test_func in tests:
        try:
            print(f"\nRunning: {test_name}")
            test_func()
        except AssertionError as e:
            print(f"✗ {test_name} FAILED: {e}")
            failed_tests.append((test_name, str(e)))
        except Exception as e:
            print(f"✗ {test_name} ERROR: {e}")
            failed_tests.append((test_name, f"Unexpected error: {e}"))
    
    print("\n" + "=" * 60)
    if failed_tests:
        print(f"VALIDATION FAILED: {len(failed_tests)} test(s) failed")
        for test_name, error in failed_tests:
            print(f"  - {test_name}: {error}")
        print("=" * 60)
        return 1
    else:
        print("VALIDATION PASSED: All tests successful")
        print("=" * 60)
        return 0

if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)


