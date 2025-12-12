#!/bin/bash
# Double-click this file on Mac to run the automation

# Navigate to parent folder (FastToggle)
cd "$(dirname "$0")/.."

echo "========================================="
echo "  Toggle Automation"
echo "========================================="
echo ""

# Pre-requisite checks
SETUP_NEEDED=false

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
    echo "Virtual environment not found. Setting up..."
    SETUP_NEEDED=true
fi

# Check 3: Required packages installed
if [ "$SETUP_NEEDED" = false ] && [ -d "_system/venv" ]; then
    source _system/venv/bin/activate
    if ! python3 -c "import playwright, pandas, openpyxl" 2>/dev/null; then
        echo "Required packages missing. Setting up..."
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

    # Create folder structure
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
if [ ! -f "ToggleExcel.xlsx" ]; then
    echo "ERROR: ToggleExcel.xlsx not found"
    echo "Please create ToggleExcel.xlsx with columns: URL, Toggle, userid, password"
    read -p "Press Enter to exit..."
    exit 1
fi

echo "Starting automation..."
echo ""

# Run with visible browser
python3 _system/scripts/toggle_automation.py "ToggleExcel.xlsx" --no-headless

# Move results to output folder
mv toggle_results.xlsx output/ 2>/dev/null
mv toggle_automation_*.log _system/logs/ 2>/dev/null

echo ""
echo "========================================="
echo "  Automation Complete!"
echo "========================================="
echo "Results saved in 'output' folder"
echo ""
read -p "Press Enter to exit..."
