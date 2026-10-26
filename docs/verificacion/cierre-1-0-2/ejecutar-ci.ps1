param(
    [Parameter(Mandatory)][string]$Registro,
    [ValidateRange(1, 8)][int]$Desde = 1
)

# Ejecutar desde frontend/ del clon limpio. No modifica las fuentes.
$env:CI = 'true'
$ciSnapshot = (git -c core.fsmonitor=false rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'No se pudo identificar el commit del clon.' }
$ciSteps = @(
    @{ id = '01'; nombre = 'npm ci'; argumentos = @('ci') },
    @{ id = '02'; nombre = 'npm audit --omit=dev --audit-level=critical'; argumentos = @('audit', '--omit=dev', '--audit-level=critical') },
    @{ id = '03'; nombre = 'npm run check:csp'; argumentos = @('run', 'check:csp') },
    @{ id = '04'; nombre = 'npm run typecheck'; argumentos = @('run', 'typecheck') },
    @{ id = '05'; nombre = 'npm run test:run'; argumentos = @('run', 'test:run') },
    @{ id = '06'; nombre = 'npm run test:e2e'; argumentos = @('run', 'test:e2e') },
    @{ id = '07'; nombre = 'npm run test:ux'; argumentos = @('run', 'test:ux') },
    @{ id = '08'; nombre = 'npm run build:desktop'; argumentos = @('run', 'build:desktop') }
)
$ciRecords = @()
foreach ($ciStep in $ciSteps | Select-Object -Skip ($Desde - 1)) {
    Write-Output ($Registro + ' ' + $ciStep.id + ': ' + $ciStep.nombre + '; commit=' + $ciSnapshot)
    $ciStart = [DateTime]::UtcNow.ToString('o')
    $ciTimer = [Diagnostics.Stopwatch]::StartNew()
    $ciLog = Join-Path $PSScriptRoot ($Registro + '-' + $ciStep.id + '.log')
    $ciArgs = $ciStep.argumentos
    & npm.cmd @ciArgs *> $ciLog
    $ciExit = $LASTEXITCODE
    $ciTimer.Stop()
    $ciRecords += [ordered]@{
        paso = $ciStep.id; comando = $ciStep.nombre; commit = $ciSnapshot
        inicio_utc = $ciStart; segundos = [Math]::Round($ciTimer.Elapsed.TotalSeconds, 2)
        salida = $ciExit; registro = [IO.Path]::GetFileName($ciLog)
    }
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot ($Registro + '-resultados.json')),
        (ConvertTo-Json -InputObject $ciRecords -Depth 5) + "`n", [Text.UTF8Encoding]::new($false))
    Get-Content -LiteralPath $ciLog -Tail 18
    Write-Output ($Registro + ' ' + $ciStep.id + ': salida=' + $ciExit + '; segundos=' + [Math]::Round($ciTimer.Elapsed.TotalSeconds, 2))
    if ($ciExit -ne 0) { exit $ciExit }
}
