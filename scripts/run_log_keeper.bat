@echo off
echo Checking for updates...
powershell -NoProfile -ExecutionPolicy Bypass -Command "pip install --upgrade viking-log-keeper > $null"

if %errorlevel% neq 0 (
    echo An error occurred during the package installation.
    pause
    exit /b %errorlevel%
) else (
    echo Package installation completed successfully.
)
echo.

echo Starting log keeper...
powershell -NoProfile -ExecutionPolicy Bypass -Command "python -m log_keeper.main"
pause