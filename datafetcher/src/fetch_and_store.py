#!/usr/bin/env python3
"""
Fetch data from Labcom and store in enhanced SQLite database
Uses the Phase 1 enhanced schema with quality control fields and alerts
"""
import sys
from datetime import datetime, timedelta
from labcom_client import LabcomClient
from config_loader import ConfigLoader
from data_manager import DataManager

def fetch_and_store_vessel_data(vessel_id: str, days_back: int = 30):
    """
    Fetch data for a vessel and store in enhanced database

    Args:
        vessel_id: Vessel identifier from config
        days_back: Number of days of historical data
    """
    print(f"{'='*70}")
    print(f"Fetching and storing data for {vessel_id}")
    print(f"{'='*70}\n")

    # Load config
    config_loader = ConfigLoader('../config/vessels_config.yaml')
    vessel_config = config_loader.get_vessel_by_id(vessel_id)

    # Initialize client and data manager
    client = LabcomClient(vessel_config.auth_token)
    dm = DataManager()

    # 1. Connect and get cloud account
    print("1. Connecting to Labcom...")
    cloud_account = client.get_cloud_account()
    print(f"   ✓ Connected as: {cloud_account.get('name')} ({cloud_account.get('email')})\n")

    # 2. Add/update vessel in database
    print("2. Updating vessel in database...")
    vessel_db_id = dm.add_or_update_vessel(
        vessel_id=vessel_config.vessel_id,
        vessel_name=vessel_config.vessel_name,
        email=vessel_config.email,
        auth_token=vessel_config.auth_token,
        labcom_account_id=cloud_account.get('id')
    )
    print(f"   ✓ Vessel database ID: {vessel_db_id}\n")

    # 3. Sync sampling points
    print("3. Syncing sampling points...")
    accounts = client.get_accounts()
    print(f"   Found {len(accounts)} sampling points in Labcom")

    for account in accounts:
        dm.add_sampling_point(
            vessel_id=vessel_db_id,
            code=f"LAB{account['id']}",
            name=account.get('name', 'Unknown'),
            labcom_account_id=account['id']
        )
    print(f"   ✓ Synced {len(accounts)} sampling points\n")

    # 4. Fetch measurements
    print(f"4. Fetching measurements (last {days_back} days)...")
    from_date = datetime.now() - timedelta(days=days_back)
    to_date = datetime.now()

    measurements = client.get_all_measurements_for_vessel(
        from_date=from_date,
        to_date=to_date
    )
    print(f"   ✓ Fetched {len(measurements)} measurements from Labcom\n")

    # 5. Store measurements with enhanced fields
    print("5. Storing measurements in database...")
    stats = dm.store_measurements(
        vessel_id=vessel_db_id,
        measurements=measurements
    )

    print(f"   ✓ Stored {stats['new']} new measurements")
    print(f"   ⚠ Skipped {stats['duplicate']} duplicates")
    print(f"   🚨 Created {stats['alerts']} alerts for out-of-range values\n")

    # 6. Create fetch log
    print("6. Creating fetch log...")
    dm.create_fetch_log(
        vessel_id=vessel_db_id,
        status='success',
        measurements_fetched=len(measurements),
        measurements_new=stats['new'],
        measurements_duplicate=stats['duplicate'],
        date_range_from=from_date,
        date_range_to=to_date
    )
    print(f"   ✓ Fetch log created\n")

    # Summary
    print(f"{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Vessel: {vessel_config.vessel_name}")
    print(f"Sampling Points: {len(accounts)}")
    print(f"Measurements Fetched: {len(measurements)}")
    print(f"New Measurements Stored: {stats['new']}")
    print(f"Duplicates Skipped: {stats['duplicate']}")
    print(f"Alerts Generated: {stats['alerts']}")
    print(f"Database: data/accubase.sqlite")
    print(f"{'='*70}\n")

    return stats


if __name__ == "__main__":
    vessel_id = sys.argv[1] if len(sys.argv) > 1 else "mv_october"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    try:
        fetch_and_store_vessel_data(vessel_id, days_back=days)
        print("✓ SUCCESS: Data fetch and storage completed!")
    except Exception as e:
        print(f"✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
