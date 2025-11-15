"""
Test script to fetch actual measurement data from Labcom API
"""
import json
import requests
from datetime import datetime, timedelta


LABCOM_ENDPOINT = "https://backend.labcom.cloud/graphql"
TOKEN = "77e32d13a13d3f0d5ca1a44915b91a46a28b2b6a2a99470b744daaa7f384298009db8718c2e2054e"


def execute_graphql_query(query: str, variables: dict = None) -> dict:
    """Execute a GraphQL query against Labcom API"""
    url = f"{LABCOM_ENDPOINT}?token={TOKEN}"
    headers = {'Content-Type': 'application/json'}

    payload = {'query': query}
    if variables:
        payload['variables'] = variables

    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()


def get_accounts():
    """Fetch all accounts"""
    query = """
    query {
      Accounts {
        id
        name
        email
        address
        gps
      }
    }
    """
    result = execute_graphql_query(query)
    return result.get('data', {}).get('Accounts', [])


def get_measurements(account_id: int, days_back: int = 30):
    """Fetch measurements for an account"""
    # Calculate timestamp (Unix timestamp in seconds)
    to_date = int(datetime.now().timestamp())
    from_date = int((datetime.now() - timedelta(days=days_back)).timestamp())

    query = """
    query GetMeasurements($accountId: Int!, $from: Int!, $to: Int!) {
      Measurements(accountId: $accountId, from: $from, to: $to) {
        id
        value
        date
        parameter {
          id
          name
          unit
          symbol
        }
        account {
          id
          name
        }
      }
    }
    """

    variables = {
        'accountId': account_id,
        'from': from_date,
        'to': to_date
    }

    result = execute_graphql_query(query, variables)
    return result.get('data', {}).get('Measurements', [])


def get_parameters():
    """Fetch all available parameters"""
    query = """
    query {
      Parameters {
        id
        name
        unit
        symbol
        minValue
        maxValue
      }
    }
    """
    result = execute_graphql_query(query)
    return result.get('data', {}).get('Parameters', [])


if __name__ == "__main__":
    print("=== Testing Labcom API ===\n")

    # 1. Get accounts
    print("1. Fetching accounts...")
    accounts = get_accounts()
    print(f"Found {len(accounts)} account(s):\n")
    for acc in accounts:
        print(f"  ID: {acc['id']}, Name: {acc['name']}, Email: {acc.get('email', 'N/A')}")

    # 2. Get parameters
    print("\n2. Fetching available parameters...")
    parameters = get_parameters()
    print(f"Found {len(parameters)} parameter(s):\n")
    for i, param in enumerate(parameters[:10]):  # Show first 10
        print(f"  {param['name']} ({param['symbol']}) - Unit: {param['unit']}")
    if len(parameters) > 10:
        print(f"  ... and {len(parameters) - 10} more")

    # 3. Get measurements for first account
    if accounts:
        account_id = accounts[0]['id']
        print(f"\n3. Fetching measurements for account {account_id} (last 30 days)...")
        measurements = get_measurements(account_id, days_back=30)
        print(f"Found {len(measurements)} measurement(s)\n")

        if measurements:
            # Show first 5 measurements
            print("Sample measurements:")
            for i, m in enumerate(measurements[:5]):
                date_str = datetime.fromtimestamp(m['date']).strftime('%Y-%m-%d %H:%M:%S')
                param_name = m['parameter']['name']
                value = m['value']
                unit = m['parameter']['symbol']
                print(f"  {date_str} - {param_name}: {value} {unit}")

            if len(measurements) > 5:
                print(f"  ... and {len(measurements) - 5} more")

            # Save sample data
            sample_file = "../sample_measurements.json"
            with open(sample_file, 'w') as f:
                json.dump(measurements[:20], f, indent=2)
            print(f"\nSaved 20 sample measurements to {sample_file}")

    print("\n=== Test Complete ===")
