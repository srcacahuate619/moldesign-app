# Documentación Histórica — MolDesign

> **Este directorio contiene un subconjunto crítico de la documentación histórica**
> del proyecto principal **`moldesign-app`** (repositorio origen del cual `moldesign-build`
> es un fork "destilado" para distribución desktop Windows nativa).

## ¿Por qué estos docs aquí?

El fork `moldesign-build` se creó para empaquetar la aplicación como un `.exe` standalone
offline (Tauri + Python embed + modelos). En ese proceso **se perdieron los docs que justifican
las decisiones científicas e ingenieriles**. Sin ellos, una auditoría externa no puede
distinguir entre:

- **Decisiones intencionales documentadas** (ej: FEATURE_GROUP_B Vina = 0 en training tras experimento empírico que mostró que no mejoraba Spearman)
- **Errores genuinos** (ej: scripts que fabrican métricas con mocks circulares)

Estos 4 documentos son el **mínimo indispensable** para que cualquier revisor (peer review,
auditoría, tú en 6 meses) entienda el *porqué* del estado actual.

---

## Archivos incluídos

| Archivo | Qué explica | Referencia en auditoría |
|---------|-------------|------------------------|
| `07_SPEARMAN_BENCHMARK_LOG.md` | Bitácora completa de 8 experimentos iterativos (hipótesis → resultado → lección). Incluye: abandono de regresión por clasificación, quality gate, delta-learning descartado, MM-GBSA protein-only descartado, Early Exit, validación DUD-E bias con 3 tests. | Corrige 5 falsos positivos del auditor científico. |
| `08_SCIENTIFIC_VALIDATION.md` | Validación científica formal: ProLIF (3 evidencias: 5-HT1A ρ=-0.035 + SHAP rank 117-172 + ablation ECIF 0.68 > ALL 0.60), ablation v1.2 vs v1.3, test set holdout scaffold-disjoint de 328 complejos (Spearman 0.6094 [CI95 0.528–0.679]; el 0.8732 histórico está INVALIDADO por leakage), SHAP feature importance, discrepancies bloqueantes + alta + media resueltas. | Justifica exclusión ProLIF, Vina 0 en training, NDCG trivial, model_a_universal. |
| `10_VINA_GPU_HYBRID.md` | Módulo GPU externo (`D:\ad-gpu-project\`) — Vina-GPU 2.1 compilado desde source (OpenCL), 3 modos (CPU idéntico, GPU search + CPU refine, batch GPU). Experimentos: parallel CPU 2.4×, GPU→CPU 40×, multi-pose 15×, GPU `--refine` 32× con Δ=0.02. EF@1% 2.24× vs 1.10× CPU histórico. | Contexto de por qué Vina-GPU NO está en producción (FP32 vs FP64, decisiones de packaging). |
| `16_AUDIT_FIXES.md` | Registro de 3 auditorías, 24 hallazgos, todos mitigados. Cubre: imports missing, credentials leaks, conda vs pip, diagrama inicio, params API, contradicción ablation, modelo ignora ablation, test set no evaluado (evaluado: 0.6094 honesto; 0.8732 INVALIDADO por leakage), CDK2/CDK4, Python versions, numeración, Mermaid, tools count, Spanglish, data loss ML/GNN, O(N²) MolGraph, SQLite concurrency, ADMET memory leak, Vina FP32 vs FP64, dedup sales, Windows subprocesos, dispatcher loops. | Historia de remediación completa hasta v1.5. |
| `17_EF_BENCHMARK_FIXES.md` | Bug fixes del pipeline EF@1% (RingInfo, composite formula, chain sanity) + re-corrida full-scale 5 targets. Parte 5 agrega GNN-v2 fix (logger crash), re-score de checkpoints y optimización de stacking weights. Resultados: AUC prom 0.958, EF@1% prom 27.11x. | Cierra loop de bugs que impedían reproducir los históricos. |
| `18_OSS_ROADMAP.md` | Hoja de ruta open source: AGPL-3.0 (código) + CC-BY-NC-SA 4.0 (modelos) + EULA custom para .exe. 6 fases: 5HT1A focused box → re-corrida + metricas → OSS readiness → legal HD → paper JCIM → frontend → release público. | Plan de trabajo hacia publication y comunidad. |
| `19_LIMITATIONS.md` | Limitaciones del pipeline MolDesign v1: silent-fails en DNA/RNA/glycan pockets, boro/selenio en ligandos, `_detect_dominant_chain` heurístico, `compute_dynamic_box` implementado desde Bucket B (pendiente de benchmark de calidad). Plan de remedio en 3 buckets (A: fix silent-fails, B: cablear dynamic box, C: GNN-v3 universal research track). | Documentación honesta para paper + roadmap v3. |

---

## Repositorio principal (fuente de verdad completa)

**`moldesign-app`** — contiene:
- Los 44 docs completos (`docs/00_INDEX.md` hasta `17_STEAM_DEPLOYMENT.md`)
- ADRs (`docs/adr/`)
- Papers en preparación (`docs/posibles_papers/`)
- Benchmarks GPU completos (`11_GPU_BENCHMARK_RESULTS.md`, `12_BENCHMARK_SETUP.md`, `13_DIARIO_EXPERIMENTOS_GPU.md`)
- Target library docs (`14_TARGET_LIBRARY.md` — 273 targets validados en 20 áreas)
- Batch screening (`15_BATCH_SCREENING.md`)
- MolGraph, MolChamb, MolChat arquitectura
- Session summaries v1.3 → v1.7

> **Si auditas este fork y algo no cuadra, ve a `moldesign-app/docs/`. La historia completa está ahí.**

---

## Estado actual de la remediación (Julio 2026)

| Fase | Tarea | Estado |
|------|-------|--------|
| **Punto 0** | Fork privado + git init + .gitignore + commit base | ✅ `fc71faa` |
| **Punto 1** | Traer docs históricos críticos | ✅ 4 docs copiados + este README |
| **Punto 2** | Aislar scripts fabricados en `rescoring/deprecated/` | ⏳ Siguiente |
| **Punto 3** | Promover `evaluate_test_set.py` como benchmark canónico + bootstrap CI | ⏳ Pendiente |
| **Punto 4** | Fix ESMFold sequence extraction ("X"*n → 20 AA SMARTS) | ⏳ Pendiente |
| **Punto 5** | Bloquear RFdiffusion fallback dummy `success=True` | ⏳ Pendiente |
| **Punto 6** | Borrar duplicados `app_backup_20260722/` + `chemistry/chemistry/` | ⏳ Pendiente |
| **Punto 7** | Pin deps ML + `cudnn.deterministic` | ⏳ Pendiente |

---

## Nota para revisores

Si estás revisando este código como parte de una peer review, auditoría o due diligence:

1. **Lee `08_SCIENTIFIC_VALIDATION.md` primero** — establece el rigor metodológico.
2. **Lee `07_SPEARMAN_BENCHMARK_LOG.md` para el proceso científico** — 8 experimentos, no cherry-picking.
3. **Los "errores" del auditor científico en 5/9 puntos eran falsos positivos** — las decisiones estaban documentadas en `moldesign-app/docs/` y no llegaron al fork.
4. **Los 4 problemas CRÍTICOS reales** (scripts fabricados, ESMFold "X"*n, RFdiffusion dummy, `cudnn.deterministic`) **sí son reales y están en el plan de remediación**.

La transparencia sobre qué era decisión intencional vs qué era error real es lo que permite que este proyecto sea reproducible y publicable.

---

*Generado automáticamente como parte del Punto 1 de la remediación post-auditoría 2026-07-23.*