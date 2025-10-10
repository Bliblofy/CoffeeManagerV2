#!/usr/bin/env python3
"""
Coffee Manager Database Initialization Script
Creates SQLite database with users and usage tracking tables
"""

import sqlite3
import os
from datetime import datetime, timedelta

# Database configuration
DB_PATH = os.path.join(os.path.dirname(__file__), 'coffee_manager.db')

def create_database():
    """Create the SQLite database with required tables"""
    
    # Connect to database (creates if doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                token_id TEXT PRIMARY KEY,
                user_name TEXT NOT NULL,
                name TEXT NOT NULL,
                email_address TEXT,
                phone_number TEXT,
                barred BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_seen TIMESTAMP,
                active BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create usage tracking table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                coffee_type TEXT DEFAULT 'unknown',
                FOREIGN KEY(token_id) REFERENCES users(token_id)
            )
        ''')
        
        # Create index on timestamp for efficient cleanup queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_timestamp 
            ON usage_log(timestamp)
        ''')
        
        # Create index on token_id for efficient lookups
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_usage_token_id 
            ON usage_log(token_id)
        ''')
        
        # Create settings table for system configuration
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create invoices table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_id TEXT NOT NULL,
                period_start TIMESTAMP NOT NULL,
                period_end TIMESTAMP NOT NULL,
                total_items INTEGER NOT NULL DEFAULT 0,
                paid BOOLEAN NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(token_id) REFERENCES users(token_id)
            )
        ''')

        # Create invoice_items table linking usage rows
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS invoice_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_id INTEGER NOT NULL,
                usage_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                -- Prevent cascading deletes; rely on explicit cleanup logic if ever needed
                FOREIGN KEY(invoice_id) REFERENCES invoices(id) ON DELETE RESTRICT,
                FOREIGN KEY(usage_id) REFERENCES usage_log(id) ON DELETE RESTRICT,
                UNIQUE(usage_id)
            )
        ''')
        
        # Insert default settings
        cursor.execute('''
            INSERT OR IGNORE INTO settings (key, value) VALUES 
            ('cleanup_enabled', '1'),
            ('retention_years', '5'),
            ('last_cleanup', '1970-01-01 00:00:00'),
            ('current_version', 'unknown'),
            ('previous_version', 'unknown'),
            ('last_update_check', '1970-01-01 00:00:00'),
            ('last_update_time', '1970-01-01 00:00:00'),
            ('last_update_status', 'never'),
            ('last_update_message', 'No updates performed yet')
        ''')
        
        conn.commit()
        
        # --- Enforce immutability: block deletions from all core tables ---
        # Users table
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS trg_no_delete_users
            BEFORE DELETE ON users
            BEGIN
                SELECT RAISE(FAIL, 'Deletion disabled: users table is immutable');
            END;
        ''')

        # Usage log table
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS trg_no_delete_usage
            BEFORE DELETE ON usage_log
            BEGIN
                SELECT RAISE(FAIL, 'Deletion disabled: usage_log table is immutable');
            END;
        ''')

        # Invoices table
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS trg_no_delete_invoices
            BEFORE DELETE ON invoices
            BEGIN
                SELECT RAISE(FAIL, 'Deletion disabled: invoices table is immutable');
            END;
        ''')

        # Invoice items table
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS trg_no_delete_invoice_items
            BEFORE DELETE ON invoice_items
            BEGIN
                SELECT RAISE(FAIL, 'Deletion disabled: invoice_items table is immutable');
            END;
        ''')

        conn.commit()
        print("✅ Database created successfully!")
        print(f"📁 Database location: {DB_PATH}")
        
    except sqlite3.Error as e:
        print(f"❌ Error creating database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def cleanup_old_records():
    """Remove usage records older than 5 years"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Calculate cutoff date (5 years ago)
        cutoff_date = datetime.now() - timedelta(days=5*365)
        
        # Count records to be deleted
        cursor.execute('''
            SELECT COUNT(*) FROM usage_log 
            WHERE timestamp < ?
        ''', (cutoff_date,))
        
        count = cursor.fetchone()[0]
        
        if count > 0:
            # Delete old records
            cursor.execute('''
                DELETE FROM usage_log 
                WHERE timestamp < ?
            ''', (cutoff_date,))
            
            # Update last cleanup timestamp
            cursor.execute('''
                UPDATE settings 
                SET value = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE key = 'last_cleanup'
            ''', (datetime.now().isoformat(),))
            
            conn.commit()
            print(f"🧹 Cleaned up {count} old usage records")
        else:
            print("✨ No old records to clean up")
            
    except sqlite3.Error as e:
        print(f"❌ Error during cleanup: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def verify_database():
    """Verify database structure and show table info"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Get table information
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("\n📊 Database Tables:")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            print(f"\n🔹 {table_name}:")
            for col in columns:
                print(f"   - {col[1]} ({col[2]})")
        
        # Count records
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM usage_log")
        usage_count = cursor.fetchone()[0]
        
        print(f"\n📈 Record Counts:")
        print(f"   - Users: {user_count}")
        print(f"   - Usage logs: {usage_count}")
        
    except sqlite3.Error as e:
        print(f"❌ Error verifying database: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 Initializing Coffee Manager Database...")
    
    # Create database
    create_database()
    
    # Clean up any existing old records
    cleanup_old_records()
    
    # Verify database structure
    verify_database()
    
    print("\n✅ Database initialization complete!")
    print("\n💡 Next steps:")
    print("   1. Install dependencies: pip3 install sqlite3")
    print("   2. Test database: python3 init_database.py")
    print("   3. Integrate with your coffee controller")
