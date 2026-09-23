param([switch]$Setup, [switch]$Rebuild)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create Python environment.' }
}
& ./.venv/Scripts/python.exe -c "import importlib.util, sys; sys.exit(0 if all(importlib.util.find_spec(x) for x in ('fastapi', 'uvicorn', 'sqlalchemy', 'httpx', 'dotenv')) else 1)"
if ($Setup -or $LASTEXITCODE -ne 0) {
    & ./.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
}
if ($Rebuild -or $Setup -or -not (Test-Path -LiteralPath 'frontend/dist/index.html')) {
    Push-Location frontend
    try {
        if ($Setup -or -not (Test-Path -LiteralPath 'node_modules/vite')) {
            npm ci --no-audit --no-fund
            if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
        }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
}
Write-Host 'Open http://127.0.0.1:8000 — press Ctrl+C to stop.'
& ./.venv/Scripts/python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

