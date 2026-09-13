# abrir_firewall_8100.ps1
# Ejecutar como Administrador: click derecho → "Ejecutar con PowerShell"
# O desde PowerShell admin:   .\abrir_firewall_8100.ps1

$ruleName = "MolDesign ESMFold TCP-8100"
$port     = 8100

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host " MolDesign — Abriendo puerto $port en el Firewall de Windows" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Eliminar regla anterior si ya existe (evita duplicados)
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "[INFO] Eliminando regla anterior..." -ForegroundColor Yellow
    Remove-NetFirewallRule -DisplayName $ruleName
}

# Crear regla de ENTRADA (el servidor Ubuntu llama a esta PC en :8100)
New-NetFirewallRule `
    -DisplayName $ruleName `
    -Direction   Inbound `
    -Action      Allow `
    -Protocol    TCP `
    -LocalPort   $port `
    -Profile     Private,Domain `
    -Description "ESMFold local service para MolDesign AI (llamado desde servidor Ubuntu)" `
    | Out-Null

Write-Host "[OK] Regla de ENTRADA creada para TCP:$port (perfiles: Private, Domain)" -ForegroundColor Green

# Verificar que quedó bien
$check = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($check -and $check.Enabled -eq "True") {
    Write-Host "[OK] Regla verificada y habilitada correctamente." -ForegroundColor Green
} else {
    Write-Host "[WARN] La regla se creó pero revisa manualmente en 'Firewall de Windows con seguridad avanzada'." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Resumen:" -ForegroundColor White
Write-Host "  Puerto:   $port/TCP" -ForegroundColor White
Write-Host "  Dirección: Inbound" -ForegroundColor White
Write-Host "  Perfiles:  Private, Domain" -ForegroundColor White
Write-Host ""
Write-Host "Para probar desde el servidor Ubuntu:"  -ForegroundColor White
Write-Host "  curl http://$($(Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like '192.168.*'}).IPAddress):$port/health" -ForegroundColor Yellow
Write-Host ""

Read-Host "Presiona Enter para cerrar"
