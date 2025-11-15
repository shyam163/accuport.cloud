# Quickstart Guide - Labcom Data Fetcher

## Overview

This application fetches marine chemical test data from Labcom's cloud platform and stores it in a local SQLite database for the Accuport platform.

## Quick Setup (3 steps)

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or run the automated setup:
```bash
./setup.sh
```

### 2. Configure Your Vessel(s)

Edit `config/vessels_config.yaml`:

```yaml
vessels:
  - vessel_id: "mv_racer"
    vessel_name: "M.V Racer"
    email: "Accu-Port@outlook.com"
    auth_token: "YOUR_ACTUAL_LABCOM_TOKEN"
    sampling_points:
      - AB1  # Auxiliary boiler 1
      - ME   # Main Engine
      # ... add more sampling points
```

**Important:** Replace `YOUR_ACTUAL_LABCOM_TOKEN` with the real token from your Labcom account.

### 3. Run the Fetcher

```bash
cd src
python fetch_labcom_data.py
```

That's it! Data will be fetched and stored in `data/accubase.sqlite`.

## Usage Examples

### Fetch all vessels (default 30 days)
```bash
python fetch_labcom_data.py
```

### Fetch specific vessel
```bash
python fetch_labcom_data.py --vessel mv_racer
```

### Fetch last 60 days
```bash
python fetch_labcom_data.py --vessel mv_racer --days 60
```

### Show help
```bash
python fetch_labcom_data.py --help
```

## What Gets Stored?

The application creates `data/accubase.sqlite` with these tables:

1. **vessels** - Ship information
2. **sampling_points** - Test locations (boilers, engines, water systems)
3. **parameters** - Chemical test parameters (pH, chlorine, etc.)
4. **measurements** - Actual test results with timestamps
5. **fetch_logs** - History of data fetch operations

## Viewing the Data

Use any SQLite browser (e.g., DB Browser for SQLite) or query via Python:

```python
import sqlite3
conn = sqlite3.connect('data/accubase.sqlite')
cursor = conn.cursor()

# Get latest measurements
cursor.execute("""
    SELECT v.vessel_name, p.name, m.value, m.measurement_date
    FROM measurements m
    JOIN vessels v ON m.vessel_id = v.id
    JOIN parameters p ON m.parameter_id = p.id
    ORDER BY m.measurement_date DESC
    LIMIT 10
""")

for row in cursor.fetchall():
    print(row)
```

## Troubleshooting

### "Authentication failed" or "No data fetched"
- Verify your auth token in `vessels_config.yaml`
- Check that the token is from the correct Labcom account

### "Config file not found"
- Make sure you're running from the `src/` directory
- Or specify config path: `--config /path/to/vessels_config.yaml`

### Database errors
- Delete `data/accubase.sqlite` and run again to recreate

## Getting Your Labcom Auth Token

1. Login to https://backend.labcom.cloud
2. Navigate to your account settings
3. Look for API access or authentication section
4. Copy the token (it's a long alphanumeric string)
5. Paste it into `vessels_config.yaml`

**Note:** Each vessel needs its own Labcom account and token.

## Automation (Optional)

### Run daily via cron

Add to your crontab (`crontab -e`):
```bash
0 2 * * * cd /path/to/datafetcher/src && /usr/bin/python3 fetch_labcom_data.py
```

This runs every day at 2 AM.

## Files You'll Need to Modify

- `config/vessels_config.yaml` - Add your vessel tokens here

## Files Created Automatically

- `data/accubase.sqlite` - Your database (don't delete!)
- `labcom_schema.json` - API schema (for reference)

## Next Steps

After fetching data successfully:
1. Connect your Accuport dashboard to `accubase.sqlite`
2. Set up automated daily fetches
3. Monitor the `fetch_logs` table for any errors

## Support

For issues, check the main `README.md` or contact the Accuport team.
