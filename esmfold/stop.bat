@echo off
REM stop.bat — Apaga el servicio ESMFold local si está corriendo.
REM
REM Intenta primero el endpoint /shutdown (limpio).
REM Si no responde en 3s, mata el proceso python a lo bruto.

setlocal

if "%ESMFOLD_PORT%"=="" set "ESMFOLD_PORT=8100"

echo [INFO] Intentando shutdown limpio en puerto %ESMFOLD_PORT%...

REM El endpoint /shutdown requiere un token que se generó al arranque.
REM Para apagado realmente limpio, leerlo del log:
set "LOG_FILE=%~dp0logs"
for /f "delims=" %%T in (
    'dir /b /a-d /o-d "%LOG_FILE%\esmfold-*.log" 2^>nul'
) do (
    set "LATEST_LOG=%LOG_FILE%\%%T"
    goto :got_log
)
:got_log
if defined LATEST_LOG (
    for /f "tokens=*" %%K in ('findstr /c:"shutdown_token" "%LATEST_LOG%" 2^>nul') do (
        set "TOKENLINE=%%K"
    )
)
REM Fallback: matar por nombre de proceso
echo [WARN] Apagado limpio requiere token (ver logs). Matando proceso python...
taskkill /F /FI "WINDOWTITLE eq *ESMFold*" 2>nul
taskkill /F /IM python.exe /FI "MEMUSAGE gt 50000" 2>nul

REM Verificar puerto libre
timeout /t 1 /nobreak >nul
netstat -ano | findstr ":%ESMFOLD_PORT% " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [OK] Puerto %ESMFOLD_PORT% libre.
) else (
    echo [WARN] Puerto aun ocupado. Cierra la ventana manualmente.
)

endlocal