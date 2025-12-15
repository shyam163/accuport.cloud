"""
Configuration Loader
Loads vessel configurations from SQLite database instead of YAML file
"""
import sqlite3
from typing import List, Dict, Optional
from pathlib import Path


class VesselConfig:
    """Vessel configuration data structure"""

    def __init__(self, config_dict: Dict):
        self.vessel_id = config_dict.get('vessel_id')
        self.vessel_name = config_dict.get('vessel_name')
        self.email = config_dict.get('email')
        self.auth_token = config_dict.get('auth_token')
        # sampling_points kept for compatibility but not used by sync
        self.sampling_points = config_dict.get('sampling_points', [])

    def __repr__(self):
        return f"<VesselConfig {self.vessel_id}: {self.vessel_name}>"


class ConfigLoader:
    """Load and manage vessel configurations from database"""

    def __init__(self, config_file: str = '../data/accubase.sqlite'):
        """
        Initialize config loader

        Args:
            config_file: Path to SQLite database file (changed from YAML)
                        For backward compatibility, accepts YAML path but will
                        look for accubase.sqlite in the same directory structure
        """
        # Handle both explicit database paths and YAML paths (for compatibility)
        if config_file.endswith('.yaml'):
            # Convert YAML path to database path
            # ../config/vessels_config.yaml -> ../data/accubase.sqlite
            config_path = Path(config_file)
            project_root = config_path.parent.parent
            self.db_path = project_root / 'data' / 'accubase.sqlite'
        else:
            self.db_path = Path(config_file)

        self.vessels: List[VesselConfig] = []
        self.load_config()

    def load_config(self):
        """Load configuration from SQLite database"""
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database file not found: {self.db_path}")

        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row  # Access columns by name
            cursor = conn.cursor()

            # Query all vessels with their configuration
            cursor.execute('''
                SELECT
                    vessel_id,
                    vessel_name,
                    email,
                    auth_token
                FROM vessels
                WHERE auth_token IS NOT NULL
                ORDER BY vessel_name
            ''')

            rows = cursor.fetchall()

            # Convert rows to VesselConfig objects
            for row in rows:
                vessel_dict = {
                    'vessel_id': row['vessel_id'],
                    'vessel_name': row['vessel_name'],
                    'email': row['email'] or 'Accu-Port@outlook.com',
                    'auth_token': row['auth_token'],
                    'sampling_points': []  # Not used, kept for compatibility
                }
                self.vessels.append(VesselConfig(vessel_dict))

            conn.close()

        except sqlite3.Error as e:
            raise Exception(f"Database error loading vessel configurations: {e}")

    def get_all_vessels(self) -> List[VesselConfig]:
        """Get all vessel configurations"""
        return self.vessels

    def get_vessel_by_id(self, vessel_id: str) -> VesselConfig:
        """
        Get a specific vessel configuration

        Args:
            vessel_id: Vessel identifier

        Returns:
            VesselConfig object

        Raises:
            ValueError: If vessel not found
        """
        for vessel in self.vessels:
            if vessel.vessel_id == vessel_id:
                return vessel

        raise ValueError(f"Vessel '{vessel_id}' not found in configuration")


# Sampling point mapping
# Maps sampling point codes to their full names and system types
SAMPLING_POINT_MAP = {
    'AB1': {'name': 'Auxiliary boiler 1', 'system': 'Boiler Water'},
    'AB2': {'name': 'Auxiliary boiler 2', 'system': 'Boiler Water'},
    'CB': {'name': 'Composite Boiler', 'system': 'Boiler Water'},
    'HW': {'name': 'Hotwell', 'system': 'Boiler Water'},
    'AE1': {'name': 'Auxiliary engine 1', 'system': 'Auxiliary Engine'},
    'AE2': {'name': 'Auxiliary engine 2', 'system': 'Auxiliary Engine'},
    'AE3': {'name': 'Auxiliary engine 3', 'system': 'Auxiliary Engine'},
    'ME': {'name': 'Main Engine 1', 'system': 'Main Engine'},
    'PW1': {'name': 'Potable water Galley', 'system': 'Potable Water'},
    'PW2': {'name': 'Potable Water acc', 'system': 'Potable Water'},
    'GW': {'name': 'Treated Sewage', 'system': 'Treated Sewage Water'},
    'SD1': {'name': 'Main engine Unit 1 Scavenge Drain', 'system': 'Scavenge Drain'},
    'SD2': {'name': 'Main engine Unit 2 Scavenge Drain', 'system': 'Scavenge Drain'},
    'SD3': {'name': 'Main engine Unit 3 Scavenge Drain', 'system': 'Scavenge Drain'},
    'SD4': {'name': 'Main engine Unit 4 Scavenge Drain', 'system': 'Scavenge Drain'},
    'SD5': {'name': 'Main engine Unit 5 Scavenge Drain', 'system': 'Scavenge Drain'},
    'SD6': {'name': 'Main engine Unit 6 Scavenge Drain', 'system': 'Scavenge Drain'},
}


if __name__ == "__main__":
    # Test config loader
    import sys
    db_path = sys.argv[1] if len(sys.argv) > 1 else '../data/accubase.sqlite'

    try:
        loader = ConfigLoader(db_path)
        print(f"Loaded {len(loader.vessels)} vessel(s) from database:\n")

        for vessel in loader.get_all_vessels():
            print(f"Vessel ID: {vessel.vessel_id}")
            print(f"Name: {vessel.vessel_name}")
            print(f"Email: {vessel.email}")
            print(f"Has Auth Token: {'Yes' if vessel.auth_token else 'No'}")
            print()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
