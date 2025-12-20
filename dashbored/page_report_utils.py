"""
Per-Page PDF Report Generation Utilities
Generate PDF reports for individual equipment pages
"""
import os
import io
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

from models import (
    get_vessel_by_id,
    get_measurements_for_scavenge_drains,
    get_alerts_for_vessel
)
from report_utils import (
    create_multi_parameter_chart,
    create_scatter_plot,
    create_summary_table,
    create_header_style,
    create_section_style,
    create_subsection_style,
    format_date
)


def create_cover_page_with_logo(vessel, start_date, end_date, page_title):
    """
    Generate cover page with AccuPort logo

    Args:
        vessel: Vessel dict with vessel_name, vessel_id
        start_date: datetime object
        end_date: datetime object
        page_title: Title of the report page (e.g., "Main Engine Scavenge Drain")

    Returns:
        List of ReportLab elements
    """
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Spacer(1, 1 * inch))

    # Add logo at top
    logo_path = os.path.join(os.path.dirname(__file__), 'static', 'img', 'logo.jpg')
    if os.path.exists(logo_path):
        logo = RLImage(logo_path, width=2.5*inch, height=1.25*inch)
        # Center the logo
        elements.append(logo)
        elements.append(Spacer(1, 0.5*inch))

    # Title
    title_style = create_header_style()
    title_style.fontSize = 22
    title_style.alignment = 1  # Center

    elements.append(Paragraph(f"AccuPort {page_title} Report", title_style))
    elements.append(Spacer(1, 0.6*inch))

    # Vessel info
    info_style = create_section_style()
    info_style.fontSize = 16
    info_style.alignment = 1

    elements.append(Paragraph(f"<b>{vessel['vessel_name']}</b>", info_style))
    elements.append(Spacer(1, 0.3*inch))

    # Date range with better formatting
    date_style = getSampleStyleSheet()['Normal']
    date_style.alignment = 1  # Center
    date_style.fontSize = 12

    elements.append(Paragraph(
        f"<b>Report Period:</b> {start_date.strftime('%B %d, %Y')} to {end_date.strftime('%B %d, %Y')}",
        date_style
    ))
    elements.append(Spacer(1, 0.2*inch))

    # Generated date
    elements.append(Paragraph(
        f"<i>Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</i>",
        date_style
    ))

    elements.append(PageBreak())
    return elements


def create_alerts_section_for_page(vessel_id, equipment_filter=None):
    """
    Create alerts section for specific equipment

    Args:
        vessel_id: Vessel database ID
        equipment_filter: List of equipment name patterns to filter by

    Returns:
        List of ReportLab elements
    """
    elements = []
    section_style = create_section_style()

    elements.append(Paragraph("Alerts and Warnings", section_style))
    elements.append(Spacer(1, 0.2 * inch))

    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)

    # Filter alerts by equipment if specified
    if alerts and equipment_filter:
        filtered_alerts = []
        for alert in alerts:
            sampling_point = alert.get('sampling_point_name', '').upper()
            for filter_pattern in equipment_filter:
                if filter_pattern.upper() in sampling_point:
                    filtered_alerts.append(alert)
                    break
        alerts = filtered_alerts

    if alerts:
        # Create alerts table
        headers = ['Date', 'Sampling Point', 'Parameter', 'Measured', 'Expected']
        rows = []

        for alert in alerts[:15]:  # Limit to 15 most recent
            rows.append([
                format_date(alert.get('alert_date', '')),
                alert.get('sampling_point_name', 'N/A')[:30],  # Truncate long names
                alert.get('parameter_name', 'N/A'),
                str(alert.get('measured_value', 'N/A')),
                f"{alert.get('ideal_low', 'N/A')} - {alert.get('ideal_high', 'N/A')}"
            ])

        if rows:
            table = create_summary_table(rows, headers)
            elements.append(table)
        else:
            elements.append(Paragraph("No alerts for selected equipment", getSampleStyleSheet()['Normal']))
    else:
        elements.append(Paragraph("No unresolved alerts", getSampleStyleSheet()['Normal']))

    elements.append(Spacer(1, 0.3 * inch))
    return elements


def generate_main_engine_sd_report(vessel_id, start_date, end_date, selected_engines=None, selected_cylinders=None):
    """
    Generate PDF report for Main Engine Scavenge Drain page

    Args:
        vessel_id: Vessel database ID
        start_date: datetime object
        end_date: datetime object
        selected_engines: List of engine IDs (e.g., ['ME1', 'ME2'])
        selected_cylinders: List of cylinder numbers (e.g., ['1', '2', '3'])

    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    # Get vessel info
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")

    # Default selections
    if not selected_engines:
        selected_engines = ['ME1', 'ME2']
    if not selected_cylinders:
        selected_cylinders = list(range(1, 13))  # Cylinders 1-12
    else:
        # Convert to integers
        selected_cylinders = [int(c) for c in selected_cylinders if c.isdigit()]

    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_MainEngine_SD_{date_str}.pdf"

    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []

    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "Main Engine - Scavenge Drain Analysis"))

    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()

    elements.append(Paragraph("Scavenge Drain Analysis", section_style))
    elements.append(Spacer(1, 0.3 * inch))

    # Get scavenge drain data
    scavenge_params = ['Iron', 'Base']
    scavenge_data = get_measurements_for_scavenge_drains(vessel_id, scavenge_params, start_date, end_date)

    if scavenge_data and len(scavenge_data) > 0:
        # Iron in Oil Chart
        elements.append(Paragraph("Iron in Oil - Timeseries", subsection_style))
        elements.append(Spacer(1, 0.15 * inch))

        iron_data = [m for m in scavenge_data if 'Iron' in m.get('parameter_name', '')]
        if iron_data:
            chart = create_multi_parameter_chart(
                iron_data,
                ['Iron'],
                f"Iron in Oil (mg/L) - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            )
            if chart is not None:
                elements.append(RLImage(chart, width=6.5*inch, height=4*inch))
                elements.append(Spacer(1, 0.4 * inch))

        # Base Number Chart
        elements.append(Paragraph("Base Number - Timeseries", subsection_style))
        elements.append(Spacer(1, 0.15 * inch))

        bn_data = [m for m in scavenge_data if 'Base' in m.get('parameter_name', '')]
        if bn_data:
            chart = create_multi_parameter_chart(
                bn_data,
                ['Base'],
                f"Base Number (BN) - {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            )
            if chart is not None:
                elements.append(RLImage(chart, width=6.5*inch, height=4*inch))
                elements.append(Spacer(1, 0.4 * inch))

        elements.append(PageBreak())

        # Scatter Plot - Iron vs Base Number
        elements.append(Paragraph("Iron vs Base Number - Correlation Analysis", subsection_style))
        elements.append(Spacer(1, 0.15 * inch))

        scatter_chart = create_scatter_plot(
            scavenge_data,
            'Iron',
            'Base',
            "Scavenge Drain - Iron vs Base Number",
            'sampling_point_name'
        )
        if scatter_chart:
            buf = io.BytesIO()
            scatter_chart.save(buf, format='PNG')
            buf.seek(0)
            elements.append(RLImage(buf, width=6.5*inch, height=4.5*inch))
            elements.append(Spacer(1, 0.4 * inch))

    else:
        elements.append(Paragraph("<i>No scavenge drain data available for this period</i>",
                                 getSampleStyleSheet()['Italic']))
        elements.append(Spacer(1, 0.3 * inch))

    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['SD', 'Scavenge', 'Main Engine']))

    # Build PDF
    doc.build(elements)
    buffer.seek(0)

    return buffer, filename


def generate_boiler_water_report(vessel_id, start_date, end_date, selected_boilers=None):
    """
    Generate PDF report for Boiler Water page
    
    Args:
        vessel_id: Vessel database ID
        start_date: datetime object
        end_date: datetime object
        selected_boilers: List of boiler IDs (e.g., ['Aux1', 'Aux2', 'EGE', 'Hotwell'])
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    from models import get_vessel_by_id, get_measurements_by_equipment_name, get_all_limits_for_equipment
    from report_utils import (
        create_line_chart_by_unit, get_limits_for_pdf, normalize_param_name_for_limits
    )
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")
    
    # Default selections
    if not selected_boilers:
        selected_boilers = ['Aux1', 'Aux2', 'EGE', 'Hotwell']
    
    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_BoilerWater_{date_str}.pdf"
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []
    
    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "Boiler Water Analysis"))
    
    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()
    
    # Boiler parameters
    boiler_params = ['Phosphate', 'Alkalinity P', 'Alkalinity M', 'Chloride', 'pH', 'Conductivity']
    hotwell_params = ['DEHA', 'Hydrazine', 'pH', 'Conductivity']
    
    # Equipment name mapping
    boiler_equipment_names = {
        'Aux1': 'AB1 Aux Boiler 1',
        'Aux2': 'AB2 Aux Boiler 2',
        'EGE': 'CB Composite Boiler',
        'Hotwell': 'HW Hot Well'
    }
    
    boiler_colors = {
        'Aux1': '#0d6efd',
        'Aux2': '#198754',
        'EGE': '#dc3545',
        'Hotwell': '#ffc107'
    }
    
    # Get boiler limits
    aux_boiler_limits = get_all_limits_for_equipment('AUX BOILER & EGE')
    hotwell_limits = get_all_limits_for_equipment('HOTWELL')
    
    # Generate charts for regular boilers (Aux1, Aux2, EGE)
    regular_boilers = [b for b in selected_boilers if b in ['Aux1', 'Aux2', 'EGE']]
    if regular_boilers:
        elements.append(Paragraph("Auxiliary Boilers & EGE", section_style))
        elements.append(Spacer(1, 0.2 * inch))
        
        # Collect data for regular boilers
        boiler_data = []
        for boiler_id in regular_boilers:
            if boiler_id in boiler_equipment_names:
                equipment_name = boiler_equipment_names[boiler_id]
                data_raw = get_measurements_by_equipment_name(vessel_id, equipment_name, boiler_params, start_date, end_date) or []
                for item in data_raw:
                    item_copy = dict(item)
                    item_copy['unit_id'] = boiler_id
                    boiler_data.append(item_copy)
        
        # Generate charts for each parameter
        for param in boiler_params:
            param_data = [m for m in boiler_data if param.lower() in m.get('parameter_name', '').lower()]
            if param_data:
                normalized_param = normalize_param_name_for_limits(param)
                limit_low, limit_high = None, None
                if normalized_param in aux_boiler_limits:
                    limit_low = aux_boiler_limits[normalized_param].get('lower_limit')
                    limit_high = aux_boiler_limits[normalized_param].get('upper_limit')
                
                elements.append(Paragraph(f"{param}", subsection_style))
                chart = create_line_chart_by_unit(
                    param_data, param,
                    ideal_low=limit_low, ideal_high=limit_high,
                    color_scheme=boiler_colors, equipment_type='AUX BOILER & EGE'
                )
                if chart is not None:
                    elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                    elements.append(Spacer(1, 0.3 * inch))
        
        elements.append(PageBreak())
    
    # Generate charts for Hotwell
    if 'Hotwell' in selected_boilers:
        elements.append(Paragraph("Hotwell", section_style))
        elements.append(Spacer(1, 0.2 * inch))
        
        hotwell_data = []
        equipment_name = boiler_equipment_names['Hotwell']
        data_raw = get_measurements_by_equipment_name(vessel_id, equipment_name, hotwell_params, start_date, end_date) or []
        for item in data_raw:
            item_copy = dict(item)
            item_copy['unit_id'] = 'Hotwell'
            hotwell_data.append(item_copy)
        
        for param in hotwell_params:
            param_data = [m for m in hotwell_data if param.lower() in m.get('parameter_name', '').lower()]
            if param_data:
                normalized_param = normalize_param_name_for_limits(param)
                limit_low, limit_high = None, None
                if normalized_param in hotwell_limits:
                    limit_low = hotwell_limits[normalized_param].get('lower_limit')
                    limit_high = hotwell_limits[normalized_param].get('upper_limit')
                
                elements.append(Paragraph(f"{param}", subsection_style))
                chart = create_line_chart_by_unit(
                    param_data, f"Hotwell - {param}",
                    ideal_low=limit_low, ideal_high=limit_high,
                    color_scheme=boiler_colors, equipment_type='HOTWELL'
                )
                if chart is not None:
                    elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                    elements.append(Spacer(1, 0.3 * inch))
    
    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['BOILER', 'AB', 'HOTWELL', 'EGE']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer, filename


def generate_aux_engines_report(vessel_id, start_date, end_date, selected_engines=None):
    """
    Generate PDF report for Aux Engines page
    
    Args:
        vessel_id: Vessel database ID
        start_date: datetime object
        end_date: datetime object
        selected_engines: List of engine IDs (e.g., ['AE1', 'AE2', 'AE3'])
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    from models import get_vessel_by_id, get_measurements_by_equipment_name, get_all_limits_for_equipment
    from report_utils import create_line_chart_by_unit, normalize_param_name_for_limits
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")
    
    # Default selections
    if not selected_engines:
        selected_engines = ['AE1', 'AE2', 'AE3']
    
    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_AuxEngines_{date_str}.pdf"
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []
    
    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "Auxiliary Engines Analysis"))
    
    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()
    
    # Aux engine cooling water parameters
    cooling_params = ['pH', 'Chloride', 'Nitrite']
    
    # Equipment name mapping
    ae_equipment_names = {
        'AE1': 'AE Aux Engine 1',
        'AE2': 'AE Aux Engine 2',
        'AE3': 'AE Aux Engine 3'
    }
    
    ae_colors = {
        'AE1': '#0d6efd',
        'AE2': '#198754',
        'AE3': '#fd7e14'
    }
    
    # Get cooling water limits
    cooling_limits = get_all_limits_for_equipment('HT & LT COOLING WATER')
    
    elements.append(Paragraph("Auxiliary Engine Cooling Water", section_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Collect data for selected engines
    ae_data = []
    for engine_id in selected_engines:
        if engine_id in ae_equipment_names:
            equipment_name = ae_equipment_names[engine_id]
            data_raw = get_measurements_by_equipment_name(vessel_id, equipment_name, cooling_params, start_date, end_date) or []
            for item in data_raw:
                item_copy = dict(item)
                item_copy['unit_id'] = engine_id
                ae_data.append(item_copy)
    
    # Generate charts for each parameter
    for param in cooling_params:
        param_data = [m for m in ae_data if param.lower() in m.get('parameter_name', '').lower()]
        if param_data:
            normalized_param = normalize_param_name_for_limits(param)
            limit_low, limit_high = None, None
            if normalized_param in cooling_limits:
                limit_low = cooling_limits[normalized_param].get('lower_limit')
                limit_high = cooling_limits[normalized_param].get('upper_limit')
            
            elements.append(Paragraph(f"{param}", subsection_style))
            chart = create_line_chart_by_unit(
                param_data, f"Aux Engines - {param}",
                ideal_low=limit_low, ideal_high=limit_high,
                color_scheme=ae_colors, equipment_type='HT & LT COOLING WATER'
            )
            if chart is not None:
                elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                elements.append(Spacer(1, 0.3 * inch))
    
    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['AE', 'AUX ENGINE']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer, filename


def generate_main_engines_lube_report(vessel_id, start_date, end_date, selected_engines=None):
    """
    Generate PDF report for Main Engine Lube Oil page
    
    Args:
        vessel_id: Vessel database ID
        start_date: datetime object
        end_date: datetime object
        selected_engines: List of engine IDs (e.g., ['ME1', 'ME2'])
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    from models import get_vessel_by_id, get_measurements_by_equipment_name
    from report_utils import create_line_chart_by_unit
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")
    
    # Default selections
    if not selected_engines:
        selected_engines = ['ME1', 'ME2']
    
    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_MainEngine_LubeOil_{date_str}.pdf"
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []
    
    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "Main Engine Lubricating Oil Analysis"))
    
    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()
    
    # Lube oil parameters (Main Engine System Oil)
    lube_params = ['Viscosity', 'Base', 'Water']
    
    # Equipment name mapping
    me_equipment_names = {
        'ME1': 'ME Main Engine System Oil 1',
        'ME2': 'ME Main Engine System Oil 2'
    }
    
    me_colors = {
        'ME1': '#dc3545',
        'ME2': '#0d6efd'
    }
    
    elements.append(Paragraph("Main Engine System Oil", section_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Collect data for selected engines
    lube_data = []
    for engine_id in selected_engines:
        if engine_id in me_equipment_names:
            equipment_name = me_equipment_names[engine_id]
            data_raw = get_measurements_by_equipment_name(vessel_id, equipment_name, lube_params, start_date, end_date) or []
            for item in data_raw:
                item_copy = dict(item)
                item_copy['unit_id'] = engine_id
                lube_data.append(item_copy)
    
    # Generate charts for each parameter
    for param in lube_params:
        param_data = [m for m in lube_data if param.lower() in m.get('parameter_name', '').lower()]
        if param_data:
            elements.append(Paragraph(f"{param}", subsection_style))
            chart = create_line_chart_by_unit(
                param_data, f"Main Engine - {param}",
                ideal_low=None, ideal_high=None,
                color_scheme=me_colors, equipment_type=None
            )
            if chart is not None:
                elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                elements.append(Spacer(1, 0.3 * inch))
    
    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['ME', 'MAIN ENGINE', 'SYSTEM OIL']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer, filename


def generate_potable_water_report(vessel_id, start_date, end_date):
    """
    Generate PDF report for Potable Water page
    
    Args:
        vessel_id: Vessel database ID
        start_date: datetime object
        end_date: datetime object
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    from models import get_vessel_by_id, get_measurements_by_equipment_name, get_all_limits_for_equipment
    from report_utils import create_line_chart_by_unit, normalize_param_name_for_limits
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")
    
    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_PotableWater_{date_str}.pdf"
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []
    
    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "Potable Water Analysis"))
    
    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()
    
    # Potable water parameters
    potable_params = ['pH', 'Chlorine', 'Conductivity', 'Turbidity', 'Copper', 'Iron', 'Nickel', 'COD']
    
    # Equipment name for potable water
    equipment_name = 'PW Potable Water'
    
    # Get potable water limits
    potable_limits = get_all_limits_for_equipment('POTABLE WATER')
    
    elements.append(Paragraph("Potable Water Quality", section_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Get data
    potable_data = get_measurements_by_equipment_name(vessel_id, equipment_name, potable_params, start_date, end_date) or []
    for item in potable_data:
        item['unit_id'] = 'PW'
    
    # Generate charts for each parameter
    for param in potable_params:
        param_data = [m for m in potable_data if param.lower() in m.get('parameter_name', '').lower()]
        if param_data:
            normalized_param = normalize_param_name_for_limits(param)
            limit_low, limit_high = None, None
            if normalized_param in potable_limits:
                limit_low = potable_limits[normalized_param].get('lower_limit')
                limit_high = potable_limits[normalized_param].get('upper_limit')
            
            elements.append(Paragraph(f"{param}", subsection_style))
            chart = create_line_chart_by_unit(
                param_data, f"Potable Water - {param}",
                ideal_low=limit_low, ideal_high=limit_high,
                color_scheme={'PW': '#0d6efd'}, equipment_type='POTABLE WATER'
            )
            if chart is not None:
                elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                elements.append(Spacer(1, 0.3 * inch))
    
    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['POTABLE', 'DRINKING', 'PW']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer, filename


def generate_central_cooling_report(vessel_id, start_date, end_date, selected_systems=None):
    """
    Generate PDF report for Central Cooling System page
    
    Args:
        vessel_id: Vessel database ID
        start_date: datetime object
        end_date: datetime object
        selected_systems: List of selected systems (HT, LT)
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    from models import get_vessel_by_id, get_measurements_by_equipment_name, get_all_limits_for_equipment
    from report_utils import create_line_chart_by_unit, normalize_param_name_for_limits
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")
    
    if selected_systems is None:
        selected_systems = ['HT', 'LT']
    
    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_CentralCooling_{date_str}.pdf"
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []
    
    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "Central Cooling System Analysis"))
    
    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()
    
    # Cooling water parameters
    cooling_params = ['pH', 'Chloride', 'Nitrite']
    
    # Equipment names for cooling water
    cooling_equipment = {
        'HT': 'HT Cooling Water',
        'LT': 'LT Cooling Water'
    }
    
    # Color scheme for cooling systems
    cooling_colors = {'HT': '#dc3545', 'LT': '#0d6efd'}
    
    # Get cooling water limits
    cooling_limits = get_all_limits_for_equipment('HT & LT COOLING WATER')
    
    elements.append(Paragraph("Central Cooling System", section_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Collect all data with system_id
    all_cooling_data = []
    for system_id, equipment_name in cooling_equipment.items():
        if system_id in selected_systems:
            data = get_measurements_by_equipment_name(vessel_id, equipment_name, cooling_params, start_date, end_date) or []
            for item in data:
                item_copy = dict(item)
                item_copy['unit_id'] = system_id
                all_cooling_data.append(item_copy)
    
    # Generate charts for each parameter
    for param in cooling_params:
        param_data = [m for m in all_cooling_data if param.lower() in m.get('parameter_name', '').lower()]
        if param_data:
            normalized_param = normalize_param_name_for_limits(param)
            limit_low, limit_high = None, None
            if normalized_param in cooling_limits:
                limit_low = cooling_limits[normalized_param].get('lower_limit')
                limit_high = cooling_limits[normalized_param].get('upper_limit')
            
            elements.append(Paragraph(f"{param}", subsection_style))
            chart = create_line_chart_by_unit(
                param_data, f"Cooling Water - {param}",
                ideal_low=limit_low, ideal_high=limit_high,
                color_scheme=cooling_colors, equipment_type='HT & LT COOLING WATER'
            )
            if chart is not None:
                elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                elements.append(Spacer(1, 0.3 * inch))
    
    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['COOLING', 'HT', 'LT']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer, filename


def generate_treated_sewage_report(vessel_id, start_date, end_date):
    """
    Generate PDF report for Treated Sewage Water page
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    from models import get_vessel_by_id, get_measurements_by_equipment_name, get_all_limits_for_equipment
    from report_utils import create_line_chart_by_unit, normalize_param_name_for_limits
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")
    
    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_TreatedSewage_{date_str}.pdf"
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []
    
    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "Treated Sewage Water Analysis"))
    
    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()
    
    # Sewage water parameters
    sewage_params = ['pH', 'COD', 'Chlorine', 'Suspended Solids', 'Turbidity']
    
    # Equipment name for sewage
    equipment_name = 'GW Treated Sewage'
    
    # Get sewage limits
    sewage_limits = get_all_limits_for_equipment('SEWAGE')
    
    elements.append(Paragraph("Treated Sewage Water Quality", section_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Get data
    sewage_data = get_measurements_by_equipment_name(vessel_id, equipment_name, sewage_params, start_date, end_date) or []
    for item in sewage_data:
        item['unit_id'] = 'GW'
    
    # Generate charts for each parameter
    for param in sewage_params:
        param_data = [m for m in sewage_data if param.lower() in m.get('parameter_name', '').lower()]
        if param_data:
            normalized_param = normalize_param_name_for_limits(param)
            limit_low, limit_high = None, None
            if normalized_param in sewage_limits:
                limit_low = sewage_limits[normalized_param].get('lower_limit')
                limit_high = sewage_limits[normalized_param].get('upper_limit')
            
            elements.append(Paragraph(f"{param}", subsection_style))
            chart = create_line_chart_by_unit(
                param_data, f"Treated Sewage - {param}",
                ideal_low=limit_low, ideal_high=limit_high,
                color_scheme={'GW': '#6c757d'}, equipment_type='SEWAGE'
            )
            if chart is not None:
                elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                elements.append(Spacer(1, 0.3 * inch))
    
    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['SEWAGE', 'GREY', 'GRAY', 'GW']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer, filename


def generate_ballast_water_report(vessel_id, start_date, end_date):
    """
    Generate PDF report for Ballast Water page
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    from models import get_vessel_by_id, get_measurements_by_equipment_name
    from report_utils import create_line_chart_by_unit
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")
    
    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_BallastWater_{date_str}.pdf"
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []
    
    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "Ballast Water Analysis"))
    
    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()
    
    # Ballast water parameters
    ballast_params = ['Total Viable Count', 'E. coli', 'Chlorine', 'pH']
    
    # Equipment name for ballast water
    equipment_name = 'Ballast Water'
    
    elements.append(Paragraph("Ballast Water Quality", section_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Get data
    ballast_data = get_measurements_by_equipment_name(vessel_id, equipment_name, ballast_params, start_date, end_date) or []
    for item in ballast_data:
        item['unit_id'] = 'BW'
    
    if not ballast_data:
        elements.append(Paragraph("No ballast water data available for the selected date range.", subsection_style))
    else:
        # Generate charts for each parameter
        for param in ballast_params:
            param_data = [m for m in ballast_data if param.lower() in m.get('parameter_name', '').lower()]
            if param_data:
                elements.append(Paragraph(f"{param}", subsection_style))
                chart = create_line_chart_by_unit(
                    param_data, f"Ballast Water - {param}",
                    color_scheme={'BW': '#17a2b8'}
                )
                if chart is not None:
                    elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                    elements.append(Spacer(1, 0.3 * inch))
    
    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['BALLAST']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer, filename


def generate_egcs_report(vessel_id, start_date, end_date):
    """
    Generate PDF report for EGCS (Exhaust Gas Cleaning System) page
    
    Returns:
        Tuple of (BytesIO buffer, filename)
    """
    from models import get_vessel_by_id, get_measurements_by_equipment_name
    from report_utils import create_line_chart_by_unit
    
    vessel = get_vessel_by_id(vessel_id)
    if not vessel:
        raise ValueError(f"Vessel ID {vessel_id} not found")
    
    # Create PDF filename
    date_str = f"{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}"
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_EGCS_{date_str}.pdf"
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter,
                           topMargin=0.75*inch, bottomMargin=0.75*inch,
                           leftMargin=0.75*inch, rightMargin=0.75*inch)
    elements = []
    
    # Add cover page
    elements.extend(create_cover_page_with_logo(vessel, start_date, end_date, "EGCS Analysis"))
    
    # Main content section
    section_style = create_section_style()
    subsection_style = create_subsection_style()
    
    # EGCS parameters
    egcs_params = ['pH', 'PAH', 'Turbidity', 'Nitrate']
    
    # Equipment name for EGCS
    equipment_name = 'EGCS'
    
    elements.append(Paragraph("EGCS (Exhaust Gas Cleaning System)", section_style))
    elements.append(Spacer(1, 0.2 * inch))
    
    # Get data
    egcs_data = get_measurements_by_equipment_name(vessel_id, equipment_name, egcs_params, start_date, end_date) or []
    for item in egcs_data:
        item['unit_id'] = 'EGCS'
    
    if not egcs_data:
        elements.append(Paragraph("No EGCS data available for the selected date range.", subsection_style))
    else:
        # Generate charts for each parameter
        for param in egcs_params:
            param_data = [m for m in egcs_data if param.lower() in m.get('parameter_name', '').lower()]
            if param_data:
                elements.append(Paragraph(f"{param}", subsection_style))
                chart = create_line_chart_by_unit(
                    param_data, f"EGCS - {param}",
                    color_scheme={'EGCS': '#6f42c1'}
                )
                if chart is not None:
                    elements.append(RLImage(chart, width=6.5*inch, height=3.5*inch))
                    elements.append(Spacer(1, 0.3 * inch))
    
    # Add alerts section
    elements.append(PageBreak())
    elements.extend(create_alerts_section_for_page(vessel_id, equipment_filter=['EGCS', 'SCRUBBER']))
    
    # Build PDF
    doc.build(elements)
    buffer.seek(0)
    
    return buffer, filename
