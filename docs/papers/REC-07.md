---
titulo: "El grid roto no estaba roto donde importa"
entradilla: "Un grid con 3 de 15 hotspots recortados y un margen de −5.147 Å debería arruinar el docking. Coloca el inhibidor en contacto con la cisteína catalítica en 5 de 5 semillas, mediana 0.773 Å."
---

`5TUN` llevaba tiempo documentado como el caso testigo de grid defectuoso: la caja de
búsqueda recortaba 3 de sus 15 hotspots, con un margen mínimo de −5.147 Å. Había incluso
una corrección propuesta.

Antes de aplicarla, este experimento hizo la pregunta que nadie había hecho: **¿el defecto
geométrico se traduce en un fallo de docking?**

Para responderla hacía falta un control real, no una métrica geométrica. Se usó E64c, el
inhibidor canónico de cisteína-proteasas, extraído de un homólogo. Si el grid funciona, la
pose ganadora debe quedar en contacto con la cisteína catalítica, que es donde ese
inhibidor se une por mecanismo conocido.

## Qué pasó

| Grid | Contacto con la cisteína catalítica | Distancia mediana |
|---|---:|---:|
| **Catálogo (el "roto")** | **5 de 5 semillas** | **0.773 Å** |
| Caja adaptativa propuesta | 4 de 5 semillas | — |
| Predicción de pocket | 5 de 5 semillas | — |

El grid del catálogo, el que la auditoría había marcado como defectuoso, **coloca el
ligando correctamente en las cinco semillas**.

Seis de los siete criterios pasan. Falla el de no regresión: el grid recomendado logra
contacto en 4 de 5 semillas frente a 5 de 5 del actual. La regla congelada exige los siete
para un cambio, así que **no se recomienda cambiar el grid de 5TUN**.

## El único fallo, diagnosticado

La semilla 45 del brazo adaptativo puso su pose ganadora a 12.89 Å. Parece una regresión
real hasta que se mira el resto de esa misma corrida: **el mejor de sus 9 modos queda a
2.09 Å**. La pose correcta se generó; el ranking la puso en otro sitio.

Es fluctuación de muestreo, no un defecto del grid. Queda anotado como tal.

## Una tentación declinada

El grid basado en predicción de pocket tiene el **mejor score mediano** de los tres:
−6.182 frente a −5.095 del catálogo, con contacto en 5 de 5.

Sería el ganador si el score decidiera. El prerregistro **prohíbe explícitamente usar el
score para elegir el grid**, porque un score mejor sobre una caja distinta no es
comparable: cambiar la caja cambia el espacio de búsqueda, y una caja más ajustada puede
dar mejores números sin colocar mejor.

El criterio era el contacto catalítico, se fijó antes, y no se cambió al ver los
resultados.

## Un fallo de preparación que se corrigió sin tocar el criterio

La primera ejecución pasó el PDB crudo al preparador, conservó las **387 aguas** de la
estructura y devolvió scores positivos de +23 a +33 con sólo 1 a 5 modos. El criterio de
validez lo marcó como fallo automáticamente.

Se corrigió la preparación y se repitió la tanda completa **sin tocar ningún criterio de
decisión**. Ese orden importa: arreglar el instrumento y volver a medir es legítimo;
arreglar el instrumento y de paso ajustar el umbral, no.

## Consecuencia para el programa

Es el hallazgo que reordena la cartera de receptor:

> Una excepción geométrica del catálogo **no implica** un fallo de docking.

La cola de 57 objetivos que la auditoría había marcado es una **lista a verificar**, no
una lista de objetivos rotos. Sin este experimento se habrían "reparado" grids que
funcionaban, con el riesgo de romper los que estaban bien — que es exactamente lo que
midió después `REC-03`, donde la reparación automática perdió dos objetivos sanos de forma
catastrófica.
