# Ejecutar desde frontend/ del worktree; registra los tres checks del encargo.
$env:CI = 'true'
$snapshot = (git -c core.fsmonitor=false rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'No se pudo identificar el commit.' }
$pasos = @(
    @{ id = '01'; nombre = 'npm run test:run'; programa = 'npm.cmd'; argumentos = @('run', 'test:run') },
    @{ id = '02'; nombre = 'npx tsc --noEmit'; programa = 'npx.cmd'; argumentos = @('tsc', '--noEmit') },
    @{ id = '03'; nombre = 'npm run lint'; programa = 'npm.cmd'; argumentos = @('run', 'lint') }
)
$resultados = @()
foreach ($paso in $pasos) {
    $inicio = [DateTime]::UtcNow.ToString('o')
    $reloj = [Diagnostics.Stopwatch]::StartNew()
    $registro = Join-Path $PSScriptRoot ('worktree-final-' + $paso.id + '.log')
    $argumentos = $paso.argumentos
    Write-Output ($paso.nombre + '; commit=' + $snapshot)
    & $paso.programa @argumentos *> $registro
    $salida = $LASTEXITCODE
    $reloj.Stop()
    $resultados += [ordered]@{
        paso = $paso.id; comando = $paso.nombre; commit = $snapshot
        inicio_utc = $inicio; segundos = [Math]::Round($reloj.Elapsed.TotalSeconds, 2)
        salida = $salida; registro = [IO.Path]::GetFileName($registro)
    }
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'worktree-final-resultados.json'),
        (ConvertTo-Json -InputObject $resultados -Depth 5) + "`n", [Text.UTF8Encoding]::new($false))
    Get-Content -LiteralPath $registro -Tail 14
    Write-Output ('salida=' + $salida + '; segundos=' + [Math]::Round($reloj.Elapsed.TotalSeconds, 2))
    if ($salida -ne 0) { exit $salida }
}
