# Accuport Report Generator

This tool generates professional PDF monthly reports for vessel chemical data.

## Features
*   **Beautiful Design:** Custom headers, footers, and cover page.
*   **Visualizations:** Line charts for key systems (Boilers, Engines).
*   **Tabular Data:** Detailed logs for Potable Water and Sewage/Ballast.
*   **Flexible:** Filters by vessel name (fuzzy match) and month.

## Usage

```bash
python3 src/report_generator.py "Vessel Name" --month YYYY-MM
```

### Examples

Generate report for MT Aqua for November 2025:
```bash
python3 src/report_generator.py "mt aqua" --month 2025-11
```

Generate report for MV Racer for current month (default):
```bash
python3 src/report_generator.py "racer"
```

## Output
Reports are saved in the `reports/` directory with the format `{vessel_id}_Report_{YYYY}_{MM}.pdf`.

## Dependencies
*   pandas
*   matplotlib
*   seaborn
*   reportlab
*   sqlalchemy
