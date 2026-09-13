---
titulo: "Pasa el gate por el mínimo exacto, y el dosis-respuesta no acompaña"
entradilla: "El criterio exigía recuperar 3 complejos de 33. Recuperó exactamente 3. Un complejo menos habría sido NO_GO, y con n=3 el intervalo no soporta ninguna afirmación de tamaño de efecto."
---

MolFlex dockea cada confórmero por separado. Eso significa que el número de confórmeros no
es sólo diversidad de formas: es también el número de **reinicios de búsqueda**
independientes. Triplicarlo debería recuperar complejos cuyo fallo es de colocación y no de
conformación, porque cada reinicio es otra oportunidad de caer en la cuenca correcta.

Es una relectura del mismo parámetro, y una de las pocas ideas que quedaban sin probar.

## Qué pasó

El criterio preregistrado exigía recuperar **al menos 3** de los 33 complejos dominados por
colocación al pasar de 30 a 90 confórmeros.

Recuperó **exactamente 3**.

Pasa. Y hay que decir con claridad lo que eso vale: **un solo complejo menos habría sido
NO_GO**. Con n=3 sobre 33, el intervalo de confianza no soporta ninguna afirmación sobre el
tamaño del efecto. Es un GO que toca el listón, no que lo supera.

## Tres advertencias que van con el sello

**1. El punto de partida es tautológico.** La cohorte se definió como los complejos que
fallan con la configuración base, así que ese brazo marca 0 de 33 por construcción, no por
medición. Es el mismo defecto que arrastraba `MF-08`, heredado al reutilizar la cohorte.

**2. El dosis-respuesta no es suave, y eso debería preocupar:**

| Salto | Complejos recuperados | Movimiento de la mediana |
|---|---:|---:|
| 29 → 58 confórmeros | **0** | 0.08 Å |
| 58 → 86 confórmeros | 3 | 0.70 Å |

Duplicar el número de reinicios no recuperó nada. El siguiente salto, más pequeño,
recuperó tres. Con estos tamaños **no se distingue un mecanismo con umbral del ruido de
muestreo**. Si el mecanismo fuera el postulado, la respuesta debería crecer de forma
gradual con el número de reinicios, y no lo hace.

**3. El coste se duplica** —601 s por complejo— para recuperar el 9% de una cohorte
difícil.

## La coincidencia que parecía un hallazgo y no lo es

Los complejos recuperados por la intervención de caja (`1d7i`, `1ew9`, `1l83`) y los
recuperados por esta (`1ela`, `1fkg`, `1mu8`) son **disjuntos**. La lectura tentadora es
que las dos intervenciones son complementarias y que sumadas convertirían 6.

No lo es. La probabilidad de que dos conjuntos de 3 extraídos de 33 sean disjuntos **por
puro azar** es **0.744**. El solapamiento vacío es el resultado *esperado* bajo
independencia, no evidencia de complementariedad. Y sumarlos a 6 está además prohibido por
el prerregistro, precisamente para que no se hiciera esta cuenta.

## Lo que sí es informativo, y apuntaba al final

La convergencia. Dos intervenciones **ortogonales** —una que reduce el espacio, otra que
multiplica los intentos— sobre la misma cohorte mejoran la mediana del oráculo en 0.82 Å y
0.79 Å respectivamente, y **ambas convierten exactamente 3**.

Dos palancas distintas, mismo resultado, mismo techo. Eso no es coincidencia: es la firma
de que las dos chocan contra el mismo obstáculo, que ninguna de ellas toca.

El obstáculo se identificó poco después: en 30 de esos 33 complejos **no existe** una pose
correcta entre las ~751 candidatas. No hay nada que recuperar con más intentos ni con menos
espacio, porque la región correcta nunca se visita.
