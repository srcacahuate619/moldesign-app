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

## Correcciones

**2026-10-22**, a raíz de la Fase B de la auditoría científica (fase 1b del plan de arreglos,
`docs/102_FASE_1B_CORRECCIONES.md`). Ninguna cifra sellada cambia.

- SCI-B-143. La cobertura no cambia en las poses recomputadas de molflex al corregir simetría.
  Al conservar el RMSD ingenuo de otras fuentes, la cobertura agregada sigue siendo una cota
  inferior de la que daría una corrección completa. Se retiran «las cifras se sostienen
  exactamente» y la afirmación de que el denominador completo no puede aumentar; no se ha
  demostrado invariancia en las fuentes sin recomputar.
- SCI-B-144. En las poses molflex recomputables de train, las positivas pasan de 357 a 432: 75
  recuperadas. Es un aumento relativo del 21,0% sobre las 357 originales; 75/432 = 17,4% de las
  positivas corregidas estaban etiquetadas negativas. Son denominadores distintos. Las otras
  fuentes no se recomputaron y no se extiende esta fracción al material restante ni se mide aquí
  el efecto sobre un selector. Productor: `scripts/analisis_fase1b_falsas.py`.
- SCI-B-145. Las 203 unidades conservadas tienen reproducción válida del RMSD ingenuo y 32 215
  poses recomputadas, coincidentes en número con el material molflex declarado por unidad y con
  sus registros de pose. El reanálisis rechaza una reproducción fallida o una lista truncada.
  Quedan 2 087 poses de otras fuentes sin corregir; por tanto no se afirma completitud de la
  corrección simétrica sobre todas las fuentes ni se elimina el límite de cota inferior.
  Productor: `scripts/analisis_fase1b_cohortes.py`.
- SCI-B-146. Los PASS de G6 y G2b acreditan ausencia de errores y NaN registrados, y
  coincidencia de las comparaciones que efectivamente se hicieron. No acreditan por sí solos
  igualdad de todos los identificadores de pose esperados y emitidos, porque el extractor podía
  omitir registros ausentes. Los recuentos reportados se conservan como resultados de la salida,
  con esa limitación de la guarda; no se infiere que la corrida histórica esté incompleta.

## MF-02B: el antecedente se lee mediante su corrigendum de marco de RMSD

**GO histórico, reemplazado por MF-02B-R1.** Aporta la procedencia de una fuente añadida; no cambia la decisión de reconstrucción de este paper.

El ensayo original confundió RMSD alineado con RMSD de bolsillo. El corrigendum conserva 14 recuperados de 38 casos antes no cubiertos, pero busca el mínimo entre todas las poses dockeadas. Ese oráculo es más permisivo que el endpoint de poses entregadas del gate original.

**SCI-B-064** retira las cifras antiguas como resultado vigente y enlaza el reemplazo. **SCI-B-065** deja sin medir el endpoint exacto top-K entregado; no se declara fallido ni superado a partir del oráculo corregido. Añadir una fuente tampoco mide la precisión del selector sobre la unión. No comprobado por mí: regenerar el material o reconstruir el conjunto exacto entregado. Fuentes: `MF-02B`, `MF-02B-R1` y `docs/102_FASE_1B_CORRECCIONES.md`.

## MF-02E: el material de evaluación se generó con receta congelada y etiquetas de reporte

**GO de generación de material.** Identifica la producción de val y test consumida por este conjunto; no añade un resultado de selección.

El registro conserva 87 casos completados con 30 confórmeros solicitados y exhaustividad 8. El coste mediano archivado es 299,8 s por complejo. El material quedó en `molflex_valtest_v2`; la cobertura posterior se lee en marco de bolsillo, no desde el RMSD alineado del informe de generación.

El sellado fue retrospectivo. **SCI-B-067** retira «no se miran etiquetas»: el runner calcula y guarda RMSD frente al cristal por caso para reporte, aunque no lo usa para ajustar parámetros ni para sus gates de validez y presencia de archivos. No se afirma cegamiento total ni procedencia molecular completa por coincidencia de agregados. No comprobado por mí: reproducir generación y tiempos desde los inputs originales. Fuente: `MF-02E`.

## RC-F0-SYM: la corrección también cambia etiquetas de las particiones de evaluación

**GO de relectura de la métrica.** Completa la distribución por split del cambio de etiquetas, sin evaluar un selector ni cambiar los límites ya expuestos en Correcciones.

El emparejamiento de poses recomputables usa `(pid, file_stem, model_idx)`. Se minimiza el RMSD sin alinear sobre automorfismos; el corte es 2,0 Å. Las poses que cruzan ese corte al corregir son 9 en val y 36 en test. No son otros tantos complejos que ganan cobertura: una unidad puede contener varias poses afectadas y ya estar cubierta.

Aplican **SCI-B-143, SCI-B-144 y SCI-B-145**, desarrolladas arriba. La comprobación posterior de cobertura no se atribuye como guarda al productor original. No comprobado por mí: recalcular automorfismos o RMSD desde material molecular. Fuente: `RC-F0-SYM`.
