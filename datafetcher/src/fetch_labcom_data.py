#!/usr/bin/env python3
"""
Labcom Data Fetcher for Accuport
Main script to fetch data from Labcom and store in SQLite database
"""
import argparse
import logging
from datetime import datetime, timedelta
from typing import Optional

from labcom_client import LabcomClient
from data_manager import DataManager
from config_loader import ConfigLoader, SAMPLING_POINT_MAP

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LabcomDataFetcher:
    """Main data fetcher orchestrator"""

    def __init__(self, config_file: str = '../config/vessels_config.yaml'):
        """
        Initialize data fetcher

        Args:
            config_file: Path to vessel configuration file
        """
        self.config_loader = ConfigLoader(config_file)
        self.data_manager = DataManager()

    def fetch_vessel_data(
        self,
        vessel_id: str,
        days_back: int = 30,
        sync_accounts: bool = True
    ) -> dict:
        """
        Fetch data for a specific vessel

        Args:
            vessel_id: Vessel identifier from config
            days_back: Number of days of historical data to fetch
            sync_accounts: Whether to sync sampling points from Labcom

        Returns:
            Dictionary with fetch statistics
        """
        logger.info(f"{'='*60}")
        logger.info(f"Starting data fetch for vessel: {vessel_id}")
        logger.info(f"{'='*60}")

        # Get vessel config
        vessel_config = self.config_loader.get_vessel_by_id(vessel_id)

        # Initialize Labcom client
        client = LabcomClient(vessel_config.auth_token)

        # Get cloud account info
        cloud_account = client.get_cloud_account()
        logger.info(f"Connected to Labcom account: {cloud_account.get('name')} ({cloud_account.get('email')})")

        # Add/update vessel in database
        vessel_db_id = self.data_manager.add_or_update_vessel(
            vessel_id=vessel_config.vessel_id,
            vessel_name=vessel_config.vessel_name,
            email=vessel_config.email,
            auth_token=vessel_config.auth_token,
            labcom_account_id=cloud_account.get('id')
        )

        logger.info(f"Vessel database ID: {vessel_db_id}")

        # Sync sampling points (accounts) from Labcom
        if sync_accounts:
            logger.info("Syncing sampling points from Labcom...")
            labcom_accounts = client.get_accounts()
            logger.info(f"Found {len(labcom_accounts)} accounts in Labcom")

            for account in labcom_accounts:
                account_id = account.get('id')
                account_name = account.get('name', 'Unknown')

                # Try to match with configured sampling points
                # For now, we'll create all accounts as sampling points
                # You can add custom matching logic here

                self.data_manager.add_sampling_point(
                    vessel_id=vessel_db_id,
                    code=f"LAB{account_id}",  # Temporary code
                    name=account_name,
                    labcom_account_id=account_id
                )

            logger.info(f"✓ Synced {len(labcom_accounts)} sampling points")

        # Fetch measurements
        logger.info(f"Fetching measurements for last {days_back} days...")

        from_date = datetime.now() - timedelta(days=days_back)
        to_date = datetime.now()

        all_measurements = client.get_all_measurements_for_vessel(
            from_date=from_date,
            to_date=to_date
        )

        # Store measurements
        total_stored = 0
        if all_measurements:
            logger.info(f"Storing {len(all_measurements)} measurements...")
            total_stored = self.data_manager.store_measurements(
                vessel_id=vessel_db_id,
                measurements=all_measurements
            )

        logger.info(f"✓ Stored {total_stored} new measurements")

        # Create fetch log
        self.data_manager.create_fetch_log(
            vessel_id=vessel_db_id,
            status='success',
            measurements_fetched=total_stored
        )

        logger.info(f"{'='*60}")
        logger.info(f"Fetch complete for {vessel_id}")
        logger.info(f"{'='*60}\n")

        return {
            'vessel_id': vessel_id,
            'vessel_name': vessel_config.vessel_name,
            'measurements_stored': total_stored,
            'status': 'success'
        }

    def fetch_all_vessels(self, days_back: int = 30) -> list:
        """
        Fetch data for all configured vessels

        Args:
            days_back: Number of days of historical data

        Returns:
            List of fetch results
        """
        vessels = self.config_loader.get_all_vessels()
        results = []

        logger.info(f"\nFetching data for {len(vessels)} vessel(s)...\n")

        for vessel_config in vessels:
            try:
                result = self.fetch_vessel_data(
                    vessel_id=vessel_config.vessel_id,
                    days_back=days_back
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Failed to fetch data for {vessel_config.vessel_id}: {e}")
                results.append({
                    'vessel_id': vessel_config.vessel_id,
                    'vessel_name': vessel_config.vessel_name,
                    'measurements_stored': 0,
                    'status': 'failed',
                    'error': str(e)
                })

                # Log the failure
                vessel_db_id = self.data_manager.get_vessel_by_id(vessel_config.vessel_id)
                if vessel_db_id:
                    self.data_manager.create_fetch_log(
                        vessel_id=vessel_db_id,
                        status='failed',
                        error_message=str(e)
                    )

        return results


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Fetch data from Labcom and store in Accuport SQLite database'
    )

    parser.add_argument(
        '--vessel',
        type=str,
        help='Vessel ID to fetch (if not specified, fetches all vessels)'
    )

    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days of historical data to fetch (default: 30)'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='../config/vessels_config.yaml',
        help='Path to vessel configuration file'
    )

    parser.add_argument(
        '--no-sync-accounts',
        action='store_true',
        help='Skip syncing sampling points from Labcom'
    )

    args = parser.parse_args()

    # Initialize fetcher
    fetcher = LabcomDataFetcher(config_file=args.config)

    # Fetch data
    if args.vessel:
        # Fetch specific vessel
        result = fetcher.fetch_vessel_data(
            vessel_id=args.vessel,
            days_back=args.days,
            sync_accounts=not args.no_sync_accounts
        )
        print(f"\n{'='*60}")
        print(f"FETCH SUMMARY")
        print(f"{'='*60}")
        print(f"Vessel: {result['vessel_name']}")
        print(f"Measurements Stored: {result['measurements_stored']}")
        print(f"Status: {result['status']}")
        print(f"{'='*60}\n")

    else:
        # Fetch all vessels
        results = fetcher.fetch_all_vessels(days_back=args.days)

        print(f"\n{'='*60}")
        print(f"FETCH SUMMARY - ALL VESSELS")
        print(f"{'='*60}")

        total_measurements = 0
        for result in results:
            print(f"\n{result['vessel_name']}:")
            print(f"  Status: {result['status']}")
            print(f"  Measurements: {result['measurements_stored']}")
            if result.get('error'):
                print(f"  Error: {result['error']}")

            total_measurements += result['measurements_stored']

        print(f"\n{'='*60}")
        print(f"Total Measurements Stored: {total_measurements}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
