# RC-F0-SYM — La cobertura aguanta; el 21% de la clase positiva de train estaba mal etiquetada

**Tipo: medición.** Relectura del material que `RC-F0-V2` usó para construir el
conjunto v2, con la métrica corregida de la §5.1 del doc. 49. Sin cómputo nuevo, sin
entrenar ni evaluar ningún selector. La cobertura del oráculo es una propiedad del
**generador**, que es exactamente lo que `RC-F0-V2` ya publicó para los tres splits.

## Verificación de validez

32,215 poses de fuente `molflex` emparejadas al material por `(pid, file_stem,
model_idx)`. El RMSD **ingenuo** recomputado reproduce el `rmsd` almacenado en
`poses_{split}.jsonl` con error máximo de **0.0005 Å** en los tres splits — el
redondeo a tres decimales del fichero. 203 de 203 complejos, cero errores.

## Resultado 1: la cobertura del oráculo no se mueve

| Split | Complejos | Cobertura ingenua | Cobertura corregida | Complejos que ganan |
|---|---:|---:|---:|---:|
| train | 116 | 79.31% (92) | **79.31% (92)** | **0** |
| val | 40 | 87.50% (35) | **87.50% (35)** | **0** |
| test | 47 | 97.87% (46) | **97.87% (46)** | **0** |

**Ni un solo complejo cambia de estado en ninguno de los tres splits.** 120 poses
individuales cruzan el umbral al corregir (0.372% de 32,215), pero siempre en
complejos que **ya tenían** una pose mejor. El defecto de simetría no toca la métrica
sobre la que descansa todo el programa.

Consecuencias directas, y son tranquilizadoras:

- **Las cifras de `RC-F0-V2` se sostienen exactamente**: 79.3 / 87.5 / 97.9.
- **El denominador de `RS-14` es correcto**: los 92 complejos cubiertos de train son 92.
- **La tabla de factibilidad de la §9** —la que decide si el gate confirmatorio de
  `>=0.70` es aritméticamente posible— no cambia.

Esto **acota el daño** del defecto encontrado en la auditoría de `MF-10`: a nivel de
cobertura de complejo sobre el conjunto v2, es inocuo.

## Resultado 2: a nivel de pose, las etiquetas sí están mal

La etiqueta del conjunto v2 es `rmsd <= 2.0 Å` → positiva, y se calculó con la métrica
ingenua. Corregida:

| Split | Poses positivas ingenuas | Corregidas | Cambio |
|---|---:|---:|---:|
| train | 357 | **432** | **+21.0%** |
| val | 187 | 196 | +4.8% |
| test | 216 | **252** | **+16.7%** |

**Una de cada cinco poses positivas de train estaba etiquetada como negativa.** Para
un clasificador que aprende a distinguir la pose correcta de sus vecinas, eso no es
ruido de fondo: es una fracción sustancial de la señal, y está sistemáticamente
sesgada hacia los ligandos simétricos.

Y **la tasa de corrupción difiere por split** —21.0% en train, 4.8% en val, 16.7% en
test—, de modo que el selector se entrenó y se evaluó con etiquetas corrompidas en
proporciones distintas.

## Dónde se concentra el sesgo

| Split | Complejo | Sesgo máximo | Poses que cruzan | Automorfismos | Oráculo |
|---|---|---:|---:|---:|---|
| train | `1kav` | **10.710 Å** | 3 | 128 | 1.971 → 1.728 |
| train | `1h22` | 10.086 Å | 0 | 2 | 3.267 → 3.060 |
| train | `1bq4` | 4.599 Å | 16 | 12 | 1.506 → 1.297 |
| train | `1a99` | 3.964 Å | 10 | 2 | 0.362 → 0.334 |
| val | `1ajx` | 3.797 Å | 0 | 32 | 5.193 → 4.543 |

Complejos donde el oráculo baja más de 0.9 Å sin cambiar de cobertura: `1l83`
(2.106 → 0.498), `1h4w` (1.632 → 0.302), `184l` (1.470 → 0.345), `1g48`
(1.419 → 0.491), `1lcp` (1.227 → 0.324), `1c5p` (1.229 → 0.327). Todos ya estaban
cubiertos: la corrección mejora una pose que ya bastaba.

## Consecuencia para la cartera D: hay un `RS-14-R1` legítimo

`RS-14` selló **NO_GO** con precisión condicional 0.4312 frente a 0.4783 del baseline,
CI95 [−0.1522, +0.0617]. Ese experimento:

- **entrenó** con el 21% de sus positivas de train marcadas como negativas;
- **evaluó** contra un baseline que `MF-09-SYM` mostró subestimado.

Los dos efectos van en direcciones opuestas y **no se puede predecir el neto sin
medirlo**. Decirlo al revés sería inventar el resultado.

Lo relevante es el encaje con la §19.1: su condición 2 dice que un `NO_GO` no cuenta
para la futilidad si **se explica por un defecto de implementación ya corregido**, y
que un corrigendum reinicia el contador **sólo si cambia la decisión**. Corregir las
etiquetas es exactamente eso: una corrección de defecto, no una arquitectura nueva ni
una seed nueva. **`RS-14-R1` con etiquetas corregidas es preregistrable sin violar la
regla de futilidad**, y su prerregistro debe declarar por adelantado que un NO_GO
repetido cierra la línea de forma definitiva.

Lo que **no** cambia: el límite de potencia. Con 92 complejos cubiertos el diseño
sigue sin poder resolver diferencias menores a ~10 puntos, y eso no lo arregla ninguna
etiqueta. `RS-14-R1` sólo tiene sentido como corrección de defecto, no como intento de
ganar el gate por otra vía.

## Alcance y honestidad del número

Sólo el 94% de las poses (las de fuente `molflex`) son recomputables; las de
`flexible_redock` y `ruta_a` conservan su RMSD ingenuo. Como corregir simetría sólo
puede **bajar** el RMSD, la cobertura corregida reportada es una **cota inferior**: el
6% restante sólo podría añadir cobertura, nunca quitarla. El hallazgo «la cobertura no
cambia» es por tanto conservador en la dirección correcta, y el de las etiquetas
(+21%) es también una cota inferior.

## Qué NO hace este análisis

- **No reabre `RC-F0-V2`** ni recalcula su sello: es una relectura con registro propio.
- **No re-etiqueta el conjunto v2.** Hacerlo exige su propio prerregistro, y es
  precisamente el contenido de un eventual `RS-14-R1`.
- **No evalúa ningún selector**, así que no consume la lectura única de `val`.

## Archivos

- `metrics.json` — cobertura por split bajo ambas métricas, verificación de reproducción y alcance declarado.
- `per_complex.jsonl` (203) — por complejo: oráculo bajo ambas métricas, automorfismos, sesgo mediano y máximo, poses que cruzan, positivas antes y después.
- `scripts/analisis_simetria_v2.py`.
