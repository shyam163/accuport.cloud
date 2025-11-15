"""
Configuration Loader
Loads vessel configurations from YAML file
"""
import yaml
from typing import List, Dict
from pathlib import Path


class VesselConfig:
    """Vessel configuration data structure"""

    def __init__(self, config_dict: Dict):
        self.vessel_id = config_dict.get('vessel_id')
        self.vessel_name = config_dict.get('vessel_name')
        self.email = config_dict.get('email')
        self.auth_token = config_dict.get('auth_token')
        self.sampling_points = config_dict.get('sampling_points', [])

    def __repr__(self):
        return f"<VesselConfig {self.vessel_id}: {self.vessel_name}>"


class ConfigLoader:
    """Load and manage vessel configurations"""

    def __init__(self, config_file: str = '../config/vessels_config.yaml'):
        """
        Initialize config loader

        Args:
            config_file: Path to YAML configuration file
        """
        self.config_file = config_file
        self.vessels: List[VesselConfig] = []
        self.load_config()

    def load_config(self):
        """Load configuration from YAML file"""
        config_path = Path(self.config_file)

        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_file}")

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        vessels_data = config_data.get('vessels', [])
        self.vessels = [VesselConfig(v) for v in vessels_data]

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
    loader = ConfigLoader()

    print(f"Loaded {len(loader.vessels)} vessel(s):\n")

    for vessel in loader.get_all_vessels():
        print(f"Vessel ID: {vessel.vessel_id}")
        print(f"Name: {vessel.vessel_name}")
        print(f"Email: {vessel.email}")
        print(f"Sampling Points: {', '.join(vessel.sampling_points)}")
        print()
