# D-MF-HARD-EXH4-VAL — Brazo Vina flexible exh4, fase 2 (10 val) — DESIGN

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** D-MF-HARD-EXH4 (sello train GO, commit a0524e3) + FORECAST.md
(correcciones procedimentales commit 47a24a8) + docs/49 §15 entregable 8
(MF-06) + D-MF-HARD/DESIGN.md (cohorte sellada).
**Estado: EJECUTADO (descriptivo). NO sellado, NO finish.**

## 1. Alcance y naturaleza de la fase

- **10 complejos val** (5 hard + 5 controles) del cohort sellado D-MF-HARD:
  1b32, 1cny, 1hms, 1hmt, 1jlr (hard) y 1bgq, 1fki, 1bm7, 1ejn, 1nvq
  (control).
- **PRIMERA y ÚNICA ejecución de Vina exh4 sobre val**: un dock flexible
  por complejo, UNA sola vez cada uno, sin retries silenciosos (fallos ->
  ITT en failures.jsonl, sin reintentar).
- **DESCRIPTIVA, NO ciega y NO confirmatoria:** la cohorte val YA fue
  examinada con MolFlex K15 (sellada D-MF-HARD-CURVE-VAL); val NO es ciega
  para el entregable 8 (FORECAST §6, congelado 5). n=5 por estrato: sin
  potencia; solo Wilson CI95 descriptivo.
- **No cambia la interpretación train:** los números de val se reportan
  como descripción; K=15 y el claim train sellado (D-MF-HARD-EXH4 GO,
  DESIGN.md §7 "Interpretación para el sello") permanecen INALTERADOS pase
  lo que pase.

## 2. Configuración (idéntica a la fase 1 sellada)

| Parámetro | Valor |
|---|---|
| engine | Vina 1.2.7, ligando FLEXIBLE meeko (conformación cristalográfica) |
| receptor | PDBQT rígido pdb_original (openbabel, misma cadena histórica) |
| exhaustiveness | 4 |
| seed | `--seed 42` explícito (seed_docking=42; seed_conformer="crystal") |
| box | 25 Å centrado en ligando cristalográfico |
| num_modes | 9 solicitados |
| cpu / workers | 1 / 6 físicos |
| timeout | 300 s por dock |
| relax | sin relax |
| gate | enmendado (heredado D-MF-HARD-CURVE §8): rc=0, archivo no vacío, 1<=n_models_emitted<=9, scores FINITOS solo de REMARK VINA RESULT, identidades solo para modelos emitidos |
| work dir | `data/dmfhard_curve_work/exh4_val/` (gitignored, separado del train) |
| identidad | `val|pid|vina_exh4|flex_exh4.out|model_idx` |
| experiment_id | D-MF-HARD-EXH4-VAL |

## 3. Implementación (por composición — congelado 7)

- Runner: `scripts/run_vina_exh4_val.py` — wrapper que importa
  `scripts/run_vina_exh4.py` SIN editarlo (asset sellado del commit
  a0524e3) y monkeypatchea split/work/artifacts/experiment_id/guardia de
  val (patrón `run_molflex_curve_val.py`). Se reusan sin modificación:
  preparar, `_preparar_ligando_flexible`, `dock_flexible_archivo`,
  `_asegurar_provenance`, `_validar_provenance_pid`, `_dock_worker`,
  `_procesar_resultado`, `dockear_lote` (resume + lotes con --wall-budget)
  y el gate corregido (`parse_vina_output` de `run_molflex_curve.py`).
- Sin pilot sobre val: el determinismo parcial es SINTÉTICO (fixture en
  temp sobre un pid TRAIN, nunca val).
- Consolidación val PROPIA: sin regla de decisión, sin comparación
  decisoria, sin bootstrap decisorio. Solo descripción.

## 4. Resultados descriptivos (val, 10 complejos)

- Poses emitidas: 76; fallos ITT: 0; candidatos
  materializados: 76.
- Hard (n=5): cobertura 2/5, Wilson CI95
  [0.118, 0.769], mediana min-RMSD 2.324 A.
- Control (n=5): cobertura 2/5, Wilson CI95
  [0.118, 0.769], mediana min-RMSD 4.143 A.

## 5. Descriptivo lado a lado vs train (MISMO brazo exh4)

| Estrato | Train (17+17, sello GO) | Val (5+5, descriptivo) |
|---|---|---|
| hard | 11/17 (64.7%), mediana 1.424 A | 2/5, mediana 2.324 A |
| control | 13/17 (76.5%), mediana 1.049 A | 2/5, mediana 4.143 A |

SIN inferencia fuerte: n=5 por estrato no admite pruebas pareadas con
potencia; esta tabla es descripción, no decisión.

## 6. Declaraciones

- 0 docks de val previos: los 10 val se ejecutaron UNA sola vez cada uno
  en esta corrida (work dir `exh4_val/` inexistente antes de arrancar).
- 0 pids train tocados (guardia verificada en metrics.json).
- K=15 INMUTABLE (sello f31bfeb); exh2 permanece CERRADO.
- Cero v0.6, cero MF-11, cero producción, cero relax, cero test histórico.
- **Ningún resultado de val altera K=15 ni el claim train sellado
  (D-MF-HARD-EXH4 GO).**

## 7. Archivos

| Archivo | Contenido |
|---|---|
| exh4_poses_val.jsonl | una linea por pose EMITIDA (identidad val|pid|vina_exh4|flex_exh4.out|model_idx) |
| exh4_provenance.jsonl | sidecar FND-06 canonico (14 campos + num_modes_requested/n_models_emitted) por corrida |
| exh4_candidates_val.jsonl | bloques PDBQT byte-fieles materializados por pose emitida |
| metrics.json | descriptivas por estrato (cobertura n/5, Wilson CI95, mediana, ITT, tiempos P50/P90) |
| per_complex.jsonl | una linea por complejo val |
| failures.jsonl | fallos ITT (sin reintentos) |
| deviations.jsonl | esperado vacio (gate corregido desde el inicio) |
| manifest.json / README.md | registro FND-01 (init/validate; sin seal ni finish) |
