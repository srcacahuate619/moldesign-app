# FORECAST — Entregable 8: Vina flexible exh4 vs MolFlex K15 vs unión

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §15, entregable 8
(Campaña 1, MF-06: "Vina flexible exh=4 y MolFlex son complementarios —
Ruta A exh4 vs MolFlex vs unión. Mejor oráculo/costo por estrato; exh2
queda cerrado").
**Tipo de artefacto:** planificación (forecast + inventario). NO es
experimento: sin manifest, sin docking, sin sellado. Único trabajo
realizado: lectura de artefactos sellados/commiteados y estimaciones.

---

## 0. Resumen ejecutivo

| Concepto | Valor |
|---|---|
| Docks nuevos (brazo Vina exh4) | **44** en DOS ejecuciones: `D-MF-HARD-EXH4` = 34 train (única autorizada ahora) · `D-MF-HARD-EXH4-VAL` = 10 val (solo tras analizar y sellar la interpretación de train), 1 corrida por complejo |
| Docks reutilizados sellados | MolFlex K15: 0 nuevos (34 train + 10 val sellados) · Unión: 0 nuevos (3469 poses selladas) |
| Reutilizables config exacta (Vina) | **0/44** (ruta_a exh4 histórico SIN `--seed`; flexible_redock exh8) |
| CPU total nueva | P50 ≈ **0.8 h** · P90 ≈ **1.5 h** · peor caso ≈ **2.1 h** |
| Wall-time (4 workers) | P50 ≈ 12 min · P90 ≈ 22 min · peor ≈ 32 min |
| Wall-time (6 workers) | P50 ≈ 8 min · P90 ≈ 15 min · peor ≈ 21 min |
| Almacenamiento | ≈ **12 MB** (sin mapas: 1 dock por complejo) |
| Timeouts esperados | ≈ 0 (ruta_a exh4 histórico: 0 fallos en 30 docks, rot hasta 24); ancla de riesgo: 1aaq |
| Identidad de reanudación | `split|pid|vina_exh4|flex_exh4.out|model_idx` |

**Limitación del claim:** el box está centrado en el ligando cristalográfico
y la conformación de entrada es la cristalográfica → este es un benchmark
de REDOCKING/GENERACIÓN dentro de una pocket conocida, NO evidencia
end-to-end para pockets desconocidas.

---

## 1. Inventario (verificado con evidencia)

### 1.1 Brazo MolFlex K15 — sellado, 0 docks nuevos

- **Train:** 34 complejos (17 hard + 17 control), 414 docks K15 (255 hard
  + 159 control), 2690 poses K15. Cobertura ≤2 Å: hard **3/17** (17.6 %),
  control **15/17** (88.2 %). K=15 INMUTABLE (sello f31bfeb).
- **Val:** 10 complejos (5+5), 121 docks (75 hard + 46 control), 949
  poses. Cobertura descriptiva (primera y única ejecución MolFlex K15
  sobre val, sellada): hard 2/5, control 4/5. La cohorte val YA fue
  examinada con MolFlex K15 → NO es ciega para el entregable 8.
- **Evidencia verificada:** `per_complex.jsonl` train = 34 filas ✓, val =
  10 filas ✓; `metrics.json` train/val sellados; manifests GO sellados
  (D-MF-HARD-CURVE commit f31bfeb, D-MF-HARD-CURVE-VAL commit 67817ee).

### 1.2 Brazo unión — sellado, 0 docks nuevos

- MF-01-UNION: **3469 poses** (2739 train + 730 val) sobre **156
  complejos** (116 train / 40 val), 447 corridas de provenance, 0
  colisiones, determinismo byte a byte (manifest + metrics sellados).
- Cohorte D-MF-HARD (44 pids) dentro de la unión: train 957 candidatos
  (802 hard + 155 control), val 129 (74 hard + 55 control). Excepción
  documentada: **1nvq (control val) tiene 0 candidatos en la unión** (sus
  corridas históricas cayeron en el bloque solo-test, 113 runs excluidos
  por alcance docs/49 §4).

### 1.3 Brazo Vina flexible exh4 — cruce cohort × sidecar FND-06

Fuentes cruzadas: `scripts/artifacts_science/D-MF-HARD/cohort.jsonl` (44
pids) × `scripts/artifacts_science/FND-06/poses_provenance.jsonl` (560
registros: 282 molflex / 188 flexible_redock / 90 ruta_a) ×
`scripts/ruta_a_exh_validation.py` × `rescoring/scripts/redock_pdbbind.py`.

**¿Qué exh usaban los históricos?**

| Fuente | exh | seed_docking | box | num_modes | Veredicto vs config exigida |
|---|---|---|---|---|---|
| `flexible_redock` (188 reg, 41 pids de cohorte: 19 hard + 22 control) | **8** (hardcodeado `redock_pdbbind.py:293`) | **unknown** (registros sellados sin `--seed`; el `SEMILLA_VINA=42` del script actual es cierre de garantía futura, posterior a esas corridas) | 25³ centro cristal | 9 | **INCOMPATIBLE** (exh≠4 y seed ausente) |
| `ruta_a` (90 reg = 30 pids × exh {1,2,4}; 14 pids de cohorte: 11 hard + 3 control) | **4 sí existió** (1/2/4) | **unknown** (recuperación sellada: `unknown_vina_sin_flag_seed_seed42_solo_cohorte`; el `SEMILLA_VINA=42` actual es posterior) | 25³ centro cristal | 9 | **INCOMPATIBLE** (exh=4 ✓, box ✓, num_modes ✓, cpu=1 ✓, pero SIN `--seed 42` explícito) |
| Sin registro flexible (1aaq, 1afk, 1afl — los 3 hard train sin flexible_redock ni ruta_a) | — | — | — | — | **NUEVO** (sin evidencia de costo directa salvo molflex rígido histórico y 1aaq timeout V1) |

**Resultado por estrato (clasificación del brazo Vina exh4):**

| Clase | Hard | Control | Total |
|---|---|---|---|
| **Reutilizable** (config exacta exh=4 + `--seed 42` + box 25 + gate enmendado) | 0 | 0 | **0** |
| **Incompatible** (histórico con evidencia de costo: ruta_a exh4 medido y/o flexible_redock exh8) | 19 | 22 | **41** |
| **Nuevo** (sin ningún registro flexible) | 3 (1aaq, 1afk, 1afl) | 0 | **3** |
| **Docks nuevos totales** | 22 | 22 | **44** |

- exh4 YA se usó históricamente (ruta_a, 30 pids, 0 fallos, veredicto
  sellado docs/40 §9.4: exh4 ρ=0.931 PASS, exh2 REFUTADO ρ=0.853). Ningún
  registro histórico cumple la config completa exigida (seed explícito),
  por lo que los 44 docks del brazo son nuevos y los históricos solo
  alimentan el modelo de costo.
- **Dos fases físicas:** los 44 docks se ejecutan en DOS experimentos.
  Fase 1 `D-MF-HARD-EXH4` = 34 train (única autorizada ahora); Fase 2
  `D-MF-HARD-EXH4-VAL` = 10 val, SOLO después de analizar y sellar la
  interpretación de train. Train y val nunca se ejecutan como un solo
  bloque 44/44.

---

## 2. Tiempos históricos por brazo (evidencia real)

### 2.1 MolFlex K15 (sellado, entregable 7, cpu=wall con cpu=1)

| Estrato | n docks | P50 | P90 | Fuente |
|---|---|---|---|---|
| hard train | 510 | 31.25 s | 42.1 s | `D-MF-HARD-CURVE/metrics.json` |
| control train | 179 | 9.2 s | 28.5 s | ídem |
| hard val | 75 | 19.6 s | 24.66 s | `D-MF-HARD-CURVE-VAL/metrics.json` |
| control val | 46 | 11.1 s | 13.65 s | ídem |

### 2.2 Vina flexible (exh4 y exh8 históricos)

- **ruta_a exh4 medido** (`scripts/artifacts_ruta_a.json`, 30 docks, 0
  fallos, timeout 300 s): P50 **76.9 s**, P90 **180.3 s**, max 226.1 s.
  Subconjunto cohorte: hard (n=11) 52.9–226.1 s; control (n=3) 8.0–23.6 s.
- Escala por exh (misma cohorte ruta_a): exh1 P50 18.6 s, exh2 P50 39.4 s,
  exh4 P50 76.9 s — el costo crece ~lineal con exh.
- **flexible_redock exh8**: calibración del maintainer media 35.0 s /
  mediana 6.9 s por complejo (mezcla fácil/difícil, citada en
  FORECAST entregable 7 §3.1); los 74 timeouts de Fase B (300 s, rot media
  25.4) delimitan el estrato duro a exh8.
- **E2 rígido** (`docs/40` §5.5, por complejo de 30 docks rígidos, pool
  12): 1a4w 166 s, 1aaq 320 s, 1ajx 179 s, 10gs 234 s, 184l 12 s — cota
  inferior del costo del estrato duro (el flexible es más lento que el
  rígido: búsqueda torsional exponencial en rot).
- **1aaq**: único `historical_timeout=true` de la cohorte (V1, `vina
  timeout 300s` a exh8, `artifacts_molflex_v1.json`) → ancla de peor caso.

---

## 3. Forecast de cómputo del brazo Vina exh4

### 3.1 Modelo de costo por pid

- Hard: P50 ≈ **100 s**, P90 ≈ **210 s** por dock (11 medidos en ruta_a
  exh4: 52.9–226.1 s, mediana 103.3 s; los 11 sin medir toman el P50 del
  estrato salvo 1aaq).
- Control: P50 ≈ **15 s**, P90 ≈ **30 s** (3 medidos: 8.0/20.5/23.6 s +
  calibración redock: mediana 6.9 s a exh8).
- **1aaq** (rot=18, histórico timeout exh8/300 s): P50 ≈ 240 s, P90 ≈
  300 s (cap de timeout), riesgo de fallo ITT documentado.

### 3.2 Totales

| Magnitud | Cálculo | Valor |
|---|---|---|
| Docks nuevos | Fase 1 `D-MF-HARD-EXH4`: 34 train · Fase 2 `D-MF-HARD-EXH4-VAL`: 10 val (posterior al sello de train) | **44** |
| CPU hard | Σ por pid (11 medidos ruta_a exh4 + 11 estimados) | 0.73 h (P50) / 1.27 h (P90) |
| CPU control | Σ por pid (3 medidos + 19 estimados) | 0.09 h (P50) / 0.18 h (P90) |
| **CPU total** | suma por pid (medidos donde existen + estimados) | **P50 ≈ 0.8 h · P90 ≈ 1.5 h** |
| Train solo | 17+17 | P50 ≈ 0.69 h · P90 ≈ 1.13 h |
| Val solo | 5+5 | P50 ≈ 0.16 h · P90 ≈ 0.33 h |
| **Peor caso** (1aaq a 300 s + 1 retry técnico + cola) | +0.6 h | **≈ 2.1 h** |

### 3.3 Wall-time (CPU=1 por Vina, workers físicos)

| Escenario | 4 workers | 6 workers |
|---|---|---|
| P50 (0.8 h CPU) | ≈ 12 min | ≈ 8 min |
| P90 (1.5 h CPU) | ≈ 22 min | ≈ 15 min |
| Peor caso (2.1 h CPU) | ≈ 32 min | ≈ 21 min |

- **Prohibido 12 workers** (oversubscription histórica documentada en
  `docs/40`, V1: "tiempos 224–421 s por oversubscription de topología").
- Sanidad contra historia: ruta_a ejecutó 90 docks flexibles (exh 1/2/4)
  en **722 s de wall con 4 workers** (`docs/40` §9.4); el brazo exh4 puro
  (44 docks, mezcla más dura) queda en el mismo orden (~12–15 min P50),
  consistente.

### 3.4 Timeouts esperados

- ruta_a exh4: **0 fallos en 30 docks** (incl. rot=24, 1hn4 180.3 s).
- Esperado: **≈ 0–1 docks**. Cap por dock: **300 s** (`FLEX_TIMEOUT` de
  `ruta_a_exh_validation.py`, el mismo de Fase B). Un timeout cuenta como
  fallo ITT → `failures.jsonl`; retry técnico UNA vez documentado.

### 3.5 Almacenamiento

| Componente | Estimación |
|---|---|
| Poses dock (44 × 25.4 KB, medido histórico) | ≈ 1.1 MB |
| Receptor PDBQT (44 × ~200 KB) | ≈ 9 MB |
| Ligando PDBQT flexible + provenance.json + work JSONs | < 2 MB |
| **Total** | **≈ 12 MB** |

Mapas de grid: **no se generan** (1 dock por complejo → sin reuso de
grid; el patrón `--write_maps`/`--maps` del entregable 7 no aplica).

---

## 4. Política de reanudación

1. **Identidad idempotente:** `split|pid|vina_exh4|flex_exh4.out|model_idx`
   (formato MF-01-UNION); `source=vina_exh4`, `file_stem=flex_exh4.out`,
   `model_idx` SOLO para los modelos realmente emitidos (gate enmendado:
   `1 <= n_models_emitted <= 9`, nada de índices fantasma).
2. **Unidad de trabajo:** 1 dock flexible por complejo (conformación
   cristalográfica, preparación Meeko flexible, receptor PDBQT rígido
   pdb_original, centro del ligando cristalográfico).
3. **Resume:** un pid cuyo `flex_exh4.out` existe y parsea bajo el gate
   enmendado NO se repite; se re-ejecutan solo faltantes/fallidos.
4. **Fallos ITT** → `failures.jsonl`: `prep_failed`,
   `receptor_prep_failed`, `meeko_failed`, `rc≠0`, `timeout_300s`,
   `no_scores`, `no_pose`, `gate_invalido`.
5. **Interrupción segura:** checkpoint por complejo; estado reconstruible
   desde `provenance.json` canónico (FND-06: seed_conformer/seed_docking/
   conformer_id/box/exh/num_modes/engine/experiment_id) + out.pdbqt.
6. **Las dos fases** comparten identidad y política; el `experiment_id`
   de provenance distingue la fase (`D-MF-HARD-EXH4` vs
   `D-MF-HARD-EXH4-VAL`).

---

## 5. Config congelada del brazo Vina exh4

| Parámetro | Valor | Estado |
|---|---|---|
| exhaustiveness | **4** | congelado (congelado 2) |
| seed Vina | `--seed 42` **explícito** | congelado (congelado 2); los históricos no lo tenían |
| box | 25³ centrada en ligando cristalográfico | sin cambio (histórico) |
| num_modes | 9 solicitados | sin cambio |
| cpu por Vina | 1 | sin cambio |
| timeout por dock | 300 s | sin cambio |
| engine | Vina 1.2.7 | sin cambio |
| workers | **4 o 6 físicos** (prohibido 12) | congelado (forecast) |
| gate | enmendado: rc=0, 1≤n_models_emitted≤9, scores FINITOS exclusivamente de REMARK VINA RESULT, identidades solo emitidos | heredado de D-MF-HARD-CURVE §8 (enmienda auditada) |
| experiment_id | Fase 1: `D-MF-HARD-EXH4` (34 train) · Fase 2: `D-MF-HARD-EXH4-VAL` (10 val, posterior) | requerido por FND-06 |
| K MolFlex | **15 INMUTABLE** (sello f31bfeb) | congelado 1; cero MF-11, cero v0.6, cero producción (congelado 8) |

**Alcance del claim (box centrado en ligando cristalográfico):** este
benchmark evalúa REDOCKING/GENERACIÓN dentro de una pocket conocida
(box 25³ centrada en el ligando cristalográfico, conformación de entrada
cristalográfica). NO es evidencia end-to-end para pockets desconocidas:
ningún resultado de este entregable se extrapola a búsqueda de novo en
pockets no caracterizadas.

**Implementación por composición (congelado 7):** el runner nuevo importa
y extiende los módulos sellados (patrón `run_molflex_curve_val.py`:
import + reasignación de constantes de módulo + envoltura mínima, nunca
edición). PROHIBIDO editar `run_molflex_curve.py` sellado, cualquier
archivo de `D-MF-HARD-CURVE*`, `ruta_a_exh_validation.py` histórico o
`redock_pdbbind.py` histórico; el wrapper reutiliza `molflex.py`
(`escribir_pdbqt` flexible, `rmsd_pose_pocket`, `parsear_out_vina`,
`prepare_receptor_pdbqt`, `find_binding_center`) sin tocarlo.

---

## 6. Diseño de comparación — denominadores exactos

Métrica de pose: `rmsd_pose_pocket` (marco del pocket, sin alineamiento —
obligatoria según docs/48). Hard y control SIEMPRE por separado
(congelado 3). **Solo train (17+17) decide. Val (5+5): la cohorte YA fue
examinada con MolFlex K15 (sellada `D-MF-HARD-CURVE-VAL`); la ejecución
Vina-exh4 sobre val es la PRIMERA y ÚNICA de ese brazo, pero NO es una
validación ciega ni confirmatoria: solo descriptiva, nunca para elegir
(congelado 5).**

### (a) Operacional completa — cobertura cruda por brazo

- **Numerador:** nº de complejos con `min(rmsd_pose_pocket) ≤ 2 Å` sobre
  TODOS los candidatos del brazo.
- **Denominador:** **17** complejos hard train; **17** complejos control
  train. Val: **5** / **5**, descriptiva (cohorte ya examinada con MolFlex
  K15; no ciega).
- Bracos: MolFlex K15 = poses prefijo 15 selladas (hard 3/17, control
  15/17); Unión = candidatos de `union_candidates_{split}.jsonl`
  restringidos a la cohorte (RMSD pocket recomputado desde el PDBQT
  embebido, sin re-dockear; 1nvq val queda en 0 candidatos documentado);
  Vina exh4 = los 44 docks nuevos (1–9 modos emitidos por complejo).

### (b) Ajustada por CPU — cobertura por CPU-hour

- **Numerador:** cobertura de (a). **Denominador:** CPU-hours del brazo
  (cpu=1 por Vina ⇒ CPU = Σ wall por dock), train y val separados.
  - **MolFlex K15 train:** 255 docks hard × 31.25 s (P50) + 159 control ×
    9.2 s = **2.62 h (P50)** / 255 × 42.1 s + 159 × 28.5 s = **4.24 h
    (P90)**. Val: 75 × 19.6 s + 46 × 11.1 s = **0.55 h**.
  - **Vina exh4:** Σ 44 docks medidos = **0.8 h (P50) / 1.5 h (P90)**.
  - **Unión — tres costes por separado (ninguno puede ser gate):**
    1. **Coste incremental HOY: 0 CPU-hours.** Ningún dock nuevo; la
       unión se materializó sin re-docking (sellada MF-01-UNION).
    2. **Coste histórico de generación: ESTIMABLE-FUERA-DE-ALCANCE.** El
       sidecar sellado FND-06 NO contiene datos de timing (`metrics.json`:
       cobertura `created_at` = 0/4300 conocido); solo cuenta corridas de
       provenance (447 = ruta_a 60 + flexible_redock 143 + molflex 244).
       El coste original de los 447 runs no es estimable desde datos
       sellados.
    3. **Coste estimado de REPRODUCIR la unión** (planificación, orden de
       magnitud, NO gate): ruta_a 60 runs ≈ 0.4–1.2 h CPU (ancla medida
       `artifacts_ruta_a.json`: 90 runs = 1.10 h total, exh4 = 0.62 h);
       flexible_redock 143 runs ≈ 1.4 h (calibración del maintainer:
       media 35 s/complejo a exh8); molflex 244 runs ≈ 0.6–2.1 h (anclas
       selladas curve: hard P50 31.25 s, control P50 9.2 s). Total ≈
       **2.4–4.7 h CPU**, con supuestos explícitos por fuente.
- Reportar por estrato: `cobertura / CPU-hours` **SOLO para MolFlex K15
  vs Vina exh4** (ambos con CPU>0). La unión NO tiene ratio CPU-ajustado:
  `cobertura / 0 CPU-hours` es INDEFINIDO y no puede ser gate; su
  cobertura cruda se reporta junto a los tres costes anteriores.

### (c) Ajustada por candidatos — cobertura vs N candidatos (DESCRIPTIVA, no decisoria)

> **Degradada a métrica descriptiva:** MF-11 aún no deduplica y los
> duplicados distorsionan N, así que esta comparación NO puede decidir.
> Para una comparación decisoria haría falta una curva label-blind con
> presupuestos N iguales por brazo, o esperar MF-11 (entregable 9). Se
> reporta SOLO como descriptiva.

- **N candidatos por brazo por estrato (train):**
  - MolFlex K15: **1450 hard + 1240 control = 2690** poses (prefijo 15).
  - Unión (restringida a cohorte): **802 hard + 155 control = 957**.
  - Vina exh4: modos emitidos 1–9 por dock (esperado ≈ 119 hard + 153
    control ≈ **272**; exacto a ejecución; rango 34–306).
- Reportar: cobertura (a) vs N total por estrato, más eficiencia oráculo
  = cobertura / (N/100) candidatos por estrato.
- Val: igual, descriptiva (ejecución Vina-exh4 sobre val: primera y única
  de ese brazo; la cohorte no es ciega).

### (d) Alcance del claim — redocking/generación en pocket conocida

El box 25³ está centrado en el ligando cristalográfico y la conformación
de entrada es la cristalográfica: este es un benchmark de
REDOCKING/GENERACIÓN dentro de una pocket conocida. NO es evidencia
end-to-end para pockets desconocidas; ningún resultado de este entregable
se extrapola a búsqueda de novo en pockets no caracterizadas.

---

## 7. Preregistro de gates

1. **G1 — ejecución (brazo Vina, DOS fases):** Fase 1 `D-MF-HARD-EXH4`:
   34/34 docks train con gate enmendado (rc=0, 1≤n≤9, REMARK VINA RESULT
   finitos, identidades solo emitidos, provenance 14 campos con seed
   42/42 y experiment_id). Fallos ITT → `failures.jsonl`; violación
   sistemática → STOP.json y reporte, sin continuar. Fase 2
   `D-MF-HARD-EXH4-VAL`: 10/10 docks val, SOLO después de analizar y
   sellar la interpretación de train. Nunca 44/44 como un solo bloque.
2. **G2 — oráculo por estrato (train decide, 4 niveles):**
   - **(i) Líder operacional por conteo:** nº de complejos con cobertura
     ≤2 Å por brazo y estrato, reportado como `n/17`. Da el orden de los
     brazos, NO declara superioridad por sí solo.
   - **(ii) Diferencia pareada:** tabla pareada por pid (mismos 17
     complejos por estrato) con complejos recuperados/perdidos de cada
     brazo frente a cada otro brazo (pares discordantes b/c).
   - **(iii) Inferencia pareada:** McNemar exacto (binomial exacta
     bilateral sobre pares discordantes) o CI pareado de la diferencia de
     proporciones. Con n=17 la potencia es baja: este nivel describe el
     ruido, no declara superioridad por sí solo.
   - **(iv) Superioridad científica:** un brazo gana solo si (i) lo
     favorece Y (ii) no muestra pérdidas netas que lo contradigan Y (iii)
     no contradice a un α nominal (0.05). Si no se cumple, G2 queda
     **INCONCLUSO** — resultado válido y esperable con 17 complejos.
   - **Formato de reporte por estrato:** tabla con los 4 niveles: conteo
     n/17, matriz pareada de discordancia, p de McNemar exacto o CI
     pareado, y veredicto (superior / inferior / INCONCLUSO). Hard y
     control SIEMPRE por separado.
3. **G3 — oráculo/costo:** ratio `cobertura/CPU-hour` SOLO entre MolFlex
   K15 y Vina exh4 (ambos con CPU>0). La unión queda FUERA de la
   comparación CPU-ajustada: `cobertura / 0 CPU-hours` es indefinido; se
   reportan sus tres costes por separado (§6.b). La comparación
   `cobertura/N candidatos` es DESCRIPTIVA (MF-11 aún no deduplica) y no
   decide. Si el brazo de mayor cobertura cuesta >2× la CPU del siguiente
   con ≤1 complejo de diferencia, el tradeoff se DOCUMENTA (no decide
   solo). Solo train (17+17).
4. **G4 — val:** la cohorte val YA fue examinada con MolFlex K15 (sellada
   `D-MF-HARD-CURVE-VAL`) → NO es ciega. La ejecución Vina-exh4 sobre val
   es la PRIMERA y ÚNICA de ese brazo y NO es una validación confirmatoria:
   solo descriptiva (n=5 sin potencia, Wilson CI95). Se ejecuta SOLO
   después de analizar y sellar la interpretación de train. NUNCA para
   elegir.
5. **exh2 CERRADO:** sellado `docs/40` §9.4 — exh2 REFUTADO (ρ=0.853 <
   0.9; exh4 ρ=0.931 PASS). El entregable 8 NO reabre exh2.
6. **GO/NO-GO del entregable 10** (ampliación de MolFlex): se alimenta de
   **7+8**, nunca de 8 solo. Del 7 queda sellado: K15 hard NO_GO (3/17),
   K30 no equivalente, hard_coverage_no_go_3_17 documentado en
   `D-MF-HARD-CURVE/metrics.json`. El 8 aporta el oráculo/costo de exh4
   y de la unión por estrato; la decisión final exige ambos sellos.
7. **Alcance excluido:** cero v0.6 (RS-01), cero deduplicación (MF-11),
   cero cambios de producción, cero reentrenamiento, cero relax, cero
   acceso a test histórico.

---

## 8. Archivos de este directorio

| Archivo | Contenido |
|---|---|
| `FORECAST.md` | este forecast |
| `inventory.json` | clasificación por pid (array plano de 44 filas): `execution_status` (`new_required` para todos), `reuse_status` (`incompatible_history` 41 / `no_history` 3 / `reusable` 0), evidencia histórica (exh real, seed, box, num_modes), tiempos medidos/estimados, fases 1/2 |
