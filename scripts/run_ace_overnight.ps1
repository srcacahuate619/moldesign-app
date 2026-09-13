# ACE benchmark overnight
$logFile = "D:\moldesign-build\data\molchamb_loto\ace_benchmark_overnight.log"
Set-Location -LiteralPath "D:\moldesign-build"
"Start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File $logFile
"Target: 1O86 (ACE), 82 actives + decoys" | Out-File -Append $logFile
python scripts/benchmark_ef_vina.py --target 1o86 --workers 4 --exhaust 8 2>&1 | Out-File -Append $logFile
"End: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append $logFile
