Set-Location -LiteralPath "D:\moldesign-build"
$logFile = "D:\moldesign-build\data\molchamb_loto\curation_overnight.log"

Write-Output "=== Curating PDE5A + CYP3A4 ===" > $logFile
Write-Output "Start: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" >> $logFile
Write-Output "" >> $logFile

python scripts/curate_metal_targets.py --targets pde5a,cyp3a4 --max-actives 500 --force --skip-pdb-download 2>&1 | ForEach-Object { $line = "$(Get-Date -Format 'HH:mm:ss') | $_"; Write-Output $line; $line | Out-File -Append -FilePath $logFile }

Write-Output "" >> $logFile
Write-Output "=== COMPLETE: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ===" >> $logFile
