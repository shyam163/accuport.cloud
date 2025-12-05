# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Accuport is a marine onboard chemical test solutions platform for monitoring vessel water systems (boiler water, engines, potable water, etc.). The system consists of two Python applications that share a common SQLite database:

1. **datafetcher**: Fetches chemical test data from Labcom's GraphQL API and stores it in SQLite
2. **dashbored**: Flask web dashboard with role-based access control for viewing and analyzing test data

### Data Flow Architecture

```
Labcom API (GraphQL)
    ↓
datafetcher/labcom_client.py (API client)
    ↓
datafetcher/data_manager.py (stores via SQLAlchemy)
    ↓
accubase.sqlite (vessel measurements - READ-ONLY for dashboard)
    ↓
dashbored/models.py (queries data)
    ↓
dashbored/app.py (Flask routes)

users.sqlite (separate database for user accounts - READ-WRITE for dashboard)
```

**Critical**: `accubase.sqlite` is opened in READ-ONLY mode (`mode=ro`) by the dashboard in `dashbored/database.py:get_accubase_connection()`. Never attempt write operations from the dashboard.

## Common Development Commands

### Data Fetcher (datafetcher/)

```bash
# Setup
cd datafetcher
./setup.sh                                    # Install dependencies + create database

# Fetch data operations (run from datafetcher/src/)
cd src
python fetch_labcom_data.py                   # Fetch all vessels (last 30 days)
python fetch_labcom_data.py --vessel mv_racer # Fetch specific vessel
python fetch_labcom_data.py --days 60         # Custom time range
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
./setup.sh                          # Install dependencies + initialize users database
python3 init_users_db.py            # Initialize users.sqlite with default accounts

# Run development server
python3 app.py                      # Start Flask at http://localhost:5000

# Production deployment
export SECRET_KEY="your-secure-key"
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## Role-Based Access Control

The dashboard implements a three-tier hierarchy for vessel access control:

```
admin (all vessels)
└── fleet_manager (vessels of subordinate vessel managers)
    └── vessel_manager (directly assigned vessels only)
```

**Implementation**: Access control logic is in `dashbored/models.py:get_user_vessels()`. This function determines which vessels a user can see based on their role and the relationships in the `users.sqlite` database.

Default test accounts (from `init_users_db.py`):
- `admin/adminpass` - Administrator (all vessels)
- `fleet1/fleet1pass` - Fleet Manager
- `super1/super1pass` - Vessel Manager (MV Racer, MT Aqua)
- `super2/super2pass` - Vessel Manager (MT Voyager, MV October)

## Database Schema (accubase.sqlite)

Key tables and their relationships (defined in `datafetcher/src/db_schema.py`):

- **vessels** - Vessel information (vessel_id, vessel_name, auth_token)
- **sampling_points** - Equipment test locations (AB1, ME, PW1, etc.)
  - Links to vessel via `vessel_id`
  - Links to Labcom via `labcom_account_id`
  - Unique constraint: `(vessel_id, code)` and `(vessel_id, labcom_account_id)`
- **parameters** - Test parameters (pH, Chloride, Phosphate, etc.)
  - Includes ideal ranges (`ideal_low`, `ideal_high`)
  - Linked to Labcom via `labcom_parameter_id`
- **measurements** - Actual test data
  - Stores both string (`value`) and numeric (`value_numeric`)
  - Quality control field: `ideal_status` (OKAY, TOO LOW, TOO HIGH, CRITICAL)
  - Tracks operator, device, and timestamp
  - Unique constraint: `(vessel_id, labcom_measurement_id)` for deduplication
- **alerts** - Automatic out-of-range detection records
- **parameter_limits** - Custom thresholds per sampling point
- **fetch_logs** - Data fetch operation history with status tracking

### Sampling Point Code System

Standard codes used across vessels (maintained in `config/vessels_config.yaml`):

- **Boiler Water**: AB1, AB2 (Auxiliary Boilers), CB (Composite), HW (Hotwell)
- **Engines**: ME (Main Engine), AE1-AE3 (Auxiliary Engines)
- **Water Systems**: PW1-PW2 (Potable Water), GW (Treated Sewage)
- **Scavenge Drains**: SD1-SD6

## Labcom API Integration

- **Base URL**: `https://backend.labcom.cloud/graphql`
- **Authentication**: Token-based via query parameter (`?token=...`)
- **Client**: `datafetcher/src/labcom_client.py`

Key methods:
- `get_cloud_account()` - Get account info
- `get_accounts()` - Get sampling points for an account
- `get_measurements(account_id, start_date, end_date)` - Fetch test data with date range

Each vessel has its own Labcom auth token stored in `config/vessels_config.yaml`. The fetcher supports multi-vessel operation where each vessel is processed independently with its own authentication.

## Configuration Files

### datafetcher Configuration

Edit `datafetcher/config/vessels_config.yaml`:

```yaml
vessels:
  - vessel_id: "mv_racer"              # Internal identifier
    vessel_name: "M.V Racer"           # Display name
    email: "vessel@example.com"
    auth_token: "LABCOM_AUTH_TOKEN"    # From Labcom backend
    sampling_points:
      - AB1  # Auxiliary boiler 1
      - ME   # Main Engine
```

Each vessel requires:
- Unique `vessel_id` (used throughout the system)
- Labcom auth token (obtained from https://backend.labcom.cloud)
- List of sampling point codes that match the vessel's equipment

## Quality Control and Alert Generation

Automatic alert generation occurs in `datafetcher/src/data_manager.py:store_measurements()`:

1. Compares `value_numeric` against `ideal_low`/`ideal_high` from `parameters` table
2. Sets `ideal_status` field (OKAY, TOO LOW, TOO HIGH, CRITICAL)
3. Creates `Alert` records for out-of-range values
4. Example: Iron-in-Oil below 50 mg/l triggers TOO LOW alert

This happens during data fetch operations, not in the dashboard.

## Flask Application Structure

The dashboard (`dashbored/app.py`) follows a modular pattern:

- **app.py** - Main Flask app with route definitions
- **auth.py** - Authentication logic (bcrypt password hashing)
- **database.py** - Database connection managers (separate connections for accubase and users)
- **models.py** - Data query functions (all accubase queries are here)
- **templates/** - Jinja2 HTML templates with Bootstrap 5
- **static/** - CSS, JS, fonts

Routes are organized by function:
- Authentication routes: `/login`, `/logout`
- Dashboard routes: `/dashboard`, `/vessel/<id>`
- Equipment pages: `/boiler_water`, `/main_engine`, `/aux_engine`, `/water_system`

## Testing with Real Data

Test vessels available in the system:
- **mv_racer** (M.V Racer) - Primary test vessel
- **mv_october** (MV October) - Has known alert conditions
- **mt_aqua** (MT Aqua)
- **mt_voyager** (MT Voyager)

Always run `datafetcher` first to ensure `accubase.sqlite` contains test data before testing dashboard features. The dashboard will show "No data available" if measurements haven't been fetched.

## Important Implementation Notes

### Multi-Vessel Data Fetching

The fetcher (`fetch_labcom_data.py`) can process multiple vessels in a single run:
- Each vessel has independent auth token and Labcom account
- Sampling points are synced from Labcom API when `sync_accounts=True`
- Measurements are deduplicated by `labcom_measurement_id` per vessel
- All operations are logged in `fetch_logs` table with status and error tracking

### Database Access Patterns

- **datafetcher**: Full read-write access to `accubase.sqlite` via SQLAlchemy ORM
- **dashbored**: READ-ONLY access to `accubase.sqlite`, read-write to `users.sqlite`
- All dashboard queries use parameterized SQL to prevent injection attacks
- Connection managers use context managers for proper resource cleanup

### Session Management

Flask-Login manages user sessions:
- Session lifetime: 8 hours (`PERMANENT_SESSION_LIFETIME`)
- Secret key: Set via `SECRET_KEY` environment variable (defaults to dev key)
- User loader: `auth.py:load_user()`
- Login required decorator: `@login_required` on all dashboard routes

## Security Considerations

- Auth tokens stored in config files (must be excluded from git via `.gitignore`)
- Dashboard uses Flask-Login with bcrypt password hashing
- SQL injection protection via parameterized queries throughout
- `accubase.sqlite` opened read-only from dashboard to prevent corruption
- Environment variable for `SECRET_KEY` in production
- Read-only database mode enforced in `database.py`
