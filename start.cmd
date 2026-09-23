@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 exit /b 1
)
.venv\Scripts\python.exe -c "import importlib.util,sys; sys.exit(0 if all(importlib.util.find_spec(x) for x in ('fastapi','uvicorn','sqlalchemy','httpx','dotenv')) else 1)"
if errorlevel 1 (
    .venv\Scripts\python.exe -m pip install -r backend\requirements.txt
    if errorlevel 1 exit /b 1
)
if /I "%~1"=="--rebuild" goto build
if not exist "frontend\dist\index.html" goto build
goto serve

:build
pushd frontend
if not exist "node_modules\vite" (
    call npm ci --no-audit --no-fund
    if errorlevel 1 (
        popd
        exit /b 1
    )
)
call npm run build
if errorlevel 1 (
    popd
    exit /b 1
)
popd

:serve
echo Open http://127.0.0.1:8000 - press Ctrl+C to stop.
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
