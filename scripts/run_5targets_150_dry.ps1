# scripts/run_5targets_150_dry.ps1
# Dry-run de validacion previa al computo full de 8 hrs.
# 150 decoys + actives disponibles (<=50) por target = ~200 mols/target.
# Tiempo estimado: ~8-12 min por target * 5 = ~50 min total.
#
# valida: PDBQT cargan, centers correctos, schema_fix ef_report con box_source,
# EF@1% ballpark (>5x para targets curated; si <2x tenemos un problema),
# feature extractor estable, no silent-fails masivos.
#
# Hardware: AMD Ryzen 5 5500, 32 GB RAM. workers=6 (deja 6 threads libres).

$ErrorActionPreference = "Stop"
$Root        = "D:\moldesign-build"
$Python      = "C:\Python314\python.exe"
$ScriptsDir  = Join-Path $Root "scripts"
$LogsDir     = Join-Path $Root "logs"
$BenchScript = Join-Path $ScriptsDir "benchmark_ef_vina.py"

if (-not (Test-Path $LogsDir)) {
    New-Item -ItemType Directory -Path $LogsDir -Force | Out-Null
}

# ?? Targets (mismo orden que run_5targets_2500.ps1) ?????????????????????
$Targets = @(
    @{ id = "7e2y";  dataset = "5ht1a";        family = "GPCR"             },
    @{ id = "3pp0";  dataset = "cdk2";         family = "Kinase"          },
    @{ id = "1hsg";  dataset = "hiv_protease"; family = "Protease"        },
    @{ id = "3ert";  dataset = "er_alpha";     family = "Nuclear Receptor" },
    @{ id = "1f0r";  dataset = "factor_xa";    family = "Soluble Enzyme"  }
)

# ?? Parametros (MUESTRA CHICA) ??????????????????????????????????????????
$N_Mols = 150
$Workers = 6
$Exhaust = 8       # paper-quality (match full run)
$UseGNN = $false   # GNN off para smoke test - lo que nos freshman el dry-run es Vina+XGB
                    # GNN+CL-GNN lo corremos en re-score-gnn.py una vez validados los checkpoints.

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DRY-RUN VALIDACION (150 mols por target)" -ForegroundColor Cyan
Write-Host "  5 targets * ~200 mols = ~50 min" -ForegroundColor Cyan
Write-Host "  Workers: $Workers  Exhaust: $Exhaust  GNN: $UseGNN" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ?? Loop principal (SECUENCIAL) ??????????????????????????????????????????
$results = @()
$overallStart = Get-Date

foreach ($t in $Targets) {
    $tid    = $t.id
    $ds     = $t.dataset
    $fam    = $t.family
    $ts     = Get-Date -Format "yyyyMMdd_HHmmss"
    $log    = Join-Path $LogsDir "dry_${ds}_${ts}.log"
    $err    = Join-Path $LogsDir "dry_${ds}_${ts}.err"

    Write-Host ""
    Write-Host "???? Target: $tid ($ds, $fam)" -ForegroundColor Yellow
    Write-Host "   Log: $log"
    Write-Host "   Start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

    # Limpiar checkpoints previos de este dataset (igual que run full)
    $ckPrev = Join-Path $Root "data\benchmark_checkpoint_${ds}.json"
    $repPrev = Join-Path $Root "data\ef_report_${ds}.json"
    if (Test-Path $ckPrev)  { Remove-Item $ckPrev  -Force }
    if (Test-Path $repPrev) { Remove-Item $repPrev -Force }

    $argz = @(
        "-u",
        $BenchScript,
        "--target",  $tid,
        "--n-mols",  $N_Mols,
        "--workers", $Workers,
        "--exhaust", $Exhaust,
        "--no-quantum-exit"   # evitar dependencia xTB en smoke test
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
        Write-Host "   Exit: $exit  Duration: $mins min" -ForegroundColor $(if ($exit -eq 0) {"Green"} else {"Red"})

        # Leer reporte para confirmar schema_fix y EF ballpark
        $repPath = Join-Path $Root "data\ef_report_${ds}.json"
        $ef = "??"; $auc = "??"; $n = "??"; $bsrc = "??"; $bcenter = "??"
        if (Test-Path $repPath) {
            $r = Get-Content $repPath -Raw | ConvertFrom-Json
            $pc = $r.pipeline_complete
            if ($pc) {
                $ef = $pc.EF_1pct
                $auc = $pc.ROC_AUC
                $n = $pc.n_total
            }
            $bsrc = $r.box_source
            $bcenter = ($r.box_center -join ", ")
        }
        Write-Host "   Result: EF@1%=$ef  ROC-AUC=$auc  N=$n" -ForegroundColor $(if ($exit -eq 0 -and $ef -ne "??") {"Green"} else {"Red"})
        Write-Host "   box_source=$bsrc  box_center=[$bcenter]" -ForegroundColor Gray
        $results += [PSCustomObject]@{
            Target  = $tid
            Dataset = $ds
            Family  = $fam
            Exit    = $exit
            Minutes = $mins
            EF1pct  = $ef
            AUC     = $auc
            N       = $n
            BoxSource = $bsrc
        }
    } catch {
        Write-Host "   EXCEPCION: $($_.Exception.Message)" -ForegroundColor Red
        $results += [PSCustomObject]@{
            Target = $tid; Dataset = $ds; Family = $fam; Exit = -1; Minutes = 0; EF1pct = "-"; AUC = "-"; N = 0; BoxSource = "-"
        }
    }
}

# ?? Summary final ???????????????????????????????????????????????????????
$overall = (Get-Date) - $overallStart
$h = [math]::Round($overall.TotalHours, 2)

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DRY-RUN COMPLETADO  -  TOTAL: $h horas" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
$results | Format-Table Target, Dataset, Family, Exit, Minutes, EF1pct, AUC, N, BoxSource -AutoSize

$summaryPath = Join-Path $LogsDir ("dry_summary_$(Get-Date -Format 'yyyyMMdd_HHmmss').json")
$results | ConvertTo-Json -Depth 3 | Out-File -FilePath $summaryPath -Encoding utf8
Write-Host "Summary: $summaryPath"

# ?? Veredicto automatico ????????????????????????????????????????????????
$allOk = ($results | Where-Object { $_.Exit -ne 0 -or $_.EF1pct -eq "???" }).Count -eq 0
$anyWeak = ($results | Where-Object { $_.EF1pct -ne "???" -and [double]($_.EF1pct) -lt 5.0 }).Count
Write-Host ""
if ($allOk -and $anyWeak -eq 0) {
    Write-Host "  VEREDICTO: OK - disparar run_5targets_2500.ps1 full." -ForegroundColor Green
} elseif ($allOk -and $anyWeak -gt 0) {
    Write-Host "  VEREDICTO: WARNING - todos completaron pero EF@1% < 5x en algunos targets." -ForegroundColor Yellow
    Write-Host "             Revisar logs antes de disparar full." -ForegroundColor Yellow
} else {
    Write-Host "  VEREDICTO: FAIL - al menos un target fallo. NO disparar full." -ForegroundColor Red
    Write-Host "             Ver logs: logs\dry_*_*.log y .err" -ForegroundColor Red
}
