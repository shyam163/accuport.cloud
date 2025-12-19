"""
Import parameter limits from limits.txt into users.sqlite
"""
import sqlite3
import os
import re

def parse_limits_file(filepath):
    """
    Parse limits.txt file with format:
    EQUIPMENT TYPE
        PARAMETER_NAME	range

    Returns: List of (equipment_type, parameter_name, lower_limit, upper_limit)
    """
    results = []
    current_equipment = None

    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.rstrip()
            if not line:
                continue

            # Check if it's an equipment header (not indented)
            if not line.startswith(' ') and not line.startswith('\t'):
                # Equipment header, may have comma-separated aliases
                equipment_types = [e.strip() for e in line.split(',')]
                current_equipment = equipment_types
                print(f"Found equipment type(s): {equipment_types}")
            else:
                # Parameter line (indented with tabs or spaces)
                line = line.strip()

                # Split on tab to separate parameter name from range
                if '\t' in line:
                    parts = line.split('\t')
                    if len(parts) >= 2:
                        param_name = parts[0].strip().upper()
                        range_str = parts[1].strip()

                        # Remove units and extra text
                        range_str = re.sub(r'\s*(mg/L|ppm|%|units).*$', '', range_str, flags=re.IGNORECASE)
                        range_str = range_str.strip()

                        # Handle different range formats
                        # Format: "X – Y" (en dash or hyphen)
                        # Format: "≤ X" (less than or equal)

                        if '–' in range_str or '-' in range_str:
                            # Range format: "6.5 – 8.5" or "100 - 300"
                            # Replace en dash with hyphen
                            range_str = range_str.replace('–', '-').replace(' ', '')

                            parts = range_str.split('-')
                            if len(parts) == 2:
                                try:
                                    lower = float(parts[0].strip())
                                    upper = float(parts[1].strip())

                                    # Add entry for each equipment type
                                    if current_equipment:
                                        for equip in current_equipment:
                                            results.append((equip.upper(), param_name, lower, upper))
                                            print(f"  Added: {equip.upper()} - {param_name}: {lower}-{upper}")
                                except ValueError as e:
                                    print(f"  WARNING: Could not parse range '{range_str}' for {param_name} (line {line_num}): {e}")

                        elif '≤' in range_str or '<=' in range_str or range_str.startswith('0 '):
                            # "≤ X" format or "0 mg/L" - use 0 as lower limit
                            try:
                                # Extract number
                                num_match = re.search(r'[\d.]+', range_str)
                                if num_match:
                                    upper = float(num_match.group())
                                    lower = 0.0

                                    if current_equipment:
                                        for equip in current_equipment:
                                            results.append((equip.upper(), param_name, lower, upper))
                                            print(f"  Added: {equip.upper()} - {param_name}: {lower}-{upper}")
                            except ValueError as e:
                                print(f"  WARNING: Could not parse limit '{range_str}' for {param_name} (line {line_num}): {e}")

    return results

def import_to_database(data, db_path):
    """Insert parsed limits into database"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Clear existing data
    cursor.execute("DELETE FROM parameter_limits")
    print(f"\nCleared existing parameter_limits table")

    # Insert new data
    for equipment, parameter, lower, upper in data:
        cursor.execute("""
            INSERT OR REPLACE INTO parameter_limits
            (equipment_type, parameter_name, lower_limit, upper_limit)
            VALUES (?, ?, ?, ?)
        """, (equipment, parameter, lower, upper))

    conn.commit()
    conn.close()
    print(f"\n✓ Successfully imported {len(data)} limit records")

if __name__ == '__main__':
    limits_file = '/var/www/accuport.cloud/dashbored/limits.txt'
    db_path = '/var/www/accuport.cloud/dashbored/users.sqlite'

    if not os.path.exists(limits_file):
        print(f"ERROR: limits.txt not found at {limits_file}")
        exit(1)

    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}")
        exit(1)

    print(f"Parsing {limits_file}...")
    data = parse_limits_file(limits_file)

    if not data:
        print("ERROR: No data parsed from limits.txt")
        exit(1)

    print(f"\nImporting to {db_path}...")
    import_to_database(data, db_path)
