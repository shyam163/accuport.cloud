#!/usr/bin/env python3
"""
PDF Report Generator for Vessel Analysis
Generate comprehensive PDF reports with custom backgrounds and matplotlib charts
"""

import argparse
import sys
import os
import io
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Image as RLImage, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import ImageReader

# Add parent directory to path to import models
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import (
    get_all_limits_for_equipment,
    get_vessel_by_id,
    get_measurements_by_equipment_name,
    get_measurements_for_scavenge_drains,
    get_alerts_for_vessel
)
from report_utils import (
    get_limits_for_pdf,
    create_line_chart_by_unit,
    create_multi_line_chart,
    create_scatter_chart,
    create_summary_table,
    create_header_style,
    create_section_style,
    create_subsection_style,
    format_date,
    format_date_short,
    get_status_color,
    BOILER_COLORS,
    MAIN_ENGINE_COLORS,
    AUX_ENGINE_COLORS,
    GENERIC_COLORS
)

# Static file paths
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'img')
COVER_IMAGE = os.path.join(STATIC_DIR, 'cover.jpg')
CONTENT_IMAGE = os.path.join(STATIC_DIR, 'content.jpg')
BACK_IMAGE = os.path.join(STATIC_DIR, 'back.jpg')

# Available sections for selection
AVAILABLE_SECTIONS = {
    'boiler': {
        'name': 'Boiler Water',
        'generator': 'generate_boiler_section'
    },
    'main_engines': {
        'name': 'Main Engines',
        'generator': 'generate_main_engine_section'
    },
    'aux_engines': {
        'name': 'Auxiliary Engines',
        'generator': 'generate_aux_engine_section'
    },
    'potable_water': {
        'name': 'Potable Water',
        'generator': 'generate_potable_water_section'
    },
    'treated_sewage': {
        'name': 'Treated Sewage',
        'generator': 'generate_treated_sewage_section'
    },
    'central_cooling': {
        'name': 'Central Cooling',
        'generator': 'generate_central_cooling_section'
    },
    'ballast_water': {
        'name': 'Ballast Water',
        'generator': 'generate_ballast_water_section'
    },
    'egcs': {
        'name': 'EGCS',
        'generator': 'generate_egcs_section'
    }
}


class ReportPDFGenerator:
    """PDF Generator with custom page backgrounds"""
    
    def __init__(self, output, vessel_name, start_date, end_date):
        self.output = output
        self.vessel_name = vessel_name
        self.start_date = start_date
        self.end_date = end_date
        self.c = canvas.Canvas(output, pagesize=letter)
        self.width, self.height = letter
        self.current_section = None
        # Content area starts below green header bar (about 90pt from top)
        self.y_position = self.height - 115  
        self.margin_left = 25
        self.margin_right = 25
        self.content_width = self.width - self.margin_left - self.margin_right
        # Orange header bar height is about 90pt from top
        self.header_bar_bottom = self.height - 100
        
        # Grid layout for 2x2 charts
        self.grid_position = 0  # 0=top-left, 1=top-right, 2=bot-left, 3=bot-right
        self.grid_row_y = None  # Y position for current grid row
        self.section_page = 1  # Page counter within section
        
    def draw_cover_page(self):
        """Draw cover page with background image and RIGHT-JUSTIFIED text"""
        # Draw background image
        if os.path.exists(COVER_IMAGE):
            self.c.drawImage(COVER_IMAGE, 0, 0, width=self.width, height=self.height,
                            preserveAspectRatio=False)
        
        # Right margin for text (from right edge)
        right_margin = 60
        text_x = self.width - right_margin
        
        # Position text in lower portion - right justified
        date_y = self.height * 0.28  # 28% from bottom
        vessel_y = date_y - 35       # Below date
        
        # Draw date period - RIGHT JUSTIFIED
        date_text = f"{format_date_short(self.start_date)} to {format_date_short(self.end_date)}"
        self.c.setFont('Helvetica', 16)
        self.c.setFillColorRGB(0.4, 0.4, 0.4)  # Grey color
        self.c.drawRightString(text_x, date_y, date_text)
        
        # Draw vessel name - RIGHT JUSTIFIED, bigger grey
        self.c.setFont('Helvetica-Bold', 24)
        self.c.setFillColorRGB(0.45, 0.45, 0.45)  # Grey color
        self.c.drawRightString(text_x, vessel_y, self.vessel_name)
        
        self.c.showPage()
    
    def draw_back_cover(self):
        """Draw back cover page"""
        if os.path.exists(BACK_IMAGE):
            self.c.drawImage(BACK_IMAGE, 0, 0, width=self.width, height=self.height,
                            preserveAspectRatio=False)
        self.c.showPage()
    
    def start_content_page(self, section_name, is_continuation=False):
        """Start a new content page with background and section header in green bar"""
        if not is_continuation:
            self.current_section = section_name
            self.section_page = 1
        else:
            self.section_page += 1

        # Draw background image
        if os.path.exists(CONTENT_IMAGE):
            self.c.drawImage(CONTENT_IMAGE, 0, 0, width=self.width, height=self.height,
                            preserveAspectRatio=False)

        # Draw section name in the green header bar
        self.c.setFont('Helvetica-Bold', 22)
        self.c.setFillColorRGB(1, 1, 1)  # White text on green bar
        header_y = self.height - 55
        text_x = 150

        # Show "Section Page N" for continuation pages
        if is_continuation:
            display_name = f"{self.current_section} Page {self.section_page}"
        else:
            display_name = section_name
        self.c.drawString(text_x, header_y, display_name)

        # Reset y position for content - start below green header bar
        self.y_position = self.header_bar_bottom - 40
        self.grid_position = 0  # Reset grid for new section
    
    def add_chart(self, chart_bytes, chart_width=None, chart_height=None):
        """Add a chart in 2x2 grid layout"""
        if chart_bytes is None:
            return False
        
        # Grid dimensions for 2x2 layout - wider charts with reduced margins
        grid_chart_width = 275   # Width for each chart in grid
        grid_chart_height = 245  # Height for each chart
        h_gap = 8                # Horizontal gap between charts
        v_gap = 15               # Vertical gap between rows
        
        # Start new row if needed
        if self.grid_position == 0:
            # Check if we need a new page
            if self.y_position - grid_chart_height < 85:
                self.c.showPage()
                self.start_content_page(self.current_section, is_continuation=True)
            self.grid_row_y = self.y_position
        
        # Calculate x position (left or right column)
        if self.grid_position % 2 == 0:  # Left column
            x_pos = self.margin_left
        else:  # Right column
            x_pos = self.margin_left + grid_chart_width + h_gap

        # Calculate y position
        if self.grid_position < 2:  # Top row
            y_pos = self.grid_row_y - grid_chart_height
        else:  # Bottom row
            y_pos = self.grid_row_y - (grid_chart_height * 2) - v_gap
        
        # Draw chart
        chart_bytes.seek(0)
        img = ImageReader(chart_bytes)
        self.c.drawImage(img, x_pos, y_pos, width=grid_chart_width, height=grid_chart_height)
        
        # Update grid position
        self.grid_position += 1
        
        # After 4 charts, reset grid and update y_position
        if self.grid_position >= 4:
            self.grid_position = 0
            self.y_position = y_pos - v_gap
        
        return True
    
    def flush_grid(self):
        """Flush remaining charts in grid and reset position"""
        if self.grid_position > 0:
            # Calculate how far down we went
            rows_used = (self.grid_position + 1) // 2
            chart_h = 260
            v_gap = 15
            self.y_position = self.grid_row_y - (rows_used * chart_h) - ((rows_used - 1) * v_gap) - v_gap
            self.grid_position = 0

    def add_wide_chart(self, chart_bytes):
        """Add a full-width chart (spans 2 columns)"""
        if chart_bytes is None:
            return False
        
        # Flush any pending grid charts first
        self.flush_grid()
        
        wide_chart_width = self.content_width  # Full width
        wide_chart_height = 280  # Slightly taller
        v_gap = 15
        
        # Check if we need a new page
        if self.y_position - wide_chart_height < 85:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        # Draw chart at full width
        chart_bytes.seek(0)
        img = ImageReader(chart_bytes)
        y_pos = self.y_position - wide_chart_height
        self.c.drawImage(img, self.margin_left, y_pos, width=wide_chart_width, height=wide_chart_height)
        
        self.y_position = y_pos - v_gap
        return True
    
    def add_subsection(self, title):
        """Add a subsection header"""
        if self.y_position < 150:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        self.c.setFont('Helvetica-Bold', 13)
        self.c.setFillColorRGB(0.2, 0.4, 0.35)  # Dark teal color
        self.c.drawString(self.margin_left, self.y_position, title)
        self.y_position -= 22
    
    def add_text(self, text, italic=False):
        """Add text line"""
        if self.y_position < 85:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        if italic:
            self.c.setFont('Helvetica-Oblique', 10)
        else:
            self.c.setFont('Helvetica', 10)
        self.c.setFillColorRGB(0.35, 0.35, 0.35)
        self.c.drawString(self.margin_left, self.y_position, text)
        self.y_position -= 16
    
    def add_table(self, data, headers, col_widths=None):
        """Add a table to the current page"""
        if not data:
            return
        
        from reportlab.platypus import Table, TableStyle
        
        table_data = [headers] + data
        
        if col_widths is None:
            col_widths = [self.content_width / len(headers)] * len(headers)
        
        table = Table(table_data, colWidths=col_widths)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f57c00')),  # Orange header
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('TOPPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#dee2e6')),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        # Calculate table height
        table_height = len(table_data) * 22 + 10
        
        if self.y_position - table_height < 85:
            self.c.showPage()
            self.start_content_page(self.current_section, is_continuation=True)
        
        table.wrapOn(self.c, self.content_width, table_height)
        table.drawOn(self.c, self.margin_left, self.y_position - table_height)
        self.y_position -= (table_height + 25)
    
    def end_section(self):
        """End current section and start new page"""
        self.c.showPage()

    def add_section_alerts(self, alerts, equipment_patterns):
        """Add alerts for specific equipment inline"""
        if not alerts:
            return

        # Filter alerts matching equipment patterns
        section_alerts = []
        for alert in alerts:
            sp_name = alert.get('sampling_point_name', '').upper()
            for pattern in equipment_patterns:
                if pattern.upper() in sp_name:
                    section_alerts.append(alert)
                    break

        if not section_alerts:
            return

        # Flush any pending grid charts
        self.flush_grid()

        self.add_subsection("Alerts")
        headers = ['Date', 'Parameter', 'Value', 'Range']
        rows = []
        for alert in section_alerts[:10]:  # Limit to 10 per section
            rows.append([
                format_date(alert.get('alert_date', ''))[:10],
                alert.get('parameter_name', 'N/A')[:20],
                str(alert.get('measured_value', 'N/A'))[:8],
                f"{alert.get('expected_low', '-')}-{alert.get('expected_high', '-')}"[:12]
            ])

        col_widths = None  # Full width
        self.add_table(rows, headers, col_widths)

    def save(self):
        """Save the PDF"""
        self.c.save()


def generate_boiler_section(pdf, vessel_id, start_date, end_date):
    """Generate boiler water analysis section with separate Aux/EGE and Hotwell plots"""
    pdf.start_content_page("Boiler Water Analysis")
    
    # Parameters for Aux/EGE boilers
    boiler_params = ['Phosphate', 'Alkalinity P', 'Alkalinity M', 'Chloride', 'pH', 'Conductivity']
    # Parameters for Hotwell
    hotwell_params = ['Chloride', 'pH', 'Hydrazine', 'Conductivity']
    
    # Equipment mappings
    boiler_map = {
        'Aux1': 'AB1 Aux Boiler 1',
        'Aux2': 'AB2 Aux Boiler 2',
        'EGE': 'CB Composite Boiler'
    }
    hotwell_map = {
        'Hotwell': 'HW Hot Well'
    }
    
    # Collect data for Aux/EGE boilers
    boiler_data = []
    for boiler_id, equipment_name in boiler_map.items():
        data = get_measurements_by_equipment_name(vessel_id, equipment_name, boiler_params, start_date, end_date)
        if data:
            for item in data:
                item_copy = dict(item)
                item_copy['unit_id'] = boiler_id
                boiler_data.append(item_copy)
    
    # Collect data for Hotwell
    hotwell_data = []
    for hw_id, equipment_name in hotwell_map.items():
        data = get_measurements_by_equipment_name(vessel_id, equipment_name, hotwell_params, start_date, end_date)
        if data:
            for item in data:
                item_copy = dict(item)
                item_copy['unit_id'] = hw_id
                hotwell_data.append(item_copy)
    
    # Helper to extract limits from data
    def get_limits(data_list):
        for d in data_list:
            low = d.get('ideal_low')
            high = d.get('ideal_high')
            if low is not None and high is not None:
                return float(low), float(high)
        return None, None
    
    # Generate Aux/EGE boiler charts
    if boiler_data:
        params_found = set()
        for item in boiler_data:
            for param in boiler_params:
                if param.lower() in item.get('parameter_name', '').lower():
                    params_found.add(item.get('parameter_name'))
        
        for param_name in sorted(params_found):
            param_data = [d for d in boiler_data if param_name.lower() in d.get('parameter_name', '').lower()]
            if param_data:
                ideal_low, ideal_high = get_limits_for_pdf('AUX BOILER & EGE', param_name)
                chart = create_line_chart_by_unit(
                    param_data,
                    title=param_name,
                    color_scheme=BOILER_COLORS,
                    ideal_low=ideal_low,
                    ideal_high=ideal_high,
                    unit_field='unit_id',
                    equipment_type='AUX BOILER & EGE'
                )
                pdf.add_chart(chart)
    
    # Generate Hotwell charts (separate section)
    if hotwell_data:
        pdf.add_subsection("Hotwell")
        params_found = set()
        for item in hotwell_data:
            for param in hotwell_params:
                if param.lower() in item.get('parameter_name', '').lower():
                    params_found.add(item.get('parameter_name'))
        
        for param_name in sorted(params_found):
            param_data = [d for d in hotwell_data if param_name.lower() in d.get('parameter_name', '').lower()]
            if param_data:
                ideal_low, ideal_high = get_limits_for_pdf('HOTWELL', param_name)
                chart = create_line_chart_by_unit(
                    param_data,
                    title=param_name,
                    color_scheme={'Hotwell': '#ffc107'},
                    ideal_low=ideal_low,
                    ideal_high=ideal_high,
                    unit_field='unit_id',
                    equipment_type='HOTWELL'
                )
                pdf.add_chart(chart)
    
    # Add boiler alerts at end of section
    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)
    pdf.add_section_alerts(alerts, ['BOILER', 'AB1', 'AB2', 'EGE', 'CB', 'HOTWELL', 'HW'])

    pdf.end_section()


def generate_main_engine_section(pdf, vessel_id, start_date, end_date):
    """Generate main engine analysis section"""
    pdf.start_content_page("Main Engine")

    # Cooling water
    cooling_params = ['Nitrite', 'pH', 'Chloride']
    all_cooling = []
    for me_id in ['ME1', 'ME2']:
        data = get_measurements_by_equipment_name(vessel_id, f'{me_id} Main Engine', cooling_params, start_date, end_date)
        if not data:
            data = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', cooling_params, start_date, end_date)
        if data:
            for item in data:
                item_copy = dict(item)
                item_copy['unit_id'] = me_id
                all_cooling.append(item_copy)

    if all_cooling:
        chart = create_multi_line_chart(all_cooling, cooling_params, "Cooling Water", equipment_type='HT & LT COOLING WATER')
        pdf.add_chart(chart)

    # Lube oil
    lube_params = ['TBN', 'Water Content', 'Viscosity', 'BaseNumber']
    lube_data = get_measurements_by_equipment_name(vessel_id, 'ME Main Engine', lube_params, start_date, end_date)

    if lube_data:
        chart = create_multi_line_chart(lube_data, lube_params, "Lube Oil")
        pdf.add_chart(chart)

    # Scavenge drain time series and scatter plots
    scavenge_params = ['Iron', 'BaseNumber']
    scavenge_data = get_measurements_for_scavenge_drains(vessel_id, scavenge_params, start_date, end_date)

    if scavenge_data:
        # Iron in Oil time series chart
        chart = create_multi_line_chart(scavenge_data, ['Iron'], "Iron in Oil")
        if chart:
            pdf.add_chart(chart)

        # Base Number time series chart
        chart = create_multi_line_chart(scavenge_data, ['BaseNumber'], "Base Number")
        if chart:
            pdf.add_chart(chart)

        # Iron vs Base Number scatter plot
        chart = create_scatter_chart(
            scavenge_data,
            'BaseNumber', 'Iron',
            "Iron vs BN",
            group_field='sampling_point_name'
        )
        pdf.add_chart(chart)

    # Add ME alerts at end
    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)
    pdf.add_section_alerts(alerts, ['ME', 'MAIN ENGINE', 'SCAVENGE'])

    pdf.end_section()


def generate_aux_engine_section(pdf, vessel_id, start_date, end_date):
    """Generate auxiliary engines analysis section"""
    cooling_params = ['Nitrite', 'pH', 'Chloride']
    lube_params = ['TBN', 'BaseNumber', 'Viscosity']

    # First check if ANY aux engine has data
    has_any_data = False
    for engine_num in [1, 2, 3]:
        engine_name = f'AE{engine_num} Aux Engine'
        if get_measurements_by_equipment_name(vessel_id, engine_name, cooling_params, start_date, end_date):
            has_any_data = True
            break
        if get_measurements_by_equipment_name(vessel_id, engine_name, lube_params, start_date, end_date):
            has_any_data = True
            break

    if not has_any_data:
        return  # Skip entire section if no data

    pdf.start_content_page("Aux Engines")

    for engine_num in [1, 2, 3]:
        engine_name = f'AE{engine_num} Aux Engine'
        cooling_data = get_measurements_by_equipment_name(vessel_id, engine_name, cooling_params, start_date, end_date)
        lube_data = get_measurements_by_equipment_name(vessel_id, engine_name, lube_params, start_date, end_date)

        if cooling_data:
            chart = create_multi_line_chart(cooling_data, cooling_params, f"AE{engine_num} Cooling", equipment_type='HT & LT COOLING WATER')
            pdf.add_chart(chart)
        if lube_data:
            chart = create_multi_line_chart(lube_data, lube_params, f"AE{engine_num} Lube")
            pdf.add_chart(chart)

    # Add AE alerts at end
    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)
    pdf.add_section_alerts(alerts, ['AE', 'AUX ENGINE'])

    pdf.end_section()


def generate_potable_water_section(pdf, vessel_id, start_date, end_date):
    """Generate potable water analysis section as table"""
    pw_params = ['pH', 'Alkalinity', 'Chlorine', 'TDS', 'Turbidity', 'Hardness', 'Chloride']

    all_data = []
    for pw_id in ['PW1', 'PW2']:
        data = get_measurements_by_equipment_name(vessel_id, f'{pw_id} Potable Water', pw_params, start_date, end_date)
        if data:
            all_data.extend(data)

    if not all_data:
        return  # Skip section if no data

    pdf.start_content_page("Potable Water")

    if all_data:
        # Group by date and parameter for table format
        from collections import defaultdict
        by_date = defaultdict(dict)
        for item in all_data:
            date = item.get('measurement_date', '')[:10]
            param = item.get('parameter_name', '')
            value = item.get('value_numeric', '')
            # Shorten param name
            for p in pw_params:
                if p.lower() in param.lower():
                    by_date[date][p] = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
                    break

        # Build table rows
        headers = ['Date'] + pw_params
        rows = []
        for date in sorted(by_date.keys(), reverse=True)[:15]:  # Last 15 dates
            row = [date]
            for p in pw_params:
                row.append(by_date[date].get(p, '-'))
            rows.append(row)

        if rows:
            col_widths = [70] + [60] * len(pw_params)
            pdf.add_table(rows, headers, col_widths)

    pdf.end_section()


def generate_treated_sewage_section(pdf, vessel_id, start_date, end_date):
    """Generate treated sewage analysis section as table"""
    gw_params = ['pH', 'COD', 'Chlorine', 'Turbidity', 'Coliform', 'TSS']
    gw_data = get_measurements_by_equipment_name(vessel_id, 'GW Treated Sewage', gw_params, start_date, end_date)

    if not gw_data:
        return  # Skip section if no data

    pdf.start_content_page("Treated Sewage")

    if gw_data:
        from collections import defaultdict
        by_date = defaultdict(dict)
        for item in gw_data:
            date = item.get('measurement_date', '')[:10]
            param = item.get('parameter_name', '')
            value = item.get('value_numeric', '')
            for p in gw_params:
                if p.lower() in param.lower():
                    by_date[date][p] = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
                    break

        headers = ['Date'] + gw_params
        rows = []
        for date in sorted(by_date.keys(), reverse=True)[:15]:
            row = [date]
            for p in gw_params:
                row.append(by_date[date].get(p, '-'))
            rows.append(row)

        if rows:
            col_widths = [70] + [70] * len(gw_params)
            pdf.add_table(rows, headers, col_widths)

    pdf.end_section()


def generate_alerts_section(pdf, vessel_id, start_date, end_date):
    """Generate alerts summary section"""
    pdf.start_content_page("Alerts Summary")
    
    alerts = get_alerts_for_vessel(vessel_id, unresolved_only=True)
    
    if alerts:
        headers = ['Date', 'Location', 'Parameter', 'Value', 'Range', 'Type']
        rows = []
        
        for alert in alerts[:25]:  # Limit to 25 most recent
            rows.append([
                format_date(alert.get('alert_date', ''))[:10],
                alert.get('sampling_point_name', 'N/A')[:20],
                alert.get('parameter_name', 'N/A')[:15],
                str(alert.get('measured_value', 'N/A'))[:8],
                f"{alert.get('expected_low', '-')}-{alert.get('expected_high', '-')}"[:10],
                alert.get('alert_type', 'N/A')[:10]
            ])
        
        col_widths = [70, 100, 90, 50, 70, 60]
        pdf.add_table(rows, headers, col_widths)
        
        if len(alerts) > 25:
            pdf.add_text(f"Showing 25 of {len(alerts)} total alerts", italic=True)
    else:
        pdf.add_text("No unresolved alerts", italic=True)
    
    pdf.end_section()


def generate_report_bytes(vessel_id, vessel_name, start_date, end_date, selected_sections=None):
    """
    Generate PDF report and return as bytes (for web integration)
    """
    if selected_sections is None:
        selected_sections = list(AVAILABLE_SECTIONS.keys())
    
    # Create PDF in memory
    output = io.BytesIO()
    pdf = ReportPDFGenerator(output, vessel_name, start_date, end_date)
    
    # Cover page
    pdf.draw_cover_page()
    
    # Generate selected sections
    section_generators = {
        'boiler': generate_boiler_section,
        'main_engines': generate_main_engine_section,
        'aux_engines': generate_aux_engine_section,
        'potable_water': generate_potable_water_section,
        'treated_sewage': generate_treated_sewage_section,
        'central_cooling': generate_central_cooling_section,
        'ballast_water': generate_ballast_water_section,
        'egcs': generate_egcs_section
    }
    
    for section_key in selected_sections:
        if section_key in section_generators:
            try:
                section_generators[section_key](pdf, vessel_id, start_date, end_date)
            except Exception as e:
                print(f"Error generating section {section_key}: {e}")
                import traceback
                traceback.print_exc()
                continue
    
    # Back cover
    pdf.draw_back_cover()
    
    # Save and return
    pdf.save()
    output.seek(0)
    return output.getvalue()


def main():
    """CLI main function"""
    parser = argparse.ArgumentParser(description='Generate PDF report for vessel measurements')
    parser.add_argument('vessel_id', type=int, help='Vessel database ID')
    parser.add_argument('--start-date', type=str, help='Start date (YYYY-MM-DD)')
    parser.add_argument('--end-date', type=str, help='End date (YYYY-MM-DD)')
    parser.add_argument('--output-dir', type=str, default='reports', help='Output directory')
    parser.add_argument('--sections', type=str, nargs='+', choices=list(AVAILABLE_SECTIONS.keys()))

    args = parser.parse_args()

    if args.end_date:
        end_date = datetime.strptime(args.end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()

    if args.start_date:
        start_date = datetime.strptime(args.start_date, '%Y-%m-%d')
    else:
        start_date = end_date - timedelta(days=30)

    vessel = get_vessel_by_id(args.vessel_id)
    if not vessel:
        print(f"Error: Vessel ID {args.vessel_id} not found")
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    filename = f"{vessel['vessel_name'].replace(' ', '_')}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    output_path = os.path.join(args.output_dir, filename)

    print(f"Generating report for {vessel['vessel_name']}...")
    print(f"Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")

    sections = args.sections if args.sections else list(AVAILABLE_SECTIONS.keys())
    pdf_bytes = generate_report_bytes(args.vessel_id, vessel['vessel_name'], start_date, end_date, sections)

    with open(output_path, 'wb') as f:
        f.write(pdf_bytes)

    print(f"\nReport generated successfully: {output_path}")
    print(f"File size: {len(pdf_bytes) / 1024:.1f} KB")


if __name__ == '__main__':
    main()


def generate_central_cooling_section(pdf, vessel_id, start_date, end_date):
    """Generate central cooling water analysis section with charts"""
    # Central cooling parameters - pH, Nitrite, Chloride
    cooling_params = ['pH', 'Nitrite', 'Chloride']
    
    # Get data for HT/LT cooling systems
    ht_data = get_measurements_by_equipment_name(vessel_id, 'HT Central Cool', cooling_params, start_date, end_date)
    lt_data = get_measurements_by_equipment_name(vessel_id, 'LT Central Cool', cooling_params, start_date, end_date)
    
    if not ht_data and not lt_data:
        return  # Skip section if no data
    
    pdf.start_content_page("Central Cooling Water")
    
    # HT Cooling Water charts
    if ht_data:
        chart = create_multi_line_chart(ht_data, cooling_params, "HT Central Cooling", equipment_type='HT & LT COOLING WATER')
        if chart:
            pdf.add_chart(chart)
    
    # LT Cooling Water charts
    if lt_data:
        chart = create_multi_line_chart(lt_data, cooling_params, "LT Central Cooling", equipment_type='HT & LT COOLING WATER')
        if chart:
            pdf.add_chart(chart)
    
    pdf.end_section()


def generate_ballast_water_section(pdf, vessel_id, start_date, end_date):
    """Generate ballast water analysis section"""
    bw_params = ['Viable Count', 'E.coli', 'Enterococci', 'Vibrio', 'Chlorine']
    bw_data = get_measurements_by_equipment_name(vessel_id, 'BW Ballast', bw_params, start_date, end_date)
    
    if not bw_data:
        return  # Skip section if no data
    
    pdf.start_content_page("Ballast Water")
    
    # Create table for ballast water data
    from collections import defaultdict
    by_date = defaultdict(dict)
    for item in bw_data:
        date = item.get('measurement_date', '')[:10]
        param = item.get('parameter_name', '')
        value = item.get('value_numeric', '')
        for p in bw_params:
            if p.lower() in param.lower():
                by_date[date][p] = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
                break
    
    headers = ['Date'] + bw_params
    rows = []
    for date in sorted(by_date.keys(), reverse=True)[:15]:
        row = [date]
        for p in bw_params:
            row.append(by_date[date].get(p, '-'))
        rows.append(row)
    
    if rows:
        col_widths = [70] + [65] * len(bw_params)
        pdf.add_table(rows, headers, col_widths)
    
    pdf.end_section()


def generate_egcs_section(pdf, vessel_id, start_date, end_date):
    """Generate EGCS (Exhaust Gas Cleaning System) analysis section"""
    egcs_params = ['pH', 'PAH', 'Turbidity', 'Nitrate']
    egcs_data = get_measurements_by_equipment_name(vessel_id, 'EGCS', egcs_params, start_date, end_date)
    
    if not egcs_data:
        return  # Skip section if no data
    
    pdf.start_content_page("EGCS")
    
    # Create table for EGCS data
    from collections import defaultdict
    by_date = defaultdict(dict)
    for item in egcs_data:
        date = item.get('measurement_date', '')[:10]
        param = item.get('parameter_name', '')
        value = item.get('value_numeric', '')
        for p in egcs_params:
            if p.lower() in param.lower():
                by_date[date][p] = f"{value:.1f}" if isinstance(value, (int, float)) else str(value)
                break
    
    headers = ['Date'] + egcs_params
    rows = []
    for date in sorted(by_date.keys(), reverse=True)[:15]:
        row = [date]
        for p in egcs_params:
            row.append(by_date[date].get(p, '-'))
        rows.append(row)
    
    if rows:
        col_widths = [80] + [80] * len(egcs_params)
        pdf.add_table(rows, headers, col_widths)
    
    pdf.end_section()

