@echo off
REM stop.bat — Apaga ESMFold-Pro si esta corriendo.

setlocal

if "%ESMFOLD_PRO_PORT%"=="" set "ESMFOLD_PRO_PORT=8300"

echo [INFO] Apagando ESMFold-Pro en puerto %ESMFOLD_PRO_PORT%...

REM Matar proceso python en este puerto
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%ESMFOLD_PRO_PORT% " ^| findstr "LISTENING"') do (
    echo [INFO] Matando PID %%a...
    taskkill /F /PID %%a 2>nul
)

timeout /t 1 /nobreak >nul
netstat -ano | findstr ":%ESMFOLD_PRO_PORT% " | findstr "LISTENING" >nul 2>&1
if errorlevel 1 (
    echo [OK] Puerto %ESMFOLD_PRO_PORT% libre.
) else (
    echo [WARN] Puerto aun ocupado.
)

endlocal
