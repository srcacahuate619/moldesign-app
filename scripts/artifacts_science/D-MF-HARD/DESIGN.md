# D-MF-HARD — Cohorte MolFlex difícil + controles fáciles (entregable 6)

**Fecha:** 2026-08-15
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §4, entregable 6
(Campaña 1, D-MF-HARD).

## 1. Desglose de la definición ambigua de docs/49

La línea de `docs/49` dice:

> "Ligandos con `rotatable_bonds >=15`, timeouts o baja cobertura del
> generador flexible. Debe incluir controles fáciles para medir regresiones
> y no sólo casos seleccionados por fracaso."

Esa frase mezcla TRES criterios de naturaleza distinta (un umbral químico,
un evento de cómputo histórico y un déficit de poses) con un "o" que no
distingue qué decide membresía y qué es indicador. Este entregable la
desglosa así, con autorización del maintainer:

| Concepto | Definición operativa en D-MF-HARD | Naturaleza | Decide |
|---|---|---|---|
| **Estrato primario (hard)** | `rot_bonds >= 15` (MF-01/per_complex.jsonl) | criterio químico, pre-registrado | membresía hard |
| **Controles fáciles** | `rot_bonds <= 4`, emparejados sin reemplazo dentro de cada split por tamaño de ligando (receptor como desempate) | criterio químico + matching determinista | membresía control y pairing |
| **`low_yield`** | `n_poses_total <= 5` sobre la unión MF-01-UNION | indicador TÉCNICO de pocas poses válidas | nada (flag documentado) |
| **`oracle_gap`** | min-RMSD > 2.0 Å computado de `union_labels_*.jsonl` | indicador dependiente de ETIQUETA, exclusivamente secundario | NADA (membresía, matching y parámetros quedan prohibidos) |
| **`historical_timeout`** | pid presente en los registros originales hasheados (V1 = "10 de los 74 fallidos" de Fase B, todos `vina_timeout_300s`) | hecho histórico con cadena de evidencia sellada | nada (flag documentado) |

Regla dura adicional (contrato, §5): **PROHIBIDO inferir timeout porque
`n_poses == 0`**. Sin registro original de timeout, no se marca timeout.
En esta cohorte ningún timeout se infirió de conteos de poses.

## 2. Universo y separación de splits

- Universo: **156 complejos train+val** (116 train / 40 val) de
  `scripts/artifacts_science/MF-01/per_complex.jsonl`. CERO test histórico
  y CERO denylist (FND-05, 112 pids): verificación dura en el builder.
- El builder nunca abre archivos de test; la pertenencia al universo se
  verifica por construcción y con una **biyección pids(unión) ==
  pids(universo)** contra MF-01-UNION: un pid ajeno (p. ej. de test
  histórico) no tiene poses en la unión y hace fallar el build.
- Estratos verificados contra el per_complex de MF-01:
  - hard: 22 = **17 train + 5 val**;
  - controles: 22 = **17 train + 5 val**.
- **Separación 17+17 / 5+5**: los 17+17 de train son el material de
  desarrollo. Los **5+5 de val se abren UNA sola vez tras fijar la
  política** (ver §5): ninguna decisión de esta construcción se tomó
  mirando val, y los umbrales/matching quedaron fijados en el contrato
  antes de ejecutar.

## 3. Matching determinista (controles)

- Criterio: minimizar la diferencia de tamaño del ligando — clave
  lexicográfica `(|Δn_heavy|, |ΔMW|, |Δn_residuos|, pid)`; ligando primero,
  receptor (n residuos del `protein.pdb`) como desempate, pid ascendente
  como último desempate.
- Algoritmo: greedy ESTABLE sin reemplazo dentro de cada split. Los hard
  se procesan en orden (n_heavy desc, MW desc, pid asc); cada hard toma,
  entre los controles libres de su split, el de menor clave.
- Tamaños: n_heavy y MW del **SDF cristalográfico**
  (`data/pdbbind/{pid}/{pid}_ligand.sdf`); receptor = n residuos (ATOM, por
  cadena+resSeq+iCode) del `protein.pdb`.
- Identidades deterministas: `H-01..H-22` (hard por pid ascendente),
  `C-01..C-22` (control del par), `P-01..P-22` (par hard+control).
- Calidad lograda (en `metrics.json`): train |Δn_heavy| media 12.94, rango
  [8, 17]; val media 2.6, rango [0, 5]. La asimetría es inherente:
  `rot_bonds >= 15` selecciona ligandos grandes; el pool `<= 4` es
  mayoritariamente pequeño. El matching es el mejor posible bajo el
  criterio contratado, no un emparejamiento químico "perfecto".

## 4. Qué se reporta (y qué NO decide)

- `low_yield` (TÉCNICO): 5 complejos (`1b4z`, `1fd0`, `1flr`, `1n0s`,
  `1nvq`) con `n_poses_total <= 5` en la unión. Informa dónde el pipeline
  tiene pocas poses; no reasigna estrato.
- `oracle_gap` (SECUNDARIO, dependiente de etiqueta): 13 complejos con
  min-RMSD > 2.0 Å sobre `union_labels_*.jsonl`. **No decide membresía,
  matching ni parámetros**: el campo se reporta como flag con su rol
  explícito en cada registro.
- `historical_timeout`: 1 complejo (`1aaq`) con registro original:
  `scripts/artifacts_molflex_v1.json` (experimento V1, "10 de los 74
  fallidos" del redock Fase B, todos `vina_timeout_300s`) + auditoría
  `docs/40_MOLFLEX_PROTOCOL.md`. Los RMSD antiguos invalidados de docs/40
  NO se usan en ninguna parte de este entregable.

## 5. Por qué val (5 difíciles) es SOLO verificación piloto

5 complejos hard en val no admiten inferencia estadística fuerte: con
n=5, un test pareado carece de potencia para decidir regresiones de
MolFlex (y menos contra 17 controles de desarrollo). El rol de los 5+5 de
val es ÚNICAMENTE pilotaje descriptivo: confirmar que el artefacto se
abre, que el matching val no colapsa y que los registros son utilizables.
Cualquier conclusión de MolFlex exige los 17+17 de train (y, a futuro,
más val si el maintainer lo autoriza). Por eso la política se fijó ANTES
de tocar val: val nunca informó umbrales ni matching.

## 6. Estado: GO operacional, SIN resultado científico

Esta construcción puede sellarse **GO OPERACIONAL**: la cohorte existe,
es trazable, determinista byte a byte y respeta el universo/denylist/test.
**Todavía NO existe resultado científico**: D-MF-HARD es un artefacto de
medición, no un hallazgo. El gate científico de MolFlex sigue separado
(RS-01 y los entregables de medición posteriores).

## 7. Verificación

- 2 corridas del builder → SHA-256 byte-idénticos de `cohort.jsonl`
  (`6D3F3A09…`) y `metrics.json` (`F40B81FD…`).
- Tests sintéticos (builder real, entradas envenenadas): pid del denylist
  inyectado → exit 1 sin salidas; pid fuera del universo 156 (`1lhu`,
  test histórico) inyectado → exit 1 sin salidas (lo atrapa la biyección
  con la unión, sin leer ningún archivo de test).
- `validate D-MF-HARD`, `validate MF-01-UNION` y `validate FND-05` OK:
  nada sellado se tocó.

## 8. Archivos

| Archivo | Contenido |
|---|---|
| `cohort.jsonl` | 44 registros (H-01..H-22 + C-01..C-22) ordenados por `cohort_id` |
| `metrics.json` | conteos por estrato/split, calidad del matching, coberturas, timeouts, low_yield, oracle_gap (secundario), hashes de entrada |
| `failures.jsonl` | anomalías no fatales (vacío: 0) |
| `manifest.json` | registro FND-01 (init/validate; sin seal ni finish) |

Builder: `scripts/build_dmfhard_cohort.py` (stdlib, docstring en español).
