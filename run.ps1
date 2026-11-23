$ErrorActionPreference = "Stop"

$python = ".\.venv\Scripts\python.exe"

function Test-CoreDependencies([string]$exe) {
    & $exe -c "import fastapi, uvicorn, PIL, numpy, multipart" 2>$null
    return $LASTEXITCODE -eq 0
}

if (-not (Test-Path $python)) {
    if (Test-CoreDependencies "python") {
        Write-Host "Using the existing Python environment (dependencies already available)." -ForegroundColor Cyan
        & python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
        exit
    }

    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv .venv
}

if (-not (Test-CoreDependencies $python)) {
    Write-Host "Installing dependencies..." -ForegroundColor Cyan
    & $python -m pip install --upgrade pip --quiet
    & $python -m pip install -r requirements.txt --quiet
}

Write-Host ""
Write-Host "Starting Fake Currency Detector at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop." -ForegroundColor DarkGray
Write-Host ""

& $python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
