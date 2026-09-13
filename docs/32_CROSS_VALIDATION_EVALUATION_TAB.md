# 32 · Cross-Validation — Pestaña Evaluación (Estado Actual vs Inventario)

**Basado en**: `31_PIPELINE_DATA_INVENTORY.md` (contrato de datos + componentes huerfanos)
**Fuente primaria**: `frontend/components/interfaces/pro/ProEvaluation.tsx` (835 líneas, 100% MOCK)
**Fecha**: 2026-07-29
**Método**: comparación sección-por-sección de lo que el usuario ve (mock) contra lo que podría ver (componentes + datos reales)

---

## Resumen Ejecutivo

La pestaña `/evaluation` **muestra un 87% de datos fake** (MOCK). Solo 4 de 30+ secciones tienen wiring real:
- KetcherEditor (editor 2D) ✓
- AdvancedMolstarViewer (visor 3D) ✓
- SMILES input bar ✓
- TargetSelectorModal (el catálogo de targets) ✓

Todo lo demás — scores, propiedades, ADMET, XAI, selectividad, acciones (guardar/certificar/descargar), pipeline progress — es MOCK o placeholder.

---

## Validación Cruzada Detallada

### A · Zona de Control (Parte Superior)

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Componente listo | Brecha |
|----------------|---------------------|--------------------| ------------------| ------ |
| **KetcherEditor** | ✓ editor 2D real; SMILES se guarda en estado | lo mismo | `KetcherEditor` (activo) | `NINGUNA` — funciona |
| **SMILES input bar** | ✓ input editable; refleja `smiles` state | lo mismo | nativo `<input>` (activo) | `NINGUNA` |
| **AdvancedMolstarViewer** | ✓ proteína 3D real; cargada vía `getTargetPdb(target)` | lo mismo | `AdvancedMolstarViewer` (activo) | [x] parpadeo arreglado en commit `ab9123b`. [ ] OJO: CDN molstar CSS/JS todavía (líneas 267-279), refactor all-local pendiente |
| **Barra de Target** | ✓ muestra "Receptor elegido: $target"; click → modal | lo mismo | `TargetSelectorModal` (activo) | `NINGUNA` |

### B · Botones de Control

| Elemento en UI | ¿Qué hace? | ¿Qué DEBERÍA hacer? | Componente/endpoint listo | Brecha |
|----------------|-----------|--------------------| ---------------------------| ------ |
| **"Simular Resultados"** | togglea `showMockResults` (MOCK) con datos fake | cambiar a "Reiniciar" o "Nueva Evaluación" — en versión real no se "simula", se evalúa de verdad | — | `CRITICAL` — este botón es la columna vertebral del mock. La versión real no necesita "simular resultados", necesita `handleSubmit()`. Considerar: reemplazar por "Ejecutar Evaluación" (real) Y "Limpiar Resultados" |
| **"Ejecutar Evaluación"** | `alert("Iniciando pipeline de evaluación biológica Vina/Gnina...")` — nada más | llamar `handleSubmit(gridCenter, gridSize, hotspots, peptideEngine, pipelineConfig)` → `submitEvaluation()` → `startPolling()` → `getJobStatus()` cada 2s | `handleSubmit` ya cableado en `evaluation/page.tsx` línea 103. `submitEvaluation` → POST `/evaluation/submit`. `getJobStatus` → polling. | `CRITICAL` — es un `alert()` placeholder |
| **Config Panel (inexistente)** | no se ve | `ProConfigPanel` colapsable: numWorkers, parallelDocks, enableSelectivity, selectedAntiTargets, enableMMGBSA, mmgbsaSteps, enableADMET. Hardware detectado (CPU/RAM/GPU). Tiempo estimado. | `ProConfigPanel` ✓ (387 líneas) | `MISSING` — no está en la UI |
| **Docking Engine Panel (inexistente)** | no se ve | `DockingEnginePanel` colapsable: elegir Vina/QVina2/DiffDock para moléculas pequeñas; elegir ESMFold/ESMFold Pro/ColabFold/RFdiffusion para péptidos; elegir FP32/FP16 para GNN | `DockingEnginePanel` ✓ (191 líneas) | `MISSING` — no está en la UI |

### C · Pantalla de Procesamiento (Processing)

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Componente/endpoint listo | Brecha |
|----------------|--------------------|--------------------| ---------------------------| ------ |
| **ThinkingOrb** | ✓ aparece cuando `showMockResults && isProcessing` (fake 1.8s timeout) | aparece cuando `busy === true` o `status.status === "PENDING"/"PROGRESS"` | `ThinkingOrb` (activo) | `CRITICAL` — condicionado a `showMockResults`, no a `busy`/`status`. Necesita cambiar el trigger |
| **Pipeline sub-etapas** | muestra texto estático "Vina · XGBoost · CL-GNN · OpenMM" + dots animados | `StageCard[]` por cada stage, actualizado en vivo vía SSE con estado `idle → running → done/error`, duración real en ms, parámetros editables | `StageCard` ✓ (161 líneas), `pipelineStream.ts` ✓ (39 líneas). SSE emite `stage_start`/`stage_done`/`pipeline_done` | `MISSING` — ni siquiera está en el mock. El mock solo muestra texto |
| **Progress bar** | no se ve | barra de progreso `JobStatus.progress` 0-100% | `JobStatus.progress` | `MISSING` — el mock solo muestra dots animados fijos |

### D · Resultados — Hero (Score Gigante)

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Campo real equivalente | Brecha |
|----------------|--------------------|--------------------| -----------------------| ------ |
| **Score total** | `78.5` (hardcoded `MOCK.total_score`) | `status.result.total_score` (número real) | `EvaluationResult.total_score` ✓ | `CRITICAL` — MOCK |
| **Tier** | Tier A (calculado de `MOCK.total_score` 78.5) | calculado del `result.total_score` real | — | `CRITICAL` — MOCK |
| **Target name** | `5-HT1A (Serotonin Receptor)` hardcoded | `result.target_name` o `result.target_pdb_id` | `EvaluationResult.target_name` ✓ | `CRITICAL` — MOCK |
| **Spearman ρ** | `0.48` hardcoded | `result.target_spearman_rho` | `EvaluationResult.target_spearman_rho` ✓ | `CRITICAL` — MOCK |

### E · Hero — Botones de Acción

| Elemento en UI | ¿Qué hace? | ¿Qué DEBERÍA hacer? | Handler en `evaluation/page.tsx` | Brecha |
|----------------|-----------|--------------------|----------------------------------| ------ |
| **"Guardar"** | togglea `isSavedMock` (falso guardado, sin backend) | `handleSave(customName)` → `saveMolecule(id, name)` → POST | `page.tsx` línea 194-203: `handleSave` real | `CRITICAL` — botón desconectado |
| **"Certificar"** | togglea `isCertifiedMock` (falso, sin backend) | `handleCertify()` → `certifyMolecule(id)` → firma Solana → actualiza `blockchain_tx_id` | `page.tsx` línea 204-224: `handleCertify` real con `setStatus`, `playSound("sparkle")` | `CRITICAL` — botón desconectado |
| **"Ocultar"** | `setShowMockResults(false)` | `handleReset()` — limpiar job actual, volver a estado inicial | `page.tsx` línea 140-150: `handleReset` resetea `taskId, status, error, suggestions, poseData, proteinData, isSaved` | `CRITICAL` — botón desconectado |
| **"Descargar PDF"** | `alert("Descargando PDF...")` | `handleDownloadCertificate()` → `downloadCertificate(id)` → blob PDF | `page.tsx` línea 225-232 | `CRITICAL` — placeholder `alert()` |
| **"Complejo .PDB"** | `alert("Descargando complejo PDB...")` | `handleDownloadComplex()` → `getComplexFile(id)` → blob PDB | `page.tsx` línea 233-250 | `CRITICAL` — placeholder `alert()` |
| **"Ver en Solana Explorer"** | link a `explorer.solana.com/tx/{MOCK.blockchain_tx_id}` (tx fake) | link con `result.blockchain_tx_id` real | `EvaluationResult.blockchain_tx_id` ✓ | `CRITICAL` — MOCK |
| **"Vista Previa"** | `alert("Vista previa del PDF...")` | (no existe endpoint real) | — | `LOW` — quizás no necesario |

### F · DOT Timeline (Cómo se calculó el score)

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Campo real | Brecha |
|----------------|--------------------|--------------------|------------| ------ |
| **Docking Vina** | `-9.4 kcal/mol`, `v1.2.7`, `w=0.4` (MOCK) | afinidad real, versión real, peso real | `affinity_kcal`, `vina_version`, `stacking_vina_weight` | `CRITICAL` — MOCK. `stacking_vina_weight` NO está en `EvaluationResult` |
| **XGBoost** | `p = 81%`, `w=0.4` (MOCK) | score real, peso real | `xgb_score` NO está en `EvaluationResult`, `stacking_xgb_weight` NO está | `CRITICAL` — MOCK + campos ausentes del type |
| **CL-GNN** | `p = 68%`, `w=0.2` (MOCK) | score real, peso real | `clgnn_score` NO está en `EvaluationResult`, `stacking_gnn_weight` NO está | `CRITICAL` — MOCK + campos ausentes |
| **MM-GBSA** | `-8.2 kcal/mol`, `OpenMM OBC2` (MOCK) | score real | `mmgbsa_score` NO está en `EvaluationResult` | `CRITICAL` — MOCK + campo ausente |
| **Familia GPCR** | `familia gpcr` hardcoded | `result.target_family` | `target_family` NO está en `EvaluationResult` | `CRITICAL` — campo ausente |

### G · Drug-likeness (Reglas)

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Campo real | Brecha |
|----------------|--------------------|--------------------|------------| ------ |
| **Lipinski** | ✓ (MOCK `lipinski_pass: true`) | `result.lipinski_pass` | ✓ existe en `EvaluationResult` | `MEDIUM` — campo existe, solo wiring |
| **Veber** | ✓ (MOCK `veber_pass: true`) | `result.veber_pass` | ✓ existe en `EvaluationResult` | `MEDIUM` |
| **Ghose** | ✓ (MOCK `ghose_pass: true`) | ... | `ghose_pass` NO está en `EvaluationResult` | `MEDIUM` — campo ausente |
| **Egan** | ✓ (MOCK `egan_pass: true`) | ... | `egan_pass` NO está | `MEDIUM` |
| **Muegge** | ✗ `4/9` (MOCK) | ... | `muegge_pass`, `muegge_score` NO están | `MEDIUM` |
| **Fsp³** | `0.15` (MOCK) | ... | `fsp3` NO está | `LOW` |
| **PAINS** | ✓ (MOCK `is_pains: false`) | ... | `is_pains`, `pains_matches` NO están | `LOW` |
| **QED** | `0.85` (MOCK) | `result.qed` | ✓ existe | `MEDIUM` — solo wiring |

### H · ADMET & Viabilidad

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Campo real | Brecha |
|----------------|--------------------|--------------------|------------| ------ |
| **Viabilidad Sanguínea** | barra `88/100` (MOCK) | `result.blood_viability_score` | ✓ existe | `MEDIUM` — solo wiring |
| **Solubilidad (LogS)** | barra calculada de MOCK `-4.2 logS` | `result.blood_solubility_logs` | ✓ existe | `MEDIUM` |
| **PPB** | `low` (MOCK) | `result.blood_ppb_category` | ✓ existe | `MEDIUM` |
| **HIA** | `✓ Alta` (MOCK) | `result.blood_hia_permeable` | ✓ existe | `MEDIUM` |
| **BBB** | `✗ No permeable` (MOCK) | `result.blood_bbb_permeable` | ✓ existe | `MEDIUM` |
| **SA Score** | `2.1 / 10` (MOCK) | `result.sa_score` | ✓ existe | `MEDIUM` |
| **Reactividad Sistémica** | `[]` vacío (MOCK) | `result.blood_systemic_reactivity` | ✓ existe | `MEDIUM` |

### I · Propiedades Físico-Químicas

| Elemento en UI | MOCK value | Campo real | Brecha |
|----------------|-----------|------------| ------ |
| **MW** | `180.16 g/mol` | `molecular_weight` ✓ | `MEDIUM` |
| **LogP** | `2.41` | `log_p` ✓ | `MEDIUM` |
| **TPSA** | `63.6 Å²` | `tpsa` ✓ | `MEDIUM` |
| **HBD / HBA** | `1 / 4` | `hbd`, `hba` ✓ | `MEDIUM` |
| **Rot. Bonds** | `4` | `rotatable_bonds` ✓ | `MEDIUM` |
| **Heavy Atoms** | `13` | `heavy_atom_count` ✓ | `MEDIUM` |
| **Rings** | `2` | `ring_count` ✓ | `MEDIUM` |
| **LE** | `-0.72` | `ligand_efficiency` ✓ | `MEDIUM` |
| **LLE** | `4.50` | `ligand_lipophilicity_efficiency` ✓ | `MEDIUM` |
| **Aff. Threshold** | `-7.5 kcal/mol` | `affinity_threshold` ✓ | `MEDIUM` |

### J · Docking Poses & Hotspots

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Campo real | Brecha |
|----------------|--------------------|--------------------|------------| ------ |
| **Pose #1** | `-9.4 kcal/mol`, `RMSD 0.0/0.0` (MOCK) | `result.docking_poses[0]` (rank, affinity_kcal, rmsd_lb/ub) | `DockingPose[]` ✓ | `MEDIUM` — solo wiring |
| **Pose #2** | `-8.8`, RMSD `1.4/2.1` (MOCK) | poses reales | ✓ | `MEDIUM` |
| **Pose #3** | `-8.2`, RMSD `2.3/3.5` (MOCK) | poses reales | ✓ | `MEDIUM` |
| **Hotspots** | LEU718 (imp=0.9), ASP855 (1.0), LYS745 (0.8) | `result.target_hotspots` + `result.hotspots_hit` | ✓ existe | `MEDIUM` |

### K · Análisis Detallado (Expandible)

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Componente listo | Brecha |
|----------------|--------------------|--------------------| ------------------| ------ |
| **Explicabilidad SHAP** | 6 features MOCK (`ecif_C_C: +0.23`, etc.) con barras | `ProXaiTab` con diagrama SHAP de abejas direccional + explicaciones científicas por feature. 18 features documentadas en `SHAP_EXPLANATIONS`. Modal expandido por feature | `ProXaiTab` ✓ (348 líneas) | `HIGH` — componente existe pero no se usa. Usa `shap_values` real |
| **Farmacóforos GNN** | pentágono MOCK (Aromáticos 45%, Donadores H 28%, ...) | `ProXaiTab` con radar pentagonal real + SVG de topología 2D (`gnn_attention_svg`) | `ProXaiTab` ✓ (misma función, polyline SVG) | `HIGH` |
| **Selectividad Anti-Target** | 3 anti-targets MOCK en formato simplificado (solo nombre, afinidad, safe/risk badge) | `ProSelectivityPanel` con 5 anti-targets detallados + biología + mitigación SAR + Ki estimado + botón "Evaluar" / "Evaluar Todos" + veredicto clínico + ratio + safety flags | `ProSelectivityPanel` ✓ (553 líneas, LA MÁS RICA) | `HIGH` — el mock muestra solo 3 anti-targets sin biología. El panel real tiene 5 con detalle exhaustivo |
| **Ratio Selectividad** | `1.8×` (MOCK), `selectivo` (MOCK) | calculado en vivo de `onTargetAffinity / worstOffAffinity` | `ProSelectivityPanel` línea 140-157 | `HIGH` |
| **Metadatos** | Vina 1.2.7, Seed 42, sdf, Normal, gpcr, ρ=0.48 | mismos campos reales (`vina_version`, `vina_random_seed`, `parsing_source`, `is_control`, `target_family`, `target_spearman_rho`) | ✓ pero `target_family` ausente de `EvaluationResult` | `LOW` — wiring |

### L · Scientific Warnings

| Elemento en UI | ¿Qué ve el usuario? | ¿Qué DEBERÍA ver? | Componente listo | Brecha |
|----------------|--------------------|--------------------| ------------------| ------ |
| **Warnings** | 1 warning MOCK (`"El SA Score 2.1 indica excelente accesibilidad sintética."`) | `result.scientific_warnings[]` clasificados por severidad (Positivo/Precaución/Crítica/Nota) en `ProAlertsTab` | `ProAlertsTab` ✓ (118 líneas) | `MEDIUM` — componente existe, solo wiring |

### M · Acciones Post-Evaluación (SAR, MMGBSA, Blockchain)

| Elemento | ¿Visible en el mock? | ¿DEBERÍA ser visible? | Componente/endpoint listo | Brecha |
|----------|---------------------|----------------------| ---------------------------| ------ |
| **Análisis SAR** | NO aparece en el mock | botón "Análisis SAR" → `getSarData(moleculeId)` → modal con tabla de análogos (similitud, ΔScore, ΔAfinidad, QED, Lipinski) | `ProResults` ✓ integra el botón. `getSarData` ✓ en `proApi.ts` línea 350 | `MISSING` de la UI actual |
| **Refinamiento MM-GBSA** | NO aparece | botón "Refinamiento MM-GBSA" → `runMmgbsa(...)` → modal con ΔG total + por pose, ΔGbind, solvatación, etc. | `ProResults` ✓ integra el botón. `runMmgbsa` ✓ línea 153 | `MISSING` |
| **Verificar Firma Blockchain** | NO aparece | botón "Verificar Firma" → `verifyBlockchainSignature(tx)` → modal valid/invalid + metadata Solana | `ProResults` ✓ integra el botón. `verifyBlockchainSignature` ✓ línea 366 | `MISSING` |
| **Descargar Complejo PDB** | placeholder `alert()` | botón funcional → `getComplexFile(id)` → blob PDB | `ProResults` ✓. Handler en `page.tsx` línea 233 | `CRITICAL` — placeholder |
| **Descargar Certificado PDF** | placeholder `alert()` | botón funcional → `downloadCertificate(id)` → blob PDF | `ProResults` ✓. Handler en `page.tsx` línea 225 | `CRITICAL` — placeholder |

### N · Tabs — Parámetros, Alertas, Explicabilidad, Selectividad

| Tab | ¿Visible en el mock? | ¿Componente listo? | Muestra | Brecha |
|-----|---------------------|---------------------|---------| ------ |
| **Parámetros** | NO — el mock muestra parámetros embebidos en secciones, no como tab | `ProParametersTab` ✓ (141 líneas) | QED, SA Score, MW, LogP + **ADMET completo** (Solubilidad LogS, PPB, HIA permeable, BBB, Reactividad Sistémica/TabPFN) + SA Reasons | `MISSING` — el mock no tiene tabs. El componente muestra ADMET+TabPFN que NO está en el mock visual |
| **Alertas** | NO como tab | `ProAlertsTab` ✓ (118 líneas) | warnings clasificados por severidad con badges color (Positivo/Precaución/Crítica/Nota) | `MISSING` |
| **Explicabilidad (XAI)** | PARCIAL — mock muestra SHAP en sección expandible, sin tabs | `ProXaiTab` ✓ (348 líneas) | SHAP bee swarm + GNN SVG + radar farmacóforos + modal por feature | `HIGH` — el mock muestra SHAP simplificado (6 features sin expandir). El componente real tiene 18+ features con explicaciones científicas |
| **Selectividad** | PARCIAL — mock muestra 3 anti-targets simplificados en sección expandible | `ProSelectivityPanel` ✓ (553 líneas) | 5 anti-targets con biología completa + SAR + Ki + botones "Evaluar" | `HIGH` — el mock es una versión MUY reducida. El panel real es el componente más rico de la app |

---

## Matriz de Completitud

| Zona de UI | Cantidad de elementos | MOCK (fake) | REAL (cableado) | MISSING (ni mock ni real) |
|-----------|----------------------|-------------|-----------------|---------------------------|
| Editor 2D + SMILES + Visor 3D + Target | 4 | 0 | 4 | 0 |
| Botones de Control | 2 | 2 | 0 | 3 (config, engine, stages) |
| Pantalla Processing | 2 | 1 (orb) | 0 | 1 (stages cards) |
| Hero Score | 3 | 3 | 0 | 0 |
| Hero Botones de Acción | 7 | 5 (MOCK) + 2 (alert) | 0 | 0 |
| DOT Timeline | 10 valores | 10 | 0 | 0 |
| Drug-likeness | 8 checks | 8 | 0 | 0 |
| ADMET | 6 métricas | 6 | 0 | 0 |
| Propiedades FQ | 10 propiedades | 10 | 0 | 0 |
| Docking Poses & Hotspots | 3 poses + 3 hotspots | 6 | 0 | 0 |
| Análisis Detallado (SHAP+GNN+Selectividad+Metadatos) | ~25 valores + ~9 métricas | todos MOCK | 0 | 0 |
| Acciones Post (SAR/MMGBSA/Blockchain) | 0 visibles | 0 | 0 | 3 (existen componentes, no visibles) |
| Tabs (4 tabs) | 0 | 0 | 0 | 4 tabs enteros invisibles |
| **TOTAL** | ~95+ elementos | **~87% MOCK** | **~4% REAL** | **~9% MISSING** |

---

## El Verdicto

| Categoría | Grados |
|-----------|--------|
| **Diseño visual** (mock) | 95% completo — el mock es excepcionalmente detallado, cada sección tiene dimensiones precisas, transiciones GSAP, tier colors, íconos Lucide correctos |
| **Componentes huerfanos** (listos para wiring) | 85% — de los 11 componentes, TODOS están bien tipados, reciben exactamente `EvaluationResult` o sus campos, los nombres de props coinciden con los nombres de campo del type |
| **Wiring a backend** (en `evaluation/page.tsx`) | 80% — `handleSubmit`, `handleSave`, `handleCertify`, `handleDownloadCertificate`, `handleDownloadComplex`, `handleReset`, `handleValidate`, `startPolling`, `stopPolling`... todos existen en la page. Solo `ProEvaluation` los ignora |
| **Datos en `EvaluationResult` type** | 65% — de ~60 campos que el mock visual muestra, ~45 tienen correspondencia en el type. ~15 campos (sección 1.7 del inventario) necesitan verificación contra el backend. |
| **Stream SSE del pipeline** | 40% — el stream existe (`pipelineStream.ts`) pero no se sabe qué `stage_id`s emite el backend. Necesita pruebas. |
| **Overall readiness** | **Listo para reconectar tuberías** — los componentes están construidos, los tipos definidos, las funciones API existen. Solo falta unirlos. |

---

## Prioridades de Wiring (orden sugerido)

| # | Tarea | Impacto | Complejidad | Dependencias |
|---|-------|---------|-------------|--------------|
| 1 | Verificar campos reales del backend corriendo un job real y comparando JSON con `EvaluationResult` type | Fundacional | Baja (1 hora) | Backend corriendo |
| 2 | Definir `stage_id`s del pipeline (leer `api/main.py` o preguntar a equipo backend) | Fundacional | Baja | #1 |
| 3 | Conectar botón "Ejecutar Evaluación" a `handleSubmit` real | Crítico (es lo que el usuario quiere hacer) | Media | #1 |
| 4 | Cambiar trigger del processing screen de `showMockResults && isProcessing` a `busy || status === "PENDING"/"PROGRESS"` | Crítico | Baja | #3 |
| 5 | Integrar `StageCard[]` + suscribir a `subscribeToPipelineEvents` durante el processing | Alto (feedback en vivo) | Media | #2, #3 |
| 6 | Montar `ProConfigPanel` + `DockingEnginePanel` (zona izq colapsable "Opciones Avanzadas") | Alto (control del usuario) | Media | ninguna |
| 7 | Al recibir `status === "SUCCESS"`, renderizar `ProResults` + `ProAnalysisTabs` en lugar del mock | Crítico (resultados reales) | Alta | #1, #3 |
| 8 | Cablear botones de acción (Guardar, Certificar, Descargar) a handlers reales | Crítico (post-proceso) | Baja | #7 |
| 9 | Reemplazar secciones del mock (drug-likeness, ADMET, props, poses, hotspots) por datos de `result` reales | Alto | Media | #7 |
| 10 | Montar `ProSelectivityPanel` con wiring real al tab "Selectividad" | Alto (el componente más rico) | Media | #7 |
| 11 | Agregar acciones post-evaluación (SAR, MMGBSA, Blockchain Verify) que el mock no tiene | Medio | Media | #7 |
| 12 | Remover el mock `MOCK` object y limpiar estados fake (`showMockResults`, `isProcessing`, `isSavedMock`, `isCertifiedMock`) | Bajo (cleanup) | Baja | #4, #7, #8, #9 |
| 13 | Refactor CDN → all-local en `AdvancedMolstarViewer` (molstar CSS/JS) | Medio (CSP compliance) | Baja | ninguna |
| 14 | Aplicar `review-animations` skill a las transiciones existentes | Bajo (polish) | Baja | #7 |

---

**END — Cross-Validation completa de la pestaña Evaluación.**
