# Developer Guide

This file provides guidance when working with code in this repository.

## Project Overview

Accuport is a marine onboard chemical test solutions platform consisting of two main components:

1. **datafetcher**: Python application that fetches chemical test data from Labcom's GraphQL API and stores it in SQLite
2. **dashbored**: Flask web dashboard with role-based access control for vessel and fleet managers

Both components share a common SQLite database (`accubase.sqlite`) that stores vessel measurements, parameters, and test data.

## Common Commands

### Data Fetcher (datafetcher/)

```bash
# Setup and initialize
cd datafetcher
./setup.sh                                    # Install dependencies and create database

# Fetch data
cd src
python fetch_labcom_data.py                   # Fetch all vessels (last 30 days)
python fetch_labcom_data.py --vessel mv_racer # Fetch specific vessel
python fetch_labcom_data.py --days 60         # Fetch custom time range
python fetch_and_store.py mv_october 30       # Enhanced fetch with quality control

# Testing and inspection
python labcom_client.py                       # Test API connection
python api_inspector.py                       # View GraphQL schema
python data_manager.py                        # Test database operations
python config_loader.py                       # Test config loading
python db_schema.py                           # Reinitialize database schema
```

### Dashboard (dashbored/)

```bash
# Setup
cd dashbored
./setup.sh                          # Install dependencies and initialize users database
python3 init_users_db.py            # Initialize users.sqlite with default accounts

# Run the dashboard
python3 app.py                      # Start Flask server at http://localhost:5000

# Production deployment
export SECRET_KEY="your-secure-key"
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Architecture

### Data Flow

1. **Labcom API** → `datafetcher/labcom_client.py` (GraphQL client)
2. **Data Manager** → `datafetcher/data_manager.py` (stores in SQLite via SQLAlchemy)
3. **accubase.sqlite** → Shared database (READ-ONLY for dashboard)
4. **Dashboard Models** → `dashbored/models.py` (reads vessel data)
5. **Flask Routes** → `dashbored/app.py` (serves web UI)

### Two Database Architecture

- **accubase.sqlite**: Vessel measurements, parameters, sampling points (READ-ONLY for dashboard)
- **users.sqlite**: User accounts, roles, vessel assignments (READ-WRITE for dashboard)

### Role-Based Access Hierarchy

```
admin (all vessels)
└── fleet_manager (vessels of subordinate vessel managers)
    └── vessel_manager (directly assigned vessels only)
```

Access control implementation: `dashbored/models.py:get_user_vessels()`

### Database Schema (accubase.sqlite)

Key tables and relationships:
- `vessels` → vessel information (vessel_id, vessel_name, auth_token)
- `sampling_points` → equipment test locations (AB1, ME, PW1, etc.)
  - Links to vessel via `vessel_id`
  - Links to Labcom via `labcom_account_id`
- `parameters` → test parameters (pH, Chloride, Phosphate, etc.)
  - Includes ideal ranges (`ideal_low`, `ideal_high`)
- `measurements` → actual test data
  - Stores both string (`value`) and numeric (`value_numeric`)
  - Quality control: `ideal_status` (OKAY, TOO LOW, TOO HIGH, CRITICAL)
  - Tracks operator, device, and timestamp
- `alerts` → automatic out-of-range detection
- `parameter_limits` → custom thresholds per sampling point
- `fetch_logs` → data fetch operation history

See `datafetcher/src/db_schema.py` for complete schema with SQLAlchemy ORM models.

## Configuration

### datafetcher Configuration

Edit `datafetcher/config/vessels_config.yaml`:
```yaml
vessels:
  - vessel_id: "mv_racer"
    vessel_name: "M.V Racer"
    email: "vessel@example.com"
    auth_token: "LABCOM_AUTH_TOKEN_HERE"
    sampling_points:
      - AB1  # Auxiliary boiler 1
      - ME   # Main Engine
```

Each vessel requires:
- Unique `vessel_id` (used internally)
- Labcom auth token (from https://backend.labcom.cloud)
- List of sampling point codes (AB1, AB2, ME, AE1-3, PW1-2, etc.)

### Dashboard User Management

Default accounts created by `init_users_db.py`:
- `admin` / `adminpass` - Administrator (all vessels)
- `fleet1` / `fleet1pass` - Fleet Manager
- `super1` / `super1pass` - Vessel Manager (MV Racer, MT Aqua)
- `super2` / `super2pass` - Vessel Manager (MT Voyager, MV October)

User authentication: `dashbored/auth.py` (bcrypt password hashing)

## Important Implementation Details

### Labcom API Integration

- Base URL: `https://backend.labcom.cloud/graphql`
- Authentication: Token-based via query parameter (`?token=...`)
- Client implementation: `datafetcher/src/labcom_client.py`
- Key methods:
  - `get_cloud_account()` - Get account info
  - `get_accounts()` - Get sampling points
  - `get_measurements()` - Fetch test data with date range

### Data Fetcher Multi-Vessel Support

The fetcher can process multiple vessels in a single run:
- Each vessel has its own auth token and Labcom account
- Sampling points are synced from Labcom (`sync_accounts=True`)
- Measurements are deduplicated by `labcom_measurement_id` per vessel
- All operations are logged in `fetch_logs` table

### Dashboard Database Access Pattern

Critical: `accubase.sqlite` is opened in READ-ONLY mode (`mode=ro`) in `dashbored/database.py:get_accubase_connection()`. Never attempt write operations from the dashboard.

### Quality Control and Alerts

Automatic alert generation in `datafetcher/src/data_manager.py:store_measurements()`:
- Compares `value_numeric` against `ideal_low`/`ideal_high`
- Sets `ideal_status` (OKAY, TOO LOW, TOO HIGH, CRITICAL)
- Creates `Alert` records for out-of-range values
- Example: Iron-in-Oil below 50 mg/l triggers TOO LOW alert

### Sampling Point Code System

Standard codes used across vessels:
- **Boiler Water**: AB1, AB2 (Auxiliary Boilers), CB (Composite), HW (Hotwell)
- **Engines**: ME (Main Engine), AE1-AE3 (Auxiliary Engines)
- **Water Systems**: PW1-PW2 (Potable Water), GW (Treated Sewage)
- **Scavenge Drains**: SD1-SD6

Mapping maintained in vessel config and synced from Labcom.

## Testing

When developing, always test with actual vessels:
- **mv_racer** (M.V Racer) - Primary test vessel
- **mv_october** (MV October) - Has known alert conditions
- **mt_aqua** (MT Aqua)
- **mt_voyager** (MT Voyager)

Run data fetch first to ensure `accubase.sqlite` has test data before testing dashboard features.

## Security Considerations

- Auth tokens stored in config files (exclude from git via `.gitignore`)
- Dashboard uses Flask-Login with session management
- Passwords hashed with bcrypt in `users.sqlite`
- SQL injection protection via parameterized queries
- Environment variable for `SECRET_KEY` in production
- accubase.sqlite opened read-only from dashboard to prevent data corruption
