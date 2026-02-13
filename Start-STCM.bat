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

REM Check if config exists
if not exist "config.yaml" (
    echo WARNING: config.yaml not found!
    echo Running setup.py to create it...
    echo.
    python setup.py
    echo.
    echo Please edit config.yaml with your SillyTavern paths, then run this script again.
    echo.
    echo Opening config.yaml in Notepad...
    start notepad config.yaml
    pause
    exit /b 0
)

echo Starting STCM...
echo.
echo Dashboard will be available at: http://localhost:8000
echo Press Ctrl+C to stop the server
echo.

REM Change to backend directory and run
cd backend
python main.py

REM If server stops, pause to show any errors
pause
