# DESIGN — RS-04-QC: control de calidad técnico del strain MMFF94s (etapa previa a RS-04)

**Fecha:** 2026-08-16
**Rama:** `experimentos/ruta-c-molflex`
**Autorización:** maintainer, tras el sello del plan CAMPANA-2-PLAN (41b7f09)
**Manifest:** `RS-04-QC` (status `created`; SIN seal, SIN finish)
**Protocolo:** CAMPANA-2-PLAN sellado (41b7f09), IT1/DECISIONS QA-5/QA-6,
§3.2 (RS-04-QC). Train-only, SIN labels, SIN entrenamiento, SIN val/test/CONFIRM.

---

## 1. Alcance y contrato

Etapa técnica previa a RS-04 sobre las **2739 poses train** de la unión
ORIGINAL (`MF-01-UNION/union_candidates_train.jsonl`, sha `61AB0E26…`, bloques
PDBQT embebidos) y los **116 ligandos sanitizados**
(`data/pdbbind/{pid}/{pid}_ligand.sdf`). Se aplicó literalmente el contrato
QA-5:

- Topología, órdenes de enlace, estereoquímica y cargas formales desde el
  **SDF sanitizado**; el PDBQT solo aporta coordenadas de pesados (nunca se
  infiere química del PDBQT).
- Mapeo heavy-atom **biyectivo y verificado** pose↔ligando (elemento +
  conectividad, isomorfismo en ambas direcciones).
- `AddHs(addCoords=True)`: los H de la pose se descartan por contrato.
- En la pose docked se optimizan **SOLO los H** (pesados fijados) con
  **MMFF94s**.
- `MMFFHasAllMoleculeParams == false` → `unsupported_mmff`; **NO se mezcla
  UFF**.
- Halógenos **NO excluidos por nombre**: se reporta la cobertura REAL.
- Strain negativo **NO se trunca**: en QC se verifica el mecanismo de
  cómputo, sin usarlo como gate.

## 2. Definiciones operativas (documentadas)

- **Ligando sanitizado:** `MolFromMolFile(sanitize=True, removeHs=False)` +
  plantilla de pesados reconstruida (átomos con Z>1, órdenes de enlace del
  mol kekulizado deterministico, cargas formales preservadas). Elimina por
  construcción cualquier H explícito anómalo (p. ej. `1a4w` retiene un H
  explícito que `RemoveHs` no elimina).
- **Mapeo biyectivo:** grafo elemento+conectividad de ambos lados; enlaces
  de la pose inferidos por distancia covalente (`d ≤ 1.25·(r_i+r_j)`);
  isomorfismo en ambas direcciones (`GetSubstructMatch` bidireccional).
- **Pseudoatomos `G`:** sitios de carga offsite de meeko
  (`meeko/atomtyper.py:_set_offatoms` escribe `PDBAtomInfo("G", …)`), NO son
  átomos de la molécula: se excluyen del mapeo y se registran como anomalía.
- **Unidad de cobertura MMFF = LIGANDO (116):** si el ligando no tiene
  parámetros, TODAS sus poses son `unsupported_mmff`. La cobertura se mide
  por ligando, no por pose (definición del plan).
- **Optimización H con pesados fijados:** `MMFFAddPositionConstraint(i, 0,
  1e6)` en todos los pesados + `OptimizeMolecule(ff, maxIters=1000)` +
  **restauración EXACTA** de las coordenadas de pesados. Resultado:
  desplazamiento pesado final **0.0 Å exacto** (verificado numéricamente).
  El drift pre-restauración del optimizador es ≤ 4.4e-4 Å (ruido del
  optimizador, no movimiento físico). `maxIters=1000` porque el default de
  RDKit (200) no convergió en 1/60 poses muy tensionadas (1b2h
  flexible_redock model 1, E 371→327 kcal/mol; converge en ≤500 iteraciones
  con energía idéntica); el optimizador corta antes al converger, sin coste
  real adicional.
- **Muestra determinista (check 2):** 60 poses = 2 poses por cada uno de los
  30 primeros complejos train de D-MF-HARD en orden de `cohort.jsonl`
  (15 pares hard/control, P-01..P-15); las 2 identidades menores mapeables
  por complejo (orden sellado por identidad ascendente).
- **Costes:** cold-start = leer SDF + sanitizar + plantilla + AddHs + setup
  MMFF + mapeo + optimización H de la primera pose mapeable (mediana de 3
  repeticiones por ligando). Cacheado por pose = parsear + mapear + mol_pose
  + AddHs + props + FF + optimización H (setup de ligando amortizado),
  medido 1 vez sobre las 2725 poses mapeables; por complejo = suma de sus
  poses. Los costes son **mediciones con varianza natural**: se congelan en
  `benchmarks.json` (corrida canónica) y la 2ª corrida los reutiliza byte a
  byte; TODO lo demás se recomputa de cero.

## 3. Blindaje y determinismo

- Guard hard de apertura: el script ABORTA si un path contiene
  `union_labels`, `poses_val`, `poses_test`, `d-rc-confirm`, `val40` o
  `rmsd`. Auditoría en `metrics.json` (`whitelist_archivos_abiertos`): 119
  paths = union train + cohort + 116 SDF + salidas propias. **Cero acceso a
  labels, val, test o CONFIRM.**
- De `cohort.jsonl` solo se leen `pid/split/stratum/cohort_id`; los campos
  dependientes de etiqueta (oracle_gap) no se usan.
- Sin timestamps; iteración en orden de archivo (identidad ascendente,
  orden sellado de MF-01-UNION); ETKDGv3 seed 42 numThreads=1; flotantes
  redondeados; JSON con claves ordenadas; saltos de línea LF.
- **Determinismo:** 2 corridas completas → sha256 byte-idénticos de las 5
  salidas (`metrics.json` `81D5B2D3…`, `per_complex.jsonl` `2793E695…`,
  `failures.jsonl` `44FF7934…`, `benchmarks.json` `E918E0C7…`,
  `run_rs04_qc.py` `45E19925…`). Verificado con `--repro` (recomputación
  total en directorio temporal + comparación) y con `Get-FileHash`
  independiente.

## 4. Resultados por check

**Check 1 — Mapeo atómico (2739 poses):**
- Biyectivo exacto: **2725/2739 (99.49%)** → gate ≥99% **PASS**.
- Discrepancias (14, 0.51%): `ligando_no_embebe` en 9 poses de `1kpm`
  (flexible_redock) y 5 de `1nm6` (flexible_redock, models 1-4 y 8):
  geometría degenerada (átomos colapsados; la conectividad no puede
  inferirse por distancias covalentes). Son poses de docking defectuosas,
  no un fallo del mapeo.
- 27 poses (1mmq/1mmr/1nm6, todas flexible_redock) contienen pseudoatomos
  `G` de meeko (2 por pose): excluidos correctamente; esas 27 poses mapean
  biyectivas.

**Check 2 — H y optimización (60 poses):**
- 60/60 con `AddHs(addCoords=True)` verificado (H añadidos, coordenadas
  finitas, MMFF params OK).
- **60/60 convergen**; desplazamiento máximo de pesados **0.0 Å** (exacto;
  pre-restauración 4.4e-4 Å); E_MMFF94s final rango [-475.5, +335.0]
  kcal/mol.

**Check 3 — Cobertura MMFF (unidad: LIGANDO):**
- **116/116 ligandos (100%)** con `MMFFHasAllMoleculeParams == true` →
  gate ≥95% **PASS**; **2739/2739 poses** soportadas.
- Lista de no soportados: **vacía**. Halógenos (Cl/Br/I) y N+ cubiertos por
  MMFF94s de RDKit 2025.09.6 (verificado: 1bju Cl, 1nm6 Cl + 2×N+, 1cet Cl,
  1e4h/1c4u Br, 10gs N+ — todos con parámetros).
- Neutros/ionizados: 79 soportados neutros, 37 ionizados (carga formal ≠ 0),
  0 sin soporte en ambos grupos.

**Check 4 — Determinismo:** PASS (2 corridas, 5/5 salidas sha256
byte-idénticas).

**Check 5 — Coste (gates del plan):**
- Cold-start: P50 6.79 ms, **P95 55.74 ms ≤ 5000 ms → PASS**.
- Cacheado por pose: P50 7.15 ms, **P95 67.95 ms ≤ 100 ms → PASS**.
- Cacheado por complejo: P50 102.29 ms, **P95 1726.37 ms ≤ 3000 ms → PASS**.
- Medidas 2725 poses (las 14 degeneradas excluidas: no tendrían strain
  computable).

**Mecanismo de strain negativo (NO gate):** la función `calcular_strain =
E_pose − E_min` no trunca (prueba de unidad: −4.0 se conserva como −4.0);
demostración end-to-end en 5 ligandos (2 poses c/u): strain rango
[+26.5, +233.9] kcal/mol, con signo, sin clamping. En esta muestra no
aparecieron negativos (poses docked por encima del mínimo aislado); si
aparecen en RS-04, el pipeline los conservará y disparará la ampliación del
search de referencia (QA-5).

## 5. Veredicto global QC

**QC PASS.** Los 5 criterios del plan: mapeo biyectivo ≥99% (99.49%),
optimización H sin mover pesados (0.0 Å, 60/60 convergen), cobertura
química ≥95% (100%), determinismo (5/5 byte-idénticos) y los 3 gates de
coste (55.7 ms / 67.9 ms / 1.73 s vs 5 s / 100 ms / 3 s). → **RS-04 OOF
completo puede proceder**, con la única advertencia operacional: 14 poses
(2 pids, flexible_redock) con geometría degenerada que RS-04 debe tratar
como no computables (fallo parametrizado, nunca energía cero).

## 6. Archivos

| Archivo | Contenido |
|---|---|
| `metrics.json` | 5 checks con números exactos, gates y veredicto |
| `per_complex.jsonl` | 116 filas: cobertura MMFF, poses, mapeo, costes |
| `failures.jsonl` | 41 anomalías no fatales (14 mapeo + 27 pseudoatomos G) |
| `benchmarks.json` | mediciones de coste congeladas (P50/P95 por nivel) |
| `run_rs04_qc.py` | runner (stdlib+RDKit, docstring español, determinista) |

Builder: `scripts/run_rs04_qc.py`, runtime `python-embed/python.exe`
(3.11.9, RDKit 2025.09.6).
