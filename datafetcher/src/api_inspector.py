"""
Labcom GraphQL API Inspector
This script introspects the Labcom GraphQL API to discover available queries and schema
"""
import json
import requests


INTROSPECTION_QUERY = """
query IntrospectionQuery {
  __schema {
    queryType { name }
    mutationType { name }
    types {
      kind
      name
      description
      fields {
        name
        description
        args {
          name
          description
          type {
            kind
            name
            ofType {
              kind
              name
            }
          }
        }
        type {
          kind
          name
          ofType {
            kind
            name
          }
        }
      }
    }
  }
}
"""


def introspect_graphql_api(endpoint: str, token: str) -> dict:
    """
    Introspect a GraphQL API to discover its schema

    Args:
        endpoint: GraphQL API endpoint URL
        token: Authentication token

    Returns:
        Dictionary containing the API schema
    """
    # Try different authentication methods
    auth_methods = [
        {'Content-Type': 'application/json'},  # Token in URL params
        {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
        {'Content-Type': 'application/json', 'Authorization': f'Token {token}'},
        {'Content-Type': 'application/json', 'X-Auth-Token': token},
    ]

    payload = {
        'query': INTROSPECTION_QUERY
    }

    for i, headers in enumerate(auth_methods):
        try:
            # Try with token as query parameter (as seen in GraphiQL URL)
            url = f"{endpoint}?token={token}" if i == 0 else endpoint

            print(f"Trying authentication method {i+1}...")
            response = requests.post(url, json=payload, headers=headers)

            if response.status_code == 200:
                print(f"Success with method {i+1}!")
                return response.json()
            else:
                print(f"Method {i+1} failed: {response.status_code}")

        except requests.exceptions.RequestException as e:
            print(f"Method {i+1} error: {e}")
            continue

    print("All authentication methods failed")
    return None


def save_schema(schema: dict, output_file: str = "labcom_schema.json"):
    """Save the schema to a JSON file"""
    with open(output_file, 'w') as f:
        json.dump(schema, f, indent=2)
    print(f"Schema saved to {output_file}")


def print_available_queries(schema: dict):
    """Print all available queries from the schema"""
    if not schema or 'data' not in schema:
        print("Invalid schema data")
        return

    types = schema['data']['__schema']['types']

    # Find the Query type
    for type_info in types:
        if type_info['name'] == 'Query':
            print("\n=== Available Queries ===\n")
            if type_info['fields']:
                for field in type_info['fields']:
                    print(f"Query: {field['name']}")
                    if field['description']:
                        print(f"  Description: {field['description']}")
                    if field['args']:
                        print("  Arguments:")
                        for arg in field['args']:
                            arg_type = arg['type']['name'] or arg['type']['ofType']['name']
                            print(f"    - {arg['name']}: {arg_type}")
                    print()


if __name__ == "__main__":
    import os
    # Labcom API endpoint
    ENDPOINT = "https://backend.labcom.cloud/graphql"
    TOKEN = "77e32d13a13d3f0d5ca1a44915b91a46a28b2b6a2a99470b744daaa7f384298009db8718c2e2054e"

    print("Introspecting Labcom GraphQL API...")
    schema = introspect_graphql_api(ENDPOINT, TOKEN)

    if schema:
        # Save to project root
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(script_dir)
        schema_path = os.path.join(project_root, "labcom_schema.json")
        save_schema(schema, schema_path)
        print_available_queries(schema)
    else:
        print("Failed to introspect API. Please check the endpoint and token.")
