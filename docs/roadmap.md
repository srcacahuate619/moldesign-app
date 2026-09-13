> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

🧬 ROADMAP MOLDESIGN AI v2 — Julio 2026
========================================
De MVP Científico a Producto Comercial
Basado en auditoría real del código (Julio 2026)


## Nota: AVANCE v1.3 (Julio 2026)

```
Estado actual del pipeline (Julio 3, 2026):

FASE A — CIERRE CIENTIFICO:         ✅ 100% completada
FASE B — COMPONENTES + AI:          ✅ 100% completada
FASE C — BENCHMARKS:                ⏳ Pendiente (cómputo pesado)
FASE 1 — EMPAQUETADO:               ⏳ Pendiente
```

**Pipeline científico completo y validado.** Ver [SESSION_SUMMARY_v1.3.md](SESSION_SUMMARY_v1.3.md) para detalle completo.

### Detalle de Fase A (completada)

| # | Tarea | Status |
|---|-------|--------|
| A.1 | MM-GBSA rewrite (real force groups) | ✅ |
| A.2 | Target curation bug fix | ✅ |
| A.3 | Receptor preparation verification | ✅ |
| A.4 | GNN torch-geometric install | ✅ |
| A.5 | TabPFN dataset + fixes | ✅ |
| A.6 | MM-GBSA ligand limitation documented | ✅ |

### Detalle de Fase B (completada)

| # | Tarea | Status | Métrica |
|---|-------|--------|---------|
| B.1 | ADMET-AI Windows fix | ✅ | num_workers=0 |
| B.2 | ADMET-AI validation | ✅ | LogS RMSE 0.92, hERG 85%, CYP 80% |
| B.3 | BBB prediction | ✅ | 91.5% en 94 fármacos (6 capas) |
| B.4 | GNN pipeline integration | ✅ | run_gnn=True |
| B.5 | ESMFold real model | ✅ | 16 GB descargado |
| B.6 | SHAP analysis | ✅ | Shell 61%, ECIF 30% |
| B.7 | Retrain XGBoost 167 feat | ✅ | Spearman +0.06 universal |
| B.8 | Training report | ✅ | PDBbind v2020, hardware, contexto |
| B.9 | AI pipeline (Local LLM) | ✅ | llama-cpp-python + Phi-3.5-mini Q4 |

### Detalle de Fase C (PENDIENTE — cómputo pesado)

| # | Benchmark | Tiempo | Script |
|---|-----------|--------|--------|
| C.1 | Benchmark multi-target (≥5 targets) | ~4h Vina | `scripts/spearman_multitarget.py` |
| C.2 | ChEMBL 5-HT1A (99 moléculas) | ~2h Vina | `scripts/spearman_5ht1a.py` |
| C.3 | DUD-E EF real (3000 decoys) | ~2h Vina | `scripts/download_decoys_and_calculate_ef.py` |
| C.4 | MM-GBSA ligand fix (GAFF2) | ~4h | `backend/scoring/mmgbsa.py` |
| C.5 | Validation report | 1h | `docs/10_FASE_C_RESULTS.md` |

### Detalle de Fase 1 (PENDIENTE — empaquetado)

| # | Tarea | Tiempo |
|---|-------|--------|
| 1.1 | Generar wheelhouse | 1h |
| 1.2 | Configurar externalBin | 1h |
| 1.3 | Empaquetar .msi (Python embed + wheels + code + models + LLM) | 4h |
| 1.4 | Test en VM Windows limpia | 2h |

**Estrategia:** Embedded Python + pip wheel cache + modelo LLM bundled.
NO conda (todo funciona via pip). Ver [09_PACKAGING_STRATEGY.md](09_PACKAGING_STRATEGY.md).

### PRÓXIMO PASO INMEDIATO

```powershell
# Fase C — Benchmark multi-target (prioridad #1)
# Requiere: Vina + receptores PDB preparados para cada target
python scripts/spearman_multitarget.py --targets all --n-mols 100
```

---

## Nota: UNIFICACION BACKEND+RESCORING COMPLETADA + OPTIMIZACIONES (v1.3, Julio 2026)

El rescoring ahora corre in-process dentro del backend. Se elimino el sidecar
separado en :8001. RAM idle bajo de ~2.4 GB a ~600 MB. Ver [02_DESKTOP.md](02_DESKTOP.md).

ESMFold ahora es on-demand: el modelo se carga en el primer /predict, no al arranque.
RAM idle bajo de ~3.7 GB a ~100 MB.

**Optimizaciones v1.3 implementadas:**
- skip_prolif=True en inferencia -- ahorra ~2s/mol (ProLIF no usado en ML)
- predict_batch() -- XGBoost vectorizado, 10-50x en cribado masivo
- Feature cache LRU 256 -- re-evaluaciones instantaneas
- Bridge directo rescoring_service.py -- sin HTTP, sin serializacion
- Medicion RAM en GET /rescoring/ram

**Discrepancias cientificas detectadas:** 8 issues (4 bloqueantes) documentados en
[08_SCIENTIFIC_VALIDATION.md](08_SCIENTIFIC_VALIDATION.md). El retrain con 167
features es el paso critico inmediato.


**Estrategia de empaquetado revisada (v2.0):** NO necesitamos conda. Todo funciona via pip.
Nueva estrategia: Embedded Python + pip wheel cache + DLC. Ver [09_PACKAGING_STRATEGY.md](09_PACKAGING_STRATEGY.md).

═══ PRE-REQUISITO: LO QUE YA ESTÁ HECHO ═══════════════════════════════

Esto YA funciona y NO hay que rehacerlo. Todo el infraestructura de
escritorio (APP_MODE, SQLite, dispatcher, storage dual) está operativa.

Infraestructura Desktop:
  ☑ APP_MODE DESKTOP/CLOUD — config.py con Literal, default DESKTOP
  ☑ db_factory.py — SQLite WAL mode (DESKTOP) / PostgreSQL (CLOUD)
  ☑ dispatcher.py — ThreadPoolExecutor 2 workers (DESKTOP) / Celery (CLOUD)
  ☑ storage.py — Disco local ~/MolDesign/data/ (DESKTOP) / MinIO S3 (CLOUD)
  ☑ hardware.py — Detección CPU, RAM, GPU (CUDA/OpenCL), OpenMM platforms
  ☑ Tauri init — src-tauri/ con lib.rs, main.rs, tauri.conf.json, updater
  ☑ next.config.js — output:'export' condicional por BUILD_TARGET=desktop
  ☑ API_URL detection — window.__TAURI__ → localhost:8000
  ☑ CI/CD — .github/workflows/desktop-release.yml (3 jobs)
  ☑ ESMFold config — esmfold_desktop_port=8100 en config.py
  ☑ Unificación rescoring — in-process (v1.3), sin sidecar :8001, ahorro ~1.8 GB RAM
  ☑ ESMFold on-demand — modelo lazy, carga en primer /predict, ahorro ~3.7 GB idle

Pipeline Científico:
  ☑ 865 feature_cache PDBbind — feature_cache_v4/ completo
  ☑ 10 modelos ML entrenados — universal + 5 familias + extended + classifier + null
  ☑ Clasificador binario — ROC AUC 0.858, integrado en /rescore
  ☑ Quality Gate — modelos familiares solo si Spearman ≥ 0.5 y p < 0.05
  ☑ PDBFixer integrado — _fix_pdb_with_pdbfixer() en mmgbsa.py (NO PROBADO E2E)
  ☑ Script DUD-E — download_decoys_and_calculate_ef.py (NO EJECUTADO con Vina real)
  ☑ QuickVina 2 mode — exhaustiveness=4, cableado en vina_service.py

Fixes Spearman v1.1 (completos):
  ☑ Fix #1 — Clasificador como métrica primaria (EF > Spearman)
  ☑ Fix #2 — Composite Score desacoplado (ADME/Lipinski no afectan ranking)
  ☑ Fix #3 — Interaction fingerprints fuera de features ML (ρ=-0.035, eran ruido)
  ☑ Fix #4 — PDBFixer para MM-GBSA (OpenMM ya no crashea por H faltantes)
  ☑ Fix #5 — DUD-E decoys script listo

Features v1.2 (completas):
  ☑ Visualización interacciones ProLIF en Molstar (esferas coloreadas por tipo)
  ☑ Coordenadas 3D en GET /evaluation/interactions/{id} (ligand_coords + protein_coords)
  ☑ Búsqueda RCSB por nombre — POST /targets/resolve-name
  ☑ Pestaña "Buscar en RCSB" en TargetSelectorModal


═══ FASE 0: CIERRE CIENTÍFICO (3-4 días) ══════════════════════════════

Objetivo: Pipeline validado con métricas reales antes de empaquetar.

Razón: Tenemos código para PDBFixer y DUD-E pero NUNCA se ejecutaron
end-to-end. El feature set cambió (176→167 features por fix #3) y los
modelos XGBoost están entrenados con las features viejas.

│ # │ Tarea │ Archivo │ Esfuerzo │ Criterio de éxito │
├───┼───────┼─────────┼──────────┼───────────────────┤
│ 1 │ Retrain XGBoost │ rescoring/ │ 2h setup │ ALL_FEATURES pasó de 176→167 │
│   │ 167 features   │ train_families.py │ +2h train │ (ProLIF counts out). │
│   │                │                   │           │ Reentrenar universal + 5   │
│   │                │                   │           │ familias + classifier.     │
│   │                │                   │           │ Spearman CV debe mantener  │
│   │                │                   │           │ ≥ 0.70 en universal.      │
│ 2 │ Probar MM-GBSA │ backend/scoring/ │ 2h        │ POST /pro/mmgbsa/{id}     │
│   │ + PDBFixer E2E │ mmgbsa.py        │           │ retorna delta_g_total_kcal │
│   │                │                   │           │ sin errores para 5 mols   │
│   │                │                   │           │ contra 7E2Y.              │
│ 3 │ Correr EF real │ scripts/          │ 1h setup  │ 3000 decoys DUD-E         │
│   │ con decoys     │ download_decoys_  │ +2h cómputo│ dockeados con QuickVina 2. │
│   │                │ and_calculate_    │           │ EF@1% calculado y          │
│   │                │ ef.py             │           │ reportado.                 │
│ 4 │ Documentar     │ docs/             │ 1h        │ Documento con: MM-GBSA     │
│   │ validación     │ 08_VALIDATION_    │           │ deltaG promedio,           │
│   │                │ RESULTS.md        │           │ EF@1%/5%/10%, comparación  │
│   │                │                   │           │ vs Vina solo.              │

Entregable: Reporte científico validando que el pipeline sirve para
cribado virtual real. Sin esto, no hay producto que vender.


═══ FASE 1: EMPAQUETADO DESKTOP (1-2 dias) ══════════════════════════════

Objetivo: .msi instalable que funciona en Windows sin Python pre-instalado.

**Estrategia (v2.0): Embedded Python + pip wheel cache + DLC.**
NO necesitamos conda — todo funciona via pip. Ver [09_PACKAGING_STRATEGY.md](09_PACKAGING_STRATEGY.md).

│ # │ Tarea │ Archivo │ Esfuerzo │ Criterio │
├───┼───────┼─────────┼──────────┼──────────┤
│ 1 │ Generar  │ scripts/ │ 1h │ ~250 MB en .whl files │
│   │ wheelhouse│       │     │ descargados localmente │
│ 2 │ Configurar│ tauri.conf │ 1h │ externalBin con ruta al │
│   │ external │ .json     │     │ python.exe embebido │
│   │ Bin      │          │     │ + launch script │
│ 3 │ Empaquetar│ npx tauri │ 4h │ .msi con Python embed + │
│   │ .msi     │ build     │     │ wheels + code + models  │
│ 4 │ Test en VM│ VM Windows │ 2h │ App funciona sin Python │
│   │ limpia   │ 10        │     │ pre-instalado │

Entregable: MolDesign-Setup-1.0.0.msi (~400 MB base, offline-first).


═══ FASE 2: QA Y POLISH (1 semana) ═══════════════════════════════════

Objetivo: Producto presentable para Steam.

Semana 2.1: Testing E2E
┌─────────────────────────────────────┬────────┬──────────────────────────┐
│ Tarea                              │ Tiempo │ Criterio                 │
├─────────────────────────────────────┼────────┼──────────────────────────┤
│ 1. Test offline completo           │ 2h     │ Sin WiFi → dockeo        │
│                                    │        │ aspirina → PDF → SQLite  │
│ 2. Test rendimiento                │ 1h     │ 10 dockings, RAM < 4GB   │
│ 3. Test instalación limpia         │ 1h     │ VM Windows 10 virgen     │
│ 4. Test auto-updates               │ 2h     │ Tauri Updater descarga   │
│                                    │        │ patch 5MB, reinicia      │
└─────────────────────────────────────┴────────┴──────────────────────────┘

Semana 2.2: UX Polish
┌─────────────────────────────────────┬────────┬──────────────────────────┐
│ Tarea                              │ Tiempo │ Archivo                 │
├─────────────────────────────────────┼────────┼──────────────────────────┤
│ 1. Onboarding tooltip              │ 3h     │ components/              │
│                                    │        │ OnboardingTour.tsx       │
│ 2. Error messages amigables        │ 2h     │ lib/api.ts              │
│ 3. Progress indicators             │ 2h     │ components/              │
│                                    │        │ LoadingStates.tsx        │
└─────────────────────────────────────┴────────┴──────────────────────────┘

Entregable: Build candidato a release (RC1) listo para Steam.


═══ FASE 3: LANZAMIENTO STEAM (1 semana) ═════════════════════════════

Objetivo: Publicar en Steamworks.

Semana 3.1: Steamworks Setup
┌─────────────────────────────────────┬────────┬──────────────────────────┐
│ Tarea                              │ Tiempo │ Criterio                │
├─────────────────────────────────────┼────────┼──────────────────────────┤
│ 1. Crear app en Steamworks         │ 2h     │ App ID asignado          │
│ 2. Subir build base                │ 1h     │ Build 400MB pasa revisión│
│ 3. Configurar DLC Pro              │ 2h     │ DLC CUDA+ESMFold listo   │
│ 4. Assets de tienda                │ 4h     │ Screenshots, video,      │
│                                    │        │ descripción HTML         │
└─────────────────────────────────────┴────────┴──────────────────────────┘

Semana 3.2: Marketing Pre-Launch
┌─────────────────────────────────────┬────────┐
│ Tarea                              │ Tiempo │
├─────────────────────────────────────┼────────┤
│ 1. Landing page                    │ 3h     │
│ 2. Reddit/Forum posts              │ 2h     │
│ 3. Email a universidades           │ 2h     │
│ 4. Press kit                       │ 1h     │
└─────────────────────────────────────┴────────┘

Entregable: Producto live en Steam, página de tienda pública.


═══ FASE 4: POST-LAUNCH (continuo) ════════════════════════════════════

Objetivo: Iterar basado en feedback real.

│ Prioridad │ Feature │ Mes │
├───────────┼─────────┼─────┤
│ 🔴 Alta   │ Fix bugs reportados │ 1 │
│ 🔴 Alta   │ Tutorial video │ 1 │
│ 🟡 Media  │ Exportar CSV/Excel │ 1-2 │
│ 🟡 Media  │ Historial con búsqueda │ 1-2 │
│ 🟢 Baja   │ MM-GBSA batch (50 poses) │ 2-3 │
│ 🟢 Baja   │ Transfer learning GPCR │ 2-3 │
│ 🟢 Baja   │ Build macOS │ 4-6 │
│ 🟢 Baja   │ Android (cliente SaaS) │ 4-6 │


═══ NOTAS TÉCNICAS ═══════════════════════════════════════════════════

Sobre sidecars (Fase 1):
  El approach de lanzar PowerShell scripts (como hace lib.rs hoy) no es
  distribuible. Los sidecars de Tauri deben declararse en externalBin
  para que el bundler los empaquete y Tauri los lance/gestione. Los 3
  binarios (conda-pack outputs) van dentro del .msi.

Sobre conda-pack:
  PyInstaller fue descartado en la auditoría (las extensiones nativas de
  rdkit/OpenMM no son relocatables). La estrategia correcta es empaquetar
  cada entorno Python con conda-pack y que Tauri lo extraiga en
  %AppData%/MolDesign/envs/ al primer inicio.

Sobre Capacitor/Android:
  No hay código de Capacitor en el repo. El roadmap anterior lo incluía
  como Fase 5 pero requiere un backend SaaS funcional primero. Se movió
  a post-launch.

Sobre ESMFold:
  El stub predictor existe y funciona. Los pesos reales (~3 GB) no están
  descargados. El DLC Pro de Steam los distribuiría.

Sobre el pricing sugerido:
  Versión Base (CPU, stub ESMFold): $49.99
  DLC Pro (GPU, ESMFold real, MM-GBSA): $59.99 extra
  (Requiere validación con usuarios reales)

Sobre MolNeuro Agent (futuro v1.5+):
  Arquitectura Planner → Obrero → Reviewer para modelos locales.
  Planner: estructura un plan antes de ejecutar
  Obrero: ejecuta herramientas del sistema (ToolNode)
  Reviewer: verifica y retroalimenta
  Delegacion: sub-agentes para tareas complejas
  Potencial: agente quimico autonomo que explora resultados, compara
  moleculas, busca similares y sugiere mejoras. Mismo modelo, +0 MB VRAM.
  Ver docs/Interprete_IA.md seccion "MolNeuro Agent".
