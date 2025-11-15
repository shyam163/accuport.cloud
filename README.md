# Accuport.cloud

Marine onboard chemical test solutions platform for vessel and fleet management.

## Overview

Accuport is a comprehensive platform for monitoring and managing chemical test data from marine vessels. It consists of two main components:

- **Data Fetcher**: Automated data collection from Labcom's cloud platform
- **Dashboard**: Web-based interface for vessel and fleet managers

## Features

### Data Fetcher
- GraphQL API client for Labcom backend
- SQLite database with comprehensive schema
- Multi-vessel support with individual authentication
- Automatic data synchronization
- Historical data fetching with configurable time ranges
- Quality control and alert generation

### Dashboard
- Role-based access control (Admin, Fleet Manager, Vessel Manager)
- Hierarchical vessel management
- Equipment-specific pages (Boiler Water, Engines, Water Systems)
- Real-time data visualization with Plotly.js
- Alert system for out-of-range parameters
- Date range filtering

## Quick Start

### Data Fetcher Setup

```bash
cd datafetcher
./setup.sh
# Edit config/vessels_config.yaml with your Labcom auth tokens
cd src
python fetch_labcom_data.py
```

### Dashboard Setup

```bash
cd dashbored
./setup.sh
python3 app.py
# Open http://localhost:5000
```

Default login credentials:
- Admin: `admin` / `adminpass`
- Fleet Manager: `fleet1` / `fleet1pass`
- Vessel Manager: `super1` / `super1pass`

## Documentation

- [Developer Guide](DEVELOPER_GUIDE.md) - Architecture and implementation details
- [Data Fetcher README](datafetcher/README.md) - Data collection documentation
- [Dashboard README](dashbored/README.md) - Dashboard usage guide

## Architecture

```
┌─────────────┐
│ Labcom API  │
└──────┬──────┘
       │
       ▼
┌─────────────────┐
│  Data Fetcher   │
└────────┬────────┘
         │
         ▼
   ┌────────────┐
   │ accubase   │ (SQLite)
   │  .sqlite   │
   └─────┬──────┘
         │ (read-only)
         ▼
   ┌────────────┐
   │ Dashboard  │
   └────────────┘
         │
         ▼
   ┌────────────┐
   │  users     │ (SQLite)
   │  .sqlite   │
   └────────────┘
```

## Technology Stack

- **Backend**: Python 3.x, Flask, SQLAlchemy
- **Database**: SQLite
- **API Client**: GraphQL (requests library)
- **Authentication**: Flask-Login, bcrypt
- **Frontend**: Bootstrap 5, Plotly.js
- **Deployment**: Gunicorn (production)

## Security

- Token-based authentication for Labcom API
- Password hashing with bcrypt
- Role-based access control
- SQL injection protection via parameterized queries
- Read-only database access for dashboard
- Environment variable configuration for secrets

## License

Proprietary - Accuport Platform

## Support

For issues or questions, contact the Accuport development team.
