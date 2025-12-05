"""
Authentication management for Accuport Dashboard
Uses Flask-Login for session management
"""
import bcrypt
from flask_login import UserMixin
from models import get_user_by_username, get_user_by_id, get_user_vessels

class User(UserMixin):
    """User class for Flask-Login"""

    def __init__(self, user_data):
        self.id = user_data['id']
        self.username = user_data['username']
        self.full_name = user_data['full_name']
        self.email = user_data['email']
        self.role = user_data['role']
        self._is_active = user_data.get('is_active', 1)

    @property
    def is_active(self):
        """Override UserMixin's is_active property"""
        return bool(self._is_active)

    def get_id(self):
        """Return user ID as string (required by Flask-Login)"""
        return str(self.id)

    def get_accessible_vessels(self):
        """Get list of vessel IDs this user can access"""
        return get_user_vessels(self.id, self.role)

    def is_fleet_manager(self):
        """Check if user is a fleet manager"""
        return self.role == 'fleet_manager'

    def is_vessel_manager(self):
        """Check if user is a vessel manager"""
        return self.role == 'vessel_manager'

    def is_admin(self):
        """Check if user is an admin"""
        return self.role == 'admin'

    def is_vessel_user(self):
        """Check if user is a vessel-specific user"""
        return self.role == 'vessel_user'

    def can_access_vessel(self, vessel_id):
        """Check if user can access a specific vessel"""
        return vessel_id in self.get_accessible_vessels()

def verify_password(plain_password, hashed_password):
    """Verify a password against its hash"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def authenticate_user(username, password):
    """
    Authenticate user with username and password
    Returns User object if successful, None otherwise
    """
    user_data = get_user_by_username(username)

    if not user_data:
        return None

    if not verify_password(password, user_data['password_hash']):
        return None

    return User(user_data)

def load_user(user_id):
    """
    Load user by ID (required by Flask-Login)
    Returns User object or None
    """
    user_data = get_user_by_id(int(user_id))

    if not user_data:
        return None

    return User(user_data)
