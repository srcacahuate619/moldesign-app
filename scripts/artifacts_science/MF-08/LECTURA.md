# MF-08 — El mecanismo es real; la magnitud, un orden por debajo de lo necesario

## Decisión: NO_GO

| Gate | Criterio | Resultado |
|---|---|---|
| G1 validez | ≥95% de las 144 corridas | PASS — 144/144 |
| G2 **recuperación** | `B_ADAPT` recupera ≥7 de los 33 | **FAIL — 3** |
| G3 monotonía | `B_ADAPT` ≥ `B20` ≥ `B25` ≥ `B30` | **FAIL** (ver §3: en parte artefactual) |
| G4 no regresión | `B_ADAPT` pierde ≤1 del control | PASS — **0 pérdidas** |

## Los números

| Brazo | Margen de deslizamiento | Cohorte (33) | Mediana del oráculo | Control (15) | Coste mediano |
|---|---:|---:|---:|---:|---:|
| `B_ADAPT` (~18.2 Å) | 2.83 Å | **3/33** | **3.18 Å** | 15/15 | 425 s |
| `B20` | 3.62 Å | 1/33 | 3.224 Å | 15/15 | 399 s |
| `B25` (actual) | 6.12 Å | 0/33 | 3.746 Å | 15/15 | — |
| `B30` | 8.6 Å | 1/33 | 4.004 Å | 15/15 | 554 s |

Recuperados por `B_ADAPT`: `1d7i`, `1ew9`, `1l83`.

La predicción declarada antes de ejecutar era que la caja adaptativa dejaría el subsitio fuera en **21 de 33**. Cruzaron el umbral **3**. Excluir el decoy era necesario pero no suficiente, y así estaba dicho — pero el margen entre lo abordable y lo convertido es mucho mayor de lo que anticipé.

## Un defecto de diseño que debo declarar

**La cohorte se definió como los complejos que fallan bajo `B25`.** Por tanto `B25 = 0/33` **es tautológico**: no es una medición, es la definición de la cohorte. Su mediana (3.746 Å) también está condicionada a ser >2.0 Å.

Eso invalida parcialmente G3: la cadena de monotonía incluye un punto fijo por construcción. Debí excluir `B25` del gate o declarar la cohorte sobre un criterio independiente del brazo de referencia. No lo vi al preregistrar.

**La decisión NO_GO no depende de ese defecto**: G2 falla por sí solo (3 frente a 7 exigidos) y G2 no tiene sesgo de selección — cuenta recuperaciones sobre una cohorte difícil por construcción, que es lo que se quería.

## El resultado limpio, sobre los tres brazos no usados para seleccionar

Comparando solo `B_ADAPT`, `B20` y `B30` —ninguno intervino en definir la cohorte— la **mediana del oráculo es monótona en el margen de deslizamiento**:

| Margen | 2.83 Å | 3.62 Å | 8.6 Å |
|---|---:|---:|---:|
| Mediana | **3.18** | 3.224 | 4.004 |

**El mecanismo existe y va en la dirección predicha**: apretar la caja acerca las poses. De `B30` a `B_ADAPT` la mediana mejora **0.82 Å**.

**Y es insuficiente por un orden de magnitud.** Esas poses están a 3.18 Å y necesitan bajar de 2.0: falta **~1.2 Å más** de los que todo el rango de caja disponible puede dar. No hay caja más pequeña que probar — `B_ADAPT` ya es el mínimo que contiene al ligando con margen de solvatación, y por debajo se recortaría la pose nativa.

## Dos cosas que sí sirven para producción

**Apretar la caja no rompe nada**: `15/15` del control en los cuatro brazos, incluido el más estrecho. Cero regresión.

**Y es más barato**: 425 s (`B_ADAPT`) frente a 554 s (`B30`), un 23% menos por complejo, porque el espacio de búsqueda es menor. Con la advertencia de siempre: la caja está centrada en el ligando cristalográfico, y `REC-03` midió el top-1 de MolPocket a **8 Å de mediana** del ligando. Con ese error de centro una caja ajustada perdería la pose nativa; el ahorro solo es cobrable si antes se resuelve la precisión del centro.

## Consecuencia para el programa

El fallo de colocación **no es «espacio para deslizarse»**. Restringir el volumen de búsqueda acerca las poses medio angstrom y no convierte. Queda en pie la otra vía sobre la misma cohorte: **`MF-02F`**, que da más intentos en vez de menos espacio. Si tampoco convierte, la conclusión será que el motor de docking no encuentra estas poses con ningún presupuesto razonable, y el problema se traslada a la función de puntuación o al muestreo, no a la geometría de la caja.

## Archivos

- `PREREGISTRO.md` (en `MF-08-PRE-R1`, sellado antes de ejecutar) — hipótesis, predicción de 21/33, criterio físico de exclusión y advertencia de transferencia.
- `metrics.json` — gates, cobertura y mediana por brazo y estrato, coste.
- `corridas.jsonl` (144) — una línea por corrida: brazo, caja efectiva, oráculo en marco de pocket, poses dockeadas.
- `cohorte.json` — los 33 dominados por colocación, los 15 de control, los 4 excluidos a priori y la predicción declarada.
