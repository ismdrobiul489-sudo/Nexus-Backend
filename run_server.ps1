# Nexus ASM - PowerShell Startup Script
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "     Nexus ASM - Facebook Automation Assistant    " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host ""

# Check for Python
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[ERROR] Python is not installed or not in PATH." -ForegroundColor Red
    Pause
    exit
}

# Create VENV if it doesn't exist
if (!(Test-Path "venv")) {
    Write-Host "[INFO] Creating Virtual Environment..." -ForegroundColor Yellow
    python -m venv venv
}

# Activate VENV
Write-Host "[INFO] Activating Virtual Environment..." -ForegroundColor Yellow
& ".\venv\Scripts\Activate.ps1"

# Install Dependencies
Write-Host "[INFO] Installing Dependencies..." -ForegroundColor Yellow
pip install -r requirements.txt

# Start Server
Write-Host ""
Write-Host "[SUCCESS] Server is Ready!" -ForegroundColor Green
Write-Host "[INFO] Opening Dashboard: http://localhost:8000" -ForegroundColor Cyan
Start-Process "http://localhost:8000"
Write-Host ""
Write-Host "[LOGS] Server Output:" -ForegroundColor Gray
Write-Host "---------------------------------------------------"
uvicorn main:app --reload --host 0.0.0.0 --port 8000
