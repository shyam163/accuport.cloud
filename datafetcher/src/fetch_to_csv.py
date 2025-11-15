#!/usr/bin/env python3
"""
Fetch Labcom data and export to CSV
Quick script to test data fetching and export results to CSV for review
"""
import csv
import sys
from datetime import datetime, timedelta
from labcom_client import LabcomClient
from config_loader import ConfigLoader

def fetch_and_export_csv(vessel_id: str, days_back: int = 30, output_file: str = None):
    """
    Fetch data for a vessel and export to CSV

    Args:
        vessel_id: Vessel identifier from config
        days_back: Number of days of historical data
        output_file: Output CSV file path
    """
    print(f"{'='*60}")
    print(f"Fetching data for {vessel_id}")
    print(f"{'='*60}\n")

    # Load config
    config_loader = ConfigLoader('../config/vessels_config.yaml')
    vessel_config = config_loader.get_vessel_by_id(vessel_id)

    # Initialize client
    client = LabcomClient(vessel_config.auth_token)

    # Get cloud account info
    print("1. Connecting to Labcom...")
    cloud_account = client.get_cloud_account()
    print(f"   ✓ Connected as: {cloud_account.get('name')} ({cloud_account.get('email')})\n")

    # Get accounts (sampling points)
    print("2. Fetching sampling points...")
    accounts = client.get_accounts()
    print(f"   ✓ Found {len(accounts)} sampling point(s)\n")

    # Get parameters
    print("3. Fetching available parameters...")
    parameters = client.get_parameters()
    print(f"   ✓ Found {len(parameters)} parameter(s)\n")

    # Fetch measurements
    print(f"4. Fetching measurements (last {days_back} days)...")
    from_date = datetime.now() - timedelta(days=days_back)
    to_date = datetime.now()

    measurements = client.get_all_measurements_for_vessel(
        from_date=from_date,
        to_date=to_date
    )

    # Flatten measurements for CSV
    csv_data = []
    total_measurements = len(measurements)

    # Create account lookup
    account_lookup = {acc['id']: acc for acc in accounts}

    for meas in measurements:
        account_id = meas.get('account_id')
        account_info = account_lookup.get(account_id, {})
        account_name = account_info.get('name', meas.get('account', 'Unknown'))

        csv_row = {
            'vessel_name': vessel_config.vessel_name,
            'vessel_id': vessel_config.vessel_id,
            'account_id': account_id,
            'account_name': account_name,
            'measurement_id': meas.get('id'),
            'measurement_date': datetime.fromtimestamp(meas.get('timestamp')).strftime('%Y-%m-%d %H:%M:%S'),
            'parameter_id': meas.get('parameter_id'),
            'parameter_name': meas.get('parameter', ''),
            'value': meas.get('value'),
            'unit': meas.get('unit', ''),
            'ideal_low': meas.get('ideal_low', ''),
            'ideal_high': meas.get('ideal_high', ''),
            'ideal_status': meas.get('ideal_status', ''),
            'comment': meas.get('comment', ''),
            'operator_name': meas.get('operator_name', ''),
            'device_serial': meas.get('device_serial', '')
        }
        csv_data.append(csv_row)

    print(f"   ✓ Found {total_measurements} measurement(s)\n")

    # Export to CSV
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = f"../data/{vessel_id}_data_{timestamp}.csv"

    print(f"5. Exporting to CSV...")

    if csv_data:
        fieldnames = [
            'vessel_name', 'vessel_id', 'account_id', 'account_name',
            'measurement_id', 'measurement_date', 'parameter_id',
            'parameter_name', 'value', 'unit',
            'ideal_low', 'ideal_high', 'ideal_status', 'comment',
            'operator_name', 'device_serial'
        ]

        with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_data)

        print(f"   ✓ Exported {len(csv_data)} rows to: {output_file}\n")
    else:
        print("   ⚠ No data to export\n")

    # Summary
    print(f"{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Vessel: {vessel_config.vessel_name}")
    print(f"Sampling Points: {len(accounts)}")
    print(f"Total Measurements: {total_measurements}")
    print(f"CSV File: {output_file}")
    print(f"{'='*60}\n")

    return output_file


if __name__ == "__main__":
    vessel_id = sys.argv[1] if len(sys.argv) > 1 else "mv_october"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    fetch_and_export_csv(vessel_id, days_back=days)
