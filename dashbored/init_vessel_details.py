#!/usr/bin/env python3
"""
Initialize vessel_details table and insert dummy data for MT Aqua
Run once to set up the database
"""
import sqlite3
from datetime import datetime

USERS_DB = '/var/www/accuport.cloud/dashbored/users.sqlite'

def init_vessel_details_table():
    """Create vessel_details table with all fields"""
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()

    try:
        # Create vessel_details table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS vessel_details (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vessel_id INTEGER NOT NULL UNIQUE,

                -- Vessel Information (5 fields)
                vessel_name TEXT,
                vessel_type TEXT,
                year_of_build INTEGER,
                imo_number TEXT,
                company_name TEXT,

                -- Main Engine 1 (7 fields)
                me1_make TEXT,
                me1_model TEXT,
                me1_serial TEXT,
                me1_system_oil TEXT,
                me1_cylinder_oil TEXT,
                me1_fuel1 TEXT,
                me1_fuel2 TEXT,

                -- Main Engine 2 (7 fields)
                me2_make TEXT,
                me2_model TEXT,
                me2_serial TEXT,
                me2_system_oil TEXT,
                me2_cylinder_oil TEXT,
                me2_fuel1 TEXT,
                me2_fuel2 TEXT,

                -- Auxiliary Engines Shared (3 fields)
                ae_system_oil TEXT,
                ae_fuel1 TEXT,
                ae_fuel2 TEXT,

                -- AE 1, 2, 3 (9 fields total)
                ae1_make TEXT,
                ae1_model TEXT,
                ae1_serial TEXT,
                ae2_make TEXT,
                ae2_model TEXT,
                ae2_serial TEXT,
                ae3_make TEXT,
                ae3_model TEXT,
                ae3_serial TEXT,

                -- Boiler Shared (3 fields)
                boiler_system_oil TEXT,
                boiler_fuel1 TEXT,
                boiler_fuel2 TEXT,

                -- Auxiliary Boilers 1 & 2, EGE (9 fields)
                ab1_make TEXT,
                ab1_model TEXT,
                ab1_serial TEXT,
                ab2_make TEXT,
                ab2_model TEXT,
                ab2_serial TEXT,
                ege_make TEXT,
                ege_model TEXT,
                ege_serial TEXT,

                -- Water Treatment (4 fields)
                bwt_chemical_manufacturer TEXT,
                bwt_chemicals_in_use TEXT,
                cwt_chemical_manufacturer TEXT,
                cwt_chemicals_in_use TEXT,

                -- Environmental Systems (11 fields)
                bwts_make TEXT,
                bwts_model TEXT,
                bwts_serial TEXT,
                egcs_make TEXT,
                egcs_model TEXT,
                egcs_serial TEXT,
                egcs_type TEXT,
                stp_make TEXT,
                stp_model TEXT,
                stp_serial TEXT,
                stp_capacity TEXT,

                -- Audit Trail
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by_user_id INTEGER,

                FOREIGN KEY (updated_by_user_id) REFERENCES users(id)
            )
        ''')

        # Create index
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_vessel_details_vessel_id
            ON vessel_details(vessel_id)
        ''')

        print("✓ vessel_details table created successfully")
        print("✓ Index on vessel_id created")

        conn.commit()
        return True

    except Exception as e:
        print(f"✗ Error creating table: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def insert_mt_aqua_data():
    """Insert realistic dummy data for MT Aqua (vessel_id=2)"""
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()

    try:
        # Check if MT Aqua data already exists
        cursor.execute('SELECT id FROM vessel_details WHERE vessel_id = 2')
        if cursor.fetchone():
            print("⚠ MT Aqua data already exists, skipping insert")
            return True

        # MT Aqua realistic marine equipment specifications
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        cursor.execute('''
            INSERT INTO vessel_details (
                vessel_id,

                -- Vessel Info
                vessel_name, vessel_type, year_of_build, imo_number, company_name,

                -- Main Engine 1
                me1_make, me1_model, me1_serial,
                me1_system_oil, me1_cylinder_oil, me1_fuel1, me1_fuel2,

                -- Main Engine 2
                me2_make, me2_model, me2_serial,
                me2_system_oil, me2_cylinder_oil, me2_fuel1, me2_fuel2,

                -- Aux Engines Shared
                ae_system_oil, ae_fuel1, ae_fuel2,

                -- AE 1
                ae1_make, ae1_model, ae1_serial,

                -- AE 2
                ae2_make, ae2_model, ae2_serial,

                -- AE 3
                ae3_make, ae3_model, ae3_serial,

                -- Boiler Shared
                boiler_system_oil, boiler_fuel1, boiler_fuel2,

                -- Aux Boiler 1
                ab1_make, ab1_model, ab1_serial,

                -- Aux Boiler 2
                ab2_make, ab2_model, ab2_serial,

                -- EGE
                ege_make, ege_model, ege_serial,

                -- Water Treatment
                bwt_chemical_manufacturer, bwt_chemicals_in_use,
                cwt_chemical_manufacturer, cwt_chemicals_in_use,

                -- BWTS
                bwts_make, bwts_model, bwts_serial,

                -- EGCS
                egcs_make, egcs_model, egcs_serial, egcs_type,

                -- STP
                stp_make, stp_model, stp_serial, stp_capacity,

                -- Audit
                created_at, updated_at, updated_by_user_id
            ) VALUES (
                2,

                -- Vessel Info
                'MT Aqua',
                'Oil/Chemical Tanker',
                2018,
                '9876543',
                'Pacific Marine Shipping Ltd',

                -- Main Engine 1 (MAN B&W 6S50ME-C8.5)
                'MAN B&W',
                '6S50ME-C8.5',
                'ME1-50298-2018',
                'Shell Alexia S6 40',
                'Shell Alexia S5 70',
                'VLSFO 0.5%S',
                'MGO',

                -- Main Engine 2 (MAN B&W 6S50ME-C8.5)
                'MAN B&W',
                '6S50ME-C8.5',
                'ME2-50299-2018',
                'Shell Alexia S6 40',
                'Shell Alexia S5 70',
                'VLSFO 0.5%S',
                'MGO',

                -- Aux Engines Shared
                'Shell Gadinia S3 40',
                'MGO',
                'LSMGO',

                -- AE 1 (Caterpillar CAT 3516C)
                'Caterpillar',
                '3516C TA',
                'AE1-CAT-35167-2018',

                -- AE 2 (Caterpillar CAT 3516C)
                'Caterpillar',
                '3516C TA',
                'AE2-CAT-35168-2018',

                -- AE 3 (Caterpillar CAT 3516C)
                'Caterpillar',
                '3516C TA',
                'AE3-CAT-35169-2018',

                -- Boiler Shared
                'Shell Morlina S2 BL 10',
                'MGO',
                'LSMGO',

                -- Aux Boiler 1 (Aalborg)
                'Aalborg',
                'OC-TC 3500',
                'AB1-AAL-35001-2018',

                -- Aux Boiler 2 (Aalborg)
                'Aalborg',
                'Mission OC 1200',
                'AB2-AAL-12002-2018',

                -- EGE (Exhaust Gas Economizer)
                'Aalborg',
                'OC-EGE 800',
                'EGE-AAL-8001-2018',

                -- Water Treatment
                'Vecom Marine',
                'Vecom WT220, WT300, Oxygen Scavenger OS10',
                'Drew Marine',
                'Aquamag Liquid, Aquatreat 220',

                -- BWTS (Ballast Water Treatment System)
                'Optimarin',
                'OBS 500',
                'BWTS-OPT-5001-2018',

                -- EGCS (Exhaust Gas Cleaning System)
                'Alfa Laval',
                'PureSOx 2.0',
                'EGCS-AL-PS2001-2018',
                'Open Loop',

                -- STP (Sewage Treatment Plant)
                'Wartsila',
                'Biokinetics 25',
                'STP-WRT-BK251-2018',
                '25 m³/day',

                -- Audit
                ?, ?, 4
            )
        ''', (now, now))

        conn.commit()
        print("✓ MT Aqua dummy data inserted successfully")
        print("\nMT Aqua Equipment Summary:")
        print("  Vessel: Oil/Chemical Tanker, Built 2018")
        print("  Main Engines: 2x MAN B&W 6S50ME-C8.5")
        print("  Aux Engines: 3x Caterpillar 3516C TA")
        print("  Boilers: Aalborg OC-TC 3500, Mission OC 1200, OC-EGE 800")
        print("  BWTS: Optimarin OBS 500")
        print("  EGCS: Alfa Laval PureSOx 2.0 (Open Loop)")
        print("  STP: Wartsila Biokinetics 25 (25 m³/day)")
        return True

    except Exception as e:
        print(f"✗ Error inserting MT Aqua data: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def verify_installation():
    """Verify the installation was successful"""
    conn = sqlite3.connect(USERS_DB)
    cursor = conn.cursor()

    try:
        # Check table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vessel_details'")
        if not cursor.fetchone():
            print("✗ Table vessel_details not found")
            return False

        # Check MT Aqua data
        cursor.execute('SELECT vessel_name, me1_make, ae1_make, bwts_make FROM vessel_details WHERE vessel_id = 2')
        row = cursor.fetchone()

        if row:
            print("\n✓ Verification successful!")
            print(f"  Vessel: {row[0]}")
            print(f"  Main Engine: {row[1]}")
            print(f"  Aux Engine: {row[2]}")
            print(f"  BWTS: {row[3]}")
            return True
        else:
            print("✗ MT Aqua data not found")
            return False

    except Exception as e:
        print(f"✗ Verification error: {e}")
        return False
    finally:
        conn.close()


if __name__ == '__main__':
    print("=" * 60)
    print("Vessel Details Initialization Script")
    print("=" * 60)
    print()

    # Step 1: Create table
    print("[1/3] Creating vessel_details table...")
    if not init_vessel_details_table():
        print("\n✗ Failed to create table. Exiting.")
        exit(1)

    print()

    # Step 2: Insert MT Aqua data
    print("[2/3] Inserting MT Aqua dummy data...")
    if not insert_mt_aqua_data():
        print("\n✗ Failed to insert data. Exiting.")
        exit(1)

    print()

    # Step 3: Verify
    print("[3/3] Verifying installation...")
    if verify_installation():
        print()
        print("=" * 60)
        print("✓ Initialization complete!")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Test backend functions: python3 -c 'from vessel_details_models import *; print(get_vessel_details(2))'")
        print("2. Update app.py with vessel_details_models imports")
        print("3. Create admin_vessel_edit.html template")
    else:
        print("\n✗ Verification failed")
        exit(1)
