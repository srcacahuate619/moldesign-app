# REC-03-PRE — Prerregistro: ¿un grid predicho repara el docking que el catálogo pierde?

**Fecha:** 2026-08-17
**Rama:** `experimentos/ruta-c-molflex`
**Estado:** PREREGISTRO (nada de docking ejecutado bajo este registro)
**Tipo:** prerregistro del experimento **REC-03**; la ejecución es un experimento distinto y no se incorpora aquí con `maintain`.
**Entradas selladas que se consumen por hash:** `REC-01` (`4a4fbc7`) y `REC-01-R1` (`4a4fbc7`), ambos GO y `validate` OK.

---

## 1. De dónde viene la pregunta

REC-01 auditó los 387 targets del catálogo y encontró que **57 (14.7%)** disparan al menos un código de excepción — 4.75× los «12 grids problemáticos» que asumía la hipótesis original. REC-01-R1 los trianguló por severidad y dejó una **cohorte accionable de 25**: 11 `S1_CRITICO` (la caja no contiene **ni un solo átomo** del ligando nativo) y 14 `S2_GRAVE` (contención parcial, 0.17–1.00).

Auditar no repara. La pregunta abierta es si existe un procedimiento **automático y sin ver el ligando** que recupere el docking en esa cohorte sin romper los targets sanos.

## 2. Por qué MolPocket y por qué NO los hotspots del catálogo

`backend/utils/structural.py::discover_pocket_from_pdb` — la función que produjo los `hotspots` del catálogo — es **ligando-dependiente**: toma los 15 residuos más cercanos al ligando nativo y centra la caja en él. Construir el grid «reparado» a partir de esos hotspots sería **circular**: derivar la caja del ligando y después «descubrir» que el ligando cabe. Por eso REC-07 necesitó un ancla independiente (Cys25) y por eso aquí los hotspots **están prohibidos** como fuente de cajas.

`backend/utils/pocket_detector.py::detect_pockets` (motor MolPocket, reimplementación de fpocket) es **ligando-libre por construcción**: `_parse_heavy_atoms` solo lee líneas `ATOM`, de modo que los `HETATM` del ligando no participan en la detección. Es determinista y sin RNG. Ese es el único predictor admisible como brazo reparador.

## 3. Entorno

- Windows 11, Python 3.14.3, ejecución local (el servidor remoto queda libre para RS-03-PARAM-B).
- AutoDock Vina **1.2.7** (`tools/vina/vina.exe`), Meeko **0.7.1**, RDKit **2025.09.6**, Open Babel (pybel), MolPocket del propio repo.
- Coste medido antes de congelar el diseño, sobre `1BN1` (`S4_LEVE`, **fuera de la cohorte**): preparación 6.9 s; una corrida `exhaustiveness=32`, `cpu=1` → **97.5 s**.

## 4. Cohorte

- **ACCIONABLE (25)**: los 11 `S1_CRITICO` + 14 `S2_GRAVE` de `REC-01-R1`. Todos HOLO con ligando nativo (10–46 átomos pesados) y geometría completa.
- **CONTROL (12)**: muestreo `random.Random(42).sample` sobre la lista **ordenada** de los 218 `S0_SIN_EXCEPCION` HOLO con ligando extraíble. El control es el que impide un GO tramposo: mide si el procedimiento rompe lo que hoy funciona.
- **Cuarentena verificada**: cero solapamiento con `poses_train.jsonl` (116) y `poses_test.jsonl` (47) del pose selector.

## 5. Brazos — la única variable es el centro de la caja

| Brazo | Centro | Tamaño |
|---|---|---|
| `G_CAT` | el del catálogo (statu quo) | el del catálogo |
| `G_MP1` | pocket top-1 de MolPocket | **el del catálogo** |
| `G_MP2` | pocket 2 | el del catálogo |
| `G_MP3` | pocket 3 | el del catálogo |
| `G_MP_SCORE` | *derivado*: entre `G_MP1..3`, el de **mejor score de Vina** por semilla | — |

El tamaño se mantiene fijo deliberadamente: si cambiara junto con el centro, un resultado positivo no podría atribuirse a ninguno de los dos. La selección de `G_MP_SCORE` usa **solo el score**, nunca la posición del ligando: elegir «el pocket más cercano al ligando» sería mirar la respuesta.

**Configuración congelada:** `exhaustiveness=32`, `num_modes=9`, `cpu=1`, semillas `{42, 43, 44}`, timeout 1800 s por corrida, 10 procesos en paralelo. Total: 37 targets × 4 cajas × 3 semillas = **444 corridas**, más 4 de determinismo.

**Preparación:** receptor = líneas `ATOM` de **todas** las cadenas, sin aguas y **sin ningún HETATM** (el ligando nativo debe salir o bloquearía su propio sitio); regla de altloc idéntica a `preparer.py`. Ligando = `HETATM` del `res_id` registrado por REC-01-R1 → Open Babel (`addh`) → SDF → Meeko. Los cuatro brazos comparten **el mismo receptor y el mismo ligando** (SHA-256 registrado por target).

## 6. Métrica

**Primaria:** RMSD simétrico **in situ** de la pose top-1 contra el ligando cristalográfico del mismo PDB — `rdMolAlign.CalcRMS`, **sin realinear**. Realinear (`GetBestRMS`) mediría parecido de forma, no acierto de docking: en la prueba de máquina la diferencia fue 125.9 Å vs 2.5 Å sobre el mismo par.
**Éxito de un target** = RMSD top-1 ≤ **2.0 Å** en **≥2 de 3** semillas.
**Secundarias (descriptivas, no deciden):** RMSD del mejor de los 9 modos, contención del ligando en la caja, score top-1, validez y coste.

## 7. Geometría ya computada, declarada antes de ejecutar

Precedente: REC-07 §6. `scripts/rec03_preflight.py` midió, sobre los 243 targets HOLO elegibles, dónde cae cada pocket respecto del ligando nativo. **Nada de esto es resultado del experimento: es la condición de partida.**

| Estrato | n | mediana `d_cat` | contención 100% catálogo | mediana `d_top1` | contención 100% MP1 | mediana `d_mejor3` | contención 100% mejor-de-3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| `S1_CRITICO` | 11 | 48.18 Å | 0/11 | 52.98 Å | 2/11 | 20.72 Å | 3/11 |
| `S2_GRAVE` | 14 | 19.65 Å | 3/14 | 34.81 Å | 2/14 | 9.39 Å | 7/14 |
| `S0` (pool control) | 218 | **0.00 Å** | **218/218** | 8.01 Å | 125/218 | 4.55 Å | 163/218 |

Lecturas obligadas, con sus consecuencias asumidas por adelantado:

1. **El catálogo es perfecto en S0 por construcción** (`d = 0.00`, contención 218/218): esos grids se derivaron del ligando. El control no premia al catálogo por acertar, sino que mide cuánto se pierde al sustituirlo.
2. **MolPocket top-1 por sí solo ya perdería targets sanos**: contiene el ligando en 125/218 (57%) de los S0. La regresión del brazo `G_MP1` está anticipada; por eso el brazo que se juzga es `G_MP_SCORE`.
3. **Techo geométrico de la reparación: 10 de 25.** Solo 3 `S1` + 7 `S2` tienen contención total del ligando en alguno de los tres pockets. En los 15 restantes **ninguna** caja de MolPocket puede producir una pose correcta, con docking o sin él. Cualquier lectura que ignore este techo es deshonesta.
4. En los 11 `S1` el fracaso de `G_CAT` **está determinado por construcción** (contención 0.0): no será un hallazgo cuando ocurra.

## 8. Gates y decisión

| ID | Gate | Criterio |
|---|---|---|
| G1 | **Validez** | ≥98% de las 444 corridas válidas: `rc=0`, 1 ≤ modos ≤ 9, scores finitos leídos de `REMARK VINA RESULT`, pose reconstruible a RDKit |
| G2 | **Sólo lectura** | `curated_targets.json` y `.csv` conservan su SHA-256 |
| G3 | **Reparación** | `G_MP_SCORE` repara **≥5 de los 25** accionables (la mitad del techo geométrico declarado de 10) |
| G4 | **No regresión** | en el control, `G_MP_SCORE` conserva **≥70%** de los targets que repara `G_CAT` |
| G5 | **Determinismo** | misma semilla → mismo score top-1 y mismo RMSD al repetir (4 targets, `G_CAT`, semilla 42) |

**GO** = los cinco gates pasan. **NO_GO** = falla G3 o G4 (o la validez técnica, en cuyo caso el experimento se repite, no se interpreta).

Un GO **no actualiza el catálogo**: promover un grid a producción exige E6 del doc. 49 (no-regresión, manifest, rollback), fuera de alcance. Un NO_GO tampoco es neutro: si `G_MP_SCORE` no repara, la conclusión registrada es que **la reparación automática del catálogo por predicción de pocket no es viable con este motor**, y los 25 targets accionables quedan como deuda de curación manual.

## 9. Prohibiciones

- Cero escrituras en `curated_targets.json`, `curated_targets.csv`, DB o `rescoring/`.
- Prohibido usar la posición del ligando nativo para elegir caja, pocket, semilla o pose. El ligando solo interviene como **referencia de evaluación**.
- Prohibido añadir brazos, semillas o targets después de ver resultados.
- Prohibido reportar `rmsd_mejor_de_9` como si fuera el endpoint: es descriptivo.
- No se modifican `REC-01` ni `REC-01-R1` (sellados).

## 10. Limitaciones declaradas

- **Sin cofactores ni metales**: se eliminan todos los `HETATM`. Idéntico en los cuatro brazos, de modo que no sesga la comparación, pero puede deprimir la tasa absoluta de éxito en metaloenzimas.
- **Órdenes de enlace inferidos por Open Babel** desde el PDB del ligando; el mismo archivo se usa como referencia de RMSD y como entrada de docking, así que un error de perceptión afecta a los cuatro brazos por igual.
- **Un solo confórmero de partida** y receptor rígido: es el protocolo de producción, no el estado del arte.
- El PDB se usa tal como está en `data/target_library/`: sin biounit, sin reconstrucción de cadenas laterales incompletas.
