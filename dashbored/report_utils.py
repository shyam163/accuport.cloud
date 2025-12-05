"""
Utility functions for PDF report generation using matplotlib
"""
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import Rectangle
from datetime import datetime
import io
from collections import defaultdict
from PIL import Image
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

# Chart configuration
CHART_WIDTH_INCHES = 8
CHART_HEIGHT_INCHES = 5
DPI = 100

# Color palette for professional look
COLORS = ['#2E86AB', '#A23B72', '#F18F01', '#C73E1D', '#6A994E', '#BC4B51', '#5B8E7D', '#8B5A3C']


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


def create_line_chart(data, parameter_name, title, ideal_low=None, ideal_high=None):
    """
    Create a line chart for a single parameter with ideal range shading

    Args:
        data: List of dicts with measurement records
        parameter_name: Parameter pattern to plot
        title: Chart title
        ideal_low: Lower ideal range
        ideal_high: Upper ideal range

    Returns:
        PIL Image object
    """
    if not data:
        return None

    # Prepare data
    chart_data = prepare_chart_data(data, [parameter_name])

    if not chart_data:
        return None

    # Get the first matching parameter
    param_key = list(chart_data.keys())[0]
    dates_values = chart_data[param_key]

    if not dates_values:
        return None

    dates, values = zip(*dates_values)

    # Create figure with professional styling
    fig, ax = plt.subplots(figsize=(CHART_WIDTH_INCHES, CHART_HEIGHT_INCHES))
    fig.patch.set_facecolor('white')

    # Add ideal range shading if provided
    if ideal_low is not None and ideal_high is not None:
        ax.axhspan(ideal_low, ideal_high, alpha=0.15, color='#6A994E',
                   label='Ideal Range', zorder=1)

    # Plot main line with professional styling
    ax.plot(dates, values, marker='o', linestyle='-', linewidth=2.5,
            markersize=7, color=COLORS[0], label=param_key, zorder=3)

    # Formatting
    ax.set_title(title, fontsize=15, fontweight='bold', pad=15, color='#2c3e50')
    ax.set_xlabel('Date', fontsize=12, fontweight='600', color='#34495e')
    ax.set_ylabel(param_key, fontsize=12, fontweight='600', color='#34495e')
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.8)
    ax.legend(loc='best', frameon=True, shadow=True, fontsize=10)

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=45)

    # Style improvements
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')

    plt.tight_layout()

    # Convert to image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)

    return Image.open(buf)


def create_multi_parameter_chart(data, parameter_names, title, equipment_name=None):
    """
    Create a chart with multiple parameters on same plot

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
    ax.set_title(title, fontsize=15, fontweight='bold', pad=15, color='#2c3e50')
    ax.set_xlabel('Date', fontsize=12, fontweight='600', color='#34495e')
    ax.set_ylabel('Value', fontsize=12, fontweight='600', color='#34495e')
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.8)
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), frameon=True,
             shadow=True, fontsize=9)

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=45)

    # Style improvements
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')

    plt.tight_layout()

    # Convert to image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)

    return Image.open(buf)


def create_scatter_plot(data, x_param, y_param, title, group_by='sampling_point_code'):
    """
    Create scatter plot (e.g., for scavenge drain analysis)

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
    ax.set_title(title, fontsize=15, fontweight='bold', pad=15, color='#2c3e50')
    ax.set_xlabel(x_param, fontsize=12, fontweight='600', color='#34495e')
    ax.set_ylabel(y_param, fontsize=12, fontweight='600', color='#34495e')
    ax.grid(True, alpha=0.25, linestyle='--', linewidth=0.8)
    ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1), frameon=True,
             shadow=True, fontsize=9)

    # Style improvements
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color('#cccccc')
    ax.spines['bottom'].set_color('#cccccc')

    plt.tight_layout()

    # Convert to image
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=DPI, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    buf.seek(0)

    return Image.open(buf)


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
