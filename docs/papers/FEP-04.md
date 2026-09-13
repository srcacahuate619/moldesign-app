---
titulo: "Una pose que sabe cuándo no confiar en sí misma"
entradilla: "Tres señales gratuitas predicen si la pose entregada es correcta. Abstenerse en el 75% menos confiable casi duplica la precisión del resto: de 0.330 a 0.620."
---

Un programa de docking entrega una pose y no dice nada más. El químico que la recibe
tiene que decidir si construir encima de ella, y no tiene con qué. Si el motor acierta
un tercio de las veces —que es aproximadamente lo que acierta el nuestro, y lo que
acierta la mayoría— entonces dos de cada tres decisiones que se tomen sobre su salida
serán decisiones tomadas sobre una pose equivocada, y nada en la interfaz lo advierte.

Este experimento pregunta si la propia salida del motor ya contiene la advertencia.

## La pregunta

Cuando Vina termina, además de la pose ganadora deja un rastro: los otros ocho modos que
consideró, sus puntuaciones, y cuánto se parecen entre sí. Ese rastro se descarta. La
hipótesis es que no debería descartarse, porque un motor que duda deja huellas de que
duda.

Se midieron tres señales, todas calculables **sin conocer la respuesta** y sin entrenar
ningún modelo:

- el **margen de score** entre modos geométricamente distintos;
- la **dispersión del top-5**, es decir cuánto se dispersan las cinco mejores poses;
- el número de **modos empatados** dentro de 1 kcal/mol.

## Qué pasó

Las tres funcionan. Sobre los 203 complejos, la precisión del top-1 global es **0.330**.
Si se ordenan los casos por confianza y se descarta el 75% menos confiable, la precisión
del cuarto restante sube a:

| Señal | Precisión al 25% más confiable |
|---|---:|
| Modos empatados a 1 kcal/mol | **0.620** |
| Margen de score | 0.600 |
| Dispersión del top-5 | 0.580 |

Los intervalos de Wilson de los dos extremos apenas se tocan —[0.269, 0.398] contra
[0.482, 0.741]—, así que la separación no es ruido.

Lo que hace que esto importe es que las tres señales son **gratis**. Se calculan de poses
que ya se generaron. No hay modelo que entrenar, ni información cristalográfica, ni un
segundo pase de cómputo.

## El segundo hallazgo, que era un efecto colateral

Midiendo lo anterior apareció algo con consecuencia más inmediata:

| Qué se entrega | Precisión |
|---|---:|
| Top-1, una sola pose | 0.330 |
| Top-5, cinco alternativas | **0.465** |
| Oráculo (la mejor pose que existe entre las generadas) | 0.615 |

Entregar cinco candidatas en vez de una sube la cobertura útil **13 puntos** sin tocar el
motor de búsqueda. Y el oráculo en 0.615 marca dónde está el techo: el material bueno ya
se está generando, lo que falla es escogerlo.

> Es un cambio de diseño, no de investigación: dejar de entregar una pose y empezar a
> entregar K con su confianza.

## Lo que este resultado no dice

Tres límites, declarados aquí porque forman parte del resultado:

1. **La curva es optimista.** Las señales se observan sobre los mismos datos donde se
   mide su utilidad. Un uso real exige calibrar en `train` y medir en `val`/`test`, y ese
   experimento todavía no se ha hecho.
2. **A cobertura del 25% quedan n=50**, con un intervalo de confianza de ±13 puntos. La
   *forma* de la curva es sólida; el valor puntual de 0.620 no lo es.
3. **Las tres señales no se combinaron.** Se midieron por separado.

Y una nota posterior que conviene leer junto a este resultado: `FND-03` midió después que
la varianza entre semillas llega a 4 Å de rango en algunos complejos. Una confianza
honesta debería incorporar repeticiones, y esta no lo hace.

## Por qué está en la columna de la izquierda

Porque es el único resultado del programa que se traduce directamente en algo que un
usuario nota. No hace al motor mejor. Hace que el motor deje de mentir sobre lo que sabe.
