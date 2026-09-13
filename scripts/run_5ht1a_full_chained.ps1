# scripts/run_5ht1a_full_chained.ps1
# Orchestrator completo 5HT1A: Vina+XGB -> GNN+CL-GNN -> MolChamb -> Ablation report
# Tiempo estimado: ~2 horas wall-clock

$ErrorActionPreference = "Stop"
$Root        = "D:\moldesign-build"
$Python      = "C:\Python314\python.exe"
$ScriptsDir  = Join-Path $Root "scripts"
$LogsDir     = Join-Path $Root "logs"
$BenchScript = Join-Path $ScriptsDir "benchmark_ef_vina.py"

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

# ── Target ───────────────────────────────────────────────────────────────
$Target = @{
    id       = "7e2y"
    dataset  = "5ht1a"
    family   = "GPCR"
    historic = $true
}
$tid    = $Target.id
$ds     = $Target.dataset
$fam    = $Target.family

# ── Parámetros ───────────────────────────────────────────────────────────
$N_Mols   = 2500
$Workers  = 8
$Exhaust  = 8
$UseGNN   = $false   # GNN se corre en re-score-gnn.py (fase B2)
$NoQuantum = $true   # evitar xTB en main loop

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  5HT1A FULL CHAINED: Vina+XGB -> GNN -> MolChamb -> Report" -ForegroundColor Cyan
Write-Host "  N_Mols: $N_Mols  Workers: $Workers  Exhaust: $Exhaust" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$overallStart = Get-Date

# ── Phase B1: Vina + XGB (sin GNN, sin quantum-exit) ─────────────────────
Write-Host "=== PHASE B1: Vina + XGB (no GNN) ===" -ForegroundColor Yellow
$ts     = Get-Date -Format "yyyyMMdd_HHmmss"
$log    = Join-Path $LogsDir "full_${ds}_B1_${ts}.log"
$err    = Join-Path $LogsDir "full_${ds}_B1_${ts}.err"

$ckPrev = Join-Path $Root "data\benchmark_checkpoint_${ds}.json"
$repPrev = Join-Path $Root "data\ef_report_${ds}.json"
if (Test-Path $ckPrev)  { Remove-Item $ckPrev  -Force }
if (Test-Path $repPrev) { Remove-Item $repPrev -Force }

$argz = @(
    "-u", $BenchScript,
    "--target",  $tid,
    "--n-mols",  $N_Mols,
    "--workers", $Workers,
    "--exhaust", $Exhaust,
    "--no-quantum-exit"
)
# NO --gnn here, GNN is in Phase B2

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
    Write-Host "  Phase B1: Exit=$exit  Duration=$mins min" -ForegroundColor $(if ($exit -eq 0) {"Green"} else {"Red"})
    if ($exit -ne 0) { throw "Phase B1 failed with exit code $exit" }
}
catch {
    Write-Host "  Phase B1 EXCEPTION: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ── Phase B2: GNN + CL-GNN re-score (re-score-gnn.py) ────────────────────
Write-Host "=== PHASE B2: GNN + CL-GNN re-score ===" -ForegroundColor Yellow
$RescoreScript = Join-Path $ScriptsDir "re-score-gnn.py"
$ts2 = Get-Date -Format "yyyyMMdd_HHmmss"
$log2 = Join-Path $LogsDir "full_${ds}_B2_${ts2}.log"
$err2 = Join-Path $LogsDir "full_${ds}_B2_${ts2}.err"

$argz2 = @("-u", $RescoreScript)
$stepStart = Get-Date
try {
    $proc = Start-Process -FilePath $Python `
        -ArgumentList $argz2 `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $log2 `
        -RedirectStandardError $err2 `
        -NoNewWindow -Wait -PassThru
    $exit = $proc.ExitCode
    $dur = (Get-Date) - $stepStart
    $mins = [math]::Round($dur.TotalMinutes, 1)
    Write-Host "  Phase B2: Exit=$exit  Duration=$mins min" -ForegroundColor $(if ($exit -eq 0) {"Green"} else {"Red"})
    if ($exit -ne 0) { throw "Phase B2 failed with exit code $exit" }
}
catch {
    Write-Host "  Phase B2 EXCEPTION: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ── Phase C: MolChamb post-process (instantáneo con cache) ───────────────
Write-Host "=== PHASE C: MolChamb post-process ===" -ForegroundColor Yellow
$PostScript = Join-Path $ScriptsDir "post_process_molchamb.py"
$ts3 = Get-Date -Format "yyyyMMdd_HHmmss"
$log3 = Join-Path $LogsDir "full_${ds}_C_${ts3}.log"
$err3 = Join-Path $LogsDir "full_${ds}_C_${ts3}.err"

$argz3 = @(
    "-u", $PostScript,
    "--target", $ds,
    "--checkpoint-dir", "data/gnn_fixed",
    "--output-dir", "data/gnn_fixed",
    "--docs-dir", "docs"
)
$cStart = Get-Date
try {
    $proc = Start-Process -FilePath $Python `
        -ArgumentList $argz3 `
        -WorkingDirectory $Root `
        -RedirectStandardOutput $log3 `
        -RedirectStandardError $err3 `
        -NoNewWindow -Wait -PassThru
    $exit = $proc.ExitCode
    $dur = (Get-Date) - $cStart
    $secs = [math]::Round($dur.TotalSeconds, 1)
    Write-Host "  Phase C: Exit=$exit  Duration=$secs sec" -ForegroundColor $(if ($exit -eq 0) {"Green"} else {"Red"})
    if ($exit -ne 0) { throw "Phase C failed with exit code $exit" }
}
catch {
    Write-Host "  Phase C EXCEPTION: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# ── Phase D: Final Summary & Ablation Report ─────────────────────────────
Write-Host "=== PHASE D: Final Summary & Ablation Report ===" -ForegroundColor Yellow

# Read ablation markdown report
$mdPath = Join-Path $Root "docs\21_ABLATION_MOLCHAMB_$($ds.ToUpper()).md"
if (Test-Path $mdPath) {
    Write-Host "  Ablation report: $mdPath" -ForegroundColor Cyan
    $content = Get-Content $mdPath -Raw
    # Print first 30 lines as summary
    $lines = $content -split "`n"
    $lines[0..29] | ForEach-Object { Write-Host "  $_" }
    if ($lines.Count -gt 30) { Write-Host "  ... (truncated, see full file)" }
} else {
    Write-Host "  WARNING: Ablation markdown not found at $mdPath" -ForegroundColor Yellow
}

# Overall timing
$totalSec = [math]::Round(((Get-Date) - $overallStart).TotalSeconds, 1)
$totalMin = [math]::Round($totalSec / 60, 1)
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  CHAIN COMPLETE - Total wall time: $totalMin min ($totalSec sec)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Phases completed:" -ForegroundColor Green
Write-Host "    B1: Vina + XGB        (~1.6 h)"
Write-Host "    B2: GNN + CL-GNN      (~18 min)"
Write-Host "    C:  MolChamb post     (instant, cache hit)"
Write-Host ""
Write-Host "  Outputs:" -ForegroundColor Green
Write-Host "    data/gnn_fixed/benchmark_checkpoint_5ht1a.json (with GNN+MolChamb)"
Write-Host "    data/gnn_fixed/ef_report_5ht1a_gs.json        (6 cuts, no MolChamb)"
Write-Host "    data/gnn_fixed/ef_report_5ht1a_molchamb_gs.json (6 cuts + MolChamb)"
Write-Host "    docs/21_ABLATION_MOLCHAMB_5HT1A.md            (paper-ready table)"
Write-Host ""
Write-Host "  NEXT: Review docs/21_ABLATION_MOLCHAMB_5HT1A.md" -ForegroundColor Cyan
Write-Host "         If MolChamb adds value (delta AUC > 0.01), scale to other 4 targets." -ForegroundColor Cyan