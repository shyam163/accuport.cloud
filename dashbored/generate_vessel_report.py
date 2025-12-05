#!/usr/bin/env python3
"""
PDF Report Generator for Vessel Analysis
Generate comprehensive PDF reports for vessel equipment and measurements

Usage:
    python3 generate_vessel_report.py <vessel_id> [options]

Examples:
    # Generate report for last 30 days (default)
    python3 generate_vessel_report.py 1

    # Generate report for custom date range
    python3 generate_vessel_report.py 1 --start-date 2025-01-01 --end-date 2025-01-31

    # Specify output directory
    python3 generate_vessel_report.py 4 --output-dir /path/to/reports
"""

import argparse
import sys
import os
import io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Table
from reportlab.lib.styles import getSampleStyleSheet

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    get_vessel_by_id,
    get_measurements_by_equipment_name,
    get_measurements_for_scavenge_drains,
    get_alerts_for_vessel
)
from report_utils import (
    create_line_chart,
    create_multi_parameter_chart,
    create_scatter_plot,
    create_summary_table,
    create_header_style,
    create_section_style,
    create_subsection_style,
    format_date,
    get_status_color
)


def generate_cover_page(vessel, start_date, end_date):
    """Generate cover page content"""
    elements = []
    styles = getSampleStyleSheet()

    # Title
    title_style = create_header_style()
    title_style.fontSize = 24
    title_style.alignment = 1  # Center

    elements.append(Spacer(1, 2 * inch))
    elements.append(Paragraph("Vessel Analysis Report", title_style))
    elements.append(Spacer(1, 0.5 * inch))

    # Vessel info
    info_style = create_section_style()
    info_style.fontSize = 16
    info_style.alignment = 1  # Center

    elements.append(Paragraph(f"<b>{vessel['vessel_name']}</b>", info_style))
    elements.append(Spacer(1, 0.3 * inch))
    elements.append(Paragraph(f"Vessel ID: {vessel['vessel_id']}", styles['Normal']))
    elements.append(Spacer(1, 0.2 * inch))

    # Date range
    elements.append(Paragraph(
        f"Report Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}",
        styles['Normal']
    ))
    elements.append(Spacer(1, 0.2 * inch))

    # Generated date
    elements.append(Paragraph(
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        styles['Normal']
    ))

    elements.append(PageBreak())
    return elements


def generate_boiler_section(vessel_id, start_date, end_date):
    """Generate boiler water analysis section"""
    elements = []
    section_style = create_section_style()
    subsection_style = create_subsection_style()

    elements.append(Paragraph("Auxiliary Boiler Water Analysis", section_style))
    elements.append(Spacer(1, 0.3 * inch))

    boiler_params = ['Phosphate', 'P-Alkalinity', 'M-Alkalinity', 'Chloride', 'pH', 'Hydrazine', 'DEHA', 'Conductivity']

    for boiler_name in ['AB1 Aux Boiler', 'AB2 Aux Boiler']:
        elements.append(Paragraph(boiler_name, subsection_style))

        data = get_measurements_by_equipment_name(vessel_id, boiler_name, boiler_params, start_date, end_date)

        if data and len(data) > 0:
            # Create chart for all available parameters
            chart = create_multi_parameter_chart(
                data,
                boiler_params,
                f"{boiler_name} - Water Chemistry Parameters"
            )
            if chart:
                buf = io.BytesIO()
                chart.save(buf, format='PNG')
                buf.seek(0)
                elements.append(RLImage(buf, width=6.5*inch, height=4*inch))
                elements.append(Spacer(1, 0.4 * inch))
            else:
                elements.append(Paragraph("<i>No chart data available</i>", getSampleStyleSheet()['Italic']))
                elements.append(Spacer(1, 0.2 * inch))
        else:
            elements.append(Paragraph("<i>No data available for this period</i>", getSampleStyleSheet()['Italic']))
            elements.append(Spacer(1, 0.2 * inch))

    elements.append(PageBreak())
    return elements


def generate_main_engine_section(vessel_id, start_date, end_date):
    """Generate main engine analysis section"""
    elements = []
    section_style = create_section_style()
    subsection_style = create_subsection_style()

    elements.append(Paragraph("Main Engine Analysis", section_style))
    elements.append(Spacer(1, 0.3 * inch))

    # Cooling water parameters
    elements.append(Paragraph("Cooling Water System", subsection_style))
    cooling_params = ['Nitrite', 'pH', 'Chloride']
    cooling_data = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', cooling_params, start_date, end_date)

    if cooling_data and len(cooling_data) > 0:
        chart = create_multi_parameter_chart(cooling_data, cooling_params, "Main Engine - Cooling Water Parameters")
        if chart:
            buf = io.BytesIO()
            chart.save(buf, format='PNG')
            buf.seek(0)
            elements.append(RLImage(buf, width=6.5*inch, height=4*inch))
            elements.append(Spacer(1, 0.4 * inch))
    else:
        elements.append(Paragraph("<i>No cooling water data available</i>", getSampleStyleSheet()['Italic']))
        elements.append(Spacer(1, 0.3 * inch))

    # Lube oil parameters
    elements.append(Paragraph("Lube Oil System", subsection_style))
    lube_params = ['TBN', 'Water Content', 'Viscosity']
    lube_data = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', lube_params, start_date, end_date)

    if lube_data and len(lube_data) > 0:
        chart = create_multi_parameter_chart(lube_data, lube_params, "Main Engine - Lube Oil Parameters")
        if chart:
            buf = io.BytesIO()
            chart.save(buf, format='PNG')
            buf.seek(0)
            elements.append(RLImage(buf, width=6.5*inch, height=4*inch))
            elements.append(Spacer(1, 0.4 * inch))
    else:
        elements.append(Paragraph("<i>No lube oil data available</i>", getSampleStyleSheet()['Italic']))
        elements.append(Spacer(1, 0.3 * inch))

    # Scavenge drain analysis
    elements.append(Paragraph("Scavenge Drain Analysis", subsection_style))
    scavenge_params = ['Iron', 'BaseNumber']
    scavenge_data = get_measurements_for_scavenge_drains(vessel_id, scavenge_params, start_date, end_date)

    if scavenge_data and len(scavenge_data) > 0:
        chart = create_scatter_plot(scavenge_data, 'Iron', 'BaseNumber', "Scavenge Drain - Iron vs Base Number", 'sampling_point_name')
        if chart:
            buf = io.BytesIO()
            chart.save(buf, format='PNG')
            buf.seek(0)
            elements.append(RLImage(buf, width=6.5*inch, height=4*inch))
            elements.append(Spacer(1, 0.4 * inch))
    else:
        elements.append(Paragraph("<i>No scavenge drain data available</i>", getSampleStyleSheet()['Italic']))
        elements.append(Spacer(1, 0.3 * inch))

    elements.append(PageBreak())
    return elements


def generate_aux_engine_section(vessel_id, start_date, end_date):
    """Generate auxiliary engines analysis section"""
    elements = []
    section_style = create_section_style()
    subsection_style = create_subsection_style()

    elements.append(Paragraph("Auxiliary Engines Analysis", section_style))
    elements.append(Spacer(1, 0.3 * inch))

    for engine_num in range(1, 5):  # AE1 through AE4
        engine_name = f'AE{engine_num} Aux Engine'
        elements.append(Paragraph(engine_name, subsection_style))
        elements.append(Spacer(1, 0.15 * inch))

        # Cooling and lube parameters
        cooling_params = ['Nitrite', 'pH', 'Chloride']
        lube_params = ['TBN', 'BaseNumber']

        cooling_data = get_measurements_by_equipment_name(vessel_id, engine_name, cooling_params, start_date, end_date)
        lube_data = get_measurements_by_equipment_name(vessel_id, engine_name, lube_params, start_date, end_date)

        # Create charts
        cooling_chart = None
        lube_chart = None

        if cooling_data and len(cooling_data) > 0:
            cooling_chart = create_multi_parameter_chart(cooling_data, cooling_params, f"Cooling Water")

        if lube_data and len(lube_data) > 0:
            lube_chart = create_multi_parameter_chart(lube_data, lube_params, f"Lube Oil")

        # Create side-by-side layout if both charts exist
        if cooling_chart and lube_chart:
            # Convert charts to images
            cooling_buf = io.BytesIO()
            cooling_chart.save(cooling_buf, format='PNG')
            cooling_buf.seek(0)
            cooling_img = RLImage(cooling_buf, width=3.5*inch, height=2.5*inch)

            lube_buf = io.BytesIO()
            lube_chart.save(lube_buf, format='PNG')
            lube_buf.seek(0)
            lube_img = RLImage(lube_buf, width=3.5*inch, height=2.5*inch)

            # Create table for side-by-side layout
            data = [[cooling_img, lube_img]]
            t = Table(data, colWidths=[3.75*inch, 3.75*inch])
            t.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
                ('RIGHTPADDING', (0, 0), (-1, -1), 0),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 0.4 * inch))

        elif cooling_chart or lube_chart:
            # Only one chart available, show it centered
            if cooling_chart:
                buf = io.BytesIO()
                cooling_chart.save(buf, format='PNG')
                buf.seek(0)
                elements.append(Paragraph("<b>Cooling Water</b>", getSampleStyleSheet()['Normal']))
                elements.append(Spacer(1, 0.1 * inch))
                elements.append(RLImage(buf, width=6*inch, height=3.5*inch))
                elements.append(Spacer(1, 0.3 * inch))

            if lube_chart:
                buf = io.BytesIO()
                lube_chart.save(buf, format='PNG')
                buf.seek(0)
                elements.append(Paragraph("<b>Lube Oil</b>", getSampleStyleSheet()['Normal']))
                elements.append(Spacer(1, 0.1 * inch))
                elements.append(RLImage(buf, width=6*inch, height=3.5*inch))
                elements.append(Spacer(1, 0.3 * inch))
        else:
            elements.append(Paragraph("<i>No data available for this engine</i>", getSampleStyleSheet()['Italic']))
            elements.append(Spacer(1, 0.2 * inch))

    elements.append(PageBreak())
    return elements


def generate_water_systems_section(vessel_id, start_date, end_date):
    """Generate water systems analysis section"""
    elements = []
    section_style = create_section_style()
    subsection_style = create_subsection_style()

    elements.append(Paragraph("Water Systems Analysis", section_style))
    elements.append(Spacer(1, 0.3 * inch))

    # Potable Water
    elements.append(Paragraph("Potable Water System", subsection_style))
    pw_params = ['pH', 'Alkalinity', 'Chlorine', 'Dissolved Solids', 'Turbidity', 'Hardness']
    pw_data = get_measurements_by_equipment_name(vessel_id, 'PW1 Potable Water', pw_params, start_date, end_date)

    if pw_data and len(pw_data) > 0:
        chart = create_multi_parameter_chart(pw_data, pw_params, "Potable Water - Quality Parameters")
        if chart:
            buf = io.BytesIO()
            chart.save(buf, format='PNG')
            buf.seek(0)
            elements.append(RLImage(buf, width=6.5*inch, height=4*inch))
            elements.append(Spacer(1, 0.4 * inch))
    else:
        elements.append(Paragraph("<i>No potable water data available</i>", getSampleStyleSheet()['Italic']))
        elements.append(Spacer(1, 0.3 * inch))

    # Treated Sewage
    elements.append(Paragraph("Treated Sewage Water", subsection_style))
    gw_params = ['pH', 'COD', 'Chlorine', 'Turbidity', 'coli']
    gw_data = get_measurements_by_equipment_name(vessel_id, 'GW Treated Sewage', gw_params, start_date, end_date)

    if gw_data and len(gw_data) > 0:
        chart = create_multi_parameter_chart(gw_data, gw_params, "Treated Sewage - Quality Parameters")
        if chart:
            buf = io.BytesIO()
            chart.save(buf, format='PNG')
            buf.seek(0)
            elements.append(RLImage(buf, width=6.5*inch, height=4*inch))
            elements.append(Spacer(1, 0.4 * inch))
    else:
        elements.append(Paragraph("<i>No treated sewage data available</i>", getSampleStyleSheet()['Italic']))
        elements.append(Spacer(1, 0.3 * inch))

    elements.append(PageBreak())
    return elements


def generate_alerts_section(vessel_id):
    """Generate alerts and warnings section"""
    elements = []
    section_style = create_section_style()

    elements.append(Paragraph("Recent Alerts and Warnings", section_style))
    elements.append(Spacer(1, 0.2 * inch))

    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)

    if alerts:
        # Create alerts table
        headers = ['Date', 'Equipment', 'Parameter', 'Severity', 'Measured', 'Expected']
        rows = []

        for alert in alerts[:20]:  # Limit to 20 most recent
            rows.append([
                format_date(alert.get('alert_date', '')),
                alert.get('equipment_name', 'N/A'),
                alert.get('parameter_name', 'N/A'),
                alert.get('alert_type', 'N/A'),
                str(alert.get('measured_value', 'N/A')),
                f"{alert.get('ideal_low', 'N/A')} - {alert.get('ideal_high', 'N/A')}"
            ])

        table = create_summary_table(rows, headers)
        elements.append(table)
    else:
        elements.append(Paragraph("No unresolved alerts", create_section_style()))

    return elements


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description='Generate PDF report for vessel measurements',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument('vessel_id', type=int, help='Vessel database ID')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD), default: 30 days ago')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD), default: today')
    parser.add_argument('--output-dir', type=str, default='reports', help='Output directory for PDF reports')

    args = parser.parse_args()

    # Parse dates
    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = end_date - timedelta(days=30)

    # Get vessel info
    vessel = get_vessel_by_id(args.vessel_id)
    if not vessel:
        print(f"Error: Vessel ID {args.vessel_id} not found")
        sys.exit(1)

    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)

    # Generate PDF filename
    filename = f"{vessel['vessel_name'].replace(' ', '_')}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    output_path = os.path.join(args.output_dir, filename)

    print(f"Generating report for {vessel['vessel_name']}...")
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    # Create PDF document
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    elements = []

    # Generate sections
    print("- Generating cover page...")
    elements.extend(generate_cover_page(vessel, start_date, end_date))

    print("- Generating boiler analysis...")
    elements.extend(generate_boiler_section(args.vessel_id, start_date, end_date))

    print("- Generating main engine analysis...")
    elements.extend(generate_main_engine_section(args.vessel_id, start_date, end_date))

    print("- Generating auxiliary engines analysis...")
    elements.extend(generate_aux_engine_section(args.vessel_id, start_date, end_date))

    print("- Generating water systems analysis...")
    elements.extend(generate_water_systems_section(args.vessel_id, start_date, end_date))

    print("- Generating alerts section...")
    elements.extend(generate_alerts_section(args.vessel_id))

    # Build PDF
    print("- Building PDF document...")
    doc.build(elements)

    print(f"\nReport generated successfully: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")


if __name__ == '__main__':
    main()
