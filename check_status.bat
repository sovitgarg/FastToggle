@echo off
REM Check toggle status without making changes (Windows)

cd /d "%~dp0"

echo =========================================
echo   Toggle Status Checker
echo =========================================
echo.

REM Pre-requisite checks
set SETUP_NEEDED=0

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

REM Check 2: Virtual environment exists
if not exist "_system\venv" (
    echo Virtual environment not found. Setting up...
    set SETUP_NEEDED=1
)

REM Check 3: Required packages installed (only if venv exists)
if %SETUP_NEEDED%==0 (
    if exist "_system\venv" (
        call _system\venv\Scripts\activate.bat
        python -c "import playwright, pandas, openpyxl" >nul 2>&1
        if errorlevel 1 (
            echo Required packages missing. Setting up...
            set SETUP_NEEDED=1
        )
    )
)

REM Run setup if needed
if %SETUP_NEEDED%==1 (
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

    echo Installing browser (this may take a minute)...
    playwright install chromium

    echo.
    echo Setup complete!
    echo.
)

REM Activate virtual environment
call _system\venv\Scripts\activate.bat

REM Check for Excel file
if not exist "ToggleExcel.xlsx" (
    echo ERROR: ToggleExcel.xlsx not found
    pause
    exit /b 1
)

echo Checking toggle status for all URLs...
echo.

python _system\scripts\check_status.py "ToggleExcel.xlsx" --no-headless

REM Move results to output folder
move status_report.xlsx output\ >nul 2>&1
move status_check_*.log _system\logs\ >nul 2>&1

echo.
echo =========================================
echo   Status Check Complete!
echo =========================================
echo Results saved in 'output' folder
echo.
pause
