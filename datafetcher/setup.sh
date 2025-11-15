#!/bin/bash
# Setup script for Labcom Data Fetcher

echo "================================================"
echo "Labcom Data Fetcher - Setup"
echo "================================================"
echo ""

# Install dependencies
echo "1. Installing Python dependencies..."
pip install -q -r requirements.txt

if [ $? -eq 0 ]; then
    echo "   ✓ Dependencies installed successfully"
else
    echo "   ✗ Failed to install dependencies"
    exit 1
fi

echo ""

# Create data directory
echo "2. Creating data directory..."
mkdir -p data
echo "   ✓ Data directory created"

echo ""

# Initialize database
echo "3. Initializing SQLite database..."
cd src
python db_schema.py > /dev/null 2>&1
cd ..

if [ -f "data/accubase.sqlite" ]; then
    echo "   ✓ Database created at data/accubase.sqlite"
else
    echo "   ✗ Failed to create database"
    exit 1
fi

echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "Next steps:"
echo "1. Edit config/vessels_config.yaml with your vessel auth tokens"
echo "2. Run: cd src && python fetch_labcom_data.py"
echo ""
