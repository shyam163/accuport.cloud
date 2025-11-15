"""
Accuport Dashboard - Main Flask Application
Marine chemical test solutions dashboard for vessel and fleet managers
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
import os

from auth import authenticate_user, load_user
from models import (
    get_vessels_by_ids,
    get_vessel_by_id,
    get_sampling_points_by_vessel,
    get_measurements_for_sampling_point,
    get_measurements_by_parameter_names,
    get_measurements_by_equipment_name,
    get_measurements_for_scavenge_drains,
    get_latest_measurements_summary,
    get_alerts_for_vessel,
    get_sampling_point_by_code,
    get_all_measurements_for_troubleshooting,
    get_all_sampling_points_for_troubleshooting,
    get_all_parameters_for_troubleshooting
)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access the dashboard.'

@login_manager.user_loader
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

        # TEMPORARY: Troubleshooting data
        troubleshooting_measurements = get_all_measurements_for_troubleshooting(selected_vessel_id, limit=500)
        troubleshooting_sampling_points = get_all_sampling_points_for_troubleshooting(selected_vessel_id)
        troubleshooting_parameters = get_all_parameters_for_troubleshooting()

    return render_template('dashboard.html',
                          vessels=vessels,
                          selected_vessel=selected_vessel,
                          alerts=alerts,
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
    vessel_id = session.get('selected_vessel_id')

    if not vessel_id or not current_user.can_access_vessel(vessel_id):
        flash('Please select a vessel first', 'warning')
        return redirect(url_for('dashboard'))

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
        'P-Alkalinity',
        'M-Alkalinity',
        'Chloride',
        'pH',
        'Hydrazine',
        'DEHA',
        'Conductivity'
    ]

    # Get measurements for auxiliary boilers (vessel-agnostic by name)
    boiler1_data = get_measurements_by_equipment_name(vessel_id, 'AB1 Aux Boiler', boiler_params, start_date, end_date)
    boiler2_data = get_measurements_by_equipment_name(vessel_id, 'AB2 Aux Boiler', boiler_params, start_date, end_date)

    return render_template('boiler_water.html',
                          vessel=vessel,
                          boiler1_data=boiler1_data,
                          boiler2_data=boiler2_data,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'))

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
    scavenge_params = ['Iron-in-Oil', 'BaseNumber']  # For scatter plot

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

@app.route('/equipment/potable-water')
@login_required
def potable_water():
    """Potable Water equipment page"""
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

    # Potable water parameters (tabular display)
    water_params = [
        'pH', 'Total Alkalinity', 'Turbidity', 'Total Dissolved Solids',
        'Total Hardness CaCO3', 'Conductivity', 'Chlorine', 'Sulphate',
        'Total Chlorine', 'Iron', 'Lead', 'Nickel', 'Zinc', 'Cadmium',
        'Copper', 'Permanganate Value', 'E. coli'
    ]

    # Get potable water data by name (vessel-agnostic)
    water_data = get_measurements_by_equipment_name(vessel_id, 'PW1 Potable Water', water_params, start_date, end_date)

    return render_template('water_system.html',
                          vessel=vessel,
                          system_type='Potable Water',
                          water_data=water_data,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'))

@app.route('/equipment/treated-sewage')
@login_required
def treated_sewage():
    """Treated Sewage Water equipment page"""
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

    water_params = ['pH', 'COD', 'Free Chlorine', 'Turbidity', 'E. coli', 'Permanganate Value']

    # Get treated sewage data by name (vessel-agnostic)
    water_data = get_measurements_by_equipment_name(vessel_id, 'GW Treated Sewage', water_params, start_date, end_date)

    return render_template('water_system.html',
                          vessel=vessel,
                          system_type='Treated Sewage Water',
                          water_data=water_data,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'))

@app.route('/equipment/ballast-water')
@login_required
def ballast_water():
    """Ballast Water equipment page"""
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

    water_params = [
        'Total Viable Count', 'Vibrio Cholerae', 'Enterococci', 'E. coli',
        'Chlorine Dioxide', 'Free Chlorine', 'Ozone', 'Peracetic Acid',
        'Hydrogen Peroxide'
    ]

    # Get ballast water data by name (vessel-agnostic)
    # Note: Ballast water may not exist for all vessels
    water_data = get_measurements_by_equipment_name(vessel_id, 'Ballast Water', water_params, start_date, end_date)

    return render_template('water_system.html',
                          vessel=vessel,
                          system_type='Ballast Water',
                          water_data=water_data,
                          start_date=start_date.strftime('%Y-%m-%d'),
                          end_date=end_date.strftime('%Y-%m-%d'))

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

# ============================================================================
# ERROR HANDLERS
# ============================================================================

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
    app.run(debug=True, host='0.0.0.0', port=5000)
