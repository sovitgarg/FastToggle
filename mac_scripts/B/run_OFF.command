#!/bin/bash
# Toggle all URLs in ToggleExcel.xlsx to OFF
# This script works from any folder - just copy the folder and run

cd "$(dirname "$0")"

echo "========================================="
echo "  Toggle Automation - Set to OFF"
echo "========================================="
echo ""

if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    read -p "Press Enter to exit..."
    exit 1
fi

if [ ! -d "../../_system/venv" ]; then
    SETUP_NEEDED=true
else
    SETUP_NEEDED=false
    source ../../_system/venv/bin/activate
    if ! python3 -c "import playwright, pandas, openpyxl" 2>/dev/null; then
        SETUP_NEEDED=true
        deactivate 2>/dev/null
    fi
fi

if [ "$SETUP_NEEDED" = true ]; then
    echo "Running First-Time Setup..."
    mkdir -p ../../_system/scripts ../../_system/logs output
    python3 -m venv ../../_system/venv
    source ../../_system/venv/bin/activate
    pip install --upgrade pip --quiet
    pip install playwright pandas openpyxl --quiet
    playwright install chromium
    echo "Setup complete!"
fi

source ../../_system/venv/bin/activate

if [ ! -f "ToggleExcel.xlsx" ]; then
    echo "ERROR: ToggleExcel.xlsx not found in this folder"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Setting all toggles to OFF..."
python3 ../../_system/scripts/toggle_automation.py "ToggleExcel.xlsx" --state OFF --no-headless

mkdir -p output
mv toggle_results.xlsx output/toggle_results_OFF.xlsx 2>/dev/null
mv toggle_automation_*.log ../../_system/logs/ 2>/dev/null

echo ""
echo "Automation Complete! Results in 'output' folder"
read -p "Press Enter to exit..."
