"""
Data models and queries for Accuport Dashboard
"""
from database import get_accubase_connection, get_accubase_write_connection, get_users_connection, dict_from_row, list_from_rows
from datetime import datetime, timedelta

# ============================================================================
# USER MANAGEMENT QUERIES (users.sqlite)
# ============================================================================

def get_user_by_username(username):
    """Get user by username"""
    with get_users_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, password_hash, full_name, email, role, is_active
            FROM users
            WHERE username = ? AND is_active = 1
        ''', (username,))
        return dict_from_row(cursor.fetchone())

def get_user_by_id(user_id):
    """Get user by ID"""
    with get_users_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, password_hash, full_name, email, role, is_active
            FROM users
            WHERE id = ? AND is_active = 1
        ''', (user_id,))
        return dict_from_row(cursor.fetchone())

def get_user_vessels(user_id, role):
    """
    Get all vessels a user can access based on their role
    - Vessel managers: only their assigned vessels
    - Fleet managers: vessels of all subordinate vessel managers
    - Admin: all vessels in the system
    """
    if role == 'admin':
        # Admin can access all vessels
        with get_accubase_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id FROM vessels')
            vessel_ids = [row['id'] for row in cursor.fetchall()]
        return vessel_ids

    with get_users_connection() as conn:
        cursor = conn.cursor()

        if role == 'vessel_manager' or role == 'vessel_user':
            # Get directly assigned vessels
            cursor.execute('''
                SELECT vessel_id
                FROM vessel_assignments
                WHERE user_id = ?
            ''', (user_id,))
            vessel_ids = [row['vessel_id'] for row in cursor.fetchall()]

        elif role == 'fleet_manager':
            # Get vessels from all subordinate vessel managers
            cursor.execute('''
                SELECT DISTINCT va.vessel_id
                FROM manager_hierarchy mh
                JOIN vessel_assignments va ON va.user_id = mh.vessel_manager_id
                WHERE mh.fleet_manager_id = ?
            ''', (user_id,))
            vessel_ids = [row['vessel_id'] for row in cursor.fetchall()]

            # Also include any vessels directly assigned to fleet manager
            cursor.execute('''
                SELECT vessel_id
                FROM vessel_assignments
                WHERE user_id = ?
            ''', (user_id,))
            direct_vessels = [row['vessel_id'] for row in cursor.fetchall()]
            vessel_ids.extend(direct_vessels)
            vessel_ids = list(set(vessel_ids))  # Remove duplicates

        else:
            vessel_ids = []

    return vessel_ids

# ============================================================================
# VESSEL DATA QUERIES (accubase.sqlite - READ ONLY)
# ============================================================================

def get_vessels_by_ids(vessel_ids):
    """Get vessel details for given vessel IDs"""
    if not vessel_ids:
        return []

    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(vessel_ids))
        cursor.execute(f'''
            SELECT id, vessel_id, vessel_name, email, created_at
            FROM vessels
            WHERE id IN ({placeholders})
            ORDER BY vessel_name
        ''', vessel_ids)
        return list_from_rows(cursor.fetchall())

def get_vessel_by_id(vessel_id):
    """Get single vessel by ID"""
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, vessel_id, vessel_name, email, created_at
            FROM vessels
            WHERE id = ?
        ''', (vessel_id,))
        return dict_from_row(cursor.fetchone())

def get_sampling_points_by_vessel(vessel_id):
    """Get all sampling points for a vessel"""
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, code, name, system_type, description, is_active
            FROM sampling_points
            WHERE vessel_id = ? AND is_active = 1
            ORDER BY code
        ''', (vessel_id,))
        return list_from_rows(cursor.fetchall())

def get_sampling_point_by_code(vessel_id, code):
    """Get specific sampling point by code"""
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, code, name, system_type, description
            FROM sampling_points
            WHERE vessel_id = ? AND code = ? AND is_active = 1
        ''', (vessel_id, code))
        return dict_from_row(cursor.fetchone())

def get_sampling_point_by_name_pattern(vessel_id, name_pattern):
    """
    Get sampling point by name pattern (vessel-agnostic)
    This allows finding equipment by name instead of hardcoded codes
    which vary between vessels
    """
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, code, name, system_type, description
            FROM sampling_points
            WHERE vessel_id = ? AND name LIKE ? AND is_active = 1
            LIMIT 1
        ''', (vessel_id, f'%{name_pattern}%'))
        return dict_from_row(cursor.fetchone())

def get_measurements_for_sampling_point(vessel_id, sampling_point_id, start_date=None, end_date=None):
    """
    Get measurements for a specific sampling point within date range
    Default: last 30 days
    """
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                m.id,
                m.measurement_date,
                m.value,
                m.value_numeric,
                m.unit,
                m.ideal_low,
                m.ideal_high,
                m.ideal_status,
                m.operator_name,
                m.comment,
                p.name as parameter_name,
                p.symbol as parameter_symbol
            FROM measurements m
            JOIN parameters p ON m.parameter_id = p.id
            WHERE m.vessel_id = ?
                AND m.sampling_point_id = ?
                AND m.measurement_date BETWEEN ? AND ?
                AND m.is_valid = 1
            ORDER BY m.measurement_date ASC, p.name
        ''', (vessel_id, sampling_point_id, start_date, end_date))
        return list_from_rows(cursor.fetchall())

def get_parameters():
    """Get all parameters"""
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, labcom_parameter_id, name, symbol, unit,
                   ideal_low, ideal_high, category, criticality
            FROM parameters
            ORDER BY name
        ''')
        return list_from_rows(cursor.fetchall())

def get_parameter_by_name(parameter_name):
    """Get parameter by name"""
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, labcom_parameter_id, name, symbol, unit,
                   ideal_low, ideal_high, category, criticality
            FROM parameters
            WHERE name LIKE ?
        ''', (f'%{parameter_name}%',))
        return dict_from_row(cursor.fetchone())

def get_measurements_by_parameter_names(vessel_id, sampling_point_code, parameter_names, start_date=None, end_date=None):
    """
    Get measurements for specific parameters at a sampling point
    Useful for getting multiple related parameters (e.g., all boiler water parameters)
    Uses LIKE pattern matching to handle parameter names with suffixes
    """
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    # Get sampling point ID
    sampling_point = get_sampling_point_by_code(vessel_id, sampling_point_code)
    if not sampling_point:
        return []

    with get_accubase_connection() as conn:
        cursor = conn.cursor()

        # Build LIKE conditions for fuzzy parameter matching
        # This handles cases like "Nitrite" matching "Nitrite (HR liq)"
        like_conditions = ' OR '.join(['p.name LIKE ?' for _ in parameter_names])

        query = f'''
            SELECT
                m.id,
                m.measurement_date,
                m.value,
                m.value_numeric,
                m.unit,
                m.ideal_low,
                m.ideal_high,
                m.ideal_status,
                m.operator_name,
                m.comment,
                p.name as parameter_name,
                p.symbol as parameter_symbol,
                sp.code as sampling_point_code,
                sp.name as sampling_point_name
            FROM measurements m
            JOIN parameters p ON m.parameter_id = p.id
            JOIN sampling_points sp ON m.sampling_point_id = sp.id
            WHERE m.vessel_id = ?
                AND sp.code = ?
                AND ({like_conditions})
                AND m.measurement_date BETWEEN ? AND ?
                AND m.is_valid = 1
            ORDER BY m.measurement_date ASC, p.name
        '''

        # Build parameters with % wildcards for LIKE matching
        like_params = [f'%{name}%' for name in parameter_names]
        params = [vessel_id, sampling_point_code] + like_params + [start_date, end_date]

        cursor.execute(query, params)
        return list_from_rows(cursor.fetchall())

def get_measurements_by_equipment_name(vessel_id, equipment_name_pattern, parameter_names, start_date=None, end_date=None):
    """
    Get measurements for specific parameters at an equipment (by name pattern)
    This is vessel-agnostic - works regardless of sampling point codes
    """
    # Find sampling point by name pattern
    sampling_point = get_sampling_point_by_name_pattern(vessel_id, equipment_name_pattern)
    if not sampling_point:
        return []

    # Use the existing function with the found code
    return get_measurements_by_parameter_names(
        vessel_id,
        sampling_point['code'],
        parameter_names,
        start_date,
        end_date
    )

def get_measurements_for_scavenge_drains(vessel_id, parameter_names, start_date=None, end_date=None):
    """
    Get measurements for scavenge drain units (SD1, SD2, SD3, etc.)
    Aggregates data from all SD sampling points for the vessel
    """
    if end_date is None:
        end_date = datetime.now()
    if start_date is None:
        start_date = end_date - timedelta(days=30)

    with get_accubase_connection() as conn:
        cursor = conn.cursor()

        # Build LIKE conditions for fuzzy parameter matching
        like_conditions = ' OR '.join(['p.name LIKE ?' for _ in parameter_names])

        query = f'''
            SELECT
                m.id,
                m.measurement_date,
                m.value,
                m.value_numeric,
                m.unit,
                m.ideal_low,
                m.ideal_high,
                m.ideal_status,
                m.operator_name,
                m.comment,
                p.name as parameter_name,
                p.symbol as parameter_symbol,
                sp.code as sampling_point_code,
                sp.name as sampling_point_name
            FROM measurements m
            JOIN parameters p ON m.parameter_id = p.id
            JOIN sampling_points sp ON m.sampling_point_id = sp.id
            WHERE m.vessel_id = ?
                AND (sp.name LIKE '%Scavenge Drain%' OR sp.name LIKE '%SD0%' OR sp.name LIKE '%Fresh%Oil%')
                AND ({like_conditions})
                AND m.measurement_date BETWEEN ? AND ?
                AND m.is_valid = 1
            ORDER BY m.measurement_date ASC, sp.name, p.name
        '''

        # Build parameters with % wildcards for LIKE matching
        like_params = [f'%{name}%' for name in parameter_names]
        params = [vessel_id] + like_params + [start_date, end_date]

        cursor.execute(query, params)
        return list_from_rows(cursor.fetchall())



def get_scavenge_drain_data_date_range(vessel_id):
    """
    Get the earliest and latest measurement dates for scavenge drain data
    Returns dict with 'earliest' and 'latest' datetime objects, or None if no data
    """
    with get_accubase_connection() as conn:
        cursor = conn.cursor()

        query = '''
            SELECT
                MIN(m.measurement_date) as earliest,
                MAX(m.measurement_date) as latest
            FROM measurements m
            JOIN sampling_points sp ON m.sampling_point_id = sp.id
            WHERE m.vessel_id = ?
                AND (sp.name LIKE '%Scavenge Drain%' OR sp.name LIKE '%SD0%' OR sp.name LIKE '%Fresh%Oil%')
                AND m.is_valid = 1
        '''

        cursor.execute(query, (vessel_id,))
        row = cursor.fetchone()

        if row and row[0] and row[1]:
            # Convert string dates to datetime objects for template formatting
            earliest_str = row[0]
            latest_str = row[1]

            # Try parsing with microseconds first, then without
            try:
                earliest = datetime.strptime(earliest_str, '%Y-%m-%d %H:%M:%S.%f')
            except:
                earliest = datetime.strptime(earliest_str, '%Y-%m-%d %H:%M:%S')

            try:
                latest = datetime.strptime(latest_str, '%Y-%m-%d %H:%M:%S.%f')
            except:
                latest = datetime.strptime(latest_str, '%Y-%m-%d %H:%M:%S')

            return {
                'earliest': earliest,
                'latest': latest
            }
        return None

def get_latest_measurements_summary(vessel_id):
    """Get latest measurement for each parameter across all sampling points"""
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                sp.name as sampling_point_name,
                sp.code as sampling_point_code,
                p.name as parameter_name,
                m.value,
                m.value_numeric,
                m.unit,
                m.ideal_status,
                m.measurement_date,
                MAX(m.measurement_date) as latest_date
            FROM measurements m
            JOIN parameters p ON m.parameter_id = p.id
            JOIN sampling_points sp ON m.sampling_point_id = sp.id
            WHERE m.vessel_id = ?
                AND m.is_valid = 1
            GROUP BY sp.id, p.id
            ORDER BY sp.code, p.name
        ''', (vessel_id,))
        return list_from_rows(cursor.fetchall())

def get_alerts_for_vessel(vessel_id, unresolved_only=True):
    """Get alerts for a vessel"""
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        query = '''
            SELECT
                a.id,
                a.alert_type,
                a.alert_reason,
                a.measured_value,
                a.expected_low,
                a.expected_high,
                a.alert_date,
                a.acknowledged_at,
                a.resolved_at,
                p.name as parameter_name,
                sp.name as sampling_point_name
            FROM alerts a
            JOIN parameters p ON a.parameter_id = p.id
            LEFT JOIN sampling_points sp ON a.sampling_point_id = sp.id
            WHERE a.vessel_id = ?
        '''

        if unresolved_only:
            query += ' AND a.resolved_at IS NULL'

        query += ' ORDER BY a.alert_date DESC LIMIT 100'

        cursor.execute(query, (vessel_id,))
        return list_from_rows(cursor.fetchall())

def get_all_measurements_for_troubleshooting(vessel_id, limit=500):
    """
    TEMPORARY TROUBLESHOOTING FUNCTION
    Get all measurements for a vessel with full details
    """
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                m.id,
                m.measurement_date,
                m.value,
                m.value_numeric,
                m.unit,
                m.ideal_low,
                m.ideal_high,
                m.ideal_status,
                m.operator_name,
                m.comment,
                p.name as parameter_name,
                p.symbol as parameter_symbol,
                p.category as parameter_category,
                sp.code as sampling_point_code,
                sp.name as sampling_point_name,
                sp.system_type
            FROM measurements m
            JOIN parameters p ON m.parameter_id = p.id
            JOIN sampling_points sp ON m.sampling_point_id = sp.id
            WHERE m.vessel_id = ?
                AND m.is_valid = 1
            ORDER BY m.measurement_date DESC, sp.code, p.name
            LIMIT ?
        ''', (vessel_id, limit))
        return list_from_rows(cursor.fetchall())

def get_all_sampling_points_for_troubleshooting(vessel_id):
    """
    TEMPORARY TROUBLESHOOTING FUNCTION
    Get all sampling points for a vessel
    """
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                id,
                code,
                name,
                system_type,
                description,
                is_active
            FROM sampling_points
            WHERE vessel_id = ?
            ORDER BY code
        ''', (vessel_id,))
        return list_from_rows(cursor.fetchall())

def get_all_parameters_for_troubleshooting():
    """
    TEMPORARY TROUBLESHOOTING FUNCTION
    Get all parameters in the system
    """
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                id,
                labcom_parameter_id,
                name,
                symbol,
                unit,
                ideal_low,
                ideal_high,
                category,
                criticality
            FROM parameters
            ORDER BY category, name
        ''')
        return list_from_rows(cursor.fetchall())

# ============================================================================
# PARAMETER LIMITS QUERIES (users.sqlite)
# ============================================================================

def get_parameter_limits(equipment_type, parameter_name):
    """
    Get limits for a specific equipment type and parameter

    Args:
        equipment_type: Equipment type string (e.g., 'AUX BOILER & EGE', 'HOTWELL')
        parameter_name: Parameter name (e.g., 'PH', 'PHOSPHATE')

    Returns:
        dict with 'lower_limit' and 'upper_limit' keys, or None if not found
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()

        # Normalize inputs to uppercase for case-insensitive matching
        equipment_type = equipment_type.upper()
        parameter_name = parameter_name.upper()

        cursor.execute('''
            SELECT lower_limit, upper_limit
            FROM parameter_limits
            WHERE equipment_type = ? AND parameter_name = ?
        ''', (equipment_type, parameter_name))

        row = cursor.fetchone()

        if row:
            return {
                'lower_limit': row[0],
                'upper_limit': row[1]
            }
        return None

def get_all_limits_for_equipment(equipment_type):
    """
    Get all parameter limits for an equipment type

    Args:
        equipment_type: Equipment type string (e.g., 'AUX BOILER & EGE', 'HOTWELL')

    Returns:
        dict mapping parameter_name -> {'lower_limit': x, 'upper_limit': y}
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()

        cursor.execute('''
            SELECT parameter_name, lower_limit, upper_limit
            FROM parameter_limits
            WHERE equipment_type = ?
        ''', (equipment_type.upper(),))

        limits_dict = {}
        for row in cursor.fetchall():
            limits_dict[row[0]] = {
                'lower_limit': row[1],
                'upper_limit': row[2]
            }

        return limits_dict


def recalculate_alerts_for_vessel(vessel_id):
    """
    Recalculate alerts for a vessel using parameter_limits from users.sqlite
    instead of old LabCom ideal_low/ideal_high values.
    
    Returns dict with counts of alerts created/resolved/checked.
    """
    import sqlite3
    from datetime import datetime
    
    # Get parameter limits from users.sqlite
    with get_users_connection() as users_conn:
        users_cursor = users_conn.cursor()
        users_cursor.execute('''
            SELECT equipment_type, parameter_name, lower_limit, upper_limit
            FROM parameter_limits
        ''')
        
        # Build limits lookup: {EQUIPMENT_TYPE: {PARAMETER_NAME: {lower, upper}}}
        limits_by_equipment = {}
        for row in users_cursor.fetchall():
            equipment_type, param_name, lower, upper = row
            if equipment_type not in limits_by_equipment:
                limits_by_equipment[equipment_type] = {}
            limits_by_equipment[equipment_type][param_name] = {
                'lower': lower,
                'upper': upper
            }
    
    # Equipment type mapping based on sampling point names
    def get_equipment_type(sampling_point_name):
        """Map sampling point name to equipment type for limits lookup"""
        sp_upper = sampling_point_name.upper()
        
        if 'HOTWELL' in sp_upper or 'HOT WELL' in sp_upper:
            return 'HOTWELL'
        elif any(x in sp_upper for x in ['AUX BOILER', 'AB1', 'AB2', 'EGE', 'COMPOSITE BOILER', 'CB ']):
            return 'AUX BOILER & EGE'
        elif 'COOLING' in sp_upper or 'HT' in sp_upper or 'LT' in sp_upper:
            return 'HT & LT COOLING WATER'
        elif 'POTABLE' in sp_upper or 'DRINKING' in sp_upper:
            return 'POTABLE WATER'
        elif 'SEWAGE' in sp_upper or 'GREY' in sp_upper or 'GRAY' in sp_upper:
            return 'SEWAGE'
        
        return None
    
    # Parameter name normalization (strip LabCom suffixes)
    def normalize_parameter_name(param_name):
        """Normalize parameter name by removing LabCom test method suffixes"""
        normalized = param_name.upper()
        
        # Remove common suffixes
        normalized = (normalized
                     .replace(' (LIQ)', '').replace(' (EL.)', '')
                     .replace(' (HR TAB)', '').replace(' (HR TAB).', '')
                     .replace(' (LR)', '').replace(' (HR)', '').replace(' (POW)', '')
                     .replace('. ORTHO', '').replace(' [LIQ]', ''))
        
        # Handle specific variations
        if normalized.startswith('PH-') or normalized.startswith('PH ('):
            normalized = 'PH'
        elif 'HARDN' in normalized and 'TOTAL' in normalized:
            normalized = 'TOTAL HARDNESS'
        elif normalized == 'TDS':
            normalized = 'TOTAL DISSOLVED SOLIDS'
        elif 'TURBIDITY' in normalized:
            normalized = 'TURBIDITY'
        elif 'SULPHATE' in normalized:
            normalized = 'SULPHATE (SO₄)'
        elif 'SUSPENDED SOLIDS' in normalized:
            normalized = 'TOTAL SUSPENDED SOLIDS'
        elif normalized.startswith('ALKALINITY M'):
            normalized = 'ALKALINITY M'
        elif normalized.startswith('ALKALINITY P'):
            normalized = 'ALKALINITY P'
        elif 'CHLORINE FREE' in normalized:
            normalized = 'FREE CHLORINE'
        elif 'CHLORINE TOTAL' in normalized:
            normalized = 'TOTAL CHLORINE'
        elif 'CHLORINE COMBINED' in normalized:
            normalized = 'COMBINED CHLORINE'
        elif 'IRON' in normalized:
            normalized = 'IRON (FE)'
        elif 'NICKEL' in normalized:
            normalized = 'NICKEL (NI)'
        elif 'ZINC' in normalized:
            normalized = 'ZINC (ZN)'
        elif 'COPPER' in normalized:
            normalized = 'COPPER (CU)'
        elif 'CHLORIDE' in normalized:
            normalized = 'CHLORIDE'
        elif 'PHOSPHATE' in normalized:
            normalized = 'PHOSPHATE'
        elif 'DEHA' in normalized:
            normalized = 'DEHA'
        elif 'HYDRAZINE' in normalized:
            normalized = 'HYDRAZINE'
        elif 'NITRITE' in normalized:
            normalized = 'NITRITE'
        elif normalized == 'COD' or 'COD' in normalized:
            normalized = 'COD'
        elif normalized == 'BOD' or 'BOD' in normalized:
            normalized = 'BOD'
        
        return normalized.strip()
    
    # Get recent measurements for this vessel
    with get_accubase_write_connection() as conn:
        cursor = conn.cursor()
        
        # Get measurements from last 90 days
        cursor.execute('''
            SELECT
                m.id as measurement_id,
                m.value_numeric,
                m.measurement_date,
                p.id as parameter_id,
                p.name as parameter_name,
                sp.id as sampling_point_id,
                sp.name as sampling_point_name
            FROM measurements m
            JOIN parameters p ON m.parameter_id = p.id
            JOIN sampling_points sp ON m.sampling_point_id = sp.id
            WHERE sp.vessel_id = ?
              AND m.measurement_date >= date('now', '-90 days')
              AND m.value_numeric IS NOT NULL
            ORDER BY m.measurement_date DESC
        ''', (vessel_id,))
        
        measurements = cursor.fetchall()
        alerts_created = 0
        alerts_resolved = 0
        
        for m in measurements:
            measurement_id, value, meas_date, param_id, param_name, sp_id, sp_name = m
            
            # Get equipment type and normalized parameter name
            equipment_type = get_equipment_type(sp_name)
            if not equipment_type or equipment_type not in limits_by_equipment:
                continue
            
            normalized_param = normalize_parameter_name(param_name)
            if normalized_param not in limits_by_equipment[equipment_type]:
                continue
            
            # Get limits for this parameter
            limits = limits_by_equipment[equipment_type][normalized_param]
            lower_limit = limits['lower']
            upper_limit = limits['upper']
            
            # Check if value is out of range
            is_out_of_range = value < lower_limit or value > upper_limit
            
            # Check for existing alert
            cursor.execute('''
                SELECT id, resolved_at
                FROM alerts
                WHERE measurement_id = ? AND vessel_id = ?
            ''', (measurement_id, vessel_id))
            existing_alert = cursor.fetchone()
            
            if is_out_of_range:
                # Value is out of range - should have an alert
                if not existing_alert or existing_alert[1]:  # No alert or resolved
                    # Create new alert
                    alert_type = 'critical' if (value < lower_limit * 0.5 or value > upper_limit * 1.5) else 'warning'
                    alert_reason = f'Value {value} outside range {lower_limit}-{upper_limit}'
                    
                    cursor.execute('''
                        INSERT INTO alerts (
                            measurement_id, vessel_id, sampling_point_id, parameter_id,
                            alert_type, alert_reason, measured_value,
                            expected_low, expected_high, alert_date, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        measurement_id, vessel_id, sp_id, param_id,
                        alert_type, alert_reason, value,
                        lower_limit, upper_limit, meas_date, datetime.now()
                    ))
                    alerts_created += 1
            else:
                # Value is in range - should NOT have an unresolved alert
                if existing_alert and not existing_alert[1]:  # Has unresolved alert
                    # Resolve the alert
                    cursor.execute('''
                        UPDATE alerts
                        SET resolved_at = ?, resolution_notes = ?
                        WHERE id = ?
                    ''', (
                        datetime.now(),
                        'Auto-resolved: value within new parameter limits',
                        existing_alert[0]
                    ))
                    alerts_resolved += 1
        
        conn.commit()
    
    return {
        'alerts_created': alerts_created,
        'alerts_resolved': alerts_resolved,
        'measurements_checked': len(measurements)
    }
