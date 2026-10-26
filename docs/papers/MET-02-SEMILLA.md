---
titulo: "INCONCLUSIVE: la decisión sobre metales no depende de la semilla, pero la regla nueva no reconoce dos metales"
entradilla: "En 41 entradas con un metal junto al sitio y 5 semillas, ninguna cambia de estado con la semilla, ni con la regla de antes ni con la de dos niveles. La regla nueva coincide con el inventario en 37 de 39: en 5E92 y 9GKV el lector de coordenadas tomaba la carga como parte del elemento y no veía el metal."
---

**INCONCLUSIVE.** La regla de metales en dos niveles (rama `claude/metales-dos-niveles`, `878c215b`) no entra en el producto
con este resultado. Hay que arreglar el lector de coordenadas y repetir el brazo nuevo.

## Por qué se hizo

`ABS-TR-01-VALIDEZ` midió que Preparación juzgaba la distancia de un metal con el mínimo entre la pose top-1 de Vina y el ligando
del cristal. En 1RKP la pose ponía el Zn a 5,17 Å y el cristal lo deja a 6,52 Å, así que la abstención podía depender de la semilla.
La regla nueva mide metales y cofactores desde el ligando del cristal y separa dos niveles: un metal que el ligando del cristal
coordina (un N, O o S suyo a 2,8 Å o menos), o un cofactor sin metal a 4 Å o menos, sigue absteniendo; uno sólo cercano pide
revisión; un metal conservado y coordinado (el Fe del hemo de 4NY4) pide revisión.

## Qué se midió

Panel congelado antes de correr (`entrada/panel.json`): las 41 entradas del inventario de metales junto al sitio
(`docs/auditorias/metales_junto_al_sitio_2026-10-11.json`) más 1RKP y 4NY4 de ABS-TR-01. Cinco semillas (42, 7, 13, 101 y 2026).
Configuración de un caso: exhaustividad 8, 9 poses, Vina 1.2.7, 4 CPU por proceso. Cada corrida se hizo dos veces, por la API de
una cápsula aislada: con el producto de antes (`861f6a0e`) y con el de la regla nueva (`878c215b`). Se registró el estado del
requisito `entorno.metales_cofactores` y el hash de la pose top-1.

Tres hipótesis, escritas antes: H1, cuántas entradas cambian de estado con la semilla con la regla de antes (descriptiva); H2,
ninguna con la regla nueva; H3, con la regla nueva el estado es ABSTENCION donde el inventario dice que el ligando coordina un ion y
REVISAR donde no.

## Qué pasó

| Medida | Resultado |
|---|---|
| Entradas evaluables (las 5 semillas en los dos brazos) | 41 de 43 (1VKG y 5I3T: Meeko rechaza el receptor en las 10 corridas) |
| H1: cambian con la semilla, regla de antes | 0 de 41 (IC 95 % 0–0,086) |
| H2: cambian con la semilla, regla nueva | 0 de 41 (IC 95 % 0–0,086) |
| H3: coinciden con el inventario, regla nueva | 37 de 39 |
| Pose top-1 idéntica entre brazos | 205 de 205 pares |
| Estados, regla de antes | 200 ABSTENCION, 5 REGISTRADO |
| Estados, regla nueva | 160 ABSTENCION, 40 REVISAR, 5 REGISTRADO |

Las dos discrepancias de H3 tienen la misma causa. En 5E92 el ANP coordina dos Mg (a 1,94 y 2,05 Å) y en 9GKV el SHH coordina un Zn
(2,15 Å, por N1, O1 y O2), pero la regla nueva dio REVISAR y escribió que el ligando no toca ninguno. El lector de coordenadas de
`services/dossier/contexto_estructural.py` toma el elemento de las columnas 77 a 79, y en estos depósitos la 79 es la carga: el Mg
se lee «MG2» y el Zn «ZN0», que no están en la lista de metales. En 9GKV, además, los hidrógenos se leen «H0» y contaban como
átomos pesados. Es un defecto de implementación, no una diferencia declarada del criterio, así que por el registro previo cuenta
como fallo.

En los demás casos la regla hace lo que dice. 1RKP pasa de ABSTENCION a REGISTRADO (el Zn queda a 6,52 Å del cristal), 6KE5 de
ABSTENCION a REVISAR (el Ca está a 4,06 Å y el ligando no lo coordina) y 4NY4 de REGISTRADO a REVISAR (el ligando coordina el Fe del
hemo, N32–Fe a 2,58 Å).

## Qué dice y qué no dice

- En este panel la decisión sobre metales no dependía de la semilla, tampoco con la regla de antes. El caso de 1RKP en ABS-TR-01 no
  se repite aquí como inestabilidad: las cinco semillas dan poses distintas, pero todas dejan el Zn entre 5,14 y 5,25 Å, por
  debajo del umbral de 6 Å. Con otro ligando o con otro umbral podría no ser así; este panel no lo mide.
- La regla nueva no puede integrarse hasta que el lector reconozca el elemento con la carga escrita al lado, y hasta repetir el brazo
  nuevo con ese arreglo.
- No dice si abstenerse o pedir revisión es la decisión correcta para cada metal: no hay etiquetas de la función del metal.
- No dice nada de la calidad del docking.
