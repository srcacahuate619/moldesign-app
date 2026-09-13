# scripts/tauri-dev.ps1 (v1.0)
# beforeDevCommand de Tauri v2.
# Levanta los sidecars del modo DESKTOP para `npx tauri dev`:
#   - Backend principal (uvicorn) -> http://127.0.0.1:8000
#   - Frontend Next.js dev server  -> http://localhost:3000 (foreground, Tauri espera devUrl)
#
# Uso (desde Tauri): powershell -NoProfile -ExecutionPolicy Bypass -File scripts/tauri-dev.ps1

param(
    [string]$BackendPort = "8000",
    [string]$FrontendPort = "3000"
)

$Root = Split-Path $PSScriptRoot -Parent

# Detect bundle vs dev environment (mismo orden que start-desktop.ps1)
$IsBundle = (Test-Path "$Root\python\python.exe")
$IsStaging = (Test-Path "$Root\python-embed\python.exe")
$PythonExe = if ($IsBundle) { "$Root\python\python.exe" } elseif ($IsStaging) { "$Root\python-embed\python.exe" } else { "python" }

function Write-Step { param($msg) Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "    [!]  $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Magenta
Write-Host "  MolDesign AI v1.0 (Tauri dev)" -ForegroundColor Magenta
Write-Host "=====================================================" -ForegroundColor Magenta

# ── 1. Backend: si ya responde en :$BackendPort, reusar. Si no, lanzar. ──
function Test-BackendHealth {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$BackendPort/health" -TimeoutSec 3 -UseBasicParsing -ErrorAction Stop
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

$backendAlreadyUp = Test-BackendHealth

if ($backendAlreadyUp) {
    Write-OK "Backend ya corriendo en :$BackendPort (reutilizado)"
} else {
    # Liberar el puerto si un proceso muerto lo ocupa
    $conn = Get-NetTCPConnection -LocalPort $BackendPort -ErrorAction SilentlyContinue
    if ($conn) {
        $pidToKill = $conn.OwningProcess
        Write-Warn "Puerto $BackendPort ocupado por PID $pidToKill. Terminando..."
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }

    # Variables de entorno (mismas que start-desktop.ps1)
    $env:APP_MODE = "DESKTOP"
    $env:PYTHONPATH = "$Root\backend"
    $env:VINA_EXECUTABLE_PATH = "$Root\tools\vina\vina.exe"

    Write-Step "Iniciando Backend (puerto $BackendPort)..."
    $backendJob = Start-Process $PythonExe -ArgumentList @(
        "-m", "uvicorn", "api.main:app",
        "--host", "127.0.0.1",
        "--port", $BackendPort,
        "--loop", "asyncio"
    ) -WorkingDirectory "$Root\backend" -PassThru -WindowStyle Hidden

    Write-OK "Backend PID: $($backendJob.Id)"

    # No bloqueamos esperando el health del backend: la precarga de modelos
    # tarda minutos y Tauri solo espera el devUrl del frontend. El frontend
    # tiene retry propio al llamar a la API.
    Start-Sleep -Seconds 2
}

# ── 2. Frontend Next.js dev server (foreground) ──────────────────────────
Write-Step "Iniciando Frontend Next.js (puerto $FrontendPort)..."

# Liberar el puerto del frontend si un proceso muerto lo ocupa (p.ej. un
# `next dev` huerfano de una sesion anterior colgado en ::3000).
$feConn = Get-NetTCPConnection -LocalPort $FrontendPort -State Listen -ErrorAction SilentlyContinue
if ($feConn) {
    foreach ($c in $feConn) {
        $fePid = $c.OwningProcess
        if ($fePid -and $fePid -ne $PID) {
            $proc = Get-Process -Id $fePid -ErrorAction SilentlyContinue
            if ($proc -and $proc.ProcessName -match "node|next") {
                Write-Warn "Puerto $FrontendPort ocupado por $($proc.ProcessName) (PID $fePid). Terminando..."
                Stop-Process -Id $fePid -Force -ErrorAction SilentlyContinue
            }
        }
    }
    Start-Sleep -Milliseconds 800
}

Write-OK "Working dir: $Root\frontend"

# Este proceso queda en FOREGROUND: Tauri espera a que devUrl (localhost:3000)
# responda y mantiene el comando vivo mientras dure `tauri dev`.
Push-Location "$Root\frontend"
try {
    npm run dev -- -p $FrontendPort
} finally {
    Pop-Location
}
