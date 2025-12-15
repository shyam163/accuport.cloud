#!/usr/bin/env python3
"""
Fetch data from Labcom and store in enhanced SQLite database.
Improved version with argparse, logging, and robust path handling.
"""
import sys
import os
import argparse
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

# Ensure we can import local modules even if run from outside src
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from labcom_client import LabcomClient
    from config_loader import ConfigLoader
    from data_manager import DataManager
except ImportError as e:
    print(f"CRITICAL ERROR: Failed to import modules: {e}")
    print(f"PYTHONPATH: {sys.path}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("FetchStore")

def fetch_and_store_vessel_data(
    vessel_id: str, 
    days_back: int, 
    config_path: str, 
    db_path: str
) -> Dict[str, Any]:
    """
    Fetch data for a vessel and store in the database.

    Args:
        vessel_id: The ID of the vessel to fetch.
        days_back: Number of days of history to fetch.
        config_path: Absolute path to the configuration file.
        db_path: Absolute path to the SQLite database.
    """
    logger.info(f"{'='*60}")
    logger.info(f"Starting fetch for vessel: {vessel_id}")
    logger.info(f"History: {days_back} days")
    logger.info(f"Config: {config_path}")
    logger.info(f"Database: {db_path}")
    logger.info(f"{'='*60}")

    # 1. Load Configuration
    try:
        # ConfigLoader expects a path. We provide the absolute path.
        config_loader = ConfigLoader(config_path)
        vessel_config = config_loader.get_vessel_by_id(vessel_id)
    except FileNotFoundError:
        logger.error(f"Config file not found at: {config_path}")
        raise
    except ValueError as e:
        logger.error(f"Vessel configuration error: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error loading config: {e}")
        raise

    # 2. Initialize Components
    try:
        client = LabcomClient(vessel_config.auth_token)
        # Initialize DataManager with the explicit database path
        dm = DataManager(db_path=db_path)
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

    # 3. Connect to Labcom
    logger.info("Connecting to Labcom API...")
    try:
        cloud_account = client.get_cloud_account()
        if not cloud_account:
             raise Exception("Failed to retrieve cloud account information.")
        logger.info(f"Connected as: {cloud_account.get('name')} ({cloud_account.get('email')})")
    except Exception as e:
        logger.error(f"API Connection failed: {e}")
        raise

    # 4. Update Vessel in DB
    try:
        vessel_db_id = dm.add_or_update_vessel(
            vessel_id=vessel_config.vessel_id,
            vessel_name=vessel_config.vessel_name,
            email=vessel_config.email,
            auth_token=vessel_config.auth_token,
            labcom_account_id=cloud_account.get('id')
        )
        logger.info(f"Vessel updated in DB with ID: {vessel_db_id}")
    except Exception as e:
        logger.error(f"Database error updating vessel: {e}")
        raise

    # 5. Sync Sampling Points
    logger.info("Syncing sampling points...")
    try:
        accounts = client.get_accounts()
        logger.info(f"Found {len(accounts)} sampling points in Labcom")

        for account in accounts:
            dm.add_sampling_point(
                vessel_id=vessel_db_id,
                code=f"LAB{account['id']}",
                name=account.get('name', 'Unknown'),
                labcom_account_id=account['id']
            )
    except Exception as e:
        logger.error(f"Failed to sync sampling points: {e}")
        # We might want to continue even if sync fails, depending on requirements.
        # For now, we raise to be safe.
        raise

    # 6. Fetch Measurements
    logger.info(f"Fetching measurements for last {days_back} days...")
    try:
        from_date = datetime.now() - timedelta(days=days_back)
        to_date = datetime.now()

        measurements = client.get_all_measurements_for_vessel(
            from_date=from_date,
            to_date=to_date
        )
        logger.info(f"Fetched {len(measurements)} measurements from Labcom")
    except Exception as e:
        logger.error(f"Failed to fetch measurements from API: {e}")
        raise

    # 7. Store Measurements
    logger.info("Storing measurements in database...")
    try:
        stats = dm.store_measurements(
            vessel_id=vessel_db_id,
            measurements=measurements
        )

        logger.info(f"Stored: {stats['new']} new, {stats['duplicate']} duplicates")
        if stats['alerts'] > 0:
            logger.warning(f"ALERTS GENERATED: {stats['alerts']}")
    except Exception as e:
        logger.error(f"Failed to store measurements in DB: {e}")
        raise

    # 8. Create Fetch Log
    try:
        dm.create_fetch_log(
            vessel_id=vessel_db_id,
            status='success',
            measurements_fetched=len(measurements),
            measurements_new=stats['new'],
            measurements_duplicate=stats['duplicate'],
            date_range_from=from_date,
            date_range_to=to_date
        )
        logger.info("Fetch log created.")
    except Exception as e:
        logger.error(f"Failed to create fetch log: {e}")
        # Non-critical error, don't raise

    return stats

def main():
    # Determine project root based on script location (assuming script is in src/)
    # script is at /path/to/project/src/fetch_and_store.py
    # project_root is /path/to/project
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    
    default_config = os.path.join(project_root, 'config', 'vessels_config.yaml')
    default_db = os.path.join(project_root, 'data', 'accubase.sqlite')

    parser = argparse.ArgumentParser(
        description="Fetch Labcom data and store in Accuport DB",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("vessel_id", help="The ID of the vessel to fetch (e.g., mt_aqua)")
    parser.add_argument("days", type=int, nargs='?', default=1825, help="Days of history to fetch")
    parser.add_argument("--config", default=default_config, help="Path to vessels_config.yaml")
    parser.add_argument("--db", default=default_db, help="Path to sqlite database")
    
    args = parser.parse_args()

    try:
        fetch_and_store_vessel_data(
            vessel_id=args.vessel_id,
            days_back=args.days,
            config_path=args.config,
            db_path=args.db
        )
        logger.info("✓ SUCCESS: Data fetch and storage completed!")
    except Exception:
        # Logger already printed the error
        logger.error("FAILURE: Operation failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()