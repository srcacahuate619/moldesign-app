# D-MF-HARD-EXH4 — Brazo Vina flexible exh4, fase 1 (34 train) — DESIGN

**Fecha:** 2026-08-16
**Rama:** experimentos/ruta-c-molflex
**Referencia:** FORECAST.md (correcciones procedimentales commit 47a24a8) +
docs/49 §15 entregable 8 (MF-06) + D-MF-HARD/DESIGN.md (cohorte sellada).
**Interpretacion aprobada por el maintainer con 2 correcciones de artefacto
(2026-08-16): guardia de val renombrada a val_no_tocado_verificado y CPU por
estrato (hard 2.214 h / control 0.406 h P50 para MolFlex). NO sellado, NO
finish (sellado diferido por instruccion del maintainer).**

## 1. Protocolo ejecutado

- Vina FLEXIBLE, exh=4, `--seed 42` explicito, box 25 A centrado en el
  ligando cristalografico, num_modes solicitados 9, cpu=1, 6 workers, sin
  relax, timeout 300 s/dock, Vina 1.2.7. Un dock por complejo.
- Ligando: CONFORMACION CRISTALOGRAFICA preparada con meeko como PDBQT
  FLEXIBLE (torsiones activas). Receptor: PDBQT rigido pdb_original. Misma
  definicion de flexibilidad/receptor del historico documentado
  (rescoring/scripts/redock_pdbbind.py flexible_redock exh8 y
  scripts/ruta_a_exh_validation.py dock_one_exh); solo cambian exh (8->4) y
  el seed explicito (los historicos no lo registraban).
- Gate ENMENDADO (auditado 2026-08-16, heredado de D-MF-HARD-CURVE §8):
  validez = rc=0 + archivo no vacio + 1 <= n_models_emitted <= 9 + TODOS los
  modelos con score FINITO de REMARK VINA RESULT + geometria parseable.
  Scores EXCLUSIVAMENTE del archivo (nunca de la tabla stdout). Identidades
  SOLO para modelos realmente emitidos (sin model_idx fantasma).
- Alcance: SOLO train (17 hard + 17 controles). CERO val: los 10 pids de val
  no se dockearon, no se leyeron de la union ni de los artefactos (guardia
  dura + verificacion final). Fase 2 (D-MF-HARD-EXH4-VAL, 10 val) queda
  FUERA de esta ejecucion: se autoriza solo tras analizar y sellar la
  interpretacion de train.
- Alcance del claim: box centrado en el ligando cristalografico y
  conformacion de entrada cristalografica -> benchmark de REDOCKING/
  GENERACION dentro de una pocket conocida. NO es evidencia end-to-end para
  pockets desconocidas.

## 2. Implementacion (por composicion — congelado 7)

- Runner: scripts/run_vina_exh4.py (stdlib, docstring espanol). NO edita
  ningun asset sellado: reusa por importacion scripts/molflex.py
  (leer_ligando, escribir_pdbqt, cargar_mapa_indices, coords_pose_a_por_mol,
  rmsd_pose_pocket, _args_box, prepare_receptor_pdbqt/find_binding_center via
  mf.rp) y scripts/run_molflex_curve.py (parse_vina_output = gate corregido,
  leer_cohort, utilidades de archivo; su hash esta sellado en
  D-MF-HARD-CURVE: solo se importa).
- Identidad canonica por pose: train|pid|vina_exh4|flex_exh4.out|model_idx
  (model_idx SOLO para modelos emitidos). Identidad sin colision con FND-06
  ni MF-01-UNION (identity-check: 0 hits).
- Provenance canonico FND-06 (14 campos) por corrida: seed_conformer=
  "crystal" (no hay generacion estocastica de conformeros; convencion del
  historico flexible_redock), seed_docking=42 (--seed explicito),
  exhaustiveness=4, experiment_id=D-MF-HARD-EXH4, mas num_modes_requested=9
  y n_models_emitted anotados tras el dock.
- Resume idempotente por identidad: dock valido bajo el gate -> no se repite;
  fallo -> ITT en failures.jsonl sin reintentos silenciosos; STOP.json ante
  fallos SISTEMATICOS (mismo motivo en >=3 complejos) o violacion de
  integridad del gate.
- Work dir: data/dmfhard_curve_work/exh4/ (gitignored; .gitignore intacto).
- Consolidacion separada del docking: los artefactos finales se reconstruyen
  desde el work dir; el docking nunca escribe en scripts/artifacts_science.
- Determinismo parcial verificado: regeneracion completa de la preparacion de
  1 complejo en temp -> byte-identica (ver reporte de ejecucion).

## 3. Metrica de pose

- rmsd_pose_pocket (molflex.py) en el marco del pocket, sin alineamiento
  (obligatoria segun docs/48), contra el ligando cristalografico
  data/pdbbind/{pid}/{pid}_ligand.sdf, sobre los modelos EMITIDOS.

## 4. Resultados (train, 34 complejos)

- Poses emitidas: 231; fallos ITT: 0; candidatos
  materializados: 231.
- Hard: cobertura 11/17, mediana min-RMSD
  1.424 A.
- Control: cobertura 13/17, mediana
  min-RMSD 1.049 A.

## 5. Comparacion vs MolFlex K15 y Union (3 niveles, train)

### (a) Operacional completa — cobertura cruda por brazo

| MolFlex K15 (sellado) | hard 3/17 (17.6%), mediana 4.024 A, N=1450 | control 15/17 (88.2%), mediana 1.041 A, N=1240 |
| Union (restringida a cohorte) | hard 11/17 (64.7%), mediana 1.4 A, N=802 | control 13/17 (76.5%), mediana 1.289 A, N=155 |
| Vina flexible exh4 (nuevo) | hard 11/17 (64.7%), mediana 1.424 A, N=119 | control 13/17 (76.5%), mediana 1.049 A, N=112 |

### (b) Ajustada por CPU — cobertura por CPU-hour (solo brazos con CPU>0)

Denominadores por estrato (correccion del maintainer 2026-08-16):

- MolFlex K15 train (P50, estimado): hard 255 docks x 31.25 s = **2.214 h**;
  control 159 x 9.2 s = **0.406 h**; total **2.620 h** (P90 total 4.24 h:
  255 x 42.1 s + 159 x 28.5 s). Fuente: FORECAST §6(b).
- Vina exh4 train (medido, cpu=1, incluye fallos ITT): hard
  **0.67 h**; control
  **0.118 h**; total
  **0.788 h**.
- Conclucion (no cambia con la correccion): en hard, exh4 obtiene mucha mas
  cobertura con ~1/3 del coste estimado de MolFlex (0.670 h vs 2.214 h).
- Union: ratio INDEFINIDO (cobertura / 0 CPU-hours; ningun dock nuevo). Tres
  costes por separado: incremental hoy = 0 h; historico de generacion NO
  estimable desde datos sellados (FND-06 sin timing); reproduccion estimada
  2.4-4.7 h CPU (planificacion, no gate).
- Eficiencia por estrato: metrics.json -> comparacion.cpu_ajustada_nivel_b.

### (c) Ajustada por candidatos (DESCRIPTIVA, no decisoria)

- N candidatos por estrato y eficiencia oraculo = cobertura/(N/100):
  metrics.json -> comparacion.n_candidatos_nivel_c_descriptiva. Degradada a
  descriptiva porque MF-11 no deduplica y los duplicados distorsionan N
  (FORECAST §6.c).

## 6. G2 — oraculo por estrato en 4 niveles (train decide)

| hard | vina_exh4_vs_molflex_k15 | vina_exh4 11/17 vs molflex_k15 3/17 | b=8, c=0 | p=0.0078125 | vina_exh4 |
| hard | vina_exh4_vs_union | vina_exh4 11/17 vs union 11/17 | b=1, c=1 | p=1.0 | INCONCLUSO |
| hard | molflex_k15_vs_union | molflex_k15 3/17 vs union 11/17 | b=0, c=8 | p=0.0078125 | union |
| control | vina_exh4_vs_molflex_k15 | vina_exh4 13/17 vs molflex_k15 15/17 | b=0, c=2 | p=0.5 | INCONCLUSO |
| control | vina_exh4_vs_union | vina_exh4 13/17 vs union 13/17 | b=2, c=2 | p=1.0 | INCONCLUSO |
| control | molflex_k15_vs_union | molflex_k15 15/17 vs union 13/17 | b=3, c=1 | p=0.625 | INCONCLUSO |

Regla de superioridad (nivel iv): un brazo gana solo si (i) el conteo lo
favorece Y (ii) la pareada no muestra perdidas netas que lo contradigan Y
(iii) McNemar exacto bilateral p <= 0.05. Con n=17 la potencia es baja:
INCONCLUSO es un resultado valido y esperable.

## 7. Interpretacion para el sello

En D-MF-HARD train, AutoDock Vina 1.2.7 con ligando flexible, receptor rígido, exhaustiveness 4 y seed 42 fue superior a MolFlex K15 en cobertura hard: 11/17 frente a 3/17; discordancias b=8, c=0; McNemar exacto bilateral p=0.0078125. El coste hard fue 0.670 CPU-h medido frente a 2.214 CPU-h P50 estimado para MolFlex, sin tradeoff de coste bajo el estimador preregistrado. El claim se limita a esta cohorte de desarrollo y a redocking/generación con pocket conocida, box y conformación inicial cristalográficos. Frente a la unión en hard y frente a MolFlex K15 en controles, el resultado permanece inconcluso.

## 8. Sensibilidad

Considerando las seis comparaciones G2, Bonferroni post hoc mantiene el resultado hard exh4-vs-K15 por debajo de 0.05 (p_adj=0.046875); se reporta como sensibilidad, no como parte del preregistro original.

## 9. Declaraciones de alcance

- 0 val tocado (ni dock, ni lectura de outputs previos mas alla de la
  cohorte: la union restringida a la cohorte train se recomputo SOLO desde
  union_candidates_train.jsonl).
- Cero v0.6 (RS-01), cero MF-11, cero produccion, cero relax, cero
  reentrenamiento, cero test historico.
- K15 MolFlex INMUTABLE (sello f31bfeb): nada de esta corrida cambia K.
- exh2 permanece CERRADO (sellado docs/40 §9.4).

## 10. Archivos

| Archivo | Contenido |
|---|---|
| exh4_poses_train.jsonl | una linea por pose EMITIDA (identidad train|pid|vina_exh4|flex_exh4.out|model_idx) |
| exh4_provenance.jsonl | sidecar FND-06 canonico (14 campos + num_modes_requested/n_models_emitted) por corrida |
| exh4_candidates_train.jsonl | bloques PDBQT byte-fieles materializados por pose emitida |
| metrics.json | por estrato (cobertura/mediana/ITT/tiempos P50-P90) + comparacion 3 niveles + G2 |
| per_complex.jsonl | una linea por complejo (min_rmsd, cubierto, n_poses) |
| failures.jsonl | fallos ITT (sin reintentos) |
| deviations.jsonl | esperado vacio (gate corregido desde el inicio) |
| FORECAST.md / inventory.json | preregistro e inventario (previos, intactos) |
| manifest.json / README.md | registro FND-01 (init/validate; sin seal ni finish) |
