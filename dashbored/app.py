"""
Accuport Dashboard - Main Flask Application
Marine chemical test solutions dashboard for vessel and fleet managers
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file, abort
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os
import sys
import io
import subprocess
import logging

from auth import authenticate_user, load_user
from models import (
    get_vessels_by_ids,
    get_vessel_by_id,
    get_sampling_points_by_vessel,
    get_measurements_for_sampling_point,
    get_measurements_by_parameter_names,
    get_measurements_by_equipment_name,
    get_measurements_for_scavenge_drains,
    get_scavenge_drain_data_date_range,
    get_latest_measurements_summary,
    get_alerts_for_vessel,
    get_sampling_point_by_code,
    get_all_measurements_for_troubleshooting,
    get_all_sampling_points_for_troubleshooting,
    get_all_parameters_for_troubleshooting,
    get_parameter_limits,
    get_all_limits_for_equipment,
    recalculate_alerts_for_vessel
)
from admin_models import (
    create_user, get_all_users, update_user_status, change_user_password,
    create_vessel, get_all_vessels_with_tokens, get_vessel_auth_token,
    assign_vessel_to_user, unassign_vessel_from_user, get_user_vessel_assignments,
    assign_vessel_manager_to_fleet_manager, unassign_vessel_manager_from_fleet_manager,
    get_subordinate_vessel_managers, get_unassigned_vessel_managers,
    get_audit_log
)
from vessel_details_models import get_vessel_details, update_vessel_details, get_vessel_details_for_display
from database import get_accubase_connection, get_accubase_write_connection, get_users_connection
from page_report_utils import generate_main_engine_sd_report
import yaml
import re

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# ============================================================================
# VESSEL ID NORMALIZATION
# ============================================================================

def normalize_vessel_name_to_id(vessel_name):
    """
    Normalize vessel name to vessel_id format.

    Handles multiple consecutive spaces by replacing them with a single underscore.

    Args:
        vessel_name: Vessel name (e.g., "M  V  Al  Mahfoza" with multiple spaces)

    Returns:
        Normalized vessel_id (e.g., "m_v_al_mahfoza" with single underscores)

    Examples:
        "M.V Racer" -> "mv_racer"
        "M  V  Al  Mahfoza" -> "m_v_al_mahfoza"
        "MT   Aqua" -> "mt_aqua"
    """
    # Convert to lowercase and remove dots
    normalized = vessel_name.lower().replace('.', '')
    # Replace one or more consecutive spaces with a single underscore
    normalized = re.sub(r'\s+', '_', normalized)
    # Remove leading/trailing underscores
    normalized = normalized.strip('_')
    return normalized

# ============================================================================
# YAML Configuration Update Function
# ============================================================================

def update_vessels_config_yaml(vessel_id, vessel_name, auth_token):
    yaml_path = '/var/www/accuport.cloud/datafetcher/config/vessels_config.yaml'
    try:
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f) or {'vessels': []}
    except FileNotFoundError:
        config = {'vessels': []}
    vessel_id_str = normalize_vessel_name_to_id(vessel_name)
    vessel_found = False
    for vessel in config.get('vessels', []):
        if vessel.get('vessel_id') == vessel_id_str or vessel.get('vessel_name') == vessel_name:
            vessel['vessel_name'] = vessel_name
            vessel['auth_token'] = auth_token
            vessel_found = True
            break
    if not vessel_found:
        new_vessel = {
            'vessel_id': vessel_id_str,
            'vessel_name': vessel_name,
            'email': 'Accu-Port@outlook.com',
            'auth_token': auth_token,
            'sampling_points': ['AB1', 'AB2', 'CB', 'HW', 'AE1', 'AE2', 'AE3', 'ME', 'PW1', 'PW2', 'GW', 'SD1', 'SD2', 'SD3', 'SD4', 'SD5', 'SD6']
        }
        config.setdefault('vessels', []).append(new_vessel)
    with open(yaml_path, 'w') as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    return True



# Context processor to make vessels available to all templates
@app.context_processor
def inject_vessels():
    """Make accessible vessels available to all templates"""
    if hasattr(current_user, 'is_authenticated') and current_user.is_authenticated:
        vessel_ids = current_user.get_accessible_vessels()
        vessels = get_vessels_by_ids(vessel_ids)
        return {'vessels': vessels}
    return {'vessels': []}

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access the dashboard.'

@login_manager.user_loader
def user_loader(user_id):
    """Load user for Flask-Login"""
    return load_user(user_id)



def get_vessel_from_yaml(vessel_name):
    """
    Read vessel data from vessels_config.yaml
    
    Args:
        vessel_name: Name of the vessel
    
    Returns:
        Dict with vessel data from YAML, or empty dict if not found
    """
    yaml_path = '/var/www/accuport.cloud/datafetcher/config/vessels_config.yaml'
    try:
        with open(yaml_path, 'r') as f:
            config = yaml.safe_load(f) or {'vessels': []}
    except FileNotFoundError:
        return {}
    
    # Convert vessel_name to vessel_id format for matching
    vessel_id_str = normalize_vessel_name_to_id(vessel_name)

    # Find vessel by vessel_id or vessel_name
    for vessel in config.get('vessels', []):
        if vessel.get('vessel_id') == vessel_id_str or vessel.get('vessel_name') == vessel_name:
            return {
                'vessel_name': vessel.get('vessel_name'),
                'auth_token': vessel.get('auth_token')
            }
    
    return {}

def user_loader(user_id):
    """Load user for Flask-Login"""
    return load_user(user_id)

# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/')
def index():
    """Redirect to dashboard if logged in, otherwise to login"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = authenticate_user(username, password)

        if user:
            login_user(user, remember=True)
            flash(f'Welcome back, {user.full_name}!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

# ============================================================================
# DASHBOARD ROUTES
# ============================================================================

@app.route('/dashboard')
@login_required
def dashboard():
    """Main dashboard with vessel selector"""
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    # Get selected vessel from query param or session
    selected_vessel_id = request.args.get('vessel_id', type=int)

    if not selected_vessel_id and vessels:
        # Default to first vessel
        selected_vessel_id = vessels[0]['id']

    # For vessel users, lock to their assigned vessel
    if current_user.is_vessel_user() and vessels:
        selected_vessel_id = vessels[0]['id']

    # Store in session
    session['selected_vessel_id'] = selected_vessel_id

    selected_vessel = None
    alerts = []
    latest_measurements = []

    if selected_vessel_id:
        # Check access
        if not current_user.can_access_vessel(selected_vessel_id):
            flash('You do not have access to this vessel', 'danger')
            return redirect(url_for('dashboard'))

        selected_vessel = get_vessel_by_id(selected_vessel_id)
        alerts = get_alerts_for_vessel(selected_vessel_id, unresolved_only=True)
        latest_measurements = get_latest_measurements_summary(selected_vessel_id)

        # Categorize alerts by equipment type
        equipment_alerts = {
            'main_engines': 0,
            'aux_engines': 0,
            'boiler': 0,
            'cooling': 0,
            'potable_water': 0,
            'grey_water': 0,
            'ballast_water': 0,
            'egcs': 0
        }

        for alert in alerts:
            sampling_point = alert.get('sampling_point_name', '').upper()

            # Main Engines
            if 'ME' in sampling_point or 'MAIN ENGINE' in sampling_point:
                equipment_alerts['main_engines'] += 1
            # Auxiliary Engines
            elif 'AE' in sampling_point or 'AUX ENGINE' in sampling_point:
                equipment_alerts['aux_engines'] += 1
            # Boiler
            elif any(keyword in sampling_point for keyword in ['BOILER', 'AB', 'HOTWELL', 'EGE']):
                equipment_alerts['boiler'] += 1
            # Central Cooling System
            elif 'COOLING' in sampling_point or 'HT' in sampling_point or 'LT' in sampling_point:
                equipment_alerts['cooling'] += 1
            # Potable Water
            elif 'POTABLE' in sampling_point or 'DRINKING' in sampling_point:
                equipment_alerts['potable_water'] += 1
            # Grey Water
            elif 'SEWAGE' in sampling_point or 'GREY' in sampling_point or 'GRAY' in sampling_point:
                equipment_alerts['grey_water'] += 1
            # Ballast Water
            elif 'BALLAST' in sampling_point:
                equipment_alerts['ballast_water'] += 1
            # EGCS (Scrubber)
            elif 'EGCS' in sampling_point or 'SCRUBBER' in sampling_point:
                equipment_alerts['egcs'] += 1

        # TEMPORARY: Troubleshooting data
        troubleshooting_measurements = get_all_measurements_for_troubleshooting(selected_vessel_id, limit=500)
        troubleshooting_sampling_points = get_all_sampling_points_for_troubleshooting(selected_vessel_id)
        troubleshooting_parameters = get_all_parameters_for_troubleshooting()

    return render_template('dashboard.html',
                          vessels=vessels,
                          selected_vessel=selected_vessel,
                          alerts=alerts,
                          equipment_alerts=equipment_alerts if selected_vessel else {},
                          latest_measurements=latest_measurements,
                          troubleshooting_measurements=troubleshooting_measurements if selected_vessel else [],
                          troubleshooting_sampling_points=troubleshooting_sampling_points if selected_vessel else [],
                          troubleshooting_parameters=troubleshooting_parameters if selected_vessel else [],
                          user=current_user)

# ============================================================================
# EQUIPMENT PAGES
# ============================================================================

@app.route('/equipment/boiler-water')
@login_required
def boiler_water():
    """Boiler Water equipment page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range (default: last 30 days)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    # Get date range from request if provided
    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # Boiler water parameters to fetch
    # Based on pagesparameteres file
    boiler_params = [
        'Phosphate',
        'Alkalinity P',
        'Alkalinity M',
        'Chloride',
        'pH',
        'Conductivity'
    ]

    # Get measurements for auxiliary boilers (vessel-agnostic by name)
    boiler1_data = get_measurements_by_equipment_name(vessel_id, 'AB1 Aux Boiler 1', boiler_params, start_date, end_date)
    boiler2_data = get_measurements_by_equipment_name(vessel_id, 'AB2 Aux Boiler 2', boiler_params, start_date, end_date)

    # Get alerts for boiler systems only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if any(keyword in alert.get('sampling_point_name', '').upper()
                     for keyword in ['BOILER', 'AB', 'HOTWELL', 'EGE'])]

    return render_template('boiler_water.html',
                          vessels=vessels,
                          vessel=vessel,
                          boiler1_data=boiler1_data,
                          boiler2_data=boiler2_data,
                          alerts=alerts,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'))

@app.route('/equipment/boiler-water-multi')
@login_required
def boiler_water_multi():
    """Multi-select Boiler Water page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # Boiler water parameters
    boiler_params = [
        'Phosphate',
        'Alkalinity P',
        'Alkalinity M',
        'Chloride',
        'pH',
        'Conductivity',
        'DEHA',
        'Hydrazine',
    ]

    # Get data for all 4 boilers with boiler_id added
    boiler_equipment_names = {
        'Aux1': 'AB1 Aux Boiler 1',
        'Aux2': 'AB2 Aux Boiler 2',
        'EGE': 'CB Composite Boiler',
        'Hotwell': 'HW Hot Well'
    }

    boiler_data = []
    for boiler_id, equipment_name in boiler_equipment_names.items():
        data_raw = get_measurements_by_equipment_name(vessel_id, equipment_name, boiler_params, start_date, end_date) or []
        for item in data_raw:
            item_copy = dict(item)
            item_copy['boiler_id'] = boiler_id
            boiler_data.append(item_copy)

    # Get alerts for boiler systems only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if any(keyword in alert.get('sampling_point_name', '').upper()
                     for keyword in ['BOILER', 'AB', 'HOTWELL', 'EGE'])]

    # Get parameter limits from users.sqlite
    aux_boiler_limits = get_all_limits_for_equipment('AUX BOILER & EGE')
    hotwell_limits = get_all_limits_for_equipment('HOTWELL')

    # Combine into single dict for template
    all_limits = {
        'AUX BOILER & EGE': aux_boiler_limits,
        'HOTWELL': hotwell_limits
    }

    vessel_specs = get_vessel_details_for_display(vessel_id, 'boiler')
    return render_template('boiler_water_multi.html',
                          vessels=vessels,
                          vessel=vessel,
                          boiler_data=boiler_data,
                          alerts=alerts,
                          limits=all_limits,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime("%Y-%m-%d"),
                          vessel_specs=vessel_specs)


@app.route('/equipment/central-cooling')
@login_required
def central_cooling():
    """Central Cooling System page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # Cooling water parameters
    cooling_params = [
        'pH',
        'Chloride',
        'Nitrite',
    ]

    # Get data for HT and LT Cooling Water with cooling_id added
    cooling_equipment_names = {
        'HT': 'HT Cooling Water',
        'LT': 'LT Cooling Water'
    }

    cooling_data = []
    for cooling_id, equipment_name in cooling_equipment_names.items():
        data_raw = get_measurements_by_equipment_name(vessel_id, equipment_name, cooling_params, start_date, end_date) or []
        for item in data_raw:
            item_copy = dict(item)
            item_copy['cooling_id'] = cooling_id
            cooling_data.append(item_copy)

    # Get alerts for cooling systems only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if any(keyword in alert.get('sampling_point_name', '').upper()
                     for keyword in ['COOLING', 'HT', 'LT'])]

    # Get parameter limits from users.sqlite
    cooling_limits = get_all_limits_for_equipment('HT & LT COOLING WATER')

    vessel_specs = get_vessel_details_for_display(vessel_id, 'water_systems')
    return render_template('central_cooling.html',
                          vessels=vessels,
                          vessel=vessel,
                          cooling_data=cooling_data,
                          alerts=alerts,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime("%Y-%m-%d"),
                          vessel_specs=vessel_specs,
                          limits=cooling_limits)

@app.route('/equipment/main-engines')
@login_required
def main_engines_multi():
    """Multi-select Main Engines page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # Parameters
    cooling_params = ['Nitrite', 'pH', 'Chloride']
    lube_params = ['TBN', 'Water Content', 'Viscosity']
    scavenge_params = ['Iron', 'Base']

    # Get data for main engines (ME Main Engine) with engine_id added
    cooling_data_raw = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', cooling_params, start_date, end_date) or []
    lube_data_raw = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', lube_params, start_date, end_date) or []

    # Get scavenge drain data from separate SD sampling points
    scavenge_data_raw = get_measurements_for_scavenge_drains(vessel_id, scavenge_params, start_date, end_date) or []

    # Add engine_id to data for multi-engine display
    # Since there's one ME Main Engine, we'll duplicate the data for ME1 and ME2
    cooling_data = []
    lube_data = []
    for me_num in [1, 2]:
        engine_id = f'ME{me_num}'
        for item in cooling_data_raw:
            item_copy = dict(item)
            item_copy['engine_id'] = engine_id
            cooling_data.append(item_copy)
        for item in lube_data_raw:
            item_copy = dict(item)
            item_copy['engine_id'] = engine_id
            lube_data.append(item_copy)

    # For scavenge drain, assign all cylinders to both ME1 and ME2
    # This allows the user to select which engine to view
    scavenge_data = []
    for me_num in [1, 2]:
        engine_id = f'ME{me_num}'
        for item in scavenge_data_raw:
            item_copy = dict(item)
            item_copy['engine_id'] = engine_id
            scavenge_data.append(item_copy)

    # Get alerts for main engines only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if 'ME' in alert.get('sampling_point_name', '') or
                 'MAIN ENGINE' in alert.get('sampling_point_name', '').upper() or
                 'Unit' in alert.get('sampling_point_name', '')]

    # Get vessel specifications for display
    vessel_specs = get_vessel_details_for_display(vessel_id, 'main_engines')
    
    # Get scavenge drain data availability
    scavenge_data_range = get_scavenge_drain_data_date_range(vessel_id)
    # Get parameter limits for cooling water
    cooling_limits = get_all_limits_for_equipment('HT & LT COOLING WATER')
    
    return render_template('main_engine_multi.html',
                          vessels=vessels,
                          vessel=vessel,
                          cooling_data=cooling_data,
                          lube_data=lube_data,
                          scavenge_data=scavenge_data,
                          alerts=alerts,
                          vessel_specs=vessel_specs,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'),
                          scavenge_data_range=scavenge_data_range,
                          limits=cooling_limits)

@app.route('/equipment/main-engine/<int:engine_num>')
@login_required
def main_engine(engine_num):
    """Main Engine equipment page (1 or 2)"""
    vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # Parameters
    cooling_params = ['Nitrite', 'pH', 'Chloride']
    lube_params = ['TBN', 'Water Content', 'Viscosity']
    scavenge_params = ['Iron', 'Base']  # For scatter plot

    # Use main engine data (vessel-agnostic by name)
    cooling_data = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', cooling_params, start_date, end_date)
    lube_data = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', lube_params, start_date, end_date)

    # Scavenge drain data comes from separate SD sampling points
    scavenge_data = get_measurements_for_scavenge_drains(vessel_id, scavenge_params, start_date, end_date)

    return render_template('main_engine.html',
                          vessel=vessel,
                          engine_num=engine_num,
                          cooling_data=cooling_data,
                          lube_data=lube_data,
                          scavenge_data=scavenge_data,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'))

@app.route('/equipment/aux-engine/<int:engine_num>')
@login_required
def aux_engine(engine_num):
    """Auxiliary Engine equipment page (1-4)"""
    vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # Parameters
    cooling_params = ['Nitrite', 'pH', 'Chloride']
    lube_params = ['TBN', 'BaseNumber']

    # Get data for specific aux engine by name (vessel-agnostic)
    engine_name = f'AE{engine_num} Aux Engine'
    cooling_data = get_measurements_by_equipment_name(vessel_id, engine_name, cooling_params, start_date, end_date)
    lube_data = get_measurements_by_equipment_name(vessel_id, engine_name, lube_params, start_date, end_date)

    return render_template('aux_engine.html',
                          vessel=vessel,
                          engine_num=engine_num,
                          cooling_data=cooling_data,
                          lube_data=lube_data,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'))

@app.route('/equipment/aux-engines')
@login_required
def aux_engines():
    """Multi-select Auxiliary Engines page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # Parameters
    cooling_params = ['Nitrite', 'pH', 'Chloride']
    lube_params = ['TBN', 'BaseNumber']

    # Fetch data for ALL aux engines (1-4)
    all_engines_data = {}
    for engine_num in range(1, 4):
        engine_name = f'AE{engine_num} Aux Engine'
        all_engines_data[engine_num] = {
            'cooling': get_measurements_by_equipment_name(vessel_id, engine_name, cooling_params, start_date, end_date) or [],
            'lube': get_measurements_by_equipment_name(vessel_id, engine_name, lube_params, start_date, end_date) or []
        }

    # Get alerts for aux engines only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if 'AE' in alert.get('sampling_point_name', '') or
                 'AUX ENGINE' in alert.get('sampling_point_name', '').upper()]

    vessel_specs = get_vessel_details_for_display(vessel_id, 'aux_engines')
    # Get parameter limits for cooling water
    cooling_limits = get_all_limits_for_equipment('HT & LT COOLING WATER')
    
    return render_template('aux_engines_multi.html',
                          vessels=vessels,
                          vessel=vessel,
                          all_engines_data=all_engines_data,
                          alerts=alerts,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime("%Y-%m-%d"),
                          vessel_specs=vessel_specs,
                          limits=cooling_limits)

@app.route('/equipment/potable-water')
@login_required
def potable_water():
    """Potable Water equipment page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # Potable water parameters
    water_params = [
        'pH', 'pH-Value', 'pH (pHPCATC)',
        'Alkalinity M', 'Alkalinity M (HR tab)',
        'Turbidity', 'Turbidity-NTU',
        'TDS', 'Total Dissolved Solids',
        'Hardn.- Total', 'Hardn.- Total (HR)', 'Hardn.- Total (LR)',
        'Conductivity',
        'Chloride', 'Chloride (Liq)',
        'Chlorine free', 'Chlorine total', 'Chlorine combined',
        'Sulphate', 'Sulphate (tab)',
        'Iron', 'Iron (LR)',
        'Lead', 'Nickel', 'Nickel (HR liq)', 'Nickel (HR tab)',
        'Zinc', 'Cadmium',
        'Copper', 'Copper free', 'Copper total', 'Copper combined',
        'Permanganate', 'Permanganate TT',
        'E. coli', 'Temperature'
    ]

    # Get data for both PW1 and PW2
    pw_data = []

    pw1_data = get_measurements_by_equipment_name(vessel_id, 'PW1 Potable Water', water_params, start_date, end_date)
    for measurement in pw1_data:
        measurement['pw_id'] = 'PW1'
        pw_data.append(measurement)

    pw2_data = get_measurements_by_equipment_name(vessel_id, 'PW2 Potable Water', water_params, start_date, end_date)
    for measurement in pw2_data:
        measurement['pw_id'] = 'PW2'
        pw_data.append(measurement)

    # Get alerts for potable water only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if 'POTABLE' in alert.get('sampling_point_name', '').upper() or
                 'DRINKING' in alert.get('sampling_point_name', '').upper()]

    # Get parameter limits for potable water
    limits = get_all_limits_for_equipment('POTABLE WATER')

    vessel_specs = get_vessel_details_for_display(vessel_id, 'water_systems')
    return render_template('potable_water_multi.html',
                          vessels=vessels,
                          vessel=vessel,
                          pw_data=pw_data,
                          alerts=alerts,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'),
                          vessel_specs=vessel_specs,
                          limits=limits)

@app.route('/equipment/treated-sewage')
@login_required
def treated_sewage():
    """Treated Sewage Water equipment page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    water_params = ['pH', 'COD', 'Chlorine', 'Suspended Solids', 'Turbidity', 'E. coli', 'Permanganate Value']

    # Get treated sewage data by name (vessel-agnostic)
    water_data = get_measurements_by_equipment_name(vessel_id, 'GW Treated Sewage', water_params, start_date, end_date)

    # Get alerts for grey/sewage water only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if 'SEWAGE' in alert.get('sampling_point_name', '').upper() or
                 'GREY' in alert.get('sampling_point_name', '').upper() or
                 'GRAY' in alert.get('sampling_point_name', '').upper()]

    # Get parameter limits for sewage
    limits = get_all_limits_for_equipment('SEWAGE')

    vessel_specs = get_vessel_details_for_display(vessel_id, 'water_systems')
    return render_template('water_system.html',
                          vessels=vessels,
                          vessel=vessel,
                          system_type='Treated Sewage Water',
                          water_data=water_data,
                          alerts=alerts,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'),
                          vessel_specs=vessel_specs,
                          limits=limits)

@app.route('/equipment/ballast-water')
@login_required
def ballast_water():
    """Ballast Water equipment page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    water_params = [
        'Total Viable Count', 'Vibrio Cholerae', 'Enterococci', 'E. coli',
        'Chlorine Dioxide', 'Free Chlorine', 'Ozone', 'Peracetic Acid',
        'Hydrogen Peroxide'
    ]

    # Get ballast water data by name (vessel-agnostic)
    # Note: Ballast water may not exist for all vessels
    water_data = get_measurements_by_equipment_name(vessel_id, 'Ballast Water', water_params, start_date, end_date)

    # Get alerts for ballast water only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if 'BALLAST' in alert.get('sampling_point_name', '').upper()]

    vessel_specs = get_vessel_details_for_display(vessel_id, 'water_systems')
    return render_template('water_system.html',
                          vessels=vessels,
                          vessel=vessel,
                          system_type='Ballast Water',
                          water_data=water_data,
                          alerts=alerts,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'),
                          vessel_specs=vessel_specs,
                          limits={})

@app.route('/equipment/egcs')
@login_required
def egcs():
    """EGCS (Exhaust Gas Cleaning System) equipment page"""
    # Get vessel_id from query param or session
    vessel_id = request.args.get('vessel_id', type=int)
    if not vessel_id:
        vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

    # Update session with selected vessel
    session['selected_vessel_id'] = vessel_id

    # Get all accessible vessels for dropdown
    vessel_ids = current_user.get_accessible_vessels()
    vessels = get_vessels_by_ids(vessel_ids)

    vessel = get_vessel_by_id(vessel_id)

    # Date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    if request.args.get('start_date'):
        start_date = datetime.strptime(request.args.get('start_date'), '%Y-%m-%d')
    if request.args.get('end_date'):
        end_date = datetime.strptime(request.args.get('end_date'), '%Y-%m-%d')

    # EGCS parameters
    water_params = [
        'pH', 'PAH', 'Turbidity', 'Nitrate',
        'Discharge Rate', 'Washwater pH', 'Washwater Temperature'
    ]

    # Get EGCS data by name (vessel-agnostic)
    # Note: EGCS may not exist for all vessels, data may be empty until configured
    water_data = get_measurements_by_equipment_name(vessel_id, 'EGCS', water_params, start_date, end_date)

    # Get alerts for EGCS only
    all_alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True) or []
    alerts = [alert for alert in all_alerts
              if 'EGCS' in alert.get('sampling_point_name', '').upper() or
                 'SCRUBBER' in alert.get('sampling_point_name', '').upper()]

    vessel_specs = get_vessel_details_for_display(vessel_id, 'water_systems')
    return render_template('water_system.html',
                          vessels=vessels,
                          vessel=vessel,
                          system_type='EGCS',
                          water_data=water_data,
                          alerts=alerts,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'),
                          vessel_specs=vessel_specs,
                          limits={})


# ============================================================================
# ADMIN/FLEET MANAGER DECORATORS
# ============================================================================

def admin_required(f):
    """Decorator for admin-only routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not current_user.is_admin():
            flash('Access denied. Admin privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def manager_required(f):
    """Decorator for admin/fleet manager routes"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if not (current_user.is_admin() or current_user.is_fleet_manager()):
            flash('Access denied. Manager privileges required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# ============================================================================
# ADMIN/FLEET MANAGER DASHBOARD ROUTES
# ============================================================================


@app.route('/admin/vessels/test-sync/<int:vessel_id>', methods=['POST'])
@admin_required
def admin_test_vessel_sync(vessel_id):
    """Test sync for a vessel with given auth token"""
    try:
        data = request.get_json()
        vessel_name = data.get('vessel_name')
        auth_token = data.get('auth_token')

        if not vessel_name or not auth_token:
            return jsonify({'success': False, 'error': 'Vessel name and auth token are required'}), 400

        # Get vessel from database to get vessel_id string
        vessel = get_vessel_by_id(vessel_id)
        if not vessel:
            return jsonify({'success': False, 'error': 'Vessel not found'}), 404

        vessel_str_id = vessel['vessel_id']

        # Temporarily update the database with the new auth token for testing
        with get_accubase_write_connection() as acc_conn:
            acc_cursor = acc_conn.cursor()
            # Get original auth token
            acc_cursor.execute('SELECT auth_token FROM vessels WHERE id = ?', (vessel_id,))
            original_token = acc_cursor.fetchone()
            original_token = original_token['auth_token'] if original_token else None

            # Set test auth token
            acc_cursor.execute(
                'UPDATE vessels SET auth_token = ? WHERE id = ?',
                (auth_token, vessel_id)
            )
            acc_conn.commit()

        try:
            # Run sync test (only fetch for 1 day to be quick)
            app.logger.info(f"Testing sync for vessel: {vessel_str_id}")
            success, output = run_sync_command(vessel_str_id, days='1')

            if success:
                # Parse output to get connection info
                connected_as = "Unknown"
                sampling_points = 0

                for line in output.split('\n'):
                    if 'Connected as:' in line:
                        connected_as = line.split('Connected as:')[1].strip()
                    elif 'Found' in line and 'sampling points' in line:
                        try:
                            sampling_points = int(line.split('Found')[1].split('sampling points')[0].strip())
                        except:
                            pass

                return jsonify({
                    'success': True,
                    'connected_as': connected_as,
                    'sampling_points': sampling_points,
                    'message': 'Sync test successful'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': output or 'Sync command failed'
                }), 500

        finally:
            # Restore original auth token
            if original_token:
                with get_accubase_write_connection() as acc_conn:
                    acc_cursor = acc_conn.cursor()
                    acc_cursor.execute(
                        'UPDATE vessels SET auth_token = ? WHERE id = ?',
                        (original_token, vessel_id)
                    )
                    acc_conn.commit()

    except Exception as e:
        app.logger.error(f"Test sync error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/vessels/delete/<int:vessel_id>', methods=['POST'])
@admin_required
def admin_delete_vessel(vessel_id):
    """Delete a vessel and all associated data"""
    try:
        # Get vessel info before deletion
        vessel = get_vessel_by_id(vessel_id)
        if not vessel:
            return jsonify({'success': False, 'error': 'Vessel not found'}), 404

        vessel_name = vessel.get('vessel_name', 'Unknown')
        vessel_str_id = vessel.get('vessel_id', '')

        app.logger.info(f"Admin {current_user.username} deleting vessel: {vessel_name} (ID: {vessel_id})")

        # Delete from accubase.sqlite
        with get_accubase_write_connection() as acc_conn:
            acc_cursor = acc_conn.cursor()

            # Delete measurements
            acc_cursor.execute('DELETE FROM measurements WHERE vessel_id = ?', (vessel_id,))
            measurements_deleted = acc_cursor.rowcount

            # Delete sampling points
            acc_cursor.execute('DELETE FROM sampling_points WHERE vessel_id = ?', (vessel_id,))
            sampling_points_deleted = acc_cursor.rowcount

            # Delete alerts
            acc_cursor.execute('DELETE FROM alerts WHERE vessel_id = ?', (vessel_id,))
            alerts_deleted = acc_cursor.rowcount

            # Delete vessel
            acc_cursor.execute('DELETE FROM vessels WHERE id = ?', (vessel_id,))

            acc_conn.commit()

        # Delete from users.sqlite
        with get_users_connection() as users_conn:
            users_cursor = users_conn.cursor()

            # Delete vessel details
            users_cursor.execute('DELETE FROM vessel_details WHERE vessel_id = ?', (vessel_id,))

            # Delete auth tokens
            users_cursor.execute('DELETE FROM vessel_auth_tokens WHERE vessel_id = ?', (vessel_id,))

            # Delete vessel assignments
            users_cursor.execute('DELETE FROM vessel_assignments WHERE vessel_id = ?', (vessel_id,))
            assignments_deleted = users_cursor.rowcount

            # Log the deletion in audit log
            users_cursor.execute('''
                INSERT INTO admin_audit_log (admin_user_id, action_type, action_details, target_vessel_id)
                VALUES (?, ?, ?, ?)
            ''', (current_user.id, 'DELETE_VESSEL', f'Deleted vessel: {vessel_name} ({vessel_str_id})', vessel_id))

            users_conn.commit()

        app.logger.info(f"Vessel deleted successfully: {vessel_name} - {measurements_deleted} measurements, {sampling_points_deleted} sampling points, {alerts_deleted} alerts, {assignments_deleted} user assignments")

        return jsonify({
            'success': True,
            'message': f'Vessel "{vessel_name}" deleted successfully',
            'stats': {
                'measurements': measurements_deleted,
                'sampling_points': sampling_points_deleted,
                'alerts': alerts_deleted,
                'assignments': assignments_deleted
            }
        })

    except Exception as e:
        app.logger.error(f"Error deleting vessel: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/admin/vessels/edit/<int:vessel_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_vessel_details(vessel_id):
    """Admin page to edit vessel equipment specifications"""
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        flash('Vessel not found', 'danger')
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        form_data = {
            'vessel_name': request.form.get('vessel_name', '').strip(),
            'vessel_type': request.form.get('vessel_type', '').strip(),
            'year_of_build': request.form.get('year_of_build', '').strip(),
            'imo_number': request.form.get('imo_number', '').strip(),
            'company_name': request.form.get('company_name', '').strip(),
            'me1_make': request.form.get('me1_make', '').strip(),
            'me1_model': request.form.get('me1_model', '').strip(),
            'me1_serial': request.form.get('me1_serial', '').strip(),
            'me1_system_oil': request.form.get('me1_system_oil', '').strip(),
            'me1_cylinder_oil': request.form.get('me1_cylinder_oil', '').strip(),
            'me1_fuel1': request.form.get('me1_fuel1', '').strip(),
            'me1_fuel2': request.form.get('me1_fuel2', '').strip(),
            'me2_make': request.form.get('me2_make', '').strip(),
            'me2_model': request.form.get('me2_model', '').strip(),
            'me2_serial': request.form.get('me2_serial', '').strip(),
            'me2_system_oil': request.form.get('me2_system_oil', '').strip(),
            'me2_cylinder_oil': request.form.get('me2_cylinder_oil', '').strip(),
            'me2_fuel1': request.form.get('me2_fuel1', '').strip(),
            'me2_fuel2': request.form.get('me2_fuel2', '').strip(),
            'ae_system_oil': request.form.get('ae_system_oil', '').strip(),
            'ae_fuel1': request.form.get('ae_fuel1', '').strip(),
            'ae_fuel2': request.form.get('ae_fuel2', '').strip(),
            'ae1_make': request.form.get('ae1_make', '').strip(),
            'ae1_model': request.form.get('ae1_model', '').strip(),
            'ae1_serial': request.form.get('ae1_serial', '').strip(),
            'ae2_make': request.form.get('ae2_make', '').strip(),
            'ae2_model': request.form.get('ae2_model', '').strip(),
            'ae2_serial': request.form.get('ae2_serial', '').strip(),
            'ae3_make': request.form.get('ae3_make', '').strip(),
            'ae3_model': request.form.get('ae3_model', '').strip(),
            'ae3_serial': request.form.get('ae3_serial', '').strip(),
            'boiler_fuel1': request.form.get('boiler_fuel1', '').strip(),
            'boiler_fuel2': request.form.get('boiler_fuel2', '').strip(),
            'ab1_make': request.form.get('ab1_make', '').strip(),
            'ab1_model': request.form.get('ab1_model', '').strip(),
            'ab1_serial': request.form.get('ab1_serial', '').strip(),
            'ab2_make': request.form.get('ab2_make', '').strip(),
            'ab2_model': request.form.get('ab2_model', '').strip(),
            'ab2_serial': request.form.get('ab2_serial', '').strip(),
            'ege_make': request.form.get('ege_make', '').strip(),
            'ege_model': request.form.get('ege_model', '').strip(),
            'ege_serial': request.form.get('ege_serial', '').strip(),
            'bwt_chemical_manufacturer': request.form.get('bwt_chemical_manufacturer', '').strip(),
            'bwt_chemicals_in_use': request.form.get('bwt_chemicals_in_use', '').strip(),
            'cwt_chemical_manufacturer': request.form.get('cwt_chemical_manufacturer', '').strip(),
            'cwt_chemicals_in_use': request.form.get('cwt_chemicals_in_use', '').strip(),
            'bwts_make': request.form.get('bwts_make', '').strip(),
            'bwts_model': request.form.get('bwts_model', '').strip(),
            'bwts_serial': request.form.get('bwts_serial', '').strip(),
            'egcs_make': request.form.get('egcs_make', '').strip(),
            'egcs_model': request.form.get('egcs_model', '').strip(),
            'egcs_serial': request.form.get('egcs_serial', '').strip(),
            'egcs_type': request.form.get('egcs_type', '').strip(),
            'stp_make': request.form.get('stp_make', '').strip(),
            'stp_model': request.form.get('stp_model', '').strip(),
            'stp_serial': request.form.get('stp_serial', '').strip(),
            'stp_capacity': request.form.get('stp_capacity', '').strip(),
            'hotwell_deha': request.form.get('hotwell_deha', '').strip(),
            'hotwell_hydrazine': request.form.get('hotwell_hydrazine', '').strip(),
            'auth_token': request.form.get('auth_token', '').strip(),
        }
        # Validate required fields
        if not form_data.get('vessel_name') or not form_data.get('auth_token'):
            flash('Vessel Name and Auth Token are required fields', 'danger')
            vessel_details = get_vessel_details(vessel_id) or {}
            return render_template('admin_vessel_edit.html', vessel=vessel, details=vessel_details, user=current_user)

        form_data = {k: (v if v != '' else None) for k, v in form_data.items()}
        if update_vessel_details(vessel_id, form_data, current_user.id):
            # Update vessel_name and auth_token in vessels table (accubase.sqlite)
            # Database is now the single source of truth for sync configuration
            try:
                with get_accubase_write_connection() as acc_conn:
                    acc_cursor = acc_conn.cursor()
                    acc_cursor.execute(
                        'UPDATE vessels SET vessel_name = ?, auth_token = ? WHERE id = ?',
                        (form_data.get('vessel_name'), form_data.get('auth_token'), vessel_id)
                    )
                    acc_conn.commit()
            except Exception as e:
                app.logger.error(f"Failed to update vessel in vessels table: {e}")
                flash(f'Vessel details updated but vessel config update failed: {e}', 'warning')

            flash(f'Vessel specifications for {vessel.get("name")} updated successfully!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Failed to update vessel specifications', 'danger')

    # GET request - load data from database
    vessel_details = get_vessel_details(vessel_id) or {}

    # Get vessel_name and auth_token from vessels table (accubase.sqlite)
    # Database is the single source of truth
    try:
        with get_accubase_connection() as acc_conn:
            acc_cursor = acc_conn.cursor()
            acc_cursor.execute(
                'SELECT vessel_name, auth_token FROM vessels WHERE id = ?',
                (vessel_id,)
            )
            row = acc_cursor.fetchone()
            if row:
                if not vessel_details.get('vessel_name'):
                    vessel_details['vessel_name'] = row['vessel_name']
                if not vessel_details.get('auth_token'):
                    vessel_details['auth_token'] = row['auth_token']
    except Exception as e:
        app.logger.error(f"Failed to load vessel config from database: {e}")

    return render_template('admin_vessel_edit.html', vessel=vessel, details=vessel_details, user=current_user)

@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard - manage users, vessels, and assignments"""
    all_users = get_all_users()
    all_vessels = get_all_vessels_with_tokens()
    recent_audit_log = get_audit_log(limit=50)
    unassigned_managers = get_unassigned_vessel_managers()

    return render_template('admin_dashboard.html',
                          all_users=all_users,
                          all_vessels=all_vessels,
                          audit_log=recent_audit_log,
                          unassigned_managers=unassigned_managers,
                          user=current_user)

@app.route('/fleet-manager')
@manager_required
def fleet_manager_dashboard():
    """Fleet manager dashboard - manage vessel managers and assignments"""
    if current_user.is_admin():
        vessel_managers = get_all_users(role_filter='vessel_manager')
        all_vessels = get_all_vessels_with_tokens()
    else:
        vessel_managers = get_subordinate_vessel_managers(current_user.id)
        vessel_ids = set()
        for vm in vessel_managers:
            vessel_ids.update([v['id'] for v in get_user_vessel_assignments(vm['id'])])
        all_vessels = [v for v in get_all_vessels_with_tokens() if v['id'] in vessel_ids]
    
    unassigned_managers = get_unassigned_vessel_managers()
    
    return render_template('fleet_manager_dashboard.html',
                          vessel_managers=vessel_managers,
                          all_vessels=all_vessels,
                          unassigned_managers=unassigned_managers,
                          user=current_user)

# ============================================================================
# ADMIN API ENDPOINTS
# ============================================================================

@app.route('/api/admin/create-user', methods=['POST'])
@admin_required
def api_create_user():
    """Create a new user"""
    data = request.form
    result = create_user(
        username=data.get('username'),
        password=data.get('password'),
        full_name=data.get('full_name'),
        email=data.get('email'),
        role=data.get('role'),
        created_by_user_id=current_user.id
    )
    
    if result:
        flash(f'User {result["username"]} created successfully!', 'success')
    else:
        flash('Failed to create user. Username may already exist.', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/api/admin/create-vessel', methods=['POST'])
@admin_required
def api_create_vessel():
    """Create a new vessel"""
    data = request.form
    vessel_name = data.get('vessel_name')

    # Auto-generate vessel_id_code from vessel_name using normalized logic
    vessel_id_code = normalize_vessel_name_to_id(vessel_name)

    result = create_vessel(
        vessel_id_code=vessel_id_code,
        vessel_name=vessel_name,
        email=data.get('email'),
        created_by_user_id=current_user.id
    )

    if result:
        flash(f'Vessel {result["vessel_name"]} created! Vessel ID: {vessel_id_code}, Auth Token: {result["auth_token"]}', 'success')
    else:
        flash('Failed to create vessel.', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route('/api/admin/assign-vessel', methods=['POST'])
@manager_required
def api_assign_vessel():
    """Assign a vessel to a user"""
    data = request.form
    user_id = int(data.get('user_id'))
    vessel_id = int(data.get('vessel_id'))
    
    if assign_vessel_to_user(user_id, vessel_id, current_user.id):
        flash('Vessel assigned successfully!', 'success')
    else:
        flash('Failed to assign vessel.', 'danger')
    
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/api/admin/unassign-vessel', methods=['POST'])
@manager_required
def api_unassign_vessel():
    """Remove vessel assignment"""
    data = request.form
    user_id = int(data.get('user_id'))
    vessel_id = int(data.get('vessel_id'))
    
    if unassign_vessel_from_user(user_id, vessel_id, current_user.id):
        flash('Vessel unassigned successfully!', 'success')
    else:
        flash('Failed to unassign vessel.', 'danger')
    
    return redirect(request.referrer or url_for('admin_dashboard'))

@app.route('/api/admin/assign-hierarchy', methods=['POST'])
@admin_required
def api_assign_hierarchy():
    """Assign vessel manager to fleet manager"""
    data = request.form
    fleet_manager_id = int(data.get('fleet_manager_id'))
    vessel_manager_id = int(data.get('vessel_manager_id'))
    
    if assign_vessel_manager_to_fleet_manager(fleet_manager_id, vessel_manager_id, current_user.id):
        flash('Hierarchy assigned successfully!', 'success')
    else:
        flash('Failed to assign hierarchy.', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/api/admin/toggle-user-status', methods=['POST'])
@admin_required
def api_toggle_user_status():
    """Toggle user active status"""
    data = request.form
    user_id = int(data.get('user_id'))
    is_active = int(data.get('is_active'))
    
    if update_user_status(user_id, is_active, current_user.id):
        status = 'activated' if is_active else 'deactivated'
        flash(f'User {status} successfully!', 'success')
    else:
        flash('Failed to update user status.', 'danger')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/api/admin/change-user-password', methods=['POST'])
@admin_required
def api_change_user_password():
    """Change user password to a specified password"""
    data = request.form
    user_id = int(data.get('user_id'))
    new_password = data.get('new_password')

    if not new_password:
        flash('Password cannot be empty', 'danger')
        return redirect(url_for('admin_dashboard'))

    result = change_user_password(user_id, new_password, current_user.id)

    if result['success']:
        flash(f'Password changed successfully for user: {result["username"]}', 'success')
    else:
        flash(f'Failed to change password: {result.get("error", "Unknown error")}', 'danger')

    return redirect(url_for('admin_dashboard'))

# ============================================================================
# API ENDPOINTS (for AJAX data fetching)
# ============================================================================

@app.route('/api/vessel/<int:vessel_id>/sampling-points')
@login_required
def api_sampling_points(vessel_id):
    """Get sampling points for a vessel"""
    if not current_user.can_access_vessel(vessel_id):
        return jsonify({'error': 'Access denied'}), 403

    sampling_points = get_sampling_points_by_vessel(vessel_id)
    return jsonify(sampling_points)


@app.route('/api/reports/main-engine-sd-pdf')
@login_required
def api_main_engine_sd_pdf():
    """Generate PDF report for Main Engine Scavenge Drain page"""
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    selected_engines = request.args.getlist('engines')
    selected_cylinders = request.args.getlist('cylinders')

    # Validate vessel access
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)

    # Parse dates
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = datetime.now() - timedelta(days=30)

        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = datetime.now()
    except ValueError:
        abort(400, "Invalid date format. Use YYYY-MM-DD")

    # Generate PDF
    try:
        buffer, filename = generate_main_engine_sd_report(
            vessel_id, start_date, end_date, selected_engines, selected_cylinders
        )

        return send_file(
            buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        app.logger.error(f"Error generating Main Engine SD PDF: {str(e)}")
        abort(500, f"Error generating PDF: {str(e)}")



@app.route('/api/reports/boiler-water-pdf')
@login_required
def api_boiler_water_pdf():
    """Generate PDF report for Boiler Water page using main generator"""
    from generate_vessel_report import generate_report_bytes
    from models import get_vessel_by_id
    
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        abort(404, 'Vessel not found')
    vessel_name = vessel['vessel_name']
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
    except ValueError:
        abort(400, 'Invalid date format')
    
    try:
        pdf_bytes = generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=['boiler'])
        filename = f"{vessel_name.replace(' ', '_')}_Boiler_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f'Error generating Boiler PDF: {str(e)}')
        abort(500, f'Error generating PDF: {str(e)}')


@app.route('/api/reports/aux-engines-pdf')
@login_required
def api_aux_engines_pdf():
    """Generate PDF report for Aux Engines page using main generator"""
    from generate_vessel_report import generate_report_bytes
    from models import get_vessel_by_id
    
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        abort(404, 'Vessel not found')
    vessel_name = vessel['vessel_name']
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
    except ValueError:
        abort(400, 'Invalid date format')
    
    try:
        pdf_bytes = generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=['aux_engines'])
        filename = f"{vessel_name.replace(' ', '_')}_AuxEngines_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f'Error generating Aux Engines PDF: {str(e)}')
        abort(500, f'Error generating PDF: {str(e)}')


@app.route('/api/reports/main-engines-lube-pdf')
@login_required
def api_main_engines_lube_pdf():
    """Generate PDF report for Main Engines page using main generator"""
    from generate_vessel_report import generate_report_bytes
    from models import get_vessel_by_id
    
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        abort(404, 'Vessel not found')
    vessel_name = vessel['vessel_name']
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
    except ValueError:
        abort(400, 'Invalid date format')
    
    try:
        pdf_bytes = generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=['main_engines'])
        filename = f"{vessel_name.replace(' ', '_')}_MainEngines_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f'Error generating Main Engines PDF: {str(e)}')
        abort(500, f'Error generating PDF: {str(e)}')


@app.route('/api/reports/potable-water-pdf')
@login_required
def api_potable_water_pdf():
    """Generate PDF report for Potable Water page using main generator"""
    from generate_vessel_report import generate_report_bytes
    from models import get_vessel_by_id
    
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        abort(404, 'Vessel not found')
    vessel_name = vessel['vessel_name']
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
    except ValueError:
        abort(400, 'Invalid date format')
    
    try:
        pdf_bytes = generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=['potable_water'])
        filename = f"{vessel_name.replace(' ', '_')}_PotableWater_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f'Error generating Potable Water PDF: {str(e)}')
        abort(500, f'Error generating PDF: {str(e)}')


@app.route('/api/reports/central-cooling-pdf')
@login_required
def api_central_cooling_pdf():
    """Generate PDF report for Central Cooling page using main generator"""
    from generate_vessel_report import generate_report_bytes
    from models import get_vessel_by_id
    
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        abort(404, 'Vessel not found')
    vessel_name = vessel['vessel_name']
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
    except ValueError:
        abort(400, 'Invalid date format')
    
    try:
        pdf_bytes = generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=['central_cooling'])
        filename = f"{vessel_name.replace(' ', '_')}_CentralCooling_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f'Error generating Central Cooling PDF: {str(e)}')
        abort(500, f'Error generating PDF: {str(e)}')


@app.route('/api/reports/treated-sewage-pdf')
@login_required
def api_treated_sewage_pdf():
    """Generate PDF report for Treated Sewage page using main generator"""
    from generate_vessel_report import generate_report_bytes
    from models import get_vessel_by_id
    
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        abort(404, 'Vessel not found')
    vessel_name = vessel['vessel_name']
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
    except ValueError:
        abort(400, 'Invalid date format')
    
    try:
        pdf_bytes = generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=['treated_sewage'])
        filename = f"{vessel_name.replace(' ', '_')}_TreatedSewage_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f'Error generating Treated Sewage PDF: {str(e)}')
        abort(500, f'Error generating PDF: {str(e)}')


@app.route('/api/reports/ballast-water-pdf')
@login_required
def api_ballast_water_pdf():
    """Generate PDF report for Ballast Water page using main generator"""
    from generate_vessel_report import generate_report_bytes
    from models import get_vessel_by_id
    
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        abort(404, 'Vessel not found')
    vessel_name = vessel['vessel_name']
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
    except ValueError:
        abort(400, 'Invalid date format')
    
    try:
        pdf_bytes = generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=['ballast_water'])
        filename = f"{vessel_name.replace(' ', '_')}_BallastWater_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f'Error generating Ballast Water PDF: {str(e)}')
        abort(500, f'Error generating PDF: {str(e)}')


@app.route('/api/reports/egcs-pdf')
@login_required
def api_egcs_pdf():
    """Generate PDF report for EGCS page using main generator"""
    from generate_vessel_report import generate_report_bytes
    from models import get_vessel_by_id
    
    vessel_id = request.args.get('vessel_id', type=int)
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        abort(403)
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        abort(404, 'Vessel not found')
    vessel_name = vessel['vessel_name']
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d') if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') if end_date_str else datetime.now()
    except ValueError:
        abort(400, 'Invalid date format')
    
    try:
        pdf_bytes = generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=['egcs'])
        filename = f"{vessel_name.replace(' ', '_')}_EGCS_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        return send_file(io.BytesIO(pdf_bytes), mimetype='application/pdf', as_attachment=True, download_name=filename)
    except Exception as e:
        app.logger.error(f'Error generating EGCS PDF: {str(e)}')
        abort(500, f'Error generating PDF: {str(e)}')


# ============================================================================
# SYNC ENDPOINTS
# ============================================================================
# ============================================================================

def run_sync_command(vessel_str_id, days='1825'):
    """Helper to run the sync script for a vessel"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.abspath(os.path.join(base_dir, '../datafetcher/src/fetch_and_store.py'))
    config_path = os.path.abspath(os.path.join(base_dir, '../datafetcher/config/vessels_config.yaml'))
    db_path = os.path.abspath(os.path.join(base_dir, '../datafetcher/data/accubase.sqlite'))

    cmd = [
        sys.executable,
        script_path,
        vessel_str_id,
        str(days), # Number of days to fetch
        "--config", config_path,
        "--db", db_path
    ]
    
    try:
        # app.logger might not be available in this scope easily if strictly separated, 
        # but here it is in the same file.
        # app.logger.info(f"Running sync command: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            check=True
        )
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr
    except Exception as e:
        return False, str(e)

@app.route('/sync_vessel_data', methods=['POST'])
@login_required
def sync_vessel_data():
    """
    Trigger data fetch for the current vessel
    """
    vessel_id = session.get('selected_vessel_id')
    if not vessel_id:
        return jsonify({'success': False, 'message': 'No vessel selected'}), 400

    # Get vessel details to get the string ID (e.g., 'mv_racer')
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        return jsonify({'success': False, 'message': 'Vessel not found'}), 404
    
    vessel_str_id = vessel['vessel_id']
    
    app.logger.info(f"Syncing single vessel: {vessel_str_id}")
    success, output = run_sync_command(vessel_str_id)
    
    if success:
        return jsonify({
            'success': True, 
            'message': 'Data sync completed successfully',
            'details': output
        })
    else:
        app.logger.error(f"Sync failed: {output}")
        return jsonify({
            'success': False, 
            'message': 'Data sync failed',
            'error': output
        }), 500

@app.route('/sync_all_vessels', methods=['POST'])
@login_required
def sync_all_vessels():
    """
    Trigger data fetch for ALL accessible vessels
    """
    # Get all accessible vessels
    vessel_ids = current_user.get_accessible_vessels()
    if not vessel_ids:
        return jsonify({'success': False, 'message': 'No vessels found'}), 404
        
    vessels = get_vessels_by_ids(vessel_ids)
    
    results = []
    success_count = 0
    
    for vessel in vessels:
        vessel_name = vessel['vessel_name']
        vessel_str_id = vessel['vessel_id']
        
        app.logger.info(f"Syncing {vessel_name} ({vessel_str_id})...")
        
        success, output = run_sync_command(vessel_str_id)
        
        results.append({
            'vessel_name': vessel_name,
            'success': success,
            'message': 'Synced successfully' if success else f'Failed: {output[:100]}...'
        })
        
        if success:
            success_count += 1
            
    return jsonify({
        'success': True,
        'total': len(vessels),
        'success_count': success_count,
        'results': results
    })



# ============================================================================
# REPORT GENERATION API
# ============================================================================

@app.route('/api/generate-report', methods=['POST'])
@login_required
def api_generate_report():
    """Generate PDF report for specified vessel"""
    from datetime import datetime
    from generate_vessel_report import generate_report_bytes, AVAILABLE_SECTIONS
    
    data = request.get_json()
    
    # Get vessel_id from request body or fall back to session
    vessel_id = data.get('vessel_id') or session.get('selected_vessel_id')
    if vessel_id:
        vessel_id = int(vessel_id)
    
    if not vessel_id:
        return jsonify({'error': 'No vessel selected'}), 400
    
    if not current_user.can_access_vessel(vessel_id):
        return jsonify({'error': 'Access denied'}), 403
    
    try:
        data = request.get_json()
        
        # Parse dates
        start_date = datetime.strptime(data.get('start_date'), '%Y-%m-%d')
        end_date = datetime.strptime(data.get('end_date'), '%Y-%m-%d')
        
        # Get selected sections (default to all if not specified)
        sections = data.get('sections', list(AVAILABLE_SECTIONS.keys()))
        
        # Get vessel info
        vessel = get_vessel_by_id(vessel_id)
        if not vessel:
            return jsonify({'error': 'Vessel not found'}), 404
        
        # Generate report
        pdf_bytes = generate_report_bytes(
            vessel_id=vessel_id,
            vessel_name=vessel['vessel_name'],
            start_date=start_date,
            end_date=end_date,
            selected_sections=sections
        )
        
        # Create filename
        filename = f"{vessel['vessel_name'].replace(' ', '_')}_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
        
        # Return as downloadable file
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except ValueError as e:
        return jsonify({'error': f'Invalid date format: {str(e)}'}), 400
    except Exception as e:
        app.logger.error(f"Report generation failed: {str(e)}")
        return jsonify({'error': f'Report generation failed: {str(e)}'}), 500


# ERROR HANDLERS
# ============================================================================


@app.route('/recalculate_alerts', methods=['POST'])
@login_required
def recalculate_vessel_alerts():
    """
    Recalculate alerts for current vessel using new parameter limits from users.sqlite
    """
    vessel_id = session.get('selected_vessel_id')
    if not vessel_id:
        return jsonify({'success': False, 'message': 'No vessel selected'}), 400
    
    try:
        result = recalculate_alerts_for_vessel(vessel_id)
        return jsonify({
            'success': True,
            'message': f"Recalculated alerts: {result['alerts_created']} created, {result['alerts_resolved']} resolved",
            'details': result
        })
    except Exception as e:
        app.logger.error(f"Alert recalculation failed: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Alert recalculation failed: {str(e)}'
        }), 500

@app.errorhandler(404)
def not_found(error):
    return render_template('error.html', error_code=404, error_message='Page not found'), 404

@app.errorhandler(403)
def forbidden(error):
    return render_template('error.html', error_code=403, error_message='Access forbidden'), 403

@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html', error_code=500, error_message='Internal server error'), 500

# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
