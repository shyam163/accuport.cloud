# Analysis and Improvement Suggestions for `fetch_and_store.py`

## Overview
The `src/fetch_and_store.py` script is the primary entry point for data ingestion. It orchestrates fetching data from the Labcom API and storing it in the SQLite database.

**Constraint:** The database structure (schema) must remain unchanged to ensure compatibility with the dashboard web app.

## Analysis Findings

### 1. Command-Line Argument Handling
*   **Current State:** Uses `sys.argv` with index-based access (`sys.argv[1]`, `sys.argv[2]`).
*   **Issue:** This is brittle. If the user provides arguments in the wrong order or omits one, it crashes or misbehaves. It lacks help text (`--help`).
*   **Suggestion:** Use the standard `argparse` library. This allows for named arguments (e.g., `--vessel`, `--days`), automatic help generation, and default values.

### 2. Hardcoded Paths
*   **Current State:** The config path (`config/vessels_config.yaml`) and database path (`data/accubase.sqlite`) are hardcoded in the function or passed explicitly in the code.
*   **Issue:** This restricts the script to running only from the project root. It complicates testing or running in different environments (e.g., cron jobs where CWD might differ).
*   **Suggestion:** Make paths configurable via arguments, or resolve them dynamically relative to the script's location (`__file__`).

### 3. Logging vs. Printing
*   **Current State:** The script uses `print()` statements for status updates.
*   **Issue:** `print` output is hard to filter, timestamp, or redirect to a file alongside other logs. `src/data_manager.py` and `src/labcom_client.py` already use the `logging` module.
*   **Suggestion:** Switch to Python's `logging` module. This provides timestamps, log levels (INFO, ERROR), and consistency with the rest of the application.

### 4. Error Handling
*   **Current State:** A generic `try...except Exception` block wraps the main execution.
*   **Issue:** This masks specific errors (like `ConfigLoader` failing vs. API network errors) and dumps a traceback for everything.
*   **Suggestion:** Catch specific exceptions (e.g., `FileNotFoundError` for config, `requests.exceptions.RequestException` for API) to provide user-friendly error messages.

### 5. Performance (Observation)
*   **Current State:** The script fetches *all* measurements for a date range. The `DataManager.store_measurements` method processes them one by one, performing database lookups (SELECT) for `Parameter` and `SamplingPoint` inside the loop.
*   **Issue:** For large datasets, this "N+1 query" problem is slow.
*   **Suggestion:** While we cannot change the DB *structure*, we can optimize `DataManager` (in a separate refactor) to cache `SamplingPoints` and `Parameters` in memory before the loop. For `fetch_and_store.py` itself, the logic is sound.

## Suggested Refactoring

Here is a proposed improved version of `src/fetch_and_store.py` that implements points 1-4.

```python
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

from labcom_client import LabcomClient
from config_loader import ConfigLoader
from data_manager import DataManager

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
    """
    logger.info(f"{'='*60}")
    logger.info(f"Starting fetch for vessel: {vessel_id}")
    logger.info(f"History: {days_back} days")
    logger.info(f"Config: {config_path}")
    logger.info(f"Database: {db_path}")
    logger.info(f"{'='*60}")

    # 1. Load Configuration
    try:
        config_loader = ConfigLoader(config_path)
        vessel_config = config_loader.get_vessel_by_id(vessel_id)
    except FileNotFoundError:
        logger.error(f"Config file not found at: {config_path}")
        raise
    except ValueError as e:
        logger.error(f"Vessel configuration error: {e}")
        raise

    # 2. Initialize Components
    try:
        client = LabcomClient(vessel_config.auth_token)
        # Use the provided db_path explicitly
        dm = DataManager(db_path=db_path)
    except Exception as e:
        logger.error(f"Failed to initialize components: {e}")
        raise

    # 3. Connect to Labcom
    logger.info("Connecting to Labcom API...")
    cloud_account = client.get_cloud_account()
    logger.info(f"Connected as: {cloud_account.get('name')} ({cloud_account.get('email')})")

    # 4. Update Vessel in DB
    vessel_db_id = dm.add_or_update_vessel(
        vessel_id=vessel_config.vessel_id,
        vessel_name=vessel_config.vessel_name,
        email=vessel_config.email,
        auth_token=vessel_config.auth_token,
        labcom_account_id=cloud_account.get('id')
    )
    
    # 5. Sync Sampling Points
    logger.info("Syncing sampling points...")
    accounts = client.get_accounts()
    logger.info(f"Found {len(accounts)} sampling points in Labcom")

    for account in accounts:
        dm.add_sampling_point(
            vessel_id=vessel_db_id,
            code=f"LAB{account['id']}",
            name=account.get('name', 'Unknown'),
            labcom_account_id=account['id']
        )

    # 6. Fetch Measurements
    logger.info(f"Fetching measurements for last {days_back} days...")
    from_date = datetime.now() - timedelta(days=days_back)
    to_date = datetime.now()

    measurements = client.get_all_measurements_for_vessel(
        from_date=from_date,
        to_date=to_date
    )
    logger.info(f"Fetched {len(measurements)} measurements from Labcom")

    # 7. Store Measurements
    logger.info("Storing measurements in database...")
    stats = dm.store_measurements(
        vessel_id=vessel_db_id,
        measurements=measurements
    )

    logger.info(f"Stored: {stats['new']} new, {stats['duplicate']} duplicates")
    if stats['alerts'] > 0:
        logger.warning(f"ALERTS GENERATED: {stats['alerts']}")

    # 8. Create Fetch Log
    dm.create_fetch_log(
        vessel_id=vessel_db_id,
        status='success',
        measurements_fetched=len(measurements),
        measurements_new=stats['new'],
        measurements_duplicate=stats['duplicate'],
        date_range_from=from_date,
        date_range_to=to_date
    )
    
    return stats

def main():
    # Define default paths relative to project root (assuming script is in src/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_config = os.path.join(project_root, 'config', 'vessels_config.yaml')
    default_db = os.path.join(project_root, 'data', 'accubase.sqlite')

    parser = argparse.ArgumentParser(description="Fetch Labcom data and store in Accuport DB")
    parser.add_argument("vessel_id", help="The ID of the vessel to fetch (e.g., mt_aqua)")
    parser.add_argument("days", type=int, nargs='?', default=30, help="Days of history to fetch (default: 30)")
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
    except Exception as e:
        logger.error(f"FAILURE: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
```
