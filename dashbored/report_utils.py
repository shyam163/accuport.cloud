"""
Utility functions for PDF report generation
Uses Matplotlib with website-matching color schemes for ARM64 compatibility
"""
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from matplotlib.ticker import MaxNLocator
from datetime import datetime
import io
from collections import defaultdict

def is_valid_limit(ideal_low, ideal_high):
    """Check if limits are valid database values, not sentinel values like -1"""
    if ideal_low is None or ideal_high is None:
        return False
    try:
        low = float(ideal_low)
        high = float(ideal_high)
        # Reject -1 sentinel values and invalid ranges
        if low < 0 or high < 0:
            return False
        if high < low:
            return False
        return True
    except (ValueError, TypeError):
        return False




def normalize_param_name_for_limits(param_name):
    """
    Normalize database parameter names to match limit lookup keys in users.sqlite

    Maps: "Phosphate (HR tab). ortho" -> "PHOSPHATE"
          "pH-Universal (liq)" -> "PH"
          etc.
    """
    if not param_name:
        return ""

    name = param_name.upper()

    # Direct mappings for common parameters
    if 'PHOSPHAT' in name:
        return 'PHOSPHATE'
    # FIX: Alkalinity M/P detection - check for " M " or " M(" patterns
    if 'ALKALINITY' in name:
        if ' M ' in name or ' M(' in name or name.endswith(' M'):
            return 'ALKALINITY M'
        elif ' P ' in name or ' P(' in name or name.endswith(' P'):
            return 'ALKALINITY P'
        return 'TOTAL ALKALINITY (AS CACO3)'
    if 'CHLORIDE' in name:
        return 'CHLORIDE'
    if 'PH' in name or 'PH-' in name:
        return 'PH'
    if 'CONDUCTIV' in name:
        return 'CONDUCTIVITY'
    if 'DEHA' in name:
        return 'DEHA'
    if 'HYDRAZINE' in name:
        return 'HYDRAZINE'
    if 'NITRITE' in name:
        return 'NITRITE'
    if 'HARDNESS' in name or 'HARDN' in name:
        if 'TOTAL' in name or 'AS CACO' in name:
            return 'TOTAL HARDNESS (AS CACO3)'
        return 'TOTAL HARDNESS'
    if 'COD' in name:
        return 'COD'
    if 'BOD' in name:
        return 'BOD'
    if 'TURBIDITY' in name:
        return 'TURBIDITY'
    if 'SUSPENDED' in name or 'TSS' in name:
        return 'TOTAL SUSPENDED SOLIDS'
    if 'CHLORINE' in name:
        if 'FREE' in name:
            return 'FREE CHLORINE'
        if 'TOTAL' in name:
            return 'TOTAL CHLORINE'
        if 'COMBINED' in name:
            return 'COMBINED CHLORINE'
        return 'TOTAL CHLORINE'
    if 'COPPER' in name or 'CU' in name:
        return 'COPPER (CU)'
    if 'IRON' in name and 'OIL' not in name:
        return 'IRON (FE)'
    if 'NICKEL' in name or 'NI' in name:
        return 'NICKEL (NI)'
    if 'ZINC' in name or 'ZN' in name:
        return 'ZINC (ZN)'
    if 'SULPHATE' in name or 'SULFATE' in name:
        return 'SULPHATE (SO4)'
    if 'TDS' in name or 'DISSOLVED SOLID' in name:
        return 'TOTAL DISSOLVED SOLIDS (TDS)'

    # Return original if no match
    return name.strip()


def get_limits_for_pdf(equipment_type, parameter_name):
    """
    Get limits from users.sqlite parameter_limits table

    Args:
        equipment_type: One of 'AUX BOILER & EGE', 'HOTWELL', 'HT & LT COOLING WATER',
                        'POTABLE WATER', 'SEWAGE'
        parameter_name: Database parameter name (will be normalized)

    Returns:
        (lower_limit, upper_limit) tuple, or (None, None) if not found
    """
    from models import get_all_limits_for_equipment

    limits = get_all_limits_for_equipment(equipment_type)
    if not limits:
        return None, None

    # Normalize the parameter name
    normalized = normalize_param_name_for_limits(parameter_name)

    # Try exact match first
    if normalized in limits:
        return limits[normalized]['lower_limit'], limits[normalized]['upper_limit']

    # Try fuzzy match - check if normalized is contained in any key or vice versa
    for key, val in limits.items():
        if normalized in key or key in normalized:
            return val['lower_limit'], val['upper_limit']

    return None, None


from PIL import Image
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Chart configuration
CHART_WIDTH_INCHES = 3.0
CHART_HEIGHT_INCHES = 2.2
SCATTER_HEIGHT_INCHES = 2.2
DPI = 120  # Higher DPI for better quality

# Website-matching color schemes
BOILER_COLORS = {
    'Aux1': '#0d6efd',   # Blue
    'Aux2': '#198754',   # Green
    'EGE': '#dc3545',    # Red
    'Hotwell': '#ffc107' # Yellow
}

MAIN_ENGINE_COLORS = {
    'ME1': '#dc3545',  # Red
    'ME2': '#0d6efd'   # Blue
}

AUX_ENGINE_COLORS = {
    1: '#2196F3',  # Blue
    2: '#4CAF50',  # Green
    3: '#FF9800'   # Orange
}

# Generic color palette for other sections
GENERIC_COLORS = ['#0d6efd', '#198754', '#dc3545', '#ffc107', '#6f42c1', '#fd7e14', '#20c997', '#6c757d']


def compact_label(label):
    """
    Compact long labels to shorter format
    """
    import re
    label = str(label)
    lbl = label.lower()
    
    # Preserve comparison titles (e.g., "Iron vs BN")
    if ' vs ' in lbl:
        return label
    
    # Parameter name shortenings - check most specific first
    if 'conductiv' in lbl or 'ec' in lbl:
        return 'Conductivity'
    if 'phosphat' in lbl or 'ortho' in lbl:
        return 'Phosphate'
    if 'chloride' in lbl:
        return 'Chloride'
    if 'alkalinity' in lbl or 'alk' in lbl:
        if ' p' in lbl or '-p' in lbl or 'p-alk' in lbl:
            return 'Alkalinity P'
        elif ' m' in lbl or '-m' in lbl or 'm-alk' in lbl:
            return 'Alkalinity M'
        return 'Alkalinity'
    if 'hardness' in lbl:
        return 'Hardness'
    if 'iron' in lbl or 'fe' in lbl:
        return 'Iron'
    if 'base number' in lbl or 'tbn' in lbl or 'bn' in lbl:
        return 'BN'
    if 'nitrite' in lbl:
        return 'Nitrite'
    if 'nitrate' in lbl:
        return 'Nitrate'
    if 'silica' in lbl:
        return 'Silica'
    if 'sulphate' in lbl or 'sulfate' in lbl:
        return 'Sulphate'
    if 'viscosity' in lbl:
        return 'Viscosity'
    if 'turbidity' in lbl:
        return 'Turbidity'
    if 'coliform' in lbl or 'coli' in lbl:
        return 'Coliform'
    if 'tss' in lbl:
        return 'TSS'
    if 'cod' in lbl:
        return 'COD'
    if 'tds' in lbl:
        return 'TDS'
    if 'chlorine' in lbl:
        return 'Chlorine'
    if 'ph' == lbl or lbl.startswith('ph ') or ' ph' in lbl:
        return 'pH'
    
    # Main Engine patterns
    if 'ME' in label.upper() and 'UNIT' in label.upper():
        me_match = re.search(r'ME\s*(\d+)', label, re.IGNORECASE)
        unit_match = re.search(r'UNIT\s*(\d+)', label, re.IGNORECASE)
        if me_match and unit_match:
            return f"ME{me_match.group(1)} U{unit_match.group(1)}"
    
    # Scavenge drain patterns
    if 'SD' in label.upper():
        me_match = re.search(r'ME\s*(\d*)', label, re.IGNORECASE)
        unit_match = re.search(r'UNIT\s*(\d+)', label, re.IGNORECASE)
        if unit_match:
            me_num = me_match.group(1) if me_match and me_match.group(1) else '1'
            return f"ME{me_num} U{unit_match.group(1)}"
    
    # Aux Boiler patterns
    if 'AUX' in label.upper() and 'BOILER' in label.upper():
        num_match = re.search(r'(\d+)', label)
        if num_match:
            return f"Aux{num_match.group(1)}"
    
    # Aux Engine patterns
    if 'AE' in label.upper() or ('AUX' in label.upper() and 'ENGINE' in label.upper()):
        num_match = re.search(r'(\d+)', label)
        if num_match:
            return f"AE{num_match.group(1)}"
    
    # If short enough, return as is
    if len(label) <= 12:
        return label
    
    return label[:12]

def get_unit_label(title):
    """Infer unit label from chart title"""
    title_lower = title.lower()
    if "conductivity" in title_lower:
        return "μS/cm"
    if "phosphate" in title_lower:
        return "ppm"
    if "chloride" in title_lower:
        return "ppm"
    if "alkalinity" in title_lower:
        return "mg/L"
    if "hardness" in title_lower:
        return "ppm"
    if "iron" in title_lower:
        return "ppm"
    if "base number" in title_lower or "bn" in title_lower:
        return "mg KOH/g"
    if "ph" in title_lower:
        return "pH"
    if "tds" in title_lower:
        return "ppm"
    if "nitrate" in title_lower or "nitrite" in title_lower:
        return "mg/L"
    if "viscosity" in title_lower:
        return "cSt"
    if "water" in title_lower:
        return "ppm"
    return ""




def create_line_chart_by_unit(data, title, color_scheme=None, ideal_low=None, ideal_high=None, unit_field='unit_id', equipment_type=None):
    """
    Create a line chart with multiple units/equipment, matching website styling.
    
    Args:
        data: List of dicts with measurement records (must have unit_field, parameter_name, measurement_date, value_numeric)
        title: Chart title
        color_scheme: Dict mapping unit_id to color (e.g., BOILER_COLORS)
        ideal_low: Lower ideal range for shading
        ideal_high: Upper ideal range for shading
        unit_field: Field name for unit identifier (e.g., 'unit_id', 'boiler_id', 'engine_id')
    
    Returns:
        BytesIO object containing PNG image
    """
    if not data:
        return None
    
    if color_scheme is None:
        color_scheme = {}
    
    # Organize data by unit
    units_data = defaultdict(list)
    for record in data:
        unit_id = record.get(unit_field, 'Unknown')
        date_str = record.get('measurement_date', '')
        value = record.get('value_numeric')
        
        if value is not None and date_str:
            try:
                date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                units_data[unit_id].append((date_obj, float(value)))
            except:
                continue
    
    if not units_data:
        return None
    
    # Create figure with website-matching style
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Add limit lines if provided (single legend entry)
    if is_valid_limit(ideal_low, ideal_high):
        ax.axhline(y=ideal_low, color='#dc3545', linestyle='--', linewidth=1.5, alpha=0.7, label='Limits', zorder=2)
        ax.axhline(y=ideal_high, color='#dc3545', linestyle='--', linewidth=1.5, alpha=0.7, zorder=2)
    
    # Plot each unit with website colors
    color_idx = 0
    for unit_id, points in sorted(units_data.items()):
        points.sort(key=lambda x: x[0])
        dates, values = zip(*points)
        
        # Get color from scheme or use generic
        color = color_scheme.get(unit_id, GENERIC_COLORS[color_idx % len(GENERIC_COLORS)])
        
        ax.plot(dates, values, marker='o', linestyle='-', linewidth=2,
                markersize=6, color=color, label=compact_label(unit_id), zorder=3)
        color_idx += 1
    
    # Website-matching formatting
    # Title with limits shown below
    ax.set_title(compact_label(title), fontsize=12, fontweight='bold', pad=12, color='#2c3e50')
    if is_valid_limit(ideal_low, ideal_high):
        ax.text(0.5, 1.01, f'Limits: {ideal_low:.1f} - {ideal_high:.1f}', transform=ax.transAxes,
                fontsize=7, color='#888888', ha='center', va='bottom')
    #ax.set_xlabel('Date', fontsize=8, color='#6c757d')  # Removed - intuitive
    ax.set_ylabel(get_unit_label(title), fontsize=7, color='#6c757d')
    
    # Grid styling to match website
    ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.5, color='#000000')
    ax.set_axisbelow(True)
    
    # Legend at top
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=6, columnspacing=0.8)
    
    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    fig.autofmt_xdate(rotation=30, ha='right')
    ax.tick_params(axis='x', labelsize=6)
    
    # Clean spine styling
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('#dee2e6')
    
    # plt.tight_layout()  # Disabled - using bbox_inches=tight
    
    # Convert to BytesIO
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


def create_multi_line_chart(data, parameter_names, title, ideal_low=None, ideal_high=None, equipment_type=None):
    """
    Create a chart with multiple parameters (different lines for each parameter)
    
    Args:
        data: List of measurement records
        parameter_names: List of parameter patterns to include
        title: Chart title
        ideal_low: Lower limit line value
        ideal_high: Upper limit line value
    
    Returns:
        BytesIO object containing PNG image
    """
    if not data:
        return None
    
    # Organize data by parameter and extract limits if not provided
    param_data = defaultdict(list)
    found_low, found_high = None, None
    for record in data:
        param_name = record.get('parameter_name', '')
        date_str = record.get('measurement_date', '')
        value = record.get('value_numeric')
        
        if value is None or not date_str:
            continue
        
        # Extract limits from first record with limits
        if found_low is None and record.get('ideal_low') is not None:
            found_low = record.get('ideal_low')
            found_high = record.get('ideal_high')
        
        # Match parameter
        for pattern in parameter_names:
            if pattern.lower() in param_name.lower():
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    param_data[param_name].append((date_obj, float(value)))
                except:
                    pass
                break
    
    if not param_data:
        return None
    
    # Use found limits if not explicitly provided
    if ideal_low is None and found_low is not None:
        ideal_low = float(found_low)
    if ideal_high is None and found_high is not None:
        ideal_high = float(found_high)
    
    # Create figure
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    # Add limit lines if available (single legend entry)
    if is_valid_limit(ideal_low, ideal_high):
        ax.axhline(y=ideal_low, color='#dc3545', linestyle='--', linewidth=1.5, alpha=0.7, label='Limits', zorder=2)
        ax.axhline(y=ideal_high, color='#dc3545', linestyle='--', linewidth=1.5, alpha=0.7, zorder=2)
    
    color_idx = 0
    for param_name, points in sorted(param_data.items()):
        points.sort(key=lambda x: x[0])
        dates, values = zip(*points)
        
        ax.plot(dates, values, marker='o', linestyle='-', linewidth=2,
                markersize=5, color=GENERIC_COLORS[color_idx % len(GENERIC_COLORS)],
                label=compact_label(param_name), zorder=3)
        color_idx += 1
    
    # Title with limits shown below
    ax.set_title(compact_label(title), fontsize=12, fontweight='bold', pad=12, color='#2c3e50')
    if is_valid_limit(ideal_low, ideal_high):
        ax.text(0.5, 1.01, f'Limits: {ideal_low:.1f} - {ideal_high:.1f}', transform=ax.transAxes,
                fontsize=7, color='#888888', ha='center', va='bottom')
    #ax.set_xlabel('Date', fontsize=8, color='#6c757d')  # Removed - intuitive
    ax.set_ylabel(get_unit_label(title), fontsize=7, color='#6c757d')
    ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.5, color='#000000')
    ax.set_axisbelow(True)
    
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=6, columnspacing=0.8)
    
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    fig.autofmt_xdate(rotation=30, ha='right')
    ax.tick_params(axis='x', labelsize=6)
    
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('#dee2e6')
    
    # plt.tight_layout()  # Disabled - using bbox_inches=tight
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


def create_scatter_chart(data, x_param, y_param, title, color_scheme=None, group_field='sampling_point_name'):
    """
    Create scatter plot (e.g., for scavenge drain Iron vs Base Number)
    
    Args:
        data: List of measurement records
        x_param: X-axis parameter pattern
        y_param: Y-axis parameter pattern
        title: Chart title
        color_scheme: Dict mapping group values to colors
        group_field: Field to group/color by
    
    Returns:
        BytesIO object containing PNG image
    """
    if not data:
        return None
    
    if color_scheme is None:
        color_scheme = {}
    
    # Organize data by group and date for matching x/y pairs
    date_groups = defaultdict(lambda: defaultdict(dict))
    
    for record in data:
        group_val = record.get(group_field, 'Unknown')
        param_name = record.get('parameter_name', '')
        date_str = record.get('measurement_date', '')
        value = record.get('value_numeric')
        
        if value is None or not date_str:
            continue
        
        if x_param.lower() in param_name.lower():
            date_groups[group_val][date_str]['x'] = float(value)
        elif y_param.lower() in param_name.lower():
            date_groups[group_val][date_str]['y'] = float(value)
    
    # Create figure - scatter plots slightly wider for better aspect ratio
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')
    ax.set_facecolor('white')
    
    has_data = False
    color_idx = 0
    
    for group_val, date_points in sorted(date_groups.items()):
        x_vals = []
        y_vals = []
        
        for date_str, vals in date_points.items():
            if 'x' in vals and 'y' in vals:
                x_vals.append(vals['x'])
                y_vals.append(vals['y'])
        
        if x_vals and y_vals:
            color = color_scheme.get(group_val, GENERIC_COLORS[color_idx % len(GENERIC_COLORS)])
            
            ax.scatter(x_vals, y_vals, s=80, alpha=0.8, color=color,
                      label=compact_label(group_val), edgecolors='white', linewidth=1, zorder=3)
            has_data = True
            color_idx += 1
    
    if not has_data:
        plt.close(fig)
        return None
    
    ax.set_title(compact_label(title), fontsize=12, fontweight='bold', pad=12, color='#2c3e50')
    ax.set_xlabel(x_param, fontsize=11, color='#6c757d')
    ax.set_ylabel(get_unit_label(title), fontsize=7, color='#6c757d')
    ax.grid(True, alpha=0.2, linestyle='-', linewidth=0.5, color='#000000')
    ax.set_axisbelow(True)
    
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=6, columnspacing=0.8)
    
    for spine in ['top', 'right']:
        ax.spines[spine].set_visible(False)
    for spine in ['left', 'bottom']:
        ax.spines[spine].set_color('#dee2e6')
    
    # plt.tight_layout()  # Disabled - using bbox_inches=tight
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


# ============================================================
# TABLE AND STYLE UTILITIES
# ============================================================

def create_summary_table(data, column_headers, title=None):
    """
    Create a formatted table for PDF

    Args:
        data: List of lists (rows)
        column_headers: List of column headers
        title: Optional table title

    Returns:
        Table object for ReportLab
    """
    if not data:
        return None

    # Prepare table data
    table_data = [column_headers] + data

    # Create table
    table = Table(table_data, repeatRows=1)

    # Professional styling
    table.setStyle(TableStyle([
        # Header style
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 14),
        ('TOPPADDING', (0, 0), (-1, 0), 14),
        # Body style
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dddddd')),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))

    return table


def format_date(date_str):
    """Format date string for display"""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d')
    except:
        return date_str


def format_date_short(date_obj):
    """Format date object for cover page display (e.g., '12 Nov 25')"""
    if isinstance(date_obj, str):
        try:
            date_obj = datetime.fromisoformat(date_obj.replace('Z', '+00:00'))
        except:
            return date_obj
    return date_obj.strftime('%d %b %y')


def get_status_color(status):
    """Get color for status indicator"""
    status_colors = {
        'NORMAL': colors.HexColor('#28a745'),
        'OKAY': colors.HexColor('#28a745'),
        'LOW': colors.HexColor('#ffc107'),
        'HIGH': colors.HexColor('#dc3545'),
        'CRITICAL': colors.HexColor('#721c24')
    }
    return status_colors.get(status, colors.grey)


def create_header_style():
    """Create paragraph style for headers"""
    styles = getSampleStyleSheet()
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading1'],
        fontSize=20,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=16,
        spaceBefore=8,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    )
    return header_style


def create_section_style():
    """Create paragraph style for section headers"""
    styles = getSampleStyleSheet()
    section_style = ParagraphStyle(
        'CustomSection',
        parent=styles['Heading2'],
        fontSize=15,
        textColor=colors.HexColor('#34495e'),
        spaceAfter=10,
        spaceBefore=14,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    )
    return section_style


def create_subsection_style():
    """Create paragraph style for subsection headers"""
    styles = getSampleStyleSheet()
    subsection_style = ParagraphStyle(
        'CustomSubsection',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=colors.HexColor('#5a6c7d'),
        spaceAfter=8,
        spaceBefore=10,
        alignment=TA_LEFT,
        fontName='Helvetica-Bold'
    )
    return subsection_style


# ============================================================
# LEGACY CHART FUNCTIONS (for page_report_utils.py compatibility)
# ============================================================

def prepare_chart_data(raw_data, parameter_names):
    """
    Reorganize raw measurement data for charting

    Args:
        raw_data: List of measurement records from database
        parameter_names: List of parameter name patterns to match

    Returns:
        dict: {parameter_name: [(date, value), ...]}
    """
    organized = defaultdict(list)

    for record in raw_data:
        param_name = record.get('parameter_name', '')
        value = record.get('value_numeric')
        date_str = record.get('measurement_date')

        if value is None or not date_str:
            continue

        try:
            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))

            # Match parameter name with fuzzy matching
            for pattern in parameter_names:
                if pattern.lower() in param_name.lower():
                    organized[param_name].append((date_obj, float(value)))
                    break
        except:
            continue

    # Sort by date
    for param in organized:
        organized[param].sort(key=lambda x: x[0])

    return dict(organized)


# Legacy color palette
COLORS = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E', '#BC4B51', '#5B8E7D', '#8B5A3C']


def create_multi_parameter_chart(data, parameter_names, title, equipment_name=None):
    """
    Create a chart with multiple parameters on same plot (legacy function)

    Args:
        data: List of measurement records
        parameter_names: List of parameter patterns to plot
        title: Chart title
        equipment_name: Optional equipment filter

    Returns:
        PIL Image object
    """
    if not data:
        return None

    # Prepare data
    chart_data = prepare_chart_data(data, parameter_names)

    if not chart_data:
        return None

    # Create figure with professional styling
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')

    # Plot each parameter with different color
    color_idx = 0
    for param_name, dates_values in chart_data.items():
        if dates_values:
            dates, values = zip(*dates_values)
            ax.plot(dates, values, marker='o', linestyle='-', linewidth=2.5,
                   markersize=6, color=COLORS[color_idx % len(COLORS)],
                   label=param_name, alpha=0.9, zorder=3)
            color_idx += 1

    # Formatting
    ax.set_title(compact_label(title), fontsize=12, fontweight='bold', pad=15, color='#2c3e50')
    ax.set_xlabel('Date', fontsize=12, fontweight='600', color='#34495e')
    ax.set_ylabel(get_unit_label(title), fontsize=7, fontweight='600', color='#34495e')
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.8)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=6, columnspacing=0.8)  #

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    fig.autofmt_xdate(rotation=30, ha='right')
    ax.tick_params(axis='x', labelsize=6)

    # Style improvements
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')

    # plt.tight_layout()  # Disabled - using bbox_inches=tight

    # Convert to image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)

    return Image.open(buf)


def create_scatter_plot(data, x_param, y_param, title, group_by='sampling_point_code'):
    """
    Create scatter plot (legacy function for page_report_utils.py)

    Args:
        data: List of measurement records
        x_param: X-axis parameter pattern
        y_param: Y-axis parameter pattern
        title: Chart title
        group_by: Field to group points by (for coloring)

    Returns:
        PIL Image object
    """
    if not data:
        return None

    # Organize data by groups
    groups = defaultdict(lambda: {'x': [], 'y': []})

    for record in data:
        group_val = record.get(group_by, 'Unknown')
        param_name = record.get('parameter_name', '')
        value = record.get('value_numeric')

        if value is None:
            continue

        # Match to x or y parameter
        if x_param.lower() in param_name.lower():
            groups[group_val]['x'].append(float(value))
        elif y_param.lower() in param_name.lower():
            groups[group_val]['y'].append(float(value))

    # Create figure
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')

    has_data = False
    color_idx = 0

    for group_name, group_data in groups.items():
        # Match x and y by ensuring equal lengths
        x_vals = group_data['x']
        y_vals = group_data['y']

        if x_vals and y_vals:
            # Take minimum length to avoid mismatched data
            min_len = min(len(x_vals), len(y_vals))
            if min_len > 0:
                ax.scatter(x_vals[:min_len], y_vals[:min_len],
                          s=100, alpha=0.7, color=COLORS[color_idx % len(COLORS)],
                          label=group_name, edgecolors='white', linewidth=1.5, zorder=3)
                has_data = True
                color_idx += 1

    if not has_data:
        plt.close(fig)
        return None

    # Formatting
    ax.set_title(compact_label(title), fontsize=12, fontweight='bold', pad=15, color='#2c3e50')
    ax.set_xlabel(x_param, fontsize=12, fontweight='600', color='#34495e')
    ax.set_ylabel(get_unit_label(title), fontsize=7, fontweight='600', color='#34495e')
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.8)
    ax.legend(loc='upper center', bbox_to_anchor=(0.5, -0.22), ncol=10, frameon=False, fontsize=6, columnspacing=0.8)  #

    # Style improvements
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')

    # plt.tight_layout()  # Disabled - using bbox_inches=tight

    # Convert to image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)

    return Image.open(buf)
