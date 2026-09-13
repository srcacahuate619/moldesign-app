---
titulo: "Un GO operacional que no rescata el NO_GO científico"
entradilla: "3,469 poses de 156 complejos unificadas sin re-dockear, con cero colisiones y determinismo byte a byte. Y una nota en el sello: esto no dice que MolFlex sirva."
---

Antes de poder comparar generadores de poses hay que poder **mirarlos juntos**. Tres
fuentes distintas producían poses en formatos, convenciones de índices y directorios
distintos, generadas a lo largo de meses. Compararlas exigía materializar una unión
trazable: cada pose con su geometría real y su enlace a la procedencia, sin volver a
dockear nada.

Este experimento es esa unión. Es puro trabajo de plomería, y está aquí por lo que dice su
sello.

## Qué se entregó

| | |
|---|---:|
| Poses unificadas | 2,739 + 730 |
| Complejos | 156 |
| Corridas con procedencia | **447 / 447** |
| Colisiones de identificador | **0** |
| Poses sin procedencia | **0** |
| Geometría real (no placeholder) | 100% |
| Determinismo | Byte a byte |
| Acceso al conjunto de test | Ninguno |

Cero colisiones importa más de lo que parece: significa que ninguna pose de una fuente
sobrescribió silenciosamente a otra al fusionar. Ese es el modo de fallo clásico de una
unión, y es invisible después — el conjunto resultante parece perfectamente sano, sólo que
le faltan filas.

## La nota que hace interesante este registro

El sello incluye, textualmente, una advertencia contra su propia lectura optimista:

> El gate **científico** permanece NO_GO. MolFlex aportó 0 complejos en la cohorte
> difícil. Este GO es exclusivamente **operacional** sobre el artefacto.

Es decir: se construyó bien la herramienta para comparar generadores, y la comparación dijo
que el generador propio no aporta nada. Las dos cosas conviven en el mismo identificador y
el registro se encarga de que no se confundan.

Sin esa nota, dentro de seis meses alguien —incluido el propio autor— vería «MF-01-UNION:
GO» en un listado y concluiría que la unión de fuentes funcionó en el sentido que
importaba.

## Por qué esta distinción es una política, no un detalle

Buena parte de los registros de este programa son de este tipo: un artefacto se construye
correctamente y la pregunta científica que motivaba construirlo se responde que no. Si
ambos casos se sellan igual, el recuento de «éxitos» del programa se llena de fontanería
que funciona, y deja de medir nada.

De aquí sale la separación que usa el registro público entre **hallazgos** —gates
científicos superados— y las otras poblaciones, entre ellas los artefactos operacionales.
Un GO que sólo dice «la herramienta hace lo que dice» es verdad, es necesario, y no es un
resultado.

## Qué quedó utilizable

La unión materializada es la base sobre la que después se midió la cobertura por fuente, se
derivó la política de deduplicación, y se reconstruyó el conjunto de poses completo. Nada
de eso habría sido posible sin poder mirar las tres fuentes en el mismo marco de
coordenadas y con el mismo esquema de índices.

La plomería no da resultados. Da la posibilidad de tenerlos.
