# Labcom Data Fetcher for Accuport

Python application to fetch marine onboard chemical test data from Labcom API and store it in a SQLite database (accubase.sqlite).

## Features

- ✅ GraphQL API client for Labcom backend
- ✅ SQLite database with proper schema for marine chemical test data
- ✅ Support for multiple vessels with individual auth tokens
- ✅ Automatic data synchronization from Labcom
- ✅ Configurable sampling points per vessel
- ✅ Historical data fetching (configurable time range)
- ✅ Fetch logging and error handling

## Project Structure

```
datafetcher/
├── config/
│   └── vessels_config.yaml      # Vessel configuration with auth tokens
├── data/
│   └── accubase.sqlite          # SQLite database (created automatically)
├── src/
│   ├── api_inspector.py         # GraphQL API introspection tool
│   ├── labcom_client.py         # Labcom API client
│   ├── db_schema.py             # SQLite database schema
│   ├── data_manager.py          # Database operations manager
│   ├── config_loader.py         # Configuration loader
│   └── fetch_labcom_data.py     # Main data fetcher script
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure vessels:**
   Edit `config/vessels_config.yaml` and add your vessel information:
   ```yaml
   vessels:
     - vessel_id: "mv_racer"
       vessel_name: "M.V Racer"
       email: "Accu-Port@outlook.com"
       auth_token: "YOUR_LABCOM_AUTH_TOKEN_HERE"
       sampling_points:
         - AB1  # Auxiliary boiler 1
         - AB2  # Auxiliary boiler 2
         - ME   # Main Engine
         # ... add more sampling points
   ```

3. **Initialize database:**
   ```bash
   cd src
   python db_schema.py
   ```

## Usage

### Fetch Data for All Vessels

Fetch data for all configured vessels (last 30 days):
```bash
cd src
python fetch_labcom_data.py
```

### Fetch Data for Specific Vessel

Fetch data for a specific vessel:
```bash
python fetch_labcom_data.py --vessel mv_racer
```

### Fetch Custom Time Range

Fetch last 60 days of data:
```bash
python fetch_labcom_data.py --vessel mv_racer --days 60
```

### Command Line Options

```
--vessel <vessel_id>       Fetch data for specific vessel only
--days <number>            Number of days of historical data (default: 30)
--config <path>            Path to config file (default: ../config/vessels_config.yaml)
--no-sync-accounts         Skip syncing sampling points from Labcom
```

## Database Schema

The SQLite database (`data/accubase.sqlite`) contains the following tables:

### Tables

1. **vessels** - Vessel/ship information
   - id, vessel_id, vessel_name, email, labcom_account_id, auth_token

2. **sampling_points** - Sampling points for each vessel
   - id, vessel_id, code, name, system_type, labcom_account_id

3. **parameters** - Chemical test parameters
   - id, labcom_parameter_id, name, symbol, unit, min_value, max_value

4. **measurements** - Test measurement data
   - id, labcom_measurement_id, vessel_id, sampling_point_id, parameter_id, value, measurement_date

5. **fetch_logs** - Data fetch operation logs
   - id, vessel_id, fetch_start, fetch_end, status, measurements_fetched, error_message

## Sampling Point Codes

The following sampling point codes are supported:

| Code | Description | System Type |
|------|-------------|-------------|
| AB1, AB2 | Auxiliary Boilers | Boiler Water |
| CB | Composite Boiler | Boiler Water |
| HW | Hotwell | Boiler Water |
| AE1-3 | Auxiliary Engines | Auxiliary Engine |
| ME | Main Engine | Main Engine |
| PW1, PW2 | Potable Water | Potable Water |
| GW | Treated Sewage | Treated Sewage Water |
| SD1-6 | Scavenge Drains | Scavenge Drain |

## How to Get Labcom Auth Token

1. Login to your Labcom account at https://backend.labcom.cloud
2. Go to Settings or Account section
3. Look for API access or authentication tokens
4. Copy the token and add it to `config/vessels_config.yaml`

**Note:** Each vessel has its own Labcom account and unique auth token.

## Development & Testing

### Test API Connection

Test the Labcom API client:
```bash
cd src
python labcom_client.py
```

### Inspect API Schema

View the complete GraphQL API schema:
```bash
python api_inspector.py
```

### Test Database Operations

Test database creation and operations:
```bash
python data_manager.py
```

### Test Configuration Loading

Test vessel configuration loading:
```bash
python config_loader.py
```

## Troubleshooting

### Problem: Empty results or authentication errors

- **Solution:** Verify that your auth token is correct in `vessels_config.yaml`
- Check that the token has not expired
- Ensure you're using the token from the correct Labcom account

### Problem: Database errors

- **Solution:** Delete `data/accubase.sqlite` and run `python db_schema.py` to recreate

### Problem: No measurements fetched

- **Solution:**
  - Check the date range (some accounts may not have recent data)
  - Verify that the Labcom account has sampling data
  - Check logs for any API errors

## Dependencies

- `requests` - HTTP client for API calls
- `sqlalchemy` - SQL toolkit and ORM
- `pyyaml` - YAML configuration file parser
- `python-dotenv` - Environment variable management
- `click` - Command-line interface creation
- `pandas` - Data manipulation (for future enhancements)

## License

Proprietary - Accuport Platform

## Support

For issues or questions, contact the Accuport development team.
