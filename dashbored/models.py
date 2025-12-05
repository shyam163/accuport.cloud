"""
Data models and queries for Accuport Dashboard
"""
from database import get_accubase_connection, get_users_connection, dict_from_row, list_from_rows
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
                AND sp.name LIKE '%Scavenge Drain%'
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
