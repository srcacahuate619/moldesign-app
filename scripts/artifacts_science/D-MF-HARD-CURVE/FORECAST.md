# FORECAST — Entregable 7: curva MolFlex 5/15/30 conformeros en D-MF-HARD

**Fecha:** 2026-08-15
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §15, entregable 7
(MF-02, curvas de conformeros sobre la cohorte D-MF-HARD, entregable 6 sellado).
**Tipo de artefacto:** planificación (forecast). NO es experimento: sin
manifest, sin docking, sin sellado. Único cómputo realizado: smoke ETKDG de
prefijo (ver §1) + mediciones de archivos en disco.

---

## 0. Resumen ejecutivo

| Concepto | Valor |
|---|---|
| Docks máximos | 1320 (44 × 30) |
| Docks reutilizados | 0 |
| Docks nuevos esperados | ~850 (hard ~650 + controles ~200, por rendimiento ETKDG) |
| CPU total | P50 ≈ 3.3 h · P90 ≈ 6.7 h · peor caso ≈ 9.3 h |
| Wall-time (4 workers) | P50 ≈ 50 min · P90 ≈ 100 min |
| Wall-time (6 workers) | P50 ≈ 33 min · P90 ≈ 67 min |
| Almacenamiento | ≈ 50 MB (mapas transient) · ≈ 1.1 GB si se conservan mapas |
| Timeouts esperados | ≈ 0 (0 observados en ~600 docks rígidos históricos) |
| Prefijo ETKDG 5/15 ⊂ 30 | CONSERVADO (verificado con hashes, 4 ligandos) |
| Reutilizables por config completa | 0/44 (los históricos no pasaban `--seed` a Vina) |

---

## 1. Smoke de prefijo ETKDG (único cómputo ejecutado)

**Pregunta:** si se genera un ensemble con `numConfs=30` (semilla fija), ¿los
primeros K conformeros (K=5, 15) son idénticos —mismo orden, mismas
coordenadas— a los de una corrida independiente con `numConfs=K`?

**Método:** réplica EXACTA de `scripts/molflex.py` (`leer_ligando` +
`construir_ensemble` importadas del módulo real), sin tocar el código:
`EmbedMultipleConfs(randomSeed=42, useExpTorsionAnglePrefs=True,
useBasicKnowledge=True, pruneRmsThresh=0.4, numThreads=0)`. Evidencia:
sha256 de las coordenadas 3D crudas (dobles, byte a byte) de todos los átomos
por conformero. Ligandos reales del dataset: 1 hard (1aaq, rot=18) y 3
controles (1fv0 rot=4, 1alw rot=4, 1bju rot=3) de D-MF-HARD. RDKit 2025.09.6.
Detalle completo: `prefix_smoke.json` (mismo directorio).

**Resultado: PREFIJO CONSERVADO — veredicto global TRUE en los 4 ligandos.**

| Ligando (estrato) | yield 5 / 15 / 30 | 30⊃5 | 30⊃15 | determinismo 30 |
|---|---|---|---|---|
| 1aaq (hard) | 5 / 15 / 30 | idéntico | idéntico | sí |
| 1fv0 (control) | 3 / 6 / 7 | idéntico | idéntico | sí |
| 1alw (control) | 4 / 8 / 9 | idéntico | idéntico | sí |
| 1bju (control) | 5 / 11 / 15 | idéntico | idéntico | sí |

- "Idéntico" = mismo orden de ids de conformero y mismos hashes sha256
  posición a posición, hasta `min(K, yield_K)`. Para los controles, la
  corrida de K devuelve MENOS de K conformeros (pruning RMSD 0.4 en ligandos
  poco flexibles); todos los que devuelve son el prefijo exacto de la de 30.
- Determinismo: dos corridas de 30 producen ids y hashes idénticos.
- **El prefijo se conserva EN TODOS los casos; la condición de anidamiento
  del maintainer queda verificada. No se necesita la política de "ensemble
  único de 30 por imposibilidad de anidar".**

**Política resultante (curva anidada, valida):**
1. Generar UNA vez el ensemble con `numConfs=30` por complejo (máximo 30).
2. Los puntos de la curva se evalúan sobre los PREFIJOS por orden de índice
   del ensemble de 30: `{0..4}`, `{0..14}`, `{0..29}`.
3. Para complejos con `yield < 15` (controles poco flexibles), los puntos
   15/30 degeneran al ensemble completo (se documenta por complejo:
   `n_conf_5/n_conf_15/n_conf_30` reales).
4. Caveat de entorno: la propiedad se verificó con RDKit 2025.09.6 en esta
   máquina. La ejecución DEBE usar el mismo entorno (RDKit/MeeKo/Vina ya
   inventariados); un cambio de versión de RDKit exige repetir este smoke.

---

## 2. Inventario de runs reutilizables (config COMPLETA)

Fuentes cruzadas: `scripts/artifacts_science/D-MF-HARD/cohort.jsonl` (44
pids) × `scripts/artifacts_science/FND-06/poses_provenance.jsonl` (560
registros: 282 molflex / 188 flexible_redock / 90 ruta_a) ×
`artifacts_molflex_v1/v2/v3.json`.

**Config base del experimento:** `seed_conformer=42` (ETKDG),
`seed_docking=42` (Vina `--seed`, preregistrado FND-06 2026-08-15), box 25³
centrado en ligando cristalográfico, exh=8, num_modes=9, engine vina 1.2.7,
receptor PDBQT rígido (protonación pdb_original), cpu=1 por Vina.

**Hecho central:** los 282 registros molflex históricos tienen
`seed_docking` AUSENTE (campo `seed`=42 es la semilla de CONFORMEROS; Vina se
invocó SIN `--seed` → `seed_docking=unknown` según el contrato canónico
FND-06). Con la config base exigiendo `--seed 42` explícito, NINGÚN run
histórico es reutilizable con configuración completa.

### Clasificación por complejo (44 totales)

| Clase | Hard | Control | Total | Detalle |
|---|---|---|---|---|
| **Reutilizable** (dock existe con config exacta) | 0 | 0 | **0** | — |
| **Incompatible** (molflex histórico, solo para costo) | 3 | 0 | **3** | 1aaq (30 confs, E2), 1afk (20, v4), 1afl (20, v4) — train los 3 |
| **Nuevo** (sin run molflex) | 19 | 22 | **41** | todos los controles + 19 hard |

Notas:
- **1aaq/1afk/1afl:** los docks históricos NO se reutilizan por
  `seed_docking` desconocido (Vina sin `--seed`). Además, 1afk/1afl solo
  tienen 20 conformeros históricos: les faltarían los confs 20–29 para la
  pata 15→30 de la curva aunque el seed coincidiera. Sus tiempos históricos
  SÍ se usaron en el modelo de costo (§3).
- Coincidencia estructural: los 3 incompatibles son los 3 ÚNICOS pids de la
  cohorte sin poses `flexible_redock` en el sidecar (su redock flexible
  falló históricamente por timeout); los otros 41 tienen flexible_redock.
- 1aaq es el único con `historical_timeout=true` en D-MF-HARD (V1, registro
  original `vina_timeout_300s`); es el ancla de peor caso del costo.

---

## 3. Costo por complejo y forecast de cómputo

### 3.1 Tiempo por dock (evidencia histórica REAL)

**Estrato hard (rot ≥ 15):**
- V1 (`artifacts_molflex_v1.json`, 10 de los 74-timeout, cpu=2, lote
  oversubscrito documentado): 15.0–28.1 s/dock, media 22.6 s.
- Probe limpio (docs/40 v4, sin contención, cpu=1): 1aaq 30.6 s fresco /
  30.9 s con mapas (el grid es ~3.5% del dock; los mapas NO aceleran de
  forma material, solo evitan reconstruir).
- E2 (`artifacts_molflex_v2.json`, pool 12, 5 pids): 13.3–25.6 s/dock
  implícito; walls por complejo de 30 confs: 166–330 s.
- v4 (`artifacts_molflex_v3.json`, pool 12, 15 pids): 2–4 s/dock implícito
  en receptores pequeños (1afk 1945 átomos → 2.6–2.9 s).
- **Modelo por estrato:** hard P50 ≈ 15 s/dock, P90 ≈ 31 s/dock (1aaq,
  receptor 3123 átomos, el mayor de la cohorte), mínimo ~3 s (receptores
  1.7–2.3 k átomos: 1j4r, 1afk, 1afl, 1jn4, 1jq8).

**Estrato control (rot ≤ 4, ligando rígido pequeño):**
- Calibración del redock FLEXIBLE (maintainer): media 35.0 s / mediana 6.9 s
  por complejo — los controles son de la clase rápida.
- Rígidos pequeños medidos (v4): 184l ~1.0 s/dock.
- **Modelo:** control P50 ≈ 4 s/dock, P90 ≈ 15 s/dock (receptores de
  control llegan a 15.6 k átomos, p. ej. 1np0; solo los átomos dentro del
  box de 25 Å pagan grid).

### 3.2 Rendimiento ETKDG por estrato (docks reales, no 30 nominales)

- Hard: piden 30 y devuelven ~29–30 (E2: 1aaq 30, 1a4w 30, 1ajx 29, 10gs 29).
- Control: el pruning RMSD 0.4 recorta el yield: smoke 1fv0 7 / 1alw 9 /
  1bju 15 (request 30). Se usa **media ~9–10 conformeros por control**
  (esperado ~200 docks de control; máximo teórico 22×15 = 330).

### 3.3 Totales

| Magnitud | Cálculo | Valor |
|---|---|---|
| Docks máximos (mant.) | 44 × 30 | 1320 |
| Docks nuevos esperados | hard 22×29.5 + control 22×9.5 | **≈ 850** |
| CPU-hard | 650 × 15 s (P50) / × 30.6 s (P90) | 2.7 h / 5.5 h |
| CPU-control | 200 × 4 s (P50) / × 15 s (P90) | 0.2 h / 0.8 h |
| CPU-prep (44 complejos: ETKDG + meeko + receptor + maps, t_prep 0.2–3.5 s + receptor ~2–10 s) | 44 × ~30 s | ≈ 0.4 h |
| **CPU total** | P50 / P90 | **≈ 3.3 h / ≈ 6.7 h** |
| **Peor caso** (todo a P90 + cola de timeouts) | 650×30.6 + 330×15 + prep 1 h | **≈ 9.3 h** |

### 3.4 Wall-time (CPU=1 por Vina, workers físicos)

| Escenario | 4 workers | 6 workers |
|---|---|---|
| P50 (3.3 h CPU) | ≈ 50 min | ≈ 33 min |
| P90 (6.7 h CPU) | ≈ 100 min | ≈ 67 min |
| Peor caso (9.3 h CPU) | ≈ 2.3 h | ≈ 1.6 h |

- **Prohibido 12 workers:** oversubscription histórica documentada en
  `docs/40_MOLFLEX_PROTOCOL.md` (V1: "tiempos 224–421s por oversubscription
  de topología, no del algoritmo") y en el comentario de topología del
  runner V1. Con CPU=1 por Vina, 4 o 6 workers dejan margen para el sistema.
- Sanidad contra historia: E2 hizo 5 hard + 1 control en wall ≤ 330 s con
  pool 12 (2.4 workers/complejo); 22 hard a 6 workers dan ~28–55 min solo de
  hard, consistente.

### 3.5 Timeouts esperados

- Rigidos históricos: **0 timeouts en ~600 docks** (V1 9/10 complejos × 15,
  E2 5/5 × 30, v4 15/15 × 20). Los 74 timeouts de Fase B eran del dock
  FLEXIBLE (exponencial en torsiones), que la curva NO usa.
- Esperado: ≈ 0–1 docks. Cap por dock: **240 s** (`TIMEOUT_DOCK` actual de
  `molflex.py`; el 300 s era el timeout del flexible histórico). Un timeout
  se cuenta como fallo ITT y se registra en `failures.jsonl`.
- Contingencia de peor caso incluida en §3.3 (si 2% de los 850 docks
  agotara 240 s: +1.1 h CPU; no esperado).

### 3.6 Almacenamiento

Medido en disco real (`data/pdbbind/vina_redock_work/*_out.pdbqt`, 218
archivos): media 25.4 KB / rango 2–56 KB por pose (9 modos); receptores
PDBQT 139–270 KB; ligando rígido PDBQT 3–5 KB.

| Componente | Estimación |
|---|---|
| Poses dock (850 esperadas / 1320 max) × 25.4 KB | ≈ 22 MB / 33 MB |
| Receptor PDBQT 44 × ~200 KB | ≈ 9 MB |
| Conformeros rigid+flex PDBQT 44 × ~350 KB | ≈ 16 MB |
| JSONs (center, index_map, provenance, runners) | < 1 MB |
| **Total sin mapas** | **≈ 50 MB** |
| Mapas de grid por complejo (si se conservan; ~15–25 MB c/u) | + 0.7–1.1 GB |

**Política de almacenamiento:** mapas de grid TRANSIENT — se escriben
(`--write_maps`, primer dock del complejo), se reutilizan dentro del
complejo (`--maps`) y se borran al completarlo. Evidencia: los mapas no
aceleran materialmente (probe: 30.6→30.9 s, grid 3.5%), pero evitan
reconstrucción redundante; conservarlos 44× no compensa ~1 GB.

---

## 4. Política de reanudación

1. **Identidad idempotente:** `split|pid|source|file_stem|model_idx`
   (formato MF-01-UNION); `source=molflex`, `file_stem=conf{cid}.out`,
   `model_idx=0..8`.
2. **Unidad de trabajo:** el dock por conformero dentro del complejo
   (`conf{cid}.out.pdbqt` con 9 modelos parseables + scores). Un complejo
   "completado" = sus `n_conf_30` docks parseables en disco.
3. **Resume:** re-ejecutar solo los docks faltantes/fallidos; un dock cuyo
   out existe y parsea NO se repite. El ensemble de 30 se regenera
   determinista (semilla 42, verificado §1) → no es necesario persistirlo,
   pero si se persiste se valida su hash.
4. **Fallos ITT** → `failures.jsonl`: `prep_failed`, `no_conformers`,
   `timeout`, `rc≠0`, `no_scores`, `no_pose`. **Los timeouts cuentan como
   fallos** (no hay reintento automático; un fallo transitorio se retry
   manualmente UNA vez, documentado).
5. **Interrupción segura:** checkpoint por complejo; el estado global es
   reconstruible desde `conf*.out.pdbqt` + `provenance.json` canónico
   (FND-06: `seed_conformer/seed_docking/conformer_id/box/exh/num_modes/
   engine/experiment_id`).

---

## 5. Config base confirmada y justificación de cambios

| Parámetro | Valor | Estado |
|---|---|---|
| seed ETKDG | 42 | sin cambio (histórico y preregistro) |
| seed Vina | `--seed 42` explícito | **CAMBIO vs histórico** — justificado por preregistro FND-06 (2026-08-15): todas las corridas futuras de Vina pasan `--seed 42`; los históricos no lo pasaban (`seed_docking=unknown`). Efecto: 0 reutilizables (los 3 con molflex histórico se re-dockean completos). |
| box | 25³ centrada en ligando cristalográfico | sin cambio |
| exhaustiveness | 8 | sin cambio |
| num_modes | 9 | sin cambio |
| cpu por Vina | 1 | sin cambio |
| timeout por dock | 240 s (TIMEOUT_DOCK actual) | sin cambio de código; el 300 s era del flexible |
| engine | Vina 1.2.7 (tools/vina/vina.exe, verificado `--version`) | sin cambio |
| workers | **4 o 6 físicos** | prohibido 12 (oversubscription documentada) |
| experiment_id | explícito `D-MF-HARD-CURVE` (provenance.json canónico) | requerido por FND-06 |
| relax Fase 3 | NO se ejecuta (curva mide dock rígido por prefijo) | alcance: entregable 7 no incluye relax (es MF-02, no E2) |

---

## 6. Preregistro de la futura ejecución (métricas y decisión)

**Separación hard/control SIEMPRE** (22 hard = 17 train + 5 val; 22
controles = 17 train + 5 val). Métrica de pose: `rmsd_pose_pocket` (marco
del pocket, sin alineamiento) — obligatoria según docs/48; `GetBestRMS` solo
para geometría interna de conformeros.

**Primaria (por estrato, por prefijo 5/15/30):** cobertura/oráculo —
fracción de complejos con `min(rmsd_pose_pocket) ≤ 2 Å` sobre los modos 0–8
de los docks del prefijo.

**Secundarias obligatorias:**
- min-RMSD por complejo (mediana por estrato y prefijo);
- ganancia pareada 5→15 y 15→30: Δ min-RMSD por complejo, bootstrap pareado
  BCa (n=2000, seed 42, CI95 + p bilateral);
- tiempo por complejo (wall y CPU por dock; P50/P90 por estrato);
- fallos ITT (tasa y lista por estrato).

**Regla de decisión (pre-registrada, corregida por el maintainer):** SOLO
train (17+17) decide. Elegir el MENOR K ∈ {5, 15} que, frente a 30 en train:
- pierda como máximo **1/17** complejos hard cubiertos (cobertura ≤2 Å);
- tenga degradación mediana de min-RMSD **≤ 0.1 Å**;
- no pierda más de **un** control cubierto ni degrade su mediana > 0.1 Å.

Si NINGÚN K cumple, elegir **30**. El bootstrap es SOLO informativo, no
decisorio. La política se fija ANTES de abrir val. (Nota: el criterio
anterior exigía que 30 costara >2× que 15, lo que es imposible por
construcción — 30 tiene aproximadamente el doble de docks — y fue
reemplazado por esta regla.)

**val sellado:** los 5 hard + 5 controles de val NO se evalúan hasta fijar
la política; se abren UNA sola vez como verificación piloto descriptiva
(n=5 sin potencia, DESIGN D-MF-HARD §5).

**Alcance excluido:** cero v0.6, cero deduplicación (MF-11), cero cambios
de producción, cero relax, cero re-entrenamiento.

---

## 7. Archivos de este directorio

| Archivo | Contenido |
|---|---|
| `FORECAST.md` | este forecast |
| `prefix_smoke.json` | smoke ETKDG: hashes sha256 por conformero, comparaciones de prefijo, determinismo, veredicto |

---

## 8. Enmienda auditada del gate de ejecución (2026-08-16)

El pilot (1aaq + 1fv0, 30 confs cada uno) reveló que el criterio original
"salida con 9 modos" falla de forma SISTEMÁTICA: Vina 1.2.7 emite entre 2 y
9 modelos por dock (clustering de poses de salida, `min_rmsd=1.0` default),
aunque la tabla de stdout liste 9. La evidencia sellada confirma que es
comportamiento del motor, no un defecto de la corrida: MF-01-UNION contiene
195 corridas molflex históricas con 1-9 modos (mediana 9); 1aaq histórico
solo 9/30 stems con 9 modos; 184l (tipo control) 4/6/9. El gate de igualdad
a 9 contradice el histórico sellado de este mismo pipeline.

**Enmienda autorizada por el maintainer (reglas EXACTAS):**

1. **Validez de cada dock:** `rc=0`, archivo PDBQT no vacío,
   `1 <= n_models_emitted <= 9`, todos los modelos emitidos con score
   FINITO (REMARK VINA RESULT parseable), geometría parseable, y mapeo
   completo identidad↔modelo.
2. **Scores:** EXCLUSIVAMENTE de `REMARK VINA RESULT` del archivo PDBQT
   (nunca de la tabla stdout, que puede listar más modos que el archivo).
3. **Por corrida registrar:** `num_modes_requested=9` y `n_models_emitted`
   (en provenance.json del work dir y en curve_provenance.jsonl).
4. **Identidades SOLO para modelos realmente emitidos:** nada de
   model_idx fantasma hasta 8; si Vina emite 4 modelos, existen 4
   identidades.
5. **Reclasificación del pilot:** los `mode_count_mismatch` del pilot son
   FALSOS FALLOS del gate anterior. NO se redockean; sus tiempos (ya
   medidos) se recuperan y se conservan en
   `scripts/artifacts_science/D-MF-HARD-CURVE/deviations.jsonl` FUERA del
   ITT científico.
6. **Los 2 rc=1 de conf0** (1aaq, 1fv0, root cause: directorio de mapas
   ausente antes de `--write_maps`, corregido en el runner): retries
   TÉCNICOS documentados (`--retry PID`, retry_log.jsonl); si el re-dock
   pasa, no cuentan como fracaso científico pero SÍ en la tasa de
   reintentos (campo `technical_retries` en metrics).
7. **Detención (en ejecución):** cero modelos emitidos, >9 modelos,
   score/geometría inválidos, provenance incorrecto, o fallos sistemáticos
   → STOP.json y reporte, sin continuar.

Implementación: `scripts/run_molflex_curve.py` (función testable
`parse_vina_output(pdbqt_texto)`), tests en
`scripts/test_molflex_curve_gate.py` (stdlib, 11 pruebas: 1/4/9 válidos,
0 y >9 inválidos, score no finito, REMARK ausente, geometría rota,
identidades solo emitidos, formato real con padding NUL, integración
out_valido). Manifest `D-MF-HARD-CURVE` actualizado con el gate enmendado.
El resto de la configuración preregistrada (seed 42 ETKDG+Vina, box 25,
exh=8, 9 modos solicitados, CPU=1, 6 workers, sin relax) NO cambia.
