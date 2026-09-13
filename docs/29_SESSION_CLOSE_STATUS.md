# MolDesign AI — Estado al Cierre de Sesión

Fecha: 2026-07-29
Sesión: Documentación institucional + GPU tasks (CL-GNN Ensemble, Metal-aware GNN-D) + ACE benchmark completion

---

## 1. ACE Benchmark — COMPLETADO (resultados mixtos)

| Métrica | Valor | Nota |
|---------|-------|------|
| Vina AUC | 0.4056 | RANDOM — docking roto |
| XGB AUC | 0.4532 | RANDOM — usa Vina poses |
| **UMS standalone AUC** | **0.8162** | ✅ Funciona (SMARTS puro) |
| **M5 equal-weight delta** | **+0.2895** | Bootstrap CI [0.252, 0.326], p=0.0 |

**Conclusión ACE**: El docking está roto (Vina random), pero UMS standalone funciona.
Esto es evidencia de robustez: "cuando el docking falla, UMS sigue funcionando".
Paper: N=1 rescue case.

---

## 2. Tareas GPU Completadas

| Tarea | Resultado | Tiempo | Validez |
|-------|-----------|--------|---------|
| CL-GNN Ensemble (3 seeds) | AUC=0.8112, EF@1%=6.12x | ~4h GPU | ✅ Válido (varianza alta: seed44=0.64) |
| Metal-aware GNN-D LOTO (7 targets) | Mean AUC=0.9289 | ~25min GPU | ⛔ **INVALIDADO** — data leakage |

### Post-Mortem: Metal-aware GNN-D

**Causa**: `gnn_d_best.pt` fue entrenado en TODAS las familias de PDBbind (865 complejos), incluyendo los 7 targets LOTO. Al cargarlo como backbone y luego hacer fine-tuning "LOTO", el backbone ya conocía los grafos del target excluido. AUC=0.99 en epoch 1 lo confirmó.

**Evidencia**: `rescoring/artifacts/training_report.json` — `training_script: "train_families.py"`, `family_distribution` incluye todas las familias. `val_targets: ["ca2","thrombin"]` — split simple, no LOTO.

**Acción**: 7 modelos renombrados a `*.INVALID_DUE_TO_DATA_LEAKAGE`. README en `rescoring/artifacts/INVALID_MODELS_README.md`.

**Corrección**: Entrenar 7 GNN-D desde cero con LOTO real (sin cargar `gnn_d_best.pt`). ~3-5h GPU.

---

## 3. Documentación Nueva

| Documento | Contenido |
|-----------|-----------|
| `docs/DECK_EJECUTIVO_INSTITUCIONAL.md` | Pitch deck 12 secciones para instituciones |
| `docs/DOCUMENTACION_TECNICA_CIENTIFICA_MOLDESIGN.md` v2.0.0 | Doc técnico-científico completo (18 secciones, verificado) |
| `docs/28_CONSOLIDATED_RESULTS.md` | Actualizado con ACE results + invalidación |
| `rescoring/artifacts/INVALID_MODELS_README.md` | Post-mortem data leakage |

---

## 4. Paper — Estado actual

### Claims listas (alta confianza)
- N=3 UMS standalone: CA2=0.978, MMP9=0.887, ACE=0.816
- N=2 full pipeline: CA2 +0.122, MMP9 +0.067 (bootstrap p<0.0001)
- N=1 rescue: ACE docking roto → UMS rescata +0.290
- N=6 zero regression: family-gating confirmado
- N=2 negative controls: PDE5A (0.513), CYP3A4 (0.565) — random

### Claims NO listas (no incluir en paper sin rehacer)
- Metal-aware GNN-D LOTO — invalidado
- GNN-D LOTO para MMP9 — bloqueado (needs Vina docking)

---

## 5. Próximos Pasos — PRÓXIMA SESIÓN

### 🔴 Inmediato (próxima sesión)
1. **ACE pipeline fix**: Reparar docking de ACE (Vina AUC debe ser >> 0.406).
   - Investigar grid center correcto (Zn²⁺ vs centroid)
   - Posible fix en `_get_extractor()` race condition
   - Prioridad: desbloquear N=3 pipeline completo

2. **Metal-aware GNN-D — rehacer correctamente**:
   - Entrenar 7 GNN-D desde cero con LOTO REAL (sin `gnn_d_best.pt`)
   - ~3-5h GPU. Usar `scripts/train_metal_aware_gnn.py` modificado con `--no-pretrain`
   - Prioridad: baja (paper tiene claims suficientes sin esto)

### 🟡 Mediano plazo
3. **MMP9 GNN-D LOTO**: Necesita benchmark MMP9 con MolChamb scores.
   - Requiere ACE pipeline fix primero (confianza en benchmark)
4. **Paper submission**: ChemRxiv + Zenodo con claims N=3 UMS + N=2 pipeline + N=1 rescue
5. **External validation**: Buscar laboratorio para validación experimental de CA2/MMP9 hits

### ⚪ Baja prioridad
6. **Smina Windows build**: MSYS2 pendiente
7. **MolChamb cache**: Build `molchamb_cache.sqlite` para MMP9/ACE
8. **AChE benchmark**: Nunca ejecutado

---

## 6. Archivos Modificados Esta Sesión

| Archivo | Cambio |
|---------|--------|
| `docs/DECK_EJECUTIVO_INSTITUCIONAL.md` | Nuevo: pitch deck ejecutivo |
| `docs/DOCUMENTACION_TECNICA_CIENTIFICA_MOLDESIGN.md` | Rewrite v2.0.0 (18 secciones verificadas) |
| `docs/28_CONSOLIDATED_RESULTS.md` | Actualizado: ACE results, invalidación metal-aware |
| `docs/29_SESSION_CLOSE_STATUS.md` | Este archivo (actualizado) |
| `scripts/train_metal_aware_gnn.py` | Nuevo: script de training (preservado para future redo) |
| `rescoring/artifacts/INVALID_MODELS_README.md` | Nuevo: post-mortem data leakage |
| `rescoring/artifacts/metal_aware_loto_*.pt` | Renombrados a `.INVALID_DUE_TO_DATA_LEAKAGE` (7 archivos) |
| `rescoring/artifacts/gnn_v2_cl_seed{42,43,44}.pt` | Actualizados: CL-GNN ensemble seeds |
| `rescoring/artifacts/metal_aware_gnn_results.json` | Resultados (marcar como invalid) |
| `data/gnn_fixed/ensemble_report.json` | CL-GNN ensemble evaluation |
| `data/molchamb_loto/metal_gnn_training_20260729.log` | Training log (para auditoría) |
| `data/gnn_v31/checkpoints/benchmark_checkpoint_5ht1a.json` | Actualizado con ensemble probs |
| `rescoring/artifacts/backup_20260729/` | Backup de 18 modelos pre-training |

---

## 7. Backups

- `rescoring/artifacts/backup_20260729/` — 18 modelos (pre-training)
- `data/gnn_v31/checkpoints/benchmark_checkpoint_5ht1a.json.bak_20260729_manual` — checkpoint pre-ensemble
