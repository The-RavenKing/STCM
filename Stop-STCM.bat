@echo off
REM Stop all running STCM instances
echo Stopping STCM...
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *main.py*" >nul 2>&1
REM Also kill by port in case the window title doesn't match
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":7847" ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo STCM stopped.
pause
