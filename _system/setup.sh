#!/bin/bash
# One-time setup script for Toggle Automation (Mac)

echo "========================================="
echo "  Toggle Automation - Setup"
echo "========================================="

# Navigate to parent folder (FastToggle)
cd "$(dirname "$0")/.."

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Install with: brew install python3"
    echo "Or download from: https://www.python.org/downloads/"
    exit 1
fi

# Create folder structure
mkdir -p _system/scripts _system/logs output

echo "Creating virtual environment..."
python3 -m venv _system/venv

echo "Activating virtual environment..."
source _system/venv/bin/activate

echo "Installing dependencies..."
pip install --upgrade pip
pip install playwright pandas openpyxl

echo "Installing Playwright browsers..."
playwright install chromium

echo ""
echo "========================================="
echo "  Setup Complete!"
echo "========================================="
echo ""
echo "Next steps:"
echo "1. Edit ToggleExcel.xlsx with your URLs"
echo "2. Double-click 'mac_scripts/run.command' to start"
echo ""
read -p "Press Enter to exit..."
