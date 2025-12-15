#!/bin/bash
# Set all toggles in ToggleExcel.xlsx to ON

cd "$(dirname "$0")/../.."

echo "========================================="
echo "  Toggle Automation - Set to ON"
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
    mkdir -p _system/scripts _system/logs mac_scripts/B/output
    python3 -m venv _system/venv
    source _system/venv/bin/activate
    pip install --upgrade pip --quiet
    pip install playwright pandas openpyxl --quiet
    playwright install chromium
    echo "Setup complete!"
fi

source _system/venv/bin/activate

if [ ! -f "mac_scripts/B/ToggleExcel.xlsx" ]; then
    echo "ERROR: mac_scripts/B/ToggleExcel.xlsx not found"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Setting all toggles to ON..."
python3 _system/scripts/toggle_automation.py "mac_scripts/B/ToggleExcel.xlsx" --state ON --no-headless

mkdir -p mac_scripts/B/output
mv toggle_results.xlsx mac_scripts/B/output/toggle_results_ON.xlsx 2>/dev/null
mv toggle_automation_*.log _system/logs/ 2>/dev/null

echo ""
echo "Automation Complete! Results in mac_scripts/B/output"
read -p "Press Enter to exit..."
