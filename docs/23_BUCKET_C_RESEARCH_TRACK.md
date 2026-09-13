# 23 — Bucket C Research Track: GNN-v3 Universal

> **Fecha**: 2026-07-25
> **Estado**: Plan de investigación — no ejecutable en esta sesión, pero escencial para declaraciones paper-correctas.
> **Origen**: Post-mortem de Bucket A.1 (Sección 7 de `docs/19_LIMITATIONS.md`). Escrito después Stops point de la sesión donde el hot-patch (commit `4f48fde`) reveló que GNN-v2 no se puede usar para paper claims sin un retrain completo.
> **Filosofía**: "Un modelo que produce near-random AUC no es un modelo — es un placeholder. Si no lo reentrenamos, eliminamos los claims que dependen de él."

---

## TL;DR

| Goal | Estado | Blocking para paper? |
|------|--------|------------------------|
| **C1. GNN-v3 retrain con 30-element alphabet** | plan, ~5 sesiones compute | blocks paper v2 (JCIM follow-up), no v1 |
| **C2. CL-GNN diagnosis** — por qué AUC == Vina post-hot-patch | investigación, ~2 sesiones | blocks cualquier claim "ensemble" en v1 |
| **C3. Re-evaluar MolChamb con full ensemble** | post C1 + C2 | depends on C1 |
| **C4. Heterogeneous GNN (DNA/RNA/glycan pockets)** | research deep, 2-3 meses | v3 paper |
| **C5. EquiBind baseline como tercer predictor** | research, 3-4 sesiones | non-blocking |

**Timing**: C2 puede correr en парalelo con el paper v1 draft (sin compute
alive, solo code inspection). C1 requires GPU (tenemos CUDA pero no
vivo probado). C3 immediately after C1. C4-C5 are v3 paper track.

---

## 1. Contexto — por qué este doc existe

La sesión 2026-07-25 (Bucket A post-mortem) descubrió que:

- **GNN-v2 no se puede usar** para claims de paper post-A.1. El hot-patch
  (`commit 4f48fde`) hace que el modelo no silent-falle, pero la
  discriminación cae a near-random (5HT1A AUC=0.5382 vs Vina+XGB 0.8288).
- **CL-GNN aparenta no aportar nada** post-hot-patch (AUC == Vina-only)
  sobre 5HT1A. Síntoma similar a Bucket A.1 — diagnosis pendiente.
- **MolChamb no puede ser evaluado** sin GNN real. Los pesos 0.20/0.40/0.20/0.20
  fueron diseñados para combinar 4 señales. Con GNN=0 forzado, comparar
  Stacking+MolChamb vs Vina+XGB es metodológicamente injusto.

El paper v1 JCIM puede publicarse con Vina+XGB como primary claim
(AUC 0.8288 en 5HT1A, 0.9860 en CDK2), **declarando** las limitaciones.
Pero cualquier paper follow-up que quiera usar GNN, CL-GNN, MolChamb o
ensemble claims necesita este track resuelto.

---

## 2. C1 — GNN-v3 retrain con 30-element alphabet

### 2.1 Objetivo

Reentrenar GNN-v2 (mismísima arquitectura `models.py`) con features
 Bucket A.1 completos:
- ELEMENTS = 30 entradas (C, N, O, S, P, F, Cl, Br, I, B, Si, Se, As, At,
  Mg, Ca, Zn, Fe, Mn, Cu, Ni, Co, K, Na, Li, Sn, Sb, Te, H, X)
- input dim = 30 + 4 hyb + 4 scalar = **38** (en vez de 18)
- hidden_dim: mantener 128 del GPU checkpoint (más capacidad)
- dropout: 0.2 (config del GPU)

### 2.2 Datasets

- **PDBbind 2020 general set** (≈17K complexes) — train backbone.
- **PDBbind 2020 refined set** (≈5K) — validation high-quality.
- **CSAR** (~2012 NRC-HiQ) — external test.
- **DUD-E v1.3** (5HT1A, CDK2, ERα, Factor Xa, HIV-P — nuestros 5 paper
  targets) — decúppy evaluation. NO entrena sobre estos, solo evalúa.

### 2.3 Arquitectura — qué cambia de v2 a v3

Mínimo cambio para hacer fixed: incrementar `LigandEncoder.in_channels`
de 18 a 38. **No se cambia la arquitectura de las capas GIN, GAT, cross-attn**.
Esto nos permite:

1. Confirmar que el problema era solo el input dim (no otra cosa).
2. Mantener el cross-experimiento con CL-GNN (que comparte encoder).

### 2.4 Pipeline de training (`rescoring/gnn_v2/train_gpu.py`)

```
# pseudocódigo
DataLoader(dataset_38dim) -> batches (ligand_x 38-dim, prot_x 24-dim)
GNNv2Classifier(hidden_dim=128, lig_in_channels=38):
    prot_encoder(in_channels=24, hidden_dim=128)
    lig_encoder(in_channels=38, hidden_dim=128)  # <- CAMBIA
    cross_attn(hidden_dim=128, residue_bias=Embedding(21, 1))
    ... (resto igual)

TrainingLoop:
    for epoch in range(200):
        loss = F.binary_cross_entropy_with_logits(model(...), y)
        ...
    save: gnn_v3_best.pt (con residue_bias.weight como parte del state_dict)
```

### 2.5 Acceptance criteria

- AUC sobre PDBbind refined validation ≥ 0.75 (v2 actual: ?).
- AUC sobre 5HT1A paper benchmark ≥ 0.80 (hot-patched adapter dio 0.54).
- Silent-fail rate ≤ 1% (cuando re-scoreamos nuestro paper benchmark).
- Tiempo de inference ≤ 1s/mol en CPU (v2 hot-patched: 0.72s/mol).

### 2.6 Output esperado

```
rescoring/artifacts/gpu/gnn_v3_best.pt  (7.8-15 MB)
rescoring/gnn_v2/data.py ( ELEMENTS ya está expandido — no se toca)
rescoring/gnn_v2/models.py ( in_channels: int = 38 default)
rescoring/artifacts/stacking_weights.json ( re-optimizado usando v3)
docs/24_GNN_V3_TRAINING_LOG.md (training log + eval)
```

### 2.7 Risks

- **R-1**: GNN-v3 deja de funcionar para pre-Bucket A.1 checkpoints. Migration
  path: mover v2 directamente a v3, sin back-compat. Eliminar `inference.py`
  feature adapter (`4f48fde`) una vez v3 se use.
- **R-2**: GPU memory OOM en train (Ryzen 5 5500, 32 GB RAM, no GPU dedica
  da CUDA comprobada). Workaround: batch_size=8, hidden_dim=128.
- **R-3**: Discrimination no mejora despite del retrain. Plan B: heterogeneous
  GNN (ver C4) — añade tipo-de-nodo como embedding, deeper architecture.

### 2.8 Effort

- Setup + data loader refactor: 1 sesión
- Train completo (200 epochs en GPU/CPU): ~48-72 hr compute
- Eval + ablation re-run: 1 sesión
- Re-opttimizar `stacking_weights.json`: 1 sesión con grid search
- Total: 3-4 sesiones humanas + ~3 días de compute background

---

## 3. C2 — CL-GNN diagnosis

### 3.1 Síntoma

Sobre 5HT1A post-hot-patch:
- Vina + CL-GNN AUC = 0.7976. Vina-only AUC = 0.7975. **CL-GNN no discrimina**.

Esto no es un silent-fail (el clgnn_prob está populado con valores variados,
no todos 0.5). Pero los valores no correlacionan con `is_active`. Significa:
o las probs son ruido puro, o están invertidas, o el adapter hot-patch no
aplica a CL-GNN pero debería, u otro bug aún no detectado.

### 3.2 Hipótesis A — CL-GNN comparte encoder y se rompe igual

`contrastive_gpu.py` y `train_gpu.py` cargan `gnn_v2_best.pt` como pretrain
para CL-GNN. Si CL-GNN hereda el encoder entrenado en 18-dim (pre-Bucket A.1)
y los features actuales son 38-dim, CL-GNN inferencia está mismamente
broken — sólo se diferencia de GNN-v2 en la cabeza de classification (la
contrastive loss no usa el in_proj directamente, o sí?).

**Acción**: leer `contrastive.py:230` (donde se carga `clgnn_pretrained`)
y `contrastive_gpu.py:237` (donde se carga `clgnn_pretrained`). Verificar
si `lig_encoder.in_proj.weight` shape del `clgnn_*.pt` es 18 o 38.

### 3.3 Hipótesis B — CL-GNN fue fine-tuned en 38-dim pero no se adapta bien

Si `clgnn_finetuned.pt` tiene `weight` shape `(128, 38)` o `(64, 38)`, el
modelo fue retrained en 38-dim y los valores 0.79 == Vina son evidencia
de degenero no atribuible al adapter.

**Acción**: cargar `clgnn_finetuned.pt` y `clgnn_pretrained.pt` con el
mismo `inspect_gnn_ckpt.py` que usé para GNN-v2, listar keys y shapes.

### 3.4 Hipótesis C — La signal está, los weights del stacking están desajustados

Si CL-GNN prob reales (varian > 0) y medianamente discriminativos, el
bug podría estar en `stacking_ef.py` `composite_stacking` para gpcr family.
Re-verify: si suficiente overlap de prob distributions, el calibrated stacking
debería mixear CL-GNN + Vina+XGB mejor que Vina solo.

**Acción**: hand-compute `pearson_corr(clgnn_prob, is_active)` sobre el 2547
mols checkpoint. Si ~0, CL-GNN no discriminate. Si > 0.3 sí hay discrimination,
el bug está en stacking logic.

### 3.5 Effort

- 2 sesiones de code inspection + 1 script de diagnostico (`scripts/diagnose_clgnn.py`)
- No requiere retrain.

### 3.6 Output

- `docs/25_CLGNN_DIAGNOSIS.md` (findings + decisiones).
- Si Hipótesis A correcta: hot-patch adapter aplicado a `contrastive.py` inference path.
- Si B correcta: C2 redirige a Bucket C (need CL-GNN retrain en 38-dim).
- Si C correcta: hotfix en `stacking_ef.py` y re-opt de `stacking_weights.json`.

---

## 4. C3 — Re-evaluar MolChamb con full ensemble (post C1+C2)

### 4.1 Pre-requisitos

- C1 (GNN-v3 retrain) completo — silent < 5%, AUC > 0.8 en 5HT1A.
- C2 (CL-GNN diagnosis) completo — sano o reparado.
- `stacking_weights.json` re-optimizado con grid search 4-dim (vina/xgb/gnn/molchamb),
  por familia (no más gnn=0 forzado en 4/5).

### 4.2 Acciones

1. Re-correr `re-score-gnn.py` sobre 5HT1A + CDK2 con GNN-v3 (NO adapter).
2. Re-correr ablation `ablation_molchamb.py` sobre los nuevos checkpoints:
   - 5HT1A ya está listo de la sesion 2026-07-25 — sólo refresh data.
   - CDK2 también — need re-score first (~50 min).
3. Agregar 3 targets más (ERα, Factor Xa, HIV-P) — full paper table.
4. Generates `docs/21_ABLATION_MOLCHAMB_<TARGET>.md` x 5 + paper-ready consolidated table.

### 4.3 Veredicto final (si delta continua negativo en 5/5)

Si MolChamb consistentemente degrada AUC vs Vina+XGB en todos los 5
targets con GNN-v3 sano y weights optimized:

> "MolChamb was evaluated on 5 standard targets (5HT1A, CDK2, ERα, Factor Xa,
> HIV protease) with the GNN-v3 ensemble fully operational. Stacking + MolChamb
> consistently produced lower AUC than Vina + XGB alone across all targets
> (mean ΔAUC = −XX, range −0.01 to −0.08). Under our honest evaluation
> framework, MolChamb shows no value-add in docking-rescoring pipelines of
> this design. Quantum-chemistry features may benefit alternative cv scoring
> approaches (e.g. Δ-ML trained on free-energy perturbation datasets) but
> orthogonalize weakly with Vina+GNN-v3 ensemble."

Documentar como **negative result**. Es paper-worthy — el negative result
sobre MolChamb en docking rescoring es en sí mismo una contribución
científica (otros grupos no van a gastar 2 meses probando lo mismo).

### 4.4 Veredicto (si delta es mixed o positivo en al menos 1 target)

Si MolChamb mejora:
- Declarar Improvement target-specific y explorar por qué (settings-family
  coupling? e.g. kinase vs GPCR differential drug-likeness in pocket?).
- Paper "MolDesign v2.1: target-specific quantum-chemistry stacking boosts
  docking rescoring for GPCR" (JCIM short communication).

### 4.5 Effort

- 5 re-scores × 50 min + 5 ablations = 5 hrs compute.
- 1 sesión de analysis + paper writing.

---

## 5. C4 — Heterogeneous GNN (DNA/RNA/glycan pockets)

### 5.1 Objetivo

GNN-v3 universal que cubre **archetypes non-protein**:
- DNA-binding (topoisomerase, integrase, polymerase)
- RNA aptamers / ribozymes / riboswitches
- Glycosyltransferases (glycan pocket)
- Metal-lo-enzymes con catalytic ZN/MN/MG en pocket

### 5.2 Arquitectura propuesta

- Node-tipe embedding (extra feature dim) sobre protein_encoder: tipos
  = {protein, DNA, RNA, glycan, cofactor, ion}.
- Cross-attn extendido a atención **cross-modality** (no solo ligand→protein,
  sino ligand→receptor heterogéneo).
- Heterogéneo GIN/GAT con diferentes conv parameter por tipo de nodo
  (parameter-efficient via shared base + small per-type adapter).

### 5.3 Datasets necesarios

- C4.1 **DNA-binding dataset** — build set de ~150 DNA-binding complexes
  de PDBbind-like coverage (TOP1, TOP2, DNA gyrase, integrase, polymerase).
- C4.2 **RNA-target dataset** — ~100 RNA aptamers/ribozimas con ligando
  (Riboswitch classes: TPP, SAM, purine, FMN, glmS).
- C4.3 **Glycan-pocket dataset** — ~50 glycosyltransferases (O-GlcNAc
  transferase, fucosyltransferases).
- C4.4 **Cofactor-bearing pockets** — bottom-curacion de ~80 pockets con
  ZN/MN/MG catalytic en pocket. Critical: pocket residue detection debe
  incluir iones como parte del pocket.

### 5.4 Effort

- 2-3 meses (curation + train + eval).
- Output: paper "MolDesign-v3: Heterogeneous GNN rescoring across biomolecular
  receptor archetypes" (JVLC or JChemIM tier 2).

### 5.5 Risks

- Curation de DNA-binding complexes lleva 2-3 sesiones manuales label.
- Heterogeneous GNN training inestable (gradient balanding entre archetypes).

---

## 6. C5 — EquiBind como tercer predictor (non-blocking)

### 6.1 Motivación

GNN-v2 y CL-GNN **comparten encoder** — high correlation. Diversidades
limitan ensemble. EquiBind (independiente, pose-prediction based) da una
señal ortogonal.

### 6.2 Acciones

1. Setup EquiBind (`git clone https://github.com/HannesStark/EquiBind`).
2. Inference wrapper similar a `gnn_v2/inference.py` — acepta (smiles,
   protein_pdb), retorna (affinity_pred, distance_score).
3. Incluir como tercer modelo en `stacking_ef.py` con weight grid search.
4. Evaluar en 5HT1A + CDK2 primero.

### 6.3 Effort

- 3-4 sesiones. No bloqueante; opciono si C1 alone no llega a AUC > 0.8.

---

## 7. Sequenciación — hacia el paper v2

```
[ paper v1 enviado: Vina+XGB primary claim, limitations detalladas ]
                                  |
                                  v
                ┌────── C1 GNN-v3 retrain (3-4 sesiones + 3 días compute)
                │
                ├── C2 CL-GNN diagnosis (2 sesiones, paralelo a C1 start)
                │
                └── C3 re-eval MolChamb (1 sesión post C1+C2)
                                  |
                                  v
                  [ decision point: MolChamb veredicto? ]
                                  |
                                  v
              [ paper v2 "MolDesign v2.1: re-evaluation of ensemble
                rescoring with GNN-v3 and quantum features" (JCIM) ]
                                  |
                                  v
                  └── C4 heterogeneous GNN (2-3 meses research)
                                  |
                                  v
                  [ paper v3 "MolDesign v3: heterogeneous GNN
                    across biomolecular archetypes" (JVLC/JChemIM) ]
```

### 7.1 Decisión explicita (v1) sobre qué va al paper JCIM y qué no

| Claim en paper v1 | Va? | Razón |
|-------------------|-----|-------|
| Vina + XGB primary (AUC 0.83-0.99 range) | ✅ | sólido, reproducible, sin deps en GNN |
| Calibrated Stacking (with current weights) | ❌ | degrada sin GNN signal, inconcluso |
| MolChamb evaluation | ❌ | inconclusive pending GNN-v3 |
| Stacking + MolChamb con delta -0.06 | ❌ | no defendible sin ensemble completo |
| Limitations section | ✅ | honesto: declare GNN-v3 needed |
| Reproducibility scripts | ✅ | `run_5targets_2500.ps1`, `ablation_molchamb.py` |

### 7.2 Decisión post-v1

C1-C3 son el bloque del paper v2 (JCIM o similar relationship). C4 es v3
paper. C5 es "mejor" v2.1 si EquiBind evidence resulta utile.

---

## 8. Archivos que se actualizarán durante este track

```
Code:
  rescoring/gnn_v2/                    (architecture changes for v3)
  rescoring/gnn_v2/models.py           (LigandEncoder.in_channels: 18 -> 38)
  rescoring/gnn_v2/train_gpu.py        (data loader con 38-dim features)
  rescoring/gnn_v2/inference.py        ( 4f48fde hot-patch removed after v3)
  rescoring/gnn_v2/contrastive*.py     ( 38-dim input propagation)
  scripts/re-score-gnn.py              ( accept --gnn-version v3)
  scripts/stacking_ef.py               ( EquiBind optional component)
  rescoring/artifacts/stacking_weights.json ( re-opt)

Data:
  rescoring/artifacts/gpu/gnn_v3_best.pt ( new)
  rescoring/artifacts/gpu/clgnn_v3_finetuned.pt ( new)
  scripts/diagnose_clgnn.py ( new, C2)
  PDBbind 2020 general set ( 17K complexes, train)
  PDBbind 2020 refined set ( 5K complexes, val)
  DUD-E subsets ( 5 targets, eval)

Docs:
  docs/24_GNN_V3_TRAINING_LOG.md ( new, C1)
  docs/25_CLGNN_DIAGNOSIS.md     ( new, C2)
  docs/26_MOLCHAMB_VERDICT.md    ( new, C3)
  docs/27_V3_PAPER_DRAFT.md      ( new, post-C3, paper v2)
  docs/19_LIMITATIONS.md          ( updated post-C1: §7 closing)
```

---

## 9. Métricos track-back

Al cerrar este track deberíamos poder afirmar:

- [ ] Silent-fail rate < 1% en 5 targets (vs 100% actualizada).
- [ ] GNN-v3 AUC ≥ 0.80 en 5HT1A.
- [ ] CL-GNN discrimina (AUC > vina-only).
- [ ] `stacking_weights.json` re-optimizado con grid search real (no gnn=0).
- [ ] MolChamb verdict si o si (positive result o negative result, no
  más "inconclusive").
- [ ] Paper v2 draft ready.

---

*Documento vivo. Actualizar §2.7 Effort lines y §7 sequenciación
conforme las sesiones de C1 avancen.*
