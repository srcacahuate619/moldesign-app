---
titulo: "Las reglas que rechazan un ligando no rechazan ninguna molécula con actividad medida"
entradilla: "Antes de acoplar, MolDesign rechaza las moléculas con mucha carga, con radicales o con varios fragmentos. Nadie había medido si esas reglas se llevaban por delante química real. En 640 moléculas activas de tres dianas, no rechazan ninguna."
---

**GO.** Las cuatro reglas bloqueantes del validador del ligando no rechazan ninguna de las 640 moléculas con actividad medida.

## Qué se midió

El validador rechaza, sin dejar elegir, cuatro casos:
- una carga neta mayor que 2 en valor absoluto;
- un átomo con carga mayor que 2 en valor absoluto;
- radicales;
- varios fragmentos que no sean una sal reconocida.

Ninguna regla tenía una medida detrás, y el propietario prefiere que el producto avise en lugar de bloquear. Lo encontró Sol en el
inventario SUPUESTOS-01. Se pasaron por el validador del producto, sin cambiar su configuración:
- 640 moléculas con afinidad medida (VMAT2, NET y 5-HT1A);
- 3000 señuelos de DUD-E;
- 6898 moléculas de los conjuntos de benchmark del proyecto.

## Qué pasó

- **Ninguna molécula activa cae en las cuatro reglas,** y tampoco ningún señuelo.
- **En los conjuntos de benchmark, la de fragmentos rechaza 6:** son solvatos escritos con el disolvente como segundo fragmento, que
  el usuario tendría que borrar a mano.
- **Otras 68 caen por reglas distintas, y con motivo:** 19 llevan boro, para el que Vina no tiene parámetros, y 49 son péptidos de
  más de 1000 Da, fuera del alcance declarado.

## Qué dice y qué no dice

- **Con estos datos el supuesto se sostiene:** las reglas no bloquean química con actividad medida.
- **No es el espacio de los fármacos:** son tres dianas, sin aniones múltiples como los fosfatos o los nucleótidos.
- **Mira el SMILES de entrada, no la especie después de protonar.**
- **Queda una mejora menor:** convertir el rechazo de los solvatos en un aviso que se quede con la molécula mayor, coherente con
  «avisar, no bloquear». El experimento no lo exige.
