> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Estrategia de Empaquetado Desktop — Analisis v2.0

> **Hallazgo clave**: NO necesitamos conda. Todo funciona via pip en Python 3.14.
> Esto elimina la dependencia de conda-pack/conda-forge y simplifica masivamente.

---

## 1. Realidad de dependencias

Verificado con pip list en la maquina de desarrollo:

| Paquete | Via | Version |
|---------|-----|---------|
| rdkit | **pip** | 2025.9.6 |
| openmm | **pip** | 8.5.2 |
| xgboost | **pip** | 3.2.0 |
| meeko | **pip** | 0.7.1 |
| prolif | **pip** | 2.1.0 |
| MDAnalysis | **pip** | 2.10.0 |
| scikit-learn | **pip** | 1.8.0 |
| shap | **pip** | 0.52.0 |
| numpy, scipy, pandas | **pip** | latest |
| torch | **pip** | 2.14.0.dev |

**micromamba**: NO instalado en el sistema
**conda**: NO instalado en el sistema
**conda-pack**: NO instalado

**Conclusion**: El environment-desktop.yml y el plan de conda-pack son
LEGACY. El proyecto ya funciona 100% con pip.

---

## 2. Opciones de Empaquetado — Comparativa

### Opcion A: conda-pack (plan original)

```
Tauri .msi
  +-- conda-pack env-backend.tar.gz  (~800 MB)
  +-- conda-pack env-rescoring.tar.gz (~300 MB)
  +-- conda-pack env-esmfold.tar.gz   (~150 MB)
  +-- Python code
  +-- Vina .exe
  +-- Models
  ─────────────────────────────────
  Total installer: ~4-6 GB
```

| Pro | Contra |
|-----|--------|
| Entorno deterministico | Requiere micromamba instalado para BUILD |
| Probado en Linux | No hay micromamba en esta maquina |
| | Instalador gigante (4-6 GB) |
| | Updates requieren re-descargar GBs |
| | Complejidad CI alta (3 entornos x 3 OS) |

### Opcion B: Embedded Python + pip first-launch

```
Tauri .msi
  +-- python-3.12-embed-amd64/       (~40 MB)
  +-- requirements-desktop.txt
  +-- Vina .exe                      (~1.2 MB)
  +-- Python code                    (~5 MB)
  +-- Models                         (~11 MB)
  +-- Pre-cached PDBs                (~60 MB)
  ─────────────────────────────────
  Total installer: ~120 MB
  First launch: pip install (~500 MB download, ~10-15 min)
```

| Pro | Contra |
|-----|--------|
| Instalador chico (120 MB) | Requiere internet primer uso |
| pip universal (funciona YA) | 10-15 min first launch |
| Updates de codigo: ~5 MB | Si pip falla, el usuario ve errores |
| Sin dependencia de conda | |
| CI simple (1 OS) | |

### Opcion C: Embedded Python + pip wheel cache

```
Tauri .msi
  +-- python-3.12-embed-amd64/       (~40 MB)
  +-- wheelhouse/                    (~500 MB, pre-downloaded .whl)
  +-- Vina .exe                      (~1.2 MB)
  +-- Python code                    (~5 MB)
  +-- Models                         (~11 MB)
  +-- Pre-cached PDBs                (~60 MB)
  ─────────────────────────────────
  Total installer: ~620 MB
  First launch: pip install from cache (~2-5 min, sin internet)
```

| Pro | Contra |
|-----|--------|
| Sin internet requerido | Instalador mediano (620 MB) |
| First launch rapido (2-5 min) | Hay que mantener wheel cache |
| pip confiable (local) | El cache ocupa ~500 MB en disco post-install |
| Updates: solo diff de wheels | |
| CI: pre-download wheels en build | |

### Opcion D: Embedded Python + sitio-paquetes pre-instalado

```
Tauri .msi
  +-- python-3.12-embed-amd64/       (~40 MB)
  +-- Lib/site-packages/             (~500 MB, pre-instalado)
  +-- Vina .exe                      (~1.2 MB)
  +-- Python code                    (~5 MB)
  +-- Models                         (~11 MB)
  +-- Pre-cached PDBs                (~60 MB)
  ─────────────────────────────────
  Total installer: ~620 MB
  First launch: instantaneo
```

| Pro | Contra |
|-----|--------|
| Instantaneo first launch | Mismo tamano que C, mas fragil |
| Sin pip en first launch | site-packages de dev != usuario |
| | Paths hardcodeados pueden romper |
| | Dificil de mantener/actualizar |

---

## 3. Analisis de componentes por peso

| Componente | Peso | ¿Base o DLC? |
|-----------|------|-------------|
| Python 3.12 embed | 40 MB | Base |
| Vina .exe | 1.2 MB | Base |
| Codigo Python (~150 .py) | 5 MB | Base |
| Modelos XGBoost (11 MB) | 11 MB | Base |
| PDBs pre-cached (94) | 60 MB | Base |
| rdkit + numpy + scipy + pandas | 220 MB | Base |
| xgboost + meeko + MDAnalysis + prolif | 80 MB | Base |
| openmm | 25 MB | Base |
| fastapi + uvicorn + sqlalchemy | 25 MB | Base |
| scikit-learn + shap | 30 MB | Base |
| reportlab + pillow | 25 MB | Base |
| admet_ai + tabpfn | 130 MB | Base* |
| anthropic | 2 MB | Base |
| **SUBTOTAL BASE** | **~650 MB** | |
| torch + torch-geometric | 2.5 GB | **DLC Pro** |
| transformers + ESMFold weights | 3.5 GB | **DLC Pro** |
| **TOTAL CON DLC** | **~6.7 GB** | |

*admet_ai/tabpfn: Se podrian mover a DLC si el usuario acepta
ADMET mock (como modo rapido).

---

## 4. Recomendacion Final — Opcion C+

### Estrategia: Embedded Python + wheel cache + DLC

```
BASE INSTALLER (~2.9 GB para Steam):
  Tauri shell                        25 MB
  Python 3.12 embed                  40 MB
  wheelhouse/ (core deps)           250 MB  (sin torch, sin admet_ai completo)
  Vina .exe                          1.2 MB
  Codigo Python                      5 MB
  Modelos XGBoost                    11 MB
  PDBs pre-cached                    60 MB
  LLM local (Phi-3.5-mini Q4)     2390 MB  ← NUEVO v1.3: incluido en base

DLC PRO (~3-6 GB, descarga opcional):
  torch + torch-geometric (CUDA)   2.5 GB
  ESMFold real mode (stub incluido
    en base, pesos en DLC)         3.5 GB

FIRST LAUNCH (sin internet):
  pip install deps desde wheelhouse/ ~2-5 min
  RAM idle: ~320 MB

UPDATES (Tauri Updater):
  Codigo: 5-30 MB
  Modelos: 11 MB
  Dependencias nuevas: solo el .whl nuevo
```

### Por que esta y no otra

1. **No conda**: Ya esta todo via pip. Agregar conda es complejidad innecesaria.
2. **Tamano aceptable**: ~2.9 GB (~2.0 GB comprimido). El LLM local es el 82% del peso.
3. **Offline**: El wheel cache permite instalacion sin internet.
4. **LLM bundled**: El modelo Phi-3.5-mini viene incluido. El usuario nunca lo descarga.
5. **Updates livianos**: Tauri Updater solo baja deltas de codigo/modelos.
6. **DLC real**: torch + ESMFold son gigantes. Separarlos es correcto.
7. **Probado**: pip install ya funciona en esta maquina con Python 3.14.

### Plan de implementacion

| Paso | Tiempo |
|------|--------|
| 1. Generar wheelhouse con pip download | 1h |
| 2. Configurar externalBin en tauri.conf | 1h |
| 3. Empaquetar Python embed + wheels en .msi | 4h |
| 4. Build de release Tauri | 2h |
| 5. Test en VM Windows limpia | 2h |
| 6. Configurar Tauri Updater | 1h |
| **Total** | **~2 dias** |
