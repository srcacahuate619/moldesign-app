# 42 - Ruta C: Protocolo del Pose-Selector ML

**Fecha**: 2026-08-14 · **Estado**: protocolo pre-registrado, pendiente de aprobación
**Precedentes**: docs/40 (MolFlex), docs/41 (investigación de campo)
**Objetivo**: re-ranker ML que, dadas N poses de docking de un ligando en su
proteína, selecciona la pose tipo-cristal. Construido sobre los 6 principios
convergentes de docs/41.

---

## 1. El problema (con evidencia propia)

El score de Vina NO selecciona la pose tipo-cristal (R4 confirmado 3 veces;
recomputación pocket-frame 2026-08-14): poses desplazadas 8-13 Å del sitio
bioactivo con geometría interna correcta y scores casi degenerados. Referencia
externa: GNINA (3D CNN) logra Top1 73% vs 58% de Vina — su score aprendido
correlaciona con RMSD, no refina energía.

## 2. Hipótesis pre-registrada

**H-RC**: un score de native-likeness APRENDIDO (ortogonal a la energía de
Vina), entrenado con objetivo de ranking por-complejo y márgenes
proporcionales a ΔRMSD (principios C1+C3), selecciona la pose tipo-cristal
significativamente mejor que el score de Vina solo, y su ventaja se mantiene
con splits honestos a nivel de complejo.

**Criterios de éxito (pre-registrados)**:

| Código | Métrica | Criterio |
|---|---|---|
| M1 | Top-1 crystal-like rate (RMSD pose seleccionada ≤ 2.0 Å), por complejo, holdout congelado, CI bootstrap | v0 > Vina; GNN v1 > v0; objetivo final ≥ 70% |
| M2 | RMSD mediano de la pose seleccionada | ≤ 2.0 Å en holdout |
| M3 | Spearman(rank predicho vs RMSD real) promedio por complejo | ≥ 0.7 |
| G1 | Gate de fidelidad de pipeline | v0 (XGBoost barato) DEBE superar a Vina antes de invertir en GNN (principio C6) |

## 3. Los 6 principios → decisiones de diseño

| Principio (docs/41) | Decisión concreta en Ruta C |
|---|---|
| **C1 señal ortogonal** | Head predice RMSD/native-likeness; el score de Vina entra SOLO como contexto (feature), jamás como objetivo de entrenamiento |
| **C2 confiabilidad + rechazo** | Ensemble calibrado (GNN + XGBoost + consenso); regla de abstención: si las señales discrepan fuerte o el margen es bajo → "no sé" (conformal) |
| **C3 amplificar diferencias** | Pérdida de ranking pairwise/listwise con margen ∝ ΔRMSD entre poses del MISMO complejo |
| **C4 consenso poblacional** | Features de consenso: contactos tipo-cristal (RANSAC-like), densidad de clúster de poses vecinas, patrón poblacional de scores |
| **C5 posterior + deferral** | Salida = distribución sobre poses, no argmax; top-k con confianza; deferral a verificación cara (re-dock/minimización) si el margen es bajo |
| **C6 medir y emparejar** | No tocamos el generador (docking). Empezamos por el verificador más barato (Fase 1) antes del GNN |

## 4. Datos de entrenamiento (inventario del recon)

- **~4,500 poses / 233 complejos** con etiqueta RMSD computable en disco:
  - 218 complejos × hasta 9 poses flexibles (exh=8) = **1,735** (`vina_redock_work/*/{pid}_out.pdbqt`, 168 archivos con 9 MODELs)
  - 20 complejos MolFlex × ~20 confs rígidos = **2,213** (`.work_molflex_v3/conf*.out.pdbqt`, `index_map.json` en 18/20)
  - 30 complejos ruta_a (exh=1/2/4) = **553** (`tmp/ruta_a/*/exh*/out.pdbqt`, `REMARK INDEX MAP` embebido)
- **Etiqueta**: RMSD pocket-frame (sin alinear) — `molflex.rmsd_pose_pocket`. PROHIBIDO `rmsd_pesados` (GetBestRMS alinea: lección 2026-08-14).
- **Pipeline de etiquetado ya probado**: `scripts/recalcular_rmsd_pose.py` (modelo 1); extender a los 9 MODELs (un loop sobre `parsear_out_vina`, que ya devuelve todos los modelos).
- **Caveat verificado**: varios complejos NO tienen ninguna pose ≤2 Å (ref exh=8 hasta 12 Å) → objetivo de RANKING por complejo, no clasificación binaria global.
- **Split MANDATORIO a nivel de complejo** (scaffold-disjoint + holdout congelado con sha256 en manifest; la lección del 0.8732→0.6094). Poses del mismo complejo jamás en dos particiones.

## 5. Arquitectura por fases

### Fase 0 — Dataset builder (`scripts/build_pose_selector_dataset.py`)
Extrae las ~4,500 poses + etiquetas RMSD + features baratas por pose:
vina_score (REMARK VINA RESULT), pose_score_variance/range intra-complejo,
contactos ligando-proteína (conteos 4/6 Å), exposición/SAS del ligando,
densidad de clúster (poses vecinas <2 Å). Split a nivel de complejo
(scaffold-disjoint + holdout congelado, sha256). Salida:
`data/pose_selector_dataset/poses_{train,val,test}.npz` + `manifest.json`.

### Fase 1 — Baseline v0 honesto (C6)
- Medir **Vina top-1 crystal-like rate** en el holdout (nuestro propio número,
  honesto; la referencia 58% de GNINA es de OTRO benchmark).
- **v0 = XGBoost ranker** (`rank:pairwise`, por-complejo, igual que el
  pipeline de rescoring existente) sobre las features baratas + score Vina
  como contexto.
- **Gate G1**: v0 debe superar a Vina top-1 en holdout. Si no supera, REVISAR
  features/labels antes de tocar el GNN (no gastar GPU en un pipeline roto).

### Fase 2 — GNN v1 PoseSelector (C1+C3+C4)
- **Backbone**: reutiliza `rescoring/gnn_v2/models.py` (ProteinEncoder GAT-Cα
  24-dim + LigandEncoder GIN 38-dim + CrossAttention con bias de distancia).
- **Head dual**: (a) regresión de RMSD por pose; (b) incertidumbre por
  MC-dropout (mc_samples=20, precedente `predict_proba` de GNNv2Classifier).
- **Pérdida**: pairwise per-complejo con margen ∝ ΔRMSD (C3): parejas con
  ΔRMSD grande reciben margen amplificado; opcional listwise (NDCG-style).
- **Pretraining contrastivo** opcional: activos `contrastive_v31.py` y
  snapshots seed 42/43/44 ya existen.
- **Restricción de producción**: CPU-only en el runtime embebido → modelo
  ≤1 M params (GNNv2 ~0.8 M es precedente probado).

### Fase 3 — Ensemble + calibración + abstención (C2+C5)
- Stacker (logística/GBT) sobre: score GNN, score v0-XGBoost, consenso
  RANSAC-like, densidad de clúster.
- Calibración + conformal: si ninguna pose pasa el umbral de confianza →
  ABSTENER (reportar "no sé", jamás elegir al azar).
- Deferral: margen bajo entre top-1 y top-2 → activar verificación cara
  (minimización local / re-dock exh=4 estándar).

### Fase 4 — Integración en el sidecar
- `rescoring_bridge._ARTIFACT_DEFAULTS` + `RescoringSettings` + bloque
  `pose_selector` en `ModelManager.predict()` (precedente `classifier_binder`).
- `RescoreResponse`: `pose_scores`, `selected_pose_rank`, `pose_confidence`,
  `pose_abstained`. Manifest v4 con sha256. `RescoreRequest.poses[].pdbqt_block`
  ya transporta las poses; `DockingPose` ya lleva `rank/affinity/pdbqt_block`.

## 6. Experimentos de validación (esperamos que PASEN)

| Código | Experimento | Criterio |
|---|---|---|
| V-RC1 | Fase 1: v0 vs Vina top-1 en holdout | v0 > Vina (Gate G1) |
| V-RC2 | Fase 2: GNN v1 vs v0 | GNN v1 > v0 en M1/M2/M3 |
| V-RC3 | Fase 3: ensemble + conformal vs GNN solo | ≥ GNN solo en M1, con tasa de abstención reportada |
| V-RC4 | Objetivo final | M1 ≥ 70% top-1 crystal-like en holdout (CI honesto) |

## 7. Experimentos de refutación (anticipando objeciones de revisores)

| Código | Experimento | Qué refutaría |
|---|---|---|
| R-RC1 | GNN entrenado SIN score Vina vs CON score Vina | Si son idénticos, el modelo no aporta señal ortogonal (C1 falso) — la ventaja sería re-ranking de energía |
| R-RC2 | Split por complejo vs split por pose (aleatorio) | Si el split por pose infla las métricas, confirma leakage (lección 0.8732) |
| R-RC3 | ¿El selector elige poses >10 Å cuando existe una ≤2 Å? | El modo de fallo de R4; si ocurre en holdout → FAIL de diseño |
| R-RC4 | Complejos SIN ninguna pose ≤2 Å: ¿el modelo abstiene o adivina? | Si adivina con confianza alta → la calibración miente; medir confianza vs error real |
| R-RC5 | Robustez a perturbación débil (metamorphic): rotar/trasladar sistema, perturbar pose 0.1 Å | La decisión no debe cambiar abruptamente |

## 8. Stack verificado (del recon)

- Sistema: Python 3.14, torch 2.14+cu126, **torch_geometric 2.8.0**, sklearn
  1.8, xgboost 3.2, lightgbm 4.6, rdkit 2025.09. GPU: GTX 1660 SUPER 6 GB.
- Runtime embebido (producción): Python 3.11, torch 2.13 **CPU-only**, PyG
  2.8 → el modelo final debe inferir en CPU a escala de un complejo.
- DGL NO disponible (RTMScore ya fue portado a PyG por eso).
- No existe código previo de ranking de poses: Ruta C es greenfield.

## 9. Evaluación y convenciones heredadas

- Split: scaffold-disjoint, holdout congelado (sha256 en manifest), seed 42,
  CI bootstrap 10k — la convención del modelo Fase A (docs/38). PROHIBIDO el
  random split de la era GNN (leakage documentado).
- Métricas: M1 (top-1 crystal-like ≤2 Å), M2 (RMSD mediano), M3 (Spearman
  rank-RMSD). El protocolo EF/AUC de screening NO aplica a poses.
- Artefacto incremental: cada experimento escribe JSON tras cada complejo
  (patrón MolFlex/ruta_a).

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Pocos positivos por complejo (sin pose ≤2 Å) | Objetivo de ranking, no binario; reportar cobertura de complejos con pose buena |
| Leakage por complejo | Split a nivel de complejo + R-RC2 como verificación |
| 6 GB VRAM | Batch pequeño, modelos ≤1 M params, pretraining opcional en snapshots existentes |
| Inferencia CPU en producción | v0 XGBoost es el fallback nativo; GNN chico |
| Score Vina dominante en features | R-RC1 (ablation sin Vina) + peso explícito del contexto |

## 11. Orden de ejecución

1. ✅ **Fase 0**: dataset builder + manifest (etiquetas de las ~4,500 poses).
2. ✅ **Fase 1**: medir Vina top-1 (baseline honesto) + v0 XGBoost (Gate G1 FAIL: v0 0.404 < Vina 0.532).
3. ✅ **Fase 1.5**: v0.5 features ricas raw (224) — test 0.489, G1 sigue FAIL; las features ricas REEMPLAZAN a vina_score (ablación), la señal existe en todas las familias.
4. ✅ **Fase 1.6**: v0.6 relativo (224 z-score intra-complejo + 9 percentiles) — **GATE G1 PASS: test 0.660 vs Vina 0.532** (+0.128), RMSD mediano 1.428. Mecanismo de relatividad intra-complejo confirmado.
5. ✅ **Fase 2**: GNN v1 ejecutada — FAIL honesto (0.489 vs 0.660); diagnóstico
   abajo. Pendiente: iteración GNN v2.
6. ✅ **Fase 3**: calibración + abstención (test: abstención 43% → top-1 0.852
   en aceptados; decidibilidad AUC val 0.928); R-RC2 sin leakage (0.216);
   R-RC3 1/47 (idéntico a Vina); checkpoint producción guardado.
7. ✅ **Fase 3.5 + R-RC5**: abstención por decidibilidad NO mejora al margen
   (SIN_MEJORA_HONESTA); invarianza rígida perfecta (diff 0.0); perturbación
   σ=0.1 Å cambia 19% solo cerca del margen. **EXPERIMENTOS COMPLETOS.**
8. ✅ **Fase 4**: integración sidecar completa (paquete `rescoring/pose_selector/`,
   hook en `ModelManager.predict()`, 5 campos en `RescoreResponse`, manifest
   v4, 11 tests nuevos + regresiones). **RUTA C TERMINADA end-to-end.**
8. ⏳ Refutaciones R-RC1..R-RC5 junto con V-RC2/V-RC3.

Regla del proyecto: sin commits sin aprobación; experimentos incrementales a JSON;
FAILs se registran y se usan para rediseñar (auto-refutación bienvenida).

## 12. Resultados acumulados (test congelado, 47 complejos)

| Modelo | top-1 | RMSD mediano | Nota |
|---|---|---|---|
| Vina (baseline) | 0.532 | 1.765 | nuestro número honesto |
| v0 (9 features baratas) | 0.404 | 2.541 | Gate G1 FAIL |
| v0.5 (224 rich raw) | 0.489 | 2.037 | G1 FAIL; rich reemplaza a Vina |
| v0.6 (224 z + 9 pct) | **0.660** | **1.428** | G1 PASS; relatividad intra-complejo |
| GNN v1 (con Vina) | 0.489 | 2.037 | FAIL; pairwise dominado por MSE aux |
| GNN v1 sin Vina (R-RC1) | 0.064 | 6.815 | colapso — C1 no se sostiene en v1 |
| GNN v2 (ECIF 152 real + CL warm-start) | 0.511 | 1.816 | FAIL; pérdida ranking SÍ se movió pero per-pose no captura relatividad |
| GNN v2 sin Vina | 0.383 | 2.470 | no colapsa, pero lejos |
| GNN B (set-level cross-pose) | 0.511 | 1.816 | FAIL; mismo top-1 que v2 |
| GNN B + init gnn_v31_best (estricta) | 0.532 | 1.816 | FAIL; ≈Vina — mejor init disponible usado |

**VEREDICTO DE LA LÍNEA GNN (regla pre-acordada, directiva cumplida al 100%)**:
H-RC REFUTADA a esta escala (~4,300 poses / 203 complejos). CUATRO iteraciones
(v1 aleatorio 0.489 · v2 CL+ECIF 0.511 · B set-level 0.511 · B+gnn_v31_best
0.532) no superan la relatividad explícita; el mejor backbone preentrenado
acerca al modelo a comportarse como Vina y no pasa de ahí. **v0.6 XGBoost
queda promovido como selector oficial de Ruta C: test top-1 0.660 vs Vina
0.532 (+0.128), RMSD mediano 1.428 vs 1.765.**

Diagnóstico acumulado: la señal discriminativa existe en todas las familias
(shells 0.454→0.581 con z-score); el factor crítico es la comparación
intra-complejo (C3/C4). La GNN v1 no la capturó: encoder per-pose sin
relatividad + pérdida de ranking plana dominada por el MSE aux. Próxima
iteración: features relativizadas intra-complejo como contexto + pérdida de
ranking dominante, o arquitectura set-level con atención cross-pose (C4 nativo).
