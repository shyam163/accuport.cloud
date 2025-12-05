#!/usr/bin/env python3
"""
Fetch and show info specifically for MT Aqua
"""
import sys
import os
import logging
from datetime import datetime

# Ensure we can import from local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from labcom_client import LabcomClient
from config_loader import ConfigLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'  # Clean format for console output
)
logger = logging.getLogger("MTAquaFetcher")

def main():
    print(f"{ '='*60}")
    print(f"MT AQUA - DATA INSPECTOR")
    print(f"{ '='*60}\n")

    # 1. Load Configuration
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'vessels_config.yaml')
    
    if not os.path.exists(config_path):
        print(f"⚠ Config file not found at: {config_path}")
        print("\nPlease set up the configuration:")
        print("1. cp config/vessels_config.yaml.example config/vessels_config.yaml")
        print("2. Edit config/vessels_config.yaml and add 'mt_aqua' details.")
        return

    try:
        loader = ConfigLoader(config_path)
        
        # Try to find 'mt_aqua' or similar
        vessel = None
        target_id = 'mt_aqua'
        
        try:
            vessel = loader.get_vessel_by_id(target_id)
        except ValueError:
            # Fallback: search by name
            print(f"ℹ Vessel ID '{target_id}' not found directly. Searching by name 'Aqua'...")
            for v in loader.get_all_vessels():
                if 'aqua' in v.vessel_name.lower():
                    vessel = v
                    break
        
        if not vessel:
            print(f"❌ Could not find configuration for 'mt_aqua' or any vessel with 'Aqua' in the name.")
            print(f"\nAvailable vessels in config:")
            for v in loader.get_all_vessels():
                print(f" - {v.vessel_id} ({v.vessel_name})")
            return

        print(f"✓ Configuration loaded for: {vessel.vessel_name}")
        print(f"  ID: {vessel.vessel_id}")
        print(f"  Email: {vessel.email}")
        print(f"  Token: {vessel.auth_token[:6]}...{vessel.auth_token[-4:]}") 
        print("")

        # 2. Connect to Labcom
        print("Connecting to Labcom API...")
        client = LabcomClient(vessel.auth_token)
        
        cloud_account = client.get_cloud_account()
        if not cloud_account:
             print("❌ Failed to authenticate with Labcom. Check token.")
             return

        print(f"✓ Authenticated as: {cloud_account.get('name')} ({cloud_account.get('email')})")
        print(f"  Account ID: {cloud_account.get('id')}")
        print("")

        # 3. Fetch Sampling Points (Accounts)
        print("Fetching Sampling Points (Accounts)...")
        accounts = client.get_accounts()
        print(f"✓ Found {len(accounts)} sampling points:")
        
        for acc in accounts:
            print(f"  - [{acc.get('id')}] {acc.get('name')}")
            if acc.get('volume'):
                print(f"    Volume: {acc.get('volume')} {acc.get('volume_unit')}")
        print("")

        # 4. Fetch Recent Measurements
        print("Fetching Recent Measurements (Last 7 days)...")
        
        # Get measurements for all accounts
        measurements = client.get_all_measurements_for_vessel(
            from_date=datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=7)
        )
        
        if measurements:
            print(f"✓ Found {len(measurements)} measurements.")
            print("\nLatest 5 measurements:")
            
            # Sort by timestamp descending
            sorted_measurements = sorted(measurements, key=lambda x: x['timestamp'], reverse=True)
            
            for m in sorted_measurements[:5]:
                ts = datetime.fromtimestamp(m['timestamp']).strftime('%Y-%m-%d %H:%M')
                print(f"  [{ts}] {m.get('account')} - {m.get('parameter')}: {m.get('value')} {m.get('unit')}")
                if m.get('ideal_status'):
                     print(f"    Status: {m.get('ideal_status')}")
        else:
            print("ℹ No measurements found in the last 7 days.")

        print(f"\n{ '='*60}")
        print("DONE")
        print(f"{ '='*60}\n")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    from datetime import timedelta # Ensure this is available
    main()
