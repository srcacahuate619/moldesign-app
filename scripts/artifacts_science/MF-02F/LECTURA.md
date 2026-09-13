# MF-02F — Pasa el gate por el mínimo exacto, y el dosis-respuesta no acompaña

## Decisión: GO

| Gate | Criterio | Resultado |
|---|---|---|
| G1 validez | ≥95% de los 48 complejos | PASS — 48/48 |
| G2 **recuperación** | `K90` recupera ≥3 de los 33 sobre lo que ya daba `K30` | **PASS — exactamente 3** |
| G3 saturación | informativo | no satura en K60: `K60`→`K90` añade 3 |
| G5 anidamiento | el ensemble K30 es prefijo exacto del K90 | PASS — 0 complejos no anidan |

## Los números

| Brazo | Confórmeros efectivos | Recupera | Mediana del oráculo | Control |
|---|---:|---:|---:|---:|
| `K30` | 29 | 0/33 | 3.746 Å | 15/15 |
| `K60` | 58 | 0/33 | 3.664 Å | 15/15 |
| `K90` | 86 | **3/33** | **2.961 Å** | 15/15 |

Recuperados: `1ela`, `1fkg`, `1mu8`. Coste mediano 601 s por complejo, ~2× el de `K30`.

## Tres advertencias sobre este GO

**1. Pasa por el mínimo exacto.** El gate pedía ≥3 y salieron 3. No hay margen: un solo complejo menos y sería NO_GO. Con n=3 sobre 33, el intervalo de confianza de esa tasa es enorme y no soporta ninguna afirmación de tamaño de efecto.

**2. `K30 = 0/33` es tautológico.** La cohorte se definió como los complejos que fallan con la configuración base, que es `K30`. No es una medición: es la definición. Mismo defecto que en MF-08 —lo arrastré al reutilizar la cohorte— y se declara igual.

**3. El dosis-respuesta no es suave.** Duplicar de 29 a 58 confórmeros no recuperó **nada** y movió la mediana 0.08 Å. Pasar de 58 a 86 recuperó 3 y movió la mediana 0.70 Å. Un mecanismo de «más reinicios, más probabilidad de acertar» debería producir una curva razonablemente regular; ésta es plana y luego salta. Con estos n no se puede distinguir entre un mecanismo real con umbral y ruido de muestreo.

## El hallazgo que sí es informativo: los conjuntos no se solapan

`MF-08` (caja adaptativa) y `MF-02F` (más reinicios) atacaron **la misma cohorte** por vías ortogonales y **cada uno recuperó exactamente 3**, sin ningún complejo en común:

| Experimento | Recuperados |
|---|---|
| `MF-08` `B_ADAPT` | `1d7i`, `1ew9`, `1l83` |
| `MF-02F` `K90` | `1ela`, `1fkg`, `1mu8` |
| Intersección | **vacía** |

Es tentador leer complementariedad y sumar a 6 de 33. **No se puede, por dos razones.**

La primera es que el prerregistro lo prohíbe explícitamente: combinar ejes exige su propio experimento.

La segunda es aritmética y más contundente: **la probabilidad de que dos conjuntos de 3 extraídos de 33 sean disjuntos por puro azar es 0.744**. Tres de cada cuatro veces saldrían disjuntos aunque no hubiera ninguna complementariedad. El solapamiento vacío es **el resultado esperado bajo independencia** y no constituye evidencia de nada.

## La convergencia que sí importa

Dos intervenciones ortogonales, sobre la misma cohorte, con resultados casi idénticos:

| | Mejora de la mediana | Convierte |
|---|---:|---:|
| `MF-08` (menos espacio) | 0.82 Å | 3/33 |
| `MF-02F` (más intentos) | 0.79 Å | 3/33 |

Ambas mueven el oráculo unos **0.8 Å** y ambas convierten **3**. Las poses se quedan en torno a **3 Å** y necesitan bajar de 2.0.

Restringir la geometría de búsqueda y multiplicar por tres el presupuesto de muestreo producen el mismo efecto marginal y chocan contra el mismo techo. Eso apunta a que el factor limitante **no es ni la caja ni el número de intentos**: o la función de puntuación de Vina no reconoce la pose nativa cuando la genera, o la pose nativa no está en el espacio que este generador explora con ningún presupuesto razonable.

## Consecuencia para el programa

La línea de «arreglar la colocación por geometría o por presupuesto» queda agotada en lo que respecta a estas dos palancas. El GO de MF-02F es real pero marginal, y **no justifica subir K a 90 en producción**: duplica el coste por complejo para recuperar el 9% de una cohorte difícil, sobre un gate que pasa por un solo complejo de margen.

Lo que queda abierto, y ya no es geometría:

1. **¿Vina genera la pose nativa y la puntúa mal?** Se responde mirando si entre las ~250 poses de `K90` hay alguna a ≤2 Å que el score no rankea arriba. Es análisis sobre material ya en disco, sin cómputo nuevo.
2. Si no la genera con 86 confórmeros y 9 modos cada uno, el problema es del muestreador y no del presupuesto.

## Archivos

- `PREREGISTRO.md` (en `MF-02F-PRE`, sellado antes de ejecutar) — el umbral derivado del prior y la advertencia de que la monotonía es tautológica.
- `metrics.json` — gates, cobertura y mediana por brazo, conteos efectivos de confórmeros, coste.
- `per_complex.jsonl` (48) — por complejo: confórmeros conservados por K, verificación de anidamiento, oráculo por brazo y poses contadas.
- `cohorte.json` — los 33 dominados por colocación y los 15 de control, compartidos con MF-08.
