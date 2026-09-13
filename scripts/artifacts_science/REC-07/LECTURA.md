# REC-07 — El grid «roto» de 5TUN no estaba roto donde importa

## Qué se preguntó

REC-01-R1 marcó `5TUN` con `E8_HOTSPOT_FUERA_DE_CAJA` y `margen_min = −5.147 Å`: la caja del catálogo recorta 3 de los 15 hotspots declarados. La pregunta de REC-07 era si ese defecto geométrico **se traduce en docking peor** y si un grid alternativo lo repara sin regresión.

Tres brazos, mismo receptor y mismo ligando (E64c extraído del homólogo 1ITO), única variable la caja:

| Brazo | Origen del centro | Tamaño (Å) | Hotspots dentro | `margen_min` | d(Cys25 SG) |
|---|---|---|---:|---:|---:|
| `G_DB` | catálogo | 22.0³ | 12/15 | **−5.15** | 9.10 |
| `G_MP` | MolPocket | 24.9³ | 15/15 | +2.78 | 10.36 |
| `G_ADAPT` | adaptativo por hotspots | 19.0×25.3×25.9 | 15/15 | +4.00 | **9.01** |

## Qué salió

15/15 corridas válidas (5 semillas × 3 brazos, `exhaustiveness=32`, `cpu=1`), 3661 s.

| Brazo | contacto top-1 ≤5 Å | mediana d(Cys25) | score top-1 mediano |
|---|---:|---:|---:|
| `G_DB` | **5/5** | 0.773 Å | −5.095 |
| `G_MP` | **5/5** | 0.777 Å | **−6.182** |
| `G_ADAPT` | 4/5 | 0.933 Å | −5.666 |

**El grid del catálogo pone el ligando en contacto con el nucleófilo catalítico en las cinco semillas.** El defecto que detectó la auditoría —tres hotspots recortados— es real como geometría y **no se manifiesta como fallo de docking** en este target. El único fallo de contacto de toda la tabla es de `G_ADAPT` (semilla 45: top-1 a 12.89 Å), y es fluctuación de muestreo, no del grid: en esa misma corrida el mejor de los 9 modos queda a 2.09 Å.

## Decisión: NO_GO

| Gate | Resultado |
|---|---|
| G1 contención (15/15 hotspots + 3/3 tríada en el recomendado) | PASS — `G_ADAPT` |
| G2 ancla (d ≤ 9.102 Å de `G_DB`) | PASS — 9.008 Å |
| G3 validez de docking (15 corridas) | PASS — 15/15 |
| G4 contacto catalítico (≥3 de 5 semillas) | PASS — 4/5 |
| G5 **no regresión** frente a `G_DB` | **FAIL** — 4/5 contra 5/5 |
| G6 determinismo | PASS — misma semilla, mismo score y misma distancia en los 3 brazos (−6.131/0.423, −6.318/1.51, −5.682/0.933, idénticos al repetir) |
| G7 sólo lectura del catálogo | PASS |

La regla congelada exige los siete gates para un GO. `G_ADAPT` arregla la contención y empata en el ancla catalítica, pero **no mejora el docking y pierde una semilla**: no hay evidencia para recomendar el cambio de grid. El catálogo de 5TUN se queda como está.

`G_MP` tiene el mejor score mediano (−6.182 vs −5.095) y contacto 5/5. No se recomienda igualmente, porque el prerregistro §6 prohíbe usar el score de docking para elegir el grid: eso invertiría la dirección de la validación. La regla de selección congelada es contención + ancla + menor volumen, y por ella el candidato era `G_ADAPT`.

## Lo que esto le enseña al programa

**Una excepción geométrica del catálogo no implica un fallo de docking.** REC-01 encontró 57 targets (14.7%) con al menos un código de excepción; REC-07 muestra que al menos en la severidad leve (`S4_LEVE`, que es donde cae 5TUN con sus tres hotspots recortados) el docking puede seguir siendo correcto. La cola de la auditoría no es una lista de targets rotos: es una lista de targets **a verificar**, y la verificación puede salir a favor del statu quo.

Esto acota lo que puede prometer REC-03: reparar geometría no es lo mismo que reparar docking, y el experimento tiene que medir el docking, no la caja.

## Incidencia registrada

La primera ejecución de este experimento pasó el PDB **crudo** a Meeko y conservó las 387 aguas cristalográficas como parte del receptor rígido: el bolsillo quedó ocupado por oxígenos de agua y el docking devolvió **scores positivos** (+23 a +33 kcal/mol) con 1–5 modos en vez de 9 — geometría imposible, no afinidad débil. El gate G3 de validez lo marcó FAIL, que es exactamente su función. Se corrigió la preparación (el runner ahora filtra aguas y **aborta** si el `.pdbqt` conserva líneas `HOH`) y se repitió la tanda completa. Ningún criterio de decisión se tocó entre una y otra: umbral de contacto, regla de selección y gates son los mismos que antes de esa corrida.

Aquella tanda queda descartada por inválida, **no por su resultado**.

## Archivos

- `PREREGISTRO.md` — diseño congelado antes de ejecutar, con la geometría de los tres brazos ya declarada.
- `metrics.json` — gates, geometría y agregados por brazo.
- `per_complex.jsonl` (15) — una línea por corrida: brazo, semilla, `rc`, modos, score top-1, distancia a Cys25 SG del top-1 y del mejor de 9, coste.
- `failures.jsonl` — vacío en la corrida válida.
- `scripts/run_rec07_grid_5tun.py` — runner; `scripts/rec07_determinismo.py` — gate G6.
