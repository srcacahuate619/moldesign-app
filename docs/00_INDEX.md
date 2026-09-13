> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# MolDesign AI v1.7 — Documentacion del Proyecto

> Ultima actualizacion: Julio 2026
>
> **v1.7**: 98 rutas backend, 9 nuevos endpoints (DiffDock, ColabFold, Protein Surgery), frontend-backend integration completa, 35+ endpoints conectados

## Convenciones del Proyecto

- **Idioma oficial**: Español técnico para documentación y comentarios de código.
- **Nombres de variables, funciones, clases**: inglés (convención estándar de programación).
- **Commits**: conventional commits en español (`feat:`, `fix:`, `docs:`, `refactor:`).

## Tabla de Contenidos

| Documento | Contenido |
|-----------|-----------|
| [00_INDEX.md](00_INDEX.md) | Este documento — vision general, arquitectura, tech stack, calidad |
| [01_PIPELINE.md](01_PIPELINE.md) | Pipeline cientifico completo con diagramas Mermaid |
| [02_DESKTOP.md](02_DESKTOP.md) | Adaptacion cloud→desktop: sidecars, GPU, Tauri, actualizaciones |
| [03_API.md](03_API.md) | Referencia completa de 35+ endpoints REST |
| [04_ARCHITECTURE.md](04_ARCHITECTURE.md) | Organizacion del codigo, cada archivo explicado |
| [05_CLOUD_DEPLOY.md](05_CLOUD_DEPLOY.md) | Cloud Run deployment guide (GCP) |
| [**06_FAMILY_RETRAINING.md**](06_FAMILY_RETRAINING.md) | **Plan: Reentrenamiento XGBoost por familia estructural + Resultados** |
| [**07_SPEARMAN_BENCHMARK_LOG.md**](07_SPEARMAN_BENCHMARK_LOG.md) | **Bitácora completa de benchmarks Spearman: experimentos, errores, soluciones** |
| [**08_SCIENTIFIC_VALIDATION.md**](08_SCIENTIFIC_VALIDATION.md) | **Validacion cientifica: ProLIF, ablation, SHAP, discrepancias** |
| [**SESSION_SUMMARY_v1.3.md**](SESSION_SUMMARY_v1.3.md) | **Resumen completo: arquitectura, retrain, optimizaciones, metricas** |
| [**SESSION_SUMMARY_v1.5.md**](SESSION_SUMMARY_v1.5.md) | **Resumen completo v1.5: auditorias, features, Steam prep, checklist** |
| [**SESSION_SUMMARY_v1.7.md**](SESSION_SUMMARY_v1.7.md) | **Resumen completo v1.7: 8 fixes de pipeline, MM-GBSA real, AutoRecalibrator conectado, Early Exit** |
| [**17_STEAM_DEPLOYMENT.md**](17_STEAM_DEPLOYMENT.md) | **Guia de despliegue Steam: billing, Cloud, MSVC, code signing** |
| **TOS_PRIVACY.md** — *no se distribuye* | Terminos del servicio EN LA NUBE, que dejo de existir. La politica vigente es [PRIVACY.md](../PRIVACY.md) |
| [auditorias/auditoria_empaquetado_desktop.md](auditorias/auditoria_empaquetado_desktop.md) | Auditoria de produccion + estrategia de empaquetado [SUPERSEDED] |
| [Plan_Multiplataforma.md](Plan_Multiplataforma.md) | Roadmap multiplataforma (Steam, Android, Web) |
| [**09_PACKAGING_STRATEGY.md**](09_PACKAGING_STRATEGY.md) | **Estrategia de empaquetado desktop: opciones, pesos, recomendacion** |
| [**10_VINA_GPU_HYBRID.md**](10_VINA_GPU_HYBRID.md) | **Modulo GPU: Vina-GPU 2.1 + pipeline hibrido GPU->CPU (30x speedup) — RETIRADO v1.5** |
| [**14_TARGET_LIBRARY.md**](14_TARGET_LIBRARY.md) | **Libreria de targets offline: 273 validados en 20 areas terapeuticas** |
| [**15_BATCH_SCREENING.md**](15_BATCH_SCREENING.md) | **Batch virtual screening: multi-target, early exit, EF metrics** |
| [**16_AUDIT_FIXES.md**](16_AUDIT_FIXES.md) | **Registro de bugs corregidos: 3 auditorias, 24 hallazgos mitigados** |
| [**Interprete_IA.md**](Interprete_IA.md) | **Modulo de IA Local: Qwen2.5-1.5B + MolNeuro + MolChat + 20 tools** |
| [**MolGraph.md**](MolGraph.md) | **Knowledge Graph Quimico: nodos + aristas + fingerprints + SAR engine** |
| [**plan_early_exit.md**](plan_early_exit.md) | **Plan: Early Exit con MolGraph (pre-filtro, 0% falsos negativos)** |
| [**campana_multitarget.md**](campana_multitarget.md) | **Plan: validacion multi-target (GPCR+Kinase+Protease), MolGraph pre-poblado, Idea B** |
| [**metricas_experimentales.md**](metricas_experimentales.md) | **Metricas experimentales: EF benchmark, comparativas, GNN+MolGraph ideas** |
| **datos_para_paper.md** — *no se distribuye* | Datos compilados para un manuscrito sin enviar. Ver la tabla de [INDEX.md](INDEX.md) |
| [**gnn_v2_arquitectura.md**](gnn_v2_arquitectura.md) | **GNN-v2: auditoria de datos, arquitectura, plan de implementacion** |
| [**SESSION_SUMMARY_v1.4.md**](SESSION_SUMMARY_v1.4.md) | **Resumen de sesion v1.4: bugs, errores, aprendizajes, dead ends** |
| [**10_VINA_GPU_HYBRID.md**](10_VINA_GPU_HYBRID.md) | **Modulo GPU: Vina-GPU 2.1 + pipeline hibrido GPU->CPU (30x speedup)** |
| [**11_GPU_BENCHMARK_RESULTS.md**](11_GPU_BENCHMARK_RESULTS.md) | **Resultados GPU: EF 2.24x (vs 1.1x CPU), AUC 0.95, 22x speedup** |
| **12_BENCHMARK_SETUP.md** — *no existe* | Entrada heredada del indice de julio: el documento nunca llego a escribirse. El setup real esta en [11_GPU_BENCHMARK_RESULTS.md](11_GPU_BENCHMARK_RESULTS.md) y [13_DIARIO_EXPERIMENTOS_GPU.md](13_DIARIO_EXPERIMENTOS_GPU.md) |
| [**13_DIARIO_EXPERIMENTOS_GPU.md**](13_DIARIO_EXPERIMENTOS_GPU.md) | **Diario completo: bugs, hipótesis descartadas, soluciones — el camino al enfoque CORAL** |
| [**SESSION_SUMMARY_v1.5.md**](SESSION_SUMMARY_v1.5.md) | **Resumen v1.5: GPU benchmark fixes, workers adaptativos, ModelRouter** |
| [**SESSION_SUMMARY_v1.6.md**](SESSION_SUMMARY_v1.6.md) | **Resumen v1.6: Pipeline revival, 5 bugs fixeados, 8 targets validados, sistema dinámico de stacking** |
| [**SESSION_SUMMARY_v1.7.md**](SESSION_SUMMARY_v1.7.md) | **Resumen v1.7: 8 fixes pipeline, MM-GBSA real, AutoRecalibrator, Early Exit, logger dual** |
| — | MolNeuro Agent Architecture (futuro v1.5+) — Planner → Obrero → Reviewer |
| [adr/](adr/) | Architecture Decision Records |

---

## Novedades v1.0 (Julio 2026)

### Pipeline Cientifico

- **6 reglas de drug-likeness**: Lipinski, Veber, Ghose, Egan, Muegge, Fsp3
- **PAINS filter**: 480 patrones RDKit (Baell & Holloway 2010)
- **ADMET-AI real**: predicciones de toxicidad con Chemprop + TabPFN (no mock)
- **ADMET toggle**: el usuario puede desactivarlo para evaluaciones rapidas (~70s vs ~210s)
- **ADMET cache**: mismo SMILES = resultado instantaneo (3s en vez de 140s)
- **Vina cache**: mismo SMILES + target = resultado instantaneo
- **Selectividad multi-target**: 5 anti-targets default + subida por usuario
- **MM-GBSA rescoring**: OpenMM con GPU auto-detect (CUDA/OpenCL/CPU)
- **SAR analysis**: tabla comparativa de analogos con delta vs baseline
- **DGL → PyG port**: GNN RTMScore ahora usa PyTorch Geometric (GPU nativa en Windows sin conda)
- **Modelos XGBoost por familia**: 5 modelos especificos (GPCR, kinase, protease, nuclear_receptor, soluble_enzyme) + universal fallback
- **Family classifier**: 865 PDBbind IDs clasificados en 6 familias via RCSB GraphQL API
- **Spearman benchmark**: 911 moleculas 5-HT1A — baseline Vina ρ=-0.65, XGBoost ρ=-0.05 (antes del fix)
- **Quality Gate**: modelo familiar solo se usa si Spearman CV ≥ 0.5 y p < 0.05 (evita usar modelos debiles)
- **ECIF Features**: reduccion de 176→68 features. ECIF (56) + Vina (4) + 1D/2D (8). Menos overfitting.
- **Vina Features Reales**: 540/865 complejos PDBbind re-dockeados. Features Vina no-cero en training.
- **Delta-Learning**: modelo entrena en pKi - Vina_pKi. Reconstruccion en inferencia.
- **Clasificador Binario**: XGBoost classifier pKi>7 con ROC AUC 0.858. Integrado en /rescore.
- **QuickVina 2**: cableado `docking_engine` en vina_service.py. Modo rapido exhaustiveness=4 (~3x).
- **Interaction Fingerprints**: conteos ProLIF expuestos en /rescore para consenso scoring.

### Infraestructura

- **Tauri v2 desktop**: ventana nativa Windows con 2 sidecars Python (v1.3: rescoring unificado in-process)
- **Hardware detection**: CPU/RAM/GPU con recomendaciones de workers
- **Batch screening**: CSV/Excel/SDF, hasta 500 moleculas, Excel ranqueado
- **Auto-updater**: Tauri updater plugin + GitHub Actions CI/CD
- **Build dual**: Next.js cloud (SSR) + desktop (static export)

### Codigo

- **Blockchain refactor**: Solana certifier async-safe, lazy RPC init, retry con backoff
- **bcrypt passwords**: migracion automatica desde PBKDF2 legacy
- **Cache LRU**: limite 10000 items con eviction en modo desktop
- **Auditoria de codigo**: 25 issues encontrados, 12 corregidos (0 criticos restantes)
- **Sin passwords hardcodeados**: `scratch/` eliminado, `secret_key` auto-generado

---

## Novedades v1.6 (Julio 11, 2026)

### Pipeline Revival & Dynamic Stacking System

- **8 bugs críticos fixeados**: box_size=None, CL-GNN no ejecutado, stacking weights incorrectos, EXHAUSTIVENESS hardcodeado, args global, PDBQT ROOT tags, multi-cadena sin trimming, centros hardcodeados incorrectos
- **8 targets validados en 6 familias**: GPCR(32.64x), Kinase(28.56x), Protease(24.21x), Nuclear Rec.(34.85x), Soluble Enz.x2, Metaloenz., Phosphodiest.
- **EF@1% promedio 5 targets funcionales: 28.89x** — comparable a Glide XP de Schrödinger ($50K/año)
- **Sistema dinámico de stacking**: pesos cargados desde `stacking_weights.json`, no hardcodeados
- **Auto-optimización post-benchmark**: grid search automático actualiza JSON (≥500 moléculas)
- **7 familias con pesos calibrados**: incluyendo metaloenzyme (vina=0.0, clgnn=0.9 — CL-GNN domina donde Vina falla con Zn²⁺)
- **`molchamb_sign` por familia**: HIV usa -1.0 (MolChamb invertido para proteasas)
- **Auto-detección de familia**: `structural_family.py` clasifica PDBs automáticamente
- **Protein surgery integrado**: centro dinámico + caja precisa para targets con `ligand_mol2`
- **MM-GBSA vía MolChamb v2**: GFN2-xTB charges + OpenMM OBC2 (limitado a C,H,O,N,S,P sin GAFF2)
- **GAFF2 bloqueado en Python 3.14**: `openff-toolkit` no compila. MM-GBSA para halogenados pendiente.
- **Pipeline universal**: `_get_target_path()` funciona para cualquier PDB ID sin configuracion manual (~390 PDBs auto-descubiertos en `data/targets/` y `data/target_library/`)
- **Auto-descubrimiento de PDB**: busca en 94 PDBs en `targets/` + ~298 PDBs en `target_library/` (20 areas terapeuticas) + descarga de RCSB
- **Chain trimming automatico**: detecta cadena dominante y extrae solo el sitio activo (reduce receptor 3-10x)
- **Centros curados automaticos**: `curated_targets.csv` (80 targets) sobreescribe cualquier centro hardcodeado incorrecto
- **5 centros corregidos**: 7E2Y (off 20A), 3PP0 (off 20A), 3ERT (off 3A), 5Z2R (off 42A), 6X1A (off 130A)
- **Temp dir en D:\\moldesign-app\\tmp**: no más basura en disco C

### Documentación
- [SESSION_SUMMARY_v1.6.md](SESSION_SUMMARY_v1.6.md) — **Documento completo de la sesión**: bugs, resultados, arquitectura, lecciones, próximos pasos
- [SESSION_SUMMARY_v1.7.md](SESSION_SUMMARY_v1.7.md) — **8 fixes del pipeline**: MM-GBSA real conectado, Early Exit en queue_handler, AutoRecalibrator integrado, GNN checkpoint defensivo, metal_features, logger dual

---

## Arquitectura de Alto Nivel

```
┌──────────────────────────────────────────────────────────────────┐
│                    MolDesign AI Desktop v1.0                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                 Tauri Shell (Rust)                        │   │
│  │  ┌────────────────────────────────────────────────────┐  │   │
│  │  │         Frontend (Next.js → HTML estatico)          │  │   │
│  │  │  • Modo EDU: simplificado, interpretado             │  │   │
│  │  │  • Modo PRO: todos los parametros, 100% transparente│  │   │
│  │  │  • Batch screening, SAR table, DrugLikeness panel   │  │   │
│  │  │  • Selector motor docking (Vina/QuickVina2/FP16)   │  │   │
│  │  │  • Ketcher editor + Molstar 3D viewer              │  │   │
│  │  └────────────────────────────────────────────────────┘  │   │
│  │                                                           │   │
│  │  Lanza 2 sidecars al iniciar (v1.3: rescoring unificado):  │   │
│  │  ┌──────────────────────┐ ┌──────────────────────┐        │   │
│  │  │ Backend + Rescoring  │ │ ESMFold :8100        │        │   │
│  │  │     :8000            │ │ FastAPI               │        │   │
│  │  │ FastAPI + XGBoost    │ │ + PyTorch             │        │   │
│  │  │ + Vina + ProLIF      │ │ + stub/real           │        │   │
│  │  │ + ADMET-AI + SHAP    │ │                       │        │   │
│  │  │ + MM-GBSA + PAINS    │ │                       │        │   │
│  │  │ + SQLite              │ │                       │        │   │
│  │  └──────────────────────┘ └──────────────────────┘        │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  Storage: ~/MolDesign/data/     Cache: LRU in-memory (10K max)   │
│  DB: SQLite                     Tasks: ThreadPoolExecutor (2-6)  │
│  Auth: JWT + bcrypt             GPU: CUDA (PyTorch) + OpenCL     │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack (actualizado)

### Backend (Python 3.11+)

| Componente | Tecnologia | Estado |
|-----------|-----------|--------|
| API | FastAPI + Pydantic v2 | ✅ |
| Quimioinformatica | RDKit 2025 | ✅ |
| PAINS | FilterCatalog (480 patrones) | ✅ v1.0 |
| Drug-likeness | 6 reglas (Lipinski, Veber, Ghose, Egan, Muegge, Fsp3) | ✅ v1.0 |
| Docking | AutoDock Vina 1.2.5 | ✅ |
| Rescoring | XGBoost 2.1 (por familia) + RTMScore GNN (PyG) | ✅ |
| ADMET | ADMET-AI 2.0 + TabPFN 8.0 (con cache) | ✅ v1.0 |
| Selectividad | 5 anti-targets default + custom | ✅ v1.0 |
| MM-GBSA | OpenMM 8.5 + AMBER14SB (GPU) | ✅ v1.0 |
| SAR | Tabla comparativa de analogos | ✅ v1.0 |
| Batch | CSV/Excel/SDF, hasta 500 mols | ✅ v1.0 |
| Auth | JWT + bcrypt (cost=12) | ✅ v1.0 |
| Blockchain | Solana devnet Memo Program (CC0) | ✅ v1.0 |
| DB Local | SQLite + aiosqlite | ✅ |
| Cache Local | LRU in-memory (10K items) | ✅ v1.0 |
| Storage Local | Disco (~/MolDesign/data/) | ✅ |

### Frontend (TypeScript)

| Componente | Tecnologia | Estado |
|-----------|-----------|--------|
| Framework | Next.js 14 + React 18 | ✅ |
| UI | Tailwind CSS 4 + Framer Motion | ✅ |
| Editor | Ketcher 3.x | ✅ |
| 3D | Molstar 5.x + Three.js | ✅ |
| Desktop | Tauri 2.x (Rust) | ✅ v1.0 |
| Batch | Upload + progress + Excel download | ✅ v1.0 |
| SAR | Tabla comparativa con delta | ✅ v1.0 |
| PRO Panel | Workers, toggles, GPU, ADMET | ✅ v1.0 |
| Docking Engine | Selector Vina/QuickVina2/FP16 | ✅ v1.0 |
| Drug-likeness | Panel con 6 reglas + PAINS | ✅ v1.0 |

---

## Calidad de Codigo

### Auditoria completada (Julio 2026): 25 issues → 12 corregidos

| Severidad | Encontrados | Corregidos |
|-----------|------------|------------|
| 🔴 Criticos | 5 | 5 ✅ |
| 🟠 Altos | 5 | 5 ✅ |
| 🟡 Medios | 11 | 2 (resto requiere decision de producto) |
| 🟢 Bajos | 4 | 0 (code smells no bloqueantes) |

### Issues corregidos:
- Hardcoded passwords en `scratch/` → eliminado
- `_get_best_platform()` variable scoping bug → OpenCL ahora detecta correctamente
- `secret_key` default inseguro → auto-genera `os.urandom(32).hex()`
- ADMET mock retornaba datos falsos → ahora retorna `None`
- Dead code duplicado en `blood_viability.py` → eliminado
- `FileNotFoundInStorage` crasheaba con `detail=` → acepta parametro
- `certify_molecule_sync` con `asyncio.run()` → refactor completo async-safe
- PBKDF2 → bcrypt con auto-migracion
- Cache in-memory sin limite → LRU 10K items
- `_check_fragments` duplicado → eliminado
- Hardcoded `/opt/conda/` paths → dinamicos
- `sascorer` path hardcodeado → busca en multiples ubicaciones

### 0 issues criticos restantes.

---

## Novedades v1.1 (Julio 2026)

### Comunidad Global
- **Community targets**: conectar con la nube para descargar PDBs compartidos
- **Leaderboard**: top scores globales por target
- **Share**: publicar targets locales a la comunidad con atribucion @username
- **Login cloud opcional**: solo necesario para atribucion de autoria

### Experiencia Desktop
- **Auto-login**: el usuario nunca ve pantalla de login en desktop
- **Sin limites**: 0 restricciones de evaluaciones en modo local
- **GPU detection**: retry 10x con backoff hasta que el backend responde
- **Logos optimizados**: 282KB → 4KB (-98%), carga instantanea

### Rendimiento
- **ADMET toggle**: evaluacion sin ADMET = ~70s (vs ~210s con ADMET)
- **ADMET cache**: mismo SMILES = 3s en vez de 140s
- **Vina cache**: mismo SMILES + target = resultado instantaneo
- **Vina exhaust=8**: sweet spot validado. >8 no mejora ranking
- **Benchmark real**: Ryzen 5 5500 + RTX 1660 SUPER

### Frontend Polish
- **ScoreGauge**: medidor circular SVG animado en modo EDU
- **Skeleton**: loading states con animacion en evaluacion
- **ErrorBoundary**: wrapper global con retry button
- **Animaciones**: definidas en Tailwind v4 nativo (sin plugins)
- **Dark mode**: forzado para app desktop

### Pipeline Cientifico (Fixes Spearman v1.1)
- **Fix #1 — Clasificador como metrica primaria**: Abandonamos Spearman como objetivo.
  Adoptamos Enrichment Factor (EF@1%/5%/10%) con decoys DUD-E. Clasificador (AUC 0.858)
  es el motor de cribado. Regresor XGBoost pasa a ser informativo.
- **Fix #2 — Composite Score desacoplado**: `total_score` ahora refleja solo afinidad
  (Vina + GNN + especificidad). ADME, Drug-likeness, SA Score y Blood Viability se
  exponen como flags independientes (no modifican ranking).
- **Fix #3 — Interaction Fingerprints visuales**: Los 9 conteos ProLIF se removieron
  de las features ML (ρ=-0.035 en 5-HT1A). Siguen en `features_used` para frontend 3D.
  ALL_FEATURES pasó de 176→167.
- **Fix #4 — PDBFixer para MM-GBSA**: Integrado PDBFixer antes de OpenMM. Resuelve
  crasheo por H faltantes en PDBs cristalograficos (ej: 7E2Y).
- **Fix #5 — DUD-E Decoys**: Script `download_decoys_and_calculate_ef.py` para
  calcular EF real con ~3000 decoys + 99 activos ChEMBL.

## Novedades v1.2 (Julio 2026)

### 🧬 Visualización de Interacciones en Molstar
- **ProLIF en el visor 3D**: Las interacciones detectadas por ProLIF (puentes H,
  hidrofóbicas, π-stacking, puentes salinos, π-catión, halógeno) ahora se renderizan
  como esferas coloreadas en el midpoint de cada interacción dentro de Molstar.
- **Coordenadas 3D en API**: El endpoint `GET /evaluation/interactions/{id}` ahora
  incluye `ligand_coords` y `protein_coords` (x,y,z) para cada interacción, permitiendo
  renderizado preciso en el visor.
- **Leyenda integrada**: El viewer PRO muestra una leyenda de colores para cada tipo
  de interacción (O=rojo puente H, C=gris hidrofóbico, N=azul π-stacking, S=amarillo
  salino, F=verde π-catión).
- **Sin esfuerzo extra**: Las interacciones se cargan automáticamente cuando el viewer
  recibe un `moleculeId`. No requiere clicks extra del usuario.

### 🔍 Búsqueda de Targets por Nombre (RCSB PDB)
- **Nuevo endpoint `POST /targets/resolve-name`**: Busca estructuras experimentales en
  RCSB PDB por nombre de proteína usando RCSB Search API v2 + Data API. Retorna
  resultados ordenados por resolución.
- **Nueva pestaña "Buscar en RCSB"**: En el selector de receptores, los usuarios pueden
  escribir "EGFR", "CDK4", "5-HT1A", etc. y obtener una lista de PDB IDs para
  seleccionar sin tener que memorizar códigos.
- **Auto-descarga**: Al seleccionar un resultado de RCSB, el backend descarga, cura y
  prepara el PDB automáticamente a través del pipeline de ingesta existente.
- **Backend**: `utils/file_handlers.py` — funciones `search_rcsb_by_name()` y
  `_fetch_rcsb_entry_detail()` que consultan las APIs REST de RCSB.

## Novedades v1.3 (Julio 2026)

### ⚡ Unificación Backend + Rescoring (sin sidecar separado)

- **1 solo proceso Python**: El rescoring (XGBoost + ProLIF + SHAP) ahora corre
  in-process dentro del backend en `:8000`. Se eliminó el sidecar separado en `:8001`.
  Arquitectura: `backend/services/rescoring_service.py` + `api/routers/rescoring.py`.
- **Ahorro RAM masivo**: De ~2.4 GB idle (2 procesos) a **~600 MB idle** (1 proceso).
  rdkit, numpy, scipy, pandas ya no se duplican. Medido real: 317 MB con todos los
  imports + modelos XGBoost cargados.
- **Compatibilidad verificada**: El rescoring funciona en Python 3.11, 3.12 y 3.14.
  DGL ya no es necesario (portado a PyG para inferencia). ODDT reemplazado por ProLIF.
- **Nuevo endpoint `GET /rescoring/health`**: Health check del modulo unificado.
- **Nuevo endpoint `GET /rescoring/ram`**: Medición de RAM en tiempo real del proceso.
- **Bridge directo**: `rescoring_client.py` ahora llama a `model_manager.predict()` 
  como función directa (sin HTTP, sin serialización) cuando APP_MODE=DESKTOP.
  HTTP al sidecar sigue como fallback para CLOUD.

### ⏳ ESMFold On-Demand

- **Modelo lazy**: El predictor ESMFold ya NO carga el modelo al arrancar. Se crea
  el predictor vacío y `load()` (torch + transformers + pesos ~3 GB) se difiere al
  primer request `POST /predict`. Ahorro: ~3.7 GB RAM en idle.
- **Primer predict más lento**: 30-90s extra en el primer /predict (carga del modelo).
  Predicts subsiguientes son instantáneos (modelo en memoria).

### 📊 RAM por Escenario

| Escenario | RAM |
|---|---|
| Idle (small mols, sin GNN) | **~600 MB** |
| Idle + GNN (torch cargado) | **~1.3 GB** |
| Docking activo | **~800 MB** |
| + ESMFold real (on-demand) | **+3.5 GB temporal** |

### ⚡ Optimizaciones de Rendimiento

- **skip_prolif en inferencia ML**: `feature_extractor.py` ahora acepta `skip_prolif=True`
  en `extract_from_pose()` para saltar ProLIF durante rescoring. Las features de
  interaccion ProLIF ya no son features de ML (fix #3: SHAP < 0.003, ρ=-0.035 en GPCR).
  Ahorro: ~2s por molecula. ProLIF se sigue ejecutando para el visor 3D en el endpoint
  `/evaluation/interactions/{id}`.
- **Batch XGBoost inference**: `model_manager.predict_batch()` + `predict_batch_rescore()`
  procesan N moleculas en una sola llamada XGBoost vectorizada. Speedup: 10-50x en
  cribado masivo (≥10 moleculas).
- **Feature cache LRU**: `model_manager._feature_cache` cachea features por
  `(smiles, target_pdb)`. 256 entradas max, eviction FIFO. Re-evaluacion instantanea.

### 🧪 Validacion Cientifica

- **Documento dedicado**: [08_SCIENTIFIC_VALIDATION.md](08_SCIENTIFIC_VALIDATION.md)
- **ProLIF analisis**: SHAP importance de features ProLIF < 0.003. ECIF-only Spearman
  0.68 > ALL features Spearman 0.60 en ablation. Interaction score ρ=-0.035 en 5-HT1A.
- **Discrepancias detectadas**: 8 issues identificados (4 bloqueantes). Feature count
  mismatch (167 vs 176), benchmark solo 5-HT1A, PDBbind version sin documentar,
  metricas de validacion confundidas con test.
- **Plan de resolucion**: Retrain con 167 features, benchmark multi-target (≥5 targets,
  ≥3 familias), documentar contexto de entrenamiento.

### Seguridad
- **bcrypt**: cost=12, auto-migracion de hashes PBKDF2 legacy
- **JWT key**: auto-generada en desktop (sin default inseguro)
- **0 passwords hardcodeados**: scratch/ eliminado
- **Blockchain refactor**: async-safe, lazy RPC, retry backoff

---

## Novedades v1.4 (Julio 2026)

### 🧠 MolNeuro — Arquitectura Neuronal Local

- **Context Compression**: comprime historial viejo, mantiene últimos 6-12 msgs. Ahorra ~6K tokens
- **Engram Memory (FTS5)**: búsqueda full-text en historial de chat + evaluaciones
- **Synaptic Pruning**: elimina saludos/ruido del contexto
- **Attention RAS**: re-ordena mensajes por relevancia a la pregunta actual
- **Sleep Consolidation**: comprime sesiones enteras en resúmenes estructurados
- **Limbic System**: XP, nivel (Recién Nacido→Arquitecto), mood, preferencias
- **Deterministic Router**: clasifica 6 intenciones (tool, memory, complex, complex_chemistry, factual, general) sin tokens del LLM
- **Dynamic System Prompt**: adaptativo según etapa + intención + herramientas + memoria
- **Hallucination Guard**: regex numérico cross-check vs datos reales. Si difiere >10% → corrección
- **Factual Mode**: ejecuta herramienta ANTES del LLM para queries numéricas. 0% alucinación
- **ReAct Light**: tool interceptor recursivo (max 2 rondas, 3 LLM calls)

### 🤖 MolChat v1.4 — Chatbot Inteligente

- **Qwen2.5-1.5B Q4_K_M**: 1.04 GB, 32K nativo, 60-90 tok/s GPU, Apache 2.0
- **Speed/Deep toggle**: [Faster] 256 tok/8192 ctx vs [Deep] 1024 tok/16384 ctx
- **5 providers implementados**: Local (Qwen2.5 GGUF), Ollama, Claude, Gemini, OpenAI/Groq — con `ProviderRegistry` y fallback automático
- **Model Browser**: búsqueda en HuggingFace + descarga de GGUF + cuantización dinámica
- **Voice input**: local (Whisper tiny, 75MB) + Web Speech fallback
- **Historial persistente**: conversaciones en SQLite, sobreviven restarts
- **molecule_context**: conexión bidireccional entre página de evaluación y MolChat
- **ProviderBadge**: GPU/CPU/Cloud + VRAM/RAM en vivo (polling 8s)
- **Conversaciones**: sidebar con historial, carga desde DB, búsqueda FTS5

### 🏗️ Arquitectura del Módulo AI

- **5 providers** en `services/ai/providers/`: `local_llm_provider.py`, `ollama_provider.py`, `claude_provider.py`, `gemini_provider.py`, `openai_provider.py` + `registry.py` para dispatch unificado
- **20 herramientas registradas** en 6 módulos: `rdkit_tools` (4), `docking_tools` (2), `admet_tools` (1), `web_tools` (4), `analog_tools` (2), `molgraph_tool` (7)
- **Tool registry**: `tool_registry.py` centraliza registro y dispatch. Tool cache en SQLite (`tool_cache.py`) → 0ms en consultas repetidas
- **Speech-to-text**: `speech_to_text.py` con faster-whisper (tiny, 75MB, local)
- **Model registry**: `model_registry.py` — versionado de modelos GGUF, auto-descarga desde HuggingFace
- **Resource manager**: `resource_manager.py` — monitoreo de VRAM/RAM, GPU/CPU switching dinámico
- **Startup detection**: `startup_detection.py` — chequeo de recursos al arrancar el backend
- Todos los módulos bajo `backend/services/ai/` (~30 archivos)

### 🧬 MolGraph — Knowledge Graph Químico (Tecnología Propia)

- **7 herramientas MolGraph**: query, neighbors, similar, impact, scaffolds, druglikeness, admet (+ 13 herramientas adicionales en el ecosistema: RDKit, docking, web, analog, ADMET)
- **Nodos**: moléculas (fingerprints Morgan 2048-bit), targets, evaluaciones
- **Aristas**: docking, same_target, modified_from
- **SAR Engine**: trackea qué modificaciones mejoraron la afinidad (delta_affinity)
- **Scaffold Auto-Detection**: clustering por Tanimoto de series químicas
- **Drug-Likeness Stats**: estadísticas Lipinski/Veber en tiempo real
- **ADMET Correlation**: correlaciona LogP con predicciones BBB/HIA
- **100% offline**: SQLite + FTS5, sin APIs externas

### 🔧 Pipeline Cientifico

- **20 herramientas totales** (16 offline + 4 online): `rdkit_tools` (4), `docking_tools` (2), `admet_tools` (1), `analog_tools` (2), `web_tools` (4), `molgraph_tool` (7)
- **PubChem RAG**: auto-lookup de 16 fármacos conocidos + cache offline
- **ChEMBL RAG**: bioactividad (IC50, Ki, targets) + cache offline
- **Tool cache**: resultados RDKit por SMILES en SQLite → 0ms en consultas repetidas
- **Prompt farmacología**: system prompt enriquecido con conocimiento PK/PD

### ⚡ Optimizaciones de Latencia

- **embedding=False**: -50% latencia (FTS5 reemplaza embeddings)
- **n_ctx=16384 default**: 4x más rápido que 32768 (configurable)
- **Prefix caching automático**: system prompt estable + split fijo/variable
- **max_tokens dinámico**: 128-256 en speed, 1024-2048 en deep
- **Modelo 3x más chico**: Qwen2.5 (1.04 GB) vs Phi-3.5 (2.5 GB)
- **91s → 13s** primer mensaje (7x). **289s → 7.7s** mensajes subsiguientes (37x)

### 🚫 MTP / Flash Attention — Bloqueado

- **MTP (Speculative Decoding)**: Qwen0.5B descargado (491 MB). `ChemistryDraftModel` listo. Bloqueado por `llama-cpp-python 0.3.32` (broadcast error CUDA). Versión 0.3.35+ requerida pero no disponible para Python 3.14 en pip.
- **Flash Attention**: mismo bloqueo.

### 📦 Infraestructura

- **CodeGraph v1.2**: 58,914 nodos indexados en 65s. Herramienta de desarrollo (no producto).
- **Backup**: `backup_molchat_v1.4/` (pre-antigravity, con `restore.ps1`) + `backup_20260706_175323/` (pre-GPU pipeline)
- **Stress tests**: 3 scripts en `scripts/` (stress, online RAG, seed MolGraph)

---

## Novedades v1.5 — Módulo GPU (Julio 2026)

### ⚡ Vina-GPU Hybrid Pipeline

- **Vina-GPU 2.1 compilado nativo Windows**: binario unificado con 3 modos (`--cpu_only`, `--refine`, GPU default)
- **`--cpu_only` idéntico a vina.exe**: mismo `do_search()`, mismo `eval_adjusted()` fp64. Drop-in replacement.
- **`--save-pose` + `--refine`**: GPU search (2s) → guarda mejor pose → CPU refine fp64 (0.06s). 32× speedup.
- **Orchestrator 100% confiable**: GPU search + CPU refine + fallback automático a Vina CPU si GPU falla.
- **Batch dock GPU**: `--ligand_directory` de Vina-GPU procesa 2000 moléculas en ~10 min (vs 33h CPU).
- **Pipeline multi-pose**: 5 poses GPU → 5× CPU `--local_only` en paralelo → mejor score fp64.
- **Toolchain MSYS2/MinGW-w64**: GCC 16.1, Boost 1.91, OpenCL 3.0. Todo nativo Windows.
- **Delta validado**: GPU vs CPU Δ=0.02-0.9 kcal/mol en factor_xa. Ranking preservado.

### 🏆 Resultados GPU Benchmark (validados)

- **Factor Xa (200 mols)**: EF@1%=**2.24x** vs CPU 1.1x (+104%). AUC=**0.954** vs CPU 0.933. Tiempo: **10 min** (GPU) vs 35 min (CPU).
- **6 targets** con 2000+ moléculas NUNCA dockeadas completas — con GPU son viables en **9 horas** vs **8 días** CPU.
- **Orchestrator 100% confiable**: 10/10 moléculas completadas, 0 errores, fallback automático a CPU.
- **Binario `--cpu_only` idéntico a vina.exe**: mismo `do_search()`, mismo `eval_adjusted()`, drop-in replacement.

Ver reporte completo: [11_GPU_BENCHMARK_RESULTS.md](11_GPU_BENCHMARK_RESULTS.md)

### 📊 Impacto en Benchmarks

| Métrica | Antes (CPU) | Ahora (GPU) |
|---------|:----------:|:----------:|
| Tiempo por molécula | ~60s | **~2s** |
| 2,000 mols target | ~33h | **~1h** |
| 10 targets | ~14 días | **~22h** |

### 🧠 Modelos Duales: CPU (FP64) vs GPU (FP32)

Se entrenaron **dos familias completas de modelos ML** para reflejar las diferencias entre Vina-CPU (fp64) y Vina-GPU (fp32):

| Componente | CPU (`artifacts/`) | GPU (`artifacts/gpu/`) |
|-----------|:------------------:|:---------------------:|
| **XGBoost model_a** | `model_a.joblib` (pdbind v2020) | `model_a.joblib` (Spearman 0.55) |
| **XGBoost extended** | `model_a_extended.joblib` | `model_a_extended.joblib` |
| **XGBoost null** | `model_null.joblib` | `model_null.joblib` |
| **GNN-v2** | `gnn_v2_best.pt` | `gnn_v2_best.pt` (AUC 0.68) |
| **Entrenamiento** | `train_pipeline.py` + `train_families.py` | `train_pipeline_gpu.py` + `gnn_v2/train_gpu.py` |

**`model_router.py`**: Router hardware-aware que selecciona el set según `engine="cpu"` o `"gpu"`. Si los GPU no existen → fallback transparente a CPU. Singleton global vía `get_router()`.

### 📁 Archivos del módulo

| Archivo | Propósito |
|---------|-----------|
| `D:\ad-gpu-project\source\AutoDock-Vina-GPU-2.1\` | Source modificado (--cpu_only, --refine, --save-pose) |
| `D:\ad-gpu-project\orchestrator.py` | GPU→CPU híbrido con fallback automático |
| `D:\ad-gpu-project\batch_dock.py` | GPU batch docking via --ligand_directory |
| `D:\ad-gpu-project\vina_hybrid.py` | Drop-in Vina CPU CLI replacement |
| `rescoring/model_router.py` | Router de modelos CPU/GPU con fallback |
| `rescoring/train_pipeline_gpu.py` | Entrenamiento XGBoost con datos GPU |
| `rescoring/gnn_v2/train_gpu.py` | Entrenamiento GNN-v2 con GPU |

Ver: [10_VINA_GPU_HYBRID.md](10_VINA_GPU_HYBRID.md) — documento completo del módulo.
