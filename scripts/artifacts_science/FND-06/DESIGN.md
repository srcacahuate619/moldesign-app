# FND-06 — Provenance de poses: diseño, contrato y auditoría histórica

**Fecha:** 2026-08-15
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md`, Cartera A, FND-06.

> "Provenance de poses explica parte del error" — Persistir `source`, seed,
> conformer, exhaustiveness, box y preparación. Gate: 100% de poses
> experimentales trazables.

## 1. Contexto y alcance

El dataset pose-selector (`data/pose_selector_dataset/poses_{train,val,test}.jsonl`,
4300 poses: 116/40/47 complejos) fue construido por
`scripts/build_pose_selector_dataset.py` a partir de tres fuentes:

| Fuente | Poses | Complejos | Corrida generadora |
|---|---|---|---|
| `molflex` | 2213 | 18 | `scripts/molflex_exp_v3.py` (olas e2 y v4) |
| `flexible_redock` | 1534 | 188 | `rescoring/scripts/redock_pdbbind.py` (exh=8) |
| `ruta_a` | 553 | 30 | `scripts/ruta_a_exh_validation.py` (exh 1/2/4) |

Nota: 18 + 188 + 30 = 236 es la suma por fuente CON solapamientos (un pid
puede aportar poses desde varias fuentes). El número correcto de complejos
únicos verificados es 203 (116 train + 40 val + 47 test).

El builder descartó en la ingesta todo metadato de corrida: solo persistió
`pid`, `source`, `file_stem`, `model_idx` y features de pose. Ninguna pose
tiene seed, conformer, exhaustiveness, box ni preparación.

FND-06 persigue dos cosas distintas y explícitas:

1. **Contrato canónico para poses NUEVAS** (garantía 100% a futuro).
2. **Auditoría honesta del histórico** (qué es recuperable de fuentes
   verificables y qué es irrecuperable, marcado `unknown`, jamás inventado).

## 2. Contrato canónico v1 (poses nuevas)

Campos obligatorios por pose:

| Campo | Tipo | Notas |
|---|---|---|
| `source` | enum | `molflex` \| `flexible_redock` \| `ruta_a` \| `futuro` |
| `seed_conformer` | int \| `"crystal"` \| `"unknown"` | semilla de generación de conformeros (ETKDG); `"crystal"` si el input es la conformación cristalográfica (sin generación estocástica) |
| `seed_docking` | int \| `"unknown"` | semilla de Vina `--seed` (preregistrada: 42 desde 2026-08-15) |
| `conformer_id` | int \| `"crystal"` \| `"unknown"` | índice de conformero de entrada, o `crystal` si se usa la conformación cristalográfica |
| `exhaustiveness` | int \| `"unknown"` | exh de Vina |
| `num_modes` | int \| `"unknown"` | modos de salida de Vina |
| `box` | dict | `{center: [x,y,z] \| "unknown", size: [x,y,z], method: center_from_crystal_ligand \| molpocket_top1 \| fixed}` |
| `preparation` | dict | `{ligand: {method, tool, version}, receptor: {protonation, tool}}` |
| `engine` | dict | `{name: "vina", version}` |
| `experiment_id` | str | identificador del experimento/corrida (manifest FND-01) |
| `created_at` | ISO 8601 \| `"unknown"` | instante de la corrida |

Los registros del backfill histórico usan la forma legacy `seed` (un solo
campo, antes de separar las semillas); el canónico futuro separa
`seed_conformer`/`seed_docking`. El verificador acepta ambas formas y trata
la familia de semillas como un solo concepto para la cobertura.

Opcionales recomendados: `cluster_id`, `dedup_rmsd_threshold`, `timeout`.

### Semántica de `unknown`

El string `"unknown"` es el marcador honesto de irrecuperable: el campo está
presente y la fuente original no lo registró. Un campo AUSENTE es una
violación del contrato (fallo de esquema), no un desconocido. El verificador
distingue ambos: `--check` falla ante campos ausentes o registros inválidos;
`--strict-unknown` falla además ante `unknown` (gate de poses NUEVAS).

### Extensibilidad

El contrato es un mínimo. Los registros pueden portar campos extra
(`n_conf`, `run`, `recovery`, `cpu`, `fallback`, ...) — `additionalProperties`
queda abierto. `recovery` documenta de dónde salió cada campo (fuente
verificable o motivo de `unknown`).

## 3. Decisión: SIDECAR `poses_provenance.jsonl` (no inline)

**Decisión: sidecar**, un registro por corrida con clave `pid|source|file_stem`.

Justificación:

1. **Integridad del dataset**: los tres JSONL están sellados por
   `data/pose_selector_dataset/manifest.json` (SHA-256 por archivo) y la regla
   del laboratorio prohíbe modificar el dataset. Agregar campos inline
   invalidaría los hashes y tocaría un activo sellado.
2. **Granularidad natural**: los 10 campos del contrato son constantes por
   corrida (archivo de poses), no por `model_idx`. Inline duplicaría el mismo
   registro ~9× por archivo (los 9 modos de Vina comparten seed, box,
   preparación, etc.). Sidecar almacena cada dato una sola vez.
3. **Compatibilidad**: los consumidores actuales (training de selectores)
   leen las claves de `ORDEN_CLAVES`; el sidecar es aditivo y no cambia ni una
   línea de poses. Si un día se requiere provenance por modelo, se añade una
   lista opcional `per_model` al registro (el contrato lo permite).
4. **Verificable en frío**: `pose_provenance.py --check` valida las poses
   contra el sidecar sin tocar el dataset.

Cuándo usar inline: datasets futuros AÚN no sellados que quieran empaquetar
todo en un solo archivo (el checker soporta ambos modos). El modo canónico del
programa experimental es sidecar.

## 4. Auditoría histórica (cobertura real, 4300 poses)

Ejecutada con `pose_provenance.py --check` contra el sidecar generado por el
backfill. Cobertura por campo y fuente (conocido / unknown / faltante):

| Campo | molflex (2213) | flexible_redock (1534) | ruta_a (553) |
|---|---|---|---|
| source | 100% | 100% | 100% |
| seed | 100% (42) | 0% | 0% |
| conformer_id | 100% (stem) | 100% (crystal) | 100% (crystal) |
| exhaustiveness | 100% (8) | 100% (8) | 100% (stem exh1/2/4) |
| num_modes | 100% (9) | 100% (9) | 100% (9) |
| box | 100% (derivado) | 100% (derivado) | 100% (derivado) |
| preparation | 100% | 100% | 100% |
| engine | 100% (vina 1.2.7) | 100% | 100% |
| experiment_id | 100% | 100% | 100% |
| created_at | 0% | 0% | 0% |

El `seed` del histórico es la forma legacy del contrato: para molflex
corresponde a `seed_conformer` (ETKDG=42); para flexible_redock y ruta_a el
`seed_docking` es desconocido porque Vina se invocó sin `--seed`.

**Trazabilidad por pose:** 0 poses con los 10 campos conocidos (`created_at`
es desconocido en todas las corridas históricas). 2213 poses molflex (51.5%)
tienen 9/10 (único `unknown`: `created_at`); 2087 poses de flexible_redock y
ruta_a (48.5%) tienen 8/10 (`unknown`: `seed` y `created_at`). Ninguna pose
tiene campos faltantes: el contrato se cumple estructuralmente en el 100% de
las poses; lo que falta es información que las corridas originales nunca
registraron.

### Qué se recuperó y de dónde

- **seed molflex = 42**: constante `randomSeed=42` de `construir_ensemble`
  (`scripts/molflex.py`), preregistrada en el protocolo 40.
- **conformer_id**: convención de nombres `conf{cid}.out` (molflex);
  `"crystal"` para flexible_redock/ruta_a (input = conformación
  cristalográfica + `AddHs`, documentado en `redock_pdbbind.py` y
  `ruta_a_exh_validation.py`).
- **exhaustiveness/num_modes**: constantes hardcodeadas en los tres
  generadores (8/9; ruta_a exh desde el nombre `exh{N}`).
- **box**: tamaño 25 Å (constante en `molflex.py` y `redock_pdbbind.py`);
  centro = centroide de átomos pesados del SDF cristalográfico (definición de
  `rp.find_binding_center`), **derivado determinista** con parser SDF V2000
  stdlib. Verificación: 203/203 complejos únicos coinciden con
  `rp.find_binding_center` (RDKit 2025.09.6) a 3 decimales. El denominador
  correcto es 203 complejos únicos del dataset; 236 = suma por fuente con
  solapamientos (18 molflex + 188 flexible_redock + 30 ruta_a).
  Marcado `center_derived: true`.
- **preparation**: cadenas documentadas en el código (ligando: meeko
  MoleculePreparation + PDBQTWriterLegacy, v0.7.1; receptor: Open Babel
  PDB→PDBQT rígido `-xr` conservando protones del PDB — `pdb_original` —,
  fallbacks documentados).
- **engine**: Vina 1.2.7 (`artifacts_molflex_v3.json:probe`; reconfirmado con
  `vina.exe --version`).
- **n_conf / corrida molflex**: `artifacts_molflex_v3.json` por pid
  (e2: 1a4w/1aaq/1ajx/184l/10gs; v4: 13 pids restantes), consistente con los
  `file_stem` presentes en el dataset (0 excepciones).

### Irrecuperable (honesto, `unknown` con justificación)

1. **seed de flexible_redock y ruta_a**: Vina se invocó SIN `--seed`
   (semilla interna no controlada). El `SEED=42` de `ruta_a_exh_validation.py`
   era solo selección de cohorte, no del dock. Recuperar esto exigiría
   re-dockear — prohibido y además no reproducible.
2. **created_at de todo el histórico**: ninguna corrida registró un instante
   determinista (los mtimes de archivos no son fuente verificable y romperían
   el determinismo byte-idéntico). Los manifests FND-01 existen solo a partir
   de FND-01/02/05.

### Caveat documentado (no es unknown, pero debe saberse)

- **10gs (molflex) es mezcla e2+v4**: el workdir `scripts/.work_molflex_v3`
  se reusó entre olas; v4 reescribió `conf0-18` y `conf19-28` quedaron
  "stale" de e2 (evidencia: stems del dataset = 29; timestamps artifacts v3
  01:21 < build dataset 14:57 del 2026-08-14). Los parámetros de motor son
  idénticos entre olas (seed/exh/modes/box/prep), así que el contrato se
  cumple; `n_conf` y `run` se atribuyen a e2 (29, consistente con los stems).
  Regla a futuro: el workdir debe limpiarse entre corridas o versionarse.
  Registrado en `backfill_report.json:caveats`.

## 5. Wiring de generadores (poses NUEVAS) — cierre 2026-08-15

Los TRES generadores quedan completos (3/3): emisión de provenance.json
canónico + semilla de docking preregistrada `--seed 42` en todas las
invocaciones de Vina.

### 5.1 COMPLETO — `scripts/molflex.py` (semillas separadas + contrato completo)

- **Semillas separadas**: `SEMILLA_ETKDG=42` es la semilla de CONFORMEROS
  (ETKDG, docs/40) y `SEMILLA_VINA=42` es la semilla de DOCKING. Preregistro
  documentado en el docstring del módulo: "seed_docking=42 preregistrado
  2026-08-15 para todas las corridas futuras de Vina". TODAS las
  invocaciones de Vina del módulo (dock rígido write_maps/maps/fresh,
  `--local_only` + fallbacks, `--score_only` + fallbacks, re-score OpenMM)
  pasan `--seed SEMILLA_VINA` explícito. Cambio de comportamiento CERO en
  poses históricas ya dockeadas (solo corridas futuras).
- **provenance.json canónico** (un registro por conformero, clave
  `pid|molflex|conf{cid}.out`): `key`, `pid`, `source`, `file_stem`,
  `seed_conformer`, `seed_docking`, `conformer_id` real (`conf{cid}`),
  `exhaustiveness`, `num_modes`, `box {center,size,method}`, `preparation
  {ligand,receptor}`, `engine {name,version}`, `experiment_id` (CLI
  `--experiment-id`, default "molflex"; las corridas futuras deben pasarlo
  explícito) y `created_at` ISO 8601.

### 5.2 COMPLETO — `scripts/build_pose_selector_dataset.py` + `scripts/provenance_builder.py`

El builder consume los provenance.json de los generadores al ingerir poses
futuras. `provenance_builder.py` (stdlib): localiza el provenance.json de
cada trabajo (dict o lista de dicts), valida la coherencia de clave ANTES de
emitir (clave exacta `pid|source|file_stem`, identidad del trabajo y esquema
del contrato) y emite el sidecar canónico `poses_provenance.jsonl` (1
registro por corrida, claves ordenadas, escritura atómica). Claves
duplicadas, incoherentes o registros inválidos (incluidos provenance.json
legacy pre-cierre) se reportan con detalle y NO se emiten. El dataset
histórico sellado (`data/pose_selector_dataset/`) es solo lectura: el
builder escribe el sidecar únicamente con `--sidecar-out` (junto a un
dataset futuro); sin el flag solo reporta el resumen.

### 5.3 COMPLETO — `rescoring/scripts/redock_pdbbind.py` y `scripts/ruta_a_exh_validation.py`

Ambos emiten `provenance.json` canónico (mismos campos del contrato;
`conformer_id="crystal"` y `seed_conformer="crystal"` — input cristalográfico
determinista, sin generación estocástica de conformeros) y pasan `--seed 42`
explícito a Vina (preregistro). redock_pdbbind sondea la versión del binario
(caché por proceso); ruta_a reutiliza `mf.version_vina()`. La emisión es
post-dock y nunca tumba el dock. 3/3 generadores completos; cero SPEC
restantes de wiring.

## 6. Implementación

- `scripts/pose_provenance.py` (stdlib): contrato, `construir_registro`,
  `validar_registro`, `validar_lote`, CLI `--check` / `--report`
  (`--provenance sidecar|inline`, `--strict-unknown`, `--out-dir`).
  Endurecido (cierre 2026-08-15): claves duplicadas del sidecar → ERROR,
  coherencia de clave `pid|source|file_stem`, `created_at` validado con
  `datetime.fromisoformat`.
- `scripts/backfill_pose_provenance.py` (stdlib): sidecar de las 4300 poses
  históricas; verificación opcional contra RDKit; `backfill_report.json`.
- `scripts/provenance_builder.py` (stdlib): consumo de provenance.json de los
  generadores + emisión del sidecar canónico (cierre 2026-08-15).
- `scripts/test_pose_provenance.py` (stdlib): 8 pruebas del contrato
  (`python scripts/test_pose_provenance.py` → OK).
- Generadores cableados: `scripts/molflex.py`,
  `rescoring/scripts/redock_pdbbind.py`, `scripts/ruta_a_exh_validation.py`
  (provenance canónico + `--seed 42` preregistrado).
- Artefactos: `metrics.json`, `failures.jsonl`, `per_complex.jsonl`,
  `coverage_report.txt`, `poses_provenance.jsonl`, `backfill_report.json`.

## 7. Gate y determinismo

Gate FND-06: contrato implementado; cobertura histórica documentada por
campo/fuente; poses futuras 100% trazables. La garantía FUTURA quedó
implementada en el cierre 2026-08-15 (semillas separadas, preregistro
`--seed=42` de Vina en los 3 generadores, provenance canónico completo,
builder que consume y valida coherencia antes de emitir, validador
endurecido con tests dedicados). El backfill histórico no cambia.

Determinismo verificado: backfill y auditoría producen salida byte-idéntica
en 2 corridas (SHA-256 iguales para `poses_provenance.jsonl`,
`backfill_report.json`, `metrics.json`, `failures.jsonl`,
`per_complex.jsonl`, `coverage_report.txt`). Sin marcas de tiempo en los
artefactos; orden canónico de claves y campos.
