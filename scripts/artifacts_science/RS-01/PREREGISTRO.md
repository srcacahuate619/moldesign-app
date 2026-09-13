# RS-01 — Preregistro: RS-01A (auditoría in-sample del checkpoint v0.6 congelado) + RS-01B (cross-fitting OOF de clones v0.6)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada ejecutado; sin seal, sin finish)
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` — Cartera D RS-01 (§9), campaña 1 entregables 5 y 9 (§14/§15), gate original de RS-01 (`+3 aciertos OOF, mediana no peor >0.1 Å; luego val >=25/40`). Insumo: `MF-11-R1` sellada GO (commit `0ec65da`, umbral 1.5 Å, 2739→2413, 0 pérdidas, degradación 0.000 Å).

---

## 1. Marco metodológico (del maintainer — se aplica literalmente)

v0.6 fue entrenado exactamente con los mismos 116 complejos / 2739 poses de la unión
original (evidencia: `rescoring/artifacts/pose_selector_v06_meta.json`
`n_train_complejos=116`, `n_train_poses=2739`; `scripts/artifacts_ruta_c_fase1_6.json`).
Por lo tanto, evaluar el checkpoint sobre las 2413 poses deduplicadas de MF-11-R1
sería **IN-SAMPLE** y no puede sostener ningún claim científico de mejora.

División:

- **RS-01A — auditoría del checkpoint congelado** (in-sample): mide compatibilidad
  (¿reproduce el checkpoint congelado su comportamiento histórico sobre las 2739
  originales?) y perturbación (¿cómo cambia su comportamiento al recalcular las
  features dependientes del conjunto sobre las 2413 deduplicadas?). **Declaración de
  resultado: SOLO auditoría in-sample de compatibilidad y perturbación. NO es claim
  de mejora.**
- **RS-01B — evaluación OOF científicamente válida**: cross-fitting de clones v0.6
  con folds simultáneos por scaffold Y receptor, gate primario `+3 Top-1 OOF` y
  degradación mediana `<=0.1 Å`. Es la ÚNICA vía de este experimento que puede
  sostener una afirmación sobre el efecto de la deduplicación.

---

## 2. Insumos sellados (solo lectura — ver INVENTORY.json para hashes completos)

| Insumo | Ruta | Uso en RS-01 |
|---|---|---|
| Checkpoint v0.6 | `rescoring/artifacts/pose_selector_v06.xgb` (+ `pose_selector_v06_meta.json`) | RS-01A: inferencia congelada |
| Selector de producción | `rescoring/pose_selector/{selector.py, feature_extractor.py}` | RS-01A: pipeline de inferencia |
| Dataset congelado | `data/pose_selector_dataset/{poses_train.jsonl, manifest.json, features_v05_progress.jsonl}` | features por pose + transform |
| Unión sellada | `scripts/artifacts_science/MF-01-UNION/union_candidates_train.jsonl` + `union_labels_train.jsonl` | PDBQT embebido + oráculo |
| Dedup sellada | `scripts/artifacts_science/MF-11-R1/` (sidecar `cluster_members_train_1.5.jsonl`, candidates/labels 1.5) | conjunto deduplicado + membresías |
| Fold de referencia | `scripts/build_confirm_cohort.py` + `scripts/build_pose_selector_dataset.py` | algoritmo de asignación de folds RS-01B |
| Entrenador histórico | `scripts/ruta_c_fase1_6_v06.py` + `scripts/artifacts_ruta_c_fase1_6.json` | hiperparámetros y semilla de clones |

Prohibiciones vigentes: NO inferencia v0.6 ni entrenamiento en esta fase (solo
registro del diseño), NO pip, NO red, NO commits, NO seal/finish.

---

## 3. RS-01A — Auditoría del checkpoint v0.6 CONGELADO (in-sample)

### 3.1 Objetivo

Responder dos preguntas de auditoría, sin reclamar mejora:

1. **Compatibilidad**: ¿el checkpoint congelado, ejecutado con el pipeline de
   producción actual (`selector.py` + `feature_extractor.py`), reproduce su
   comportamiento histórico sobre las 2739 poses originales (referencia:
   `modelo_B.train.top1_rate=0.6724`, `mediana_rmsd=1.425` en
   `scripts/artifacts_ruta_c_fase1_6.json`)?
2. **Perturbación**: ¿cómo cambia ese comportamiento cuando las features
   dependientes del conjunto se recalculan DESPUÉS de deduplicar (2413 poses)?

### 3.2 Pipeline de features (contrato EXACTO — no corregir nada)

- **224 features raw** (orden canónico de `FEATURES_TOTAL`, validado en carga por
  `selector.py:151-163` contra `feature_names_raw_224` de la meta):
  - 9 baratas/geométricas: `vina_score`, `pose_score_variance`, `pose_score_range`,
    `n_heavy`, `n_contacts_4`, `n_contacts_6`, `contacts_per_ha_4`, `n_clashes`,
    `cluster_density`.
  - 96 shells: 4 elementos de proteína (C,N,O,S) × 8 de ligando
    (C,N,O,S,F,P,Cl,Br) × 3 cascarones ((0,4),(4,8),(8,12) Å).
  - 56 ECIF-lite: 8 tipos de proteína × 7 de ligando, pares < 6.0 Å.
  - 63 per-residuo: 21 residuos × {4 Å, 6 Å, hbond N/O < 3.5 Å}.
  - Procedencia: extractor v0.5 (`ruta_c_fase1_5_v05.py`, réplica del extractor de
    producción); las 215 ricas viven en el cache congelado
    `data/pose_selector_dataset/features_v05_progress.jsonl` (cabecera valida
    sha256 de los splits; carga fuerte si no coincide — `ruta_c_fase1_6_v06.py:152-160`).
- **233 features de modelo** = 224 z-scores + 9 rangos percentiles (PCT_RAW =
  `[vina_score, n_contacts_4, n_contacts_6, contacts_per_ha_4, n_clashes,
  pose_score_variance, pose_score_range, cluster_density, n_heavy]`).
- **Transformación** (por complejo, independiente por split): z-score por columna
  (std==0 → z=0); rango percentil 0-100 con empates → rango promedio (complejo de 1
  pose → 50.0); NaN → 0 DESPUÉS de transformar. `round(...,4)` en los valores
  congelados de variance/range (contrato del dataset builder).
- **Semántica histórica de `cluster_density` — PRESERVADA, NO corregida** (romperla
  rompería el contrato del modelo entrenado):
  - Dataset builder (`build_pose_selector_dataset.py:662-681` pasada B): pares de
    poses del MISMO complejo con RMSD pocket-frame de átomos pesados <
    `UMBRAL_CLUSTER = 2.0` Å, SIN alineamiento, sobre la malla densa de índices
    mapeados (misma malla por complejo; comparación de posiciones compartidas si
    difieren). Cada pose del par suma 1. Se computó sobre las 2739 poses originales
    (conjunto completo del complejo, todas las fuentes mezcladas).
  - Selector de producción (`selector.py:77-113` `_cluster_density_por_serials`):
    misma definición vía seriales de bloques PDBQT; degrada TODO a 0 con warning si
    los seriales no se alinean entre poses.
  - Para la auditoría de perturbación, la densidad se RECALCULA entre las poses
    SUPERVIVIENTES del cluster de dedup usando la definición del dataset builder
    (coords del PDBQT embebido en la unión), nunca con una definición nueva.
- **`pose_score_variance` / `pose_score_range`**: en el dataset congelado son
  POR-RUN (varianza/rango de los modelos del MISMO `.out` de docking,
  `build_pose_selector_dataset.py:353-361`); el selector de producción los
  sobrescribe con la varianza/rango del conjunto del request
  (`selector.py:219-225`). La auditoría reporta AMBAS lecturas para el conjunto
  deduplicado (la por-run es inmutable por dedup; la de conjunto cambia) y declara
  explícitamente cuál se usa en cada fila de resultados.

### 3.3 Protocolo de ejecución (RS-01A) — TRES lecturas A0/A1/A2 (B1)

La comparación original vs deduplicado se separa en tres lecturas independientes
y NO intercambiables:

- **A0 — reproducción histórica exacta**: conjunto original (2739) con las
  features de conjunto CONGELADAS del dataset (variance/range POR-RUN +
  `cluster_density` congelada). Solo verifica que el pipeline actual reproduce la
  referencia histórica (`modelo_B.train.top1_rate=0.6724`, `mediana_rmsd=1.425`).
  **Alcance EXPLÍCITO (C4): A0 reproduce el CONTRATO HISTÓRICO de features y
  transformación, NO valida el pipeline de producción end-to-end** (no re-ejecuta
  el extractor `feature_extractor.py` sobre geometría nueva; usa las features
  congeladas del dataset/vista).
- **A1 — PRIMARIA (original vs dedup, variance/range POR CORRIDA en ambos brazos)**:
  en AMBOS brazos (2739 y 2413) las features `pose_score_variance`/`pose_score_range`
  conservan los valores POR-RUN del dataset congelado (inmutables por dedup: cada
  pose superviviente mantiene los de su run original). SOLO se recalculan tras
  deduplicar: `cluster_density` (pares entre supervivientes, semántica histórica
  2.0 Å) y, en consecuencia, las columnas z y percentiles afectados (toda la
  matriz z/pct se computa por complejo sobre el conjunto resultante). Esta es la
  comparación principal de perturbación del preregistro.
- **A2 — sensibilidad de producción (SECUNDARIA)**: variance/range POR REQUEST en
  ambos brazos (semántica exacta de `selector.py:219-225`). Mide lo que el selector
  de producción haría HOY con cada conjunto. **Alcance EXPLÍCITO (C4): A2 aplica
  la "semántica de producción" SOBRE features congeladas; TAMPOCO valida el
  extractor end-to-end** (no re-extrae geometría ni re-ejecuta
  `feature_extractor.py`). Se reporta explícitamente como lectura secundaria y
  diagnóstica, nunca como resultado primario.

**RS-01B usa A1 como contrato primario** (ver §4.3): las features de conjunto de
los clones siguen la lectura A1.

Procedimiento común a las tres lecturas:

1. Leer la vista train-only del cache (`cache_train_only_view.jsonl`, 2739
   registros, B4) y `dedup_candidates_train_1.5.jsonl` (2413) — orden canónico
   `(pid, source, file_stem, model_idx)`.
2. Features por pose: cache v05 + 9 baratas congeladas (vista validada por sha y
   por identidad posicional contra la unión). NO re-extraer geometría si la vista
   valida; en contingencia (vista inválida) re-extraer con
   `rescoring/pose_selector/feature_extractor.py` — SOLO train.
3. Por lectura (A0/A1/A2) y por conjunto (original/dedup): recomputar las features
   dependientes del conjunto según el contrato de la lectura.
4. z + pct por complejo → matriz (N, 233) → `Booster.predict` del checkpoint
   congelado (52 árboles, best_iteration 51).
5. Umbral de abstención: `0.097663` (Fase 3; `selector.py:39`). N=1 pose →
   abstenido (margen 0). Margen = top1 − top2.

### 3.4 Métricas RS-01A (por conjunto y pareado original→deduplicado)

- Top-1 crystal-like (RMSD ≤ 2.0 Å) por complejo; total y por fuente ganadora.
- RMSD mediana del ganador (oráculo `union_labels_train`).
- Ganadores cambiados (identidad del ganador distinta tras dedup); pérdidas
  (ganador original correcto que se pierde) y recuperaciones.
- Margen top1−top2 (distribución y cambios); tasa de abstención (t=0.097663);
  abstenidos correctos vs costosos (mismo esquema de Fase 3).
- Fuente ganadora por complejo (flexible_redock / molflex / ruta_a) antes/después,
  **condicionada a MÁSCARAS DE DISPONIBILIDAD de fuentes** (B6-iii): por complejo se
  registra QUÉ fuentes tienen poses en el conjunto (original y dedup); la métrica
  de fuente ganadora se reporta solo dentro de los complejos donde la fuente estaba
  disponible, y los cambios de disponibilidad inducidos por la dedup se listan
  aparte (una fuente que desaparece del complejo no cuenta como "pérdida" del
  selector).
- **Análisis explícito de los 31 empates cross-source** (MF-11-R1 `metrics.json`,
  bloque `empates_medoid`): 212 clusters no-singleton, 141 empates de medoid, 31
  cross-source, en los 31 ganó `flexible_redock` por orden lexicográfico de
  identidad (`split|pid|source|...`, f<m<r). Procedimiento (B6-ii): identificar los
  31 clusters por recomputación determinista de las sumas de distancias del medoid
  (dmat por pid a partir de las coords PDBQT de la unión sellada + membresías del
  sidecar; NO existe lista precocinada — el artefacto solo conserva conteos).
  Para CADA uno de los 31: evaluar TODOS los medoides alternativos empatados y
  recalcular el conjunto completo para cada alternativa (NADA de escoger uno
  después); reportar por cluster: miembros empatados, fuentes de cada uno, fuente
  del representante sellado, y el ganador del selector v0.6 bajo cada alternativa
  empatada (contrafactual de auditoría).

### 3.5 Declaración de resultado RS-01A

"El resultado es SOLO una auditoría in-sample de compatibilidad y perturbación del
checkpoint congelado v0.6 frente a la unión deduplicada MF-11-R1. Cualquier
diferencia observada no constituye evidencia de mejora ni de degradación
generalizable; para eso existe RS-01B."

---

## 4. RS-01B — Cross-fitting OOF de clones v0.6 (evaluación científicamente válida)

### 4.1 Objetivo

Medir OOF si la deduplicación (política MF-11-R1) mejora Top-1 sin degradar RMSD,
con clones v0.6 cuyos hiperparámetros y semillas están CONGELADOS a los del
entrenamiento histórico.

### 4.2 Asignación de folds (K=5, simultánea por scaffold Y receptor) — B2

**Plan de folds MATERIALIZADO y sellable**: `scripts/artifacts_science/RS-01/fold_plan.json`
(generado por `scripts/build_rs01_fold_plan.py`, determinista, 2 corridas
byte-idénticas). Las membresías EXACTAS quedan fijadas ahí; la ejecución RS-01B
debe usarlas sin recalcularlas.

Algoritmo (reutiliza por composición las funciones selladas de
`build_confirm_cohort.py`, sha `a77c8d17...`):

1. **Bloque por scaffold del ligando con política química FND-05**: `scaffold_class`
   = Murcko (`m:<smiles>`), oligosacáridos heurísticos (`oligo:n:o`), y para
   acíclicos **clase propia `acyclic:<ik14>` como unidad de scaffold** (la MISMA
   política usada en FND-05/D-RC-CONFIRM — NO el fallback `pid:<pid>`).
   `scaffold_id` = sha256(scaffold_class)[:12].
2. **Bloque por componente de similitud de cadena del receptor**: secuencias por
   cadena vía SEQRES (fallback CA de ATOM); similitud entre complejos = MÁXIMO del
   solapamiento de k-meros (K=8) sobre pares de cadenas, arista si ≥ 0.90;
   componentes conexas por union-find con cierre transitivo
   (`clusters_cadenas`, ITERACIÓN 3).
3. Grafo combinado: nodos = 116 complejos train; aristas por MISMO `scaffold_class`
   O MISMA componente de cadenas. Componentes conexas = unidades de asignación
   (ninguna cruza folds).
4. Asignación determinista: componentes ordenadas por (tamaño desc, clave canónica
   asc) → asignadas al fold menos lleno (empate → índice de fold menor). Sin
   semilla, sin aleatoriedad.

**Verificación propia (IT1) contra el pre-audit del maintainer** — TODO coincide:
38 componentes combinadas, componente mayor 55, folds `[55, 16, 15, 15, 15]`,
19 ligandos acíclicos (`acyclic:<ik14>`), 0 pids sin secuencia de receptor, 0 sin
scaffold. El fold_plan incluye por complejo: fold, componente, scaffold_id
(política acíclica aplicada), y por fold: tamaños + balance del estrato
hard/control de D-MF-HARD train (leído del cohort sellado).

**Claim honesto del plan**: *near-identity-receptor-disjoint + Murcko-disjoint
donde Murcko está definido* (los acíclicos quedan como clase propia por
InChIKey14, no como Murcko).

### 4.3 Clones y entrenamiento (hiperparámetros CONGELADOS)

- Hiperparámetros EXACTOS del entrenamiento histórico (`ruta_c_fase1_6_v06.py:91-101`
  y `pose_selector_v06_meta.json.hiperparametros`): `XGBRanker(objective=
  "rank:pairwise", max_depth=6, learning_rate=0.05, subsample=0.8, n_jobs=4,
  seed=42, random_state=42, eval_metric="auc" con fallback "rmse")`.
  **n_estimators=52 (B3)** — el del checkpoint efectivo (best_iteration 51 + 1) —,
  **SIN early stopping** (no se usa `early_stopping_rounds`), con TODOS los datos
  del outer-train disponibles para el entrenamiento. Mismo runtime y configuración
  en ambos brazos (original y deduplicado). Relevancia `-rmsd`, grupos por
  complejo, orden canónico `(pid, source, file_stem, model_idx)`.
- **NO usar val 40 para early stopping ni selección** (val está gastada — ver §6).
  Al no haber early stopping no existe ningún ES-set: no hay decisión de
  configuración que tomar dentro del outer-train. La val 40 NUNCA entra al
  pipeline.
- Dos variantes por fold: (a) **original** (todas las poses del fold-train, features
  de conjunto congeladas del dataset), (b) **deduplicada** (fold-train reducido con
  la política MF-11-R1 y features de conjunto recalculadas post-dedup con la
  lectura **A1** del §3.3 — contrato primario de RS-01B).

### 4.4 Anidación del umbral de deduplicación (requisito metodológico)

El umbral 1.5 Å fue elegido observando TODO train (regla MF-11-R1 sobre las 2739),
lo que no es totalmente OOF. Anidación:

- Dentro de CADA fold, elegir U ∈ {0.5, 0.75, 1.0, 1.5, 2.0} usando SOLO el
  fold-train con la regla EXACTA de MF-11-R1 (clustering label-blind de diámetro
  controlado + medoid geométrico con empate por identidad; MAYOR U con 0 pérdidas
  de cobertura ≤2.0 Å, degradación mediana ≤0.1 Å, reducción ≥10%; los labels se
  leen SOLO en la fase de evaluación de la regla — separación de oráculo idéntica
  a `dedup_pose_union_medoid.py`).
- Aplicar el U elegido en el fold-train para entrenar la variante deduplicada, y
  aplicar el MISMO U a las poses del fold de EVALUACIÓN (que el fold nunca vio).
- Reportar el U elegido por fold como diagnóstico de la anidación.
- **Contingencia cerrada ANTES de observar (B6-i)**: si NINGÚN umbral del conjunto
  cumple la regla dentro de un outer-train, ese fold usa **U=None (sin
  deduplicación)** en ambas variantes y se registra la causa; el fold cuenta igual
  en la comparación pareada (no se excluye ni se sustituye el umbral a dedo).

### 4.5 Evaluación pareada y gate primario

- Cada complejo de evaluación recibe puntajes de los DOS clones (original y
  deduplicado del fold correspondiente) sobre las MISMAS poses de evaluación (el
  clon deduplicado ve el conjunto deduplicado con el U anidado del fold).
- Métricas por complejo OOF: Top-1 crystal-like (≤2.0 Å), RMSD del ganador.
- **Comparación pareada** original vs deduplicado sobre los 116 complejos OOF
  (agregados entre folds).
- **Gate OPERACIONAL (OOF)**: `+3 o más aciertos Top-1 OOF` (el clon deduplicado
  gana en ≥3 complejos OOF más que el clon original, pareado) Y `degradación de
  RMSD mediana ≤ 0.1 Å` (mediana de las diferencias pareadas de RMSD del ganador no
  superior a 0.1 Å a favor del original). **El +3 NO equivale por sí solo a
  superioridad estadística** (B5): es un gate operacional; la evidencia estadística
  viene del bootstrap y McNemar de abajo.
- **Incertidumbre PRIMARIA por grupos (B5)**: bootstrap sobre las **38 componentes
  combinadas** del fold_plan (resampling de COMPONENTES con reemplazo, 10 000
  réplicas exactas, semilla 42, BCa) sobre la diferencia pareada de aciertos y de
  RMSD; intervalos por estrato (estratos: máscaras de disponibilidad de fuentes
  B6-iii, complejos cubiertos/no cubiertos por el oráculo, y fold).
  Bootstrap por COMPLEJO SOLO como análisis de sensibilidad, reportado aparte; si
  las dos lecturas (por componente b vs por complejo c) discuerdan sobre el cero,
  la discordancia se reporta explícitamente. Además: **McNemar exacto** sobre la
  tabla 2×2 de aciertos pareados OOF.
- **Bootstrap estratificado — reglas PREREGISTRADAS (C3)**:
  (a) el BCa **PRIMARIO se computa únicamente sobre las 38 componentes globales**
  (sin estratificar);
  (b) los cortes por fold o por estrato con pocas componentes se reportan SOLO
  como **descriptivos con denominador explícito** (n componentes / n complejos);
  (c) **umbral mínimo para intervalos estratificados: ≥5 componentes por
  fold/estrato**; por debajo no se calcula intervalo. Consecuencia declarada:
  **fold 0 tiene 1 componente → sin intervalo para ese fold** (solo descriptivo);
  (d) si el BCa global es **degenerado** (aceleración/jackknife indefinidos o
  NaN), se usa el **fallback al percentil 95% (2.5–97.5) de la distribución
  bootstrap**, registrado explícitamente en metrics como "BCa degenerado →
  percentil bootstrap", sin reinterpretación posterior.
- Reporte secundario: tasa de abstención OOF con el umbral CONGELADO 0.097663
  (el umbral NO se recalibra en RS-01B).

### 4.6 Determinismo

Salidas sin timestamps ni aleatoriedad no-seeded; dos corridas completas deben
producir bytes idénticos (patrón del programa: verificación en DESIGN.md del
experimento ejecutado). Los 10 checkpoints de clones se guardan con su sha256.

### 4.7 Contingencias cerradas ANTES de observar (B6)

1. **U=None por fold**: si ningún umbral de dedup cumple la regla dentro de un
   outer-train → U=None (sin deduplicación en ese fold), causa registrada, el fold
   participa igual (ver §4.4).
2. **31 empates cross-source**: se evalúan TODOS los medoides alternativos
   empatados y se recalcula el conjunto completo para cada alternativa; nada de
   escoger un representante después de ver resultados (ver §3.4).
3. **Máscaras de disponibilidad de fuentes** sustituyen a "fuente dominante": la
   métrica de fuente ganadora se condiciona a qué fuentes tenían poses en cada
   complejo antes y después de deduplicar (ver §3.4).
4. **Umbral de abstención**: congelado (0.097663); si la tasa de abstención OOF
   difiere entre brazos por cambios de N de poses, se reporta el desglose por
   número de poses del complejo y NO se recalibra el umbral.

---

## 5. Gates y decisiones

| Nivel | Artefacto | Uso en RS-01 |
|---|---|---|
| PRIMARIO (estadístico) | RS-01B OOF (116 complejos, folds del fold_plan) | Bootstrap por las 38 componentes (10 000 réplicas, BCa) + McNemar exacto sobre aciertos pareados; degradación de RMSD mediana ≤0.1 Å |
| OPERACIONAL | RS-01B OOF | Gate `+3 Top-1 OOF` (no equivale por sí solo a superioridad estadística — B5) |
| DESCRIPTIVO | val (40 complejos, 730 poses) | SOLO reporte descriptivo, sin gate (ver §6) |
| SELLADO, INTOCADO | test (47 complejos, 831 poses) | CERO uso en RS-01 |
| SELLADO, INTOCADO | D-RC-CONFIRM (denylist 112 pids) | CERO uso en RS-01 |

Decisión posterior (NO en este preregistro): si el gate primario OOF PASA, el
siguiente paso natural sería proponer el uso de val UNA sola vez dentro del marco
reformulado del programa; si NO PASA, la deduplicación no cambia materialmente el
comportamiento OOF del selector y se documenta.

---

## 6. Val 40 — estado y por qué es solo descriptiva

- val = 40 complejos / 730 poses (`data/pose_selector_dataset/manifest.json`).
- Gastada: (1) early stopping del entrenamiento v0.6
  (`ruta_c_fase1_6_v06.py:366-382`, `eval_set` val); (2) barrido del umbral de
  abstención de Fase 3 sobre cuantiles de márgenes de val
  (`ruta_c_fase3_calibracion.py:492-506`, regla `255-274`); (3) la desviación D1
  de MF-11 procesó val junto con train → "la val actual ya no puede validar
  ninguna variante posterior" (`MF-11/DESIGN.md:136`); MF-11-R1 la EXCLUYÓ por
  completo (`MF-11-R1/DESIGN.md` §1).
- Además, el gate histórico `val >= 25/40` no se cumple ni con la lectura
  histórica: v0.6-B val top1 = 0.575 = 23/40 (`artifacts_ruta_c_fase1_6.json`,
  `modelo_B.val`).
- Conclusión: val NO puede sostener gate confirmatorio alguno. Solo se reporta de
  forma descriptiva (si acaso) y NUNCA como decisión.

## 7. Test y D-RC-CONFIRM — sellados e intocados

- Test: 47 complejos, `poses_test.jsonl` sha `a36d1245...`, `test_pids_sha256` en
  el manifest del dataset. MF-11-R1 verificó `n_test_manifest=47`, intersección con
  la unión = `[]` y leyó SOLO metadatos (`poses_test.jsonl` NUNCA se abre).
- D-RC-CONFIRM: `FND-05/denylist_pids.json` sellado (n=112, sha `93186207...`,
  `sha256_candidates` verificado); intersección con la unión = `[]`.
- Este diseño NO abre, NO lee poses, NO ejecuta inferencia ni entrenamiento sobre
  test o denylist en ninguna fase de RS-01. Cero referencias a ejecutarlos.

## 8. Sello paraguas, runtime planificado y vista del cache (B7/B4/C4)

- **Sello PARAGUAS DE PREREGISTRO**: el sello de RS-01 congela este preregistro
  (documentos, fold_plan, vista del cache y scripts de planificación). Las
  EJECUCIONES y sus RESULTADOS vivirán y se sellarán por separado como **RS-01A** y
  **RS-01B** (experimentos propios del manifest, cada uno con su gate, metrics y
  trazabilidad).
- **Clasificación EXACTA de buckets del sello paraguas (C4)**:
  - **dataset_hashes**: `scripts/artifacts_science/RS-01/fold_plan.json`,
    `scripts/artifacts_science/RS-01/cache_train_only_view.jsonl`,
    `scripts/artifacts_science/RS-01/cache_view_manifest.json`,
    `data/pose_selector_dataset/poses_train.jsonl` (fuente de las 8 features
    baratas que NO están en la unión — ver abajo).
  - **model_hashes**: `rescoring/artifacts/pose_selector_v06.xgb` (checkpoint) +
    `rescoring/artifacts/pose_selector_v06_meta.json` (meta del contrato).
  - **assets_hashes**: `PREREGISTRO.md`, `INVENTORY.json`, `FORECAST.md`,
    `scripts/build_rs01_fold_plan.py`, `scripts/materialize_cache_train_view.py`,
    `scripts/experiment_manifest.py`, `scripts/artifacts_science/manifest.schema.json`.
  - **EXCLUIDOS del sello**: `scripts/artifacts_science/RS-01/manifest.json` y
    `README.md` (el propio proceso de sellado los regenera/modifica).
- **Las 8 features baratas con fuente en `poses_train.jsonl`** (documentadas en
  INVENTORY.json → `checkpoint_v06.contrato_features`): `pose_score_variance`,
  `pose_score_range`, `n_heavy`, `n_contacts_4`, `n_contacts_6`,
  `contacts_per_ha_4`, `n_clashes`, `cluster_density`. La novena
  (`vina_score`) NO se lee de `poses_train.jsonl` porque ya está en
  `union_candidates_train.jsonl` (campo `vina_score` por identidad).
- **Runtime planificado** (registrado en `manifest.json` → `dependencies`):
  Python **3.11.9** verificado en el repo (`python-embed/python.exe`, venv embebido
  de la herramienta), XGBoost **3.2.0**, NumPy **2.4.4**, SciPy **1.17.1**, RDKit
  **2025.09.6**. (Antes: declarado "a localizar"; IT1 localizó y verificó el
  intérprete 3.11.9 con las cuatro dependencias instaladas.)
- **Vista train-only del cache (B4)**: `cache_train_only_view.jsonl` (2739
  registros, bytes exactos del bloque train de `features_v05_progress.jsonl`,
  identidad posicional verificada contra la unión 2739/2739) +
  `cache_view_manifest.json` (sha de la vista, provenance del sha del origen SIN
  recalcular, rangos de registros/bytes, bytes leídos del origen — solo el bloque
  train — y auditoría de archivos abiertos). El loader RS-01A/RS-01B debe
  leer ESTA vista, NUNCA `cargar_cache_v05()` (que abriría train+val+test del
  cache completo).

## 9. Referencias archivo:línea (evidencia)

- Checkpoint/meta: `rescoring/artifacts/pose_selector_v06_meta.json:4-6,481-492,612-619`.
- Contrato de features: `scripts/ruta_c_fase1_6_v06.py:47-101`; `selector.py:39-40,44-113,151-163,219-243`.
- cluster_density histórica: `scripts/build_pose_selector_dataset.py:57,662-681`; `selector.py:77-113`.
- Entrenamiento v0.6: `scripts/ruta_c_fase1_6_v06.py:366-382`; resultados `scripts/artifacts_ruta_c_fase1_6.json` (`modelo_B`, `duracion_total_s=5.3`).
- Dedup: `scripts/dedup_pose_union_medoid.py:186-245` (sidecar + empates); `MF-11-R1/metrics.json` (`empates_medoid`, `exclusiones`, `label_blind`).
- Folds: `scripts/build_confirm_cohort.py:126-127,282-400`; fold_plan materializado `scripts/artifacts_science/RS-01/fold_plan.json` (generador `scripts/build_rs01_fold_plan.py`).
- Vista del cache: `scripts/materialize_cache_train_view.py` + `scripts/artifacts_science/RS-01/cache_view_manifest.json`.
- Umbral de abstención: `scripts/ruta_c_fase3_calibracion.py:232-274,492-506`; `selector.py:38-39`.
- Val gastada: `scripts/artifacts_science/MF-11/DESIGN.md:136-137`; `MF-11-R1/DESIGN.md` §1.
