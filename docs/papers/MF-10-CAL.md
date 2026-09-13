---
titulo: "Los dos controles que convierten un negativo en una respuesta"
entradilla: "Antes de creerse un «no funciona» hay que descartar que el instrumento estuviera ciego. El suelo es 0.401 Å y el minimizador estaba convergido: el negativo era real."
---

Un experimento anterior había medido que relajar las poses con un campo de fuerza bien
parametrizado no convierte ningún complejo. Antes de aceptar ese resultado hay dos
preguntas que un negativo obliga a responder, y que casi nadie responde:

1. **¿Tenía resolución el instrumento?** Si el proceso de medición mueve las cosas tanto
   como el efecto buscado, no puede detectarlo.
2. **¿Estaba convergido el minimizador?** Si se paró antes de tiempo, el «no se mueve» sólo
   significa «no le dio tiempo».

Un negativo sin estos dos controles es indistinguible de un experimento mal montado. Este
los ejecuta.

## Control 1 — el suelo del instrumento

Se sometió **la propia pose cristalina** al protocolo idéntico de relajación. El cristal ya
está en la conformación correcta, así que cuánto se mueve mide el ruido que el
procedimiento introduce por sí solo.

| | Desplazamiento del cristal |
|---|---:|
| Mediana | **0.401 Å** |
| Percentil 90 | 0.787 Å |
| Máximo | 1.939 Å |

El efecto que había que detectar era de aproximadamente **1 Å**. El suelo está muy por
debajo. **El instrumento tenía resolución de sobra**, y el negativo es un negativo real, no
ceguera del aparato.

## Control 2 — la convergencia del minimizador

Se multiplicó el presupuesto de minimización por **20**: de 500 a 10,000 iteraciones. Si el
minimizador se hubiera estado parando antes de tiempo, aquí se vería.

Mejora del delta mediano: **0.061 Å**, por debajo del umbral de 0.1 Å que se había fijado
antes. El experimento original midió con el minimizador esencialmente convergido.

## El matiz que forma parte del sello

El efecto del presupuesto **no es exactamente cero**, y decirlo importa. Con las primeras 5
a 7 poses parecía nulo; con las 21 válidas se ve **pequeño pero real**. Y aun a 10,000
iteraciones el delta llega como mucho a −0.111 Å.

Un orden de magnitud corto de lo necesario. Es decir: la dirección es correcta, el
minimizador sí mejora las poses, y la mejora es del tamaño equivocado. Eso refuerza el
negativo en lugar de debilitarlo, pero es una afirmación distinta de «el presupuesto no
hace nada», y se registra como tal.

## Un diagnóstico confirmado de paso

Los **9 complejos** que fallan la parametrización son exactamente los mismos que en el
experimento original, con el mismo error de plantilla. Que el fallo se reproduzca
idénticamente al cambiar el presupuesto confirma que la causa es la **preparación del
receptor** y no algo estocástico del minimizador.

Ese diagnóstico se verificó después de forma independiente: los 9 tienen huecos de cadena,
9 de 9, contra una tasa base del 42.4%.

## Por qué este registro es de los que más valen

Es un experimento cuyo único propósito es comprobar que otro experimento medía algo. No
produce ningún hallazgo sobre docking. Lo que produce es el derecho a creerse un negativo.

La mayoría de los resultados negativos publicados en este campo no tienen su equivalente, y
por eso no se distinguen de un montaje que no funcionaba.
