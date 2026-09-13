# MF-01-UNION — Unión materializada de poses existentes (entregable 4)

**Fecha:** 2026-08-15
**Rama:** `experimentos/ruta-c-molflex`
**Referencia:** `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` §15, entregable 4
(Campaña 1, MF-01).

> "Unión de poses existentes sin re-docking" — materializar la unión de las
> poses de Ruta C sobre train/val, trazable y sin deduplicar.

## 1. Alcance

- **Splits separados** (train y val): 2739 poses train + 730 val = **3469**,
  **156 complejos** (116 train / 40 val).
- **447 corridas de provenance** usadas (subconjunto train+val del sidecar
  sellado FND-06, que tiene 560 corridas totales: las 113 restantes son
  solo-test y quedan fuera por alcance, docs/49 §4).
- **Identidad canónica**: `split|pid|source|file_stem|model_idx`.
- **NO se lee `poses_test.jsonl`** — el builder
  (`scripts/build_pose_union.py`) SOLO abre `poses_train.jsonl` y
  `poses_val.jsonl`. Verificado operacionalmente con un test sintético
  (test envenenado con JSON inválido: el build termina OK, prueba de que
  el archivo nunca se abre).
- **NO re-docking, NO scoring v0.6, NO deduplicación/clustering** (MF-11,
  entregable 9, posterior a RS-01).
- **Determinismo**: 2 corridas → SHA-256 byte-idénticos de las 6 salidas
  (4 JSONL + failures + metrics).

## 2. Formato de identidad

`identity = split|pid|source|file_stem|model_idx`, idéntica a la clave
natural de una pose en el dataset sellado más su split. La `provenance_key`
(= `pid|source|file_stem`, la clave del sidecar FND-06) enlaza cada
candidato con su corrida de provenance sin duplicar los 10 campos del
contrato FND-06 dentro del candidato.

Validaciones DURAS (exit 1, nada parcial, verificado en tests sintéticos):

1. **Colisión de identidad** → FAIL del build.
2. **Pose sin provenance** (clave ausente en el sidecar) → FAIL del build.
3. Geometría faltante NO es fatal: la pose válida se registra con
   `geometry_source="missing"` en `failures.jsonl` y el build continúa.

## 3. Separación candidatos / labels — y POR QUÉ

`union_candidates_{split}.jsonl` NO contiene `rmsd` ni ningún label de
calidad. `union_labels_{split}.jsonl` lleva `identity`, `rmsd` y los campos
de calidad históricos (`n_heavy`, `n_contacts_4`, `n_contacts_6`,
`n_clashes`, `pose_score_variance`, `pose_score_range`), keyed por identidad
y en el MISMO orden por identidad ascendente.

**Motivo:** el entregable 5/RS-01 va a puntuar esta unión; el criterio de
inclusión, el orden y la selección de candidatos deben depender SOLO de la
identidad, nunca del rmsd. Si el rmsd viajara dentro del candidato, un
proceso posterior (o una lectura humana) podría condicionar la selección
por la etiqueta — contaminación de etiqueta a nivel de artefacto. La
separación física la hace estructuralmente imposible sin romper el join
por identidad.

Campos no incluidos en labels, a propósito: `contacts_per_ha_4` (derivada
de `n_contacts_4`/`n_heavy`, ya presentes) y `cluster_density` (feature de
clustering, competencia de MF-11, fuera del alcance de este entregable).

## 4. Descubrimiento de geometrías y cobertura honesta

Investigación por fuente de las 3469 poses train+val (0 colisiones, 0 sin
provenance):

| Fuente | Poses | Corridas | Fuente del PDBQT real | pdbqt | `_coords` | missing |
|---|---|---|---|---|---|---|
| flexible_redock | 1169 | 143 | `data/pdbbind/vina_redock_work/{pid}/{pid}_out.pdbqt` | 1169 | 0 | 0 |
| molflex | 1934 | 244 | `work_molflex_v3/{pid}/conf{cid}.out.pdbqt` (reubicado) | 1934 | 0 | 0 |
| ruta_a | 366 | 60 | `tmp/ruta_a/{pid}/exh{N}/out.pdbqt` | 366 | 0 | 0 |
| **total** | **3469** | **447** | | **3469** | **0** | **0** |

- **Cobertura PDBQT real: 3469/3469 (100%).** Cada pose se materializa con
  su bloque `MODEL..ENDMDL` verbatim (incluido `REMARK VINA RESULT`), cuyo
  score coincide 1:1 con el `vina_score` del dataset (verificado en todas
  las poses).
- `scripts/.work_molflex_v3/` ya no está en el repo (movido durante la
  reorganización a `C:\Users\JOHANA~1\AppData\Local\Temp\opencode\`
  `moldesign-backups\work_molflex_v3`). El builder lo resuelve vía
  `--geometry-root` apuntando a `moldesign-backups` y NO copia nada al
  repo. Los candidatos materializan el PDBQT, así que la unión queda
  autocontenida (independiente del backup).
- Los bloques MODEL de los 447 archivos suman exactamente 3469 y el índice
  de bloque coincide 1:1 con `model_idx` del dataset (misma convención que
  `mf.parsear_out_vina`); 0 bloques vacíos, 0 desalineaciones.
- `records/{pid}.json` (`_coords`) quedó como fallback honesto
  (`geometry_source="_coords"`) y se probó en test sintético; en el build
  real no hizo falta: 0 poses por `_coords`, 0 por `missing`.

## 5. Salidas

| Archivo | Contenido |
|---|---|
| `union_candidates_train.jsonl` (2739) | `identity`, `split`, `pid`, `source`, `file_stem`, `model_idx`, `vina_score`, `provenance_key`, `geometry_source`, `pdbqt` |
| `union_candidates_val.jsonl` (730) | ídem |
| `union_labels_train.jsonl` (2739) | `identity`, `rmsd`, 6 campos de calidad |
| `union_labels_val.jsonl` (730) | ídem |
| `failures.jsonl` | anomalías no fatales (vacío: 0) |
| `metrics.json` | conteos exactos, cobertura de geometría por fuente, provenance |

Orden: `identity` ascendente en candidatos y labels (determinista,
independiente de rmsd).

## 6. Verificación

- 2 corridas → SHA-256 idénticos (candidatos train `61AB0E26…`, val
  `21DF7637…`, labels train `19843AFD…`, val `BB9FF264…`, failures
  `E3B0C442…`, metrics `248DD104…`).
- Tests sintéticos (tempdir, con el builder real): colisión → exit 1 sin
  salidas; sin provenance → exit 1 sin salidas; test envenenado + fallback
  `_coords` → exit 0; geometría faltante → exit 0 + 1 entrada en
  `failures.jsonl`.
- `validate MF-01-UNION` OK y `validate FND-06` OK (nada sellado se tocó).

## 7. Nota de gate

**PASS OPERACIONAL del artefacto ≠ gate científico de MF-01** (que
permanece NO_GO: MolFlex aportó 0 complejos en D-MF-HARD; decisión en
RS-01). Este entregable materializa y hace trazable la unión; no decide
nada sobre ella: la deduplicación es MF-11 y el scoring v0.6 es RS-01.
