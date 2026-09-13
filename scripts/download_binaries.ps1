<#
.SYNOPSIS
  Downloads Vina + xTB binaries from their official sources.
.DESCRIPTION
  Required once after `git clone` before running `run_5targets_2500.ps1`.
  Downloads go to: tools/vina/vina.exe, tools/xtb/xtb-6.7.1/bin/xtb.exe.
#>

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$toolsDir = Join-Path $root 'tools'

# --- Vina (Apache-2.0, Scripps) ---
$vinaDir = Join-Path $toolsDir 'vina'
if (-not (Test-Path $vinaDir)) {
    New-Item -ItemType Directory -Force -Path $vinaDir | Out-Null
}
$vinaExe = Join-Path $vinaDir 'vina.exe'
if (-not (Test-Path $vinaExe)) {
    Write-Host "Downloading Vina..."
    # The URL changes; current known-good: https://github.com/ccsdysb/vina/releases
    # Keep a pinned version in source control (see LICENSE-vina.txt)
    Invoke-WebRequest -Uri 'https://github.com/ccsdysb/vina/releases/download/v1.2.5/vina_1.2.5_windows.exe' -OutFile $vinaExe
    Write-Host "Vina downloaded: $vinaExe"
} else {
    Write-Host "Vina already present: $vinaExe"
}

# --- xTB (GPL/LGPL, grimme-lab) ---
$xtbDir = Join-Path $toolsDir 'xtb\xtb-6.7.1\bin'
if (-not (Test-Path $xtbDir)) {
    New-Item -ItemType Directory -Force -Path $xtbDir | Out-Null
}
$xtbExe = Join-Path $xtbDir 'xtb.exe'
if (-not (Test-Path $xtbExe)) {
    Write-Host "Downloading xTB..."
    Invoke-WebRequest -Uri 'https://github.com/grimme-lab/xtb/releases/download/v6.7.1/xtb-6.7.1-windows.zip' -OutFile "$xtbDir\xtb.zip"
    Expand-Archive -Path "$xtbDir\xtb.zip" -DestinationPath (Join-Path $toolsDir 'xtb') -Force
    Remove-Item "$xtbDir\xtb.zip"
    Write-Host "xTB extracted: $xtbExe"
} else {
    Write-Host "xTB already present: $xtbExe"
}

Write-Host ""
Write-Host "Binaries ready. Now: scripts\run_5targets_2500.ps1"