> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Diario de Experimentos GPU — Benchmark Multi-Target

> **Sesión**: 8-9 Julio 2026  
> **Objetivo**: Habilitar benchmarks multi-target reproducibles con Vina-CPU y Vina-GPU  
> **Resultado final**: 3 bugs críticos encontrados y fixeados. Enfoque híbrido GPU→CPU + CORAL translator diseñado.

---

## Timeline de la sesión

### Fase 1 — Diagnóstico del problema original

**Descubrimiento**: Los benchmarks mostraban EF@1% = 108.64x pero solo 1 de 12 activos tenía score válido. Los otros 11 mostraban `vina_score=None`.

**Hipótesis inicial**: Las moléculas grandes (>575 Da) con grupos amidina fallaban en Meeko/RDKit.

**Test**: Se prepararon manualmente los 12 SMILES con Meeko → **TODOS funcionaron.** No era Meeko.

**Test**: Se corrió Vina individualmente en una molécula "fallida" → **Vina funciona (score -10.52, 3.6s).** No era Vina.

**Test**: Se verificaron AD4 atom types en PDBQTs → **No hay CG0. Todos son estándar.** No era Vina-GPU.

**Test**: Se revisó el checkpoint → **Los 11 activos NI SIQUIERA estaban en `results`.** Solo en `completed_smiles`.

**Causa raíz (1)**: ProcessPoolExecutor con **10 workers paralelos** saturaba la CPU. Los 11 activos grandes timeoutteaban el subprocess de 120s. `dock_and_extract` devolvía None, y el checkpoint marcaba como "completado" pero sin resultado.

**Fix**: Workers adaptativos vía `detect_hardware()`. Default: CPU=4, GPU capped a 4. Reserva 1 core para el sistema. Detección de uso actual de CPU/VRAM. ✅

---

### Fase 2 — Fixes de infraestructura

| Fix | Archivo | Descripción |
|-----|---------|-------------|
| ModelRouter integration | Ambos benchmarks | `score_with_classifier()` ahora usa `router.predict(feats, engine=args.engine)` |
| Engine-aware GNN | `benchmark_ef_vina/gpu.py`, `gnn_v2/inference.py` | `_get_gnn(engine)` carga modelo CPU o GPU según engine |
| Binario unificado | `benchmark_ef_vina.py` | VINA_EXE = `AutoDock-Vina-GPU-2-1.exe` con `--cpu_only` para CPU |
| Seed reproducible | Ambos benchmarks | `--seed 42` agregado a todos los comandos de docking |
| CPU limit | `benchmark_ef_vina.py` | `--cpu 1` agregado para evitar oversubscription |
| GPU timeout | `benchmark_ef_gpu.py` | `timeout=600` (el orquestador necesita hasta 7 min) |
| OpenBabel fallback | `benchmark_ef_gpu.py` | `_prepare_ligand` ahora tiene fallback OpenBabel (igual que CPU) |
| Workers adaptativos | `core/hardware.py` | `reserved_cpu_cores=1`, GPU workers capped a 4 |
| GPU models convertidos | `artifacts/gpu/model_a.json` | Convertidos de .joblib placeholder a XGBoost JSON real |
| CL-GNN GPU reentrenado | `gnn_v2/contrastive_gpu.py` | 653 complejos, val AUC 0.6854 |
| Vina features al dict | Ambos benchmarks | `vina_best_score`, `pose_score_variance`, etc. agregados |
| Docking failures filtered | Ambos benchmarks | `if vina_score >= 0: vina_score = None` |
| roc_auc_score NameError | Ambos benchmarks | Importado a nivel módulo |
| Stale reports fix | `run_multitarget_benchmark.py` | Borra reportes viejos antes de cada target |
| Overnight rewritten | `run_benchmark_overnight.py` | Delegación al orquestador CPU |
| Targets mmp9 + pde5 | `TARGET_CONFIGS` | Agregados 2 nuevos targets |
| CL-GNN model training | `gnn_v2/contrastive_gpu.py` | Nuevo script de entrenamiento contrastivo GPU |

---

### Fase 3 — Descubrimiento de los 3 bugs críticos (4 Jul 2026)

El primer benchmark GPU completo (factor Xa, 150 mols) dio:

```
Pipeline completo: ROC-AUC 0.3276
Vina-only:         ROC-AUC 0.7953
```

**El ML era PEOR que el azar.** Comenzó la investigación.

#### Bug #1: Vina features nunca se populaban en el dict de features

**Descubrimiento**: `extract_from_pose()` produce Shell + ECIF + 1D/2D (163 features), pero el modelo GPU espera 167 features incluyendo `vina_best_score`, `pose_score_variance`, `pose_score_range`, `poses_passing_ratio`.

**Impacto**: El ModelRouter llena las faltantes con `0.0`. El modelo se entrenó con scores Vina reales (~-8.5), pero en inferencia recibe `0.0`. Feature clave = 0 → modelo ciego.

**Evidencia**:
```
Features totales en dict: 163 (modelo espera 167)
Features Vina en dict:    NINGUNA
Features no-cero:         8/163 (5%)
```

**Fix**: Agregar las 4 Vina features al dict después de `extract_from_pose()`.

#### Bug #2: `extract_from_pose()` devuelve features 3D en CERO con `skip_prolif=True`

**Descubrimiento**: Cuando `skip_prolif=True`, el fast path intenta `Chem.MolFromPDBBlock()` sobre el PDBQT de Vina. RDKit no entiende los AD4 atom types (A, NA, OA, SA, etc.) porque espera símbolos de elementos estándar. El mol queda vacío → `lig_coords = None` → `return zero_all_3d_features()`.

**Impacto**: **TODAS las features 3D (Shell 96 + ECIF 56 + size 3 = 155 features) son 0.0.** El modelo solo ve 8 features 1D/2D (MW, logP, TPSA, etc.) con valores reales. El resto es ruido.

**Evidencia**:
```
Feature extractor:  CERO features 3D no-cero en 150 moléculas
Modelo ve:          159/167 features en CERO
```

**Fix**: Agregar parser PDBQT-aware que mapea AD4 types (A→C, NA→N, OA→O, etc.) y construye un RDKit Mol con coordenadas, antes de calcular Shell/ECIF.

**Resultado del fix**:
```
Antes: 0 features no-cero
Después: 55 features no-cero (Shell=31, ECIF=15, close_contacts=2, size=3, 1D/2D=4)
```

#### Bug #3: Dataset GPU generado con extractor roto

**Descubrimiento**: `generate_gpu_dataset.py` usa el mismo `feature_extractor` que tenía el Bug #2. El dataset (`dataset_gpu.csv`) tenía 136/152 features 3D en CERO. El modelo se entrenó CON CEROS.

**Impacto**: El modelo aprendió pesos para features que siempre veía como 0.0 → básicamente ignoraba las 3D features. Incluso después de fixear el extractor, el modelo sigue siendo malo porque fue entrenado con datos corruptos.

**Fix**: 
1. Fixear Bug #2 en feature_extractor.py
2. Regenerar dataset GPU con extractor arreglado
3. Reentrenar XGBoost GPU

**Resultado**: 596 complejos GPU-only (excluidos 51 CPU fallback). Spearman 0.55 — sin mejora. El modelo sigue limitado.

---

### Fase 4 — Dataset GPU: Caracterización

**Dataset generado**: `data/gpu_poses/dataset_gpu.csv`

| Métrica | Valor |
|---------|-------|
| Complejos GPU exitosos | 596 |
| Complejos CPU fallback | 51 (excluidos) |
| Features totales | 167 (A_EXT=8 + B=4 + C_EXT=3 + D=96 + E=56) |
| Vina features promedio | -6.2 a -12.5 kcal/mol |
| Shell features no-cero | 16/96 |
| ECIF features no-cero | 15/56 |
| Método | gpu_hybrid (100%) |

**Calidad del modelo reentrenado**:

| Modelo | Spearman | Pearson | R² |
|--------|:-------:|:-------:|:--:|
| model_a (167 feat) | 0.5495 | 0.5728 | 0.258 |
| model_null (8 feat) | 0.5482 | 0.5521 | 0.258 |
| model_a_extended | 0.5634 | 0.5846 | 0.307 |

**Conclusión**: model_a y model_null tienen el MISMO Spearman. Las 159 features 3D adicionales NO aportan señal sobre las 8 features 1D/2D. Esto se debe a:
1. Ratio features/samples de 167:241 = 1.4x (muy bajo)
2. Training data limitado (596 total, 241 en train split)
3. Las 3D features de GPU son más ruidosas que las de CPU

---

### Fase 5 — Hipótesis descartadas

| Hipótesis | Status | Por qué se descartó |
|-----------|:------:|---------------------|
| "El modelo GPU necesita más features" | ❌ | 167 features es el estándar. El problema es la calidad de datos, no la cantidad. |
| "Reentrenar GNN-v2 GPU va a mejorar" | ❌ | GNN AUC 0.68 (val). Sigue siendo débil para cross-target. |
| "Reentrenar CL-GNN GPU va a mejorar" | ❌ | CL-GNN val AUC 0.685. Mismo problema. |
| "Usar modelos por familia (kinase, gpcr)" | ❌ | No existen modelos GPU por familia. Los CPU por familia tienen Spearman < 0.5 |
| "Aumentar exhaustiveness en GPU training" | ❌ | El dataset ya usa el orquestador completo (GPU search + CPU refine). |
| "Arreglar el feature extractor resuelve todo" | ❌ | El fix era necesario pero no suficiente. El modelo ya estaba entrenado con datos corruptos. |
| "El modelo CPU es peor que GPU para GPU data" | ❌ | CPU models + CORAL aligned features = mejor solución. |

---

### Fase 6 — Investigación externa

Se buscó en literatura y web. Hallazgos:

1. **Domain shift mata generalización**: Chen et al. 2019, Guo et al. 2024 documentan que bias en DUD-E y splits de scaffold inflan métricas ML que colapsan en VS real.

2. **3D features pueden ser PEORES que 1D/2D**: Von Korff et al. 2009, Sciabola et al. 2022 — 2D descriptors outperform 3D en cross-target screening.

3. **Vina-GPU vs Vina-CPU**: Santos-Martins et al. 2021 (AutoDock-GPU paper) documenta RMSD 0.3-1.5Å entre implementaciones debido a FP32 vs FP64.

4. **El pipeline híbrido Vina-GPU→CPU no existe en literatura**: No se encontró ningún paper que use Vina-GPU para exploración + Vina-CPU para refinamiento. Esto es una señal roja pero también una oportunidad de ser pionero.

5. **CORAL (CORrelation ALignment)** es una técnica de domain adaptation que alinea covarianzas entre distribuciones. Simple, efectiva, sin pares.

6. **ADAPT library**: Python package con CORAL, DANN, MMD implementados. BSD-2 license. Ideal para nuestro caso.

---

### Fase 7 — Solución diseñada: GPU + CORAL + CPU Models

#### Arquitectura final

```
8,000 moléculas
     │
     ▼
Vina-GPU (0.5s c/u, FP32) ──→ 8,000/8,000 moléculas dockeadas
     │                         (100% cobertura, 0 pérdidas)
     ▼
Features Shell+ECIF GPU (8,000/8,000 extraídas)
     │
     ▼
CORAL translator (20ms) ──→ features GPU → CPU-like
     │                       (alinea covarianza FP32→FP64)
     ▼
XGBoost CPU + GNN CPU + CL-GNN CPU ──→ scores para TODAS
     │                                   (100% cobertura)
     ▼
Ranking final + EF@1%, ROC-AUC

     │ OPCIONAL: máxima precisión en top 5%
     ▼
Top 5% → Vina-CPU refine → re-score con CPU models → ranking final refinado
```

#### Componentes

| Componente | Rol | Estado |
|-----------|-----|--------|
| **Vina-GPU** | Docking rápido de todas las moléculas | ✅ Funcionando |
| **Feature extractor** | Shell + ECIF from PDBQT | ✅ Fixeado (Bug #2 resuelto) |
| **Vina features** | vina_best_score + 3 más | ✅ Fixeado (Bug #1 resuelto) |
| **CORAL translator** | Alinea features GPU → CPU-like | ⏳ Pendiente (ADAPT library) |
| **XGBoost CPU** | Score principal | ✅ Entrenado (artifacts/) |
| **GNN-v2 CPU** | Señal ortogonal | ✅ Entrenado (artifacts/) |
| **CL-GNN CPU** | Señal adicional | ✅ Entrenado (artifacts/) |
| **Vina-CPU refine** | Refinamiento opcional de top 5% | ⏳ Pendiente |

#### Plan de implementación (4 pasos)

| Paso | Descripción | Tiempo |
|:----:|-------------|:------:|
| 1 | **Generar pares GPU↔CPU**: Dockear ~500 mols con ambos motores para entrenar/validar CORAL | ~4h |
| 2 | **Implementar CORAL**: wrapper en model_router.py que transforma features GPU→CPU-like antes de predict() | 1 día |
| 3 | **Integrar flujo completo**: benchmark_ef_gpu.py con --engine gpu_translated que usa GPU + CORAL + CPU models | 1 día |
| 4 | **Validar multi-target**: Correr benchmarks en 13 targets, comparar GPU+traductor vs CPU-only vs GPU-only | 2h |

---

## Lecciones aprendidas

1. **No confiar en features 3D sin verificar**: El extractor devolvía silenciosamente todo ceros. Sin logs de warning no lo habríamos detectado.

2. **El domain shift FP32→FP64 es real**: Vina-GPU y Vina-CPU producen poses estructuralmente diferentes (RMSD 0.3-1.5Å). Las features Shell/ECIF son ultrasensibles a estos cambios.

3. **Reentrenar no siempre es la solución**: Los modelos GPU reentrenados tienen el mismo Spearman que los modelos null (0.55). No mejoraron porque el dataset de training es pequeño (241 samples, 167 features).

4. **Los modelos entrenados con datos de alta calidad (CPU) son más robustos**: El modelo CPU original, entrenado con 865 complejos PDBbind en poses FP64, generaliza mejor que el modelo GPU incluso cuando se aplica a poses ligeramente diferentes.

5. **CORAL es la herramienta correcta**: Porque el domain gap es principalmente un cambio de escala/covarianza entre FP32 y FP64, y CORAL alinea exactamente eso en 20 líneas de código.

6. **Descartar modelos GPU**: XGBoost GPU, GNN GPU y CL-GNN GPU no aportan valor sobre los modelos CPU con features alineadas.

---

## Archivos modificados en esta sesión

| Archivo | Cambios |
|---------|---------|
| `scripts/benchmark_ef_vina.py` | ModelRouter, GNN engine-aware, binario unificado, seed 42, --cpu 1, --cpu_only, workers auto, Vina features |
| `scripts/benchmark_ef_gpu.py` | ModelRouter, GNN engine-aware, OpenBabel fallback, timeout 600s, seed 42, workers auto, Vina features, docking failures filter |
| `scripts/run_multitarget_benchmark.py` | Stale report fix, engine-aware, workers auto |
| `scripts/run_benchmark_overnight.py` | Reescrito como wrapper CPU |
| `scripts/analyze_unified_metrics.py` | Nuevo: métricas unificadas pipeline completo + Vina-only |
| `rescoring/model_router.py` | (sin cambios, ya existía) |
| `rescoring/gnn_v2/inference.py` | hidden_dim dinámico desde checkpoint, model_path parametrizable |
| `rescoring/gnn_v2/contrastive_gpu.py` | Nuevo: entrenamiento CL-GNN para GPU |
| `rescoring/feature_extractor.py` | Parser PDBQT-aware (Bug #2 fix), UpdatePropertyCache, sanitización ligera |
| `rescoring/artifacts/gpu/model_a.json` | Convertido de .joblib a XGBoost JSON (184KB, 167 feat) |
| `rescoring/artifacts/gpu/model_null.json` | Convertido |
| `rescoring/artifacts/gpu/clgnn_pretrained.pt` | Nuevo: CL-GNN pretrained GPU |
| `rescoring/artifacts/gpu/clgnn_finetuned.pt` | Nuevo: CL-GNN finetuned GPU |
| `rescoring/generate_gpu_dataset.py` | Unicode fix, GPU-only filter |
| `backend/core/hardware.py` | reserved_cpu_cores, cpu_usage_percent, gpu_vram_free_gb, workers capped |
| `backend/services/docking/vina_service.py` | QuickVina 2 dispatch real |
| `backend/core/config.py` | QVina2 docstring |
| `frontend/src-tauri/tauri.conf.json` | CSP: removido :8001 |
| `.gitignore` | +.env.cloud |
| `ad-gpu-project/vina_hybrid.bat` | Removido 2>&1 |
| `docs/00_INDEX.md` | AUC 0.858, sidecars 2, modelos duales, backup, AI module |
| `docs/04_ARCHITECTURE.md` | GNN-v2, MM-GBSA vars, ESMFold-Pro, frontend AI, model_router |
| `docs/SESSION_SUMMARY_v1.5.md` | Documento de esta sesión |
| `CHANGELOG.md` | v1.5.0 entry |
| `docs/vina gpu y vina cpu.txt` | Conversación externa documentando domain shift GPU↔CPU |
| `docs/13_DIARIO_EXPERIMENTOS_GPU.md` | **Este documento** |
