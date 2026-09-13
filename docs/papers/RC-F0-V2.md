---
titulo: "Reconstruir el conjunto entero para poder confiar en él"
entradilla: "34,302 poses sobre 203 complejos. Antes de añadir una sola se reprodujo el conjunto anterior línea a línea, y las 2,087 heredadas se recalcularon en vez de copiarse del caché."
---

Un conjunto de datos que crece por acumulación deja de ser un conjunto de datos y pasa a
ser un sedimento. Las poses viejas vienen de una versión del generador, las nuevas de
otra, y nadie puede decir qué parte de una diferencia medida se debe al método y qué parte
a la geología.

Este experimento reconstruye el conjunto entero aplicando el generador congelado a los
tres cortes de datos, para que todo lo que hay dentro venga del mismo sitio.

## Los dos gates que sostienen los demás

Antes de generar nada nuevo hubo que demostrar dos cosas, y son las que dan valor a todo
lo que vino después.

**Reproducir el conjunto anterior línea a línea.** Desde los registros intermedios, sin
mirar el resultado final: 2,739 / 730 / 831 filas idénticas en los tres cortes, incluida
la división por scaffold con su semilla. Si eso hubiera fallado, el conjunto anterior
—y todo lo medido sobre él— habría quedado en entredicho.

**Recalcular las poses heredadas en vez de copiarlas.** Las 2,087 poses que sobreviven del
conjunto anterior se volvieron a extraer desde el material crudo. Coincidieron 2,087 de
2,087.

Reusar el caché habría sido mucho más barato. Recalcular es lo que demuestra que el
extractor sigue produciendo lo mismo hoy que el día que se ejecutó.

## Qué pasó

Los siete gates pasan. El conjunto v2 tiene **34,302 poses** con 224 características cada
una, sobre 203 complejos: 2,087 conservadas y 32,215 nuevas.

La cobertura del oráculo —la fracción de complejos donde *existe* una pose correcta entre
las candidatas— sube en los tres cortes:

| Corte | Antes | Después |
|---|---:|---:|
| train | 67.2% | **79.3%** |
| val | 75.0% | 87.5% |
| test | 87.2% | **97.9%** |

Estas cifras coinciden **exactamente** con las medidas por una vía independiente sobre el
material crudo: dos caminos de código distintos, el mismo número.

## Tres consecuencias que se declaran, y una de ellas es incómoda

**1. v2 no es v1 ampliado.** La tarea cambia de ordenar unos 9 candidatos a ordenar unos
169. Queda prohibido comparar cifras del selector entre las dos versiones sin
reentrenarlo: no es la misma tarea con más datos, es otra tarea.

**2. El gradiente train < val < test persiste, y no es una buena noticia.** 79.3 < 87.5 <
97.9. La división por scaffold concentró los scaffolds difíciles en `train`. Eso significa
que un selector entrenado ahí y evaluado en `test` **tiene el generador a favor**, y esa
ventaja no es suya. Cualquier cifra de rendimiento en `test` está inflada por una
propiedad del corte de datos, no del modelo.

**3. `test` queda casi saturado**, con 46 de 47 complejos cubiertos. Ahí ya no hay techo
de generación que ganar; lo que se mida será selección pura.

## Lo que deliberadamente no se hizo

No se entrena ni evalúa ningún selector aquí. Este experimento construye el terreno; medir
sobre él es otro experimento, y mezclarlos habría permitido ajustar el terreno en función
del resultado.

Y **no se aplicó la deduplicación** de poses que ya estaba disponible, aunque habría hecho
el conjunto más manejable. Su umbral de 1.5 Å se eligió sobre una unión **6.9 veces menos
densa**, y reusarlo aquí sería extrapolarlo a otro régimen sin comprobarlo. La
re-derivación se hizo después, en su propio experimento, y dio un umbral distinto —2.0 Å—
lo que confirma que aplicar el viejo habría sido un error.

## Epílogo

Este conjunto se construyó para dar una segunda oportunidad al selector de poses: la
hipótesis era que su fracaso anterior se debía a tener pocos candidatos que ordenar.

Se le dio 6.9 veces más material, y volvió a perder contra la puntuación cruda de Vina.
El denominador no era el problema. Pero eso sólo se pudo afirmar porque el conjunto sobre
el que se midió era reproducible línea a línea.
