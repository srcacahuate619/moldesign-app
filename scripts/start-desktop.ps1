# scripts/start-desktop.ps1  (v1.3)
# Levanta los sidecars del modo DESKTOP:
#   - Backend principal (+ rescoring unificado) -> http://localhost:8000
#   - ESMFold (Peptide Docking -- on-demand)      -> http://localhost:8100
#   - ESMFold-Pro (RFdiffusion experimental)     -> http://localhost:8300 (opcional)
#
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
# v1.3: Rescoring ahora corre IN-PROCESS dentro del backend.
#       El sidecar separado (:8001) ya NO se inicia.
#       Ahorro: ~1.8 GB RAM (rdkit/torch no duplicados).
# â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
#
# Uso:
#   .\scripts\start-desktop.ps1
#   .\scripts\start-desktop.ps1 -WithESMFold $false    (sin peptide docking)
#   .\scripts\start-desktop.ps1 -WithESMFoldPro $true  (activar RFdiffusion)

param(
    [switch]$WithESMFold = $false,
    [switch]$WithESMFoldPro = $false,
    [string]$BackendPort = "8000",
    [string]$ESMFoldPort = "8100",
    [string]$ESMFoldProPort = "8300"
)

$Root = Split-Path $PSScriptRoot -Parent

# Detect bundle vs dev environment
$IsBundle = (Test-Path "$Root\python\python.exe")
$IsStaging = (Test-Path "$Root\python-embed\python.exe")
$PythonExe = if ($IsBundle) { "$Root\python\python.exe" } elseif ($IsStaging) { "$Root\python-embed\python.exe" } else { "python" }

# Colores
function Write-Step { param($msg) Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg) Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg) Write-Host "    [!]  $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Magenta
Write-Host "  MolDesign AI v1.0" -ForegroundColor Magenta
if ($IsBundle) { Write-Host "  (Production)" -ForegroundColor Green }
else           { Write-Host "  (Dev Mode)" -ForegroundColor Yellow }
Write-Host "=====================================================" -ForegroundColor Magenta

# Kill previous instances on our ports
function Kill-PortProcess($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
    if ($conn) {
        $pidToKill = $conn.OwningProcess
        Write-Warn "Puerto $port ocupado por PID $pidToKill. Terminando..."
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        Start-Sleep -Milliseconds 500
    }
}
Kill-PortProcess $BackendPort
Kill-PortProcess $ESMFoldPort
Kill-PortProcess $ESMFoldProPort

# Variables de entorno comunes
$env:APP_MODE = "DESKTOP"
$env:PYTHONPATH = "$Root\backend"
$env:VINA_EXECUTABLE_PATH = "$Root\tools\vina\vina.exe"
if (-not (Test-Path $env:VINA_EXECUTABLE_PATH)) {
    Write-Warn "Vina no encontrado en $env:VINA_EXECUTABLE_PATH"
}

# Sidecar 1: Backend
Write-Step "Iniciando Backend (puerto $BackendPort)..."
$backendJob = Start-Process $PythonExe -ArgumentList @(
    "-m", "uvicorn", "api.main:app",
    "--host", "127.0.0.1",
    "--port", $BackendPort,
    "--loop", "asyncio"
    ) -WorkingDirectory "$Root\backend" -PassThru -WindowStyle Hidden

Write-OK "Backend PID: $($backendJob.Id)"

# Sidecar 2: ESMFold (Nivel 3 Peptide Docking -- on-demand v1.3)
if ($WithESMFold) {
    Write-Step "Iniciando ESMFold (puerto $ESMFoldPort)..."
    if (-not (Test-Path "$Root\esmfold")) {
        Write-Warn "Directorio esmfold/ no encontrado. Peptide docking no disponible. Instala el modulo esmfold para habilitarlo."
    } else {
        $dpJob = Start-Process $PythonExe -ArgumentList @(
            "-m", "uvicorn", "app:app",
            "--host", "127.0.0.1",
            "--port", $ESMFoldPort
        ) -WorkingDirectory "$Root\esmfold" -PassThru -WindowStyle Hidden

        Write-OK "ESMFold PID: $($dpJob.Id)"
    }
} else {
    Write-Warn "ESMFold omitido (WithESMFold=false -- peptide docking desactivado)"
}

# Sidecar 4: ESMFold-Pro (RFdiffusion Experimental -- requiere GPU)
if ($WithESMFoldPro) {
    Write-Step "Iniciando ESMFold-Pro Experimental (puerto $ESMFoldProPort)..."
    if (-not (Test-Path "$Root\esmfold-pro")) {
        Write-Warn "Directorio esmfold-pro/ no encontrado. RFdiffusion no disponible. Instala el modulo esmfold-pro (requiere GPU) para habilitarlo."
    } else {
        $proJob = Start-Process $PythonExe -ArgumentList @(
            "-m", "uvicorn", "app:app",
            "--host", "127.0.0.1",
            "--port", $ESMFoldProPort
        ) -WorkingDirectory "$Root\esmfold-pro" -PassThru -WindowStyle Hidden

        Write-OK "ESMFold-Pro PID: $($proJob.Id)"
    }
} else {
    Write-Warn "ESMFold-Pro omitido (WithESMFoldPro=false -- requiere GPU NVIDIA >=8 GB)"
}

# Esperar a que arranquen
Write-Step "Esperando que los sidecars arranquen..."
Start-Sleep -Seconds 5

$services = @(
    @{ Name = "Backend (+rescoring)"; Url = "http://localhost:$BackendPort/health" }
)
if ($WithESMFold)    { $services += @{ Name = "ESMFold";    Url = "http://localhost:$ESMFoldPort/health" } }
if ($WithESMFoldPro) { $services += @{ Name = "ESMFold-Pro"; Url = "http://localhost:$ESMFoldProPort/health" } }

foreach ($svc in $services) {
    try {
        $r = Invoke-WebRequest -Uri $svc.Url -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        $preview = $r.Content.Substring(0, [Math]::Min(80, $r.Content.Length))
        Write-OK "$($svc.Name): HTTP $($r.StatusCode) - $preview"
    } catch {
        Write-Warn "$($svc.Name): Sin respuesta aun (puede que aun este cargando)"
    }
}

Write-Host ""
Write-Host "=====================================================" -ForegroundColor Magenta
Write-Host "  Sidecars corriendo. Endpoints:" -ForegroundColor White
Write-Host "  Backend (+rescoring unificado): http://localhost:$BackendPort/docs" -ForegroundColor White
if ($WithESMFold)    { Write-Host "  ESMFold:        http://localhost:$ESMFoldPort/health" -ForegroundColor White }
if ($WithESMFoldPro) { Write-Host "  ESMFold-Pro:    http://localhost:$ESMFoldProPort/health (GPU)" -ForegroundColor Yellow }
Write-Host ""
Write-Host "  RAM idle estimada: ~600 MB (backend+rescoring unificado)" -ForegroundColor Green
if (-not $WithESMFold) {
    Write-Host "  ESMFold: on-demand (activar con -WithESMFold)" -ForegroundColor DarkGray
}
Write-Host "  Para el frontend: cd frontend; npm run dev" -ForegroundColor Yellow
Write-Host "=====================================================" -ForegroundColor Magenta
Write-Host ""
