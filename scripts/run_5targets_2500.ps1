# scripts/run_5targets_2500.ps1
# Orquestador de re-corrida full-scale de 5 targets × 2500 moléculas cada uno.
# Ver docs/17_EF_BENCHMARK_FIXES.md para contexto y reproducibilidad.
#
# Hardware: AMD Ryzen 5 5500 (6 cores / 12 threads) + 32 GB RAM.
# Estrategia: workers=8 para Vina (deja 4 threads libres para OS + Python overhead),
# targets en SECUENCIA (no paralelo) para no saturar CPU + RAM.
# Tiempo estimado: ~1.6 h por target × 5 = ~8 h total.
#
# Uso:
#   cd D:\moldesign-build
#   .\scripts\run_5targets_2500.ps1
#
# Monitoreo:
#   Get-Content logs\full_<target>_<timestamp>.log -Tail 20
#   Get-Process python    # ver si sigue vivo
#
# Outputs por target:
#   logs\full_<target>_<timestamp>.log     (stdout)
#   logs\full_<target>_<timestamp>.err     (stderr / RDKit warnings)
#   data\benchmark_checkpoint_<dataset>.json
#   data\ef_report_<dataset>.json

# ── Setup ────────────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"
$Root        = Split-Path -Parent $PSScriptRoot
$Python      = if ($env:PYTHON) { $env:PYTHON } elseif (Get-Command python -ErrorAction SilentlyContinue) { (Get-Command python).Source } else { 'python' }
$ScriptsDir  = Join-Path $Root "scripts"
$LogsDir     = Join-Path $Root "logs"
$BenchScript = Join-Path $ScriptsDir "benchmark_ef_vina.py"

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

# Validate required binaries
$vinaExe = Join-Path $Root "tools\vina\vina.exe"
if (-not (Test-Path $vinaExe)) {
    Write-Error "Missing Vina. Run scripts\download_binaries.ps1 first."
    exit 1
}
$xtbExe = Join-Path $Root "tools\xtb\xtb-6.7.1\bin\xtb.exe"
if (-not (Test-Path $xtbExe)) {
    Write-Error "Missing xTB. Run scripts\download_binaries.ps1 first."
    exit 1
}

# ── Targets a correr en orden (los 3 históricos primero para comparación temprana) ─
# Tuple: script_target_id, dataset_name, description
$Targets = @(
    @{ id = "7e2y";  dataset = "5ht1a";        family = "GPCR";            historic = $true  },
    @{ id = "3pp0";  dataset = "cdk2";         family = "Kinase";          historic = $true  },
    @{ id = "1hsg";  dataset = "hiv_protease"; family = "Protease";        historic = $true  },
    @{ id = "3ert";  dataset = "er_alpha";     family = "Nuclear Receptor"; historic = $false },
    @{ id = "1f0r";  dataset = "factor_xa";    family = "Soluble Enzyme";  historic = $false }
)

# ── Parámetros de ejecución ────────────────────────────────────────────
$N_Mols       = 2500   # decoys = 2500, actives = min(50, available) → N total ≈ 2550
$Workers      = 8      # Vina threads (4 threads libres para OS, suficiente headroom)
$Exhaust      = 8      # paper-quality (match histórico)
$UseGNN       = $true  # activar --gnn para GNN-v2 + CL-GNN + calibrated stacking

# ── Banner ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  RE-CORRIDA FULL-SCALE EF Benchmark" -ForegroundColor Cyan
Write-Host "  $($Targets.Count) targets × $N_Mols mols ≈ 8 horas" -ForegroundColor Cyan
Write-Host "  Workers: $Workers  Exhaust: $Exhaust  GNN: $UseGNN" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ── Loop principal (SECUENCIAL) ──────────────────────────────────────────
$results = @()
$overallStart = Get-Date

foreach ($t in $Targets) {
    $tid    = $t.id
    $ds     = $t.dataset
    $fam    = $t.family
    $ts     = Get-Date -Format "yyyyMMdd_HHmmss"
    $log    = Join-Path $LogsDir "full_${ds}_${ts}.log"
    $err    = Join-Path $LogsDir "full_${ds}_${ts}.err"

    Write-Host ""
    Write-Host "──── Target: $tid ($ds, $fam)" -ForegroundColor Yellow
    Write-Host "   Log: $log"
    Write-Host "   Start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

    # Limpiar checkpoints previos de este dataset para forzar dock fresh
    $ckPrev = Join-Path $Root "data\benchmark_checkpoint_${ds}.json"
    $repPrev = Join-Path $Root "data\ef_report_${ds}.json"
    if (Test-Path $ckPrev)  { Remove-Item $ckPrev  -Force }
    if (Test-Path $repPrev) { Remove-Item $repPrev -Force }

    # Construir args
    $argz = @(
        "-u",
        $BenchScript,
        "--target",  $tid,
        "--n-mols",  $N_Mols,
        "--workers", $Workers,
        "--exhaust", $Exhaust
    )
    if ($UseGNN) { $argz += "--gnn" }

    $stepStart = Get-Date
    try {
        $proc = Start-Process -FilePath $Python `
            -ArgumentList $argz `
            -WorkingDirectory $Root `
            -RedirectStandardOutput $log `
            -RedirectStandardError $err `
            -NoNewWindow -Wait -PassThru
        $exit = $proc.ExitCode
        $dur = (Get-Date) - $stepStart
        $mins = [math]::Round($dur.TotalMinutes, 1)
        Write-Host "   Exit code: $exit  Duration: $mins min" -ForegroundColor $(if ($exit -eq 0) {"Green"} else {"Red"})

        # Leer el reporte para confirmar EF
        $repPath = Join-Path $Root "data\ef_report_${ds}.json"
        $ef = "??"; $auc = "??"; $n = "??"
        if (Test-Path $repPath) {
            $r = Get-Content $repPath -Raw | ConvertFrom-Json
            $pc = $r.pipeline_complete
            if ($pc) {
                $ef = $pc.EF_1pct
                $auc = $pc.ROC_AUC
                $n = $pc.n_total
            }
        }
        Write-Host "   Result: EF@1%=$ef  ROC-AUC=$auc  N=$n" -ForegroundColor $(if ($exit -eq 0) {"Green"} else {"Red"})
        $results += [PSCustomObject]@{
            Target  = $tid
            Dataset = $ds
            Family  = $fam
            Exit    = $exit
            Minutes = $mins
            EF1pct  = $ef
            AUC     = $auc
            N       = $n
        }
    } catch {
        Write-Host "   EXCEPCION: $($_.Exception.Message)" -ForegroundColor Red
        $results += [PSCustomObject]@{
            Target = $tid; Dataset = $ds; Family = $fam; Exit = -1; Minutes = 0; EF1pct = "-"; AUC = "-"; N = 0
        }
    }
}

# ── Summary final ───────────────────────────────────────────────────────
$overall = (Get-Date) - $overallStart
$h = [math]::Round($overall.TotalHours, 2)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  RE-CORRIDA COMPLETADA  -  TOTAL: $h horas" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
$results | Format-Table Target, Dataset, Family, Exit, Minutes, EF1pct, AUC, N -AutoSize

# Escribir summary a disco
$summaryPath = Join-Path $LogsDir ("full_summary_$(Get-Date -Format 'yyyyMMdd_HHmmss').json")
$results | ConvertTo-Json -Depth 3 | Out-File -FilePath $summaryPath -Encoding utf8
Write-Host ""
Write-Host "Done. Reports: $Root\data\gnn_fixed\ef_report_*_gs.json"

# ── Comparación con histórico (los 3 que tienen ref) ───────────────────
Write-Host ""
Write-Host "Comparación vs histórico (metricas_experimentales.md):" -ForegroundColor Green
$ref = @{
    "5ht1a"        = @{ vina = 21.68; composite = 32.51 }
    "cdk2"         = @{ vina = 13.28; composite = 42.10 }
    "hiv_protease" = @{ vina = 9.80;  composite = 13.10 }
}
foreach ($r in $results) {
    if ($ref.ContainsKey($r.Dataset)) {
        $h_ef = $ref[$r.Dataset].composite
        Write-Host ("  {0,-15}  nosotros={1}  histórico={2}" -f $r.Dataset, $r.EF1pct, $h_ef)
    }
}
