# start_dev.ps1 – Start the FastAPI backend in development mode
# Run from the pad-vending-backend root directory

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Pad Vending Machine – Dev Backend Start " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Check Python
$pythonCmd = "python"
try {
    $version = & $pythonCmd --version 2>&1
    Write-Host "✅ $version" -ForegroundColor Green
} catch {
    Write-Host "❌ Python not found. Please install Python 3.10+." -ForegroundColor Red
    exit 1
}

# Activate virtual environment if it exists
if (Test-Path ".\venv\Scripts\Activate.ps1") {
    Write-Host "🔄 Activating virtual environment …" -ForegroundColor Yellow
    .\venv\Scripts\Activate.ps1
} else {
    Write-Host "⚠️  No venv found. Creating one …" -ForegroundColor Yellow
    & $pythonCmd -m venv venv
    .\venv\Scripts\Activate.ps1
    pip install -r requirements.txt
}

# Check .env
if (-not (Test-Path ".env")) {
    Write-Host "❌ .env file not found. Copy .env.example to .env and fill in values." -ForegroundColor Red
    exit 1
}

# Start server
Write-Host ""
Write-Host "🚀 Starting FastAPI server on http://localhost:8000 …" -ForegroundColor Green
Write-Host "   Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
