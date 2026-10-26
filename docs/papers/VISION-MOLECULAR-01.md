---
titulo: "Levantar el dibujo a 3D en moléculas grandes: seis alternativas medidas, ninguna mejora lo que ya hace el producto"
entradilla: "Cuando una molécula grande y flexible se dibuja en 2D, ninguna geometría 3D se le parece del todo, y el producto se abstiene en 8 de 37. Se midieron seis formas de arreglarlo, cada una con su criterio escrito antes. Ninguna lo consigue sin pagar en otra cosa."
---

**NO_GO.** Ninguna de las seis alternativas cumple su registro previo, así que el producto se queda como está: enseña la pose en 3D
aunque no pueda levantarla desde el dibujo, y declara la energía del conformador que enseña.

## Qué se midió

La «visión molecular» levanta el dibujo plano de una molécula a una geometría 3D que se le parezca, para que el químico vea en 3D lo
que dibujó. En moléculas grandes y flexibles el dibujo extendido no se parece a ningún 3D real. Con 37 moléculas de 35 a 51 átomos
pesados, el producto se abstiene en 8, y el conformador que elige está una mediana de 11,5 kcal/mol por encima del más estable que
encuentra.

Se probaron seis ideas. Cada una tenía su criterio escrito y guardado antes de medirla:

| | Idea | Resultado |
|---|---|---|
| E1 | Que el dibujo se ajuste al 3D, y no al revés | Rescata 10 de 25 abstenciones; hacía falta el 75 % |
| E2 | Medir la energía con xTB y disolvente, no con MMFF en fase gas | Parcial: la cifra baja un 31 %, pero el problema sigue |
| E3 | Plegar la molécula con los anillos fijos donde están en el dibujo | 5 abstenciones de 37 (hacían falta 4 o menos) y 11 moléculas imposibles |
| E4 | Elegir sólo entre conformadores a menos de 5 kcal/mol del mínimo | La abstención sube de 8 a 23 |
| E5 | Enderezar cadenas y girar colas, como hace MolTalk | Baja de 8 a 7; hacía falta 4 o menos |
| E6 | Animar el paso de 2D a 3D girando enlaces y no en línea recta | La línea recta casi nunca cruza átomos (2 de 29), y las torsiones cruzan más |

## Qué dice y qué no dice

- **Parecerse al dibujo y ser estable son objetivos opuestos** en moléculas flexibles. Cada kcal/mol que se le quita al conformador
  se paga en parecido, y ninguna de las alternativas consigue las dos cosas.
- **La energía declarada exagera, pero no engaña.** Con xTB y disolvente, el conformador elegido sigue por encima de 5 kcal/mol en 27
  de 37 moléculas.
- **No mide poses de Vina.** E1 usa como «pose» un conformador sin elegir, que es una aproximación a lo que ve Moldex.
- **No es ciencia de afinidad:** la elevación es una vista. No cambia ninguna corrida, ningún score ni ninguna decisión de Preparación.
- **Se selló al cerrar.** Los seis se registraron y se midieron por separado el 2026-10-24 y 25, y se reunieron en un solo
  experimento. Lo que garantiza que cada criterio precede a su dato es el orden de los commits.
