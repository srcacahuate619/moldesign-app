# ACE benchmark - correct run
Set-Location -LiteralPath "D:\moldesign-build"
$logFile = "D:\moldesign-build\data\molchamb_loto\ace_benchmark_v2.log"
Remove-Item -LiteralPath $logFile -Force -ErrorAction SilentlyContinue
$env:PYTHONUNBUFFERED = "1"
python scripts/benchmark_ef_vina.py --target 1o86 --workers 4 --exhaust 8 2>$null | Out-File -FilePath $logFile
Write-Output "End: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Out-File -Append $logFile
