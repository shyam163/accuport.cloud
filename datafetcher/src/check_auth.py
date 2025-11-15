"""
Check authentication and what data is accessible with the current token
"""
import json
import requests


LABCOM_ENDPOINT = "https://backend.labcom.cloud/graphql"
TOKEN = "77e32d13a13d3f0d5ca1a44915b91a46a28b2b6a2a99470b744daaa7f384298009db8718c2e2054e"


def execute_query(query: str):
    """Execute a GraphQL query"""
    url = f"{LABCOM_ENDPOINT}?token={TOKEN}"
    headers = {'Content-Type': 'application/json'}
    payload = {'query': query}

    response = requests.post(url, json=payload, headers=headers)
    return response.json()


# Test CloudAccount query
print("Testing CloudAccount query...")
result = execute_query("""
query {
  CloudAccount {
    id
    email
    name
  }
}
""")
print(json.dumps(result, indent=2))
