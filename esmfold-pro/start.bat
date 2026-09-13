@echo off
REM start.bat — Arranca ESMFold-Pro (RFdiffusion experimental).
REM Requiere GPU NVIDIA >=8 GB VRAM.

setlocal

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%"

REM Verificar Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no esta en PATH.
    pause
    exit /b 1
)

REM Verificar GPU
python -c "import torch; assert torch.cuda.is_available(), 'GPU_NO_CUDA'; print(f'GPU: {torch.cuda.get_device_name(0)}')" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ============================================================
    echo  [!] GPU NVIDIA no detectada o CUDA no disponible.
    echo  [!] RFdiffusion requiere GPU dedicada para funcionar.
    echo  [!] Usa 'esmfold' (rapido) o 'esmfold-pro' (preciso).
    echo  [!] Estos modos funcionan sin GPU en el sidecar esmfold:8100
    echo ============================================================
    echo.
    pause
    exit /b 1
)

REM Activar venv si existe
if exist "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    echo [INFO] Activando venv local...
    call "%SCRIPT_DIR%venv\Scripts\activate.bat"
)

REM Instalar deps
python -c "import fastapi, uvicorn, torch" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Instalando dependencias...
    python -m pip install --upgrade pip
    python -m pip install -r "%SCRIPT_DIR%requirements.txt"
)

REM Verificar checkpoints RFdiffusion
if not exist "%SCRIPT_DIR%models\Base_ckpt.pt" (
    echo.
    echo ============================================================
    echo  [!] Checkpoints RFdiffusion no encontrados en models\
    echo  [!] Descargalos de: http://files.ipd.uw.edu/pub/RFdiffusion/
    echo  [!] Archivos requeridos: Base_ckpt.pt, Complex_base_ckpt.pt
    echo  [!] El servicio arrancara en modo stub (dummy).
    echo ============================================================
    echo.
)

REM Verificar repo RFdiffusion
set "RFDIFFUSION_PATH=%SCRIPT_DIR%..\rfdiffusion"
if not exist "%RFDIFFUSION_PATH%\scripts\run_inference.py" (
    echo.
    echo ============================================================
    echo  [!] Repositorio RFdiffusion no encontrado en ..\rfdiffusion
    echo  [!] Clonalo: git clone https://github.com/RosettaCommons/RFdiffusion.git ..\rfdiffusion
    echo  [!] Y segui las instrucciones de instalacion del repo.
    echo  [!] El servicio usara fallback dummy si RFdiffusion no esta.
    echo ============================================================
    echo.
)

REM Config defaults
if "%ESMFOLD_PRO_PORT%"=="" set "ESMFOLD_PRO_PORT=8300"
if "%ESMFOLD_PRO_IDLE_MIN%"=="" set "ESMFOLD_PRO_IDLE_MIN=0"

echo.
echo ============================================================
echo  ESMFold-Pro (RFdiffusion Experimental)
echo  Puerto: %ESMFOLD_PRO_PORT%
echo  Modo:   rfdiffusion
echo  Health: http://localhost:%ESMFOLD_PRO_PORT%/health
echo ============================================================
echo.

python -m uvicorn app:app --host 0.0.0.0 --port %ESMFOLD_PRO_PORT% --log-level info

endlocal
