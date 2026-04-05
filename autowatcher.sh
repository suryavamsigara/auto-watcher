#!/bin/bash

echo "==================================================="
echo "  Starting Auto-Watcher Environment..."
echo "==================================================="

# Check if the virtual environment folder exists
if [ ! -d "venv" ]; then
    echo "No virtual environment found. Creating one now..."
    python3 -m venv venv
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements silently
echo "Installing/Updating dependencies..."
python3 -m pip install --upgrade pip -q
pip install -r requirements.txt -q

# Ensure Playwright browsers are installed
echo "Verifying Playwright browsers..."
playwright install chromium

# Run the main Python script
echo "Launching Auto-Watcher..."
echo ""
python3 main.py