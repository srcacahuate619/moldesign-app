# build-base.ps1 - Pack all runtime components into base-v1.0.0.zip
param(
    [string]$OutputDir = "dist",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$OutDir = Join-Path $Root $OutputDir
$ZipName = "base-v$Version.zip"
$ZipPath = Join-Path $OutDir $ZipName

Write-Host "=== MolDesign AI - Build Base Package v$Version ===" -ForegroundColor Cyan

if (-not (Test-Path $OutDir)) {
    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
    Write-Host "  Removed previous $ZipName"
}

Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$compressionLevel = [System.IO.Compression.CompressionLevel]::Optimal

function Add-DirToZip($zip, $sourceDir, $entryPrefix) {
    if (-not (Test-Path $sourceDir)) {
        Write-Host "  SKIP (missing): $sourceDir" -ForegroundColor DarkGray
        return
    }
    $files = Get-ChildItem $sourceDir -Recurse -File -ErrorAction SilentlyContinue
    $count = 0
    foreach ($f in $files) {
        $relative = $f.FullName.Substring($sourceDir.Length).TrimStart('\', '/')
        $entry = "$entryPrefix/$relative"
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, $entry, $compressionLevel) | Out-Null
        $count++
        if ($count % 5000 -eq 0) { Write-Host "    ... $count files" }
    }
    Write-Host "  $entryPrefix`: $count files" -ForegroundColor Green
}

$zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Create)

try {
    Write-Host "Packing modules..." -ForegroundColor Yellow

    Add-DirToZip $zip (Join-Path $Root "python-embed") "python"
    Add-DirToZip $zip (Join-Path $Root "backend") "backend"
    Add-DirToZip $zip (Join-Path $Root "rescoring") "rescoring"
    Add-DirToZip $zip (Join-Path $Root "tools") "tools"
    Add-DirToZip $zip (Join-Path $Root "data") "data"
    Add-DirToZip $zip (Join-Path $Root "scripts") "scripts"

    # ESMFold - code only, exclude weights
    $esmfoldSrc = Join-Path $Root "esmfold"
    if (Test-Path $esmfoldSrc) {
        $efiles = Get-ChildItem $esmfoldSrc -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -notin @('.bin', '.safetensors', '.ckpt', '.pt', '.gguf') -and $_.Name -notlike '*pytorch_model*' }
        $ecount = 0
        foreach ($f in $efiles) {
            $rel = $f.FullName.Substring($esmfoldSrc.Length).TrimStart('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, "esmfold/$rel", $compressionLevel) | Out-Null
            $ecount++
        }
        Write-Host "  esmfold`: $ecount files (code only)" -ForegroundColor Green
    }

    # ESMFold-Pro - code only
    $eproSrc = Join-Path $Root "esmfold-pro"
    if (Test-Path $eproSrc) {
        $epfiles = Get-ChildItem $eproSrc -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Extension -notin @('.bin', '.safetensors', '.ckpt', '.pt', '.gguf') }
        $epcount = 0
        foreach ($f in $epfiles) {
            $rel = $f.FullName.Substring($eproSrc.Length).TrimStart('\', '/')
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $f.FullName, "esmfold-pro/$rel", $compressionLevel) | Out-Null
            $epcount++
        }
        Write-Host "  esmfold-pro`: $epcount files (code only)" -ForegroundColor Green
    }

    # curated_targets.csv at root
    $csv = Join-Path $Root "curated_targets.csv"
    if (Test-Path $csv) {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $csv, "curated_targets.csv", $compressionLevel) | Out-Null
        Write-Host "  curated_targets.csv: included" -ForegroundColor Green
    }

    $csvj = Join-Path $Root "curated_targets.json"
    if (Test-Path $csvj) {
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $csvj, "curated_targets.json", $compressionLevel) | Out-Null
        Write-Host "  curated_targets.json: included" -ForegroundColor Green
    }
}
finally {
    $zip.Dispose()
}

$sizeMB = [math]::Round((Get-Item $ZipPath).Length / 1MB, 0)
Write-Host ""
Write-Host "=== Done ===" -ForegroundColor Cyan
Write-Host "  Package: $ZipPath"
Write-Host "  Size: ${sizeMB} MB"
Write-Host ""
Write-Host "  Upload to HF:"
Write-Host "  huggingface-cli upload srcacahuate/moldesign-models $ZipPath v1.0.0/$ZipName"
Write-Host ""
Write-Host "  Then get SHA-256:"
Write-Host "  Get-FileHash $ZipPath -Algorithm SHA256"
