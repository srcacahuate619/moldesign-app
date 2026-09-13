@echo off
REM install_real.bat
REM Instala las dependencias para ESMFold real (modo "real").
REM
REM Requiere: GPU NVIDIA con CUDA (recomendado) o CPU como fallback.
REM Tiempo estimado: 10-20 minutos (depende de tu conexión y GPU).
REM
REM Uso:
REM   install_real.bat        → instala todo (GPU CUDA)
REM   install_real.bat cpu   → instala para CPU (lento, ~30min extra)

setlocal

set "MODE=%~1"
set "SCRIPT_DIR=%~dp0"

echo ============================================================
echo  ESMFold Real — Instalador de dependencias
echo ============================================================
echo.

REM Detectar Python
where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python no encontrado. Instala Python 3.10+ primero.
    pause
    exit /b 1
)

REM Versión de Python
for /f "tokens=2" %%V in ('python --version 2^>^&1') do set "PYVER=%%V"
echo [INFO] Python: %PYVER%

REM Crear venv recomendado para aislar deps
set "VENV_DIR=%SCRIPT_DIR%venv"
if not exist "%VENV_DIR%" (
    echo [INFO] Creando venv en %VENV_DIR%...
    python -m venv "%VENV_DIR%"
)
echo [INFO] Activando venv...
call "%VENV_DIR%\Scripts\activate.bat"

REM Instalar pip actualizado
echo [INFO] Actualizando pip...
python -m pip install --upgrade pip -q

REM ── PyTorch ──────────────────────────────────────────────────────────
if /i "%MODE%"=="cpu" (
    echo [INFO] Modo CPU: instalando PyTorch CPU-only...
    pip install torch torchvision torchaudio ^
        --index-url https://download.pytorch.org/whl/cpu -q
) else (
    REM Detectar CUDA
    set "CUDA_VER="
    for /f "tokens=*" %%C in ('nvidia-smi --query-gpu=driver_version ^>nul 2^>^&1 ^^^
        ^&^& echo cuda_available') do (
        if "%%C"=="cuda_available" set "CUDA_VER=cu124"
    )
    if defined CUDA_VER (
        echo [INFO] GPU NVIDIA detectada — instalando PyTorch con CUDA 12.4...
        pip install torch torchvision torchaudio ^
            --index-url https://download.pytorch.org/whl/cu124 -q
    ) else (
        echo [WARN] No se detectó GPU NVIDIA. Instalando CPU-only.
        echo    Si tienes GPU NVIDIA, instala los drivers + CUDA Toolkit.
        echo    O fuerza CPU: install_real.bat cpu
        pip install torch torchvision torchaudio ^
            --index-url https://download.pytorch.org/whl/cpu -q
    )
)

REM ── Deps de ESMFold ──────────────────────────────────────────────
echo [INFO] Instalando deps de ESMFold (transformers, rdkit, biotite)...
pip install transformers rdkit biotite biopython omegafold ^
    einops fastdtw frozendict pandas numpy scipy scikit-learn ^
    -q

REM ── FastAPI deps (por si no están) ─────────────────────────────────────
echo [INFO] Asegurando fastapi + uvicorn...
pip install fastapi "uvicorn[standard]" httpx pydantic -q

echo.
echo ============================================================
echo  Instalación completada
echo ============================================================
echo.
echo  Próximos pasos:
echo.
echo  1. Descarga el modelo ESMFold:
echo     git clone https://github.com/patrickbryant1/ESMFold.git
echo     # Sigue las instrucciones del repo para bajar el checkpoint
echo     # Guarda el .pt en: %SCRIPT_DIR%models\
echo.
echo  2. Implementa RealPredictor.predict() en predictor.py
echo     (el esqueleto ya existe — busca # TODO)
echo.
echo  3. Arranca en modo real:
echo     set ESMFOLD_MODE=real
echo     start.bat
echo.
echo  4. Valida con los tests:
echo     python tests\test_e2e.py
echo.
echo ============================================================
pause
endlocal
