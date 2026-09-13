# ADR científico: contrato de M5-Zn V1

**Estado:** decisión aceptada, pendiente de alineación de artefactos e implementación  
**Fecha:** septiembre de 2026  
**Afecta:** `scoring/engine.py`, dispatcher de protocolos, manifiestos, dossier y pruebas científicas  
**Documento marco:** `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md`  

> **CORRIGENDUM 2026-09-04 — dos de los tres perfiles están en cuarentena.**
>
> `docs/77_CORRIGENDUM_SITIO_DEL_BENCHMARK_M5_ZN.md` demuestra que los
> benchmarks retrospectivos de **MMP9 / 1GKC** y **ACE / 1O86** no acoplaron en
> el sitio del zinc catalítico: MMP9 a 18.74 Å del zinc y a 4.96 Å de un ion de
> calcio, y en ACE el 75.8 % de las poses cayó fuera de la caja declarada.
>
> Los §4.2 y §4.3 de este ADR siguen describiendo correctamente las FÓRMULAS y
> sus constantes —son reproducibles a precisión de máquina— pero **las
> afirmaciones sobre qué miden quedan retiradas** hasta que se rehaga la
> evidencia. Los dos perfiles devuelven `REVIEW_INVALID_BENCHMARK_SITE` y no
> `VALIDATED_PROFILE`.
>
> Hoy **ningún perfil M5-Zn produce un resultado científicamente liberable**:
> CA2 se abstiene por ausencia de GNN-D, y MMP9 y ACE están en revisión.

---

## 1. Decisión

M5 es la familia extensible de protocolos de MolDesign para sistemas con
metales. M5-Zn es su primer adaptador. La V1 no utiliza un peso familiar
genérico: define tres perfiles exactos para las tres dianas con comparación de
pipeline disponible y se abstiene de calcular un score compuesto fuera de ese
dominio.

Esta decisión sustituye dos comportamientos que no reproducen los experimentos:

- el ajuste actual de UMS en `engine.py`, con peso máximo `0.06` que se encoge
  según la confianza del stack;
- la entrada genérica de `stacking_weights.json` con `clgnn=1.0` para toda la
  familia metálica.

Las señales originales siempre se conservan por separado. El score M5-Zn es una
interpretación de ranking específica de un perfil, no una afinidad ni una
medida experimental.

---

## 2. UMS autorizado

La señal que entra en los tres perfiles es la variante **SMARTS-only** usada por
los análisis finales de bootstrap, DeLong y enriquecimiento. No es el UMS
histórico que mezclaba warheads, número de donantes y MolChamb.

```python
def ums_warhead_score(n_warheads: int) -> float:
    if n_warheads <= 0:
        return 0.0
    return 0.85 + 0.10 * min(n_warheads / 3.0, 1.0)
```

La detección usa los SMARTS corregidos y versionados. Modificar patrones,
normalización o escala crea una nueva versión de protocolo y exige regenerar
la evidencia científica.

La función debe vivir una sola vez en código de producción. Los scripts
`bootstrap_ci.py`, `delong_paired_test.py` y `ef_metrics.py` deben importarla o
demostrar mediante vectores comunes que calculan exactamente los mismos bytes
de entrada y valores de salida.

---

## 3. Normalización de Vina

Los benchmarks construyeron la señal como:

```python
vina_norm = min(abs(vina_kcal_mol) / vina_reference_max, 1.0)
```

`vina_reference_max` era el máximo de la cohorte evaluada. Recalcularlo con las
moléculas que el usuario haya cargado haría que una molécula cambiara de score
según sus vecinas. Para permitir evaluación individual reproducible, V1 congela
las referencias de los checkpoints originales:

| Perfil | Checkpoint | `vina_reference_max` |
|---|---|---:|
| CA2 / 3DC3 | `benchmark_checkpoint_ca2.json` | 10.450 |
| MMP9 / 1GKC | `benchmark_checkpoint_mmp9.json` | 8.247 |
| ACE / 1O86 | `benchmark_checkpoint_ace.json` | 9.566 |

Estas constantes deben almacenarse junto a los hashes de sus checkpoints. No
son umbrales universales de Vina. Una normalización diferente requiere
revalidación y un nuevo `protocol_version`.

---

## 4. Perfiles exactos autorizados

### 4.1. CA2 / PDB 3DC3

```text
protocol_id = M5_ZN_CA2_3DC3_V1

score = 0.20*Vina_norm
      + 0.20*XGBoost
      + 0.20*GNN-D
      + 0.40*UMS_warhead
```

CA2 requiere **GNN-D**, no CL-GNN. Si GNN-D no está disponible o no produce una
salida válida, el score compuesto queda `NOT_EVALUATED`. No se sustituye por
CL-GNN ni se redistribuyen sus pesos.

Referencia de reproducción actual: AUC M4 `0.8042`, AUC M5 `0.9314`, delta
`+0.1272` en `data/molchamb_loto/delong_paired_report.json`.

### 4.2. MMP9 / PDB 1GKC

```text
protocol_id = M5_ZN_MMP9_1GKC_V1

score = 0.75*XGBoost
      + 0.25*UMS_warhead
```

Vina y los GNN pueden conservarse como observaciones, pero no entran en este
score. No se les asigna peso por estar disponibles.

Referencia de reproducción actual: AUC M4 `0.8473`, AUC M5 `0.9208`, delta
`+0.0735` en `data/molchamb_loto/delong_paired_report.json`.

### 4.3. ACE / PDB 1O86

```text
protocol_id = M5_ZN_ACE_1O86_V1

score = 0.20*Vina_norm
      + 0.40*XGBoost
      + 0.40*UMS_warhead
```

Los GNN no entran en este perfil. La transferencia zero-shot medida para ellos
no justifica incorporarlos ni sustituir XGBoost.

Referencia de reproducción actual: AUC M4 `0.4362`, AUC M5 `0.6708`, delta
`+0.2345` en `data/molchamb_loto/delong_paired_report.json`.

---

## 5. Componentes ausentes o inválidos

Para cualquiera de los perfiles:

1. si falta un componente con peso distinto de cero, `m5_score = null`;
2. el estado se registra como `NOT_EVALUATED_MISSING_COMPONENT`;
3. no se renormalizan pesos;
4. no se sustituye XGBoost, GNN-D o UMS por otro modelo;
5. las señales que sí existan se muestran individualmente;
6. el dossier registra el componente ausente y la razón.

Un valor neutral fabricado, por ejemplo `0.5`, no cuenta como evaluación. NaN,
infinito, timeout, checkpoint ausente, error de features o fuera de dominio
producen abstención explícita.

---

## 6. Grafía canónica

La identidad canónica es:

```text
metalloenzyme
```

Es la forma inglesa estándar y la usada por el catálogo curado. La grafía
legacy `metaloenzyme` se acepta sólo al leer entradas antiguas.

Reglas:

1. nuevas claves, contratos emitidos y persistencia usan `metalloenzyme`;
2. los lectores aplican el alias exacto
   `metaloenzyme -> metalloenzyme`;
3. no se clasifica mediante coincidencias difusas como `"metal" in family`;
4. artefactos configurables no sellados se migran a la forma canónica con nueva
   versión y hash;
5. artefactos científicos sellados no se editan: su grafía histórica se
   conserva como procedencia y se normaliza al cargarlos;
6. los expedientes anteriores deben seguir abriendo sin reescribir su historia.

La normalización de grafía y la activación de los pesos nuevos se despliegan en
el mismo cambio. Corregir sólo el nombre activaría accidentalmente la política
genérica `clgnn=1.0`, que no reproduce los perfiles anteriores.

---

## 7. Comportamiento fuera de las tres dianas

### 7.1. Otra estructura de CA2, MMP9 o ACE

El nombre de la proteína no basta para heredar el perfil. Una estructura PDB
distinta puede cambiar cadena, bolsillo, metal, cofactores, aguas, caja y
distribución de poses.

Hasta demostrar equivalencia estructural mediante una regla versionada, el caso
queda:

```text
protocol_family = M5_ZN
scientific_status = REVIEW_OUT_OF_VALIDATED_STRUCTURE
m5_score = null
```

### 7.2. Otra metaloenzima de zinc

M5-Zn sí ejecuta la preparación y auditoría comunes:

- verifica y conserva el Zn relevante;
- registra coordenadas y geometría;
- ejecuta Vina como evidencia instrumental;
- detecta warheads SMARTS;
- calcula señales geométricas si existe una pose válida;
- conserva las salidas de modelos que tengan su propio dominio aplicable.

Pero no hereda los pesos de CA2, MMP9 o ACE:

```text
scientific_status = REVIEW_OUT_OF_VALIDATED_TARGET
m5_score = null
```

La presencia de un warhead no produce por sí sola un veredicto favorable.

### 7.3. Otro metal

Fe, Mg, Ca, Mn u otro metal seleccionan su adaptador M5 específico. Mientras el
adaptador no exista:

```text
scientific_status = BLOCKED_PROTOCOL_NOT_AVAILABLE
```

M4 puede ejecutarse únicamente como comparación exploratoria solicitada por el
investigador y debe quedar etiquetado como protocolo no especializado. Nunca es
un fallback silencioso.

---

## 8. Identificación del perfil

La selección requiere conjuntamente:

- familia normalizada `metalloenzyme`;
- Zn confirmado en el snapshot estructural y en el bolsillo relevante;
- identidad exacta del perfil por PDB y target;
- preparación compatible con la usada por el benchmark;
- versiones y hashes de los modelos requeridos.

Un warhead del ligando es una feature, no una condición suficiente para activar
M5. Si el receptor no contiene ni declara un centro metálico válido, el caso no
se convierte en metaloenzima por tener un carboxilato, tiol o sulfonamida.

---

## 9. Inconsistencias que bloquean el sellado

La política ya queda decidida, pero V1 no debe marcarse como alineada hasta
resolver:

1. `model-manifest.json`, `stacking_weights.json` y `scoring/engine.py`
   describen hoy políticas distintas;
2. `stacking_weights.json` con `clgnn=1.0` no reproduce ninguno de los tres
   perfiles autorizados;
3. `ace_m5_report_postfix.json` declara `p_value=0.5007` y
   `significant=false`, incompatibles con su propio intervalo positivo
   `[0.2005, 0.2783]` y con el reporte DeLong;
4. los scripts históricos no usan todos la misma variante de UMS;
5. faltan manifiestos por perfil que unan fórmula, constantes, modelos,
   checkpoint, SMARTS y hashes.

El reporte ACE debe regenerarse desde el script corregido. No se arregla
editando a mano el JSON.

---

## 10. Gates de aceptación

M5-Zn V1 se puede activar cuando:

1. los tres perfiles viven en un manifiesto legible por producción;
2. cada manifiesto contiene fórmula, constantes y hashes;
3. los scripts científicos y producción comparten la misma implementación de
   `UMS_warhead` y normalización;
4. golden tests reconstruyen las AUC y deltas esperados desde los checkpoints;
5. tests unitarios cubren alias, target exacto, componente ausente y fuera de
   dominio;
6. una corrida individual reproduce el mismo score independientemente de otras
   moléculas presentes;
7. el dossier separa señales crudas, score derivado, aplicabilidad y abstención;
8. el backend embebido ejecuta los mismos perfiles y manifiestos que los tests.

---

## 11. Consecuencia de producto

MolDesign podrá decir “M5-Zn” para cualquier sistema de zinc porque ésa es la
familia de preparación y auditoría que ejecutó. Sólo podrá mostrar un **score
M5-Zn validado** cuando el caso corresponda a uno de los perfiles exactos y
todos sus componentes estén disponibles.

Esta distinción permite que el pipeline evolucione hacia nuevos targets y
metales sin congelar el desarrollo, y evita presentar extrapolación como
validación.
