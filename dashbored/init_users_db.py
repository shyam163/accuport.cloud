"""
Initialize users.sqlite database with Accuport user structure
- super1, super2: Vessel Managers
- fleet1: Fleet Manager
- admin: Administrator account
"""
import sqlite3
import bcrypt
from datetime import datetime

def create_users_database():
    """Create users.sqlite with proper schema"""
    conn = sqlite3.connect('users.sqlite')
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            full_name VARCHAR(100) NOT NULL,
            email VARCHAR(100),
            role VARCHAR(20) NOT NULL CHECK(role IN ('vessel_manager', 'fleet_manager', 'admin')),
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create vessel_assignments table
    # vessel_id references vessels.id from accubase.sqlite
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS vessel_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            vessel_id INTEGER NOT NULL,
            assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            UNIQUE(user_id, vessel_id)
        )
    ''')

    # Create manager_hierarchy table
    # Defines which vessel managers report to which fleet managers
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS manager_hierarchy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fleet_manager_id INTEGER NOT NULL,
            vessel_manager_id INTEGER NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (fleet_manager_id) REFERENCES users(id),
            FOREIGN KEY (vessel_manager_id) REFERENCES users(id),
            UNIQUE(fleet_manager_id, vessel_manager_id)
        )
    ''')

    conn.commit()
    print("✓ Database schema created successfully")
    return conn

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_accuport_users(conn):
    """Create Accuport user accounts"""
    cursor = conn.cursor()

    # User accounts
    # Format: (username, password, full_name, email, role)
    users = [
        ('super1', 'super1pass', 'Superintendent 1', 'super1@accuport.cloud', 'vessel_manager'),
        ('super2', 'super2pass', 'Superintendent 2', 'super2@accuport.cloud', 'vessel_manager'),
        ('fleet1', 'fleet1pass', 'Fleet Manager 1', 'fleet1@accuport.cloud', 'fleet_manager'),
        ('admin', 'adminpass', 'Administrator', 'admin@accuport.cloud', 'admin'),
    ]

    print("\nCreating user accounts...")
    user_ids = {}

    for username, password, full_name, email, role in users:
        password_hash = hash_password(password)
        try:
            cursor.execute('''
                INSERT INTO users (username, password_hash, full_name, email, role)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, password_hash, full_name, email, role))
            user_ids[username] = cursor.lastrowid
            print(f"✓ Created user: {username} ({role})")
        except sqlite3.IntegrityError:
            print(f"  User {username} already exists, skipping...")
            cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
            user_ids[username] = cursor.fetchone()[0]

    conn.commit()
    return user_ids

def setup_vessel_assignments(conn, user_ids):
    """
    Setup vessel assignments
    NOTE: Vessel IDs must match entries in accubase.sqlite vessels table

    Current vessel structure:
    - super1 manages: MV Racer (id=2), MT Aqua (id=3)
    - super2 manages: MT Voyager (id=4), MV October (id=1)
    """
    cursor = conn.cursor()

    # Vessel assignments (user, vessel_id)
    # NOTE: These vessel IDs must exist in accubase.sqlite
    assignments = [
        # super1's vessels
        ('super1', 2),  # MV Racer
        ('super1', 3),  # MT Aqua

        # super2's vessels
        ('super2', 4),  # MT Voyager
        ('super2', 1),  # MV October (exists in database)
    ]

    print("\nCreating vessel assignments...")
    for username, vessel_id in assignments:
        try:
            cursor.execute('''
                INSERT INTO vessel_assignments (user_id, vessel_id)
                VALUES (?, ?)
            ''', (user_ids[username], vessel_id))
            print(f"✓ Assigned vessel {vessel_id} to {username}")
        except sqlite3.IntegrityError:
            print(f"  Assignment already exists for {username} -> vessel {vessel_id}")

    conn.commit()

def setup_manager_hierarchy(conn, user_ids):
    """
    Setup manager hierarchy
    fleet1 manages both super1 and super2
    """
    cursor = conn.cursor()

    # Hierarchy: (fleet_manager, vessel_manager)
    hierarchies = [
        ('fleet1', 'super1'),
        ('fleet1', 'super2'),
    ]

    print("\nCreating manager hierarchy...")
    for fleet_manager, vessel_manager in hierarchies:
        try:
            cursor.execute('''
                INSERT INTO manager_hierarchy (fleet_manager_id, vessel_manager_id)
                VALUES (?, ?)
            ''', (user_ids[fleet_manager], user_ids[vessel_manager]))
            print(f"✓ {fleet_manager} manages {vessel_manager}")
        except sqlite3.IntegrityError:
            print(f"  Hierarchy already exists: {fleet_manager} -> {vessel_manager}")

    conn.commit()

def verify_accubase_vessels():
    """Verify and show vessels in accubase.sqlite"""
    print("\nVerifying vessels in accubase.sqlite...")
    try:
        conn = sqlite3.connect('accubase.sqlite')
        cursor = conn.cursor()
        cursor.execute('SELECT id, vessel_id, vessel_name FROM vessels ORDER BY id')
        vessels = cursor.fetchall()

        if vessels:
            print("\nExisting vessels:")
            for vid, vessel_id, vessel_name in vessels:
                print(f"  ID {vid}: {vessel_name} ({vessel_id})")
        else:
            print("  No vessels found in accubase.sqlite")

        conn.close()
        return vessels
    except Exception as e:
        print(f"  Error accessing accubase.sqlite: {e}")
        return []

def main():
    print("=" * 70)
    print("Initializing Accuport Users Database")
    print("=" * 70)

    # Check vessels first
    vessels = verify_accubase_vessels()

    if len(vessels) < 4:
        print("\n" + "!" * 70)
        print("WARNING: Not all 4 vessels exist in accubase.sqlite yet!")
        print(f"Found {len(vessels)} vessel(s), expected 4")
        print("\nMissing vessels will need to be added by the data fetcher.")
        print("!" * 70)
    else:
        print("\n✓ All 4 vessels found in accubase.sqlite!")

    # Create users database
    conn = create_users_database()
    user_ids = create_accuport_users(conn)
    setup_vessel_assignments(conn, user_ids)
    setup_manager_hierarchy(conn, user_ids)

    conn.close()

    print("\n" + "=" * 70)
    print("Database initialized successfully!")
    print("=" * 70)
    print("\nUser Hierarchy:")
    print("  fleet1 (Fleet Manager)")
    print("    ├── super1 (Vessel Manager)")
    print("    │   ├── MV Racer (vessel_id=2)")
    print("    │   └── MT Aqua (vessel_id=3)")
    print("    └── super2 (Vessel Manager)")
    print("        ├── MT Voyager (vessel_id=4)")
    print("        └── MV October (vessel_id=1)")
    print("  admin (Administrator)")
    print("\nLogin Credentials:")
    print("  super1 / super1pass")
    print("  super2 / super2pass")
    print("  fleet1 / fleet1pass")
    print("  admin  / adminpass")
    print("=" * 70)

if __name__ == '__main__':
    main()
