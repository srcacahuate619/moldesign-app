---
titulo: "GO: con el lector arreglado, la regla de metales en dos niveles es estable con la semilla y coincide con el inventario"
entradilla: "En 41 entradas con un metal junto al sitio y 5 semillas, ninguna cambia de estado con la semilla y las 39 del inventario dan el estado que predice la geometría del cristal. Cambian 7 decisiones respecto de la regla de antes: cinco iones que el ligando no coordina pasan a revisión, 1RKP deja de abstenerse y 4NY4 pide revisión por el Fe del hemo."
---

**GO.** La regla de metales en dos niveles con el lector de coordenadas arreglado (`f7c46736`, rama
`claude/metales-dos-niveles`) puede integrarse en el producto. Repite el brazo nuevo de `MET-02-SEMILLA`, que quedó INCONCLUSIVE
porque el lector no reconocía el elemento con la carga escrita en la columna 79.

## Qué se midió

El mismo panel congelado de MET-02 (las 41 entradas del inventario de metales junto al sitio más 1RKP y 4NY4), las mismas cinco
semillas y la misma configuración de un caso (exhaustividad 8, 9 poses, Vina 1.2.7, 4 CPU por proceso, cápsula de API aislada). Sólo
cambia el producto del brazo nuevo: `f7c46736` quita la carga del elemento al leer coordenadas. El comparador es el brazo de antes
ya sellado en MET-02 (`861f6a0e`).

La regla: un metal retirado que el ligando del cristal coordina (un N, O o S suyo a 2,8 Å o menos), o un cofactor sin metal a 4 Å o
menos de él, sigue absteniendo; uno sólo cercano, a 6 Å o menos, pide revisión; un metal conservado que el ligando coordina pide
revisión; las distancias de metales y cofactores se miden desde el ligando del cristal; sin ligando del cristal no se sabe si lo
coordina y se abstiene.

## Qué pasó

| Medida | Resultado |
|---|---|
| Entradas evaluables y primarias | 41 de 43 (1VKG y 5I3T: Meeko rechaza el receptor) |
| H2: cambian de estado con la semilla | 0 de 41 (IC 95 % 0–0,086) |
| H3: coinciden con el inventario | 39 de 39 |
| H4: pose top-1 igual a la del brazo de antes de MET-02 | 205 de 205 pares |
| Estados | 170 ABSTENCION, 30 REVISAR, 5 REGISTRADO |

Cambian siete decisiones respecto de la regla de antes, las mismas en las cinco semillas:

| Entrada | Antes → ahora | Por qué |
|---|---|---|
| 4PHL, 4QGE, 5A2R, 6KE5, 8WGR | ABSTENCION → REVISAR | ion a 6 Å o menos que el ligando del cristal no coordina (en 6KE5, un Ca a 4,06 Å) |
| 1RKP | ABSTENCION → REGISTRADO | el Zn está a 6,52 Å del ligando del cristal; la pose lo acercaba a 5,14–5,25 Å |
| 4NY4 | REGISTRADO → REVISAR | el ligando coordina el Fe del hemo conservado (N32–Fe 2,58 Å) y Vina no modela esa coordinación |

En 5E92 y 9GKV, las dos discrepancias de MET-02, la regla ve ahora el metal coordinado (O1G–Mg 1,94 Å; O1–Zn 2,30 Å) y se abstiene.
En 9GKV el «2,15 Å» de MET-02 y del inventario era la distancia a un hidrógeno que se contaba como átomo pesado.

## Qué dice y qué no dice

- La decisión de Preparación sobre metales no depende de la semilla en este panel, y separa los iones coordinados por el ligando de
  los que sólo están cerca, como lo hace la medida geométrica del inventario.
- Dos de los falsos bloqueos que midió ABS-TR-01-VALIDEZ (1RKP y 6KE5) dejan de serlo, y una de sus autorizaciones con aviso (4NY4)
  pasa a pedir revisión por el hemo. No se ha repetido ABS-TR-01-VALIDEZ con la regla nueva.
- No dice si abstenerse o pedir revisión es la decisión correcta para cada metal: el panel no tiene etiquetas de su función, y un
  ion en la segunda esfera puede seguir siendo necesario. Por eso el nivel bajo es revisión, no autorización.
- No dice nada de la calidad del docking.
