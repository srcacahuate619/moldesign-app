# REC-07 — Corrección del grid APO de 5TUN, con ancla catalítica y control de docking

**Estado:** preregistrado, **sin ejecutar**.
**Fecha de preregistro:** 2026-08-17.
**Nivel de madurez (doc. 49 §3):** E2 — desarrollo con artefacto y comparación. **No** promueve a producción.
**Protocolo:** doc. 49 §7 (REC-07) · [`docs/35_GRID_APO_5TUN_PENDIENTE.md`](../../../docs/35_GRID_APO_5TUN_PENDIENTE.md)
**Entrada sellada:** [`REC-01-R1`](../REC-01-R1/) — `5TUN` marcado `E8_HOTSPOT_FUERA_DE_CAJA`, `margen_min = −5.147 Å`, severidad `S4_LEVE`.

---

## 1. Qué se conoce ya y qué no (honestidad sobre el cegamiento)

**Parte geométrica: NO ciega.** Las distancias y contenciones de los tres grids
se computaron durante el diseño y están declaradas en §6. El propósito de la
ejecución no es descubrirlas, sino sellarlas con artefacto reproducible.

**Parte de docking: ciega salvo un smoke.** Se ejecutó una única corrida de
prueba de la cadena técnica (receptor + E64c + Vina, `exhaustiveness=8`,
`seed=42`, brazo `G_ADAPT`) que devolvió top-1 = −4.418 kcal/mol. **No** se midió
la distancia a Cys25 SG, **no** se ejecutaron los otros brazos y **no** se probó
ninguna otra semilla. La configuración definitiva (`exhaustiveness=32`, 5
semillas, 3 brazos) no se ha ejecutado.

## 2. El problema

`5TUN` (catepsina K humana, **APO**, 1.62 Å) no tiene ligando co-cristalizado, de
modo que el grid del catálogo lo fijó MolPocket. El doc. 35 documentó por
inspección visual que `TYR89` y `GLU84` —hotspots legítimos— quedan fuera de la
caja, y REC-01-R1 lo confirmó cuantitativamente: `margen_min = −5.147 Å`.

El doc. 35 §4 propuso recalibrar a la detección de `discover_pocket_from_pdb`
(centro `(8.44, 136.26, 21.28)`, tamaño `24.9³`) **advirtiendo explícitamente que
la detección APO es probabilística y no debe creerse a ciegas**. Este experimento
toma esa advertencia en serio: valida la propuesta contra un ancla independiente
de MolPocket antes de recomendarla.

## 3. Ancla independiente

La catepsina K pertenece a la familia papaína (cisteína-proteasas C1), cuya
tríada catalítica es **Cys25 – His162 – Asn182**. Es una referencia estructural
canónica, verificada presente en el PDB de 5TUN, e **independiente de MolPocket,
de los hotspots del catálogo y de cualquier predicción**.

**Convención de altloc, congelada.** `Cys25:SG` está modelado en **dos
confórmeros alternativos** con ocupancia 0.50 cada uno:

| altloc | `Cys25:SG` (Å) |
|---|---|
| **A** | **(16.59, 140.61, 16.59)** ← se usa |
| B | (17.30, 139.78, 16.40) |

Se adopta **altloc A** porque es el que Meeko escribe en el receptor
(`--default_altloc A`): la geometría del ancla debe describir el mismo átomo que
el docking realmente ve. Usar el otro confórmero mediría un receptor que no se
está acoplando.

| Ancla (altloc A) | Coordenada (Å) |
|---|---|
| `Cys25:SG` (nucleófilo catalítico) | (16.59, 140.61, 16.59) |
| `His162:NE2` (sin altloc) | (12.80, 142.34, 14.71) |
| `Asn182:ND2` (sin altloc) | (9.17, 143.85, 14.52) |
| centroide de la tríada | (12.85, 141.60, 15.27) |

El ancla primaria es **`Cys25:SG`**: es el átomo que ataca al sustrato y el centro
funcional del sitio catalítico.

> **Corrección de diseño (2026-08-17, antes de sellar).** Un cómputo exploratorio
> previo leyó `Cys25:SG` tomando la **última** ocurrencia del PDB, es decir
> altloc **B**, y produjo distancias ~0.2–0.3 Å distintas de las de §6. Al fijar
> la convención en altloc A —coherente con el receptor— las cifras se recomputaron.
> Las conclusiones cualitativas no cambian. Se registra porque el preregistro no
> debe contener números obtenidos con una convención distinta de la que se ejecuta.

## 4. Brazos comparados (congelados)

| Brazo | Centro (Å) | Tamaño (Å) | Origen |
|---|---|---|---|
| `G_DB` | (11.151, 133.751, 14.09) | 22.0 × 22.0 × 22.0 | catálogo actual |
| `G_MP` | (8.44, 136.26, 21.28) | 24.9 × 24.9 × 24.9 | propuesta del doc. 35 (MolPocket) |
| `G_ADAPT` | (11.104, 135.221, 21.288) | 19.0 × 25.3 × 25.9 | caja mínima axis-aligned que contiene los 15 hotspots (CA) **y** los 3 átomos de la tríada, con 4.0 Å de padding, leyendo `Cys25:SG` en altloc A |

El padding de 4.0 Å y la regla de construcción de `G_ADAPT` se fijan aquí y no se
ajustan tras ver resultados. No se exploran otros paddings ni otros centros.

## 5. Control de docking

**Ligando:** `E6C` (E64c), extraído de los `HETATM` de
`data/target_library/03_protease/1ITO.pdb` (catepsina B + E64c). E64/E64c es el
inhibidor canónico de cisteína-proteasas de la familia papaína y alquila el
azufre de la cisteína catalítica. El ligando procede de una estructura local, no
de una SMILES escrita de memoria: `C15H28N2O5`, 22 átomos pesados, 12 enlaces
rotables tras preparación con Meeko.

**Expectativa física preregistrada:** bajo un grid que contenga correctamente el
sitio, Vina debe colocar E64c **en contacto con `Cys25:SG`**. Se mide la distancia
mínima de cualquier átomo pesado del ligando a `Cys25:SG` en la pose top-1.
Umbral de contacto: **≤ 5.0 Å**.

**Limitación declarada:** Vina hace docking **no covalente**; E64c es un inhibidor
covalente. Por eso el criterio es *contacto*, no distancia de enlace, y el
resultado valida que **la caja permite encontrar el sitio**, no que la pose
reproduzca el aducto covalente. No se afirma exactitud de pose: 5TUN es APO y no
existe pose cristalográfica de referencia en esta estructura.

**Preparación del receptor, congelada.** El PDB se filtra **antes** de Meeko
replicando `backend/services/docking/preparer.py`, que es el camino de
producción: sólo registros de coordenadas, **eliminación de aguas**
(`HOH`/`WAT`/`DOD`), sólo la cadena `A`, `residue_seq > 0`, y altloc mayoritario
por residuo (prefiriendo la variante sin altloc en caso de empate — regla que
selecciona `A` para `Cys25`). Después,
`meeko.cli.mk_prepare_receptor --default_altloc A -a`.

El script **aborta** si el `.pdbqt` resultante conserva alguna línea `HOH`.

**Configuración congelada:** `exhaustiveness=32`, `num_modes=9`, `cpu=1`,
semillas `{42, 43, 44, 45, 46}`. Los tres brazos usan el **mismo** archivo de
receptor y el **mismo** ligando: la única variable es la caja.

> **Ejecución invalidada y repetida (2026-08-17, antes de sellar).** Una primera
> ejecución pasó el PDB **crudo** a Meeko, que conservó las ~387 aguas
> cristalográficas (1161 líneas con hidrógenos añadidos) como parte del receptor
> rígido. El bolsillo quedó ocupado por oxígenos de agua y el docking devolvió
> **scores positivos** (+23 a +33 kcal/mol) con 1–5 modos en vez de 9 — geometría
> imposible, no afinidad débil. **El gate G3 de validez detectó el fallo y marcó
> FAIL**, que es exactamente su función. Se corrigió la preparación y se repitió.
> Ningún criterio de decisión se modificó: el umbral de contacto (5.0 Å), la
> regla de selección del grid y los gates son los mismos que antes de esa
> ejecución. Aquella corrida queda descartada por inválida, no por su resultado.
> (Las corridas de esa tanda con `rc=3221225794` son un artefacto de haber
> detenido el proceso padre a mitad, no un fallo experimental.)

Verificado en el diseño: el `.pdbqt` del receptor es **idéntico** (mismo SHA-256)
al prepararlo con la caja de `G_DB` y con la de `G_ADAPT`, porque para un receptor
rígido Meeko escribe la macromolécula completa. Esto garantiza que la comparación
aísla el efecto del grid.

**Desviación de preparación declarada:** el residuo `A:49` (SER con la cadena
lateral incompleta — le faltan átomos, sin `OG`) no supera el emparejamiento de
plantillas de Meeko y se elimina con `-a/--allow_bad_res`, que es el mismo
fallback que usa `backend/services/docking/preparer.py`. Está a **13.64 Å** de
`Cys25:SG`, fuera del sitio catalítico inmediato, pero **adyacente a los hotspots
`LEU48` y `PRO50`**. La eliminación es idéntica en los tres brazos, por lo que no
sesga la comparación, pero queda registrada porque afecta al receptor absoluto.

## 6. Resultado geométrico ya computado, declarado antes de ejecutar

Con la convención de altloc A de §3:

| Brazo | d(Cys25 SG) | d(triada) | hotspots dentro | tríada dentro | `margen_min` hotspots | volumen (Å³) |
|---|---:|---:|---:|---:|---:|---:|
| `G_DB` | 9.10 | 8.77 | 12/15 | 3/3 | **−5.15** | 10,648 |
| `G_MP` | **10.36** | 9.57 | **15/15** | 3/3 | +2.78 | 15,438 |
| `G_ADAPT` | 9.01 | 9.43 | **15/15** | 3/3 | +4.00 | **12,450** |

Lectura anticipada, con los matices que corresponden:

- la propuesta del doc. 35 (`G_MP`) **sí** arregla la contención de hotspots pero
  **empeora** la proximidad al nucleófilo catalítico en 1.26 Å (10.36 vs 9.10);
- `G_ADAPT` contiene los 15 hotspots y la tríada, y queda **empatada** con `G_DB`
  en el ancla catalítica: 9.01 vs 9.10 Å es una diferencia de **0.09 Å, que no es
  significativa**. La afirmación honesta no es «está más cerca» sino «no está más
  lejos», que es lo que exige G2;
- los tres brazos contienen la tríada catalítica completa (3/3), de modo que
  ninguno excluye la maquinaria catalítica: lo que distingue a `G_DB` es que
  **recorta 3 hotspots** (`margen_min = −5.15 Å`);
- el `margen_min` de `G_ADAPT` es +4.00 Å por construcción (es el padding), no un
  resultado medido.

Una discrepancia con estas cifras indica error de implementación, no hallazgo.

**Regla de selección congelada:** entre los brazos que satisfacen G1 (15/15
hotspots y 3/3 tríada) y G2 (`d(Cys25 SG)` no mayor que `G_DB`), se recomienda el
de **menor volumen**, porque a igualdad de contención un grid menor reduce el
espacio de búsqueda y el coste. No se usa el score de docking para elegir el
grid: eso invertiría la dirección de la validación.

## 7. Gates

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Contención** | el grid recomendado contiene 15/15 hotspots (CA) y 3/3 átomos de la tríada |
| G2 | **Ancla** | `d(centro, Cys25 SG)` no mayor que la de `G_DB` (8.91 Å) |
| G3 | **Validez de docking** | en las 15 corridas: `rc=0`, archivo no vacío, `1 <= modos <= 9`, scores finitos leídos **exclusivamente** de `REMARK VINA RESULT`, geometría parseable |
| G4 | **Contacto catalítico** | pose top-1 de E64c a ≤ 5.0 Å de `Cys25:SG` en ≥ 3 de 5 semillas, en el grid recomendado |
| G5 | **No regresión** | el grid recomendado no es peor que `G_DB` en la tasa de contacto ni en la mediana de la distancia a `Cys25:SG` por más de 1.0 Å |
| G6 | **Determinismo** | misma semilla → mismo score top-1 y misma distancia de contacto al repetir |
| G7 | **Sólo lectura** | `curated_targets.json`, `curated_targets.csv` y las DB conservan su SHA-256 |

**GO** = los siete gates pasan y existe un grid recomendado.
**NO_GO** = ningún candidato satisface G1+G2, o falla la validez/contacto.

Un GO **recomienda** un grid; **no** actualiza el catálogo. Promover a producción
exige E6 en la escalera del doc. 49 (no-regresión, manifest, rollback), fuera del
alcance de este experimento.

## 8. Prohibiciones

- **Cero escrituras** en `curated_targets.json`, `curated_targets.csv`, DB o `rescoring/`.
- No se modifica `REC-01` ni `REC-01-R1` (sellados); su evidencia se consume por hash.
- No se re-ejecuta `discover_pocket_from_pdb`: el centro de `G_MP` se toma como
  dato del doc. 35, para probar *esa* propuesta y no otra.
- No se explora una retícula de paddings, centros, exhaustiveness ni ligandos
  adicionales. Si `G_ADAPT` falla, se registra el negativo.
- No se afirma exactitud de pose ni RMSD: 5TUN es APO y no hay ground truth de pose.
- No se generaliza a otros targets APO. La auditoría en lote es REC-01/REC-03.

## 9. Artefactos

```text
scripts/artifacts_science/REC-07/
  PREREGISTRO.md
  manifest.json
  metrics.json        geometría por brazo + docking por brazo/semilla + gates
  per_complex.jsonl   una línea por (brazo, semilla) = 15 registros
  failures.jsonl
  LECTURA.md
```

Ejecutor: `scripts/run_rec07_grid_5tun.py`. Semillas `{42,43,44,45,46}`;
la semilla del manifest es 42.
