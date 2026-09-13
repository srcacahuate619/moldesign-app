> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# Resumen de Sesión — Julio 2026 (v1.5)

## Objetivo

Preparar MolDesign AI para distribución comercial en Steam ($49.99 base + $49.99 DLC Pro), mitigando todas las auditorías externas y completando los requisitos técnicos para un producto vendible.

---

## 1. Auditorías Mitigadas (3 auditorías, 24 hallazgos)

### Auditoría 1 — Reporte de Proyecto (16 hallazgos)

| # | Hallazgo | Fix |
|---|----------|-----|
| 1 | Imports rotos en modo DESKTOP | `_cleanup_molecule_direct()`, dispatcher DEPRECATED |
| 2 | Credenciales expuestas en docs | 7 leaks sanitizados en 5 archivos + `query_db.py` |
| 3 | Inconsistencia conda-pack vs pip | Docs marcados SUPERSEDED, `09_PACKAGING_STRATEGY.md` canónico |
| 4 | Diagrama desactualizado | Removido `Rescoring :8001`, diagrama actualizado |
| 5 | Parámetros corruptos API docs | `um_workers→num_workers`, `um_steps→num_steps`, caracteres BEL |
| 6 | Contradicción ablation | ECIF-only era mejor en modelo VIEJO con ProLIF; nuevo modelo supera |
| 7 | Modelo ignora ablation | `model_a_universal.json` (167 feat, Spearman 0.764 CV, 0.873 test) |
| 8 | Test set sin evaluar | Evaluado: **Spearman 0.8732** en 327 complejos holdout |
| 9 | Error CDK2/CDK4 (PDB 3PP0) | Corregido + advertencia científica |
| 10 | Versiones Python conflicto | Documentado como legacy |
| 11 | Numeración duplicada | `11_STRESS_TEST` → `12_STRESS_TEST` |
| 12 | Comentarios obsoletos | `train_families.py` actualizado |
| 13 | Párrafos duplicados | `01_PIPELINE.md` limpiado |
| 14 | Mermaid roto | ADMET corregido |
| 15 | Conteo tools inconsistente | **20 tools** (16 offline + 4 online) |
| 16 | Spanglish | Español técnico oficial |

### Auditoría 2 — Técnica Profunda (5 hallazgos)

| # | Hallazgo | Fix |
|---|----------|-----|
| 1 | Pérdida datos ML/GNN en reportes | +8 columnas DB, persistencia completa, endpoints ML-aware |
| 2 | Bottleneck O(N²) MolGraph | Fingerprint cache RAM + `run_in_executor` |
| 3 | Concurrencia SQLite Desktop | Retry logic, `busy_timeout=15s`, `max_workers=1` |
| 4 | Memory leak ADMET-AI | Idle timer 5min + `gc.collect()` + fix double instantiation |
| 5 | Sesgo Vina FP32/64 | Vina-GPU removido, `vina.exe` nativo FP64 |

### Auditoría 3 — Backend (3 hallazgos)

| # | Hallazgo | Fix |
|---|----------|-----|
| 1 | Duplicados por sales | `smiles_to_hash` desalina con `SaltRemover` |
| 2 | Subprocesos Windows (selectividad) | `selectivity.py` + `batch.py` con `Semaphore`, sin threads |
| 3 | Loops dispatcher Desktop | `max_workers=1` + retry logic |

---

## 2. Features Nuevas (v1.5)

| Feature | Archivos | Impacto |
|---------|----------|---------|
| **Modelo universal default** | `config.py`, `rescoring_service.py`, `model_router.py` | Spearman 0.8732 en test set |
| **Test set evaluation** | `rescoring/evaluate_test_set.py` | 327 complejos, métrica independiente |
| **Batch multi-target** | `batch.py`, `batch/page.tsx` | ALL targets, early exit, EF metrics |
| **Target library (386)** | `scripts/curate_target_library.py`, `scripts/seed_*` | 20 áreas, 273 validados |
| **Heartbeat anti-zombie** | `main.py` | `_parent_heartbeat()` cada 2s |
| **Offline PDB cache** | `file_handlers.py` | Cache local antes de RCSB |
| **UI zoom support** | `layout.tsx`, `globals.css` | `data-zoom="100|120|150"` |
| **Auto-ingesta targets** | `queue_handler.py` | Cualquier PDB ID → download + prepare automático |
| **Friendly error mapping** | `frontend/lib/errors.ts` | 50+ errores técnicos → español legible |
| **Steamworks billing** | `api/routers/steam.py` | `GET /steam/verify` con Steam Web API |
| **Crash reporting** | `main.py` | Sentry con sanitización de SMILES |
| **ESMFold real** | Pesos descargados (8 GB) | `esmfold/models/pytorch_model.bin` |
| **Grid box validation** | `vina_service.py` | Warning si ligando > caja |
| **Chirality detection** | `validator.py` | Warning si estereocentros sin `@`/`@@` |

---

## 3. Documentación Nueva

| Documento | Contenido |
|-----------|-----------|
| `14_TARGET_LIBRARY.md` | 386 targets en 20 áreas, pipeline de ingestión, scripts |
| `15_BATCH_SCREENING.md` | Batch screening: multi-target, early exit, EF, formatos, flujo |
| `16_AUDIT_FIXES.md` | Registro completo de 24 bugs corregidos, 35+ archivos |
| `17_STEAM_DEPLOYMENT.md` | Steamworks billing, Cloud, MSVC, code signing, Sentry |
| `TOS_PRIVACY.md` | Términos de servicio + política de privacidad |

---

## 4. Archivos Modificados (35+)

### Backend
```
backend/core/models.py              +8 columnas ML scores
backend/db/repository.py            Persistencia ML scores
backend/api/routers/evaluation.py   Endpoints ML-aware, canonical SMILES
backend/api/routers/batch.py        Multi-target, early exit, EF metrics
backend/api/routers/steam.py        NUEVO: Steamworks verification
backend/services/docking/queue_handler.py  Cleanup, auto-ingesta, lazy Celery, max_workers=1
backend/services/docking/selectivity.py    Reescrito sin threads
backend/services/docking/vina_service.py   Sin GPU binary, grid validation
backend/services/ai/molgraph.py     Fingerprint cache, sin pickle
backend/services/ai/tools/admet_tools.py   Usa singleton
backend/services/ai/tools/molgraph_tool.py run_in_executor
backend/chem/validator.py           smiles_to_hash desalina, chiral warning
backend/chem/blood_viability.py     Idle offloading timer
backend/core/config.py              Vina nativo, model_a_universal
backend/core/database.py            Retry logic, busy_timeout 15s
backend/api/main.py                 Heartbeat + Sentry + Steam router
backend/utils/file_handlers.py      PDB offline cache
backend/tasks/dispatcher.py         DEPRECATED
backend/query_db.py                 Credenciales → env var
backend/services/rescoring_service.py model_a_universal
backend/requirements.txt            280→147 líneas, sin duplicados
```

### Rescoring
```
rescoring/config.py                 model_a_universal.json
rescoring/model_router.py           CPU path → universal
rescoring/evaluate_test_set.py      NUEVO: test set evaluation
rescoring/train_families.py         Comentarios corregidos
```

### Frontend
```
frontend/app/evaluation/batch/page.tsx  Multi-target, early exit, EF UI, friendly errors
frontend/app/layout.tsx             data-zoom
frontend/app/globals.css            Zoom CSS
frontend/lib/errors.ts              NUEVO: friendly error mapping (50+ entradas)
```

### Scripts Nuevos
```
scripts/curate_target_library.py    Descargar PDBs por área terapéutica
scripts/seed_target_library.py      Registrar PDBs en DB con grid detection
scripts/seed_curated_targets.py     Registrar 80 targets de curated_targets.csv
scripts/seed_all_targets.py         Registrar 19 targets principales
scripts/validate_targets_fast.py    Smoke test: preparar receptor PDBQT
scripts/validate_targets.py         Validación completa: redocking + RMSD
scripts/discover_new_targets.py     Estimar targets en RCSB sin descargar
scripts/discover_remaining_areas.py Buscar targets en nuevas áreas
scripts/bundle_pdbs.py             Empaquetar PDBs para instalador Steam
scripts/download_esmfold_weights.py Descargar pesos ESMFold (~8 GB)
```

### Docs (13 corregidos/actualizados + 5 nuevos)
```
docs/00_INDEX.md                    v1.5, nuevos docs en TOC
docs/01_PIPELINE.md                 Párrafos duplicados, Mermaid, caracteres
docs/02_DESKTOP.md                  Diagrama actualizado
docs/03_API.md                      Parámetros corruptos
docs/05_CLOUD_DEPLOY.md             Credenciales
docs/06_FAMILY_RETRAINING.md        Tabla modelos, feature mismatch
docs/08_SCIENTIFIC_VALIDATION.md    Ablation corregido, v1.3, test set
docs/09_PACKAGING_STRATEGY.md       Canónico
docs/14_TARGET_LIBRARY.md           NUEVO
docs/15_BATCH_SCREENING.md          NUEVO
docs/16_AUDIT_FIXES.md              NUEVO
docs/17_STEAM_DEPLOYMENT.md         NUEVO
docs/TOS_PRIVACY.md                 NUEVO
docs/auditoria_empaquetado_desktop.md SUPERSEDED
docs/Plan_Multiplataforma.md        SUPERSEDED
docs/campana_multitarget.md         CDK2/CDK4 corregido
docs/Interprete_IA.md               Tabla de tools
docs/adr/0001-app-mode-pattern.md   Nombre corregido
```

---

## 5. Estado del Proyecto — Métricas Clave

| Métrica | Valor |
|---------|-------|
| Targets en DB | **386** (273 validados, 20 áreas) |
| Spearman test set | **0.8732** (327 complejos, p<0.0001) |
| Modelo producción | `model_a_universal.json` (167 features) |
| Bugs corregidos | **24** (3 auditorías) |
| Features nuevas | **13** |
| Archivos modificados/creados | **50+** |
| Docs nuevos/actualizados | **18** |
| ESMFold | Pesos descargados (8 GB), modo `fast` |

---

## 6. Lo Que Falta Para Steam (checklist de despliegue)

### Bloqueantes (no se puede publicar sin esto)
- [ ] Comprar certificado de firma de código (~$300/año Sectigo/DigiCert)
- [ ] Crear cuenta Steamworks Partner + obtener App ID
- [ ] Obtener Steam Web API Key para verificación de compra
- [ ] Configurar `STEAM_WEB_API_KEY` + `STEAM_APP_ID` en `.env`
- [ ] Build del instalador `.msi` con Tauri + Python embed + wheelhouse + PDBs
- [ ] Probar en VM Windows limpia (sin Python, sin RDKit, sin nada)

### Alta Prioridad (afecta UX significativamente)
- [ ] Configurar MSVC Redistributables en Steamworks Dashboard (checkbox)
- [ ] Configurar Steam Cloud saves (checkbox + paths)
- [ ] Ejecutar `bundle_pdbs.py` + incluir en el `.msi` (~60 MB)
- [ ] Crear store page en Steam (screenshots, trailer, descripción)
- [ ] Wire `friendlyError()` en evaluation page (EDU mode) — actualmente solo en batch
- [ ] Agregar tooltip "¿Qué significa esto?" en errores de docking

### Media Prioridad (mejora pero no bloquea)
- [ ] Empaquetar ESMFold weights como DLC Pro (8 GB, $49.99 extra)
- [ ] Steam Achievements (usar `steamworks.js`)
- [ ] Tutorial/onboarding (5 pasos: "diseñá tu primera molécula")
- [ ] Sentry DSN en `.env` para crash reporting en producción
- [ ] Ejecutar `validate_targets.py` overnight para RMSD de todos los targets

### Baja Prioridad (post-launch)
- [ ] MacOS / Linux builds (Steam Deck — Proton funciona para MVP)
- [ ] MM-GBSA fix (actualmente roto/lento)
- [ ] RFdiffusion / ESMFold-Pro (requiere GPU, DLC Pro)
- [ ] Steam Leaderboards (competencia global de scores)
- [ ] Analytics dashboard para entender uso

---

## 7. Scripts de Despliegue (orden de ejecución)

```powershell
# 1. Empaquetar PDBs para el instalador
python scripts/bundle_pdbs.py --output dist/steam_assets/pdbs

# 2. Build del frontend (Next.js static export)
cd frontend; npm run build

# 3. Build del instalador Tauri (.msi)
cd frontend; npm run tauri build

# 4. Firmar binarios (requiere certificado)
.\scripts\sign.ps1

# 5. Subir a Steamworks (via SteamPipe o web dashboard)
```

---

## 8. Scripts de Primer Arranque (en el instalador)

Estos se ejecutan automáticamente en el primer lanzamiento:

```powershell
# 1. Seed de la DB con todos los targets
$env:APP_MODE="DESKTOP"
cd backend
python scripts/seed_all_targets.py
python scripts/seed_curated_targets.py
python scripts/seed_target_library.py

# 2. Smoke test de preparación de receptores
python ../scripts/validate_targets_fast.py
```
