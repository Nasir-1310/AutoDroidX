# LLMDroid UI Launcher (PowerShell)
# Run: .\start_ui.ps1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  LLMDroid UI - Starting..." -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $PSScriptRoot

# Activate virtual environment if exists
$venvPath = Join-Path (Split-Path $PSScriptRoot) "venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
    Write-Host "Virtual environment activated" -ForegroundColor Green
}

# Install dependencies if needed
$fastapi = pip show fastapi 2>$null
if (-not $fastapi) {
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# Start the UI server
Write-Host ""
Write-Host "Starting UI server at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

python run_ui.py
