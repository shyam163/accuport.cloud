#!/bin/bash
# Accuport Dashboard Setup Script

echo "======================================================================="
echo "Accuport.cloud Dashboard Setup"
echo "======================================================================="
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    exit 1
fi

echo "Step 1: Installing Python dependencies..."
pip install -r requirements.txt
echo ""

echo "Step 2: Initializing users database..."
python3 init_users_db.py
echo ""

echo "======================================================================="
echo "Setup Complete!"
echo "======================================================================="
echo ""
echo "To start the dashboard, run:"
echo "  python3 app.py"
echo ""
echo "Then open your browser to: http://localhost:5000"
echo ""
echo "Login credentials:"
echo "  super1 / super1pass (Vessel Manager - M.V Racer, MT Aqua)"
echo "  super2 / super2pass (Vessel Manager - MT Voyager, MV October)"
echo "  fleet1 / fleet1pass (Fleet Manager - All 4 vessels)"
echo "  admin  / adminpass  (Administrator - All 4 vessels)"
echo ""
echo "Features: Material Design UI with custom color palette"
echo "======================================================================="
