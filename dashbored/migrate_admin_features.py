"""
Migration script to add admin management features
Adds vessel_auth_tokens and admin_audit_log tables to users.sqlite
"""
import sqlite3
from datetime import datetime

def run_migration():
    print("=" * 70)
    print("Migrating users.sqlite for Admin/Fleet Manager Features")
    print("=" * 70)
    
    conn = sqlite3.connect('users.sqlite')
    cursor = conn.cursor()
    
    # Add vessel_auth_tokens table
    print("\nCreating vessel_auth_tokens table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vessel_auth_tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vessel_id INTEGER NOT NULL UNIQUE,
            auth_token VARCHAR(255) NOT NULL UNIQUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            created_by INTEGER,
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    print("✓ vessel_auth_tokens table created")
    
    # Add admin_audit_log table
    print("\nCreating admin_audit_log table...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_user_id INTEGER NOT NULL,
            action_type VARCHAR(50) NOT NULL,
            action_details TEXT,
            target_user_id INTEGER,
            target_vessel_id INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_user_id) REFERENCES users(id),
            FOREIGN KEY (target_user_id) REFERENCES users(id)
        )
    ''')
    print("✓ admin_audit_log table created")
    
    conn.commit()
    conn.close()
    
    print("\n" + "=" * 70)
    print("Migration completed successfully!")
    print("=" * 70)

if __name__ == '__main__':
    run_migration()
