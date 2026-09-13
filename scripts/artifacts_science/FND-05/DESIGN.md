# FND-05 — Diseño de la cohorte confirmatoria D-RC-CONFIRM (ITERACIÓN 4)

**Estado:** diseño APROBADO técnicamente por el maintainer (sin sellar). La iteración 4 NO regenera la cohorte: solo correcciones documentales y operativas (provenance, contrato de denominadores, alcance del sello, RMSD simétrica, cegamiento como mecanismo y cuarentena materializada).
**Rama:** `experimentos/ruta-c-molflex`; snapshot de revalidación: `4aa166a` (el HEAD del momento de la revalidación de la iteración 3; la cadena de provenance completa está en el párrafo siguiente).
**Fecha:** 2026-08-15.

**Provenance (cadena legible para un tercero):** el SNAPSHOT científico de FND-05 (código de construcción + artefactos, cohorte de 112 en `candidates.jsonl` con SHA-256 `C12FB947A3B4068F164595D193147ECA9E4EB31C67B85142733E8CBBA7A26959`) está identificado por el commit **632bcbc**; el `manifest.json` apunta al commit **f93cc3e** (estado pre-sello: correcciones documentales de la iteración 4, cuarentena materializada, fix del doble conteo de receptores, tool de manifest extendido con `--assets` y regeneración de README, y provenance corregida) con `dirty=false`. Cadena de commits: **632bcbc** (iteración 3, snapshot de la cohorte) → **048ac41** (manifest apunta al commit final de IT3) → **4aa166a** (revalidación de IT3) → **475ffbe** (iteración 4 documental/operativa) → **4c6cc9d** (manifest apunta a 475ffbe) → **6d81d40** (fix de alcance de sello + tool `--assets`) → **1626291** (manifest apunta a 6d81d40) → **f93cc3e** (provenance corregida: manifest apunta a 6d81d40 pasó a f93cc3e) → **9b6d30a** (manifest apunta a f93cc3e). **Convención de provenance del repo:** `manifest.git_state.commit` apunta al commit de CONTENIDO; el commit que contiene únicamente la actualización del puntero del manifest es siempre el siguiente. Commits documentales posteriores a `9b6d30a` (ajustes de redacción de este documento, p. ej. la línea 4) no alteran la cohorte ni el puntero del manifest; la integridad del sello se basa en los SHA-256 de los assets congelados por `seal`, no en el puntero. Los commits posteriores a 632bcbc no cambian la cohorte: los candidatos son byte-idénticos (hash `C12FB947…` verificado por re-ejecución determinista y por validador independiente).

## 1. Objetivo e hipótesis

FND-05 (docs/49, Cartera A, P0): "El confirmatorio puede permanecer realmente
ciego". Interpretación operativa en FND-05 (sin control de acceso de máquina,
NO se afirma cegamiento real): **holdout confirmatorio con secuestro
procedimental de etiquetas** (§17). Crear D-RC-CONFIRM — holdout confirmatorio
interno independiente para el gate final de Ruta C — antes de probar el
candidato definitivo, y custodiar etiquetas/evaluación con manifest sellado
previo a puntuar.

**Hipótesis preregistrada:** existe un pool local suficiente para 100+ complejos
confirmatorios disjuntos del desarrollo por pid, por química de ligando
(scaffold, InChIKey de conectividad y ECFP de conteo) y por cadena de receptor
(identidad/homología).

**Gate:** pool ≥ 100 tras exclusiones; disyunción química + disyunción de
receptor por cadena; balance estratificado documentado; contrato de
denominadores en §9 (gate confirmatorio PRIMARIO sobre los 102 drug-like;
resultado global OBLIGATORIO/ITT sobre los 112 contando fallos técnicos como
fallos; análisis SECUNDARIO descriptivo sobre los 10 no drug-like).

Requisitos del contrato D-RC-CONFIRM (docs/49, §4) cubiertos:

- ≥ 100 complejos con pose cristalográfica (SDF del cristal) y candidatos
  reproducibles (re-docking Vina/MolFlex sobre activos locales).
- Disyunción por scaffold/InChIKey/ECFP del ligando Y por identidad/homología
  POR CADENA del receptor respecto de desarrollo.
- Balance por componentes de similitud de cadena (proxy de familia: clusters
  de cadenas de receptor), flexibilidad, tamaño, metales y año/resolución.
- Hashes, lista de PDB/ligandos y reglas de exclusión sellados antes de
  inferencia (plan en §17).
- Sin reutilización de complejos vistos en depuración manual (los 30 pids
  excluidos del manifest de pose_selector_dataset están en la lista de
  desarrollo, verificados).

## 2. Activos locales verificados

| Activo | Verificado |
|---|---|
| `data/pdbbind/` (junction) | 5325 directorios de complejos; 2908 con `{pid}_protein.pdb` + `{pid}_ligand.sdf/.mol2` para pids del índice enriquecido |
| `INDEX_faseb_enriched_full_20260813_184439.2020` | 3815 entradas con resolución/año/pKi |
| `INDEX_refined_data.2020` (actual) | 1165 entradas = Fase A (865) + 300 selección BindingDB |
| Backup `INDEX_refined_data.2020.faseA_20260813_184212` | 865 pids Fase A, fuente de la lista Fase A |
| `data/pose_selector_dataset` | 203 pids Ruta C (116 train + 40 val + 47 test), manifest con `test_pids_sha256` intacto |
| RDKit | 2025.09.6 (scaffold Murcko, InChIKey, ECFP4, descriptores) |
| numpy | 2.4.4 (distancias metal–ligando y covalencia) |
| meeko | 0.7.1 (flag de preparación por ligando) |

Notas: 907 pids del índice enriquecido no tienen `protein.pdb` en disco (fuera
del pool, sin descargas); ningún complejo elegible pertenece al índice refined;
las cabeceras de los protein.pdb son genéricas (la familia biológica se
aproxima con clusters de cadenas, §12); el 100 % de los protein.pdb tienen
SEQRES o fallback CA válido.

## 3. Definición del pool candidato (etapa 1)

**Pool** = intersección de:

1. entradas de `INDEX_faseb_enriched_full_20260813_184439.2020` (3815), y
2. complejos con `{pid}_protein.pdb` (no vacío) y `{pid}_ligand.sdf` o
   `{pid}_ligand.mol2` (no vacío) en `data/pdbbind/{pid}/`.

Resultado: **2908** complejos (907 descartados por falta de `protein.pdb`).

## 4. Pids de desarrollo excluidos por identidad (etapa 2)

Lista completa en `dev_seen_pids.json`, REGENERADA de forma reproducible con
`scripts/discover_dev_pids.py` (stdlib, docstring con las 8 reglas de
extracción). Unión deduplicada: **1571** pids, idéntica a la histórica.

| Categoría | Fuente | pids |
|---|---|---|
| `ruta_c` | `poses_{train,val,test}.jsonl` de pose_selector_dataset | 203 |
| `fase_a` | backup `INDEX_refined_data.2020.faseA_20260813_184212` | 865 |
| `fase_b_new` | `data/pdbbind/faseb_selection_manifest.json → selected_new_ids` | 300 |
| `artifacts_scripts` | `scripts/artifacts_ruta_c_*.json`, `artifacts_ruta_a.json`, `artifacts_molflex_*.json`, `.molflex_cheap_test.json` | 254* |
| `gnn_v31` | `data/gnn_v31/pids_in_dataset.txt` | 708 |
| `target_library` | `data/target_library/targets_manifest.json → pdb_ids` | 298 |
| `data_pdbs` | PDBs sueltos en `data/`, `data/targets/` (nombres de archivo) | 110 |
| `otros_artifacts_data` | JSON/JSONL de `data/{multitarget,molchamb_loto,gnn_fixed,gnn_v2_dataset,backups,box_test_7e2y}` | 9* |

\* Las categorías `artifacts_scripts` y `otros_artifacts_data` usan una regla
conservadora documentada (superconjunto de los conteos históricos 113 y 2;
la regla histórica exacta no se pudo reconstruir — limitación declarada en el
README de FND-05). La unión deduplicada no cambia: **1571 pids**.

Pids del pool excluidos en esta etapa: **1176** (2908 − 1732 restantes).

## 5. Exclusión por química del ligando (etapa 3)

Se computa para TODOS los ligandos de desarrollo parseables (**1197**) y para
cada candidato:

1. **Clase de scaffold**: Murcko (`m:<smiles>`); acíclicos con clase propia
   `acyclic:<ik14>` (corrige el bug de fallback de FND-02); **oligosacáridos
   heurísticos** (≥ 3 anillos con O en el anillo) con clase
   `oligo:<n_rings>:<n_oxygen>` — distinta longitud de oligo NO es familia
   independiente.
2. **InChIKey de conectividad** (prefijo 14): exclusión exacta.
3. **ECFP4 de conteo** (Morgan counts, radio 2): Tanimoto-count máximo contra
   TODOS los ligandos de desarrollo parseables (deduplicados por InChIKey14,
   **1061** fingerprints). `>= 0.90` → exclusión; `0.80–0.89` → flag
   `chem_flag` (no excluye).

Criterios: `scaffold_en_desarrollo` **640**, `ligando_ik14_en_desarrollo`
**192**, `ecfp_tanimoto_ge90` **173** (0 ligandos no parseables y 0 receptores
sin secuencia en el pool). Los criterios pueden solaparse; el conteo por etapa
asigna cada complejo a la PRIMERA etapa que falla. Excluidos en la etapa:
**646** (1732 − 1086). Flags `chem_flag` (ECFP 0.80–0.89): **61**.

**Unidad primaria química** = (scaffold_id, connectivity InChIKey14) =
SHA-256[:12] de `clase|ik14`. Tope de **1 candidato por unidad primaria** en
el muestreo (§13).

## 6. Exclusión por cadena de receptor (etapa 4, CRÍTICA — B1)

**Claim: `near-identity-disjoint`.** La unidad de comparación es la CADENA
individual, no el complejo. `secuencia_pdb_texto()` devuelve ahora un dict
`{cadena: secuencia}` (SEQRES por cadena, fallback CA de ATOM por cadena). La
similitud entre dos complejos es el **MÁXIMO del coeficiente de solapamiento
de k-meros (k=8) sobre todos los pares de cadenas** (cadena de A vs cadena de
B). Un candidato se excluye si CUALQUIER par de cadenas alcanza **≥ 0.90**:

- `kmer_overlap_100`: sim == 1.0 (**650** criterios). ADVERTENCIA: sim == 1.0
  del coeficiente de solapamiento NO implica secuencia idéntica — captura
  también constructos truncados (una secuencia contenida en la otra); el
  criterio se renombra para no confundir solapamiento con identidad.
- `receptor_cadena_homologa_90`: 0.90 ≤ sim < 1.0 (**279** criterios).

Receptores de desarrollo comparados: **1314 unidades** (pids locales con
protein.pdb + PDB externos de benchmark) = **2088 cadenas** totales /
**1073 cadenas únicas** (denominador ÚNICO y nombrado en metrics.json:
`dev_receptores_complejos` / `dev_cadenas_totales` / `dev_cadenas_unicas`).
Nota de corrección: la iteración 4 corrigió un doble conteo en
`expandir_archivos_pdb()` (en Windows, `rglob("*.pdb")` y `rglob("*.PDB")`
devuelven los mismos archivos); los valores inflados previos eran 1425
unidades / 2346 cadenas, y la inconsistencia original de la iteración 1
(1119 vs 1425 vs 897) queda resuelta con el denominador único actual.

Índice invertido de k-meros a nivel de cadena (deduplicado por secuencia) para
escalar sin alineamientos. `failures.jsonl` reporta el mejor par con campos
`chain_a`, `chain_b` (origen `pid:cadena` o `archivo:cadena`), `sim` y
`n_cadenas_match`.

**Casos de regresión verificados (todos excluidos):**

| Par | Sim por cadena (nueva) | Sim por concatenación (vieja) | Resultado |
|---|---|---|---|
| `2x00` ↔ `3c84` | **1.0** (A↔A) | 0.842 | excluido, `kmer_overlap_100`, chain_a=A, chain_b=3c84:A |
| `1xr9` ↔ `5VUF` | **1.0** (B↔B) | 0.861 | excluido, chain_a=B, chain_b=5VUF.pdb:B |
| `3t70` ↔ `3t60` | **0.9493** (A↔C) | 0.830 | excluido, `receptor_cadena_homologa_90` |

Los tres pids estaban EN LA COHORTE de la iteración 1 (fuga real). `5VUF` no
está en el índice enriquecido, pero su PDB existe en `data/targets/` y se
captura por la ruta de PDB externos; `2x00`/`1xr9`/`3t70` sí están indexados.
Todos capturados; ninguno pendiente de documentar.

El mismo criterio por cadena se aplica DENTRO de la cohorte: los elegibles se
agrupan en **clusters de cadena** con union-find COMPLETO de cierre transitivo
(arista si cualquier par de cadenas ≥ 0.90, INCLUIDAS las idénticas sim = 1.0)
con **tope de 3 complejos por componente conexa** y **0 pares directos ≥ 0.90**
en la cohorte (§12). Excluidos en la etapa: **645** (1086 − 441).

**Nota de trabajo futuro:** la disyunción por FAMILIA biológica
(family-disjoint) requiere anotación CATH/Pfam/ECOD, no disponible localmente.
NO se implementa en esta iteración; queda documentada como trabajo futuro
antes del sellado si el maintainer lo exige.

## 7. Covalencia (etapa 5, B7)

`covalent_suspect`: átomo PESADO del ligando a < 1.8 Å de cualquier átomo
PESADO de proteína (registros ATOM con elemento != H; los H de proteína se
excluyen porque los contactos H···ligando producían falsos positivos masivos —
196 con el criterio naif; los HETATM no-agua/metales son cofactores y no
cuentan). Si `covalent_suspect` → **excluido del gate primario** y pasado al
estrato de revisión manual (en failures.jsonl con criterio
`covalent_suspect`). Excluidos: **1** (441 − 440).

## 8. Resultado por etapa

| Etapa | Descripción | Descartados | Restantes |
|---|---|---|---|
| 1 | Pool: índice ∩ archivos completos | 907 | 2908 |
| 2 | Pids vistos en desarrollo (8 categorías) | 1176 | 1732 |
| 3 | Química: scaffold / InChIKey14 / ECFP ≥ 0.90 | 646 | 1086 |
| 4 | Receptor por cadena (identidad u homólogo ≥ 0.90) | 645 | 441 |
| 5 | Covalencia (covalent_suspect) | 1 | **440** |
| 6 | Muestreo estratificado (semilla 42) | 328 no seleccionados | **112** |

**Gate: CUMPLIDO** — 440 elegibles ≥ 100, disyunción química + por cadena
verificada por construcción, balance documentado (§13).

## 9. Dominio químico y política de estratos (B7)

Por ligando se computan: MW, `n_heavy`, `n_rings`, `n_amide` (SMARTS
`[NX3][CX3](=[OX1])`), anillos con O y estrato. Prioridad de estrato
(documentada en el código): **fragment > peptide > lipid > oligo > xl >
druglike**:

| Estrato | Regla |
|---|---|
| `fragment` | MW ≤ 150 o n_heavy ≤ 10 |
| `peptide` | ≥ 3 enlaces amida |
| `lipid` | 0 anillos (acíclico) + MW > 150 |
| `oligo` | ≥ 3 anillos con O en el anillo (misma heurística de la clase química) |
| `xl` | MW > 500 |
| `druglike` | el resto |

**El gate confirmatorio PRIMARIO se evalúa SOLO sobre el estrato drug-like**;
los demás estratos se reportan aparte y NO dominan el gate. Distribución de
los 440 elegibles: druglike **256**, fragment 45, lipid 33, oligo 6, peptide
52, xl 48. Con las cotas duras del §13 (tope 3 por componente conexa y 0 pares
directos ≥ 0.90), la heurística determinista seleccionó **102** drug-like (no
se demostró que 102 sea el máximo combinatorio); los **10** restantes se
completan con estratos no drug-like en el orden documentado
(`gate_primary=false`: fragment 1, peptide 6, oligo 1, xl 2).

**Contrato de denominadores de D-RC-CONFIRM (redacción canónica, propagada a
docs/49 §4 y §9):**

- **Gate confirmatorio PRIMARIO**: los **102 complejos drug-like**
  (`gate_primary=true`), punto estimado ≥ 0.70 + bootstrap pareado vs v0.6.
- **Resultado global OBLIGATORIO (ITT)**: los **112 complejos**, contando los
  fallos técnicos como fallos.
- **Análisis SECUNDARIO**: los **10 complejos no drug-like** (fragment 1,
  peptide 6, oligo 1, xl 2), descriptivo, sin inferencia fuerte por tamaño.

## 10. Metales del pocket (B6)

`metales_pocket(pdbbind, pid)` parsea las coordenadas de los HETATM de metales
(Zn/Fe/Mg/Mn/Ca/Co/Ni/Cu) del protein.pdb y las del ligando cristalográfico
(SDF, RDKit). Distancia mínima metal–ligando:

- `<= 4 Å` → **pocket** (metaloenzima candidata): cuenta como metal en el
  balance y el complejo lleva `metals=[...]` con el símbolo del metal.
- `4–8 Å` → **near** (flag `metal_near`).
- `> 8 Å` → **remote** (flag `metal_remote`, control negativo).

Cada metal se reporta en `metal_detail` con tipo y distancia mínima. En la
cohorte: **17** con metal pocket (Zn 8, Ca 6, Mn 3, Fe 2, Co 1, Ni 1;
objetivo proporcional 15), 5 flags near y 90 flags remote.

## 11. QC estructural (flags, no exclusiones)

- `qc_altloc`: cualquier línea ATOM/HETATM del protein.pdb con altLoc distinto
  de blanco/A.
- `qc_occupancy_lt1`: HETATM (sin aguas ni metales) con ocupancia < 1.0.
- `meeko_status` por ligando: `meeko_ok` (con `meeko_n_setups`), `meeko_fail`
  (con `meeko_error`) o `meeko_unavailable`. En esta corrida: 440/440 `meeko_ok`
  en elegibles, 112/112 en la cohorte.

Cohorte: 0 altloc, 1 con ocupancia < 1 (flag declarado, no excluye).

## 12. Clusters de cadenas de receptores elegibles (B1 intra-cohorte, IT3)

Los 440 elegibles se agrupan con **union-find completo con cierre transitivo**
(`clusters_cadenas()` en `scripts/build_confirm_cohort.py`): nodos = complejos;
arista entre A y B si existe ALGÚN par de cadenas (cadA, cadB) con solapamiento
de k-meros k=8 ≥ 0.90, INCLUIDAS las cadenas idénticas (sim = 1.0), que unen a
TODOS sus dueños entre sí. Path compression + union by rank; las componentes
conexas son los clusters de cadena. La iteración 2 deduplicaba secuencias con
"primer dueño" y perdía las aristas entre complejos con cadenas idénticas
(grafo incompleto) — de ahí salían clusters falsamente pequeños y el cap de 3
violado dentro de la cohorte.

Resultado IT3 sobre los 440 elegibles: **256 componentes** (tamaño máximo
**21**). En el muestreo se aplican dos cotas duras: **tope de 3 por componente
conexa** y **0 pares directos ≥ 0.90** dentro de la cohorte (un complejo es
inelegible si comparte una cadena ≥ 0.90 con otro ya seleccionado). La cohorte
final usa **112 componentes, todas de tamaño 1**, con **0 pares de cadenas
≥ 0.90** (verificado con un union-find independiente que reparsea SEQRES;
`metrics.json: selection.pares_cadena_ge90_en_cohorte = 0`).

**Caso de regresión documentado (fallo IT2):** la serie
`3g2z/3g30/3g31/3g34/4de0/4de1` comparte una cadena A IDÉNTICA de 262
residuos (pares sim = 1.0; `3g35` a 0.972). En IT2, 6 de esos complejos
entraron a la cohorte con ids de cluster distintos (el union-find incompleto
no los colapsaba). En IT3 los 6 (`3g2z`, `3g30`, `3g31`, `3g34`, `3g35`,
`4de0`) caen de la cohorte y se reemplazan por elegibles sin conflicto;
`4de1` permanece sin ningún par ≥ 0.90 con el resto de la cohorte.

## 13. Muestreo estratificado (etapa 6)

Procedimiento (determinista, `scripts/build_confirm_cohort.py`):

1. Pool primario = estrato drug-like (256). Celdas = flexibilidad (4 bins de
   rotables) × resolución (3 bins); cuotas proporcionales con el método del
   resto mayor CORREGIDO (B2): `floor(count/n · total)` para todos, piso 1 solo
   para bins no vacíos con cuota 0 cuando el total lo permite, remanente
   repartido de a +1 por parte fraccionaria descendente con desempate por
   nombre de bin.
2. Cotas DURAS (nunca se relajan): **tope 1 por unidad primaria química**
   (scaffold_id + InChIKey14), **tope 3 por componente conexa de cadenas de
   receptor** y **0 pares directos ≥ 0.90** dentro de la cohorte (un complejo
   es inelegible si comparte una cadena ≥ 0.90 con otro ya seleccionado).
3. Restricciones suaves con relajación documentada: cuota de metales pocket
   (objetivo 15, cohorte 17), cuotas de pKi y año con tolerancia.
4. Orden determinista por celda; barajado DENTRO de cada celda con
   `random.Random(42)` (semilla preregistrada).
5. La heurística determinista seleccionó **102** drug-like de 112 bajo las
   cotas duras (no se demostró que 102 sea el máximo combinatorio); los
   **10** restantes se completan con estratos no drug-like en orden
   documentado (fragment, peptide, lipid, oligo, xl) con `gate_primary=false`
   y reporte aparte (fragment 1, peptide 6, oligo 1, xl 2).

Cuotas de celda almacenadas (`metrics.json: selection.cuotas_celdas_druglike`,
orden alfabético de celda): 31 / 36 / 4 / 15 / 26. Son OBJETIVOS para 112,
NO la composición efectiva de los 102 drug-like. Celdas drug-like EFECTIVAS
realizadas (mismo orden alfabético): `rot_0_4|res_2_2p5` 31, `rot_0_4|res_lt2`
27, `rot_10_14|res_lt2` 3, `rot_5_9|res_2_2p5` 15, `rot_5_9|res_lt2` 26
(31 / 27 / 3 / 15 / 26 = 102). No hay drug-like con ≥ 15 rotables entre los
elegibles: los 33 elegibles `rot_15_plus` son fragmentos/péptidos/xl,
reportados aparte.

Distribución de la cohorte: resolución < 2.0 Å 64 / 2.0–2.5 Å 48; rotables
0–4 59, 5–9 42, 10–14 6, ≥ 15 5; pKi < 6 47, 6–8 31, ≥ 8 34; año ≤ 2000 6,
2001–2010 58, > 2010 48; con metal pocket 17, sin metal 95.

## 14. Composición final y garantías

`candidates.jsonl`: 112 líneas, una por complejo, con `pid`, `resolution`,
`year`, `pki`, `n_heavy`, `mw`, `n_rings`, `n_amide`, `rot_bonds`, `stratum`,
`scaffold_id` (SHA-256[:12] de la clase), `inchikey14`, `primary_unit`,
`receptor_cluster_id`, `metals` (pocket), `metal_detail`, `metal_near`,
`metal_remote`, `meeko_status`, flags de QC, `gate_primary` y `selected_rank`.

Garantías verificadas por construcción y por chequeo independiente:

- 0 pids de la cohorte en las 8 categorías de desarrollo (1571 pids).
- 0 ligandos con clase de scaffold, InChIKey14 o ECFP ≥ 0.90 de desarrollo.
- 0 receptores con solapamiento de cadenas ≥ 0.90 contra las 1073 cadenas
  únicas de desarrollo (1314 unidades / 2088 cadenas); incluye
  `kmer_overlap_100` (sim == 1.0, que NO implica secuencia idéntica — captura
  también constructos truncados, §6).
- ≤ 3 complejos por componente conexa de cadenas — la cohorte usa **112
  componentes, todas de tamaño 1** (el cap de 3 se cumple con margen).
- 0 pares de cadenas ≥ 0.90 dentro de la cohorte (verificado con union-find
  independiente que reparsea SEQRES; `pares_cadena_ge90_en_cohorte = 0`).
- ≤ 1 complejo por unidad primaria química (112 unidades para 112 complejos).
- Todos con `protein.pdb` + `ligand.sdf` presentes; pose cristalográfica en el SDF.
- 102 drug-like con `gate_primary=true` + 10 no drug-like con
  `gate_primary=false` (fragment 1, peptide 6, oligo 1, xl 2); meeko OK en
  los 112.

## 15. Protocolo de evaluación — BORRADOR para RS-CONFIRM-01 (NO parte del sello de FND-05)

**Separación de alcances (crítico):** FND-05 congela EXCLUSIVAMENTE la
composición de la cohorte (pids, exclusiones, estratos, hashes de estructura).
Todo lo que sigue es BORRADOR de trabajo y NO forma parte del sello de FND-05:
**30 conformeros**, **box (MolPocket 20 Å vs MolFlex 25 Å + centro
cristalográfico)**, **deduplicación provisional** y **RMSD simétrica** siguen
ABIERTOS y se congelarán en RS-CONFIRM-01 junto con poses, motores, modelos,
dedup, métrica y evaluación. FND-05 puede sellarse sin fingir que la
evaluación está cerrada.

Baseline y candidato recibirán EXACTAMENTE el mismo conjunto de poses:

- **Binarios y versiones**: AutoDock Vina **v1.2.7** (`tools/vina/vina.exe`),
  Meeko **0.7.1**, Open Babel **3.1.0**, `scripts/molflex.py` (rama
  `experimentos/ruta-c-molflex`, commit del manifest), Python **3.14.3**,
  RDKit 2025.09.6, numpy 2.4.4.
- **Preparación química**: ligando con Meeko (AddHs +
  `MoleculePreparation`); receptor SIN protonación explícita — el repositorio
  no documenta protonación del receptor, así que la política actual (receptor
  sin protonar) se propone como DEFAULT de D-RC-CONFIRM (a congelar en
  RS-CONFIRM-01).
- **Semillas**: 42 (muestreo, ensemble y cualquier aleatoriedad).
- **Vina**: `--exhaustiveness 8 --num_modes 9 --cpu` explícito (constantes de
  `scripts/molflex.py`).
- **Conformeros MolFlex**: 30 fijos (`--n-conf 30`) — ABIERTO, a revisar en
  MF-02 y congelar en RS-CONFIRM-01.
- **Definición de box**: pocket detector / MolPocket top-1, radio **20 Å** —
  ABIERTO. NOTA de alineación pendiente: `scripts/molflex.py` usa
  `BOX_SIZE = 25.0` Å centrada en el centroide del ligando cristalográfico;
  la ejecución de D-RC-CONFIRM debe alinear el script a 20 Å (acción
  registrada, resolución en RS-CONFIRM-01).
- **Deduplicación por RMSD pocket-frame**: umbral a definir en MF-11 — ABIERTO;
  valor PROVISIONAL documentado: dos poses con RMSD pocket-frame < 1.0 Å se
  tratan como duplicadas (revisar y congelar en RS-CONFIRM-01).
- **Política de timeout/fallo**: los fallos técnicos cuentan como fallos en el
  resultado global OBLIGATORIO (ITT); NO hay reemplazos silenciosos.
- **Construcción de la unión Vina+MolFlex**: concatenar los candidatos de
  ambos motores por complejo y deduplicar con la regla anterior.
- **Denominadores** (contrato §9, redacción canónica):
  - Gate confirmatorio PRIMARIO: los **102 complejos drug-like**
    (`gate_primary=true`), punto estimado ≥ 0.70 + bootstrap pareado vs v0.6.
  - Resultado global OBLIGATORIO (ITT): los **112 complejos**, contando los
    fallos técnicos como fallos (un complejo con 0 poses válidas = fallo del
    complejo).
  - Análisis SECUNDARIO: los **10 complejos no drug-like** (fragment 1,
    peptide 6, oligo 1, xl 2), descriptivo, sin inferencia fuerte por tamaño.
- **Igualdad de condiciones**: el baseline y el candidato consumen EXACTAMENTE
  el mismo conjunto de poses (misma preparación, misma caja, misma semilla).

## 16. Métrica RMSD simétrica — BORRADOR para RS-CONFIRM-01 (especificación, implementación futura)

RMSD **pocket-frame SIN alineamiento rígido**, con **simetría química por
automorfismos del grafo molecular** (NO parte del sello de FND-05):

1. Marco de pocket: idéntico al de `rmsd_pose_pocket()` de
   `scripts/molflex.py` (línea 262) — comparación 1:1 en el sistema de
   coordenadas del cristal, sin compensar traslación/rotación de la pose.
2. La simetría química NO se resuelve con asignación libre por elemento. El
   RMSD se minimiza EXCLUSIVAMENTE sobre **automorfismos del grafo molecular
   del ligando**: grafos no dirigidos con aristas tipadas por orden de enlace
   y aromaticidad, vértices tipados por elemento y carga formal, y
   estereoquímica cuando aplica. **ADVERTENCIA:** una asignación libre por
   elemento (p. ej. húngaro por elemento) puede intercambiar carbonos
   químicamente no equivalentes y producir un RMSD artificialmente bajo.

Algoritmo (especificación — se describe el método, no se implementa):

1. Construir el grafo tipado del ligando (vértices: elemento + carga formal +
   estereoquímica cuando aplica; aristas no dirigidas: orden de enlace +
   aromaticidad).
2. Enumerar los automorfismos del grafo tipado (p. ej. vía canonical labeling
   o particiones de órbitas de átomos).
3. rmsd^2 = mínimo sobre automorfismos del RMSD pocket-frame con el mapping
   inducido por cada automorfismo, sin alineamiento rígido.

Pseudocódigo:

```
rmsd_pose_pocket_simetrica(crystal, coords_pose, ligando):
    pesados = átomos pesados de ambos (misma cuenta)
    grafo_tipado = construir_grafo_tipado(ligando)      # vértices: elemento/carga/estereo
                                                        # aristas: orden de enlace + aromaticidad
    automorfismos = enumerar_automorfismos(grafo_tipado)  # canonical labeling u
                                                          # órbitas (RS-CONFIRM-01)
    costo(i, j) = ||p_crystal[i] - p_pose[j]||^2       # coordenadas del cristal,
                                                        # sin alineamiento rígido
    rmsd^2 = min_{phi en automorfismos} ( suma_i costo(i, phi(i)) / n_pesados )
    return sqrt(rmsd^2)
```

La implementación sigue siendo trabajo de RS-CONFIRM-01; esta sección fija el
contrato SIN congelarlo en FND-05 (coherente con §15).

## 17. Cegamiento = MECANISMO, no intención — cuarentena materializada (B3)

El claim correcto NO es "realmente ciego": en esta máquina monousuario no hay
control de acceso de máquina. La frase correcta es **holdout confirmatorio con
secuestro procedimental de etiquetas**: los 112 complejos proceden del MISMO
corpus PDBbind que el desarrollo (no es una cohorte externa) y la protección
se logra por procedimiento, no por acceso.

Mecanismo materializado (ITERACIÓN 4):

1. **Denylist central** — `scripts/artifacts_science/FND-05/denylist_pids.json`:
   112 pids, SHA-256 de `candidates.jsonl` y regla explícita ("prohibido
   incluir estos pids en cualquier dataset o experimento futuro del programa").
2. **Verificación automática en builders** — `scripts/build_confirm_cohort.py`
   excluye los pids denylistados del pool en la etapa 1 (defensivo; hoy no-op
   porque la cohorte no se regenera). `scripts/confirm_denylist.py` audita
   cualquier lista de pids contra la denylist y aborta si la cohorte cambió
   ("cohorte cambiada, denylist obsoleto").
3. **Challenge inputs sin coordenadas nativas** — los ligandos de referencia
   se entregan al evaluador sin su pose cristalográfica (la generación de los
   challenge inputs es trabajo de RS-CONFIRM-01).
4. **Custodia separada de referencias** — las referencias 3D viven en un área
   separada FUERA del path de trabajo, p. ej. `data/confirm_references/`.
5. **Política explícita de ejecución del evaluador** — en esta máquina
   monousuario, SOLO el maintainer o un script de evaluación sellado pueden
   ejecutar el evaluador de D-RC-CONFIRM (política procesal documentada; no
   hay enforcement técnico de acceso).
6. **Prohibición explícita de reuso** — los 112 pids quedan registrados en el
   manifest y en la denylist.
7. Orden de sellado (única pasada): **diseño → lista dev → candidatos →
   índice → código → PDB externos → paquetes → validador**.

FND-05 queda en `draft` validado; `seal` y `finish` son actos explícitos del
maintainer.

## 18. Limitaciones conocidas (declaradas, no ocultas)

1. **Familia biológica** no disponible localmente → clusters de cadenas como
   proxy; family-disjoint (CATH/Pfam/ECOD) queda como trabajo futuro (§6).
2. **Homología por k-meros k=8** es proxy de identidad, no alineamiento global.
3. **Reglas de `discover_dev_pids.py`** para 2 de 8 categorías son
   superconjuntos conservadores del conteo histórico (documentado en el
   README de FND-05); la unión deduplicada (1571) no cambia.
4. **907 pids del índice sin protein.pdb** quedan fuera del pool.
5. **Estratos no drug-like** (fragment/peptide/lipid/oligo/xl: 184 de 440
   elegibles) no entran al gate primario; en IT3, 10 de ellos completan la
   cohorte con `gate_primary=false` tras las cotas duras del §13 (102
   drug-like), y se reportan aparte.
6. La evaluación confirmatoria NO se ejecuta aquí: es posterior al sellado y
   de una sola pasada (RS-CONFIRM-01).

## 19. Reproducibilidad

```powershell
python scripts/discover_dev_pids.py --out scripts/artifacts_science/FND-05/dev_seen_pids.json
python scripts/build_confirm_cohort.py `
  --index data/pdbbind/INDEX_faseb_enriched_full_20260813_184439.2020 `
  --pdbbind data/pdbbind `
  --dev-pids scripts/artifacts_science/FND-05/dev_seen_pids.json `
  --dev-receptor-pdbs data/targets "data/1f0r_protein.pdb" "data/1gkc.pdb" `
    "data/1gpk_protein.pdb" "data/1hsg.pdb" "data/1O86.pdb" "data/1O86_clean.pdb" `
    "data/1UZE.pdb" "data/1xp0.pdb" "data/3ert.pdb" "data/3pp0.pdb" `
    "data/4NY4.pdb" "data/7e2y.pdb" "data/7e2y_chainR.pdb" `
  --refined-index data/pdbbind/INDEX_refined_data.2020 `
  --out-dir scripts/artifacts_science/FND-05 --n-target 112 --seed 42
```

Tests obligatorios:

```powershell
python scripts/test_build_confirm_cohort.py
python scripts/experiment_manifest.py validate FND-05
```

Salidas: `candidates.jsonl` (112), `pool_eligible.jsonl` (440),
`failures.jsonl` (1292 con criterios y pares de cadenas), `metrics.json`
(conteos por etapa y distribuciones), `per_complex.jsonl` (alias). Determinismo
verificado: dos ejecuciones producen `candidates.jsonl` con SHA-256 idéntico
(`C12FB947A3B4068F164595D193147ECA9E4EB31C67B85142733E8CBBA7A26959`).

Nota de cuarentena (ITERACIÓN 4): re-ejecutar el builder DESPUÉS de la
cuarentena produce una cohorte nueva por diseño (los 112 pids retirados se
excluyen del pool en la etapa 1). La cohorte congelada es reproducible desde
los artefactos sellados (SHA-256 `C12FB947...A26959`) y desde el commit
`632bcbc`, no re-ejecutando el script.

## 20. Archivos de este experimento

- `manifest.json` — registro FND-01 (draft, validado, sin sellar; commit y
  dependencias reales).
- `DESIGN.md` — este documento.
- `dev_seen_pids.json` — pids de desarrollo por categoría (regenerado).
- `candidates.jsonl` — cohorte propuesta (112).
- `pool_eligible.jsonl` / `per_complex.jsonl` — 440 elegibles tras exclusiones.
- `failures.jsonl` — 1292 excluidos con criterios.
- `denylist_pids.json` — cuarentena materializada: los 112 pids congelados,
  el SHA-256 de `candidates.jsonl` y la regla de prohibición de reuso.
- `metrics.json` — conteos por etapa y distribuciones.
- `README.md` — generado por la herramienta de manifest + sección de
  limitaciones documentadas.
