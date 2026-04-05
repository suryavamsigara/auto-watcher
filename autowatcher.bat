@echo off
echo ===================================================
echo   Starting Auto-Watcher Environment...
echo ===================================================

:: Check if the virtual environment folder exists
IF NOT EXIST "venv" (
    echo No virtual environment found. Creating one now...
    python -m venv venv
)

:: Activate the virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Install requirements silently
echo Installing/Updating dependencies...
python -m pip install --upgrade pip -q
pip install -r requirements.txt -q

:: Ensure Playwright browsers are installed
echo Verifying Playwright browsers...
playwright install chromium

:: Run the main Python script
echo Launching Auto-Watcher...
echo.
python main.py

:: Keep the window open if the script crashes or finishes
pause