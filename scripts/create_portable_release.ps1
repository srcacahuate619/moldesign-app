# scripts/create_portable_release.ps1
# Creates a self-contained portable offline release directory for MolDesign AI

$Dest = "D:\MolDesign_AI_Portable"
$SrcExe = "D:\moldesign-build\frontend\src-tauri\target\release\moldesign.exe"
$SrcRes = "D:\moldesign-build\frontend\src-tauri\resources"

Write-Host ">>> Creating portable release directory at: $Dest"
New-Item -Path $Dest -ItemType Directory -Force | Out-Null

Write-Host ">>> Copying compiled executable..."
Copy-Item -Path $SrcExe -Destination (Join-Path $Dest "moldesign.exe") -Force

Write-Host ">>> Copying staged resources (~11 GB of code, weights, tools)..."
# Use robocopy to efficiently copy the entire staged resources folder
robocopy $SrcRes (Join-Path $Dest "resources") /E /NJH /NJS /NFL /NDL

Write-Host "`n>>> Portable Release successfully created!"
Write-Host "Path: $Dest"
Write-Host "To run, execute: $Dest\moldesign.exe"
