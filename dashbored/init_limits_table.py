"""
Initialize parameter_limits table in users.sqlite
"""
import sqlite3
import os

def create_limits_table(db_path):
    """Create parameter_limits table if it doesn't exist"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS parameter_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            equipment_type TEXT NOT NULL,
            parameter_name TEXT NOT NULL,
            lower_limit REAL NOT NULL,
            upper_limit REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(equipment_type, parameter_name)
        )
    """)

    conn.commit()
    conn.close()
    print("✓ parameter_limits table created successfully")

if __name__ == '__main__':
    db_path = '/var/www/accuport.cloud/dashbored/users.sqlite'

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        exit(1)

    create_limits_table(db_path)
