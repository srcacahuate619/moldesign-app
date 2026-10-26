# SUP-02-TOTAL-SCORE — registro previo (2026-10-25)

Escrito y commiteado **antes** de calcular ninguna correlación del `total_score`. Sale del inventario SUPUESTOS-01: la semilla de
Claude (S27) y la entrega de Sol 6.1 (C-136 a C-140) señalan, cada una por su lado, que el `total_score` no tiene medida detrás.

## La pregunta

El producto muestra un `total_score` de 0 a 100 como índice de calidad: en la tabla SAR, en Comunidad y como score certificado de
Moldex (`blockchain/certifier.py`). Sale de `scoring/engine.py::calculate_score_breakdown`:
- una sigmoide de la eficiencia de ligando, con centro de −0,42 a −0,20 y pendiente de 20 a 10 interpoladas entre 15 y 45 átomos
  pesados (`scoring/normalizer.py`);
- una penalización de potencia con umbral de −7,5 kcal/mol;
- una resta de 8 puntos por átomo por debajo de 12 átomos pesados;
- el factor de stacking, en el que hoy sólo pesa Vina.

Ninguna de esas constantes tiene una medida localizada. La pregunta es si, con todo eso, ordena mejor que el score de Vina sin
transformar. Si no lo hace, mostrarlo como índice de calidad es ciencia aparente.

## Datos (ya existen; no se corre nada)

| Serie | Fuente | n | Afinidad experimental |
|---|---|---:|---|
| 8T69 (VMAT2) | `CAL-D-01-R4-2-VMAT2-8T69`: `per_complex.jsonl` (filas `panel`) y los crudos de `_work/panel/shard-*/` | 89 | Ki de US11718618B2 (pKi) |
| 8HFI (NET) | `CAL-8HFI-01`: `per_complex.jsonl` (filas `panel`) y `_work/panel-*.json.gz` | 57 | Ki de CHEMBL853189 (pKi) |

- **Vina:** `E_kcal` de `per_complex.jsonl`, el top-1 de cada padre. Se usa `−E_kcal`, de modo que mayor es mejor.
- **total_score:** `resultado.total_score` del crudo de la misma corrida, tal como lo calculó el producto entonces. No se recalcula.
  8HFI se corrió el 2026-10-09, antes de algunos cambios del normalizador; se usa el valor que vio el usuario, y se declara.
- Las filas son exactamente las de la ρ primaria de cada experimento (89 y 57).

## Medidas

1. ρ de Spearman entre `total_score` y pKi, y entre `−E_kcal` y pKi, en cada serie.
2. **Δ = ρ(total_score) − ρ(Vina)**, con IC 95 % por bootstrap pareado: 10 000 remuestreos de compuestos, semilla 42, percentiles
   2,5 y 97,5.
3. Descriptiva: ρ de Spearman entre `total_score` y `−E_kcal` (cuánto es el `total_score` una simple transformación de Vina), y el
   número de compuestos cuyo `total_score` está en el techo (≥ 99,5) o en el suelo (≤ 0,5).

## Regla de decisión

- **GO** (el `total_score` se gana su lugar como índice): el IC 95 % de Δ excluye el cero **por encima** en las dos series.
- **DAÑO**: el IC 95 % de Δ excluye el cero **por debajo** en alguna serie (ordena peor que Vina). Se informa como NO_GO.
- **NO_GO** en cualquier otro caso: no demuestra valor añadido sobre Vina.

Consecuencia que se propondrá al propietario (no la decide este experimento):
- con NO_GO, dejar de presentar el `total_score` como índice de calidad en SAR, Comunidad y Moldex, o rotularlo en todas partes
  como el PDF ya hace («índice compuesto heredado»);
- con GO, declarar su medida junto al número.

## Lo que no es ciego

La ρ de Vina ya es conocida (0,39 en 8T69 y 0,13 en 8HFI, en sus sellos). La del `total_score` no se ha calculado ni mirado. Una
sola fila de un crudo se abrió para comprobar que el campo existe (`panel-4-1`: `total_score` 60,58).

## Límites declarados de antemano

- Dos series congenéricas, con un rango de tamaño estrecho: la normalización por átomos pesados puede importar poco dentro de cada
  una. Un NO_GO aquí no prueba que el `total_score` nunca ayude entre quimiotipos distintos; sólo que no está demostrado donde hay
  datos.
- No mide la parte de especificidad por hotspots, que sólo actúa con hotspots `curated_experimental`.
