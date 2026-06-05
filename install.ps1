# install.ps1 — first-time local development setup for Windows.
#
# Safe to re-run: skips steps that are already complete.
#
# Run from an elevated (or normal) PowerShell terminal:
#   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
#   .\install.ps1
#
# What this does:
#   1. Checks prerequisites (Docker, Python 3.12+, Node 18+)
#   2. Creates backend\.env with secure random keys
#   3. Creates the backend Python virtualenv and installs dependencies
#   4. Starts Docker infrastructure (Postgres, Redis, Mailpit)
#   5. Creates the database schema and stamps Alembic
#   6. Installs frontend npm dependencies
#   7. Offers to launch dev.ps1

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$RootDir    = $PSScriptRoot
$BackendDir = Join-Path $RootDir 'backend'
$FrontendDir = Join-Path $RootDir 'frontend'

# ── Helpers ───────────────────────────────────────────────────────────────────
function Write-Step  { Write-Host "`n▶ $args" -ForegroundColor White }
function Write-Ok    { Write-Host "  $args" -ForegroundColor Green }
function Write-Skip  { Write-Host "  $args" -ForegroundColor Yellow }
function Write-Fail  { Write-Host "  ✗ $args" -ForegroundColor Red; exit 1 }

# ── 1. Prerequisites ──────────────────────────────────────────────────────────
Write-Step 'Checking prerequisites'

# Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Fail 'Docker not found. Install Docker Desktop from https://www.docker.com/products/docker-desktop/'
}
try { docker info 2>&1 | Out-Null } catch {
    Write-Fail 'Docker daemon is not running. Start Docker Desktop and try again.'
}
if ($LASTEXITCODE -ne 0) {
    Write-Fail 'Docker daemon is not running. Start Docker Desktop and try again.'
}
$dockerVer = (docker --version) -replace '^Docker version ([^,]+).*', '$1'
Write-Ok "✓ Docker $dockerVer"

# Python 3.12+
$PythonExe = $null
foreach ($candidate in @('python', 'python3')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        $verStr = & $candidate -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
        $parts  = $verStr.Trim().Split('.')
        if ([int]$parts[0] -ge 3 -and [int]$parts[1] -ge 12) {
            $PythonExe = $candidate
            break
        }
    }
}
if (-not $PythonExe) {
    Write-Fail 'Python 3.12+ not found. Install from https://www.python.org/downloads/'
}
$pyVer = & $PythonExe --version
Write-Ok "✓ $pyVer"

# Node 18+
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Fail 'Node.js not found. Install from https://nodejs.org/ (v18 or later)'
}
$nodeVer = (node --version).TrimStart('v')
if ([int]($nodeVer.Split('.')[0]) -lt 18) {
    Write-Fail "Node.js 18+ required (found v$nodeVer). Upgrade at https://nodejs.org/"
}
Write-Ok "✓ Node v$nodeVer"

# ── 2. backend\.env ───────────────────────────────────────────────────────────
Write-Step 'Configuring backend environment'

$EnvFile     = Join-Path $BackendDir '.env'
$EnvExample  = Join-Path $BackendDir '.env.example'

if (Test-Path $EnvFile) {
    Write-Skip '↩ backend\.env already exists — skipping'
} else {
    Copy-Item $EnvExample $EnvFile

    $appSecret = & $PythonExe -c 'import secrets; print(secrets.token_urlsafe(32))'
    $jwtSecret = & $PythonExe -c 'import secrets; print(secrets.token_urlsafe(32))'
    $encKey    = & $PythonExe -c 'import secrets; print(secrets.token_urlsafe(32))'

    $content = Get-Content $EnvFile -Raw
    $content = $content -replace 'your-secret-key-change-in-production',    $appSecret
    $content = $content -replace 'your-jwt-secret-key-change-in-production', $jwtSecret
    $content = $content -replace 'your-encryption-key-change-in-production', $encKey
    Set-Content $EnvFile $content -NoNewline

    Write-Ok '✓ backend\.env created with generated secret keys'
    Write-Host ''
    Write-Host '  +-------------------------------------------------------+' -ForegroundColor Yellow
    Write-Host '  |  Optional: add your AI API key(s) to backend\.env     |' -ForegroundColor Yellow
    Write-Host '  |                                                       |' -ForegroundColor Yellow
    Write-Host '  |  ANTHROPIC_API_KEY=sk-ant-...                         |' -ForegroundColor Yellow
    Write-Host '  |  GOOGLE_AI_API_KEY=...                                |' -ForegroundColor Yellow
    Write-Host '  |                                                       |' -ForegroundColor Yellow
    Write-Host '  |  You can also add them later via Settings > Creds.    |' -ForegroundColor Yellow
    Write-Host '  +-------------------------------------------------------+' -ForegroundColor Yellow
}

# ── 3. Backend virtualenv ─────────────────────────────────────────────────────
Write-Step 'Setting up backend Python environment'

$VenvDir    = Join-Path $BackendDir 'venv'
$VenvPython = Join-Path $VenvDir 'Scripts\python.exe'
$VenvPip    = Join-Path $VenvDir 'Scripts\pip.exe'
$VenvAlembic = Join-Path $VenvDir 'Scripts\alembic.exe'

if (Test-Path $VenvPython) {
    Write-Skip '↩ venv already exists — syncing dependencies'
} else {
    & $PythonExe -m venv $VenvDir
    Write-Ok '✓ Virtualenv created'
}

& $VenvPip install -q --disable-pip-version-check -r (Join-Path $BackendDir 'requirements.txt')
Write-Ok '✓ Backend dependencies installed'

# ── 4. Docker infrastructure ──────────────────────────────────────────────────
Write-Step 'Starting Docker infrastructure'

$composeFile = Join-Path $RootDir 'docker-compose.yml'
docker compose -f $composeFile up -d --wait postgres redis mailpit 2>&1 |
    Where-Object { $_ -notmatch 'level=warning' -and $_ -notmatch 'obsolete' } |
    ForEach-Object { Write-Host "  $_" }

Write-Ok '✓ Postgres, Redis, and Mailpit are running'

# ── 5. Database schema ────────────────────────────────────────────────────────
Write-Step 'Initialising database'

$tableCount = docker exec release-notes-db `
    psql -U user -d release_notes_db -tAc `
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public' AND table_name != 'alembic_version';"

if ($tableCount -and [int]$tableCount.Trim() -gt 0) {
    Write-Skip '↩ Database already has tables — skipping schema creation'
    Write-Skip '  (run .\reset.ps1 to wipe and start fresh)'
} else {
    Push-Location $BackendDir
    try {
        & $VenvPython -c @'
from app.models.database import Base, engine
Base.metadata.create_all(bind=engine)
print("  + Schema created")
'@
        & $VenvAlembic stamp head 2>&1 | Out-Null
        Write-Ok '✓ Database schema created and Alembic stamped'
    } finally {
        Pop-Location
    }
}

# ── 6. Frontend dependencies ──────────────────────────────────────────────────
Write-Step 'Installing frontend dependencies'

$nodeModules = Join-Path $FrontendDir 'node_modules'
if (Test-Path $nodeModules) {
    Write-Skip '↩ node_modules already exists — skipping'
} else {
    Push-Location $FrontendDir
    try {
        npm install --silent
        Write-Ok '✓ Frontend dependencies installed'
    } finally {
        Pop-Location
    }
}

# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '====================================================' -ForegroundColor Green
Write-Host '  Installation complete!'                             -ForegroundColor Green
Write-Host '====================================================' -ForegroundColor Green
Write-Host ''
Write-Host '  Frontend  -> http://localhost:4200'
Write-Host '  Backend   -> http://localhost:8000'
Write-Host '  API docs  -> http://localhost:8000/docs'
Write-Host '  Mailpit   -> http://localhost:8025'
Write-Host ''

$answer = Read-Host 'Start the development environment now? [Y/n]'
if ($answer -eq '' -or $answer -match '^[Yy]') {
    & "$RootDir\dev.ps1"
} else {
    Write-Host ''
    Write-Host 'Run .\dev.ps1 when you are ready.'
}
