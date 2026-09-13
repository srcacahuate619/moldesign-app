# Corrigendum: el sitio de acoplamiento de los benchmarks M5-Zn

**Estado:** MMP9 con sitio incorrecto; ACE con sitio correcto y top-1 que no coordina
**Fecha:** 2026-09-04 · **corregido el mismo día** (ver §7)
**Afecta:** `M5_ZN_MMP9_1GKC_V1`, `M5_ZN_ACE_1O86_V1`
**Corrige:** `docs/75_DECISION_CIENTIFICA_M5_ZN_V1.md` §4.2 y §4.3
**Instrumentos:** `scripts/auditar_sitio_m5.py`, `scripts/auditar_coordinacion_zinc.py`
**Evidencia:** `data/molchamb_loto/auditoria_sitio_1gkc.json`,
`data/molchamb_loto/auditoria_sitio_1o86.json`,
`data/molchamb_loto/auditoria_coordinacion_1gkc.json`,
`data/molchamb_loto/auditoria_coordinacion_1o86.json`

> **Este documento se emitió con un error geométrico y se corrigió.** La primera
> versión invalidaba también ACE/1O86 apoyándose en un criterio equivocado. El
> §7 explica el error, y aquí no queda nada de aquella conclusión. Se conserva
> el registro porque un corrigendum que esconde su propio corrigendum no sirve
> de nada.

---

## 1. Qué se encontró

### 1.0. El criterio correcto

Una caja de Vina es un **cubo**. La pertenencia se comprueba eje a eje:

```text
|Δx| ≤ sx/2   ∧   |Δy| ≤ sy/2   ∧   |Δz| ≤ sz/2
```

La distancia euclídea al centro **no decide**: usarla equivale a comparar contra
la esfera inscrita en el cubo, que descarta todas las esquinas. Para una caja de
25 Å, el semilado es 12.5 Å pero el radio hasta una esquina es
√(12.5²·3) = **21.65 Å**.

El tamaño de 25 Å es un **supuesto declarado**: `benchmark_ef_vina.py` usa
`curated_box or 25` y ninguna de las tres dianas está en `curated_targets.csv`,
pero los logs del benchmark no registran la caja efectiva. Sólo se puede afirmar
*compatibilidad* con 25 Å.

### 1.1. MMP9 / 1GKC — sitio incorrecto, demostrado

Centro declarado (53.25, 22.51, 129.72), coincidente en dos fuentes
independientes (`benchmark_ef_vina.py` y `data/multitarget/mmp9/metadata.json`).

**Ningún zinc cae dentro de la caja**, por el criterio por eje:

| ion | Δx | Δy | Δz | dentro |
|---|---|---|---|---|
| ZN A1450 (catalítico) | +10.02 | +7.44 | **−17.34** | no |
| ZN A1451 | **+17.48** | −2.89 | **−18.05** | no |
| ZN B1451 | −11.98 | −4.67 | **+16.82** | no |
| ZN B1452 | −3.57 | **−13.62** | **+20.58** | no |
| **CA A1447 (calcio)** | +4.15 | +1.79 | +1.28 | **sí** |

El inhibidor cristalográfico **NFH A1448** tiene su centroide fuera
(Δ = +12.59, +8.20, −11.97) y **sólo 4 de sus 22 átomos dentro de la caja**.

Medido **átomo a átomo** —distancia del zinc al átomo donante N/O/S más cercano
de cada pose, no al centroide del ligando—:

```text
activos (los 50)   mínima 14.91 Å · mediana 16.99 Å · a ≤4.0 Å: 0
decoys  (n=1816)   mínima  8.44 Å · mediana 17.27 Å · a ≤4.0 Å: 0
```

Las poses sí llenaron la caja declarada —582 con todos sus átomos dentro, 55
asomando, ninguna fuera—, lo que respalda el supuesto de 25 Å. El problema no es
que las poses se salieran: es que **el zinc catalítico nunca estuvo dentro**, y
el único metal dentro es un ion de calcio a 4.7 Å del centro.

### 1.2. ACE / 1O86 — el sitio es correcto (y aun así falla; ver §8)

El centro declarado **es exactamente la coordenada de ZN A701** —idéntica en
`1O86_clean.pdb` y en el receptor acoplado `1O86.pdbqt`, sin traslación de
sistema—, así que el zinc está dentro de la caja por construcción.

Y las poses también:

| eje | límites de la caja | ocupación real por átomo |
|---|---|---|
| x | 31.32 – 56.32 | 30.5 – 45.3 |
| y | 25.74 – 50.74 | 29.9 – 51.7 |
| z | 34.21 – 59.21 | 48.8 – 60.3 |

**262 poses con todos sus átomos dentro, 428 asomando ~1 Å, ninguna fuera.** El
centroide medio de las poses queda a Δ = (−7.55, +6.78, +8.27): dentro por los
tres ejes.

**No hay incompatibilidad geométrica.** Lo que impide dar el benchmark por
bueno son tres huecos de procedencia:

1. **falta el complejo cristalográfico.** `1O86_clean.pdb` sólo conserva HOH,
   GLY, CL y ZN, así que el bolsillo del inhibidor no se puede usar como
   referencia independiente;
2. **la caja efectiva no está registrada** en ningún artefacto;
3. **la integridad del checkpoint tiene huecos**: 44 registros sin pose y 21 con
   pose y sin features.

Con esto solo, ACE quedaría en «procedencia incompleta». **El §8 lo cambia**:
medido sobre los 47 activos evaluables, ninguno acerca un donante al zinc, y eso
sí es un resultado sobre lo que el benchmark midió.

### 1.3. Integridad de los artefactos

```text
MMP9   38 registros sin pose ·  1 con pose y sin features
ACE    44 registros sin pose · 21 con pose y sin features
```

Es un problema de **integridad**, independiente de dónde se acopló. Rompe la
correspondencia uno a uno entre predicción y geometría, y por eso se informa —
pero no dice nada sobre el sitio, y la primera versión de este documento lo
usaba indebidamente como si lo dijera.

---

## 2. Qué componentes quedan afectados

| perfil | fórmula | dependiente de la pose | peso |
|---|---|---|---|
| `M5_ZN_MMP9_1GKC_V1` | 0.75·XGBoost + 0.25·UMS_warhead | XGBoost | **0.75** |
| `M5_ZN_ACE_1O86_V1` | 0.20·Vina_norm + 0.40·XGBoost + 0.40·UMS_warhead | Vina_norm, XGBoost | **0.60** |

Los checkpoints confirman que `xgb_score` se calcula sobre `features` de la
pose —descriptores shell/ECIF, huellas de interacción—. `Vina_norm` deriva del
score de acoplamiento. `UMS_warhead` es la única componente **no afectada**:
mira el SMILES del ligando.

CA2 / 3DC3 no entra en este corrigendum: su perfil ya no producía score por
ausencia de GNN-D, y su sitio **no se ha auditado todavía**.

---

## 3. Afirmaciones que se retiran

Para **MMP9**, se retiran:

1. que el AUC retrospectivo mida capacidad de acoplamiento metaloproteico;
2. que la mejora M5 sobre M4 sea evidencia de que la señal de metal aporta
   información estructural;
3. que el perfil esté validado sobre el sitio de unión de su inhibidor;
4. que `vina_reference_max = 8.247` sea el máximo de |Vina| en el sitio
   catalítico — es el máximo observado en la caja que se usó.

Para **ACE** se retira que su AUC sea evidencia de reconocimiento del metal
(§8): el sitio era correcto y ninguna pose puntuada de ningún activo coordina el
zinc. **No** se afirma que su caja fuera incorrecta — no lo era.

**No se retira** que los números sean reproducibles: la reconstrucción de las
AUC desde los checkpoints sigue siendo exacta a precisión de máquina
(`tests/test_m5_zn_perfiles.py`).

---

## 4. Hipótesis pendientes, que NO son conclusiones

Un AUC de 0.92 (MMP9) obtenido en un sitio que no es el catalítico exige
explicación, y aquí no se da ninguna por buena:

- que `UMS_warhead` —independiente de la pose— explique la mayor parte de la
  separación, siendo el conjunto de activos quelantes de zinc;
- que las features de la pose capturen tamaño y composición del ligando más que
  interacción específica;
- que el conjunto de decoys difiera de los activos en propiedades globales;
- que el sitio acoplado sea un bolsillo real con selectividad correlacionada.

**Ninguna está medida.** La ablación contra `UMS_warhead` solo, con intervalo
bootstrap del 95 %, es el experimento que las distingue, y está pendiente.

---

## 5. Qué se hace, y qué no

**Se hace:**

- MMP9 pasa a `REVIEW_INVALID_BENCHMARK_SITE`;
- ACE pasa a `REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING` (ver §8);
- ninguno produce `VALIDATED_PROFILE`;
- el manifiesto declara ambos estados y enlaza este documento;
- el dossier lo dice donde se lee.

**No se hace:**

- **no se recentra ninguna caja.** Generar una caja nueva produce otro número,
  no una corrección;
- **no se tocan los checkpoints ni los artefactos sellados.** Son la prueba;
- **no se reescriben las corridas históricas**, ni los commits ya emitidos.

---

## 6. Consecuencia sobre el estado de M5-Zn

```text
CA2  / 3DC3   NOT_EVALUATED_MISSING_COMPONENT
              No existe productor de GNN-D.
MMP9 / 1GKC   REVIEW_INVALID_BENCHMARK_SITE            sitio incorrecto demostrado
ACE  / 1O86   REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING
              Zn dentro y caja coherente, 0/47 top-1 coordinantes.
              No hay oráculo: se descartaron las demás poses.
```

Los tres estados dicen cosas distintas, y esa es la aportación del episodio:

    sitio demostrado incorrecto      MMP9   se midió, y está mal
    protocolo no verificable         —      no se puede comprobar (ACE lo fue
                                            hasta el §8, y dejó de serlo)
    top-1 que no coordina el metal   ACE    la caja era correcta, y lo que se
                                            puntuó no toca el metal
    componente no ejecutado          CA2    falta una pieza, no falló ninguna

Ninguno de los cuatro es «el modelo falló». Reducirlos todos a esa frase es lo
que impide saber qué arreglar.

Ningún perfil es hoy científicamente liberable. Lo que sí queda demostrado es
que **la maquinaria de ejecución, persistencia y abstención funciona**.

M5-Zn es **infraestructura operativa sin perfil positivo liberable**.

---

## 8. Ninguna pose top-1 de un activo coordina el zinc

Auditoría posterior sobre **todos** los activos, sin ejecutar docking nuevo
(`scripts/auditar_coordinacion_zinc.py`). Se mide la distancia del zinc al
átomo **donante** (N/O/S) más cercano de la pose puntuada:

| | activos evaluables | mínima | mediana | ≤4.0 Å |
|---|---|---|---|---|
| MMP9 / 1GKC | 50 / 50 | **14.91 Å** | 16.99 | **0** |
| ACE / 1O86 | 47 / 50 | **6.13 Å** | 11.04 | **0** |

En MMP9 era lo esperable: el zinc está fuera de la caja.

**En ACE no.** Ahí el zinc es el centro exacto de la caja y las poses caen
dentro, y aun así **ninguna pose top-1 de un activo acerca un donante al
metal**. Los inhibidores de ACE del tipo lisinopril quelan zinc: si lo que se
puntuó hubiera reproducido su modo de unión, se vería.

Esas top-1 son **las que produjeron las features y sostienen el AUC**, así que
ese AUC no es evidencia de reconocimiento del metal.

Por eso ACE pasa de `REVIEW_BENCHMARK_PROVENANCE_INCOMPLETE` a
`REVIEW_BENCHMARK_TOP1_NOT_METAL_COORDINATING`.

**El nombre del estado dice TOP1 a propósito.** Un estado como «el benchmark no
probó el metal» afirmaría que la búsqueda nunca exploró la coordinación, y eso
**no se puede saber**: el checkpoint descartó las poses alternativas (§8.1).
Los hechos demostrados son cuatro, y ninguno más:

1. el Zn estaba dentro de la caja;
2. ninguna de las 47 poses top-1 evaluables de los activos tiene un donante
   N/O/S a ≤4 Å;
3. esas poses son las que produjeron las features y sostienen el AUC;
4. **se desconoce** si alguna pose descartada sí coordinaba.

Convertir el cuarto punto en «el muestreo falló» sería transformar un oráculo
ausente en un resultado.

### 8.1. El ensemble no se guardó, así que no hay oráculo

Cada registro conserva **un solo `MODEL`**: el checkpoint guardó la pose top-1 y
descartó el resto. No se puede distinguir «el ligando nunca alcanza el zinc» de
«lo alcanza en otra pose y el scoring eligió mal», y por eso el oráculo se
declara ausente en vez de simularse.

Para lo que aquí importa la distinción es menor: las `features` y las
predicciones se calcularon **sobre la pose top-1**, así que top-1 es la única
pose que entró en el AUC. Lo que otras poses hubieran hecho no cambia qué midió
el benchmark — sólo cambiaría el diagnóstico sobre el muestreo de Vina, que es
otra pregunta.

### 8.2. Registros perdidos, por clase

| | total | sin pose | con pose sin features | completos |
|---|---|---|---|---|
| MMP9 activos | 50 | 0 | 0 | **50** |
| MMP9 decoys | 1973 | 95 | 3 | 1875 |
| ACE activos | 50 | 3 | 1 | 46 |
| ACE decoys | 2152 | 127 | 68 | 1957 |

En **ACE** la pérdida es proporcionalmente pareja (6.0 % de activos frente a
5.9 % de decoys): no está sesgada por clase. En **MMP9** se concentra
enteramente en los decoys —ningún activo se perdió—, lo que sí es un sesgo,
aunque favorable a la clase mayoritaria.

### 8.3. El AUC, y un análisis de sensibilidad

Recalculado desde predicciones y etiquetas crudas, con una implementación de
Mann-Whitney independiente de la cadena auditada:

| | AUC (casos completos) | n | límite inferior ITT adverso | n |
|---|---|---|---|---|
| MMP9 | **0.9208** | 1925 | 0.8750 | 2023 |
| ACE | **0.6708** | 2003 | 0.5612 | 2202 |

Los dos valores de casos completos **reproducen exactamente** los publicados en
`delong_paired_report.json` (0.9207733333 y 0.6707693675), lo que confirma que
la recomputación mira los mismos datos.

La segunda columna **no es un AUC corregido y no estima qué habrían puntuado los
ausentes.** Es un análisis de sensibilidad: imputa a cada registro perdido el
peor valor posible de su clase —0.0 a un activo, 1.0 a un decoy—, que es el
escenario más adverso concebible, y por tanto da un **límite inferior** bajo esa
imputación.

Lo que mide es fragilidad. MMP9 aguanta el escenario adverso; ACE baja hasta
0.5612. La pérdida de ACE **no está sesgada por clase** (§8.2), así que ese
descenso no indica un sesgo: indica que un AUC de 0.67 apoyado en 2003 registros
completos es sensible a qué se suponga de los ~200 que faltan.

---

## 7. El error de la primera versión de este corrigendum

La primera versión, emitida el 2026-09-04, invalidaba **también ACE** con este
razonamiento: «el 75.8 % de las poses cae fuera del semilado de 12.5 Å y su
centroide está a 13.14 Å del metal, lo que es geométricamente incompatible con
la configuración declarada».

Era falso. El auditor comparaba la **distancia euclídea** al centro contra el
semilado del cubo:

```python
math.dist(punto, centro) > 12.5     # MAL: eso es la esfera inscrita
```

Con el criterio correcto —por eje— el centroide medio de ACE queda a
(−7.55, +6.78, +8.27): **dentro por los tres**. El «75.8 % fuera» era el
porcentaje de poses situadas en las esquinas del volumen cúbico, todas válidas.

Se corrigieron además tres inferencias que el instrumento no sostenía:

1. llamar `centro_reconstruido` al promedio de la nube de poses. **El promedio
   de una nube de poses no reconstruye el centro de la caja**: las poses se
   acumulan donde el scoring encuentra mínimos, no uniformemente. Ahora se llama
   `centroide_medio_de_poses` y lleva su advertencia;
2. medir la cercanía al zinc con el **centroide** del ligando. La coordinación
   se mide del metal al átomo **donante** más cercano (N/O/S), por pose y
   estratificando activos y decoys — exigirle quelación a un decoy no tiene
   sentido. Los «8.75 Å» de la primera versión eran centroide-a-metal;
3. usar los registros incompletos como prueba de sitio incorrecto. Es un
   problema de integridad y se informa aparte.

**MMP9 sobrevive a la corrección**, y con evidencia más fuerte: su zinc está
fuera *por el eje Z*, su inhibidor tiene 4 de 22 átomos dentro y la distancia
donante–zinc de los activos es de 15.99 Å medida átomo a átomo.

**La lección de método.** Las 1971 pruebas del backend estaban en verde cuando
se emitió la primera versión: el código cumplía exactamente el criterio
programado, y el criterio programado era matemáticamente incorrecto. Una suite
verde acredita consistencia con lo que se le pidió comprobar, nunca que lo
pedido fuera lo correcto. Por eso el instrumento —y no sólo su resultado— tiene
que poder revisarse: `scripts/auditar_sitio_m5.py` documenta hoy su criterio en
la salida (`"criterio"`), para que la próxima revisión empiece por ahí.

**No se ejecutó la auditoría sobre los otros checkpoints con la versión
defectuosa.** Con ella habría producido falsos positivos sistemáticos para
cualquier pose situada en las esquinas del volumen cúbico.
