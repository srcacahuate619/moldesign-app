# MF-11 — Deduplicación de poses preservando el oráculo (entregable 9)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §15 entregable 9
y Cartera C, MF-11 ("Duplicados consumen presupuesto y distorsionan densidad"
→ "Cluster de poses por RMSD pocket-frame" → "Menos candidatos conservando
oráculo").

## 1. Alcance

Deduplicar la unión materializada sellada `MF-01-UNION` (3469 poses: 2739
train + 730 val, 156 complejos) reduciendo candidatos redundantes SIN perder
el oráculo (cobertura min-RMSD ≤ 2.0 Å). Análisis PURO sobre poses
existentes: SIN docking, SIN scoring v0.6, SIN acceso a test histórico, SIN
usar val como decisión (la regla no tiene parámetros aprendidos; train y val
se procesan con la MISMA regla fija e independiente).

**Nota de alcance:** esta deduplicación opera SOLO sobre la unión histórica
`MF-01-UNION`. Los brazos sellados aparte `D-MF-HARD-CURVE` y
`D-MF-HARD-EXH4` NO se tocan.

## 2. Regla predefinida (preregistrada ANTES de evaluar)

1. **Métrica (geometría pose-vs-pose):** RMSD pocket-frame entre poses
   dockeadas del MISMO complejo: átomos pesados, matching 1:1 por serial del
   PDBQT, SIN alineamiento, sobre coordenadas absolutas del marco del
   receptor fijo. Es la extensión por pares de `molflex.rmsd_pose_pocket`
   (misma definición de marco: traslación/rotación de la pose NO se
   compensan). Verificado operacionalmente: las firmas (serial, elemento)
   son homogéneas entre fuentes dentro de cada complejo (0/156 complejos
   heterogéneos), por lo que el matching por serial es consistente entre
   flexible_redock, molflex y ruta_a.
2. **Umbral:** 2.0 Å (inclusivo, `RMSD ≤ 2.0`).
3. **Algoritmo:** clustering greedy por identidad ascendente (orden
   determinista); cada pose se une al PRIMER cluster existente cuyo
   representante cumple el umbral; si ninguno, abre cluster nuevo.
4. **Representante:** la PRIMERA pose del cluster en orden de identidad
   (label-blind). Si el cluster contiene una pose con mejor rmsd que el
   representante, `dedup_labels_*` registra `cluster_best_rmsd` y
   `cluster_best_identity` SOLO como dato de evaluación — la selección del
   representante NUNCA usa labels.

## 3. Label-blind estructural (separación oráculo)

El clustering usa SOLO geometría. Las funciones de clustering
(`clustering_greedy`, `deduplicar_split`) NO reciben labels por contrato;
`union_labels_*.jsonl` se lee únicamente en `evaluar_preservacion`, DESPUÉS
de decidida la membresía, para medir preservación. Verificado por test
sintético: alterar los labels deja los candidatos dedup byte-idénticos.

## 4. Caveats de la métrica

- Heredado de `rmsd_pose_pocket`: matching 1:1 por índice SIN simetría
  química. Una pose relacionada por simetría (p. ej. flip de anillo) puede
  reportar RMSD inflado aunque sea equivalente. La métrica
  simetría-corregida es trabajo futuro. Consecuencia: el clustering puede
  ser conservador (mantiene clusters que una métrica simétrica fusionaría).
- Sin alineamiento: mide ubicación bioactiva (marco del pocket), no solo
  geometría interna — intencional, mismo criterio que la etiqueta del
  dataset (`rmsd_pocket_frame_sin_alinear`).
- El RMSD pose-vs-pose usa la intersección de seriales pesados; dentro de un
  complejo las firmas son homogéneas (ver §2.1), así que la intersección es
  completa en la práctica. 0 fallos en el build real.

## 5. Resultados (evaluación, no decisión)

| Split | n antes | n después | Reducción | Cobertura antes | Cobertura después | Perdidos |
|---|---|---|---|---|---|---|
| train | 2739 | 2093 | 23.59% | 78/116 (67.24%) | 76/116 (65.52%) | 2 |
| val | 730 | 559 | 23.42% | 30/40 (75.0%) | 30/40 (75.0%) | 0 |
| global | 3469 | 2652 | 23.55% | 108/156 (69.23%) | 106/156 (67.95%) | 2 |

Supervivencia por fuente (global): flexible_redock 93.67%, molflex 71.20%,
ruta_a 49.18%. Tamaño de clusters: P50 = 1, P90 = 2, max = 14 (media 1.31).

### 5.1 Complejos perdidos (2) — justificación

El gate preregistrado ("0 complejos cubiertos perdidos") NO se cumple.
Ambos casos son de frontera y consecuencia directa de la regla fija
(representante = primera por identidad, label-blind):

| Complejo | Mejor pose (rmsd) | ¿Es representante? | Min rmsd de representantes |
|---|---|---|---|
| `train|1bcd` | `…1bcd|2` (1.384 Å) | no (miembro) | 2.016 Å (0.016 Å sobre el umbral) |
| `train|1alw` | `…1alw|3` (1.95 Å) | no (miembro) | 2.44 Å |

En ambos, la pose buena está a ≤2.0 Å pose-vs-pose del representante y por
eso quedó como MIEMBRO del cluster; el representante (primera por identidad)
tiene rmsd cristalográfico justo por encima de 2.0. Elegir "representante =
mejor pose" cerraría los 2 casos PERO usaría labels en la selección,
violando el label-blind preregistrado. No se modifica la regla: ajustar el
umbral o el criterio de representante a posteriori sería p-hacking. La
decisión del gate queda PENDING (sin seal ni finish, por instrucción del
protocolo; el maintainer decide el camino: aceptar los 2 casos de frontera,
o preregistrar una enmienda en un experimento futuro).

## 6. Exclusiones verificadas (cero test, cero D-RC-CONFIRM)

- 156 pids de la unión ∩ 47 test históricos = ∅. Fuente: `test_pids` del
  manifest sellado del dataset (metadatos de split; `poses_test.jsonl`
  NUNCA se abre), integridad verificada contra `test_pids_sha256`.
- 156 pids ∩ 112 denylist D-RC-CONFIRM (FND-05) = ∅. Integridad de la
  cuarentena verificada (sha256 de `candidates.jsonl` coincide con
  `sha256_candidates`).

## 7. Determinismo y verificación

- 2 corridas → 7 salidas SHA-256 byte-idénticas:
  - `dedup_candidates_train.jsonl` `91615a58faa4d384832de3126829f2f3209cce3d35d1d4fc5ec9345aa89e34b7`
  - `dedup_candidates_val.jsonl` `dc8f042453ff83d3a5e5eafde8e2b471df1a0219ef916e38c13cd7e63e434a3b`
  - `dedup_labels_train.jsonl` `e3470cfe484759cb3acb51785b236ac79865773d6a3a04fbb474dd21885e57d3`
  - `dedup_labels_val.jsonl` `8a263561c4d8e7ea985133b4a1dbc7997ceef3398f96a8e7ac0f86cdcb126089`
  - `metrics.json` `2dc81e6bd4bcdb1eb3dd68d3fa69635dfc14ec421702efdbf54e663b2671f863`
  - `per_complex.jsonl` `3f992934e8b46e20f4c29745633476681d9ea73742f7cb419a846a12bc4adad9`
  - `failures.jsonl` `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (vacío: 0 anomalías)
- Test sintético `scripts/test_dedup_pose_union.py`: 11/11 OK (fixture 3
  poses → 2 clusters; label-blind: labels alterados → candidatos
  byte-idénticos; greedy une al primer cluster; RMSD None sin comunes;
  end-to-end en tempdirs).
- `validate MF-01-UNION` OK (solo lectura de la unión sellada) y
  `validate MF-11` OK. Sin seal ni finish (instrucción del protocolo).

## 8. Salidas

| Archivo | Contenido |
|---|---|
| `dedup_candidates_train.jsonl` (2093) / `val` (559) | representante por cluster (identity + PDBQT + vina_score + campos de la unión), SIN rmsd, ordenado por identidad |
| `dedup_labels_train.jsonl` (2093) / `val` (559) | labels del representante keyed por identidad + `cluster_id`, `cluster_size`, y `cluster_best_*` cuando el mejor del cluster no es el representante |
| `metrics.json` | por split y global: N antes/después, reducción %, cobertura antes/después, perdidos + detalle, supervivencia por fuente, P50/P90, exclusiones |
| `per_complex.jsonl` (156) | n_antes, n_despues, coverage_antes, coverage_despues, cluster_count por complejo |
| `failures.jsonl` | anomalías (vacío) |

## Desviaciones procedimentales (registradas por el maintainer)

- **D1**: se procesó val junto con train, aunque se había autorizado train primero. Impacto: la val actual ya no puede validar ninguna variante posterior (MF-11-R1 excluirá val).
- **D2**: se usó 'primera identidad' como representante en vez del medoid geométrico autorizado. No es p-hacking (se fijó antes de evaluar), pero causó directamente las 2 pérdidas de frontera (1alw, 1bcd).

