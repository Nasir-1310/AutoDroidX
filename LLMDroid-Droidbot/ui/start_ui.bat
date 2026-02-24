@echo off
REM LLMDroid UI Launcher
REM Double-click this file to start the UI

echo ============================================
echo   LLMDroid UI - Starting...
echo ============================================
echo.

cd /d "%~dp0"

REM Check if virtual environment exists
if exist "..\venv\Scripts\activate.bat" (
    call ..\venv\Scripts\activate.bat
)

REM Install dependencies if needed
pip show fastapi >nul 2>&1 || pip install -r requirements.txt

REM Start the UI server
python run_ui.py

pause
