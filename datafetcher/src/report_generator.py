#!/usr/bin/env python3
"""
Accuport Report Generator (Rebuilt)
Generates professional PDF reports with precise layout control.
"""
import argparse
import os
import sys
import logging
import calendar
import csv
from datetime import datetime
import tempfile
import warnings

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Table, TableStyle
from sqlalchemy import create_engine

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Paths
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'accubase.sqlite')
REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'reports')

# Theme
COLOR_PRIMARY = colors.HexColor("#00639B")
COLOR_SECONDARY = colors.HexColor("#006874")
COLOR_ACCENT = colors.HexColor("#6D5E0F")
COLOR_GREY = colors.HexColor("#E0E2E5")

class ReportGenerator:
    def __init__(self, vessel_name, year, month, output_dir=REPORTS_DIR):
        self.vessel_name_query = vessel_name
        self.year = year
        self.month = month
        self.output_dir = output_dir
        self.engine = create_engine(f'sqlite:///{DB_PATH}')
        self.vessel_info = None
        self.data = None
        self.temp_files = []
        self.limits = {
            "AUX BOILER, COMPOSITE BOILER": {
                "PH": (9.5, 11.5, "9.5-11.5"),
                "P ALKALINITY": (150, 300, "150-300"),
                "CONDUCTIVITY": (0, 2250, "0-2250"),
                "CHLORIDE": (0, 200, "0-200"),
                "PHOSPHATE": (30, 70, "30-70"),
                "M ALKALINITY": (300, 600, "300-600")
            },
            "HOTWELL": {
                "PH": (8.5, 9.2, "8.5-9.2"),
                "DEHA": (80, 300, "80-300"),
                "HYDRAZINE": (100, 200, "100-200"),
                "CONDUCTIVITY": (0, 40, "0-40"),
                "CHLORIDE": (0, 6, "0-6")
            },
            "COOLING WATER": {
                "PH": (8.3, 10, "8.3-10"),
                "NITRITE": (1000, 2400, "1000-2400"),
                "CHLORIDE": (0, 50, "0-50")
            }
        }
        
        # Matplotlib setup
        sns.set_style("whitegrid")
        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.size'] = 8
        plt.rcParams['axes.edgecolor'] = "#70777C"

        os.makedirs(self.output_dir, exist_ok=True)

    def check_alerts(self, df):
        alerts = []
        if df.empty: return alerts
        
        for _, row in df.iterrows():
            sp_name = row['sp_name']
            param = row['p_name']
            val = row['value_numeric']
            date_str = row['measurement_date'].strftime('%Y-%m-%d')
            
            # Map SP to System Group
            system_key = None
            if any(x in sp_name for x in ["AB1", "AB2", "CB"]): system_key = "AUX BOILER, COMPOSITE BOILER"
            elif "HW" in sp_name: system_key = "HOTWELL"
            elif any(x in sp_name for x in ["ME", "AE", "SD"]): system_key = "COOLING WATER"
            elif any(x in sp_name for x in ["GW", "Sewage"]): system_key = "GREY WATER/SEWAGE"
            
            if system_key and system_key in self.limits:
                # Fuzzy match parameter? Or exact? The CSV has "PH", DB might have "pH"
                # Let's try case-insensitive match
                limit_info = None
                for lp, lv in self.limits[system_key].items():
                    if lp.lower() == param.lower():
                        limit_info = lv
                        break
                
                if limit_info:
                    min_v, max_v, range_str = limit_info
                    if val < min_v or val > max_v:
                        alerts.append([sp_name, param, f"{val}", range_str, date_str])
        return alerts

    def draw_alerts_table(self, c, alerts):
        if not alerts: return
        
        width, height = A4
        
        # Header
        c.setFillColor(colors.red)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(0.5*inch, 2.2*inch, "Alerts - Exceeding Limits")
        
        data = [['System', 'Parameter', 'Value', 'Limit', 'Date']] + alerts
        
        table = Table(data, colWidths=[1.5*inch, 2*inch, 1*inch, 1*inch, 1.5*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.red),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('FONTSIZE', (0,0), (-1,-1), 8),
        ]))
        
        table.wrapOn(c, width, height)
        table.drawOn(c, 0.5*inch, 1.2*inch) # Position above footer

    def fetch_data(self):
        # 1. Get Vessel
        try:
            q = f"SELECT * FROM vessels WHERE LOWER(vessel_name) LIKE '%%{self.vessel_name_query.lower()}%%' LIMIT 1"
            df = pd.read_sql(q, self.engine)
            if df.empty: raise ValueError("Vessel not found")
            self.vessel_info = df.iloc[0]
        except Exception as e:
            logger.error(str(e))
            sys.exit(1)

        # 2. Get Data
        start = f"{self.year}-{self.month:02d}-01"
        end = f"{self.year}-{self.month:02d}-{calendar.monthrange(self.year, self.month)[1]} 23:59:59"
        
        q = f"""
        SELECT m.measurement_date, m.value_numeric, m.unit, p.name as p_name, sp.name as sp_name
        FROM measurements m
        JOIN sampling_points sp ON m.sampling_point_id = sp.id
        JOIN parameters p ON m.parameter_id = p.id
        WHERE m.vessel_id = {self.vessel_info['id']} AND m.measurement_date BETWEEN '{start}' AND '{end}'
        """
        self.data = pd.read_sql(q, self.engine)
        self.data['measurement_date'] = pd.to_datetime(self.data['measurement_date'])

    def generate_plot(self, data, title):
        """Generate clean plot, return path"""
        if data.empty: return None
        
        fig, ax = plt.subplots(figsize=(5, 3))
        sns.lineplot(data=data, x='measurement_date', y='value_numeric', hue='sp_name', 
                     marker='o', markersize=4, linewidth=1.5, ax=ax)
        
        ax.set_title(title, fontsize=10, fontweight='bold', color="#00639B")
        ax.set_xlabel('')
        ax.set_ylabel(data.iloc[0]['unit'], fontsize=8)
        ax.grid(True, linestyle=':', color="#E0E2E5")
        ax.legend(title='', fontsize=6)
        
        locator = mdates.AutoDateLocator(maxticks=6)
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        
        sns.despine()
        plt.tight_layout()
        
        fd, path = tempfile.mkstemp(suffix=".png")
        plt.savefig(path, dpi=150)
        plt.close(fig)
        os.close(fd)
        self.temp_files.append(path)
        return path

    def draw_header(self, c, title):
        """Draw formal header and page background"""
        width, height = A4
        
        # Page Background (pages.png)
        bg_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'pages.png')
        if os.path.exists(bg_path):
            c.drawImage(bg_path, 0, 0, width=width, height=height)
            
        # Text (Changed to colors.white as requested)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 31)
        # Lowered by 0.5 cm (approx 0.197 inch) and now left-aligned
        c.drawString(0.5*inch, height - (0.7*inch + 0.197*inch), title)
        c.setFont("Helvetica", 16)
        # Lowered by 0.5 cm (approx 0.197 inch)
        c.drawRightString(width - 0.5*inch, height - (0.7*inch + 0.197*inch), "Accuport.Cloud")

    def draw_footer(self, c):
        """Draw footer with vessel info"""
        width, height = A4
        
        # Get full month name
        month_name = calendar.month_name[self.month]
        footer_text = f"{self.vessel_info['vessel_name']} Chemical analysis report {month_name} {self.year}"
        
        c.saveState()
        c.setFillColor(colors.white)
        c.setFont("Helvetica", 14) # Changed to 14pt
        # Move down by approximately 0.5 cm (0.19685 inches)
        c.drawCentredString(width/2, 0.5*inch - (0.5/2.54)*inch, footer_text) 
        c.restoreState()

    def draw_graphs_page(self, c, section_title, keywords):
        """Draw 2x3 grid of graphs"""
        width, height = A4
        self.draw_header(c, section_title)
        self.draw_footer(c)
        
        # Filter data
        mask = self.data['sp_name'].apply(lambda x: any(k in x for k in keywords))
        section_data = self.data[mask]
        if section_data.empty: 
            c.showPage()
            return
            
        # Check Alerts
        alerts = self.check_alerts(section_data)

        params = sorted(section_data['p_name'].unique())
        
        # Layout Constants
        MARGIN = 0.5 * inch
        
        # Grid Area
        grid_top = height - 1.5 * inch 
        plot_h = 2.6 * inch 
        plot_w = 3.5 * inch
        col_space = 0.2 * inch
        row_space = 0.2 * inch

        for i, param in enumerate(params):
            idx = i % 6
            if idx == 0 and i > 0:
                self.draw_footer(c)
                # Draw alerts if any on previous page? 
                # Complexity: Alerts should probably be per page content. 
                # If we split pages, we should split alerts too? 
                # Or just show all alerts for the section on the last page? 
                # User said "for every page". 
                # I'll stick to drawing all alerts for the section on the FIRST page or EVERY page? 
                # Let's draw alerts at the bottom of the LAST page of the section, or every page if it fits.
                # Simpler: Draw alerts on the page where space permits. 
                # With 6 graphs, space is tight (2.4 inch left).
                # Let's just draw it on every page for the *visible* data? 
                # No, `section_data` is for the whole section.
                # I will draw the alerts table on the page where the graphs are drawn. 
                # If multiple pages, I'll just draw it on the last one to avoid duplication, OR calculate alerts for the specific subset displayed.
                # Calculating for subset is better but harder to track.
                # I'll just draw the alerts table at the end of the loop (last page) for simplicity, 
                # or better: `self.draw_alerts_table(c, alerts)` at the end of method.
                c.showPage()
                self.draw_header(c, f"{section_title} (Cont.)")
                self.draw_footer(c)
            
            col = idx % 2
            row = idx // 2
            x = MARGIN + col * (plot_w + col_space)
            y = grid_top - ((row + 1) * plot_h) - (row * row_space)
            
            p_data = section_data[section_data['p_name'] == param]
            img = self.generate_plot(p_data, param)
            if img:
                c.drawImage(img, x, y, width=plot_w, height=plot_h)
        
        # Draw alerts at the bottom of the last page of the section
        self.draw_alerts_table(c, alerts)
        
        self.draw_footer(c)
        c.showPage()

    def draw_table_page(self, c, title, keywords):
        """Draw data table"""
        width, height = A4
        self.draw_header(c, title)
        self.draw_footer(c)
        
        mask = self.data['sp_name'].apply(lambda x: any(k in x for k in keywords))
        df = self.data[mask].sort_values(['sp_name', 'measurement_date'])
        if df.empty: 
            c.showPage()
            return
            
        # Check Alerts
        alerts = self.check_alerts(df)

        # Summarize
        summary = df.groupby(['sp_name', 'p_name']).agg(
            Val=('value_numeric', 'last'),
            Unit=('unit', 'first'),
            Date=('measurement_date', 'max')
        ).reset_index()
        summary['Date'] = summary['Date'].dt.strftime('%Y-%m-%d')
        
        data = [['System', 'Parameter', 'Value', 'Unit', 'Date']] + summary.values.tolist()
        
        table = Table(data, colWidths=[2*inch, 2.5*inch, 1*inch, 1*inch, 1*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), COLOR_SECONDARY),
            ('TEXTCOLOR', (0,0), (-1,0), colors.white),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.5, COLOR_GREY),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.whitesmoke])
        ]))
        
        table_height = table.wrapOn(c, width, height)[1]
        y_pos = height - (1.2 * inch + 0.5 * inch) - table_height 
        table.drawOn(c, 0.5*inch, y_pos)
        
        # Draw alerts below the main table
        # Need to check space.
        # If summary table is long, it might overlap. 
        # For now, I'll put it at fixed position bottom, assuming summary table isn't huge.
        self.draw_alerts_table(c, alerts)
        
        self.draw_footer(c)
        c.showPage()

    def generate(self):
        self.fetch_data()
        fname = os.path.join(self.output_dir, f"{self.vessel_info['vessel_id']}_{self.year}_{self.month:02d}.pdf")
        c = canvas.Canvas(fname, pagesize=A4)
        
        # Cover
        width, height = A4
        cover_image_found = False
        possible_cover_files = ['cover.jpg', 'cover.png']
        
        for cover_file_name in possible_cover_files:
            cover_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), cover_file_name)
            if os.path.exists(cover_path):
                c.drawImage(cover_path, 0, 0, width=width, height=height)
                cover_image_found = True
                break
        
        if not cover_image_found:
            # Fallback if no cover image is found
            c.setFillColor(COLOR_PRIMARY)
            c.rect(0, 0, width, height, fill=True)
            c.setFillColor(colors.white)
            c.setFont("Helvetica-Bold", 40)
            c.drawCentredString(width/2, height/2, "MONTHLY REPORT")

        # Overlay Text (Vessel Name & Date)
        # Assuming the cover design requires black text; adjust if needed.
        c.setFillColor(colors.black) 
        c.setFont("Helvetica-Bold", 24)
        
        # Format date as "Nov 2025"
        date_str = datetime(self.year, self.month, 1).strftime('%b %Y')
        
        # Draw aligned to the right margin
        c.drawRightString(width - 0.5*inch, height/2 - 2.0*inch, f"{self.vessel_info['vessel_name']}")
        c.setFont("Helvetica", 16)
        c.drawRightString(width - 0.5*inch, height/2 - 2.4*inch, date_str)
        
        c.showPage()

        # Content
        self.draw_graphs_page(c, "Boiler Systems", ["AB1", "AB2", "CB", "HW"])
        
        self.draw_graphs_page(c, "Main Engine", ["ME"])
        self.draw_graphs_page(c, "Auxiliary Engine", ["AE"])
        self.draw_graphs_page(c, "Scavenge Drain", ["SD"])
        
        self.draw_graphs_page(c, "Potable Water", ["PW"])
        self.draw_graphs_page(c, "Grey Water", ["GW"])
        self.draw_graphs_page(c, "Ballast Water", ["Ballast"])
        
        c.save()
        print(f"Report: {fname}")
        
        for f in self.temp_files: os.remove(f)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("vessel")
    parser.add_argument("--month", default=datetime.now().strftime("%Y-%m"))
    args = parser.parse_args()
    y, m = map(int, args.month.split('-'))
    ReportGenerator(args.vessel, y, m).generate()