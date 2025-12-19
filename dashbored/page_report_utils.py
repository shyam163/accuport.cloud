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
            if chart:
                buf = io.BytesIO()
                chart.save(buf, format='PNG')
                buf.seek(0)
                elements.append(RLImage(buf, width=6.5*inch, height=4*inch))
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
            if chart:
                buf = io.BytesIO()
                chart.save(buf, format='PNG')
                buf.seek(0)
                elements.append(RLImage(buf, width=6.5*inch, height=4*inch))
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
