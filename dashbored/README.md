# Accuport.cloud Dashboard

Marine onboard chemical test solutions dashboard for vessel and fleet managers.

## Features

- **Role-based Access Control**: Vessel managers, Fleet managers, and Admin accounts
- **Hierarchical Vessel Management**: Fleet managers see vessels of subordinate vessel managers
- **Equipment-specific Pages**: Boiler Water, Main Engines, Auxiliary Engines, Water Systems
- **Data Visualization**: Time-series graphs with Plotly.js, tabular data, scatter plots
- **Date Range Filtering**: Default 30-day view with customizable date ranges
- **Alert System**: Real-time alerts for parameters outside normal ranges

## User Hierarchy

```
admin (Administrator - all vessels)

fleet1 (Fleet Manager)
  ├── super1 (Vessel Manager)
  │   ├── MV Racer
  │   └── MT Aqua
  └── super2 (Vessel Manager)
      ├── MT Voyager
      └── MV October
```

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Add Missing Vessels to Database

```bash
python3 add_vessels.py
```

This will add placeholder entries for MV Racer, MT Aqua, and MT Voyager to accubase.sqlite.

### 3. Initialize Users Database

```bash
python3 init_users_db.py
```

This creates users.sqlite with the following accounts:

| Username | Password    | Role            | Vessels                    |
|----------|-------------|-----------------|----------------------------|
| super1   | super1pass  | Vessel Manager  | MV Racer, MT Aqua          |
| super2   | super2pass  | Vessel Manager  | MT Voyager, MV October     |
| fleet1   | fleet1pass  | Fleet Manager   | All vessels under super1 & super2 |
| admin    | adminpass   | Administrator   | All vessels                |

## Running the Dashboard

```bash
python3 app.py
```

The dashboard will be available at: **http://localhost:5000**

## Usage

### 1. Login
- Navigate to http://localhost:5000
- Enter your username and password
- You'll be redirected to the dashboard

### 2. Select Vessel
- Use the vessel selector dropdown on the dashboard
- Only vessels you have access to will be shown

### 3. View Equipment Data
- Click on equipment cards (Boiler Water, Main Engines, etc.)
- View time-series graphs and tabular data
- Use date range filters to customize the view

### 4. Equipment Pages

#### Boiler Water
- Graphical time-series for: Phosphate, pH, Alkalinity, Chloride, etc.
- Color-coded status indicators (Green = OK, Red = Out of range)
- Shows data for both Auxiliary Boilers

#### Main Engines (1 & 2)
- Cooling Water: Nitrite, pH, Chloride (graphs)
- Lubricating Oil: TBN, Water Content, Viscosity (table)
- Scavenge Drain Oil: Iron-BN scatter plot (per cylinder)

#### Auxiliary Engines (1-4)
- Cooling Water parameters (graphs)
- Lubricating Oil parameters (table)

#### Water Systems
- Potable Water: 17 parameters (table)
- Treated Sewage: 6 parameters (table)
- Ballast Water: 9 parameters (table)

## Database Structure

### accubase.sqlite (READ-ONLY)
Contains vessel measurement data:
- `vessels`: Vessel information
- `measurements`: Chemical test measurements
- `parameters`: Test parameter definitions
- `sampling_points`: Equipment sampling locations
- `alerts`: Out-of-range alerts

### users.sqlite (READ-WRITE)
Contains user management data:
- `users`: User accounts and roles
- `vessel_assignments`: User-to-vessel assignments
- `manager_hierarchy`: Fleet manager-to-vessel manager relationships

## File Structure

```
dashbored/
├── app.py                  # Main Flask application
├── auth.py                 # Authentication logic
├── database.py             # Database connections
├── models.py               # Data queries
├── init_users_db.py        # User database setup
├── add_vessels.py          # Add vessels to accubase
├── requirements.txt        # Python dependencies
├── templates/              # HTML templates
│   ├── base.html
│   ├── login.html
│   ├── dashboard.html
│   ├── boiler_water.html
│   ├── main_engine.html
│   ├── aux_engine.html
│   ├── water_system.html
│   └── error.html
└── static/
    ├── css/
    │   └── custom.css
    └── js/
        └── (charts.js if needed)
```

## Security Notes

- Change default passwords in production
- Use HTTPS in production
- Set strong SECRET_KEY in environment variable
- accubase.sqlite is opened in READ-ONLY mode
- Passwords are hashed with bcrypt
- SQL injection protection via parameterized queries

## Production Deployment

For production deployment:

1. Set environment variables:
```bash
export SECRET_KEY="your-secure-random-key"
```

2. Use a production WSGI server (e.g., Gunicorn):
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

3. Configure reverse proxy (nginx/Apache) with HTTPS

4. Set up automatic backups of users.sqlite

## Troubleshooting

### "No vessels found"
- Run `python3 add_vessels.py` to add vessel entries
- Check that accubase.sqlite exists and is readable

### "Login failed"
- Verify users.sqlite exists: run `python3 init_users_db.py`
- Check username and password are correct

### "No data available"
- The data fetcher needs to populate measurement data
- Check that vessel IDs match between databases

## Future Enhancements

- Export to Excel/PDF
- Email alerts for critical parameters
- Admin panel for user management
- Multi-tenant support
- Mobile responsive improvements
- Data trend analysis and predictions

## License

Copyright 2025 Accuport. All rights reserved.
