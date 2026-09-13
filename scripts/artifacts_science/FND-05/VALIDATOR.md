# VALIDATOR.md — Validación independiente de D-RC-CONFIRM (FND-05, iteración 3)

**Validador:** agente independiente (no participó en el diseño ni en la
regeneración). **Fecha:** 2026-08-15. **Rama:** `experimentos/ruta-c-molflex`,
HEAD = `4aa166a28bc87a6ec4c0be684dbfeec35d52aa25`; commit de artefactos
(`manifest.git_state.commit`) = `632bcbcf8fb67270190528f1879237814599747a`.

**Cohorte validada:** `candidates.jsonl` con SHA-256
`C12FB947A3B4068F164595D193147ECA9E4EB31C67B85142733E8CBBA7A26959`
(112 complejos).

**Método:** todos los bloqueadores B1–B8 fueron recomprobados sobre la cohorte
actual con parsers y algoritmos propios del validador (SEQRES por cadena con
fallback CA, k-meros k=8 con coeficiente de solapamiento, union-find con cierre
transitivo, método del resto mayor, ECFP4 de conteo con Tanimoto-count propio,
parser HETATM cols 76:78, parser de atom-block SDF/MOL2, reglas de estrato y QC
propios). RDKit 2025.09.6 / numpy 2.4.4 / meeko 0.7.1 se usaron SOLO como
librerías de química. Python 3.14.3 verificado. Las corridas de determinismo se
ejecutaron en directorios temporales; el único archivo creado es este reporte.

---

## Veredicto por bloqueador

| Bloqueador | Veredicto | Números medidos por el validador |
|---|---|---|
| B1 — receptor por cadena | **PASS** (1 discrepancia de métrica, no bloqueante) | 0 pares intra-cohorte ≥ 0.90; 112 componentes de tamaño 1; 0 violaciones vs desarrollo (máx 0.8993); denominadores reales 1314/2088/1073 (ver discrepancia 1) |
| B2 — cuotas | **PASS** | resto mayor 31/36/4/15/26 = declaradas; efectivas drug-like 31/27/3/15/26 (=102) |
| B5 — unicidad química y ECFP | **PASS** | 112 ik14 y 112 unidades primarias únicas; hashes 112/112 coinciden; ECFP máx 0.7385; 0 ≥ 0.90; 0 en 0.80–0.89 |
| B6 — metales | **PASS** | 17 pocket (Zn 8, Ca 6, Mn 3, Fe 2, Co 1, Ni 1); near 5, remote 90; 0 discrepancias |
| B7 — dominio, QC, covalencia, meeko | **PASS** | 102 drug-like + 10 secundarios (fragment 1, peptide 6, oligo 1, xl 2); 64/48; 59/42/6/5; 1t7d 1.513 Å excluido; meeko 112/112 |
| B8 — provenance | **PASS** | manifest = 632bcbc; diff 632bcbc..HEAD solo manifest.git_state + VALIDATOR.md; deps exactas; validate OK |
| Determinismo | **PASS** | 2 corridas (51.5 s / 44.7 s) byte-idénticas entre sí y con lo commiteado; SHA-256 C12FB947…26959 |

### B1 — Receptor por cadena — **PASS**

Parser propio SEQRES por cadena (fallback CA de ATOM) sobre los 112
candidatos:

- **Intra-cohorte:** 0 pares de complejos con cadenas ≥ 0.90 (k=8, coeficiente
  de solapamiento `|A∩B|/min(|A|,|B|)`). Union-find propio con cierre
  transitivo: **112 componentes, todas de tamaño 1** (cap de 3 cumplido en su
  forma más fuerte).
- **Contra desarrollo:** 0 violaciones en los 112 candidatos; máximo observado
  **0.8993** (4pmm:A). Controles reproducidos con mi parser: `2x00`↔`3c84:A` =
  **1.0**, `1xr9`↔`5VUF.pdb:B` = **1.0**, `3t70`↔`3t60:C` = **0.9493**. Los
  tres están excluidos en failures.jsonl con los criterios declarados
  (receptor_cadena_identica ×2, receptor_cadena_homologa_90 ×1). ✓
- **Clustering de los 440 elegibles:** mi union-find reproduce **256
  componentes** con tamaños `[21, 15, 13, 10, 10, …]`, IDÉNTICOS a los
  declarados en metrics.json, y la partición por pids coincide componente por
  componente con la declarada.
- **Serie de regresión:** `3g2z/3g30/3g31/3g34/3g35/4de0` fuera de la cohorte
  (los 6); `4de1` permanece con similitud máxima **0.0000** contra el resto;
  `3gr2` 0.0000; `4n07` 0.4382 (sin par ≥ 0.90). ✓

### B2 — Cuotas — **PASS**

Mi reimplementación del método del resto mayor (floor, piso 1 solo bins no
vacíos con cuota 0, remanente por fracción descendente con desempate por
nombre) sobre el inventario drug-like (**256**; celdas 70/83/8/35/60):

| Celda | Disponibles | Mi cuota | Declarada |
|---|---|---|---|
| rot_0_4\|res_2_2p5 | 70 | 31 | 31 |
| rot_0_4\|res_lt2 | 83 | 36 | 36 |
| rot_5_9\|res_2_2p5 | 35 | 15 | 15 |
| rot_5_9\|res_lt2 | 60 | 26 | 26 |
| rot_10_14\|res_lt2 | 8 | 4 | 4 |

Coincidencia exacta (+0/−0). Composición efectiva: **drug-like 31/27/3/15/26
(=102)**; los 10 secundarios ocupan rot_0_4|res_lt2 ×1, rot_5_9|res_lt2 ×1,
rot_10_14|res_lt2 ×3, rot_15_plus ×5. Cohort total por celda 31/28/6/2/3/15/27
(=112). ✓

### B5 — Unicidad química y ECFP — **PASS**

- Recomputé scaffold_id (SHA-256[:12] de la clase), InChIKey14 y primary_unit
  (SHA-256[:12] de `clase|ik14`) desde los ligandos en disco: **112/112
  coinciden** con lo declarado; **112 ik14 distintos** y **112 unidades
  primarias distintas**.
- ECFP4 de conteo propio (Morgan r=2, useCounts) contra el índice dev propio:
  **1197 ligandos parseables**, deduplicados por ik14 → **1061 fingerprints**
  (2 pids dev con ik14 vacío — 1f5l, 3qgy — descartados por falsy, igual que el
  pipeline). **Máximo Tanimoto = 0.7385** (2qd7); **0 candidatos ≥ 0.90**; **0
  en la banda 0.80–0.89** (chem_flag = 0 en cohorte). ✓

### B6 — Metales del pocket — **PASS**

Parser HETATM propio (elemento cols 76:78, coordenadas 30:38/38:46/46:54) y
parser propio del atom-block del ligando (SDF, fallback MOL2), distancia mínima
metal–átomo pesado del ligando, clases ≤4 Å pocket / 4–8 near / >8 remote:

- **17 complejos** con metal pocket (declarado 17). Símbolos: **Zn 8, Ca 6,
  Mn 3, Fe 2, Co 1, Ni 1** (idéntico a lo declarado; 21 metales en 17
  complejos).
- Flags: **near 5, remote 90** — coincidentes.
- **0 discrepancias** en `metal_detail` (símbolo, distancia a 3 decimales y
  clase), `metal_near` y `metal_remote` sobre los 112. ✓

### B7 — Dominio químico y QC — **PASS**

- Estratos recomputados con las reglas del diseño (fragment > peptide > lipid >
  oligo > xl > druglike): **druglike 102, fragment 1, peptide 6, oligo 1,
  xl 2** (lipid 0); `gate_primary` 102 true / 10 false. **0 discrepancias** de
  estrato y de rotables sobre los 112.
- Distribuciones: resolución **64/48** (lt2 / 2–2.5); rotables **59/42/6/5**
  (0–4 / 5–9 / 10–14 / ≥15). Coinciden con metrics.json.
- QC: **0 altloc**, **1 occupancy < 1** (flag, no excluye), **0 covalent** en
  la cohorte; mis `dist_min_prot_lig` son idénticas a las declaradas en los
  112 (0 discrepancias).
- Covalencia: `1t7d` excluido con `covalent_suspect` (failures, etapa 5); mi
  cómputo da distancia mínima ligando–proteína **1.513 Å < 1.8 Å** ✓; no está
  en pool ni cohorte.
- Meeko ejecutado por mí sobre los 112: **112/112 meeko_ok** con el mismo
  n_setups declarado; pool 440/440 meeko_ok. ✓

### B8 — Provenance — **PASS**

- `manifest.git_state.commit` = **632bcbc** (snapshot científico); `git diff
  632bcbc..HEAD -- scripts/artifacts_science/FND-05/` toca SOLO
  `manifest.json` (únicamente `git_state`: commit eb7e376→632bcbc, dirty
  true→false) y `VALIDATOR.md` (provenance/validación). ✓
- `dependencies` = rdkit==2025.09.6, numpy==2.4.4, meeko==0.7.1,
  python_version 3.14.3: **coinciden con lo instalado**. ✓
- `python scripts/experiment_manifest.py validate FND-05` → **Validation OK**. ✓
- Nota operativa: durante esta validación aparecieron ediciones SIN commitear
  de una "iteración 4" documental (guard de cuarentena: `denylist_pids.json`
  con los 112 pids de la cohorte, `confirm_denylist.py` y cambios a
  `build_confirm_cohort.py`/DESIGN.md/README.md). No forman parte del snapshot
  632bcbc ni modifican los artefactos commiteados; una reconstrucción FUTURA
  con ese código excluye los 112 pids por diseño y produciría una cohorte
  nueva. El sello de FND-05 cubre la cohorte C12FB947…26959 tal como está
  commiteada.

---

## Discrepancias entre lo declarado y lo medido

| Declarado (DESIGN/metrics) | Medido por el validador | Impacto |
|---|---|---|
| `dev_receptores_complejos` = 1425, `dev_cadenas_totales` = 2346 | **1314** unidades / **2088** cadenas reales | Métrica de reporte inflada; sin efecto en exclusiones ni en la cohorte (ver abajo) |
| `dev_cadenas_unicas` = 1073 | 1073 ✓ | Sin discrepancia |

**Causa raíz de la discrepancia 1 (verificada):** `expandir_archivos_pdb()`
concatena `rglob("*.pdb")` y `rglob("*.PDB")`; en Windows (filesystem
case-insensitive) ambos globs devuelven los mismos **111 archivos** de
`data/targets/`, así que cada uno se cuenta **dos veces** (1190 pids dev +
111×2 targets + 13 sueltos = 1425; el conteo honesto es 1190 + 111 + 13 =
1314). El índice de comparación deduplica por secuencia (`dev_cadenas_unicas`
= 1073 coincide), por lo que **la garantía de exclusión B1 no se ve afectada**:
0 violaciones con mi parser sobre el denominador honesto. Recomendación para la
próxima regeneración: deduplicar los paths en `expandir_archivos_pdb()` (p. ej.
`dict.fromkeys`) o contar el denominador sobre el índice deduplicado.

Ninguna otra discrepancia: cuotas, hashes de estructura, ECFP, metales,
estratos, QC, covalencia, meeko, conteos por etapa (2908→1176→646→645→1→440→
112; failures 1292 = 646+645+1 con criterios scaffold 640 / ik14 192 / ecfp
173 / identica 650 / homologa 279 / covalent 1), cohorte ⊆ pool, ranks 1..112 y
los 112 pids fuera de las 8 categorías de desarrollo (unión 1571) fueron
reproducidos con código propio.

## Determinismo — **PASS**

2 corridas completas con los argumentos del diseño (semilla 42, sin red, sin
re-docking) en directorios temporales, usando el código del commit 632bcbc:
**51.5 s** y **44.7 s**. Las 5 salidas (candidates.jsonl, metrics.json,
pool_eligible.jsonl, failures.jsonl, per_complex.jsonl) son **byte-idénticas
entre corridas y con los archivos commiteados**. SHA-256 de candidates.jsonl =
`C12FB947A3B4068F164595D193147ECA9E4EB31C67B85142733E8CBBA7A26959` (coincide
con DESIGN §19 y con el archivo commiteado).

## Veredicto global

**APROBADO PARA SELLAR — el sello de FND-05 cubre EXCLUSIVAMENTE la
composición de la cohorte (pids, exclusiones, estratos, hashes de estructura);
la evaluación se congela aparte en RS-CONFIRM-01.**

Resumen: B1–B8 y determinismo verificados con análisis independiente sobre la
cohorte actual (112): 0 pares de cadenas ≥ 0.90 intra-cohorte (112 componentes
de tamaño 1), 0 violaciones de receptor y 0 violaciones químicas contra
desarrollo (ECFP máx 0.7385), 112 unidades primarias únicas, cuotas 31/36/4/
15/26 declaradas y 31/27/3/15/26 efectivas drug-like, 102 drug-like + 10
secundarios, 17 pocket-metal, covalencia y meeko OK, provenance y validate OK,
determinismo byte-idéntico. La única discrepancia es una métrica de reporte
(denominador de receptores dev inflado por 111 duplicados de `data/targets/` en
Windows) que NO afecta exclusiones ni composición; se documenta para corregir
en la próxima regeneración. Los trabajos futuros ya declarados (family-disjoint
CATH/Pfam/ECOD, alineación de caja Vina a 20 Å, RMSD simétrica MF-11) quedan
fuera del alcance de esta cohorte y no bloquean el sellado según el diseño
declarado.

## Addendum final (post-commit, iteración 4)

La validación anterior se emitió con HEAD `4aa166a` y manifest apuntando a
`632bcbc`, mientras la IT4 estaba sin commitear. Estado final consolidado:

- IT4 commiteada: **475ffbe** (9 archivos: DESIGN.md actualizado, cuarentena
  materializada — `denylist_pids.json` + `scripts/confirm_denylist.py` —, guard
  `--respect-denylist` opt-in, fix de `expandir_archivos_pdb()`, metrics con el
  denominador honesto, docs/49 §4 y §9) y **4c6cc9d** (manifest provenance →
  475ffbe). Posteriormente: **6d81d40** (fix de alcance de sello + tool
  `--assets`), **1626291** (manifest provenance → 6d81d40), **f93cc3e**
  (provenance corregida en DESIGN/VALIDATOR) y **9b6d30a** (manifest provenance
  → f93cc3e). HEAD actual: `9b6d30a` (o el commit de este documento, si
  posterior — convención: el manifest apunta al commit de CONTENIDO anterior al
  commit que lo actualiza).
- `manifest.git_state.commit` = **f93cc3e**, `dirty=false`; `validate FND-05` →
  OK (reverificado).
- **Discrepancia del denominador RESUELTA en 475ffbe**: `expandir_archivos_pdb()`
  ahora deduplica paths (Windows case-insensitive contaba `*.pdb` + `*.PDB`
  dos veces). Denominadores honestos: `dev_receptores_complejos` = **1314**,
  `dev_cadenas_totales` = **2088**, `dev_cadenas_unicas` = **1073**. La cohorte
  es **byte-idéntica** tras el fix (hash `C12FB947…A26959` re-verificado por
  re-ejecución determinista del builder corregido): las exclusiones no cambian.
- Única diferencia en `failures.jsonl`: el par `3zv7` reporta `chain_b`
  `1gpk_protein.pdb:A` en vez de `1e66.pdb:A` (ambas cadenas dev idénticas,
  sim=1.0; el orden del set cambió el label). Exclusión idéntica.
- El guard de denylist quedó **opt-in** (`--respect-denylist`): la denylist
  deriva de la salida del builder; un guard por defecto rompería la
  autorreproducibilidad (re-selecciona otra cohorte). Verificado: sin el flag,
  el builder reproduce `C12FB947…`; con el flag, excluye los 112 del pool.
- Los veredictos B1–B8 y el determinismo de este documento siguen vigentes: la
  cohorte no se regeneró en IT4 y el código que afecta exclusiones no cambió
  (solo dedupe de paths de entrada, que deja las exclusiones intactas).

**Veredicto global (confirmado post-IT4): APROBADO PARA SELLAR — el sello de
FND-05 cubre EXCLUSIVAMENTE la composición de la cohorte (pids, exclusiones,
estratos, hashes de estructura y cuarentena); la evaluación se congela aparte
en RS-CONFIRM-01.**
