---
titulo: "Dos métodos de carga, y hasta 216 kJ/mol de diferencia"
entradilla: "El método rápido y el de referencia difieren 0.0118 e por átomo de mediana. Traducido a energía: 24.3 kJ/mol de mediana y 216.4 de máximo, que es del orden de lo que un rescoring pretende resolver."
---

El experimento anterior parametrizó los 116 ligandos con un método de cargas rápido, basado
en red neuronal. Este los parametriza otra vez con el método de **referencia** —lento,
semi-empírico, el estándar del campo— y compara.

La comparación tiene una regla escrita antes de empezar, y es lo primero que hay que decir:

> **Prohibido concluir sobre el método rápido desde este experimento.** Esto es
> caracterización, no selección. La decisión se toma en un tercer experimento que agrega
> ambos contra el contrato declarado.

Sin esa regla, este experimento sería un juez que se nombra a sí mismo: se elige un método
de referencia, se mide la discrepancia, y luego se decide *a posteriori* qué discrepancia
era aceptable.

## El mapeo, verificado en vez de asumido

Comparar cargas átomo por átomo exige saber qué átomo de un cálculo corresponde a qué átomo
del otro. La versión anterior del código lo asumía **por índice**, que funciona hasta que
un preparador reordena los átomos y entonces compara silenciosamente el carbono 3 con el
oxígeno 7.

Aquí se verificó elemento a elemento **y por coordenadas**: 115 de 115, con desplazamiento
máximo de **0.0005 Å**. Ese cambio de «asumido» a «verificado» es la razón por la que las
cifras de abajo significan algo.

## Qué salió

| Diferencia de carga por átomo | Valor |
|---|---:|
| Media | 0.0142 e |
| Mediana | 0.0118 e |
| Máximo | **0.4255 e** |
| Ligandos con algún átomo por encima de 0.2 e | 13 de 115 |

Traducido a energía de punto único:

| | Valor |
|---|---:|
| Mediana | **24.3 kJ/mol** |
| Máximo | **216.4 kJ/mol** |

Ese número es el que importa, y por eso está en el titular: **24 kJ/mol de mediana es del
orden de magnitud de lo que un rescoring pretende resolver**. La elección de método de
cargas no es un detalle de implementación — es comparable al efecto que se quiere medir.

## Dónde divergen más

La discrepancia no es uniforme, y su estructura es químicamente sensata:

| Estrato | Diferencia media por átomo |
|---|---:|
| Azufre y fósforo | **0.0168 e** ← contiene el máximo global |
| Resto | 0.0125 e |
| Fragmentos | 0.0107 e |
| Drug-like | 0.0155 e |
| Menos de 5 enlaces rotables | 0.0113 e |
| Más de 10 rotables | 0.0157 e |

La divergencia **crece con el tamaño y la flexibilidad**, y es mayor en los elementos de la
tercera fila. Eso es coherente con lo que se sabe de estos métodos: los modelos entrenados
generalizan peor en química menos representada y en moléculas más grandes.

Es decir: divergen más justo donde el proyecto trabaja.

## Los fallos, separados por causa

**Uno solo es real:** un ligando donde el método de referencia no converge. Es un fallo
**químico**, no de presupuesto, y se declara como tal.

**Los otros cuatro no eran fallos.** Fueron tiempos de espera agotados en la primera
ejecución, y se diagnosticaron como artefacto de haber lanzado tres particiones simultáneas
en cuatro núcleos. Ejecutados en solitario con más margen, se recuperaron los cuatro.

Distinguir esas dos categorías importa: contar los cuatro como fallos químicos habría
inflado la tasa de fallo del método de referencia y sesgado la comparación a favor del
rápido.
