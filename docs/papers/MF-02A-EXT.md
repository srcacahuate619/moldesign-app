---
titulo: "Dije «satura» con 116 complejos; con 4,636 sigue subiendo"
entradilla: "El techo conformacional generaliza: un 12% de PDBBind no tiene la conformación bioactiva ni con 150 confórmeros. Y el plateau que había declarado era en parte artefacto del tamaño de muestra."
---

Antes de decidir cuántos confórmeros generar hay que saber qué se compra con cada uno. Una
medición previa sobre los 116 complejos de entrenamiento había dado una curva que se
aplanaba, y de ahí salió una decisión: **satura alrededor de 60 confórmeros**, más allá no
compensa.

Este experimento repite la medición sobre **4,636 complejos** de PDBBind.

## La curva

Disponibilidad conformacional a ≤2 Å del bioactivo:

| Confórmeros | Disponibilidad |
|---:|---:|
| 5 | 75.2% |
| 15 | 81.2% |
| 30 | 83.9% |
| 60 | 86.2% |
| 90 | 87.2% |
| 150 | **88.1%** |

## Tres lecturas

**1. El techo generaliza.** Alrededor del **12% de PDBBind no tiene la conformación
bioactiva en el ensemble ni con 150 confórmeros**. Eso no es una peculiaridad de la cohorte
del programa: es una propiedad del método de generación de confórmeros.

Es un límite duro que ningún ajuste de docking puede superar, porque el material correcto
nunca se produce.

Y hay un número más que conviene no perder: **680 complejos de los 5,316 (12.8%) fallaron el
embebido** y no pasan ni la primera fase del generador. Ese 12.8% es distinto del 12%
anterior y se suma a él.

**2. Corrige mi propia conclusión anterior.** Sobre los 116 la curva se aplanaba en 80.2%
desde 60 confórmeros, y declaré saturación. Sobre 4,636 **sigue subiendo** alrededor de un
punto por cada duplicación: 86.2 → 87.2 → 88.1.

El plateau era en parte **artefacto del tamaño de muestra**. Con 116 complejos, un punto de
diferencia son 1.2 complejos, indistinguible del ruido; con 4,636 se ve.

La conclusión cualitativa sobrevive —hay rendimientos decrecientes, y multiplicar el coste
por 5 de 30 a 150 confórmeros compra 4.2 puntos— pero **la palabra «satura» era demasiado
fuerte**, y estaba respaldada por menos datos de los necesarios para usarla.

**3. El conjunto de entrenamiento es más difícil que PDBBind en general.** A 30 confórmeros
la disponibilidad es **83.9% en PDBBind** frente a **77.6% en los 116**.

Eso es coherente con el gradiente que otro experimento encontró entre los conjuntos de
entrenamiento, validación y test, y sugiere un **sesgo en cómo se armó la cohorte**. No es
una casualidad: es la misma sombra que aparece en varios resultados del programa, y explica
por qué algunas curvas medidas en entrenamiento no se replican fuera.

## Por qué una medición descriptiva merece un registro

Este experimento no tiene criterio de aceptación. No decide nada: mide.

Su valor está en las dos correcciones que produjo. Retiró una palabra que se había usado
para justificar una decisión de configuración, y puso número a una sospecha sobre el sesgo
de la cohorte que hasta entonces era intuición.

Ninguna de las dos habría aparecido sin extender la medición a cuarenta veces más
complejos, que era la clase de trabajo que resultaba fácil no hacer porque la respuesta ya
parecía conocida.
