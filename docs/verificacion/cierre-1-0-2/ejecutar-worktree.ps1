$env:CI = 'true'
$qaCommit = (git -c core.fsmonitor=false rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'No se pudo identificar el commit.' }
$qaSteps = @(
    @{ nombre = 'npm run test:run'; programa = 'npm.cmd'; argumentos = @('run', 'test:run') },
    @{ nombre = 'npx tsc --noEmit'; programa = 'npx.cmd'; argumentos = @('tsc', '--noEmit') },
    @{ nombre = 'npm run lint'; programa = 'npm.cmd'; argumentos = @('run', 'lint') }
)
$qaRecords = @()
foreach ($qaStep in $qaSteps) {
    $qaIndex = '{0:00}' -f ($qaRecords.Count + 1)
    $qaLog = Join-Path $PSScriptRoot ('worktree-cierre-' + $qaIndex + '.log')
    $qaStart = [DateTime]::UtcNow.ToString('o')
    $qaTimer = [Diagnostics.Stopwatch]::StartNew()
    $qaArgs = $qaStep.argumentos
    & $qaStep.programa @qaArgs *> $qaLog
    $qaExit = $LASTEXITCODE
    $qaTimer.Stop()
    $qaRecords += [ordered]@{
        comando = $qaStep.nombre; commit = $qaCommit; inicio_utc = $qaStart
        segundos = [Math]::Round($qaTimer.Elapsed.TotalSeconds, 2)
        salida = $qaExit; registro = [IO.Path]::GetFileName($qaLog)
    }
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'worktree-cierre-resultados.json'),
        (ConvertTo-Json -InputObject $qaRecords -Depth 5) + "`n", [Text.UTF8Encoding]::new($false))
    Get-Content -LiteralPath $qaLog -Tail 14
    Write-Output ($qaStep.nombre + ': salida=' + $qaExit)
    if ($qaExit -ne 0) { exit $qaExit }
}
