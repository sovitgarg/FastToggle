@echo off
REM One-time setup script for Toggle Automation (Windows)

echo =========================================
echo   Toggle Automation - Setup
echo =========================================

cd /d "%~dp0\.."

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation!
    pause
    exit /b 1
)

REM Create folder structure
if not exist "_system\scripts" mkdir _system\scripts
if not exist "_system\logs" mkdir _system\logs
if not exist "output" mkdir output

REM Create requirements.txt if not exists
if not exist "_system\scripts\requirements.txt" (
    echo playwright>=1.40.0> _system\scripts\requirements.txt
    echo pandas>=2.0.0>> _system\scripts\requirements.txt
    echo openpyxl>=3.1.0>> _system\scripts\requirements.txt
)

echo Creating virtual environment...
python -m venv _system\venv

echo Activating virtual environment...
call _system\venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip
pip install playwright pandas openpyxl

echo Installing Playwright browsers...
playwright install chromium

echo.
echo =========================================
echo   Setup Complete!
echo =========================================
echo.
echo Next steps:
echo 1. Edit ToggleExcel.xlsx with your URLs
echo 2. Double-click 'run.bat' to start
echo.
pause
