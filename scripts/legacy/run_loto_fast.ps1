$logDir = "D:\moldesign-build\data\molchamb_loto"
$script = "D:\moldesign-build\scripts\loto_exact_rescore_fast.py"
$outFile = "$logDir\loto_exact_rescore_fast.log"

Set-Location "D:\moldesign-build"
python $script *>&1 | Out-File $outFile -Encoding ascii
