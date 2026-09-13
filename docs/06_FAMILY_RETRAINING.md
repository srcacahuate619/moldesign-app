> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Plan: Reentrenamiento XGBoost por Familia Estructural

> **ESTADO (Julio 2026 v1.3):** El modelo tiene **176 features** pero ALL_FEATURES = 167
> (ProLIF removido en fix #3). **El retrain con 167 features es obligatorio.**
> Ver [08_SCIENTIFIC_VALIDATION.md](08_SCIENTIFIC_VALIDATION.md).

> **Objetivo**: Alcanzar Spearman > 0.5 en el pipeline de scoring entrenando modelos
> XGBoost específicos por tipo de receptor (GPCR, quinasa, proteasa, etc.) en vez
> de un único modelo universal.

---

## Contexto — Lo que paso antes de este plan

### El problema original

El Spearman benchmark dio correlación NEGATIVA con las 911 moléculas de 5-HT1A:
- **Vina**: ρ = -0.65 (anti-correlacionado)
- **XGBoost (modelo universal)**: ρ = -0.05 (aleatorio)
- **GNN RTMScore**: ρ = -0.56 (anti-correlacionado)

### Causa raíz

El clasificador de familias estructurales (`structural_family.py`) estaba **roto**:

1. Solo tenía 18 PDB IDs en `CURATED_FAMILIES`
2. 655 de 656 complejos PDBbind (99.8%) se clasificaban como `"other"`
3. El modelo se entrenó con una "sopa de todo" sin distinguir GPCR de quinasa de proteasa

### Lo que ya arreglamos

1. ✅ `family_map.json` generado vía RCSB GraphQL API — **865 complejos clasificados en 6 familias**
2. ✅ `structural_family.py` actualizado con CURATED_FAMILIES de 865 entradas + carga automática de family_map.json
3. ✅ DGL → PyG portado (GPU nativa en Windows, sin conda)
4. ✅ Pipeline E2E validado (Vina → XGBoost → GNN → Scoring)
5. ✅ 94 targets pre-cargados offline
6. ✅ Auto-detección de binding sites (cadena, grid, hotspots, multi-ligando)

### Lo que falta (ESTE PLAN)

1. Descargar feature_cache de PDBbind del servidor de producción
2. Reentrenar modelos XGBoost por familia estructural localmente
3. Actualizar `model_manager.py` y backend para usar modelos family-specific
4. Re-ejecutar Spearman benchmark

---

## Distribución de familias (PDBbind v2020 refined: 865 complejos → 752 curados)

| Familia | Complejos | ¿Modelo viable? | Nota |
|---------|:---------:|:----------------:|------|
| soluble_enzyme | 678 | ✅ | Catch-all. Mayoría de PDBbind. |
| kinase | 96 | ✅ | Suficiente para modelo específico |
| protease | 51 | ✅ | Suficiente para modelo específico |
| nuclear_receptor | 19 | ✅ | Mínimo viable (≥15) |
| gpcr | 18 | ✅ | Mínimo viable. Tus 911 moléculas son GPCR → crítico |
| phosphodiesterase | 3 | ❌ | Muy pocos, usa soluble_enzyme como fallback |

---

## Paso 1: Descargar datos del servidor

```powershell
# 1.1 Feature cache (features pre-computados, evita extracción 3D)
scp -r <USER>@<SERVER_IP>:/home/<USER>/molecular-design/data/pdbbind/feature_cache_v4/ D:\moldesign-app\data\pdbbind\feature_cache_v4\

# 1.2 INDEX file (metadatos de afinidad)
scp <USER>@<SERVER_IP>:/home/<USER>/molecular-design/data/pdbbind/INDEX_refined_data.2020 D:\moldesign-app\data\pdbbind\

# 1.3 (Opcional) Si el feature_cache no existe o no es compatible,
#     descargar los PDBs completos:
# scp -r <USER>@<SERVER_IP>:/home/<USER>/molecular-design/data/pdbbind/ D:\moldesign-app\data\pdbbind\
```

> **Credenciales**: Usar las credenciales configuradas en `.env` o `~/.ssh/config`. No hardcodear passwords.

---

## Paso 2: Verificar entorno local

```powershell
cd D:\moldesign-app
.\scripts\install_deps.ps1 -CheckOnly
```

Debe confirmar:
- Python 3.12 (rescoring venv) ✅
- xgboost ✅
- numpy / scipy / scikit-learn ✅
- rdkit ✅
- pandas / joblib ✅

### Estructura de directorios esperada

```
D:\moldesign-app\
├── data\
│   └── pdbbind\
│       ├── feature_cache_v4\     ← bajar del servidor
│       │   └── *.json            (features por complejo)
│       └── INDEX_refined_data.2020
├── rescoring\
│   ├── venv\                     ← Python 3.12 con xgboost, rdkit, etc.
│   ├── artifacts\
│   │   └── family_map.json       ← YA EXISTE (865 entradas)
│   ├── structural_family.py      ← YA ACTUALIZADO
│   ├── train_pipeline.py         ← sin cambios
│   ├── model_manager.py          ← modificar (Paso 4)
│   └── train_families.py         ← CREAR (Paso 3)
├── backend\
│   ├── services\docking\
│   │   ├── queue_handler.py      ← modificar (Paso 5)
│   │   └── rescoring_client.py   ← modificar (Paso 5)
│   └── core\models.py
└── scripts\
    └── spearman_5ht1a.py          ← YA EXISTE
```

---

## Paso 3: Crear y ejecutar script de entrenamiento

### 3.1 Crear `D:\moldesign-app\rescoring\train_families.py`

```python
"""
train_families.py — Reentrenamiento XGBoost por familia estructural.

Usa el feature_cache_v4 para evitar re-extraer features 3D.
Genera modelos separados: kinase, protease, gpcr, nuclear_receptor, soluble_enzyme.
"""
import sys, os, json, time, logging, pickle
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
os.chdir(str(Path(__file__).parent))

from train_pipeline import MLTrainer, ALL_FEATURES, NULL_FEATURES
from structural_family import StructuralFamilyClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

CACHE_DIR = Path("../data/pdbbind/feature_cache_v4")
ARTIFACTS = Path("artifacts")
MIN_FAMILY_SIZE = 15
SEED = 42


def load_cached_features():
    """
    Carga features pre-computados del cache.
    El cache puede estar en varios formatos. Intentamos:
      1. Archivos JSON individuales por complejo
      2. Un archivo features.npz + labels.json
      3. Archivos pickle (.pkl)
    """
    features = {}
    labels = {}

    # Formato 1: JSON files
    json_files = list(CACHE_DIR.glob("*.json"))
    if json_files:
        log.info(f"Found {len(json_files)} JSON cache files")
        for cache_file in json_files:
            with open(cache_file) as f:
                data = json.load(f)
            # Intentar extraer PDB ID del nombre
            pdb_id = cache_file.stem.split("_")[0].upper()
            features[pdb_id] = data.get("features", data)
            if "pki" in data:
                labels[pdb_id] = data["pki"]
            elif "label" in data:
                labels[pdb_id] = data["label"]
        return features, labels

    # Formato 2: NPZ + labels
    npz_files = list(CACHE_DIR.glob("*.npz"))
    if npz_files:
        log.info(f"Found NPZ cache: {npz_files[0]}")
        data = np.load(npz_files[0])
        # Intentar cargar
        return {}, {}

    # Formato 3: CSV file
    csv_files = list(CACHE_DIR.glob("*.csv"))
    if csv_files:
        import pandas as pd
        df = pd.read_csv(csv_files[0])
        log.info(f"Found CSV cache: {len(df)} rows")
        return {}, {}

    log.warning("No recognized cache format found. Will extract features from PDB files.")
    return {}, {}


def main():
    log.info("=" * 60)
    log.info("  FAMILY-SPECIFIC XGBOOST TRAINING (LOCAL)")
    log.info("=" * 60)

    # 1. Load features
    log.info("\nStep 1: Loading features from cache...")
    features, labels = load_cached_features()

    if not features:
        log.warning("No features in cache. Need to extract from PDBbind PDB files.")
        log.warning("Run: python -c \"from train_orchestrator import *; main()\"")
        log.warning("Or download PDBbind PDB files and feature_cache from server.")
        return

    log.info(f"  Loaded {len(features)} complexes with features")

    # 2. Classify by family
    log.info("\nStep 2: Classifying by structural family...")
    with open(ARTIFACTS / "family_map.json") as f:
        family_map = json.load(f)

    by_family = {}
    for pdb_id, fam in family_map.items():
        pid = pdb_id.upper()
        if pid in features:
            by_family.setdefault(fam, []).append(pid)

    log.info("  Family distribution (with features):")
    for fam, ids in sorted(by_family.items(), key=lambda x: -len(x[1])):
        log.info(f"    {fam:25s}: {len(ids)} complexes")

    # 3. Train universal model
    log.info("\nStep 3: Training UNIVERSAL model (all families)...")
    trainer = MLTrainer(seed=SEED)
    all_ids = list(features.keys())

    try:
        X_all, y_all = _build_matrices(all_ids, features, labels)
        train_ids, val_ids = _split_ids(all_ids)
        X_tr, X_vl = _build_matrices(train_ids, features, labels, return_Xy=False)[0], _build_matrices(train_ids, features, labels, return_Xy=False)[0]
        # Simple train/val split
        m = trainer.train_model(
            X_all[:len(train_ids)], y_all[:len(train_ids)], [1]*len(train_ids),
            X_all[len(train_ids):], y_all[len(train_ids):], [1]*len(val_ids),
            ALL_FEATURES, "model_a_universal"
        )
        trainer.save_model(m, ARTIFACTS / "model_a_universal.joblib")
        log.info(f"  UNIVERSAL: Spearman={m.metrics.get('spearman',0):.4f}")
    except Exception as e:
        log.error(f"  UNIVERSAL FAILED: {e}")

    # 4. Train per family
    for fam, fam_ids in sorted(by_family.items()):
        if len(fam_ids) < MIN_FAMILY_SIZE:
            log.info(f"\n  SKIP {fam}: {len(fam_ids)} < {MIN_FAMILY_SIZE}")
            continue

        log.info(f"\nStep 4: Training {fam} ({len(fam_ids)} complexes)...")
        try:
            np.random.seed(SEED)
            np.random.shuffle(fam_ids)
            split = max(5, int(len(fam_ids) * 0.8))
            train_ids = fam_ids[:split]
            val_ids = fam_ids[split:]

            X_train = np.array([[features[pid].get(fn, 0.0) for fn in ALL_FEATURES] for pid in train_ids])
            y_train = np.array([labels.get(pid, features[pid].get("pki", 0)) for pid in train_ids])
            X_val = np.array([[features[pid].get(fn, 0.0) for fn in ALL_FEATURES] for pid in val_ids])
            y_val = np.array([labels.get(pid, features[pid].get("pki", 0)) for pid in val_ids])

            m = trainer.train_model(
                X_train, y_train, [1]*len(train_ids),
                X_val, y_val, [1]*len(val_ids),
                ALL_FEATURES, f"model_a_{fam}"
            )
            trainer.save_model(m, ARTIFACTS / f"model_a_{fam}.joblib")
            log.info(f"  {fam}: Spearman={m.metrics.get('spearman',0):.4f}")
        except Exception as e:
            log.error(f"  {fam} FAILED: {e}")

    log.info("\n" + "=" * 60)
    log.info("  TRAINING COMPLETE")
    log.info(f"  Models: {list(ARTIFACTS.glob('model_a*.joblib'))}")
    log.info("=" * 60)


def _build_matrices(ids, features, labels, return_Xy=True):
    X = np.array([[features[pid].get(fn, 0.0) for fn in ALL_FEATURES] for pid in ids])
    y = np.array([labels.get(pid, features[pid].get("pki", 0)) for pid in ids])
    return X, y

def _split_ids(ids):
    np.random.seed(SEED)
    shuffled = list(ids)
    np.random.shuffle(shuffled)
    split = int(len(shuffled) * 0.8)
    return shuffled[:split], shuffled[split:]


if __name__ == "__main__":
    main()
```

### 3.2 Si el cache no existe o es incompatible

Si `feature_cache_v4` no funciona, hay que extraer features desde los PDBs. Esto requiere tener los archivos PDB de PDBbind locales. El pipeline de extracción usa:

```python
from pdbbind_parser import PDBBindParser
from data_curator import DataCurator
from feature_extractor import InteractionFeatureExtractor

parser = PDBBindParser(data_dir="../data/pdbbind")
parser.load()
vip, report = DataCurator().curate(parser.complexes)
# ... extraer features con InteractionFeatureExtractor para cada complejo
```

Tiempo estimado de extracción: **20-40 minutos** para 752 complejos.

### 3.3 Ejecutar

```powershell
cd D:\moldesign-app\rescoring
.\venv\Scripts\python.exe train_families.py
```

---

## Paso 4: Convertir modelos .joblib → .json

```powershell
cd D:\moldesign-app\rescoring
.\venv\Scripts\python.exe -c "
from pathlib import Path
from model_manager import ModelManager

mm = ModelManager()
artifacts = Path('artifacts')
for jp in artifacts.glob('model_a*.joblib'):
    name = jp.stem
    mm._auto_convert_joblib(
        artifacts / f'{name}.json',
        artifacts / f'model_null.json',
        artifacts / f'{name}.json',
    )
    print(f'Converted: {name}')
"
```

---

## Paso 5: Actualizar model_manager.py para modelos por familia

### 5.1 Agregar a `ModelManager.__init__()` (después de línea 44)

```python
# Family-specific models
self.family_models: dict[str, Any] = {}
self.family_metadata: dict[str, dict] = {}
```

### 5.2 Agregar a `ModelManager.load_models()` (después de cargar model_a_extended)

```python
# ── Cargar modelos por familia estructural ──
family_model_dir = Path(settings.model_a_path).parent
for family in ["kinase", "protease", "gpcr", "nuclear_receptor", "soluble_enzyme"]:
    fam_path = family_model_dir / f"model_a_{family}.json"
    if not fam_path.exists():
        continue
    try:
        model = xgb.Booster()
        model.load_model(str(fam_path))
        self.family_models[family] = model
        meta_path = fam_path.with_suffix(".metadata.json")
        if meta_path.exists():
            with open(meta_path) as f:
                self.family_metadata[family] = json.load(f)
        else:
            self.family_metadata[family] = {"feature_names": ALL_FEATURES}
        log.info(f"family_model_loaded", family=family)
    except Exception as e:
        log.warning(f"family_model_load_failed", family=family, error=str(e))
```

### 5.3 Modificar `ModelManager.predict()` para enrutar por familia

Al inicio del método, agregar:

```python
# Detectar familia del target
target_family = getattr(request, 'target_family', None)

# Seleccionar modelo: family-specific > universal fallback
if target_family and target_family in self.family_models:
    active_model = self.family_models[target_family]
    active_artifact = self.family_metadata[target_family]
    log.info("using_family_model", family=target_family)
else:
    active_model = self.model_a
    active_artifact = self.model_a_artifact
```

Luego reemplazar todas las referencias a `self.model_a` dentro del método `predict()` por `active_model` y `self.model_a_artifact` por `active_artifact`.

**Alternativa más simple**: Solo modificar la sección donde se hace la predicción de Model A Core (línea ~366):

```python
# Seleccionar modelo según familia
target_family = getattr(request, 'target_family', None)
if target_family and target_family in self.family_models:
    model_for_prediction = self.family_models[target_family]
    artifact_for_prediction = self.family_metadata.get(target_family, self.model_a_artifact)
else:
    model_for_prediction = self.model_a
    artifact_for_prediction = self.model_a_artifact

features_a = self._prepare_feature_vector(all_features, model="A")
feature_names_a = artifact_for_prediction.get("feature_names", [])
dm_a = xgb.DMatrix(features_a.reshape(1, -1), feature_names=feature_names_a)
score_a_core = float(model_for_prediction.predict(dm_a)[0])
```

---

## Paso 6: Pasar target_family al rescoring desde el backend

### 6.1 `backend/services/docking/rescoring_client.py`

Agregar campo a `RescoreRequest`:

```python
class RescoreRequest(BaseModel):
    # ... campos existentes ...
    target_family: str | None = None  # Familia estructural para modelo específico
```

### 6.2 `backend/services/docking/queue_handler.py` (línea ~569)

Agregar `target_family` a la llamada:

```python
target_family = getattr(target, "structural_family", None)
ml_result = await get_ml_rescore(
    smiles=smiles,
    target_pdb_path=get_target_pdb_path(target.pdb_id),
    poses=[p.model_dump() for p in docking.poses],
    properties=properties,
    grid_center=list(box_center),
    grid_size=list(box_size),
    run_gnn=True,
    target_family=target_family,  # NUEVO
)
```

### 6.3 `backend/services/docking/rescoring_client.py` (función `get_ml_rescore`)

Agregar `target_family` al payload:

```python
request_data = RescoreRequest(
    # ... campos existentes ...
    target_family=target_family,  # NUEVO
)
```

---

## Paso 7: Re-ejecutar Spearman benchmark

```powershell
cd D:\moldesign-app
python scripts\spearman_5ht1a.py
```

Con el modelo GPCR-specific para 5-HT1A, el Spearman esperado:

| Capa | Antes (universal) | Ahora (family-specific) |
|------|:-----------------:|:-----------------------:|
| Vina | -0.65 | 0.15-0.30 |
| XGBoost | -0.05 | **0.40-0.60** |
| GNN | -0.56 | **0.35-0.55** |

---

## Paso 8: Ejecutar validación completa E2E

```powershell
cd D:\moldesign-app
python scripts\validate_pipeline.py -n 5
```

Debe mostrar:
- GNN available: 5/5
- Family model usado en logs
- Scores coherentes por target

---

## Resumen de archivos

| Archivo | Acción | Dónde |
|---------|--------|-------|
| `rescoring/train_families.py` | **CREAR** | Script de entrenamiento local |
| `rescoring/model_manager.py` | **MODIFICAR** | family_models dict + routing |
| `backend/services/docking/rescoring_client.py` | **MODIFICAR** | target_family en request |
| `backend/services/docking/queue_handler.py` | **MODIFICAR** | target_family al llamar rescoring |
| `data/pdbbind/feature_cache_v4/` | **DESCARGAR** | Del servidor (192.168.1.64) |
| `data/pdbbind/INDEX_refined_data.2020` | **DESCARGAR** | Del servidor |
| `rescoring/artifacts/family_map.json` | ✅ Existe | 865 PDB IDs clasificados |
| `rescoring/structural_family.py` | ✅ Actualizado | CURATED_FAMILIES 865 entradas |

---

## Ejecución completa — Julio 2026

### Modelos entrenados finales (692 complejos, feature set v4.1 = 167 features)

> **Nota (Julio 2026):** Valores actualizados según `artifacts/model_a_*.metadata.json`.
> El feature set son 167 features (8 1D/2D + 4 Vina + 3 size-norm + 96 Shell + 56 ECIF).
> Las 9 features ProLIF fueron removidas en Fix #3.

| Modelo | Complejos | Features | Spearman CV | Quality Gate | Estado |
|--------|:---------:|:--------:|:-----------:|:------------:|--------|
| universal | 692 | 167 | 0.7643 (p<0.001) | — | ✅ Producción |
| soluble_enzyme | 542 | 167 | 0.7029 (p<0.001) | PASA | ✅ Usado |
| protease | 40 | 167 | 0.7364 (p=0.019) | PASA | ✅ Usado |
| kinase | 76 | 167 | 0.4256 | Spearman < 0.5 | ⏭️ Universal |
| gpcr | 14 | 167 | 0.400 | Spearman < 0.5 | ⏭️ Universal |
| nuclear_receptor | 15 | 167 | -0.400 | No significativo | ⏭️ Universal |

### Fixes implementados

> ⚠️ **PENDIENTE (Julio 2026):** `model_a.json` (modelo DEFAULT en producción) todavía
> tiene **176 features** incluyendo 9 features ProLIF. En inferencia, estas features son
> siempre 0.0 (`skip_prolif=True` en `model_manager.py:417`), creando un mismatch
> training/inference. Los modelos familiares (`model_a_universal.json`, etc.) ya usan
> el feature set correcto de 167 features.
> **Acción requerida:** Reemplazar `model_a.json` con `model_a_universal.json` o
> re-entrenar model_a con 167 features.

1. **Quality Gate** (`model_manager.py:436-456`): El modelo familiar solo se usa si Spearman CV ≥ 0.5 Y p < 0.05. Caso contrario → fallback al universal. Esto evita que GPCR (entrenado con 14 muestras) se use en vez del universal (692 muestras).

2. **Features v4.1** (`train_pipeline.py:85-91`): Feature set de 167 features sin ProLIF. Grupos: A_EXT (8 1D/2D) + B (4 Vina) + C_EXT (3 size-norm) + D (96 Shell) + E (56 ECIF). Las 9 features ProLIF fueron removidas (Fix #3) porque actuaban como ruido (SHAP < 0.003).

3. **Vina Features Reales** (`data/pdbbind/feature_cache_v4/`): 540/865 complejos re-dockeados con AutoDock Vina (exhaustiveness=8). 339 rellenados con media para 100% coverage. Los features Vina (`vina_best_score`, `pose_score_variance`, etc.) ahora tienen valores reales en training.

4. **Delta-Learning** (`train_families.py:273-277`): Modelo entrenado para predecir `pKi - Vina_pKi`. En inferencia, `model_manager.py:470-476` reconstruye: `pKi_pred = Vina_pKi + delta_pred`. No mejoró el benchmark (skew PDBbind→ChEMBL persiste).

5. **Clasificador Binario** (`rescoring/artifacts/classifier_binder.json`): XGBoost classifier con Shell+ECIF+1D (160 features). Predice P(pKi > 7.0). ROC AUC 0.858, F1 0.805 en PDBbind validation. Integrado en `model_manager.py` y expuesto como `classifier_prob` en `/rescore`.

6. **QuickVina 2** (`backend/services/docking/vina_service.py:287-295`): Cableado `docking_engine` parameter. Modo `qvina2` usa exhaustiveness=4 (~3x más rápido). Config existía pero sin backend wiring. Frontend `DockingEnginePanel.tsx` ya tenía el selector.

### Benchmark 5-HT1A (7E2Y, GPCR) — 99 moléculas ChEMBL

| Métrica | Mejor ρ | p-val | Nota |
|---------|:-------:|:-----:|------|
| Vina (raw, exh=8) | +0.286 | 0.004 | Significativo ✅ |
| Vina (quick, exh=4) | +0.182 | 0.071 | Tendencia (6.7 min vs 12 min) |
| XGBoost | +0.228 | 0.110 | Mejor corrida, no significativo |
| GNN RTMScore | +0.200 | 0.338 | Solo 30/99 muestras |
| Interaction score | -0.035 | 0.731 | No ayuda para GPCR |

### Lecciones aprendidas

1. **Train/serve skew es el problema fundamental**: Features 3D de PDBbind (cristales) no transfieren a ChEMBL (dockeados). Vina es la señal más robusta porque usa el mismo motor en training e inferencia.

2. **GPCR es la familia más difícil**: Vina solo ρ=0.07 con pKi en PDBbind para GPCRs. Los bolsillos transmembranales son inherentemente más difíciles de modelar.

3. **Clasificación > Regresión**: El clasificador binario (ROC AUC 0.858) es más robusto que la regresión de pKi. El dominio shift degrada menos la clasificación.

4. **Calibración Vina no cambia Spearman**: Es una transformación lineal monótona. Solo sirve para combinar scores en diferentes escalas.

5. **Interaction fingerprints no ayudan en GPCR**: El conteo total de interacciones (hbonds, hydrophobic, etc.) no correlaciona con pKi para 5-HT1A. Posiblemente porque GPCR binding depende de interacciones específicas con residuos clave, no del conteo total.

### Próximos pasos recomendados

1. **MM-GBSA rescoring**: OpenMM con solvente implícito OBC2. Ya implementado en `scoring/mmgbsa.py`. Corregiría efectos de solvente que Vina ignora. ~15s/molécula en GPU.

2. **Consenso Vina + GNN + clasificador**: Pesos fijos en vez de XGBoost. Más robusto al skew.

3. **Refinamiento estructural post-docking**: OpenMM minimization (100 steps) para aliviar steric clashes. Ya implementado como stage del pipeline PRO pero deshabilitado.

4. **Transfer learning GPCR**: Pre-entrenar en PDBbind general (14K+ complejos), fine-tunear en GPCR específicos. Imrie et al. 2018 muestra que esto funciona.

### Archivos modificados/creados en esta sesión

| Archivo | Acción |
|---------|--------|
| `rescoring/train_families.py` | MODIFICADO — Delta-learning, ECIF features, feature_names param |
| `rescoring/model_manager.py` | MODIFICADO — Quality gate, clasificador, delta reconstruction, params en metadata |
| `rescoring/schemas.py` | MODIFICADO — `classifier_prob` en RescoreResponse |
| `backend/services/docking/vina_service.py` | MODIFICADO — `docking_engine` param, exhaustiveness override |
| `backend/core/database.py` | MODIFICADO — SQLite WAL mode + busy_timeout |
| `backend/core/db_factory.py` | MODIFICADO — SQLite WAL mode |
| `data/pdbbind/feature_cache_v4/` | MODIFICADO — 526 complejos con Vina features reales |
| `rescoring/artifacts/classifier_binder.json` | NUEVO — Clasificador binario |
| `rescoring/artifacts/vina_calibration.json` | NUEVO — Coeficientes de calibración por familia |
| `docs/06_FAMILY_RETRAINING.md` | MODIFICADO — Este documento |

---

## Checklist de inicio rápido (original)

```powershell
# 1. Descargar datos del servidor (~5 min)
scp -r <USER>@<SERVER_IP>:/home/<USER>/molecular-design/data/pdbbind/feature_cache_v4/ D:\moldesign-app\data\pdbbind\feature_cache_v4\

# 2. Ejecutar entrenamiento (~10 min)
cd D:\moldesign-app\rescoring
.\venv\Scripts\python.exe train_families.py

# 3. Convertir modelos (~1 min)
.\venv\Scripts\python.exe -c "from model_manager import ModelManager; from pathlib import Path; mm=ModelManager(); [mm._auto_convert_joblib(Path(f'artifacts/{j.stem}.json'), Path('artifacts/model_null.json')) for j in Path('artifacts').glob('model_a*.joblib')]"

# 4. Arrancar sidecar rescoring
# (Inicia automáticamente con start-desktop.ps1 o manualmente:)
.\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001

# 5. Ejecutar benchmark
cd D:\moldesign-app
python scripts\spearman_5ht1a.py
```

---

## Contacto rápido

- **Servidor producción**: Ver `.env` o `~/.ssh/config` para credenciales
- **PDBbind data**: `/home/<USER>/molecular-design/data/pdbbind/` (30 GB)
- **Docker rescoring**: `docker exec -it moldesign_rescoring python3` (si necesitas debuggear)
- **Feature cache**: `/home/<USER>/molecular-design/data/pdbbind/feature_cache_v4/`
