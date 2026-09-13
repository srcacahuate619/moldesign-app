> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# 🔬 Auditoría de Producción — Estrategia de Empaquetado Desktop
## MolDesign AI — Junio 2026

---

## 1. Lo que corre en producción HOY

### Tres entornos Python distintos (dato crítico)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Servidor Ubuntu 192.168.1.64                   │
│                                                                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │  moldesign_api   │  │  worker (Celery) │  │ moldesign_       │  │
│  │  :8010 → :8000   │  │  sin puerto      │  │ rescoring :8001  │  │
│  │  Python 3.11     │  │  Python 3.11     │  │  Python 3.10     │  │
│  │  micromamba      │  │  mismo Dockerfile│  │  PyTorch 2.0.1   │  │
│  │  rdkit (conda)   │  │  Celery worker   │  │  PyG (torch-     │  │
│  │  OpenMM, Amber   │  │  pool=solo       │  │   geometric)     │  │
│  │  Vina 1.2.5 bin  │  │  concurrency=1   │  │  RTMScore GNN    │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                     │
│  ┌──────────┐  ┌─────────┐  ┌──────────┐  ┌──────────┐            │
│  │ postgres │  │  redis  │  │  minio   │  │ grafana  │            │
│  │  :5432   │  │  :6379  │  │  :9005   │  │  :3002   │            │
│  └──────────┘  └─────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────────────────┘

PC local del developer (192.168.1.71):
  ┌──────────────────────────────────┐
  │  ESMFold :8100  ← ACTIVO ✅  │
  │  Python (cualquier versión)      │
  │  FastAPI + stub predictor        │
  │  POST /predict → best_conf=0.956 │
  └──────────────────────────────────┘
```

### Inventario completo de contenedores activos

| Contenedor | Puerto | Stack | Rol |
|-----------|--------|-------|-----|
| `moldesign_api` | :8010 | Python 3.11, micromamba, FastAPI | API principal |
| `molecular-design-worker-1` | — | Python 3.11, Celery pool=solo | Ejecuta docking/pipeline |
| `moldesign_rescoring` | :8001 | Python 3.10, PyTorch+PyG | ML rescoring (GNN/XGBoost) |
| `postgres_db` | :5432 | PostgreSQL | Persistencia |
| `redis_cache` | :6379 | Redis | Broker Celery |
| `minio_storage` | :9005 | MinIO | Storage S3 |
| `moldesign_frontend` | :3001 | Next.js / Node | Frontend |
| `moldesign_grafana` | :3002 | Grafana | Monitoreo |
| `moldesign_ngrok` | — | Cloudflare tunnel | Exposición pública |

---

## 2. El Hallazgo Crítico: Son 3 entornos Python, no 1

La auditoría confirmó algo que cambia toda la estrategia de empaquetado:

| Entorno | Python | Dependencias únicas | Peso estimado |
|---------|--------|---------------------|---------------|
| `api + worker` | **3.11** conda-forge | rdkit, OpenMM, AmberTools, Vina, meeko, prolif | ~2.5 GB |
| `rescoring` | **3.12** pip | PyTorch, PyG (torch-geometric), xgboost, ProLIF, RTMScore | ~800 MB |
| `esmfold` | libre | fastapi, uvicorn, stub/torch | ~100 MB stub / ~3 GB real |

**Por qué importa para el empaquetado:** No puedes mezclarlos. El rescoring en Windows usa pip + PyG (nativo) en vez del entorno conda del servidor. DGL fue portado a PyTorch Geometric para eliminar la dependencia de DGL (sin wheel para Windows). ProLIF reemplaza ODDT para interaction fingerprints. Son entornos aislados por razon de diseño.

### Modelos ML en disco (sorprendentemente ligeros)

| Modelo | Archivo | Peso |
|--------|---------|------|
| RTMScore GNN | `rtmscore_model1.pth` | 10.3 MB |
| RTMScore GNN | `rtmscore_model2.pth` | 10.3 MB |
| RTMScore GNN | `rtmscore_model3.pth` | 10.3 MB |
| **Total** | — | **~31 MB** |

Los modelos XGBoost y SHAP se regeneran en runtime desde PDBbind (los `.pkl` no están en repo).

### 35 endpoints API documentados

La API tiene cobertura completa: auth, evaluación molecular, targets, historial, química, blockchain, estadísticas, sugerencias de novo, y el catálogo Moldex. **No falta funcionalidad por implementar — el MVP está completo.**

### Archivos Python del backend

- **~84 archivos .py** en `backend/` (api, services, scoring, utils, db, core)
- **~20 archivos .py** en `rescoring/`
- **Total codebase Python:** ~104 archivos, tamaño ligero (< 5 MB total)

---

## 3. Por Qué PyInstaller No Sirve Aquí

```
rdkit          → instalado desde conda-forge (no pip). Sus .so dependen de libGL,
                 libboost y otras libs del sistema. PyInstaller no puede resolverlas.

OpenMM/Amber   → Binarios CUDA/OpenCL compilados para el OS. No son relocatables.

Vina 1.2.5     → Binario Linux x86_64. En Windows necesitas el .exe oficial (existe).

ProLIF 2.1      → Interaction fingerprints en Python puro (reemplaza ODDT). Multi-plataforma sin compilacion.

PyG (torch-geometric) → pip installable en Windows. No requiere conda. GPU CUDA nativa con `torch.cuda.is_available()`.
```

**Veredicto:** PyInstaller puede empaquetar el 70% del código Python, pero las extensiones nativas de las librerías científicas rompen en la primera ejecución en una máquina limpia.

---

## 4. La Estrategia Correcta: Conda-pack por Entorno + Tauri

### Arquitectura de la app de escritorio

```
MolDesignApp.exe (Tauri)
│
├── Lanza: sidecar-backend       → localhost:8000
│   └── Entorno conda 3.11:
│       rdkit, OpenMM (fase 2), Vina.exe, meeko, prolif
│       Código: backend/ (~84 .py, ~4 MB)
│
├── Lanza: sidecar-rescoring     → localhost:8001
│   └── Python 3.12 pip:
│       PyTorch, PyG (torch-geometric), xgboost, ProLIF, RTMScore models (~31 MB)
│       Código: rescoring/ (~25 .py, ~3 MB)
│
└── Lanza: sidecar-esmfold   → localhost:8100
    └── Entorno mínimo:
        fastapi, uvicorn
        Modo: stub (base) o real con pesos (Pro DLC)
        Código: local_services/esmfold/ (~10 .py, ~1 MB)
```

### Dos velocidades de actualización

```
ACTUALIZACIÓN LENTA (Tier 1) — cada 1-3 meses
─────────────────────────────────────────────
Cuando cambia: requirements.txt, environment.yml,
               versiones de librerías, nuevo motor

Proceso:
  1. Generar nuevo conda-pack de cada entorno
  2. Build nuevo Tauri .msi / .AppImage
  3. Push a Steam / GitHub Releases
  4. Usuario descarga instalador completo

Tamaño: ~4-6 GB (instalador gordo)
Tiempo de build: ~30-60 min en CI
Tiempo para el usuario: depende del internet


ACTUALIZACIÓN RÁPIDA (Tier 2) — diaria si hace falta
──────────────────────────────────────────────────────
Cuando cambia: archivos .py del backend/rescoring/esmfold,
               modelos .pth, configuración

Proceso:
  1. git push
  2. CI empaqueta SOLO los .py nuevos en un .zip (~5-15 MB)
  3. Tauri Updater descarga el .zip
  4. Extrae sobre %AppData%\MolDesign\code\
  5. Reinicia los 3 sidecars (proceso interno Tauri)
  6. Usuario ve popup "Actualizado a v1.2.3"

Tamaño del delta: 5-15 MB
Tiempo de build: ~2 minutos en CI
Tiempo para el usuario: 30-60 segundos
```

---

## 5. Plan Concreto: Las Primeras 3 Semanas

### Semana 1 — Validar el backend en modo DESKTOP en Windows

El objetivo de esta semana es saber exactamente qué código hay que cambiar antes de empaquetar. No tocar Tauri todavía.

**Día 1-2: Crear el entorno conda Windows para el backend**

```powershell
# PowerShell (instalar micromamba si no está)
winget install -e --id=prefix-dev.pixi

# Crear entorno mínimo (sin OpenMM/Amber por ahora — son Nivel 4)
micromamba create -n moldesign-desktop -c conda-forge `
    python=3.11 rdkit>=2024.03 numpy scipy

micromamba activate moldesign-desktop

# Pip deps mínimas del backend
pip install fastapi uvicorn[standard] pydantic pydantic-settings `
    sqlalchemy aiosqlite httpx reportlab xgboost scikit-learn `
    python-dotenv structlog meeko openbabel-wheel prolif

# Vina para Windows
New-Item -ItemType Directory -Force "d:\molecular-design\tools\vina-win"
Invoke-WebRequest `
  -Uri "https://github.com/ccsb-scripps/AutoDock-Vina/releases/download/v1.2.5/vina_1.2.5_win_x64.exe" `
  -OutFile "d:\molecular-design\tools\vina-win\vina.exe"
```

**Día 3: Arrancar el backend en modo DESKTOP y diagnosticar**

```powershell
micromamba activate moldesign-desktop
$env:APP_MODE = "DESKTOP"
$env:VINA_EXECUTABLE_PATH = "d:\molecular-design\tools\vina-win\vina.exe"
$env:PYTHONPATH = "d:\molecular-design\backend"

cd d:\molecular-design\backend
uvicorn api.main:app --port 8000 --reload
```

Este comando va a fallar con errores de importación. **Eso es exactamente lo que queremos ver.** Cada error es una dependencia cloud que hay que abstraer.

**Día 4-5: Resolver los errores uno a uno**

Errores esperados y sus soluciones:

| Error esperado | Causa | Solución |
|---------------|-------|----------|
| `asyncpg: cannot connect` | PostgreSQL no disponible | `db_factory.py` → SQLite en DESKTOP |
| `redis.ConnectionError` | Redis no disponible | `dispatcher.py` → ThreadPoolExecutor |
| `minio.S3Error` | MinIO no disponible | `storage.py` → disco local |
| `celery_app: broker error` | Redis no disponible | Skip Celery en DESKTOP |
| `ImportError: oddt` | oddt no esta en este entorno | Normal — ya no usamos ODDT (reemplazado por ProLIF 2.1) |

**Criterio de éxito:** `GET http://localhost:8000/health` responde `{"status": "ok"}` con `APP_MODE=DESKTOP`.

---

### Semana 2 — Empaquetar los 3 entornos con conda-pack

**Backend (Python 3.11):**

```bash
# En Windows (PowerShell con micromamba activado)
micromamba activate moldesign-desktop
pip install conda-pack
conda-pack -n moldesign-desktop -o dist/env-backend-win-x64.tar.gz
# → ~1.5 GB comprimido
```

**Rescoring (Python 3.10):**

```bash
# En Linux (el servidor Ubuntu, donde el entorno ya existe)
ssh <USER>@<SERVER_IP>
conda-pack -n base -o /tmp/env-rescoring-linux-x64.tar.gz
# Copiar a tu PC:
scp <USER>@<SERVER_IP>:/tmp/env-rescoring-linux-x64.tar.gz dist/
```

> **Nota sobre rescoring en Windows — Julio 2026:** El rescoring ahora corre nativamente en Windows con pip:
> - PyG (torch-geometric) reemplaza DGL — `pip install torch-geometric` funciona en Windows
> - ProLIF 2.1 reemplaza ODDT — Python puro, sin compilacion C
> - GPU CUDA nativa con PyTorch Geometric (`torch.cuda.is_available()`)
> - El sidecar se inicia con `python -m uvicorn app:app` desde un venv pip

**ESMFold:**

```bash
cd d:\molecular-design\local_services\esmfold
micromamba create -n esmfold-sidecar fastapi uvicorn
conda-pack -n esmfold-sidecar -o dist/env-esmfold-win-x64.tar.gz
# → ~150 MB
```

---

### Semana 3 — Primer build de Tauri con los 3 sidecars

**Configurar el lanzador de sidecars en Tauri:**

```rust
// frontend/src-tauri/src/main.rs
use std::path::PathBuf;
use tauri::Manager;

struct SidecarHandles {
    backend: Option<tauri::async_runtime::JoinHandle<()>>,
    rescoring: Option<tauri::async_runtime::JoinHandle<()>>,
    esmfold: Option<tauri::async_runtime::JoinHandle<()>>,
}

fn launch_sidecar(env_path: PathBuf, script: &str, port: u16) {
    let python = env_path.join("python.exe"); // Windows
    std::process::Command::new(python)
        .args(["-m", "uvicorn", script,
               "--host", "127.0.0.1",
               "--port", &port.to_string()])
        .env("APP_MODE", "DESKTOP")
        .spawn()
        .expect(&format!("No se pudo iniciar sidecar en :{}", port));
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let res = app.path_resolver().resource_dir().unwrap();

            // Backend: FastAPI principal
            launch_sidecar(res.join("envs/backend"), "api.main:app", 8000);

            // Rescoring: GNN + XGBoost
            launch_sidecar(res.join("envs/rescoring"), "app:app", 8001);

            // ESMFold: Nivel 3 péptidos
            launch_sidecar(res.join("envs/esmfold"), "app:app", 8100);

            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("Error al ejecutar MolDesign AI");
}
```

**Configurar auto-updates (Tauri Updater):**

```json
// frontend/src-tauri/tauri.conf.json
{
  "tauri": {
    "updater": {
      "active": true,
      "endpoints": [
        "https://github.com/TU_ORG/moldesign-releases/releases/latest/download/update-{{target}}-{{arch}}.json"
      ],
      "dialog": true,
      "pubkey": "GENERA_CON: tauri signer generate -w ~/.tauri/moldesign.key"
    }
  }
}
```

**Servidor de releases (GitHub Actions, gratis):**

```yaml
# .github/workflows/desktop-release.yml
name: Desktop Release
on:
  push:
    tags: ['v*']

jobs:
  build-code-patch:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Package Python code (sin entornos)
        run: |
          zip -r code-patch.zip \
            backend/ rescoring/ local_services/esmfold/ \
            --exclude "**/__pycache__/*" --exclude "**/.pyc"
      - name: Upload patch
        uses: softprops/action-gh-release@v1
        with:
          files: code-patch.zip

  build-full-installer:
    runs-on: windows-latest  # Para el .exe
    steps:
      - uses: actions/checkout@v4
      - name: Build Tauri .msi
        run: npx tauri build
      - name: Upload installer
        uses: softprops/action-gh-release@v1
        with:
          files: frontend/src-tauri/target/release/bundle/msi/*.msi
```

---

## 6. Resumen Ejecutivo

### Lo que tienes hoy

| Asset | Estado | Valor para el desktop |
|-------|--------|----------------------|
| 35 endpoints API | ✅ Completo | Se reutiliza 100% en modo DESKTOP |
| Pipeline Nivel 1+2 (Vina+XGBoost) | ✅ Probado | Core del build base $49.99 |
| ESMFold Nivel 3 | ✅ Activo (stub) | Core del DLC Pro $59.99 |
| GNN RTMScore (31 MB modelos) | ✅ En disco | Se incluye en build base |
| Frontend Next.js | ✅ Completo | Se compila estático para Tauri |

### Lo que falta para el primer instalador

| Tarea | Esfuerzo | Semana |
|-------|----------|--------|
| `db_factory.py` (SQLite en DESKTOP) | 2 h | 1 |
| `dispatcher.py` (sin Celery en DESKTOP) | 3 h | 1 |
| `storage.py` (sin MinIO en DESKTOP) | 2 h | 1 |
| Entorno conda Windows para backend | 1 día | 1 |
| Entorno conda Linux para rescoring | 2 h | 2 |
| conda-pack de los 3 entornos | 1 día | 2 |
| `npx tauri init` + sidecars | 1 día | 3 |
| Tauri Updater configurado | 2 h | 3 |
| **Total** | **~6 días reales** | 3 semanas |

### Stack definitivo

| Componente | Tecnología | Razón |
|-----------|-----------|-------|
| UI wrapper | Tauri (Rust) | 10× más ligero que Electron |
| Entorno Python | conda-pack por sidecar | Única forma confiable con rdkit/OpenMM en 2024. ⚠️ SUPERSEDED: ver 09_PACKAGING_STRATEGY.md — pip + Python embed funciona en 2026 |
| Auto-updates | Tauri Updater + GitHub Releases | Gratis, firma criptográfica, delta updates |
| Base de datos local | SQLite + aiosqlite | Sin servidor, un archivo, portable |
| Storage local | Disco (pathlib) | Sin MinIO, archivos en %AppData% |
| Broker de tareas | ThreadPoolExecutor | Sin Redis, 2 workers concurrentes |
| ESMFold | Sidecar independiente (ya existe) | Se empaqueta como está, modo stub/real |
