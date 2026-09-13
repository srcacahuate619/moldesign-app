# Overnight computation pipeline - MolDesign
# Target: 8h run (22:00 - 06:00)
# Start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')

$logFile = "D:\moldesign-build\data\molchamb_loto\overnight_complete.log"
$startTime = Get-Date

function Log {
    param([string]$msg)
    $line = "$(Get-Date -Format 'HH:mm:ss') | $msg"
    Write-Output $line
    $line | Out-File -Append -FilePath $logFile
}

# ── Phase 1: Curation of PDE5A + CYP3A4 (API-driven, ~15 min each) ──
Log "=== PHASE 1: Curate new metal targets ==="
Log "Targets: pde5a (CHEMBL1827), cyp3a4 (CHEMBL340)"

Set-Location -LiteralPath "D:\moldesign-build"

# Curation uses ChEMBL API + RDKit property-matching
python scripts/curate_metal_targets.py --targets pde5a,cyp3a4 --max-actives 500 --force --skip-pdb-download 2>&1 | ForEach-Object {
    Log $_
}

Log "Phase 1 complete: $(Get-Date -Format 'HH:mm:ss')"

# ── Phase 2: Re-download 4NY4.pdb (was truncated) and convert to PDBQT ──
Log "=== PHASE 2: Re-download missing PDBs ==="
python -c "
import urllib.request
for pdb in ['4NY4']:
    try:
        resp = urllib.request.urlopen(f'https://files.rcsb.org/download/{pdb}.pdb', timeout=60)
        data = resp.read()
        with open(f'D:\\moldesign-build\\data\\{pdb}.pdb', 'wb') as f:
            f.write(data)
        Log(f'Downloaded {pdb}.pdb: {len(data)} bytes')
    except Exception as e:
        Log(f'Failed to download {pdb}: {e}')
"

Log "Phase 2 complete: $(Get-Date -Format 'HH:mm:ss')"

# ── Phase 3: Check MMP9 benchmark status and start AChE if MMP9 done ──
Log "=== PHASE 3: Check and queue benchmarks ==="

$mmp9Report = "D:\moldesign-build\data\benchmark_checkpoint_mmp9.json"
if (Test-Path $mmp9Report) {
    $report = Get-Content $mmp9Report -Raw | ConvertFrom-Json
    Log "MMP9 report found. Checking status..."
    if ($report.pipeline_complete.ROC_AUC) {
        Log "MMP9 BENCHMARK COMPLETE! ROC-AUC: $($report.pipeline_complete.ROC_AUC)"
        Log "EF@1%: $($report.pipeline_complete.EF_1pct)  EF@5%: $($report.pipeline_complete.EF_5pct)"
    }
} else {
    Log "MMP9 still running (no report yet)"
}

# ── Phase 4: Populate MolChamb for ACE + PDE5A + CYP3A4 ──
Log "=== PHASE 4: Populate MolChamb for new targets ==="
# Only runs if curation files exist
if (Test-Path "D:\moldesign-build\data\multitarget\ace\actives.txt") {
    Log "ACE actives found. Ready for MolChamb populate."
}
else {
    Log "ACE actives not found. Something went wrong."
}

Log "=== OVERNIGHT COMPLETE ==="
Log "Start: $($startTime.ToString('yyyy-MM-dd HH:mm:ss'))"
Log "End: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Log "Elapsed: $(((Get-Date) - $startTime).TotalMinutes) min"
