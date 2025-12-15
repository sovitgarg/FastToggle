@echo off
REM Toggle all URLs in ToggleExcel_B.xlsx to ON

cd /d "%~dp0"

echo =========================================
echo   Toggle Automation - Set B to ON
echo =========================================
echo.

REM Check 1: Python installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed
    echo.
    echo Please install Python first:
    echo   1. Go to https://www.python.org/downloads/
    echo   2. Download and install Python 3
    echo   3. IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    pause
    exit /b 1
)

REM Check 2: Virtual environment exists - if not, run setup
if not exist "_system\venv\Scripts\activate.bat" goto :setup

REM Check 3: Required packages installed
call _system\venv\Scripts\activate.bat
python -c "import playwright, pandas, openpyxl" >nul 2>&1
if errorlevel 1 goto :setup

REM All checks passed, skip to run
goto :run

:setup
echo.
echo =========================================
echo   Running First-Time Setup
echo =========================================
echo.

REM Create folder structure
if not exist "_system\scripts" mkdir _system\scripts
if not exist "_system\logs" mkdir _system\logs
if not exist "output" mkdir output

echo Creating virtual environment...
python -m venv _system\venv

call _system\venv\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip --quiet
pip install playwright pandas openpyxl --quiet

echo Installing browser - this may take a minute...
playwright install chromium

echo.
echo Setup complete!
echo.

:run
REM Activate virtual environment
call _system\venv\Scripts\activate.bat

REM Check for Excel file
if not exist "ToggleExcel_B.xlsx" (
    echo ERROR: ToggleExcel_B.xlsx not found
    echo Please create ToggleExcel_B.xlsx with columns: URL, userid, password
    pause
    exit /b 1
)

echo Starting automation - Setting all toggles to ON...
echo.

python _system\scripts\toggle_automation.py "ToggleExcel_B.xlsx" --state ON --no-headless

REM Move results to output folder
move toggle_results.xlsx "output\toggle_results_B_ON.xlsx" >nul 2>&1
move toggle_automation_*.log _system\logs\ >nul 2>&1

echo.
echo =========================================
echo   Automation Complete!
echo =========================================
echo Results saved in 'output' folder
echo.
pause
