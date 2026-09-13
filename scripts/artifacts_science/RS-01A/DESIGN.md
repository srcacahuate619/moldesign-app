# RS-01A — Auditoría in-sample del checkpoint v0.6 congelado (DESIGN)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** EJECUTADO (sin seal, sin finish — por instrucción del maintainer)
**Autorización:** maintainer, tras el sello PARAGUAS de preregistro RS-01 (commit `d320bcd`)
**Preregistro:** `scripts/artifacts_science/RS-01/PREREGISTRO.md` §3.3 (lecturas A0/A1/A2), §3.4 (métricas), B4 (vista train-only), B6-ii (31 empates), §3.5 (declaración in-sample)
**Script:** `scripts/run_rs01a_audit.py` (por composición; nada sellado se edita)

## 1. Declaración de resultado (preregistro §3.5, literal)

> El resultado es SOLO una auditoría in-sample de compatibilidad y
> perturbación del checkpoint congelado v0.6 frente a la unión deduplicada
> MF-11-R1. Cualquier diferencia observada no constituye evidencia de mejora
> ni de degradación generalizable; para eso existe RS-01B.

## 2. Runtime planificado y carga del checkpoint

- Intérprete: `python-embed/python.exe` (Python **3.11.9**), xgboost **3.2.0**,
  numpy **2.4.4**, scipy **1.17.1**, rdkit **2025.09.6** — verificado que
  importa xgboost y carga el booster (52 árboles, `best_iteration=51`).
  No se necesitó fallback al python del sistema.
- Checkpoint: `rescoring/artifacts/pose_selector_v06.xgb`, sha256
  `9827ddb94c5ded5b2ef1dda1250606d73f73163becc310641d5bd493196e5d31`
  (199 127 bytes, verificado en carga contra INVENTORY.json sellado). Meta
  `pose_selector_v06_meta.json` sha256 `296b125b…` (contrato 224 raw / 233
  modelo / orden_pct validado contra `FEATURES_TOTAL`).
- Composición solo lectura: `rescoring/pose_selector/selector.py`
  (`PoseSelector` + constantes) y `scripts/dedup_pose_union_medoid.py`
  (`parsear_atomos_pesados`, `rmsd_pocket_pose_vs_pose`, `matriz_distancias`,
  `medoid_detalle`). La transformación z/pct replica `ruta_c_fase1_6_v06.py:217-251`.

## 3. Protocolo ejecutado (tres lecturas independientes)

- **A0 — reproducción histórica exacta**: 2739 poses originales (orden
  canónico `(pid, source, file_stem, model_idx)`), features de conjunto
  CONGELADAS del dataset (variance/range POR-RUN + cluster_density congelada
  de `poses_train.jsonl`) + 215 ricas de la vista train-only
  (`cache_train_only_view.jsonl`, sha `6afeb370…`, identidad posicional
  2739/2739 contra la unión). Alcance C4: NO re-ejecuta el extractor.
  Referencia: `modelo_B.train.top1_rate=0.6724`, `mediana_rmsd=1.425`.
- **A1 — PRIMARIA**: original (2739) vs deduplicado MF-11-R1 (2413 medoids,
  1.5 Å). En AMBOS brazos variance/range POR-RUN congelados. Tras dedup SOLO
  se recalculan `cluster_density` (semántica histórica del dataset builder:
  pares del MISMO complejo con RMSD pocket-frame < 2.0 Å sin alinear,
  UMBRAL_CLUSTER=2.0 — preservada, NO corregida) y, en consecuencia, la
  matriz z/pct por complejo sobre el conjunto resultante.
- **A2 — sensibilidad de producción (SECUNDARIA)**: variance/range POR
  REQUEST en ambos brazos (semántica exacta de `selector.py:219-225`,
  `round(...,4)`; complejo de 1 pose → 0.0). cluster_density: original
  congelada (validada idéntica a la recomputada sobre el conjunto completo),
  dedup recalculada entre supervivientes. Alcance C4: no valida el extractor.

Común a las tres lecturas: z-score por columna dentro de cada complejo
(std==0 → z=0) + rango percentil 0-100 (empates → rango promedio, 1 pose →
50.0) de las 9 columnas `PCT_RAW`; NaN→0 después de transformar; matriz
(N,233); `Booster.predict`; umbral de abstención congelado **0.097663**
(`selector.py:39`); margen = top1 − top2 (N=1 → margen 0 → abstenido).

## 4. Decisión de diseño documentada: fuente de coordenadas de cluster_density

La definición del dataset builder compara poses sobre la MALLA DENSA de
índices mapeados por fuente (serial → índice de átomo pesado del cristal,
mapas por fuente). Las coords PDBQT de la unión comparadas 1:1 por serial NO
reproducen la densidad congelada (2212/2739 discrepancias: los mapas
serial→átomo difieren entre fuentes dentro del mismo complejo). Por tanto la
densidad post-dedup se recalcula desde las coords densas mapeadas de
`data/pose_selector_dataset/records/{pid}.json` (`_coords`, misma malla por
complejo, redondeo a 3 decimales del builder), NO desde el PDBQT crudo.
**Validación dura:** recomputación sobre el conjunto ORIGINAL completo =
valores congelados **2739/2739 exactos** (bloque `validacion_densidad_historica`).

Los **empates de medoid** SÍ se recomputan con la métrica del sidecar sellado
(dmat por serial desde coords PDBQT de la unión — métricas exactas de
`dedup_pose_union_medoid.py`): 2413/2413 representantes coinciden con el
medoid recomputado; 212 no-singleton / 141 empates / 31 cross-source —
coincide 1:1 con MF-11-R1 `metrics.json`.

## 5. Contrafactual de los 31 empates cross-source (B6-ii)

- Identificación por recomputación determinista (no existe lista precocinada).
- Para CADA uno de los 31 clusters: TODOS los medoides alternativos empatados
  (31 alternativas en total) se evalúan reemplazando al representante sellado
  y RECALCULANDO el conjunto completo de resultados A1 (nunca se escoge uno
  después de ver resultados). Por alternativa se reporta: ganador del
  complejo bajo el representante sellado y bajo la alternativa (identidad,
  fuente, RMSD, hit), cambio de ganador/hit, y top1/RMSD globales.

## 6. Métricas y estadística

- Top-1 (ganador = argmax del score por complejo; hit = RMSD ≤ 2.0 Å),
  RMSD mediana/mediadel ganador, ganadores cambiados, pérdidas (hit original
  que se pierde) / recuperaciones, pérdidas/recuperaciones de cobertura,
  margen top1−top2 (mediana + deltas pareados), abstención (t=0.097663) con
  desglose Fase 3 (abstenidos/aceptados × decidibilidad y acierto), fuente
  ganadora CONDICIONADA a máscaras de disponibilidad (B6-iii) + cambios de
  disponibilidad inducidos por la dedup.
- **A1**: McNemar exacto sobre aciertos pareados + bootstrap por las **38
  componentes combinadas** del fold_plan (b; 10 000 réplicas, semilla 42,
  BCa primario con fallback percentil regla C3d) y por **complejo** (c;
  sensibilidad, percentil), sobre la suma de diferencias pareadas de aciertos
  y de RMSD del ganador. Discordancias b/c reportadas explícitamente.
- **A2**: pareado propio + deltas de la semántica por-request vs por-run
  dentro de cada brazo.

## 7. Determinismo y cuarentena

- Determinismo: dos corridas completas → SHA-256 byte-idénticos de
  `metrics.json` (`076B80E4…1DEDA`) y `per_complex.jsonl` (`BBD00343…3C16`).
  Sin timestamps ni aleatoriedad no-seeded en las salidas.
- Cuarentena: `builtins.open` auditado contra whitelist explícita; 130
  archivos del repo abiertos, todos declarados (insumos sellados, módulos
  importados por composición, records train, salidas RS-01A). `poses_val.jsonl`
  y `poses_test.jsonl` NO se abren nunca (0 referencias; verificado
  operacionalmente en la auditoría). `validate RS-01` OK (paraguas intacto),
  `validate MF-11-R1` OK, `validate RS-01A` OK.

## 8. Salidas

| Archivo | Contenido |
|---|---|
| `metrics.json` | bloques A0 (con reproducción histórica), A1 (primaria + pareado + McNemar + bootstrap b/c), A2 (sensibilidad + deltas), empates_contrafactual (31 clusters) + verificación de recomputación |
| `per_complex.jsonl` (116) | por complejo: ganadores A0/A1/A2 con fuente, RMSD, hit, margen, abstención, máscaras de disponibilidad, cambios |
| `failures.jsonl` | vacío (0 fallos) |
| `DESIGN.md` | este documento |

## 9. Estado

Ejecutado y validado; **sin seal y sin finish** (instrucción explícita del
maintainer para RS-01A). Sin commits, sin pip, sin red, sin cambios al
modelo ni a ningún artefacto sellado.

## 10. Corrigendum (maintainer, 2026-08-16)

Correcciones aplicadas sobre `metrics.json` (regenerado por
`scripts/run_rs01a_corrigendum.py`, 2 corridas byte-idénticas, sha
`C6F4A2EF…AEB46`), `manifest.json` y este documento:

1. **Contrafactual NO invariante.** El contrafactual de los 31 empates
   cross-source muestra SENSIBILIDAD al desempate de fuente, NO invarianza:
   base **0.6379**; valores globales observados bajo las 31 alternativas
   **0.6293, 0.6379, 0.6466** (7 cambian ganador, 2 cambian hit). La
   afirmación previa de "Top-1 global invariable" queda corregida.
2. **Estadísticos pareados distinguidos** (recalculados desde
   `per_complex.jsonl`):
   - diferencia de medianas: **+0.032 Å** (1.457 − 1.425) — NO primario;
   - **mediana de diferencias pareadas: 0.000 Å** — **PRIMARIO**: el gate de
     RS-01B (degradación mediana ≤ 0.1 Å) usa la MEDIANA de RMSD_dedup −
     RMSD_original por complejo, y el bootstrap de RMSD de RS-01B debe usar
     ese estadístico — NUNCA la diferencia de medianas ni la suma;
   - media pareada: **+0.0731 Å** (descriptivo);
   - suma pareada: **+8.476 Å** (secundaria, puede conservarse).
3. **Manifest RS-01A**: `git_state` = rama `experimentos/ruta-c-molflex`,
   commit `e095b30…` (HEAD actual); `dependencies` = runtime real verificado
   con `python-embed/python.exe`: python 3.11.9, xgboost==3.2.0,
   numpy==2.4.4, scipy==1.17.1, rdkit==2025.09.6.
4. **Nota de sello**: cuando RS-01A se selle, el bucket de datasets DEBE
   incluir los **116 `data/pose_selector_dataset/records/{pid}.json`**
   (necesarios para reproducir cluster_density — hallazgo de la auditoría:
   la densidad congelada NO es reproducible desde el PDBQT de la unión por
   serial, 2212/2739 discrepancias), además del runner
   (`scripts/run_rs01a_audit.py` y `scripts/run_rs01a_corrigendum.py`), el
   checkpoint y su meta, las entradas selladas y los resultados del
   experimento.
