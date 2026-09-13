# MF-02B — El tercio sin cobertura no era un fallo del método: era que no se había ejecutado

## Decisión: GO — los cinco gates pasan

| Gate | Criterio | Resultado |
|---|---|---|
| G1 validez | ≥95% de corridas completan | **100%** (50/50) |
| G2 **recuperación** | `A8` entrega pose ≤2 Å en ≥10 de los 38 | **30 de 38** |
| G3 no regresión | la unión no reduce la cobertura de ningún complejo | PASS — 0 pérdidas |
| G4 determinismo | misma semilla → mismo RMSD y mismo score | PASS — 2/2 idénticos |
| G5 coste | descriptivo, sin umbral | mediana 344 s/complejo |

## El número

**La cobertura del oráculo de train pasa de 67.2% a 93.1%** (78/116 → 108/116) ejecutando el pipeline MolFlex **congelado**, sin cambiar un solo parámetro: mismo ensemble de 30 confórmeros, misma caja de 25 Å, `exhaustiveness=8`, semillas 42.

En los 38 complejos sin cobertura, el mejor RMSD entregado baja de una mediana de **4.234 Å a 1.433 Å**; la mejora mediana es de **2.56 Å** y la máxima de 8.92 Å.

De los 32 complejos que **no tenían ninguna pose de MolFlex** en el conjunto sellado, se recuperan **27**.

## Qué significa, dicho sin adornos

El conjunto de poses sobre el que se evaluaron **RS-01, RS-04-OOF y RS-08** se construyó sin la salida de MolFlex en el 89% de los complejos. En 38 de 116 no existía pose que seleccionar, y esos experimentos midieron Top-1 **global**, es decir, se evaluaron sobre un universo del que un tercio era inganable por construcción.

No es que el selector fallara en esos 38: es que no había nada que elegir.

Esto no reabre esos experimentos —cada uno tiene su gate sellado y su decisión— pero sí cambia el denominador sobre el que cualquier experimento futuro de selección debe evaluarse, que es exactamente lo que la §19.1 exige para reabrir una cartera: **que cambie el denominador**.

## Lo que este experimento NO dice

**Añadir una fuente a una unión solo puede subir la cobertura del oráculo.** Que suba no es el hallazgo, y así quedó declarado en el prerregistro antes de ejecutar. El hallazgo es **cuánto** sube (26 puntos), **a qué coste** (11 h de CPU para los 116, ~1 h de reloj con 10 procesos) y, sobre todo, **que la fuente no estaba**.

Tampoco dice nada sobre el selector: la precisión condicional era 61.5% en train y 61.0% en test antes de esto, y sigue siendo desconocida sobre el conjunto ampliado hasta que se reconstruya y se re-evalúe. Eso exige su propio prerregistro.

## Los 8 que no se recuperaron son casi-aciertos

| pid | entregado | ensemble mín. | dataset |
|---|---:|---:|---:|
| `1apv` | 2.199 Å | 1.833 | 4.067 |
| `1jq8` | 2.207 Å | 1.872 | 3.657 |
| `1fkh` | 2.559 Å | 1.253 | 5.284 |
| `1elb` | 2.621 Å | **2.576** | 7.161 |
| `1d9i` | 2.683 Å | 1.695 | 2.620 |
| `10gs` | 2.739 Å | 1.470 | 5.951 |
| `1aaq` | 2.782 Å | 2.190 | 3.795 |
| `1a4w` | 3.135 Å | **4.446** | 4.208 |

Ninguno falla por goleada: todos caen entre 2.2 y 3.1 Å, contra un umbral de 2.0. Y todos **mejoran** respecto al conjunto sellado. Dos de ellos —`1a4w` y `1elb`— ya estaban señalados por MF-02A como techo conformacional duro: su ensemble nunca contiene la conformación bioactiva (4.446 y 2.576 Å), así que ningún presupuesto de búsqueda los arregla. Los otros seis tienen la conformación disponible y son fallo de colocación: el material está, la búsqueda no lo coloca.

## El control confirma que no se rompe nada

En los 12 complejos ya cubiertos: `A8` entrega pose ≤2 Å en 9, **mejora el mejor RMSD en 7 de 12** (mediana 0.952 → 0.668 Å) y **no pierde cobertura en ninguno**. La fuente se **añade** a la unión, no la sustituye — que es lo que G3 verificaba.

## Coste

Mediana **344 s por complejo** con `cpu=1` (19,021 s de CPU para 50 complejos). Reconstruir el conjunto completo de 116 costaría **~11 h de CPU**, aproximadamente **1.1 h de reloj** con 10 procesos. Es barato para lo que cambia.

## Consecuencia para el programa

1. **Antes de volver a evaluar ningún selector hay que reconstruir el conjunto de poses** aplicando MolFlex a los 116 (y al resto de las particiones bajo su propio prerregistro, cuidando la cuarentena de `D-RC-CONFIRM`).
2. La descomposición `Top-1 = cobertura × precisión condicional` deja de ser teórica: con cobertura al 93.1% y precisión condicional histórica de ~61%, el Top-1 alcanzable pasa de 67.2% a 93.1% de techo. Cuánto de eso se convierte en Top-1 real depende del selector, y **eso todavía no se ha medido**.
3. El eje conformacional está agotado (MF-02A): la palanca era la aplicación del generador, no su parametrización.

## Archivos

- `PREREGISTRO.md` (en `MF-02-PRE`, sellado antes de ejecutar) — descomposición declarada, techo conformacional de MF-02A y la calibración de `1nki`.
- `metrics.json` — gates, cobertura antes/después, coste y determinismo.
- `per_complex.jsonl` (50) — por complejo: RMSD entregado, éxito, ensemble mínimo, mejor del dataset, fuentes del dataset y mejor de la unión.
- `corridas.jsonl` (50) — una línea por corrida de MolFlex. Las 2 repeticiones de determinismo se registran en `metrics.json`, no aquí.
- `scripts/run_mf02b_apply_molflex.py`, `scripts/molflex.py`.
