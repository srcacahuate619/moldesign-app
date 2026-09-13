# 51 — Política de aguas del receptor

**Estado: DECLARADA el 2026-08-20.** Antes de esta fecha el pipeline tenía un
comportamiento, no una política: nadie lo había decidido ni escrito. Este documento no lo
cambia — lo declara, mide sus consecuencias y fija qué evidencia haría falta para cambiarlo.

**Puesta a prueba el 2026-08-22 por `REC-11`, el experimento que el §5 pedía: la política
se mantiene, y ahora se sabe con qué resolución.** Sobre los 116 de train y en docking de
novo, quitar todas las aguas da 96/116 de cobertura del oráculo contra 94/116
conservándolas — `b`=10, `c`=8, McNemar exacto p=0.814529, `SIN_DIFERENCIA_DETECTABLE`.
**No es equivalencia**: el MDE del diseño es de 9.92 pp. Ver §5.

---

## 1. Qué hace el pipeline hoy

**Conserva todas las aguas cristalográficas del PDB de origen en `rec.pdbqt`.** Todas: las
que median puentes de hidrógeno con el ligando, las de la segunda esfera, las de la
superficie, y las que el ligando desplaza al unirse.

Está medido, no supuesto. `REC-08-EXT` comparó el original contra el preparado en 116
complejos de train:

| | |
|---|---:|
| Complejos con agua en el sitio (≤8 Å del ligando) | 111 de 116 |
| Aguas del sitio en el original | 1788 |
| Aguas del sitio conservadas en `rec.pdbqt` | **1788** |
| Perdidas | **0** |

Lo mismo con los metales: 42 de 42 conservados, 0 perdidos.

## 2. Por qué es una decisión y no un detalle

Conservarlas **tiene consecuencia medida sobre la función de puntuación**. `REC-09` puntuó
el ligando cristalográfico contra su propio receptor, con y sin las aguas que chocan con él
—criterio geométrico, `d_clash = 2.6 Å`, heredado del prerregistro de `MF-28`—:

| | |
|---|---:|
| Complejos con al menos un agua bloqueante | **26 de 116** |
| Δ mediano al quitarlas, en complejos sanos | **0.000** kcal/mol |
| Δ máximo en complejos sanos | 4.008 |
| Complejos sanos que se mueven más de 0.5 | 11 de 110 |

Y el caso que lo hace innegable: **`1fkh` pasa de +2.550 a −10.369 kcal/mol al quitar dos
moléculas de agua.** 12.919 kcal/mol de artefacto producidos por dos aguas que el ligando
cristalizado desplaza y el pipeline conservó. `MF-13` había nombrado a `1fkh` como «sistema
mal montado» sin saber por qué; era esto.

`MF-33-CRUCES` lo conecta con el resto: de los 7 complejos que el ensemble flexible de
`MF-33` no convierte, **4 son cristales que puntúan absurdamente mal** — 57.1% frente al
4.9% entre los 41 que sí convierte.

## 3. La política declarada

> **Se conservan todas las aguas cristalográficas del receptor, sin excepción, en todos los
> artefactos del programa.** No se eliminan, no se filtran por B-factor ni por ocupancia, y
> no se decide por complejo.

**Se declara tal cual, sin cambiarla**, por tres razones:

1. **Cambiarla invalidaría el registro.** 111 artefactos sellados consumen receptores
   preparados con esta regla. Un cambio de comportamiento obliga a regenerar y volver a
   sellar, y eso es un programa, no una corrección.
2. **La evidencia disponible mide una cosa y la política gobierna otra.** `REC-09` mide el
   efecto de las aguas sobre el **scoring del cristal en su sitio**. La política gobierna
   sobre todo el **docking de novo**, donde la pose no se conoce de antemano y no se puede
   saber qué agua estorbaría. No hay medición de ese caso.
3. **El criterio geométrico no distingue lo que hay que distinguir.** Un agua que el ligando
   desplaza y una estructural que media un puente de hidrógeno están a la misma distancia.
   Quitar la segunda empeora el modelo aunque mejore el número.

## 4. Consecuencia operativa, desde hoy

La política es explícita, así que sus efectos dejan de ser sorpresas y pasan a ser
limitaciones declarables:

- **Todo artefacto que puntúe una pose cristalográfica debe declarar** que el receptor
  conserva las aguas, y que un score anómalamente malo puede ser el bloqueo y no la función.
  `REC-09` da la lista de los 26 afectados.
- **Un cristal que puntúa por encima de −3.0 kcal/mol no es evidencia contra la función de
  puntuación** mientras no se compruebe el bloqueo. Ese umbral viene de la lectura sellada
  de `MF-13`.
- Los complejos `1fkh` y `1eld` quedan **explicados**: su anomalía era bloqueo por agua.
  `1afl` y `1ew8` tienen aguas bloqueantes de efecto pequeño y siguen sin explicar. `1d7i`
  y `1ew9` **no tienen ninguna** y su anomalía es otra cosa.

## 5. Qué la cambiaría

Un solo experimento, y está sin diseñar:

> Medir el efecto de las aguas sobre el **docking de novo**, no sobre el scoring del
> cristal. Dos brazos sobre la misma cohorte —receptor con todas las aguas contra receptor
> sin ellas—, misma semilla y presupuesto, midiendo cobertura del oráculo y RMSD del top-1.

Si el brazo sin aguas convierte más complejos, la política cambia y el coste de regenerar
está justificado. Si no, esta declaración se confirma y el asunto queda cerrado.

**Lo que no la cambia:** más casos como `1fkh`. Ya están medidos y no deciden sobre docking
de novo.

### 5bis. Respondido el 2026-08-22 — y esta sección ofrecía una opción de menos

> **Esta sección no se reescribe: describió correctamente el experimento que hacía falta, y
> se ejecutó tal cual.** Lo que hay que corregir es su desenlace binario.

`REC-11` hizo exactamente lo que el §5 pedía —dos brazos, misma cohorte de 116, mismo
ligando `conf0.flex.pdbqt`, mismas cinco semillas, `exh`=8, receptor como única variable— y
midió 61.27 CPU-h:

| Brazo | Cobertura del oráculo | |
|---|---:|---:|
| CON aguas — la política | 94 / 116 | 0.8103 |
| SIN aguas — receptor seco | 96 / 116 | 0.8276 |

`b`=10, `c`=8, 18 discordantes, **McNemar exacto p = 0.814529**. Lectura preregistrada:
**`SIN_DIFERENCIA_DETECTABLE`**. Decisión del artefacto: `INCONCLUSIVE`.

**El párrafo de arriba planteaba dos desenlaces —«la política cambia» o «esta declaración se
confirma y el asunto queda cerrado»— y el que ocurrió es un tercero.** El prerregistro
`REC-11-PRE` sí lo escribió antes de correr, y es el que manda: la política **se mantiene
por inercia**, no confirmada, con el límite de potencia declarado. Con este `n` el diseño no
resuelve diferencias menores a **9.92 pp**, unos 13 complejos netos. Leer este resultado
como equivalencia está **prohibido** por el prerregistro, y el asunto **no queda cerrado**:
queda acotado.

Dos consecuencias operativas:

- **La política sigue sin estar confirmada positivamente.** Ésa era la rama (2) del gate de
  `REC-11` y no salió. `docs/51` continúa siendo una declaración con consecuencias medidas,
  no una regla validada.
- **`1fkh` aparece en la columna de «quitarlas gana»** también en de novo: 5.131 Å con aguas
  contra 1.914 Å sin ellas. Sigue siendo **un caso**, exactamente como dice el párrafo
  anterior, y sigue sin decidir la política.

Lo que abriría el asunto de nuevo no es repetir esto con más complejos, sino lo que `REC-11`
declaró fuera de alcance: las **políticas intermedias** —filtrar por B-factor, ocupancia o
enterramiento— y un diseño con **ensemble conformacional**, ya que `REC-11` mide a
confórmero igualado y `MF-33` midió que un solo confórmero convierte 12 de 33 contra 26.

Lectura completa en `scripts/artifacts_science/REC-11/LECTURA.md`.

## 6. Procedencia

| Artefacto | Qué aporta | Decisión |
|---|---|---|
| `REC-08` | El preparado no pierde cadenas del sitio | GO |
| `REC-08-EXT` | No pierde metales (42/42) ni aguas (1788/1788); destapa que la política no existía | GO |
| `REC-09` | 26 de 116 con agua bloqueante; `1fkh` +2.550 → −10.369; control limpio en los sanos | INCONCLUSIVE (`MIXTO`, f = 0.3333) |
| `MF-13` | Nombra `1fkh` y `1ew8` como sistemas mal montados; aporta el umbral de −3.0 | INCONCLUSIVE |
| `MF-33-CRUCES` | 4 de los 7 que el ensemble no convierte son cristales absurdos | GO |
| `REC-11` | **La medición que el §5 pedía**: en docking de novo, quitarlas todas da 96/116 contra 94/116, `b`=10 `c`=8, p=0.814529, MDE 9.92 pp | INCONCLUSIVE (`SIN_DIFERENCIA_DETECTABLE`) |
