# Registro de Bugs Corregidos — v1.5

> **3 auditorias, 24 hallazgos, todos verificados y mitigados.**
> **Julio 2026**

---

## Auditoria 1 — Reporte de Auditoria de Proyecto (16 hallazgos)

| # | Hallazgo | Severidad | Estado |
|---|----------|:---------:|:------:|
| 1 | Imports de modulos inexistentes en modo DESKTOP | Critico | Corregido — `_cleanup_molecule_direct()`, dispatcher DEPRECATED |
| 2 | Credenciales expuestas en documentacion | Critico | Corregido — 7 leaks sanitizados en docs + query_db.py |
| 3 | Inconsistencia conda-pack vs pip | Critico | Corregido — docs marcados SUPERSEDED, 09_PACKAGING canónico |
| 4 | Diagrama de inicio desactualizado | Critico | Corregido — removido Rescoring :8001 |
| 5 | Parametros corruptos en API docs | Alta | Corregido — um_workers→num_workers, caracteres BEL |
| 6 | Contradiccion en conclusiones del ablation | Alta | Corregido — ECIF-only era mejor en modelo viejo con ProLIF |
| 7 | Modelo ignora ablation (167 vs 56 features) | Alta | Corregido — universal 0.7731 CV (Fase A 2026-08-10), supera ECIF-only |
| 8 | Test set no evaluado | Alta | Corregido — evaluado. El 0.8732 histórico está INVALIDADO por leakage; holdout honesto scaffold-disjoint (Fase A retrain 2026-08-10): Spearman 0.6094 [CI95 0.528–0.679] en 328 complejos. No citar el 0.8732. |
| 9 | Error CDK2/CDK4 (PDB 3PP0) | Alta | Corregido — tabla + advertencia cientifica |
| 10 | Versiones Python en conflicto | Alta | Documentado como legacy |
| 11 | Numeracion duplicada (dos 11_) | Media | Corregido — renombrado |
| 12 | Comentarios obsoletos train_families.py | Media | Corregido |
| 13 | Parrafos duplicados 01_PIPELINE.md | Media | Corregido |
| 14 | Mermaid mal formateado ADMET | Media | Corregido |
| 15 | Conteo inconsistente de tools | Baja | Corregido — 20 tools (16 offline + 4 online) |
| 16 | Spanglish | Baja | Corregido — español tecnico oficial |

---

## Auditoria 2 — Reporte de Auditoria Tecnica Profunda (5 hallazgos)

| # | Hallazgo | Severidad | Estado |
|---|----------|:---------:|:------:|
| 1 | Perdida silenciosa de datos ML/GNN en reportes | Critico | Corregido — +8 columnas DB, persistencia completa, endpoints ML-aware |
| 2 | Cuello de botella O(N²) en MolGraph Tanimoto | Alta | Corregido — fingerprint cache en RAM, run_in_executor |
| 3 | Riesgo de concurrencia SQLite Desktop | Alta | Corregido — retry logic, busy_timeout 15s, max_workers=1 |
| 4 | Fuga de memoria ADMET-AI | Alta | Corregido — idle timer 5min + gc.collect + torch.cuda, fix double instantiation |
| 5 | Sesgo en benchmarks Vina (FP32 vs FP64) | Alta | Corregido — Vina-GPU removido de produccion, vina.exe nativo FP64 |

---

## Auditoria 3 — Reporte de Backend (3 hallazgos)

| # | Hallazgo | Severidad | Estado |
|---|----------|:---------:|:------:|
| 1 | Evasion de detector de duplicados por sales | Critico | Corregido — smiles_to_hash desalina con SaltRemover, evaluation.py usa canonical |
| 2 | Incompatibilidad subprocesos Windows (selectividad) | Critico | Corregido — selectivity.py + batch.py usan Semaphore sin threads |
| 3 | Inyeccion de loops en dispatcher Desktop | Alta | Corregido — max_workers=1 + retry logic |

---

## Features Nuevas (v1.5)

| Feature | Archivos |
|---------|----------|
| Modelo universal default | `config.py`, `rescoring_service.py`, `model_router.py` |
| Test set evaluation script | `rescoring/evaluate_test_set.py` |
| Batch multi-target + early exit + EF | `batch.py`, `batch/page.tsx` |
| Target library (386 targets, 20 areas) | `scripts/curate_target_library.py`, `scripts/seed_target_library.py` |
| Heartbeat anti-zombie | `main.py` |
| Offline PDB cache | `file_handlers.py` |
| UI zoom support | `layout.tsx`, `globals.css` |
| Auto-ingesta de targets | `queue_handler.py` |
| Seed scripts | `seed_all_targets.py`, `seed_curated_targets.py` |
| Discovery scripts | `discover_new_targets.py`, `discover_remaining_areas.py` |
| Validation scripts | `validate_targets_fast.py`, `validate_targets.py` |

---

## Archivos Modificados (35+)

| Archivo | Cambio |
|---------|--------|
| `backend/core/models.py` | +8 columnas ML scores |
| `backend/db/repository.py` | Persistencia ML scores |
| `backend/api/routers/evaluation.py` | Endpoints ML-aware, canonical SMILES |
| `backend/api/routers/batch.py` | Multi-target, early exit, EF metrics |
| `backend/services/docking/queue_handler.py` | Cleanup fix, auto-ingesta, lazy Celery, max_workers=1 |
| `backend/services/docking/selectivity.py` | Reescrito sin threads |
| `backend/services/docking/vina_service.py` | Sin GPU binary, grid validation |
| `backend/services/ai/molgraph.py` | Fingerprint cache, sin pickle en loop |
| `backend/services/ai/tools/admet_tools.py` | Usa singleton |
| `backend/services/ai/tools/molgraph_tool.py` | run_in_executor |
| `backend/chem/validator.py` | smiles_to_hash desalina, chiral warning |
| `backend/chem/blood_viability.py` | Idle offloading timer |
| `backend/chem/conformer.py` | Sin cambios (ya era correcto) |
| `backend/scoring/normalizer.py` | Sin cambios |
| `backend/core/config.py` | Vina nativo, model_a_universal |
| `backend/core/database.py` | Retry logic, busy_timeout 15s |
| `backend/api/main.py` | Heartbeat anti-zombie |
| `backend/utils/file_handlers.py` | PDB offline cache |
| `backend/tasks/dispatcher.py` | DEPRECATED |
| `backend/query_db.py` | Credenciales → env var |
| `backend/services/rescoring_service.py` | model_a_universal |
| `rescoring/config.py` | model_a_universal |
| `rescoring/model_router.py` | CPU path → universal |
| `frontend/app/evaluation/batch/page.tsx` | Multi-target, early exit, EF UI |
| `frontend/app/layout.tsx` | data-zoom |
| `frontend/app/globals.css` | Zoom CSS |
| 13 archivos `.md` en `docs/` | Correcciones + nuevos docs |
