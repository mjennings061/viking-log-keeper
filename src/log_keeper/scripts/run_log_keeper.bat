@echo off
echo Checking for updates...
powershell -NoProfile -ExecutionPolicy Bypass -Command "python -m pip install --user --upgrade viking-log-keeper > $null"

if %errorlevel% neq 0 (
    echo An error occurred during the package installation.
    pause
    exit /b %errorlevel%
) else (
    echo Package installation completed successfully.
)
echo .

echo Running update-logs.exe...
update-logs.exe
echo .

if %errorlevel% neq 0 (
    echo update-logs.exe failed. Starting log keeper...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "python -m log_keeper.main"
) else (
    echo update-logs.exe completed successfully.
)
pause