@echo off
REM start.bat — Arranca el servicio ESMFold local en una ventana nueva.
REM
REM Uso: doble click, o desde cmd:  start.bat
REM
REM Variables de entorno opcionales (antes de llamar):
REM   ESMFOLD_PORT       (default 8100)
REM   ESMFOLD_MODE       (default stub)  — stub | real
REM   ESMFOLD_IDLE_MIN   (default 10)    — auto-shutdown por inactividad

setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Detectar Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta en PATH. Instala Python 3.10+ y vuelve a intentar.
    pause
    exit /b 1
)

REM Activar venv si existe (./venv)
if exist "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    echo [INFO] Activando venv local...
    call "%SCRIPT_DIR%venv\Scripts\activate.bat"
)

REM Instalar deps si no están
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando dependencias (primera vez)...
    python -m pip install --upgrade pip
    python -m pip install -r "%SCRIPT_DIR%requirements.txt"
    if errorlevel 1 (
        echo [ERROR] Fallo instalando dependencias.
        pause
        exit /b 1
    )
)

REM Config defaults
if "%ESMFOLD_PORT%"=="" set "ESMFOLD_PORT=8100"
if "%ESMFOLD_MODE%"=="" set "ESMFOLD_MODE=fast"
if "%ESMFOLD_IDLE_MIN%"=="" set "ESMFOLD_IDLE_MIN=10"

echo.
echo ============================================================
echo  ESMFold Local Service
echo  Puerto: %ESMFOLD_PORT%
echo  Modo:   %ESMFOLD_MODE%
echo  Auto-shutdown: %ESMFOLD_IDLE_MIN% min sin requests
echo ============================================================
echo  Logs:    %SCRIPT_DIR%logs\
echo  Apagar:  stop.bat  (o esperar inactividad)
echo  Health:  http://localhost:%ESMFOLD_PORT%/health
echo ============================================================
echo.

REM Lanzar uvicorn. La ventana queda abierta con logs en vivo.
python -m uvicorn app:app --host 0.0.0.0 --port %ESMFOLD_PORT% --log-level info

endlocal