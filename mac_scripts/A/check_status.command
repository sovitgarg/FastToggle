#!/bin/bash
# Check toggle status for all URLs

cd "$(dirname "$0")/../.."

echo "========================================="
echo "  Toggle Status Checker"
echo "========================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    read -p "Press Enter to exit..."
    exit 1
fi

if [ ! -d "_system/venv" ]; then
    SETUP_NEEDED=true
else
    SETUP_NEEDED=false
    source _system/venv/bin/activate
    if ! python3 -c "import playwright, pandas, openpyxl" 2>/dev/null; then
        SETUP_NEEDED=true
        deactivate 2>/dev/null
    fi
fi

if [ "$SETUP_NEEDED" = true ]; then
    echo "Running First-Time Setup..."
    mkdir -p _system/scripts _system/logs mac_scripts/A/output
    python3 -m venv _system/venv
    source _system/venv/bin/activate
    pip install --upgrade pip --quiet
    pip install playwright pandas openpyxl --quiet
    playwright install chromium
    echo "Setup complete!"
fi

source _system/venv/bin/activate

if [ ! -f "mac_scripts/A/ToggleExcel.xlsx" ]; then
    echo "ERROR: mac_scripts/A/ToggleExcel.xlsx not found"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Checking toggle status..."
python3 _system/scripts/check_status.py "mac_scripts/A/ToggleExcel.xlsx" --no-headless

mkdir -p mac_scripts/A/output
mv status_report.xlsx mac_scripts/A/output/status_report.xlsx 2>/dev/null
mv status_check_*.log _system/logs/ 2>/dev/null

echo ""
echo "Status Check Complete! Results in mac_scripts/A/output"
read -p "Press Enter to exit..."
