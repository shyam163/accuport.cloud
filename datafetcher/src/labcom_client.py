"""
Labcom GraphQL API Client
Handles all communication with the Labcom backend
"""
import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LabcomClient:
    """Client for interacting with Labcom GraphQL API"""

    BASE_URL = "https://backend.labcom.cloud/graphql"

    def __init__(self, auth_token: str):
        """
        Initialize Labcom API client

        Args:
            auth_token: Authentication token for the vessel/account
        """
        self.auth_token = auth_token
        self.endpoint = f"{self.BASE_URL}?token={auth_token}"
        self.headers = {'Content-Type': 'application/json'}

    def _execute_query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """
        Execute a GraphQL query

        Args:
            query: GraphQL query string
            variables: Optional query variables

        Returns:
            API response data
        """
        payload = {'query': query}
        if variables:
            payload['variables'] = variables

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers=self.headers,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()

            if 'errors' in result:
                logger.error(f"GraphQL errors: {result['errors']}")
                raise Exception(f"GraphQL errors: {result['errors']}")

            return result.get('data', {})

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def get_cloud_account(self) -> Dict:
        """Get the authenticated cloud account information"""
        query = """
        query {
          CloudAccount {
            id
            email
            name
          }
        }
        """
        return self._execute_query(query).get('CloudAccount', {})

    def get_accounts(self) -> List[Dict]:
        """
        Get all accounts (sampling points) for the authenticated user

        Returns:
            List of account dictionaries
        """
        query = """
        query {
          Accounts {
            id
            forename
            surname
            email
            address
            gps
            volume
            volume_unit
            pooltext
          }
        }
        """
        accounts = self._execute_query(query).get('Accounts', [])

        # Add a 'name' field combining forename and surname
        for account in accounts:
            forename = account.get('forename', '')
            surname = account.get('surname', '')
            account['name'] = f"{forename} {surname}".strip() or account.get('pooltext', 'Unknown')

        return accounts

    def get_parameters(self, language_id: Optional[int] = None) -> List[Dict]:
        """
        Get all available test parameters

        Args:
            language_id: Optional language ID filter (default: 1 for English)

        Returns:
            List of parameter dictionaries
        """
        query = """
        query GetParameters($languageId: Int) {
          Parameters(languageId: $languageId) {
            parameter_id
            name_short_i18n
            name_long_i18n
            language_id
            Parameter {
              id
              name_short
              name_long
              unit
              limit_min
              limit_max
            }
          }
        }
        """
        # Default to English (language_id = 1)
        variables = {'languageId': language_id or 1}

        param_translations = self._execute_query(query, variables).get('Parameters', [])

        # Flatten the structure to be more usable
        parameters = []
        for pt in param_translations:
            param = pt.get('Parameter', {})
            parameters.append({
                'id': param.get('id'),
                'name': pt.get('name_short_i18n') or param.get('name_short', ''),
                'name_long': pt.get('name_long_i18n') or param.get('name_long', ''),
                'unit': param.get('unit', ''),
                'symbol': pt.get('name_short_i18n') or param.get('name_short', ''),
                'minValue': param.get('limit_min'),
                'maxValue': param.get('limit_max')
            })

        return parameters

    def get_measurements(
        self,
        account_ids: List[int],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        parameter_name: Optional[str] = None
    ) -> List[Dict]:
        """
        Get measurements for specific accounts

        Args:
            account_ids: List of account/sampling point IDs
            from_date: Start date (defaults to 30 days ago)
            to_date: End date (defaults to now)
            parameter_name: Optional filter by parameter name

        Returns:
            List of measurement dictionaries
        """
        # Default date range: last 30 days
        if not to_date:
            to_date = datetime.now()
        if not from_date:
            from_date = to_date - timedelta(days=30)

        # Convert to Unix timestamps
        from_timestamp = int(from_date.timestamp())
        to_timestamp = int(to_date.timestamp())

        query = """
        query GetMeasurements($accountId: [Int], $from: Int, $to: Int, $parameterName: String) {
          Measurements(
            accountId: $accountId,
            from: $from,
            to: $to,
            parameterName: $parameterName
          ) {
            id
            account_id
            account
            parameter_id
            parameter
            value
            timestamp
            unit
            comment
            ideal_low
            ideal_high
            ideal_status
            operator_name
            device_serial
          }
        }
        """

        variables = {
            'accountId': account_ids,
            'from': from_timestamp,
            'to': to_timestamp
        }

        if parameter_name:
            variables['parameterName'] = parameter_name

        return self._execute_query(query, variables).get('Measurements', [])

    def get_all_measurements_for_vessel(
        self,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Get all measurements for all accounts associated with this vessel

        Args:
            from_date: Start date
            to_date: End date

        Returns:
            List of all measurements
        """
        logger.info("Fetching all accounts for vessel...")
        accounts = self.get_accounts()
        logger.info(f"Found {len(accounts)} accounts")

        # Get all account IDs
        account_ids = [acc['id'] for acc in accounts]

        logger.info(f"Fetching measurements for all {len(account_ids)} accounts...")

        try:
            measurements = self.get_measurements(
                account_ids=account_ids,
                from_date=from_date,
                to_date=to_date
            )
            logger.info(f"  Found {len(measurements)} total measurements")
            return measurements

        except Exception as e:
            logger.error(f"  Failed to fetch measurements: {e}")
            return []


if __name__ == "__main__":
    # Test with demo token
    DEMO_TOKEN = "77e32d13a13d3f0d5ca1a44915b91a46a28b2b6a2a99470b744daaa7f384298009db8718c2e2054e"

    client = LabcomClient(DEMO_TOKEN)

    print("=== Testing Labcom Client ===\n")

    # Test cloud account
    print("1. Cloud Account:")
    account = client.get_cloud_account()
    print(f"   ID: {account.get('id')}")
    print(f"   Name: {account.get('name')}")
    print(f"   Email: {account.get('email')}\n")

    # Test accounts
    print("2. Accounts:")
    accounts = client.get_accounts()
    print(f"   Found {len(accounts)} account(s)\n")

    # Test parameters
    print("3. Parameters:")
    parameters = client.get_parameters()
    print(f"   Found {len(parameters)} parameter(s)")
    if parameters:
        print(f"   First parameter: {parameters[0].get('name')}\n")

    print("=== Test Complete ===")
