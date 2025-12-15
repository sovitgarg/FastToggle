#!/bin/bash
# Check toggle status for all URLs in ToggleExcel_B.xlsx

# Navigate to parent folder (FastToggle)
cd "$(dirname "$0")/.."

echo "========================================="
echo "  Toggle Status Checker - Group B"
echo "========================================="
echo ""

# Check 1: Python installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo ""
    echo "Please install Python first:"
    echo "  Option 1: brew install python3"
    echo "  Option 2: Download from https://www.python.org/downloads/"
    echo ""
    read -p "Press Enter to exit..."
    exit 1
fi

# Check 2: Virtual environment exists
if [ ! -d "_system/venv" ]; then
    SETUP_NEEDED=true
else
    SETUP_NEEDED=false
fi

# Check 3: Required packages installed
if [ "$SETUP_NEEDED" = false ]; then
    source _system/venv/bin/activate
    if ! python3 -c "import playwright, pandas, openpyxl" 2>/dev/null; then
        SETUP_NEEDED=true
        deactivate 2>/dev/null
    fi
fi

# Run setup if needed
if [ "$SETUP_NEEDED" = true ]; then
    echo ""
    echo "========================================="
    echo "  Running First-Time Setup"
    echo "========================================="
    echo ""

    mkdir -p _system/scripts _system/logs output

    echo "Creating virtual environment..."
    python3 -m venv _system/venv

    source _system/venv/bin/activate

    echo "Installing dependencies..."
    pip install --upgrade pip --quiet
    pip install playwright pandas openpyxl --quiet

    echo "Installing browser (this may take a minute)..."
    playwright install chromium

    echo ""
    echo "Setup complete!"
    echo ""
fi

# Activate virtual environment
source _system/venv/bin/activate

# Check for Excel file
if [ ! -f "ToggleExcel_B.xlsx" ]; then
    echo "ERROR: ToggleExcel_B.xlsx not found"
    echo "Please create ToggleExcel_B.xlsx with columns: URL, userid, password"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Checking toggle status for Group B..."
echo ""

python3 _system/scripts/check_status.py "ToggleExcel_B.xlsx" --no-headless

# Move results to output folder
mv status_report.xlsx output/status_report_B.xlsx 2>/dev/null
mv status_check_*.log _system/logs/ 2>/dev/null

echo ""
echo "========================================="
echo "  Status Check Complete!"
echo "========================================="
echo "Results saved in 'output' folder"
echo ""
read -p "Press Enter to exit..."
