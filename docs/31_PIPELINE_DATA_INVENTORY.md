# 31 · Inventario del Contrato de Datos del Pipeline

**Estado**: Inventario histórico de UX; **no es contrato API vigente**.
**Propósito**: Mapear TODOS los datos que el backend devuelve y TODOS los componentes del frontend que existen para mostrarlos, antes de reconectar las "tuberías" entre ambos.
**Alcance original**: Frontend únicamente. No documenta el backend Python.

> **Vigencia auditada — 2026-08-15:** este documento conserva contexto útil
> del rediseño de interfaz, pero sus rutas, conteos, estados y afirmaciones de
> componentes no se deben usar para integrar ni publicar el backend. El
> OpenAPI real generado desde `backend/api/main.py` tiene **97 paths / 100
> operaciones** y queda versionado en
> [`docs/api/openapi-current.json`](api/openapi-current.json), con el mapa
> legible [`docs/45_API_CONTRACT_CURRENT.md`](45_API_CONTRACT_CURRENT.md).
> Esos dos artefactos son el contrato vigente y se verifican por CI; este
> inventario no debe volver a usarse para integrar ni publicar el backend.

---

## 0 · Contexto

La pestaña `/evaluation` actualmente muestra un `_mockup_` visual hardcodeado (`MOCK` object en `ProEvaluation.tsx` líneas 64-155). El pipeline real ya está cableado en `app/evaluation/page.tsx` (líneas 103-138: `submitEvaluation` → `startPolling` → `getJobStatus`) pero `ProEvaluation` **ignora los props reales** (solo desestructura `smiles, setSmiles, target, setTarget, targets, proteinData, poseData, onTargetUploadSuccess`).

**Componentes huerfanos** — existen, están bien diseñados, consumen datos reales del `JobStatus.result`, pero ninguna página los importa:
- `ProResults`, `ProAnalysisTabs`, `ProParametersTab`, `ProAlertsTab`, `ProXaiTab`,
  `ProSelectivityPanel`, `SelectivityModal`, `ProConfigPanel`, `DockingEnginePanel`,
  `StageCard`, `Pro3DViewer`

Este documento es el "mapa del tesoro" antes de empezar a cablear: qué campos hay, dónde se muestran, y qué componente los consume.

---

## 1 · Contrato de Datos Principal

### `JobStatus` (envoltorio del estado de un job)
**Fuente**: `frontend/lib/types.ts` líneas 102-111

| Campo | Tipo | Significado |
|-------|------|-------------|
| `task_id` | `string` | UUID del job (lo devuelve `submitEvaluation`) |
| `status` | `string` | `"submitted" \| "PENDING" \| "PROGRESS" \| "SUCCESS" \| "FAILURE"` |
| `progress` | `number` | 0-100 (porcentaje de avance del pipeline) |
| `result` | `EvaluationResult \| null` | Solo no-null cuando `status === "SUCCESS"` |
| `error` | `string \| null` | Mensaje de error cuando `status === "FAILURE"` |
| `started_at` | `string \| null` | ISO timestamp |
| `finished_at` | `string \| null` | ISO timestamp |
| `logs` | `string[]` (opcional) | Tail de logs del pipeline (si el backend los stream) |

### `EvaluationResult` (los 50+ campos que devuelve el pipeline)
**Fuente**: `frontend/lib/types.ts` líneas 25-100

Organizados por sección temática:

#### 1.1 · Identidad / Target
| Campo | Tipo | Componente que lo muestra |
|-------|------|----------------------------|
| `id` | `string` |interno, no se muestra directamente |
| `molecule_id` | `string` |`ProResults` (lo pasa a SAR / MMGBSA / Selectivity / Certify) |
| `smiles_hash` | `string` |interno |
| `target_name` | `string \| null` |`ProResults` (ScoreCard) |
| `target_spearman_rho` | `number \| null` |`ProResults` (ScoreCard `targetSpearman`) |
| `target_pdb_id` | `string \| null` |`ProResults` (ScoreCard), `/history` |
| `is_control` | `boolean` |`ProResults` (ScoreCard `isControl`) |

#### 1.2 · Docking
| Campo | Tipo | Componente |
|-------|------|------------|
| `affinity_kcal` | `number \| null` |Hero/Línea DOT/ScoreCard. Score crudo del stacking XGBoost |
| `affinity_score` | `number \| null` |ScoreCard. Normalizado 0-100 |
| `docking_poses` | `DockingPose[] \| null` |Columna derecha de resultados. Cada pose: `(rank, affinity_kcal, rmsd_lb, rmsd_ub)` |
| `parsing_source` | `string \| null` |Sección "Metadatos de Reproducibilidad" (sdf / mol / smiles) |
| `vina_version` | `string \| null` |Metadatos (ej: `"Vina 1.2.7"`) |
| `vina_random_seed` | `number \| null` |Metadatos (semilla estocástica) |
| `scientific_warnings` | `string[] \| null` |Tab "Alertas" (`ProAlertsTab`) |
| `task_id` | `string \| null` |Interno: identifica el job del dispatcher local. |
| `celery_task_id` | `string \| null` |Alias temporal de compatibilidad API (schema v3); no usar en código nuevo. |
| `certified` | `boolean` (opcional) |`/history` |

#### 1.3 · Propiedades Físico-Químicas
| Campo | Tipo | Componente |
|-------|------|------------|
| `molecular_weight` | `number \| null` |Sección "Propiedades Físico-Químicas" (MW) |
| `log_p` | `number \| null` |Sección propiedades (LogP) |
| `tpsa` | `number \| null` |Sección propiedades (TPSA) |
| `hbd` | `number \| null` |Sección propiedades (HBD) |
| `hba` | `number \| null` |Sección propiedades (HBA) |
| `rotatable_bonds` | `number \| null` |Sección propiedades (Rot. Bonds) |
| `heavy_atom_count` | `number \| null` |Sección propiedades (Heavy Atoms) |
| `ring_count` | `number \| null` |Sección propiedades (Rings) |
| `lipinski_pass` | `boolean \| null` |Drug-likeness ✓/✗ + ScoreCard |
| `veber_pass` | `boolean \| null` |Drug-likeness ✓/✗ |
| `qed` | `number \| null` |Drug-likeness número + Tab "Parámetros" (QED Score) |
| `sa_score` | `number \| null` |Drug-likeness (SA Score) + Tab Parámetros |
| `sa_reasons` | `string[] \| null` |Tab Parámetros ("Restricciones SA") |

#### 1.4 · Scores Compuestos
| Campo | Tipo | Componente |
|-------|------|------------|
| `adme_score` | `number \| null` |ScoreCard (`adme`) |
| `druglikeness_score` | `number \| null` |ScoreCard (`druglikeness`) |
| `blood_viability_score` | `number \| null` |Sección ADMET barras + ScoreCard |
| `blood_solubility_logs` | `number \| null` |Sección ADMET + Tab Parámetros |
| `blood_ppb_category` | `string \| null` |Sección ADMET + Tab Parámetros (PPB) |
| `blood_bbb_permeable` | `boolean \| null` |Sección ADMET + Tab Parámetros (BBB) |
| `blood_hia_permeable` | `boolean \| null` |Sección ADMET + Tab Parámetros (HIA) |
| `blood_systemic_reactivity` | `string[] \| null` |Sección ADMET + Tab Parámetros + ScoreCard |
| `total_score` | `number \| null` |Hero gigante (4rem) + Tier S/A/B/C/D + ScoreCard |
| `gnn_score` | `number \| null` |ScoreCard (`gnnScore`) |
| `specificity_score` | `number \| null` |ScoreCard (`specificity`) |
| `hotspots_hit` | `string[] \| null` |Sección Hotspots (residuos en púrpura) |
| `target_hotspots` | `{name, importance}[] \| null` |Sección Hotspots (lista con importancia) |
| `affinity_threshold` | `number \| null` |Sección propiedades |
| `affinity_multiplier` | `number \| null` |ScoreCard |
| `specificity_multiplier` | `number \| null` |ScoreCard |
| `gnn_factor` | `number \| null` |ScoreCard |
| `sa_factor` | `number \| null` |ScoreCard |
| `blood_factor` | `number \| null` |ScoreCard |
| `ligand_efficiency` | `number \| null` |Sección propiedades (LE) + ScoreCard |
| `ligand_lipophilicity_efficiency` | `number \| null` |Sección propiedades (LLE) + ScoreCard |

#### 1.5 · XAI (Explicabilidad)
| Campo | Tipo | Componente |
|-------|------|------------|
| `shap_values` | `Record<string, number> \| null` |Tab "Explicabilidad" (`ProXaiTab`) — diagrama de abejas direccional SHAP |
| `gnn_attention` | `number[] \| null` |ProXaiTab — disponibilidad (condicional). Mapa de hotspots GNN |
| `gnn_attention_svg` | `string \| null` |ProXaiTab — SVG de topología 2D de atención RTMScore |
| `gnn_pharmacophores` | `Record<string, number> \| null` |ProXaiTab — radar pentagonal (Aromáticos / Donadores H / Aceptores H / Alifáticos / Halógenos) |

`ProXaiTab` ya trae **explicaciones científicas hardcodeadas** para 18 features SHAP (ECIF, shells, close_contacts) en el diccionario `SHAP_EXPLANATIONS` (líneas 7-28) + heurística para features desconocidas (líneas 30-43).

#### 1.6 · Archivos
| Campo | Tipo | Componente |
|-------|------|------------|
| `poses_file_path` | `string \| null` |interno (descargable vía `getPoseFile`) |
| `ai_report` | `string \| null` |No se muestra actualmente en `ProResults`. Disponible vía `getAiReport` |

#### 1.7 · Blockchain / Reproducibilidad
| Campo | Tipo | Componente |
|-------|------|------------|
| `blockchain_tx_id` | `string \| null` |Hero "Ver en Solana Explorer" + ScoreCard (`solanaSignature`) + ProResults botón "Verificar Firma" |
| `error_message` | `string \| null` |interno |
| `evaluated_at` | `string` |interno (timestamp) |

### Campos presentes en `MOCK` pero ausentes del `EvaluationResult` type
**Estos son "deseados" pero no confirmados en `types.ts`**: hay que verificar contra el backend real.

| Campo MOCK | Tipo | Dónde debería ir |
|-------------|------|-------------------|
| `clgnn_score` | `number` |Línea DOT + ScoreCard (`clgnnScore`) |
| `xgb_score` | `number` |Línea DOT (probabilidad XGBoost) |
| `mmgbsa_score` | `number` |Línea DOT + ScoreCard (`mmgbsaScore`) |
| `quantum_score` | `number` |ScoreCard (`quantumScore`) |
| `target_family` | `string` |DOT ("familia GPCR") + ScoreCard (`targetFamily`) |
| `stacking_vina_weight` | `number` |DOT sub-`w=` + ScoreCard |
| `stacking_xgb_weight` | `number` |DOT + ScoreCard |
| `stacking_gnn_weight` | `number` |DOT + ScoreCard |
| `ghose_pass` | `boolean` |Drug-likeness (Ghose) |
| `egan_pass` | `boolean` |Drug-likeness (Egan) |
| `muegge_pass` | `boolean` |Drug-likeness (Muegge) |
| `muegge_score` | `number` |Drug-likeness (`4/9` badge) |
| `fsp3` | `number` |Drug-likeness (Fsp³) |
| `is_pains` | `boolean` |Drug-likeness (PAINS ✓/✗) |
| `pains_matches` | `string[]` |no se muestra en el mock |
| `selectivity_ratio` | `number` |Sección "Selectividad Anti-Target" |
| `selectivity_verdict` | `string` |Sección selectividad ("selectivo") |
| `selectivity_ran` | `boolean` |interno |
| `anti_targets` | `{target, affinity, threshold, safe}[]` |Sección selectividad — pero `ProSelectivityPanel` ya tiene su propia estructura más rica (`resultsMap`) |

**Acción**: antes de cablear, hay que hacer un test real del backend y comparar el JSON devuelto con este type. Los campos que falten se agregan a `EvaluationResult`.

---

## 2 · Endpoints Disponibles (Tuberías hacia el Backend)

### `lib/api.ts` (26 exports)
**Endpoint base**: `http://127.0.0.1:8000` (configurable vía `NEXT_PUBLIC_API_URL`)

#### Pipeline principal
- `submitEvaluation(smiles, target_pdb_id, is_control, grid_center, grid_size, custom_hotspots, peptide_docking_engine, pipeline_config)` → POST `/evaluation/submit` — devuelve `EvaluationSubmitResponse { task_id, status, target_pdb_id, smiles_hash }`
- `getJobStatus(taskId)` → GET `/evaluation/status/{taskId}` — devuelve `JobStatus`
- `getLimitStatus()` → GET `/evaluation/limit-status`
- `validateSmiles(smiles)` → POST `/validate` — devuelve `ValidationResult { is_valid, canonical_smiles, ... }`

#### Targets
- `getTargets()` → GET `/targets`
- `getTargetPdb(pdbId)` → GET `/target/{pdbId}/pdb` — devuelve string PDB
- `uploadCustomTarget(formData)` → POST `/targets/upload` — sube receptor custom
- `shareCustomTarget(targetId)` → POST `/targets/{id}/share`
- `lookupAlphaFold(uniprotId)` → GET `/alphafold/{uniprotId}`

#### Archivos / Resultados
- `getPoseFile(moleculeId)` → GET `/molecule/{id}/poses.sdf`
- `getProteinFile(moleculeId)` → GET `/molecule/{id}/protein.pdb`
- `getComplexFile(moleculeId)` → GET `/molecule/{id}/complex.pdb` — descargable
- `getAiReport(moleculeId)` → GET `/molecule/{id}/ai-report`
- `getSuggestions(...)` → POST `/suggestions`

#### Persistencia / Certificación
- `saveMolecule(id, name)` → POST `/molecule/{id}/save`
- `certifyMolecule(id)` → POST `/molecule/{id}/certify` — devuelve `{ signature }`
- `prepareCertification(id)` → POST
- `linkCertification(id, signature)` → POST
- `downloadCertificate(id)` → blob PDF
- `fetchCertificateBlobUrl(id)` → URL firmada
- `getEvaluationHistory(page, size, sort, order)` → GET `/evaluation/history`
- `getUserStats()` → GET `/evaluation/user-stats`
- `getMoldex(targetPdbId?)` → GET `/moldex`
- `getGlobalStats()` → GET `/stats/global`
- `checkBlockchainHealth()` → GET `/blockchain/health`
- `resolveTargetName(pdbId, targetsList?)` — helper local

### `lib/proApi.ts` (31 exports) — features "Pro"
TODOS usan un endpoint que parece estar bajo `/pro/`. Hay versión "Pro" del backend con features avanzadas.

#### Selectivity / Anti-targets
- `getAntiTargets()` → GET `/pro/anti-targets` — lista de receptores de seguridad (hERG, CYP3A4, ...)
- `runSelectivity(...)` → POST (polling)
- `runSelectivityStream(moleculeId, onEvent, signal, numWorkers)` → EventSource `/pro/selectivity/stream/{id}` — stream SSE en tiempo real
- `dockSingleAntiTarget(moleculeId, pdbId)` → POST — corre docking contra un anti-target
- `saveSelectivityResults(moleculeId, fullObj)` → POST — persiste resultados localmente

#### MM-GBSA / Refinamiento
- `runMmgbsa(...)` → POST
- (ver `ProResults` lines 50-53: `mmgbsaResult`, `mmgbsaNumSteps`)

#### SAR (Estructura-Actividad)
- `getSarData(moleculeId)` → GET — devuelve lista de análogos evaluados contra el mismo target, con similarity, ΔScore, ΔAfinidad

#### Hardware / Estimación
- `getGpuStatus()` → GET `/hardware/gpu`
- `getHealth()` → GET `/hardware/health`
- (usado por `ProConfigPanel`):
  - `fetch(/hardware)` → info CPU/RAM/GPU + recomendaciones workers/parallel_docks
  - `fetch(/hardware/estimate?mode=pro&anti_targets=N&mmgbsa=bool)` → estimación tiempo total

#### Comunidad
- `getLeaderboard()` — tabla de líderes global
- `getCommunityTargets()` — targets compartidos
- `downloadCommunityTarget(pdbId)` — descarga target compartido
- `ingestTarget(...)` — sube target propio a la comunidad

#### IA / Descarga de Modelos
- `searchAIModels(query)`, `getLocalAIModels()`, `downloadAIModel(id)`, `getDownloadStatus(id)`, `recommendQuantization()` — gestor de modelos locales

#### Cálculos químicos
- `calculateProperties(smiles)` → calcula fisicoquímicas sin necesidad de docking
- `generateConformer(smiles, forceRegenerate)` → conformero 3D
- `getMolRender(moleculeId)` → render 2D imagen

#### DiffDock / ColabFold (motores alternativos)
- `runDiffDock(...)`, `getDiffDockHealth()`
- `runColabFold(...)`, `getColabFoldHealth()`

#### Metales / Docking Dinámico
- `getMetalFeatures(smiles)`, `detectMetals(pdbContent)`, `getDynamicBox(ligandPdb)`, `validateVinaAtoms(smiles)`, `prepareTarget(...)`

#### Blockchain
- `verifyBlockchainSignature(signature)` → verifica en Solana Devnet

### `lib/pipelineStream.ts` — el stream SSE perdido
**Crítico**: este archivo existe y NADIE lo usa actualmente.

```ts
subscribeToPipelineEvents(taskId, onEvent, onClose) {
  const eventSource = new EventSource(`/api/evaluation/stream/${taskId}`);
  // recibe eventos: pipeline_started | stage_start | stage_done | stage_error | pipeline_done | pipeline_error
}
```

**`PipelineEvent`** ( tipos soportados por el SSE ):

| `type` | `stage_id` | `label` | `duration_ms` | `error` |
|--------|------------|---------|---------------|---------|
| `pipeline_started` | — | — | — | — |
| `stage_start` | `"docking"` | `"Docking Vina"` | — | — |
| `stage_done` | `"docking"` | — | `1234` | — |
| `stage_error` | `"docking"` | — | — | `"Vina executable not found"` |
| `pipeline_done` | — | — | — | — |
| `pipeline_error` | — | — | — | `"Vina executable not found"` |

**Usuarios potenciales**: `StageCard`consume `(stage.id, stage.label, stage.required, stage.cost_estimate, stage.params, status: idle/running/done/error, progress, durationMs, error)` — o sea, es el componente visual desarrollado justo para renderizar eventos SSE del pipeline en tiempo real. Solo necesita un contenedor que mantenga `stages[]` en estado y los actualice conforme llegan eventos del stream.

---

## 3 · Componentes del Frontend — Inventario

### 3.1 · Componentes realmente montados (en uso)

| Component | Path | Page padre | Estado |
|-----------|------|-----------|--------|
| `ProEvaluation` | `components/interfaces/pro/ProEvaluation.tsx` | `/evaluation` | **MOCK** — 100% hardcodeado, ignora props reales |
| `TargetSelectorModal` | `.../pro/TargetSelectorModal.tsx` | `ProEvaluation` | ✓ real — abre modal de targets, soporta custom receptor |
| `KetcherEditor` | `components/KetcherEditor.tsx` (no interfaces/pro) | `ProEvaluation` | ✓ real — editor 2D de moléculas (Ketcher) |
| `AdvancedMolstarViewer` | `.../pro/AdvancedMolstarViewer.tsx` | `ProEvaluation` | ✓ real — visor 3D MolStar con `proteinData`/`poseData` cargados via useEffect. **Fix de parpadeo** aplicado (commit `ab9123b`). OJO: todavía carga molstar CSS/JS por CDN primero (líneas 267-279) — pendiente refactor all-local |
| `CustomReceptorModal` | `.../pro/CustomReceptorModal.tsx` | `TargetSelectorModal` | ✓ — sube PDB custom a `/targets/upload` |
| `ProMoldex` | `.../pro/ProMoldex.tsx` | `/moldex` | ✓ real — biblioteca pública |
| `LauncherScreen` | `components/LauncherScreen.tsx` | `/launcher` | ✓ — launcher tipo Riot con descarga de modelos |
| `LoginForm` / `DesktopLogin` / `CloudLogin` | `app/login/*` | `/login` | ✓ |

### 3.2 · Componentes huerfanos (bien diseñados, esperando wiring)

| Component | Path | Props principales | Función |
|-----------|------|-------------------|---------|
| `ProResults` | `.../pro/ProResults.tsx` (633 líneas) | `status: JobStatus, isSaved, enableSelectivity, numWorkers, onCertify, onSave, onDownloadCertificate, onViewCertificate, onDownloadComplex` | Hero de resultados + botones post-evaluación: SAR, MMGBSA, Blockchain Verify. AUTO-lanza `runSelectivityStream` cuando `status === "SUCCESS"` y `enableSelectivity` |
| `ProAnalysisTabs` | `.../pro/ProAnalysisTabs.tsx` (104) | `status: JobStatus, selectivityResult, moleculeId, onUpdateSelectivityResult` | Contenedor de tabs (Parámetros / Alertas / Explicabilidad / Selectividad). Lee `status.result` y reparte a sub-tabs |
| `ProParametersTab` | `.../pro/ProParametersTab.tsx` (141) | `result: EvaluationResult` | **QED, SA Score, MW, LogP** + **ADMET completo** (Solubilidad, PPB, HIA, BBB, Reactividad Sistémica). Fuentes: ADMET-AI, TabPFN |
| `ProAlertsTab` | `.../pro/ProAlertsTab.tsx` (118) | `warnings: string[]` | Tarjetas de alerta clasificadas por color: Positivo / Precaución / Crítica / Nota científica |
| `ProXaiTab` | `.../pro/ProXaiTab.tsx` (348) | `shapValues, gnnAttention, gnnAttentionSvg, gnnPharmacophores` | **Diagrama SHAP de abejas direccional** + Mapa GNN 2D (SVG) + Radar pentagonal de farmacóforos + Modal explicativo por feature |
| `ProSelectivityPanel` | `.../pro/ProSelectivityPanel.tsx` (553) | `moleculeId, onTargetAffinity, initialResult, onUpdateResult` | **Panel de selectividad regulatorio 1 a 1**. 5 anti-targets hardcodeados: hERG (5VA1), CYP3A4 (4NY4), 5-HT2B (4NC3), PDE3A (1SO2), NaV1.5 (6MVW). Cada uno con: bioDetails, mitigación SAR, función biológica. Botones "Evaluar" / "Evaluar Todos". Calcula ratio, veredicto clínico, Ki estimado. Modal educativo "Saber más" |
| ~~`SelectivityModal`~~ | **RETIRADO (2026-09-02)** | — | Duplicado sin usar de `ProSelectivityPanel`; arrastraba los defectos B1/B2 del doc 71. Restaurable: `git show ec4fb21:frontend/components/interfaces/pro/SelectivityModal.tsx` |
| `ProConfigPanel` | `.../pro/ProConfigPanel.tsx` (387) | `config: ProConfig, onChange` | **Opciones avanzadas del hardware**: workers, parallel_docks, enableSelectivity, selectedAntiTargets, enableMMGBSA, mmgbsaSteps, enableADMET. Lee `/hardware`, `/pro/anti-targets`, `/hardware/estimate`. Muestra CPU/RAM/GPU, warnings, tiempo estimado |
| `DockingEnginePanel` | `.../pro/DockingEnginePanel.tsx` (191) | `config: DockingEngineConfig, onChange, gpuAvailable, gpuCuda, isPeptide` | **Selección de motor**: AutoDock Vina / QuickVina 2 / DiffDock. Motor de péptidos: ESMFold / ESMFold Pro / ColabFold / RFdiffusion. Precision GNN: FP32 / FP16 |
| `StageCard` | `.../pro/StageCard.tsx` (161) | `stage: StageInfo, status: StageStatus, progress, durationMs, error, onToggle, onParamChange, onMoveUp, onMoveDown, showReorderControls` | **Card individual por etapa del pipeline**. Toggle on/off. Editar parámetros in-line. Reordenar (modo manual). Costo estimado. Estado `idle/running/done/error` con spinner, check, error badge |
| `Pro3DViewer` | `.../pro/Pro3DViewer.tsx` | (wrapper 3D) | Parece ser un wrapper alternativo al AdvancedMolstarViewer |

### 3.3 · Componentes UI compartidos

| Component | Dónde se usa |
|-----------|--------------|
| `ThinkingOrb` (`ui/ThinkingOrb.tsx`) | `ProEvaluation` (pantalla de carga) |
| `ScoreCard` (`components/ScoreCard.tsx`) | `ProResults` — tarjeta con 25+ props de scores compuestos |
| `KetcherEditor` | `ProEvaluation` — editor 2D |
| `PipelineFlowchart` | `/` (home) |
| `TechNetwork3D` | `/` (home) |
| `Navbar`, `OptionsMenu` | layout global |

---

## 4 · Flujo de Usuario Ideal (post-wiring)

```
Home (/)  →  Click "Iniciar Evaluación"  →  /evaluation
        │
        ▼
[ProEvaluation con wiring real]
        │
        ├─ Selecciona SMILES (KetcherEditor o input)
        ├─ Tab "Parámetros": valida SMILES → muestra canonical + formula
        ├─ Abre TargetSelectorModal → elige target (o sube custom)
        │   └─ useEffect → getTargetPdb → AdvancedMolstarViewer muestra proteína
        │
        ├─ [Panel izq] ProConfigPanel
        │   ├─ Hardware detectado (CPU/RAM/GPU)
        │   ├─ numWorkers, parallelDocks
        │   ├─ enableSelectivity, selectedAntiTargets
        │   ├─ enableMMGBSA, mmgbsaSteps
        │   └─ enableADMET
        │
        ├─ [Panel izq] DockingEnginePanel
        │   ├─ Motor moléculas pequeñas: Vina / QVina2 / DiffDock
        │   ├─ Motor péptidos (si isPeptide): ESMFold / ESMFold Pro / ColabFold / RFdiffusion
        │   └─ GNN precision: FP32 / FP16 (si GPU/CUDA)
        │
        ├─ [Panel izq] StageCard[]
        │   ├─ Cada etapa del pipeline: toggle, parámetros in-line, reordenar
        │   └─ Costo estimado, estado idle/running/done/error
        │   └─ (Se actualiza en vivo desde SSE `pipelineStream.ts`)
        │
        ├─ [Botón "Ejecutar Evaluación"]
        │   └─ handleSubmit(gridCenter, gridSize, hotspots, peptideEngine, pipelineConfig)
        │       └─ POST /evaluation/submit → task_id
        │
        ├─ [Pantalla processing]
        │   ├─ ThinkingOrb +游行了 dots animados
        │   ├─ StageCards en estado running/done en vivo (SSE)
        │   └─ Progress bar (JobStatus.progress)
        │
        └─ [Resultados — SUCCESS]
            ├─ ProResults (Hero ScoreCard con los 25+ scores)
            ├─ ProAnalysisTabs
            │   ├─ Tab "Parámetros": QED, SA, MW, LogP, ADMET (TabPFN, ADMET-AI)
            │   ├─ Tab "Alertas": scientific_warnings clasificadas por severidad
            │   ├─ Tab "Explicabilidad": SHAP + GNN attention SVG + farmacóforos
            │   └─ Tab "Selectividad": 1-a-1 vs 5 anti-targets (hERG, CYP3A4, 5-HT2B, PDE3A, NaV1.5)
            │       ├─ Boton "Evaluar Todos" → dockSingleAntiTarget[] ×5
            │       ├─ Ratio, veredicto clínico, safety flags
            │       └─ Modal "Saber más" con biología + mitigación SAR
            │
            ├─ [Acciones post-resultados]
            │   ├─ Guardar (saveMolecule)
            │   ├─ Certificar (certifyMolecule → firma Solana)
            │   ├─ Descargar Certificado PDF (downloadCertificate)
            │   ├─ Ver en Solana Explorer
            │   ├─ Descargar Complejo .PDB (getComplexFile)
            │   ├─ Análisis SAR (getSarData → tabla análogos)
            │   ├─ Refinamiento MM-GBSA (runMmgbsa → ΔG total + por pose)
            │   └─ Verificar Firma Blockchain (verifyBlockchainSignature)
```

---

## 5 · Brechas Detectadas (Trabajo Pendiente)

| Brecha | Severidad | Notas |
|--------|-----------|-------|
| `ProEvaluation` ignora `handleSubmit`, `busy`, `status`, `error`, `selectivityResult`, `handleSave`, `handleCertify`, `handleValidate`, `handleDownloadCertificate`, `handleDownloadComplex`, `startPolling`, `stopPolling`, `suggestions`, `loadingSuggestions` | **Critical** — es la razón por la que el usuario ve el `alert()` placeholder |
| `pipelineStream.ts` no se usa en ningún lado | **High** — el SSE de progreso del pipeline existe en código pero nadie lo subscribe |
| `StageCard` no se usa en ningún lado | **High** — el control granular de etapas del pipeline no está expuesto |
| `ProConfigPanel` no se usa | **High** — el usuario no puede ajustar workers/parallel_docks/MMGBSA-steps/selectividad/anti-targets/ADMET |
| `DockingEnginePanel` no se usa | **High** — el usuario no puede elegir Vina/QVina2/DiffDock, ni motor de péptidos, ni FP32/FP16 |
| `ProResults`, `ProAnalysisTabs` y los 4 sub-tabs no se montan | **Critical** — los datos del pipeline real nunca se muestran |
| `ProSelectivityPanel` no se usa | **High** — el análisis de selectividad regulatorio no aparece |
| Campos ausentes del `EvaluationResult` type (sección 1.7) | Medium — hay que verificar contra el backend real y sincronizar el type |
| AdvancedMolstarViewer todavía carga MolStar CSS/JS por CDN (líneas 267-279) con fallback local | Medium — pendiente refactor "all-local" para no romper CSP `'unsafe-eval'` |
| `Review-Animations` skill no aplicado | Low — seria un polish visual |

---

## 6 · Principios a Seguir en el Wiring

1. **No tocar el mock visual todavía**: `ProEvaluation` ya tiene el diseño aprobado por el autor. Es el "contrato visual". Mover a `ProEvaluation_legacy.tsx` como referencia si es necesario, pero NO borrar.

2. **Estrategia (A) recomendada**: refactor `ProEvaluation` in-place para usar props reales preservando el diseño GSAP. Riesgo: depende de cuánto se acople `MOCK.total_score.toFixed()` en el JSX.

3. **Estrategia (B) alternativa**: crear `ProEvaluationLive.tsx` que use los props reales. Ventaja: no rompe la demo. Desventaja: dos fuentes de UI que mantener hasta cleanup.

4. **Respetar el flujo SSE**: cuando se ejecute el pipeline, `subscribeToPipelineEvents(taskId, onEvent, onClose)` manda eventos que alimentan `stages[]` en estado. Una iteración natural:
   ```
   const [stages, setStages] = useState<Record<string, {status, progress, durationMs, error}>>({});
   subscribeToPipelineEvents(taskId, (event) => {
     if (event.type === "stage_start") setStages(prev => ({...prev, [event.stage_id]: {status: "running"}}));
     if (event.type === "stage_done") setStages(prev => ({...prev, [event.stage_id]: {status: "done", durationMs: event.duration_ms}}));
     // ...
   });
   ```
   `StageCard` recibe su `stage` + `status` de este mapa.

5. **Definir las etapas del pipeline** previamente. El backend SSE emite `stage_id` strings. Necesitamos el listado de IDs (`docking`, `mmgbsa`, `xgboost`, `clgnn`, `...`?) que emite el backend Python para mapear a `StageInfo` con su label, descripción, costo, params editables. **Acción requerida**: leer `api/main.py` o pedir al backend team el listado de stage_ids.

6. **Cableado default**: cuando `enableSelectivity` esté `true`, `ProResults` ya auto-lanza `runSelectivityStream` (línea 87-99) — el todo-labelledbyedy forwarding debe respetar ese comportamiento.

---

## 7 · Archivos Relevantes

- `frontend/lib/types.ts` — definiciones de tipos (250 líneas)
- `frontend/lib/api.ts` — 26 exports de endpoints comunes (522 líneas)
- `frontend/lib/proApi.ts` — 31 exports de endpoints "Pro" (~560 líneas)
- `frontend/lib/pipelineStream.ts` — SSE stream de pipeline (39 líneas, SIN USO)
- `frontend/app/evaluation/page.tsx` — page con wiring real pero ignorado
- `frontend/components/interfaces/pro/ProEvaluation.tsx` — componente activo, 100% MOCK (835 líneas)
- `frontend/components/interfaces/pro/ProResults.tsx` — hero/results real, huérfano (633 líneas)
- `frontend/components/interfaces/pro/ProAnalysisTabs.tsx` — contenedor tabs, huérfano (104)
- `frontend/components/interfaces/pro/ProParametersTab.tsx` — QED/SA/ADMET, huérfano (141)
- `frontend/components/interfaces/pro/ProXaiTab.tsx` — SHAP + GNN, huérfano (348)
- `frontend/components/interfaces/pro/ProSelectivityPanel.tsx` — anti-targets regulatorio, huérfano (553)
- `frontend/components/interfaces/pro/ProConfigPanel.tsx` — hardware config, huérfano (387)
- `frontend/components/interfaces/pro/DockingEnginePanel.tsx` — selección motor, huérfano (191)
- `frontend/components/interfaces/pro/StageCard.tsx` — card por etapa, huérfano (161)
- `frontend/components/interfaces/pro/AdvancedMolstarViewer.tsx` — visor 3D, ACTIVO
- `frontend/components/ScoreCard.tsx` — scorecard 25+ props
- `frontend/components/KetcherEditor.tsx` — editor 2D

---

## 8 · Próximos Pasos Sugeridos

1. **Verificar el contrato real contra el backend**: levantar el backend (`scripts/start-desktop.ps1`), correr una evaluación con un SMILES conocido, e inspeccionar el JSON que devuelve `getJobStatus` cuando `status === "SUCCESS"`. Comparar con `EvaluationResult`. Agregar campos faltantes (sección 1.7).

2. **Conseguir el listado de `stage_id`s del backend**: leer `api/main.py` (o equivalente) para ver qué IDs emite el SSE en cada `stage_start`/`stage_done`. Esto define el contenido del `stages[]` inicial en el contenedor de `StageCard`.

3. **Decidir estrategia**: (A) refactor in-place `ProEvaluation` vs (B) nuevo `ProEvaluationLive`.

4. **Definir UX del pipeline**: ¿qué threshold decide si los paneles `ProConfigPanel` + `DockingEnginePanel` + `StageCard`s están colapsados por defecto o visibles? ¿sección "Opciones Avanzadas" expandible?

5. **Una vez decidido**: cables en orden:
   a. Conectar `ProConfigPanel` + `DockingEnginePanel` al estado de `evaluation/page.tsx`.
   b. Construir contenedor de `StageCard`s alimentado por `subscribeToPipelineEvents`.
   c. Reemplazar el botón `alert()` con `handleSubmit(gridCenter, gridSize, hotspots, peptideEngine, pipelineConfig)`.
   d. Cambiar `ProEvaluation` para que renderice `ProResults` + `ProAnalysisTabs` cuando `status?.status === "SUCCESS"`.
   e. Wire los handlers de ProResults (`onCertify`, `onSave`, `onDownloadCertificate`, `onDownloadComplex`) a los que `evaluation/page.tsx` ya está construyendo.

---

**END — Inventario completo de contrato de datos del pipeline.**
