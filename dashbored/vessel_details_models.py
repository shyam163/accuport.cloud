"""
Vessel Details Models
Database operations for vessel equipment specifications
"""
import sqlite3
from typing import Optional, Dict, Any
from datetime import datetime
from database import get_users_connection


def get_vessel_details(vessel_id: int) -> Optional[Dict[str, Any]]:
    """
    Retrieve all vessel details by vessel_id

    Args:
        vessel_id: ID of vessel to retrieve

    Returns:
        Dict with all vessel details or None if not found
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM vessel_details WHERE vessel_id = ?', (vessel_id,))
        row = cursor.fetchone()

        if not row:
            return None

        # Convert row to dict
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))


def update_vessel_details(vessel_id: int, details: Dict[str, Any], user_id: int) -> bool:
    """
    Upsert vessel details (INSERT if new, UPDATE if exists)

    Args:
        vessel_id: ID of vessel to update
        details: Dict of field_name: value pairs
        user_id: ID of user making the update

    Returns:
        True on success, False on failure
    """
    try:
        with get_users_connection() as conn:
            cursor = conn.cursor()

            # Check if record exists
            cursor.execute('SELECT id FROM vessel_details WHERE vessel_id = ?', (vessel_id,))
            existing = cursor.fetchone()

            # Add metadata
            details['vessel_id'] = vessel_id
            details['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            details['updated_by_user_id'] = user_id

            if existing:
                # UPDATE existing record
                set_clause = ', '.join([f'{k} = ?' for k in details.keys() if k != 'vessel_id'])
                values = [v for k, v in details.items() if k != 'vessel_id']
                values.append(vessel_id)

                sql = f'UPDATE vessel_details SET {set_clause} WHERE vessel_id = ?'
                cursor.execute(sql, values)
            else:
                # INSERT new record
                details['created_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

                fields = ', '.join(details.keys())
                placeholders = ', '.join(['?'] * len(details))
                values = list(details.values())

                sql = f'INSERT INTO vessel_details ({fields}) VALUES ({placeholders})'
                cursor.execute(sql, values)

            conn.commit()
            return True
    except Exception as e:
        print(f"Error updating vessel details: {e}")
        return False


def get_vessel_details_for_display(vessel_id: int, equipment_filter: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    """
    Get formatted vessel specifications for equipment page display
    Filters out empty/NULL fields and optionally filters by equipment type

    Args:
        vessel_id: ID of vessel to retrieve
        equipment_filter: 'main_engines', 'aux_engines', 'boiler', 'water_systems', or None for all

    Returns:
        Nested dict: {category: {field_label: field_value}}
        Only non-empty fields are included
    """
    details = get_vessel_details(vessel_id)
    if not details:
        return {}

    # Define field mappings: database_field -> (category, display_label)
    field_mappings = {
        # Vessel Info
        'vessel_name': ('vessel_info', 'Vessel Name'),
        'vessel_type': ('vessel_info', 'Vessel Type'),
        'year_of_build': ('vessel_info', 'Year of Build'),
        'imo_number': ('vessel_info', 'IMO Number'),
        'company_name': ('vessel_info', 'Company Name'),

        # Main Engine 1
        'me1_make': ('main_engines', 'ME1 - Make'),
        'me1_model': ('main_engines', 'ME1 - Model'),
        'me1_serial': ('main_engines', 'ME1 - Serial'),
        'me1_system_oil': ('main_engines', 'ME1 - System Oil'),
        'me1_cylinder_oil': ('main_engines', 'ME1 - Cylinder Oil'),
        'me1_fuel1': ('main_engines', 'ME1 - Fuel 1'),
        'me1_fuel2': ('main_engines', 'ME1 - Fuel 2'),

        # Main Engine 2
        'me2_make': ('main_engines', 'ME2 - Make'),
        'me2_model': ('main_engines', 'ME2 - Model'),
        'me2_serial': ('main_engines', 'ME2 - Serial'),
        'me2_system_oil': ('main_engines', 'ME2 - System Oil'),
        'me2_cylinder_oil': ('main_engines', 'ME2 - Cylinder Oil'),
        'me2_fuel1': ('main_engines', 'ME2 - Fuel 1'),
        'me2_fuel2': ('main_engines', 'ME2 - Fuel 2'),

        # Aux Engines Shared
        'ae_system_oil': ('aux_engines', 'AE - System Oil'),
        'ae_fuel1': ('aux_engines', 'AE - Fuel 1'),
        'ae_fuel2': ('aux_engines', 'AE - Fuel 2'),

        # AE 1
        'ae1_make': ('aux_engines', 'AE1 - Make'),
        'ae1_model': ('aux_engines', 'AE1 - Model'),
        'ae1_serial': ('aux_engines', 'AE1 - Serial'),

        # AE 2
        'ae2_make': ('aux_engines', 'AE2 - Make'),
        'ae2_model': ('aux_engines', 'AE2 - Model'),
        'ae2_serial': ('aux_engines', 'AE2 - Serial'),

        # AE 3
        'ae3_make': ('aux_engines', 'AE3 - Make'),
        'ae3_model': ('aux_engines', 'AE3 - Model'),
        'ae3_serial': ('aux_engines', 'AE3 - Serial'),

        # Boiler Shared
        'boiler_system_oil': ('boiler', 'Boiler - System Oil'),
        'boiler_fuel1': ('boiler', 'Boiler - Fuel 1'),
        'boiler_fuel2': ('boiler', 'Boiler - Fuel 2'),

        # Aux Boiler 1
        'ab1_make': ('boiler', 'Aux Boiler 1 - Make'),
        'ab1_model': ('boiler', 'Aux Boiler 1 - Model'),
        'ab1_serial': ('boiler', 'Aux Boiler 1 - Serial'),

        # Aux Boiler 2
        'ab2_make': ('boiler', 'Aux Boiler 2 - Make'),
        'ab2_model': ('boiler', 'Aux Boiler 2 - Model'),
        'ab2_serial': ('boiler', 'Aux Boiler 2 - Serial'),

        # EGE
        'ege_make': ('boiler', 'EGE - Make'),
        'ege_model': ('boiler', 'EGE - Model'),
        'ege_serial': ('boiler', 'EGE - Serial'),

        # Water Treatment
        # Hotwell
        'hotwell_deha': ('boiler', 'Hotwell DEHA'),
        'hotwell_hydrazine': ('boiler', 'Hotwell Hydrazine'),

        'bwt_chemical_manufacturer': ('boiler', 'Boiler WT - Manufacturer'),
        'bwt_chemicals_in_use': ('boiler', 'Boiler WT - Chemicals'),
        'cwt_chemical_manufacturer': ('boiler', 'Cooling WT - Manufacturer'),
        'cwt_chemicals_in_use': ('boiler', 'Cooling WT - Chemicals'),

        # BWTS
        'bwts_make': ('water_systems', 'BWTS - Make'),
        'bwts_model': ('water_systems', 'BWTS - Model'),
        'bwts_serial': ('water_systems', 'BWTS - Serial'),

        # EGCS
        'egcs_make': ('water_systems', 'EGCS - Make'),
        'egcs_model': ('water_systems', 'EGCS - Model'),
        'egcs_serial': ('water_systems', 'EGCS - Serial'),
        'egcs_type': ('water_systems', 'EGCS - Type'),

        # STP
        'stp_make': ('water_systems', 'STP - Make'),
        'stp_model': ('water_systems', 'STP - Model'),
        'stp_serial': ('water_systems', 'STP - Serial'),
        'stp_capacity': ('water_systems', 'STP - Capacity'),
    }

    # Build result dict
    result = {}
    for db_field, (category, display_label) in field_mappings.items():
        # Filter by equipment type if specified
        if equipment_filter and category != equipment_filter:
            continue

        # Get value from details
        value = details.get(db_field)

        # Skip empty/NULL values
        if not value:
            continue

        # Add to result
        if category not in result:
            result[category] = {}
        result[category][display_label] = str(value)

    return result
