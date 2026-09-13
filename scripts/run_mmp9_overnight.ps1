# Run MMP9 benchmark overnight
$logFile = "D:\moldesign-build\data\molchamb_loto\mmp9_benchmark_overnight.log"
$logFile | ForEach-Object { Remove-Item -LiteralPath $_ -Force -ErrorAction SilentlyContinue }

Set-Location -LiteralPath "D:\moldesign-build"

"=== MMP9 Benchmark Overnight ===" | Out-File -FilePath $logFile
"Target: 1gkc (MMP9), 858 actives + 2000 decoys = 2858 total" | Out-File -Append -FilePath $logFile
"Workers: 4, Exhaust: 8" | Out-File -Append -FilePath $logFile
"Start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append -FilePath $logFile
"" | Out-File -Append -FilePath $logFile

$sw = [System.Diagnostics.Stopwatch]::StartNew()
python scripts/benchmark_ef_vina.py --target 1gkc --workers 4 --exhaust 8 2>&1 | Out-File -Append -FilePath $logFile

$sw.Stop()
"" | Out-File -Append -FilePath $logFile
"=== COMPLETED ===" | Out-File -Append -FilePath $logFile
"End: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append -FilePath $logFile
"Elapsed: $($sw.Elapsed.TotalMinutes) min" | Out-File -Append -FilePath $logFile
