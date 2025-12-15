"""
Admin and Fleet Manager Models
Functions for user management, vessel creation, and assignments
"""
from database import get_users_connection, get_accubase_write_connection, dict_from_row, list_from_rows
import bcrypt
import secrets
from datetime import datetime

# ============================================================================
# USER MANAGEMENT
# ============================================================================

def hash_password(password):
    """Hash password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def create_user(username, password, full_name, email, role, created_by_user_id):
    """
    Create a new user account
    Args:
        username: Unique username
        password: Plain text password (will be hashed)
        full_name: Full name of user
        email: Email address
        role: 'vessel_manager' or 'fleet_manager' or 'admin'
        created_by_user_id: ID of admin/fleet manager creating this user
    Returns:
        dict with new user data or None if failed
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        
        try:
            password_hash = hash_password(password)
            cursor.execute('''
                INSERT INTO users (username, password_hash, full_name, email, role, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            ''', (username, password_hash, full_name, email, role))
            
            user_id = cursor.lastrowid
            
            # Log the action
            cursor.execute('''
                INSERT INTO admin_audit_log (admin_user_id, action_type, action_details, target_user_id)
                VALUES (?, ?, ?, ?)
            ''', (created_by_user_id, 'CREATE_USER', f'Created {role}: {username}', user_id))
            
            conn.commit()
            
            return {
                'id': user_id,
                'username': username,
                'full_name': full_name,
                'email': email,
                'role': role
            }
        except Exception as e:
            conn.rollback()
            print(f"Error creating user: {e}")
            return None

def get_all_users(role_filter=None):
    """
    Get all users, optionally filtered by role
    Args:
        role_filter: Optional role to filter by ('vessel_manager', 'fleet_manager', 'admin')
    Returns:
        list of user dicts
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        
        if role_filter:
            cursor.execute('''
                SELECT id, username, full_name, email, role, is_active, created_at
                FROM users
                WHERE role = ?
                ORDER BY full_name
            ''', (role_filter,))
        else:
            cursor.execute('''
                SELECT id, username, full_name, email, role, is_active, created_at
                FROM users
                ORDER BY role, full_name
            ''')
        
        return list_from_rows(cursor.fetchall())

def update_user_status(user_id, is_active, admin_user_id):
    """
    Activate or deactivate a user account
    Args:
        user_id: User ID to update
        is_active: 1 for active, 0 for inactive
        admin_user_id: ID of admin performing the action
    Returns:
        True if successful, False otherwise
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE users
                SET is_active = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (is_active, user_id))
            
            action = 'ACTIVATE_USER' if is_active else 'DEACTIVATE_USER'
            cursor.execute('''
                INSERT INTO admin_audit_log (admin_user_id, action_type, target_user_id)
                VALUES (?, ?, ?)
            ''', (admin_user_id, action, user_id))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error updating user status: {e}")
            return False

# ============================================================================
# VESSEL MANAGEMENT
# ============================================================================

def generate_auth_token():
    """Generate a secure random auth token for vessels"""
    return 'acc_' + secrets.token_urlsafe(32)

def create_vessel(vessel_id_code, vessel_name, email, created_by_user_id):
    """
    Create a new vessel in both accubase.sqlite and users.sqlite
    Args:
        vessel_id_code: Vessel identifier code (e.g., 'MV001')
        vessel_name: Human-readable vessel name
        email: Contact email for vessel
        created_by_user_id: ID of admin creating the vessel
    Returns:
        dict with vessel data including auth_token, or None if failed
    """
    auth_token = generate_auth_token()
    
    # Create vessel in accubase.sqlite
    try:
        with get_accubase_write_connection() as acc_conn:
            acc_cursor = acc_conn.cursor()
            acc_cursor.execute('''
                INSERT INTO vessels (vessel_id, vessel_name, email, created_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (vessel_id_code, vessel_name, email))
            
            vessel_db_id = acc_cursor.lastrowid
            acc_conn.commit()
    except Exception as e:
        print(f"Error creating vessel in accubase: {e}")
        return None
    
    # Store auth token in users.sqlite
    try:
        with get_users_connection() as users_conn:
            users_cursor = users_conn.cursor()
            users_cursor.execute('''
                INSERT INTO vessel_auth_tokens (vessel_id, auth_token, created_by, is_active)
                VALUES (?, ?, ?, 1)
            ''', (vessel_db_id, auth_token, created_by_user_id))
            
            # Log the action
            users_cursor.execute('''
                INSERT INTO admin_audit_log (admin_user_id, action_type, action_details, target_vessel_id)
                VALUES (?, ?, ?, ?)
            ''', (created_by_user_id, 'CREATE_VESSEL', f'Created vessel: {vessel_name} ({vessel_id_code})', vessel_db_id))
            
            users_conn.commit()
    except Exception as e:
        print(f"Error storing auth token: {e}")
        # Rollback vessel creation if token storage fails
        with get_accubase_write_connection() as acc_conn:
            acc_cursor = acc_conn.cursor()
            acc_cursor.execute('DELETE FROM vessels WHERE id = ?', (vessel_db_id,))
            acc_conn.commit()
        return None
    
    return {
        'id': vessel_db_id,
        'vessel_id': vessel_id_code,
        'vessel_name': vessel_name,
        'email': email,
        'auth_token': auth_token
    }

def get_all_vessels():
    """Get all vessels from accubase.sqlite"""
    from database import get_accubase_connection
    with get_accubase_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, vessel_id, vessel_name, email, created_at
            FROM vessels
            ORDER BY vessel_name
        ''')
        return list_from_rows(cursor.fetchall())

def get_vessel_auth_token(vessel_id):
    """
    Get auth token for a vessel
    Args:
        vessel_id: Vessel database ID
    Returns:
        Auth token string or None
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT auth_token
            FROM vessel_auth_tokens
            WHERE vessel_id = ? AND is_active = 1
        ''', (vessel_id,))
        row = cursor.fetchone()
        return row['auth_token'] if row else None

def get_all_vessels_with_tokens():
    """Get all vessels with their auth tokens"""
    vessels = get_all_vessels()
    
    with get_users_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT vessel_id, auth_token, created_at as token_created_at
            FROM vessel_auth_tokens
            WHERE is_active = 1
        ''')
        tokens = {row['vessel_id']: dict_from_row(row) for row in cursor.fetchall()}
    
    # Merge token info with vessel info
    for vessel in vessels:
        token_info = tokens.get(vessel['id'], {})
        vessel['auth_token'] = token_info.get('auth_token', 'N/A')
        vessel['token_created_at'] = token_info.get('token_created_at', None)
    
    return vessels

# ============================================================================
# VESSEL ASSIGNMENTS
# ============================================================================

def assign_vessel_to_user(user_id, vessel_id, assigned_by_user_id):
    """
    Assign a vessel to a user (vessel manager or fleet manager)
    Args:
        user_id: User ID to assign vessel to
        vessel_id: Vessel database ID
        assigned_by_user_id: ID of admin/fleet manager performing assignment
    Returns:
        True if successful, False otherwise
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO vessel_assignments (user_id, vessel_id)
                VALUES (?, ?)
            ''', (user_id, vessel_id))
            
            # Log the action
            cursor.execute('''
                INSERT INTO admin_audit_log (admin_user_id, action_type, target_user_id, target_vessel_id)
                VALUES (?, ?, ?, ?)
            ''', (assigned_by_user_id, 'ASSIGN_VESSEL', user_id, vessel_id))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error assigning vessel: {e}")
            return False

def unassign_vessel_from_user(user_id, vessel_id, unassigned_by_user_id):
    """
    Remove vessel assignment from a user
    Args:
        user_id: User ID to remove vessel from
        vessel_id: Vessel database ID
        unassigned_by_user_id: ID of admin/fleet manager performing unassignment
    Returns:
        True if successful, False otherwise
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM vessel_assignments
                WHERE user_id = ? AND vessel_id = ?
            ''', (user_id, vessel_id))
            
            # Log the action
            cursor.execute('''
                INSERT INTO admin_audit_log (admin_user_id, action_type, target_user_id, target_vessel_id)
                VALUES (?, ?, ?, ?)
            ''', (unassigned_by_user_id, 'UNASSIGN_VESSEL', user_id, vessel_id))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error unassigning vessel: {e}")
            return False

def get_user_vessel_assignments(user_id):
    """
    Get all vessel assignments for a user
    Args:
        user_id: User ID
    Returns:
        list of vessel dicts
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT vessel_id
            FROM vessel_assignments
            WHERE user_id = ?
        ''', (user_id,))
        vessel_ids = [row['vessel_id'] for row in cursor.fetchall()]
    
    if not vessel_ids:
        return []
    
    from models import get_vessels_by_ids
    return get_vessels_by_ids(vessel_ids)

# ============================================================================
# MANAGER HIERARCHY
# ============================================================================

def assign_vessel_manager_to_fleet_manager(fleet_manager_id, vessel_manager_id, assigned_by_user_id):
    """
    Assign a vessel manager to report to a fleet manager
    If the vessel manager is already assigned to another fleet manager, reassign them
    Args:
        fleet_manager_id: Fleet manager user ID
        vessel_manager_id: Vessel manager user ID
        assigned_by_user_id: ID of admin performing assignment
    Returns:
        True if successful, False otherwise
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()

        try:
            # Check if vessel manager is already assigned
            cursor.execute('''
                SELECT fleet_manager_id FROM manager_hierarchy
                WHERE vessel_manager_id = ?
            ''', (vessel_manager_id,))
            existing = cursor.fetchone()

            if existing:
                # Update existing assignment (reassignment)
                cursor.execute('''
                    UPDATE manager_hierarchy
                    SET fleet_manager_id = ?
                    WHERE vessel_manager_id = ?
                ''', (fleet_manager_id, vessel_manager_id))
                action_detail = f'Reassigned vessel manager {vessel_manager_id} from fleet manager {existing[0]} to fleet manager {fleet_manager_id}'
            else:
                # Create new assignment
                cursor.execute('''
                    INSERT INTO manager_hierarchy (fleet_manager_id, vessel_manager_id)
                    VALUES (?, ?)
                ''', (fleet_manager_id, vessel_manager_id))
                action_detail = f'Assigned vessel manager {vessel_manager_id} to fleet manager {fleet_manager_id}'

            # Log the action
            cursor.execute('''
                INSERT INTO admin_audit_log (admin_user_id, action_type, action_details, target_user_id)
                VALUES (?, ?, ?, ?)
            ''', (assigned_by_user_id, 'ASSIGN_HIERARCHY', action_detail, vessel_manager_id))

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error assigning manager hierarchy: {e}")
            return False

def unassign_vessel_manager_from_fleet_manager(fleet_manager_id, vessel_manager_id, unassigned_by_user_id):
    """
    Remove vessel manager from fleet manager
    Args:
        fleet_manager_id: Fleet manager user ID
        vessel_manager_id: Vessel manager user ID
        unassigned_by_user_id: ID of admin performing unassignment
    Returns:
        True if successful, False otherwise
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                DELETE FROM manager_hierarchy
                WHERE fleet_manager_id = ? AND vessel_manager_id = ?
            ''', (fleet_manager_id, vessel_manager_id))
            
            # Log the action
            cursor.execute('''
                INSERT INTO admin_audit_log (admin_user_id, action_type, target_user_id)
                VALUES (?, ?, ?)
            ''', (unassigned_by_user_id, 'UNASSIGN_HIERARCHY', vessel_manager_id))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"Error unassigning manager hierarchy: {e}")
            return False

def get_subordinate_vessel_managers(fleet_manager_id):
    """
    Get all vessel managers under a fleet manager
    Args:
        fleet_manager_id: Fleet manager user ID
    Returns:
        list of user dicts
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT u.id, u.username, u.full_name, u.email, u.role, u.is_active
            FROM users u
            JOIN manager_hierarchy mh ON u.id = mh.vessel_manager_id
            WHERE mh.fleet_manager_id = ?
            ORDER BY u.full_name
        ''', (fleet_manager_id,))
        return list_from_rows(cursor.fetchall())

def get_unassigned_vessel_managers():
    """
    Get all vessel managers (both assigned and unassigned)
    Shows current assignment status in the results
    Returns:
        list of user dicts with 'current_fleet_manager' field
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                u.id,
                u.username,
                u.full_name,
                u.email,
                u.role,
                u.is_active,
                fm.full_name as current_fleet_manager,
                mh.fleet_manager_id as current_fleet_manager_id
            FROM users u
            LEFT JOIN manager_hierarchy mh ON u.id = mh.vessel_manager_id
            LEFT JOIN users fm ON mh.fleet_manager_id = fm.id
            WHERE u.role = 'vessel_manager'
            AND u.is_active = 1
            ORDER BY u.full_name
        ''')
        return list_from_rows(cursor.fetchall())

# ============================================================================
# AUDIT LOG
# ============================================================================

def get_audit_log(limit=100, user_id=None, action_type=None):
    """
    Get audit log entries
    Args:
        limit: Maximum number of entries to return
        user_id: Optional filter by admin user ID
        action_type: Optional filter by action type
    Returns:
        list of audit log entry dicts
    """
    with get_users_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT al.*, u.username as admin_username, u.full_name as admin_name
            FROM admin_audit_log al
            JOIN users u ON al.admin_user_id = u.id
            WHERE 1=1
        '''
        params = []
        
        if user_id:
            query += ' AND al.admin_user_id = ?'
            params.append(user_id)
        
        if action_type:
            query += ' AND al.action_type = ?'
            params.append(action_type)
        
        query += ' ORDER BY al.created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        return list_from_rows(cursor.fetchall())
