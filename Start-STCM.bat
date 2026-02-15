@echo off
REM SillyTavern Campaign Manager - Windows Startup Script

echo.
echo ========================================
echo   SillyTavern Campaign Manager
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH!
    echo.
    echo Please install Python 3.9+ from https://www.python.org
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

echo Python found: 
python --version
echo.

REM Check if in correct directory
if not exist "backend\main.py" (
    echo ERROR: Cannot find backend\main.py
    echo Please run this script from the STCM root directory.
    echo.
    pause
    exit /b 1
)

REM Check if config exists — run setup if not
if not exist "config.yaml" (
    echo First-time setup detected...
    echo.
    python setup.py
    echo.
)

echo Starting STCM...
echo.
echo Dashboard will be available at: http://localhost:7847
echo Press Ctrl+C to stop the server
echo.

REM Open the browser (will go to setup wizard on first run, dashboard otherwise)
start http://localhost:7847

REM Change to backend directory and run
cd backend
python main.py

REM If server stops, pause to show any errors
pause
