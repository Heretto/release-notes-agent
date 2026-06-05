# dev.ps1 — start the local development environment on Windows.
#
# Starts Docker infrastructure (Postgres, Redis, Mailpit), syncs backend
# dependencies, and launches both the FastAPI backend and Angular frontend
# with live reload.
#
# Run from the repo root:
#   .\dev.ps1
#
# Press Ctrl+C to stop all services.

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RootDir     = $PSScriptRoot
$BackendDir  = Join-Path $RootDir 'backend'
$FrontendDir = Join-Path $RootDir 'frontend'

$VenvPython = Join-Path $BackendDir 'venv\Scripts\python.exe'
$VenvPip    = Join-Path $BackendDir 'venv\Scripts\pip.exe'

# ── Kill any leftover processes from a previous run ───────────────────────────
Get-Process -Name python -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*uvicorn*' } |
    Stop-Process -Force -ErrorAction SilentlyContinue

Get-Process -Name node -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like '*ng serve*' } |
    Stop-Process -Force -ErrorAction SilentlyContinue

# ── Infrastructure ────────────────────────────────────────────────────────────
Write-Host 'Starting infrastructure (postgres, redis, mailpit)...'
docker compose -f (Join-Path $RootDir 'docker-compose.yml') up -d --wait postgres redis mailpit 2>&1 |
    Where-Object { $_ -notmatch 'level=warning' -and $_ -notmatch 'obsolete' } |
    ForEach-Object { Write-Host "  $_" }

# ── Sanity checks ─────────────────────────────────────────────────────────────
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: backend venv not found at $BackendDir\venv — run .\install.ps1 first." -ForegroundColor Red
    exit 1
}

$EnvFile = Join-Path $BackendDir '.env'
if (-not (Test-Path $EnvFile)) {
    Write-Host "WARNING: $EnvFile not found — copying from .env.example" -ForegroundColor Yellow
    Copy-Item (Join-Path $BackendDir '.env.example') $EnvFile
}

# ── Sync backend dependencies ─────────────────────────────────────────────────
Write-Host 'Syncing backend dependencies...'
& $VenvPip install -q --disable-pip-version-check -r (Join-Path $BackendDir 'requirements.txt')

# ── Backend (uvicorn) ─────────────────────────────────────────────────────────
Write-Host 'Starting backend...'
$backendJob = Start-Job -ScriptBlock {
    param($dir, $python)
    Set-Location $dir
    & $python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
} -ArgumentList $BackendDir, $VenvPython

# ── Frontend (ng serve) ───────────────────────────────────────────────────────
if (-not (Test-Path (Join-Path $FrontendDir 'node_modules'))) {
    Write-Host 'Installing frontend dependencies...'
    Push-Location $FrontendDir
    try { npm install } finally { Pop-Location }
}

Write-Host 'Starting frontend...'
$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    $env:NG_CLI_ANALYTICS = 'false'
    npm start
} -ArgumentList $FrontendDir

# ── Summary ───────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host 'Dev environment running:' -ForegroundColor Green
Write-Host '  Frontend  -> http://localhost:4200'
Write-Host '  Backend   -> http://localhost:8000'
Write-Host '  API docs  -> http://localhost:8000/docs'
Write-Host '  Mailpit   -> http://localhost:8025'
Write-Host ''
Write-Host 'Press Ctrl+C to stop all services.'

# ── Stream output and wait ────────────────────────────────────────────────────
try {
    while ($true) {
        $backendJob, $frontendJob | Receive-Job
        Start-Sleep -Milliseconds 500

        if ($backendJob.State -eq 'Failed' -or $frontendJob.State -eq 'Failed') {
            Write-Host 'A background job has failed.' -ForegroundColor Red
            $backendJob, $frontendJob | Receive-Job
            break
        }
    }
} finally {
    Write-Host ''
    Write-Host 'Shutting down...'
    $backendJob, $frontendJob | Stop-Job -ErrorAction SilentlyContinue
    $backendJob, $frontendJob | Remove-Job -Force -ErrorAction SilentlyContinue
    docker compose -f (Join-Path $RootDir 'docker-compose.yml') stop postgres redis mailpit 2>$null
}
