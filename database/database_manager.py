#!/usr/bin/env python3
"""
Coffee Manager Database Manager
Provides high-level interface for database operations
"""

import sqlite3
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

class CoffeeDatabaseManager:
    """Manages all database operations for the Coffee Manager system"""
    
    def __init__(self, db_path: str = None):
        """Initialize database manager"""
        if db_path is None:
            self.db_path = os.path.join(os.path.dirname(__file__), 'coffee_manager.db')
        else:
            self.db_path = db_path
    
    def get_connection(self):
        """Get database connection with proper configuration"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        return conn
    
    # User Management Methods
    
    def add_pending_user(self, token_id: str) -> bool:
        """Create a placeholder user for a newly scanned token.
        Uses minimal placeholder values due to NOT NULL constraints and bars the token.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                '''
                INSERT INTO users (token_id, user_name, name, email_address, phone_number, barred, active)
                VALUES (?, ?, ?, NULL, NULL, 1, 0)
                ON CONFLICT(token_id) DO NOTHING
                ''',
                (token_id, f"pending_{token_id}", "Pending")
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"❌ Error adding pending user: {e}")
            return False
        finally:
            conn.close()

    def add_user(self, token_id: str, user_name: str, name: str, 
                 email_address: str = None, phone_number: str = None) -> bool:
        """Add a new user to the database"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users (token_id, user_name, name, email_address, phone_number)
                VALUES (?, ?, ?, ?, ?)
            ''', (token_id, user_name, name, email_address, phone_number))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            print(f"❌ User with token_id {token_id} already exists")
            return False
        except sqlite3.Error as e:
            print(f"❌ Error adding user: {e}")
            return False
        finally:
            conn.close()
    
    def get_user(self, token_id: str) -> Optional[Dict[str, Any]]:
        """Get user information by token_id"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users WHERE token_id = ?
            ''', (token_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"❌ Error getting user: {e}")
            return None
        finally:
            conn.close()
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Get all users from the database"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM users ORDER BY created_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"❌ Error getting users: {e}")
            return []
        finally:
            conn.close()
    
    def update_user(self, token_id: str, **kwargs) -> bool:
        """Update user information"""
        if not kwargs:
            return False
            
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Ensure the user exists first; treat no-op updates as success for existing users
            cursor.execute('SELECT 1 FROM users WHERE token_id = ? LIMIT 1', (token_id,))
            exists_row = cursor.fetchone()
            if not exists_row:
                return False
            
            # Build dynamic update query
            set_clauses = []
            values = []
            for key, value in kwargs.items():
                if key in ['user_name', 'name', 'email_address', 'phone_number', 'barred', 'active']:
                    set_clauses.append(f"{key} = ?")
                    values.append(value)
            
            if not set_clauses:
                # Nothing to update, but user exists — consider this a successful no-op
                return True
                
            values.append(token_id)
            query = f"UPDATE users SET {', '.join(set_clauses)} WHERE token_id = ?"
            
            cursor.execute(query, values)
            conn.commit()
            # Some SQLite builds report rowcount=0 for no-op updates even when the row exists
            # Treat commit without error as success since the user exists
            return True
        except sqlite3.Error as e:
            print(f"❌ Error updating user: {e}")
            return False
        finally:
            conn.close()
    
    def bar_user(self, token_id: str, barred: bool = True) -> bool:
        """Bar or unbar a user"""
        return self.update_user(token_id, barred=barred)
    
    def delete_user(self, token_id: str) -> bool:
        """Delete a user and all their usage logs"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            # Delete usage logs first (foreign key constraint)
            cursor.execute('DELETE FROM usage_log WHERE token_id = ?', (token_id,))
            # Delete invoice items linked to this user's usage
            cursor.execute('''
                DELETE FROM invoice_items 
                WHERE usage_id IN (SELECT id FROM usage_log WHERE token_id = ?)
            ''', (token_id,))
            # Delete invoices for this user
            cursor.execute('DELETE FROM invoices WHERE token_id = ?', (token_id,))
            # Delete the user
            cursor.execute('DELETE FROM users WHERE token_id = ?', (token_id,))
            conn.commit()
            return cursor.rowcount > 0
        except sqlite3.Error as e:
            print(f"❌ Error deleting user: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    # Usage Tracking Methods
    
    def log_coffee_usage(self, token_id: str, coffee_type: str = 'unknown') -> bool:
        """Log a coffee usage event"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO usage_log (token_id, coffee_type)
                VALUES (?, ?)
            ''', (token_id, coffee_type))
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"❌ Error logging usage: {e}")
            return False
        finally:
            conn.close()
    
    def get_usage_history(self, token_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get usage history, optionally filtered by token_id"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            if token_id:
                cursor.execute('''
                    SELECT ul.*, u.name, u.user_name 
                    FROM usage_log ul
                    JOIN users u ON ul.token_id = u.token_id
                    WHERE ul.token_id = ?
                    ORDER BY ul.timestamp DESC
                    LIMIT ?
                ''', (token_id, limit))
            else:
                cursor.execute('''
                    SELECT ul.*, u.name, u.user_name 
                    FROM usage_log ul
                    JOIN users u ON ul.token_id = u.token_id
                    ORDER BY ul.timestamp DESC
                    LIMIT ?
                ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"❌ Error getting usage history: {e}")
            return []
        finally:
            conn.close()
    
    def get_last_usage_timestamp(self) -> Optional[datetime]:
        """Get the timestamp of the most recent usage across all users.
        Uses ORDER BY to avoid reliance on string MAX semantics and parses common SQLite formats.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp AS last_usage
                FROM usage_log
                ORDER BY timestamp DESC
                LIMIT 1
            ''')
            row = cursor.fetchone()
            if not row:
                return None
            ts = row['last_usage']
            if not ts:
                return None
            # Normalize and parse timestamp strings like 'YYYY-MM-DD HH:MM:SS[.ffffff]'
            try:
                return datetime.fromisoformat(str(ts))
            except Exception:
                from datetime import timezone
                for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
                    try:
                        return datetime.strptime(str(ts), fmt)
                    except Exception:
                        continue
                # As a last resort, try treating as UTC ISO string
                try:
                    return datetime.fromisoformat(str(ts).replace('Z', '+00:00')).astimezone(timezone.utc).replace(tzinfo=None)
                except Exception:
                    return None
        except sqlite3.Error as e:
            print(f"❌ Error getting last usage timestamp: {e}")
            return None
        finally:
            conn.close()
    
    def get_user_statistics(self, token_id: str) -> Dict[str, Any]:
        """Get usage statistics for a specific user"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Get total usage count
            cursor.execute('''
                SELECT COUNT(*) as total_coffees
                FROM usage_log 
                WHERE token_id = ?
            ''', (token_id,))
            total_coffees = cursor.fetchone()['total_coffees']
            
            # Get usage this month
            month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            cursor.execute('''
                SELECT COUNT(*) as monthly_coffees
                FROM usage_log 
                WHERE token_id = ? AND timestamp >= ?
            ''', (token_id, month_start))
            monthly_coffees = cursor.fetchone()['monthly_coffees']
            
            # Get last usage
            cursor.execute('''
                SELECT timestamp as last_usage
                FROM usage_log 
                WHERE token_id = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (token_id,))
            last_usage_row = cursor.fetchone()
            last_usage = last_usage_row['last_usage'] if last_usage_row else None
            
            return {
                'total_coffees': total_coffees,
                'monthly_coffees': monthly_coffees,
                'last_usage': last_usage
            }
        except sqlite3.Error as e:
            print(f"❌ Error getting user statistics: {e}")
            return {}
        finally:
            conn.close()
    
    # Cleanup Methods
    
    def cleanup_old_records(self, retention_years: int = 5) -> int:
        """Remove usage records older than specified years"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=retention_years * 365)
            
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
            
            return count
        except sqlite3.Error as e:
            print(f"❌ Error during cleanup: {e}")
            conn.rollback()
            return 0
        finally:
            conn.close()
    
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Count users
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            # Count active users
            cursor.execute("SELECT COUNT(*) FROM users WHERE active = 1")
            active_users = cursor.fetchone()[0]
            
            # Count barred users
            cursor.execute("SELECT COUNT(*) FROM users WHERE barred = 1")
            barred_users = cursor.fetchone()[0]
            
            # Count usage records
            cursor.execute("SELECT COUNT(*) FROM usage_log")
            usage_count = cursor.fetchone()[0]
            
            # Get database size
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            
            return {
                'total_users': user_count,
                'active_users': active_users,
                'barred_users': barred_users,
                'total_usage_records': usage_count,
                'database_size_mb': round(db_size / (1024 * 1024), 2)
            }
        except sqlite3.Error as e:
            print(f"❌ Error getting database stats: {e}")
            return {}
        finally:
            conn.close()

    # Settings helpers
    def get_setting(self, key: str) -> Optional[str]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            print(f"❌ Error getting setting '{key}': {e}")
            return None
        finally:
            conn.close()

    # Invoicing helpers
    def get_last_invoice_end(self, token_id: str) -> Optional[str]:
        """Return the period_end of the last invoice for a user, or None.
        Checks user's invoices first, then falls back to batch date if user has no invoices."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            # First check for user's last invoice (individual or batch-related)
            cur.execute(
                "SELECT period_end FROM invoices WHERE token_id = ? ORDER BY period_end DESC LIMIT 1",
                (token_id,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
        finally:
            conn.close()
        
        # If user has no invoices, check for last batch date (becomes new billing cycle start)
        last_batch = self.get_last_batch_date()
        return last_batch if last_batch else None

    def get_uninvoiced_usage(self, token_id: str, start_ts: Optional[str], end_ts: Optional[str]) -> List[Dict[str, Any]]:
        """Fetch usage not yet linked to any invoice, within optional [start,end] bounds."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            query = (
                "SELECT ul.* FROM usage_log ul "
                "LEFT JOIN invoice_items ii ON ii.usage_id = ul.id "
                "WHERE ii.id IS NULL AND ul.token_id = ? "
            )
            params = [token_id]
            if start_ts:
                query += "AND ul.timestamp >= ? "
                params.append(start_ts)
            if end_ts:
                query += "AND ul.timestamp <= ? "
                params.append(end_ts)
            query += "ORDER BY ul.timestamp ASC"
            cur.execute(query, params)
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def create_invoice_for_user(self, token_id: str, period_start: str, period_end: str, batch_id: Optional[int] = None) -> Optional[int]:
        """Create invoice for all uninvoiced usage in [period_start, period_end]. Returns invoice_id or None."""
        conn = self.get_connection()
        try:
            conn.execute('BEGIN')
            cur = conn.cursor()
            # fetch uninvoiced usage within the same connection to avoid race conditions
            query = (
                "SELECT ul.* FROM usage_log ul "
                "LEFT JOIN invoice_items ii ON ii.usage_id = ul.id "
                "WHERE ii.id IS NULL AND ul.token_id = ? "
                "AND ul.timestamp >= ? AND ul.timestamp <= ? "
                "ORDER BY ul.timestamp ASC"
            )
            cur.execute(query, (token_id, period_start, period_end))
            usage_rows = [dict(r) for r in cur.fetchall()]
            total_items = len(usage_rows)
            if total_items == 0:
                return None
            if batch_id:
                cur.execute(
                    "INSERT INTO invoices (token_id, period_start, period_end, total_items, paid, batch_id) VALUES (?,?,?,?,0,?)",
                    (token_id, period_start, period_end, total_items, batch_id),
                )
            else:
                cur.execute(
                    "INSERT INTO invoices (token_id, period_start, period_end, total_items, paid) VALUES (?,?,?,?,0)",
                    (token_id, period_start, period_end, total_items),
                )
            invoice_id = cur.lastrowid
            for u in usage_rows:
                cur.execute(
                    "INSERT INTO invoice_items (invoice_id, usage_id, timestamp) VALUES (?,?,?)",
                    (invoice_id, u['id'], u['timestamp']),
                )
            conn.commit()
            return invoice_id
        except sqlite3.Error as e:
            print(f"❌ Error creating invoice: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()

    def list_invoices(self, token_id: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            if token_id:
                cur.execute(
                    "SELECT i.*, u.name, u.user_name, u.email_address FROM invoices i JOIN users u ON i.token_id=u.token_id WHERE i.token_id=? ORDER BY i.created_at DESC",
                    (token_id,),
                )
            else:
                cur.execute(
                    "SELECT i.*, u.name, u.user_name, u.email_address FROM invoices i JOIN users u ON i.token_id=u.token_id ORDER BY i.created_at DESC"
                )
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

    def get_invoice(self, invoice_id: int) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT i.*, u.name, u.user_name, u.email_address FROM invoices i JOIN users u ON i.token_id=u.token_id WHERE i.id=?",
                (invoice_id,),
            )
            header = cur.fetchone()
            if not header:
                return None
            cur.execute(
                "SELECT ii.id, ii.timestamp, ul.id as usage_id FROM invoice_items ii JOIN usage_log ul ON ul.id=ii.usage_id WHERE ii.invoice_id=? ORDER BY ii.timestamp ASC",
                (invoice_id,),
            )
            items = [dict(r) for r in cur.fetchall()]
            inv = dict(header)
            # Use a non-conflicting key name for template access
            inv['line_items'] = items
            return inv
        finally:
            conn.close()

    def set_invoice_paid(self, invoice_id: int, paid: bool) -> bool:
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("UPDATE invoices SET paid=? WHERE id=?", (1 if paid else 0, invoice_id))
            conn.commit()
            return cur.rowcount > 0
        except sqlite3.Error as e:
            print(f"❌ Error updating invoice status: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def set_setting(self, key: str, value: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP",
                (key, value),
            )
            conn.commit()
            return True
        except sqlite3.Error as e:
            print(f"❌ Error setting setting '{key}': {e}")
            return False
        finally:
            conn.close()
    
    def _ensure_batch_tables(self):
        """Ensure batch_invoices table and batch_id column exist (migration helper)"""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            # Check if batch_invoices table exists
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='batch_invoices'")
            if not cur.fetchone():
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS batch_invoices (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        batch_date TIMESTAMP NOT NULL,
                        period_start TIMESTAMP NOT NULL,
                        period_end TIMESTAMP NOT NULL,
                        total_users INTEGER NOT NULL DEFAULT 0,
                        total_items INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
            # Check if batch_id column exists in invoices table
            cur.execute("PRAGMA table_info(invoices)")
            columns = [col[1] for col in cur.fetchall()]
            if 'batch_id' not in columns:
                cur.execute("ALTER TABLE invoices ADD COLUMN batch_id INTEGER REFERENCES batch_invoices(id)")
            conn.commit()
        except sqlite3.Error as e:
            print(f"⚠️ Migration note: {e}")
        finally:
            conn.close()
    
    def get_last_batch_date(self) -> Optional[str]:
        """Get the date of the last batch invoice, which becomes the new billing cycle start"""
        self._ensure_batch_tables()
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT batch_date FROM batch_invoices ORDER BY batch_date DESC LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else None
        finally:
            conn.close()
    
    def create_batch_invoice(self, period_start: Optional[str] = None, period_end: Optional[str] = None) -> Optional[int]:
        """Create batch invoice for all users. Returns batch_id or None."""
        from datetime import datetime
        self._ensure_batch_tables()
        
        # Determine period: from last batch date (or last invoice per user) to now
        if not period_end:
            period_end = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if not period_start:
            # Get the latest batch date, or earliest usage if no batch exists
            last_batch = self.get_last_batch_date()
            if last_batch:
                period_start = last_batch
            else:
                conn = self.get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT MIN(timestamp) FROM usage_log")
                    row = cur.fetchone()
                    period_start = row[0] if row and row[0] else period_end
                finally:
                    conn.close()
        
        # Create batch_invoice record first
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            batch_date = period_end
            cur.execute('''
                INSERT INTO batch_invoices (batch_date, period_start, period_end, total_users, total_items)
                VALUES (?, ?, ?, 0, 0)
            ''', (batch_date, period_start, period_end))
            batch_id = cur.lastrowid
            conn.commit()
        except sqlite3.Error as e:
            print(f"❌ Error creating batch invoice record: {e}")
            conn.rollback()
            return None
        finally:
            conn.close()
        
        # Get all users (not just active/barred) - invoice all users with usage
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT token_id FROM users")
            users = [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()
        
        total_items = 0
        invoice_ids = []
        
        # Create invoice for each user (each creates its own transaction)
        for user in users:
            token_id = user['token_id']
            # Get last invoice end for this user
            last_end = self.get_last_invoice_end(token_id)
            
            # If user has no invoices, use their first usage timestamp (or batch period_start as fallback)
            if not last_end:
                conn = self.get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT MIN(timestamp) FROM usage_log WHERE token_id = ?", (token_id,))
                    row = cur.fetchone()
                    user_start = row[0] if row and row[0] else period_start
                finally:
                    conn.close()
            else:
                # Use last_end as start - this will include usage from that point forward
                # The query uses >= so it will include usage at or after last_end
                user_start = last_end
            
            # Ensure we have valid dates
            if not user_start or not period_end:
                continue
            
            # Create invoice for this user (with batch_id)
            # create_invoice_for_user will return None if there's no uninvoiced usage
            invoice_id = self.create_invoice_for_user(token_id, user_start, period_end, batch_id)
            if invoice_id:
                invoice_ids.append(invoice_id)
                # Get item count
                conn = self.get_connection()
                try:
                    cur = conn.cursor()
                    cur.execute("SELECT total_items FROM invoices WHERE id = ?", (invoice_id,))
                    row = cur.fetchone()
                    if row:
                        total_items += row[0]
                finally:
                    conn.close()
        
        # Update batch totals
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute('''
                UPDATE batch_invoices 
                SET total_users = ?, total_items = ?
                WHERE id = ?
            ''', (len(invoice_ids), total_items, batch_id))
            conn.commit()
        except sqlite3.Error as e:
            print(f"❌ Error updating batch totals: {e}")
            conn.rollback()
        finally:
            conn.close()
        
        return batch_id if invoice_ids else None
    
    def get_batch_invoice(self, batch_id: int) -> Optional[Dict[str, Any]]:
        """Get batch invoice with all user invoices"""
        self._ensure_batch_tables()
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM batch_invoices WHERE id = ?", (batch_id,))
            batch = cur.fetchone()
            if not batch:
                return None
            
            batch_dict = dict(batch)
            
            # Get all invoices in this batch
            cur.execute('''
                SELECT i.*, u.name, u.user_name, u.email_address
                FROM invoices i
                JOIN users u ON i.token_id = u.token_id
                WHERE i.batch_id = ?
                ORDER BY u.name ASC
            ''', (batch_id,))
            invoices = [dict(r) for r in cur.fetchall()]
            batch_dict['invoices'] = invoices
            
            return batch_dict
        finally:
            conn.close()
    
    def list_batch_invoices(self) -> List[Dict[str, Any]]:
        """List all batch invoices"""
        self._ensure_batch_tables()
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM batch_invoices ORDER BY batch_date DESC")
            return [dict(r) for r in cur.fetchall()]
        finally:
            conn.close()

# Example usage and testing
if __name__ == "__main__":
    # Test the database manager
    db = CoffeeDatabaseManager()
    
    print("🧪 Testing Coffee Database Manager...")
    
    # Test adding a user
    print("\n1. Adding test user...")
    success = db.add_user("1234567890", "john_doe", "John Doe", "john@example.com", "+1234567890")
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Test getting user
    print("\n2. Getting user info...")
    user = db.get_user("1234567890")
    print(f"   User: {user}")
    
    # Test logging usage
    print("\n3. Logging coffee usage...")
    success = db.log_coffee_usage("1234567890", "espresso")
    print(f"   Result: {'✅ Success' if success else '❌ Failed'}")
    
    # Test getting statistics
    print("\n4. Getting user statistics...")
    stats = db.get_user_statistics("1234567890")
    print(f"   Stats: {stats}")
    
    # Test database stats
    print("\n5. Database statistics...")
    db_stats = db.get_database_stats()
    print(f"   Stats: {db_stats}")
    
    print("\n✅ Database manager test complete!")
