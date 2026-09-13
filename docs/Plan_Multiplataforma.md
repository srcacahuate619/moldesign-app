> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Plan de Implementación y Estrategia de Negocio Multi-Plataforma: MolDesign AI 🧬

> ⚠️ **DOCUMENTO HISTÓRICO (Junio 2026)**
> Este plan fue escrito antes de los descubrimientos de la auditoría de empaquetado
> y antes de los fixes Spearman v1.1 + features v1.2. Muchas secciones están
> desactualizadas. Ver el [roadmap.md](roadmap.md) actual para el plan vigente.
>
> **Diferencias clave:**
> - PyInstaller fue descartado (rdkit/OpenMM no son relocatables). Usar conda-pack.
> - APP_MODE, SQLite, dispatcher, storage dual ya están implementados. No son "pendientes".
> - Los fixes Spearman (v1.1) y features v1.2 (Molstar, RCSB search) no están reflejados.
> - Capacitor/Android es post-launch, no Fase 5 inmediata.

Este documento detalla la hoja de ruta técnica y comercial para transformar **MolDesign AI** en un ecosistema multi-plataforma que maximiza la escalabilidad, reduce los costos operativos y ofrece privacidad absoluta a los investigadores farmacéuticos.

> **Estado actual (Julio 2026):** MVP científico ✅ completado. Infraestructura desktop ✅ (APP_MODE, SQLite, dispatcher, storage dual). Fixes Spearman v1.1 ✅ completos. Features v1.2 ✅ (Molstar + RCSB search). Pipeline E2E validado. Próximo paso: **Cierre científico Fase 0 + Sidecars Tauri**. Ver [roadmap.md](roadmap.md).

---

## Estrategia de Negocio y Monetización

Para capitalizar el sistema, dividiremos el producto en tres canales de distribución complementarios:

### 1. Steam: Aplicación de Escritorio (Pago Único / Volumen e Indie)
*   **Modelo**: Venta directa (Pago único) en la categoría "Software" de Steam.
*   **Precios Propuestos**:
    *   **Versión Base (CPU-Only)**: **$49.99 USD** (compra única). Ideal para estudiantes, investigadores independientes y laboratorios pequeños.
    *   **Licencia Pro (Aceleración GPU/ML Completo)**: Distribuido como un **DLC de Steam (Pago único extra o versión base Pro a $99.99 USD)**. Esto mantiene la descarga inicial ligera (~400MB) y permite que solo los usuarios con tarjetas NVIDIA dedicadas descarguen las librerías pesadas de PyTorch/CUDA (~2.5GB).
*   **Beneficios**: Cero costo de servidores para el desarrollador; el cliente aporta su propio hardware.

### 2. SaaS Web: Servidores Privados Dedicados (Suscripción Mensual / Corporativo)
*   **Modelo**: Software as a Service (SaaS) enfocado en la privacidad (Single-Tenant) y potencia garantizada.
*   **Precios Propuestos**: Suscripción de **$199.99 a $499.99 USD/mes** según los núcleos de procesamiento y el uso de GPU dedicados.
*   **Funcionamiento**:
    *   La web pública actúa como demo limitada (1-2 dockings gratuitos bajo CPU compartida) y centro de conversión.
    *   Al suscribirse al plan de pago, el sistema automatiza (vía Webhooks de Stripe + API del proveedor Cloud) la creación de un **servidor privado dedicado** y una base de datos aislada con un subdominio único (ej. `nombre-cliente.moldesign.ai`).
*   **Beneficios**: Ingreso recurrente mensual (MRR) y máxima garantía de confidencialidad para patentes biotecnológicas.

### 3. Android App (Online / Movilidad)
*   **Modelo**: Descarga gratuita en Google Play Store.
*   **Funcionamiento**: Funciona como cliente del SaaS. Los dockings y simulaciones se mandan a procesar al servidor en la nube (el del plan SaaS gratuito o al servidor privado del cliente si está autenticado).

---

## Estrategia de Arquitectura Unificada (Monorepo)

El código fuente del Frontend (Next.js) y del Backend (FastAPI) se mantendrá en un único repositorio estructurado para compilar hacia múltiples destinos:

```
                          ┌───────────────────────────┐
                          │     Shared Codebase       │
                          │   (Frontend & Backend)    │
                          └─────────────┬─────────────┘
                                        │
             ┌──────────────────────────┼──────────────────────────┐
             ▼                          ▼                          ▼
   [ Destino 1: Web SaaS ]    [ Destino 2: Steam App ]   [ Destino 3: Android App ]
   • Cloud Deploy (Railway)   • Tauri Wrapper (C++/Rust) • Capacitor Wrapper
   • PostgreSQL Cloud         • SQLite Local             • Conectado a la API SaaS
   • Límite Demo de Docking   • Cómputo CPU/GPU Local    • Renderizado Nativo Webview
```

---

## Hoja de Ruta de Desarrollo (Fases para este Año)

### Fase 1: Adaptación de Base de Datos y Pipeline Local (Backend)
#### ✅ COMPLETADA (Julio 2026)
- [x] `APP_MODE = "DESKTOP" | "CLOUD"` en `backend/core/config.py`
- [x] `db_factory.py` — SQLite WAL mode (DESKTOP) / PostgreSQL (CLOUD)
- [x] `dispatcher.py` — ThreadPoolExecutor (DESKTOP) / Celery (CLOUD)
- [x] `storage.py` — Disco local (DESKTOP) / MinIO S3 (CLOUD)
- [x] `hardware.py` — Detección CPU/RAM/GPU/OpenMM

### Fase 2: Construcción del Contenedor de Escritorio (Tauri)
- [ ] Inicializar Tauri en el directorio frontend.
- [ ] Configurar Next.js para compilación estática (`output: 'export'`).
- [ ] Configurar el "Python Sidecar" en Tauri para empaquetar el intérprete de Python y las librerías de química (`rdkit`, `vina`, `openbabel`).

### Fase 3: Integración de CPU/GPU y Configuración de Steam
- [ ] Implementar script de auto-detección de CUDA/GPU en el backend de Python.
- [ ] Diseñar el panel de configuración de Hardware en la interfaz de usuario.
- [ ] Estructurar los builds de Steam para separar las librerías CUDA en un DLC gratuito opcional.
- [ ] **Integración de Motores IA Offline (ESMFold)**:
    - *Desafío de Base de Datos*: AlphaFold2/ColabFold completo requiere bases de datos de alineamiento de secuencias (MSAs) de >100 GB. Para el entorno offline de escritorio, se integrará **ESMFold** como alternativa "single-sequence" rápida (peso del modelo: ~3 GB, sin bases de datos adicionales).
    - *Pesos de ESMFold*: Empaquetar los pesos del modelo de difusión de péptidos (~1.5 GB) en el instalador Pro de escritorio.
    - *Requisitos mínimos*: Requerir obligatoriamente una GPU NVIDIA con >= 8 GB de VRAM para activar el Nivel 3 (ESMFold) de forma fluida.

### Fase 4: Automatización de Servidores Privados (Web SaaS)
- [ ] Desarrollar scripts de despliegue usando la API de tu proveedor de nube (ej. Railway API o AWS CloudFormation).
- [ ] Integrar Stripe Webhooks para aprovisionar automáticamente el servidor privado del cliente tras el pago.
- [ ] Configurar el enrutamiento de subdominios dinámicos para los clientes SaaS Pro.

### Fase 5: Compilación para Android (Capacitor)
- [ ] Agregar Capacitor al proyecto de Next.js.
- [ ] Ajustar la responsividad del diseño para pantallas móviles (enfoque tipo aplicación nativa).
- [ ] Configurar la redirección de llamadas API hacia el dominio del servidor SaaS en producción o al servidor dedicado del usuario.

### Fase 6: Lanzamiento Comercial
- [ ] Diseñar la landing page promocional con los botones de descarga de Steam, Play Store y contratación de Servidores Privados.
- [ ] Configurar la página de la tienda en Steamworks.
- [ ] Enviar el build a revisión en Steam y Google Play.

---

> **Estado de implementación (Julio 2026):** Las secciones de Etapas 4-6 (Steam, pricing,
> assets de tienda) y Fase 5 (Android) son estrategia comercial no implementada. No hay
> código de Capacitor en el repo. Los precios sugeridos ($49.99/$99.99) requieren
> validación con usuarios reales.

## Plan de Verificación

### Pruebas Locales (Escritorio)
1.  **Ejecución Offline**: Apagar el Wi-Fi de la máquina de pruebas y validar que el docking de nivel 1 y la generación de reportes PDF funcionen localmente sin llamadas externas.
2.  **Rendimiento de Cómputo**: Medir los tiempos de docking en CPU vs. GPU local.

### Pruebas de Aprovisionamiento (SaaS)
1.  **Simulación de Compra**: Ejecutar un pago de prueba en Stripe y verificar que el script levante un nuevo backend aislado y asigne el subdominio correctamente en menos de 5 minutos.

---

---

# 🛠️ PLAN DE EJECUCIÓN PASO A PASO — De SaaS a Software Distribuido

> Esta sección es el **plan de construcción real**. Cada paso tiene una tarea concreta, los archivos que se tocan y el criterio de éxito (Definition of Done). Seguir en orden estricto.

---

## ETAPA 0 — Preparación del Entorno (1-2 días)

Antes de tocar una sola línea de código, hay que tener las herramientas instaladas y el repositorio organizado para soportar múltiples destinos de compilación.

### Paso 0.1 — Auditar el estado actual del código

**Qué hacer:**
- Listar todos los lugares donde el backend llama directamente a PostgreSQL, Redis, MinIO o Celery.
- Listar todos los `fetch()` del frontend que apuntan a URLs hardcodeadas o a `NEXT_PUBLIC_API_URL`.
- Crear el archivo `docs/DESKTOP_AUDIT.md` con este inventario.

**Criterio de éxito:** Tienes una lista completa de las dependencias de infraestructura que hay que abstraer.

---

### Paso 0.2 — Instalar las herramientas de escritorio

**Qué instalar:**
```bash
# Rust (necesario para Tauri)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh

# Tauri CLI
cargo install tauri-cli

# Verificar Node y npm (ya deberías tenerlos)
node -v && npm -v
```

**Criterio de éxito:** `cargo tauri --version` responde sin errores.

---

### Paso 0.3 — Estructurar el monorepo

**Cómo debe quedar el repo:**
```
molecular-design/
├── frontend/               ← Next.js (ya existe)
│   └── src-tauri/         ← [NUEVO] Configuración Tauri (se crea en Fase 2)
├── backend/                ← FastAPI principal (ya existe)
│   ├── core/
│   │   ├── config.py          ← [MODIFICAR] agregar APP_MODE
│   │   └── db_factory.py      ← [NUEVO] selector SQLite/PostgreSQL
│   ├── services/esmfold/
│   │   └── service.py         ← [YA EXISTE] cliente con circuit breaker ✅
│   └── tasks/
│       └── dispatcher.py      ← [NUEVO] reemplaza Celery en modo DESKTOP
├── local_services/
│   └── esmfold/           ← [YA EXISTE] microservicio FastAPI Nivel 3 ✅
│       ├── app.py             ← Servidor HTTP del predictor
│       ├── predictor.py       ← Stub + RealPredictor (ESMFold)
│       ├── config.py          ← Vars de entorno del servicio
│       ├── requirements.txt   ← Deps mínimas (fastapi + uvicorn)
│       └── models/            ← Pesos del modelo (~1.5 GB, solo Pro)
├── desktop/                ← [NUEVO] Builds y recursos del instalador
│   ├── icons/
│   ├── sidecar-backend/    ← PyInstaller del backend principal
│   ├── sidecar-esmfold/ ← PyInstaller del servicio ESMFold
│   └── builds/
├── docs/
└── docker-compose.yml      ← Solo para modo CLOUD
```

> **Nota clave:** `local_services/esmfold/` ya existe y está probado (8/8 tests unitarios ✅, E2E ✅). En el build de escritorio se convierte en el **segundo sidecar** que Tauri lanza automáticamente junto al backend principal.

**Criterio de éxito:** La estructura de carpetas existe y está documentada en `README.md`.

---

## ETAPA 1 — Refactoring del Backend para Modo Dual (3-5 días)

Este es el trabajo más crítico. El objetivo es que el mismo código Python arranque de dos formas: como microservicio cloud (modo actual) o como proceso local embebido.

### Paso 1.1 — Agregar `APP_MODE` a la configuración central

**Archivo a modificar:** `backend/core/config.py`

**Qué agregar:**
```python
from enum import Enum

class AppMode(str, Enum):
    CLOUD = "CLOUD"
    DESKTOP = "DESKTOP"

class Settings(BaseSettings):
    # ... configuración existente ...
    APP_MODE: AppMode = AppMode.CLOUD

    # En modo DESKTOP, estas variables se vuelven opcionales
    DATABASE_URL: str = "sqlite:///./moldesign_local.db"  # default local
    REDIS_URL: str | None = None    # None = no se usa en DESKTOP
    MINIO_ENDPOINT: str | None = None  # None = guardar en disco local

settings = Settings()
```

**Criterio de éxito:** La app arranca con `APP_MODE=DESKTOP` sin necesitar Redis ni PostgreSQL.

---

### Paso 1.2 — Crear el `db_factory.py` (selector de base de datos)

**Archivo nuevo:** `backend/core/db_factory.py`

**Qué hace:** Devuelve el engine correcto según `APP_MODE`.

```python
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import settings, AppMode

def get_engine():
    if settings.APP_MODE == AppMode.DESKTOP:
        # SQLite asíncrono para modo local
        return create_async_engine(
            "sqlite+aiosqlite:///./moldesign_local.db",
            echo=False,
            connect_args={"check_same_thread": False}
        )
    else:
        # PostgreSQL (modo actual en producción)
        return create_async_engine(settings.DATABASE_URL, echo=False)

engine = get_engine()
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
```

**Por qué SQLite:** No requiere servidor. Un solo archivo `.db` que vive dentro de la carpeta de datos del usuario. Perfecto para uso offline.

**Criterio de éxito:** Los modelos ORM existentes crean sus tablas en SQLite sin errores (ejecutar `alembic upgrade head` con la nueva URL).

---

### Paso 1.3 — Crear el `dispatcher.py` (reemplaza Celery en modo DESKTOP)

**Archivo nuevo:** `backend/tasks/dispatcher.py`

**Problema que resuelve:** Celery requiere Redis como broker. En modo escritorio no hay Redis. La solución es un despachador basado en `asyncio` que ejecuta las tareas en un ThreadPoolExecutor local.

```python
import asyncio
from concurrent.futures import ThreadPoolExecutor
from backend.core.config import settings, AppMode

_executor = ThreadPoolExecutor(max_workers=2)

async def dispatch_docking_task(task_id: str, smiles: str, target: str):
    """
    En modo CLOUD: encola la tarea en Celery/Redis (comportamiento actual).
    En modo DESKTOP: ejecuta la tarea en un thread local y actualiza el estado.
    """
    if settings.APP_MODE == AppMode.CLOUD:
        from backend.tasks.celery_tasks import run_docking_pipeline
        run_docking_pipeline.delay(task_id, smiles, target)
    else:
        loop = asyncio.get_event_loop()
        loop.run_in_executor(
            _executor,
            _run_docking_sync,
            task_id, smiles, target
        )

def _run_docking_sync(task_id, smiles, target):
    """Pipeline síncrono para modo desktop. Sin Redis, sin Celery."""
    from backend.tasks.docking_pipeline import run_full_pipeline
    run_full_pipeline(task_id, smiles, target)
```

**Criterio de éxito:** Un docking completo se ejecuta desde la terminal con `APP_MODE=DESKTOP` sin instalar Redis.

---

### Paso 1.4 — Adaptar el almacenamiento de archivos (sin MinIO)

**Archivo a modificar:** Donde actualmente se guarden los PDBQT/SDF (probablemente `backend/core/storage.py`)

**Qué hacer:** Crear un adaptador de almacenamiento que escriba en disco local cuando `APP_MODE=DESKTOP`.

```python
from pathlib import Path
from backend.core.config import settings, AppMode

class StorageBackend:
    def save_file(self, key: str, data: bytes) -> str:
        if settings.APP_MODE == AppMode.DESKTOP:
            path = Path(settings.LOCAL_DATA_DIR) / key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            return str(path)
        else:
            # MinIO S3 (comportamiento actual en producción)
            self.minio_client.put_object(...)
            return f"s3://{key}"
```

**Criterio de éxito:** Los archivos PDBQT de poses se guardan en `~/MolDesign/data/` en modo DESKTOP.

---

### Paso 1.5 — Prueba de integración del backend en modo DESKTOP

**Qué hacer:**
```bash
# En la terminal, desde /backend
APP_MODE=DESKTOP uvicorn main:app --reload --port 8000
```
- Abrir `http://localhost:8000/docs`
- Ejecutar un docking de prueba con la molécula de referencia (aspirina o ibuprofen)
- Verificar que el resultado se guarde en SQLite y en disco local

**Criterio de éxito:** El docking completo termina, el PDF se genera y no hay ninguna llamada saliente a servicios externos.

---

### Paso 1.6 — Adaptar `service.py` de ESMFold para modo DESKTOP

> **Contexto:** `backend/services/esmfold/service.py` ya tiene circuit breaker, retry y health cache (v2 jun-2026 ✅). En modo CLOUD apunta a `ESMFOLD_API_URL=http://192.168.1.71:8100` (PC del developer). En modo DESKTOP, el sidecar corre dentro de la misma máquina del usuario, así que la URL cambia a `localhost:8100`.

**Archivo a modificar:** `backend/services/esmfold/service.py` — método `_load_config`

```python
def _load_config(self) -> None:
    try:
        settings = get_settings()
        if settings.app_mode == AppMode.DESKTOP:
            # En desktop, ESMFold corre como sidecar local
            # La URL siempre es localhost independientemente del .env
            self._api_url = f"http://localhost:{settings.esmfold_desktop_port}"
        else:
            # En cloud, usa la URL configurada en .env (PC del developer u otro servidor)
            self._api_url = settings.esmfold_api_url
    except Exception:
        self._api_url = None
```

**Variable a agregar en `backend/core/config.py`:**
```python
# Puerto en el que corre el sidecar ESMFold en modo DESKTOP
esmfold_desktop_port: int = Field(default=8100, env="ESMFOLD_DESKTOP_PORT")
```

**Por qué no hardcodear `localhost`:** Si en el futuro el usuario cambia el puerto (conflicto con otra app), lo puede sobreescribir con una variable sin recompilar.

**Criterio de éxito:** Con `APP_MODE=DESKTOP`, `ESMFoldService()._api_url` devuelve `http://localhost:8100` sin leer ningún `.env` externo.

---

## ETAPA 2 — Construcción de la App de Escritorio con Tauri (5-7 días)

Tauri es el wrapper que convierte el frontend de Next.js en un ejecutable nativo (.exe en Windows, .dmg en Mac, .AppImage en Linux). El backend de Python corre como un "sidecar" — un proceso hijo que Tauri lanza automáticamente.

### Paso 2.1 — Inicializar Tauri en el proyecto frontend

**Qué hacer:**
```bash
cd frontend
npm install --save-dev @tauri-apps/cli @tauri-apps/api
npx tauri init
```

**Configuración inicial en `frontend/src-tauri/tauri.conf.json`:**
```json
{
  "build": {
    "beforeBuildCommand": "npm run build",
    "beforeDevCommand": "npm run dev",
    "devPath": "http://localhost:3000",
    "distDir": "../out"
  },
  "tauri": {
    "windows": [{
      "title": "MolDesign AI",
      "width": 1400,
      "height": 900,
      "minWidth": 1024,
      "minHeight": 700,
      "decorations": true,
      "transparent": false
    }],
    "bundle": {
      "identifier": "ai.moldesign.app",
      "icon": [
        "icons/32x32.png",
        "icons/128x128.png",
        "icons/icon.icns",
        "icons/icon.ico"
      ]
    }
  }
}
```

**Criterio de éxito:** `npx tauri dev` abre una ventana nativa mostrando el frontend de Next.js.

---

### Paso 2.2 — Configurar Next.js para exportación estática

**Archivo a modificar:** `frontend/next.config.js`

**Qué agregar:**
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // En modo DESKTOP, exportar como HTML estático (sin servidor Node)
  ...(process.env.BUILD_TARGET === 'desktop' && {
    output: 'export',
    trailingSlash: true,
    images: { unoptimized: true }
  }),
  // En modo CLOUD, comportamiento normal de Next.js
  ...(process.env.BUILD_TARGET !== 'desktop' && {
    // config existente...
  })
}

module.exports = nextConfig
```

**Por qué:** Tauri no puede servir un servidor Node. El frontend debe compilarse a HTML/CSS/JS estático que Tauri sirve directamente desde disco.

**Criterio de éxito:** `BUILD_TARGET=desktop npm run build` genera la carpeta `/out` con HTML estático sin errores.

---

### Paso 2.3 — Configurar los Sidecars de Python

La app de escritorio necesita **dos** procesos Python corriendo en background: el backend principal (FastAPI/Vina/XGBoost) y el servicio ESMFold (Nivel 3). Tauri los lanza y los mata automáticamente al abrir/cerrar la app.

```
┌─────────────────────────────────────────┐
│          Tauri (proceso principal)       │
│                                          │
│  lanza ──► sidecar: moldesign-backend   │ :8000
│            (FastAPI + Vina + XGBoost)    │
│                                          │
│  lanza ──► sidecar: esmfold         │ :8100
│            (FastAPI + predictor stub/real│
│             modo stub: Base $49.99       │
│             modo real: Pro DLC $59.99)   │
└─────────────────────────────────────────┘
```

#### Sidecar 1 — Backend Principal

> ⚠️ **PyInstaller fue descartado.** La auditoría de empaquetado (`docs/auditoria_empaquetado_desktop.md`) demostró que las extensiones nativas de rdkit, OpenMM, Vina no son relocatables con PyInstaller. La estrategia correcta es **conda-pack** (ver sección "Stack definitivo" abajo y [roadmap.md](roadmap.md) Fase 1).

**Estrategia actual (conda-pack):**
```bash
# Empaquetar entorno backend con conda-pack
micromamba create -n moldesign-desktop -c conda-forge \
    python=3.11 rdkit numpy scipy openmm
micromamba activate moldesign-desktop
conda-pack -n moldesign-desktop -o dist/env-backend-win-x64.tar.gz
# Tauri extrae el entorno en %APPDATA%/MolDesign/envs/ al primer inicio
```

#### Sidecar 2 — Rescoring (GNN + XGBoost)

> El rescoring corre nativamente en Windows con pip (PyG nativo, sin DGL, sin conda).
> El entorno se empaqueta con conda-pack igual que el backend.

```bash
conda-pack -n moldesign-rescoring -o dist/env-rescoring-win-x64.tar.gz
```

#### Sidecar 3 — ESMFold (Nivel 3)

> ⚠️ **PyInstaller fue descartado.** Usar conda-pack.

```bash
micromamba create -n esmfold-sidecar python=3.11 fastapi uvicorn
conda-pack -n esmfold-sidecar -o dist/env-esmfold-win-x64.tar.gz
# ~150 MB (stub, sin pesos del modelo)
# Modo real requiere +3GB de pesos PyTorch (DLC Pro)
```

**Registrar los 3 sidecars en Tauri** (`frontend/src-tauri/tauri.conf.json`):
```json
{
  "tauri": {
    "bundle": {
      "externalBin": [
        "binaries/moldesign-backend",
        "binaries/moldesign-rescoring",
        "binaries/esmfold-sidecar"
      ]
    }
  }
}
```

> **Estado actual (Julio 2026):** ⚠️ `externalBin` NO está configurado en `tauri.conf.json`.
> El `lib.rs` actual lanza `start-desktop.ps1` vía PowerShell, lo cual no es distribuible.
> Ver [roadmap.md](roadmap.md) Fase 1 para el plan de migración.

**Criterio de éxito:**
- `http://localhost:8000/health` → `{"status": "ok"}` (backend)
- `http://localhost:8100/health` → `{"status": "ok", "mode": "stub"}` (ESMFold base)
- Ambos responden sin que el usuario tenga Python instalado.

---

### Paso 2.4 — Comunicación Frontend ↔ Sidecar

**Archivo a modificar:** `frontend/src/lib/api.ts`

```typescript
const BASE_URL = typeof window !== 'undefined' && (window as any).__TAURI__
  ? 'http://localhost:8000'           // Desktop: sidecar local
  : process.env.NEXT_PUBLIC_API_URL;  // Web: URL del servidor SaaS

export const apiClient = {
  post: (path: string, body: object) =>
    fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })
};
```

**Criterio de éxito:** El botón "Ejecutar Docking" en la app de escritorio envía la molécula al sidecar local y muestra el resultado sin tocar internet.

---

### Paso 2.5 — Primer build completo del .exe

```bash
cd frontend
BUILD_TARGET=desktop npm run build
npx tauri build
# El instalador se genera en:
# frontend/src-tauri/target/release/bundle/
```

**Criterio de éxito:** Se puede instalar y ejecutar el `.exe` en una máquina Windows sin tener Python, Node, Redis, ni Docker instalados.

---

## ETAPA 3 — Detección de Hardware y Panel de Configuración (2-3 días)

### Paso 3.1 — Script de auto-detección de GPU

**Archivo nuevo:** `backend/core/hardware_detect.py`

```python
import os
from typing import TypedDict

class HardwareInfo(TypedDict):
    cpu_cores: int
    cuda_available: bool
    gpu_name: str | None
    vram_gb: float | None
    recommended_mode: str

def detect_hardware() -> HardwareInfo:
    info: HardwareInfo = {
        "cpu_cores": os.cpu_count() or 1,
        "cuda_available": False,
        "gpu_name": None,
        "vram_gb": None,
        "recommended_mode": "CPU"
    }

    try:
        import torch
        if torch.cuda.is_available():
            info["cuda_available"] = True
            info["gpu_name"] = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory
            info["vram_gb"] = round(vram / (1024**3), 1)
            info["recommended_mode"] = "GPU" if (info["vram_gb"] or 0) >= 8 else "CPU"
    except ImportError:
        pass  # Versión CPU-only, sin PyTorch

    return info
```

**Endpoint a crear:** `GET /api/hardware` → retorna el JSON de hardware.

### Paso 3.2 — Panel de Configuración de Hardware en la UI

**Qué construir:** Una pantalla de "Configuración" en el frontend que muestre:
- GPU detectada (o "CPU Only")
- VRAM disponible
- Nivel de pipeline habilitado:
  - **Nivel 1** — AutoDock Vina (CPU, siempre disponible)
  - **Nivel 2** — XGBoost + GNN RTMScore (CPU/GPU, siempre disponible)
  - **Nivel 3** — ESMFold peptide docking (requiere Pro DLC)
- Estado del sidecar ESMFold: `🟢 Activo (modo stub)` / `🟢 Activo (modo real)` / `🔴 No disponible`
- Toggle para activar/desactivar GPU manualmente

**Endpoint adicional a crear:** `GET /api/esmfold/status` → llama a `ESMFoldService().check_health()` y retorna el estado del sidecar con su modo (`stub` o `real`) y el número de predicciones ejecutadas en la sesión.

**Criterio de éxito:** El usuario ve en tiempo real qué nivel de cómputo tiene disponible, el modo de ESMFold activo, y el sistema ajusta el pipeline automáticamente.

---

## ETAPA 4 — Configuración de Steam (3-4 días)

### Paso 4.1 — Crear cuenta de Steamworks y registrar la app
1. Registrarse en [partner.steamgames.com](https://partner.steamgames.com)
2. Pagar el fee de $100 USD por app
3. Crear la App de Steam: **MolDesign AI**
4. Crear el DLC: **MolDesign AI — GPU Pro Pack**

### Paso 4.2 — Configurar los builds en Steamworks

| Build | Contenido | Tamaño aprox. | Precio |
|-------|-----------|---------------|--------|
| **Base (CPU-Only)** | Tauri .exe + `moldesign-backend` + `esmfold-sidecar` (modo stub) | ~400 MB | $49.99 |
| **DLC GPU Pro** | PyTorch/CUDA + pesos ESMFold real (~1.5 GB) + pesos ESMFold (~3 GB) | ~5 GB | +$59.99 |

**Detalles del DLC:**
- Al activar el DLC, Steam descarga los pesos en `%APPDATA%/MolDesign/models/esmfold/`
- La variable `ESMFOLD_MODE` cambia de `stub` → `real` al detectar los pesos
- El sidecar se reinicia automáticamente: el backend consulta `GET /health` y detecta el cambio de modo
- El usuario **no necesita reinstalar la app** para activar el Pro — solo comprar el DLC

### Paso 4.3 — Assets de tienda requeridos
- [ ] Ícono de la app (512×512 PNG)
- [ ] Cápsula de tienda (460×215 PNG)
- [ ] Header de tienda (460×215 PNG)
- [ ] Screenshots del pipeline (mínimo 5)
- [ ] Video de demostración (docking en tiempo real)
- [ ] Descripción corta (< 300 caracteres)
- [ ] Descripción larga con HTML enriquecido

### Paso 4.4 — Pricing y configuración regional
- Precio base: **$49.99 USD**
- Precio Pro (o DLC GPU): **$59.99 USD** adicionales
- Configurar precios regionales recomendados por Valve para LatAm / EU / Asia

**Criterio de éxito:** El build pasa la revisión de Steam (3-5 días hábiles) y aparece visible en la tienda.

---

## ETAPA 5 — Verificación de Calidad Pre-Lanzamiento

### Checklist de QA para el build de escritorio

**Funcionalidad offline (Build Base):**
- [ ] Desconectar internet → ejecutar docking con aspirina → obtener PDF ✅
- [ ] Reiniciar la app → el historial de moléculas persiste en SQLite ✅
- [ ] Ejecutar 10 dockings consecutivos → sin memory leaks ni crashes ✅
- [ ] `GET /api/esmfold/status` → `{"mode": "stub", "status": "healthy"}` ✅
- [ ] Nivel 3 con modo stub → devuelve poses sintéticas, no crashea ✅
- [ ] Desconectar internet → ESMFold stub sigue funcionando ✅

**ESMFold sidecar — arranque automático:**
- [ ] Abrir la app → `http://localhost:8100/health` responde en < 3 s ✅
- [ ] Cerrar la app → proceso `esmfold-sidecar` termina limpiamente (sin quedar zombie) ✅
- [ ] Abrir la app dos veces → no hay conflicto de puerto (segunda instancia avisa) ✅

**DLC Pro (modo real):**
- [ ] Instalar DLC → pesos detectados automáticamente → sidecar cambia a `mode: real` ✅
- [ ] GPU RTX 3080 (8 GB VRAM): predicción ESMFold real < 3 minutos ✅
- [ ] Desinstalar DLC → sidecar vuelve a modo stub automáticamente ✅

**Compatibilidad de plataformas:**
- [ ] Windows 10 (64-bit) ✅
- [ ] Windows 11 (64-bit) ✅
- [ ] Mac M1/M2 (aarch64) ✅ *(requiere build separado con `cross`)*
- [ ] Ubuntu 22.04 LTS ✅

**Rendimiento:**
- [ ] CPU solo: docking de nivel 1 < 5 minutos ✅
- [ ] CPU solo: ESMFold stub < 2 segundos ✅
- [ ] GPU RTX 3080: ESMFold real (péptido 10-mer) < 3 minutos ✅

**Instalación limpia:**
- [ ] Instalar en máquina sin Python → ambos sidecars funcionan ✅
- [ ] Desinstalar → no quedan residuos, pesos del DLC borrados por Steam ✅

---

## ETAPA 6 — Roadmap Post-Lanzamiento

Una vez que el build de escritorio esté en Steam, las siguientes iteraciones son:

| Prioridad | Feature | Impacto |
|-----------|---------|---------|
| 🔴 Alta | Modo multi-target en DESKTOP (SQLite) | Desbloquea el caso de uso más pedido |
| 🔴 Alta | Actualizaciones automáticas vía Steam | Crítico para distribuir fixes sin fricción |
| 🟡 Media | Panel de Historial de Moléculas con búsqueda local | UX esencial para usuarios power |
| 🟡 Media | Exportación de resultados a Excel / CSV | Investigadores integran con sus flujos |
| 🟢 Baja | Sincronización opcional con nube (backup de historial) | Upsell natural hacia plan SaaS |
| 🟢 Baja | Build para macOS en App Store | Amplía el mercado significativamente |

---

## Decisiones de Arquitectura — Justificación Técnica

| Decisión | Alternativa descartada | Por qué se eligió esta opción |
|----------|----------------------|-------------------------------|
| **Tauri** (Rust) como wrapper | Electron | Tauri produce binarios 10× más pequeños y usa < 50 MB de RAM extra. Electron empaqueta Chromium completo (~200 MB). Para una app científica que ya consume recursos, esto es crítico. |
| **SQLite** en modo local | PostgreSQL local | SQLite no requiere instalación ni proceso de servidor. Un solo archivo portable. Perfecto para distribución. |
| **PyInstaller** para ambos sidecars | Conda-pack / Docker Desktop | PyInstaller genera ejecutables standalone sin requerir que el usuario instale Python. ⚠️ SUPERSEDED: ver 09_PACKAGING_STRATEGY.md — estrategia actual es pip + Python embed, no PyInstaller. |
| **Dos sidecars separados** (backend + esmfold) | Un solo sidecar monolítico | Separar los procesos permite: (1) distribuir ESMFold como DLC sin reempaquetar el backend, (2) actualizar los pesos del modelo independientemente, (3) que el backend arranque rápido aunque ESMFold tarde más en cargar el modelo. |
| **`ESMFOLD_IDLE_MIN=0`** en modo sidecar | Mantener auto-shutdown | El auto-shutdown es útil en modo manual (PC developer). En producción, Tauri gestiona el ciclo de vida del proceso — el idle timer interferiría matando el sidecar inesperadamente. |
| **Modo stub en Build Base** | Sin ESMFold en Base | Incluir el sidecar en modo stub en la versión de $49.99 permite que todos los usuarios experimenten el Nivel 3 con datos sintéticos. Es un driver de conversión al DLC Pro. |
| **ThreadPoolExecutor** en lugar de Celery | Celery con Redis local | Celery requiere Redis. Un ThreadPoolExecutor con asyncio es suficiente para 1-2 dockings concurrentes en un escritorio personal. |
| **ESMFold** en lugar de AlphaFold2 | ColabFold local | AlphaFold2 requiere >100 GB de bases de datos MSA. ESMFold es single-sequence y pesa ~3 GB — distribuible en el mismo DLC que ESMFold. |
