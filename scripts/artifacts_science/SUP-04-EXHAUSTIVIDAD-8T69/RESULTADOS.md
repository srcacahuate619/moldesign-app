# SUP-04-EXHAUSTIVIDAD-8T69 — acta de cierre

**Decisión: INCONCLUSIVE.** Δρ(`e32` − `e8`) = +0,043, IC 95 % −0,006 a +0,116 (bootstrap pareado por padre, 10 000 réplicas,
semilla 20261025; 89 padres comunes). El IC no excluye el cero, así que no es NO_GO; tampoco cabe entero en ±0,10 (lo supera por
0,016), así que no es GO. La regla del registro previo (`d43cf418`) se aplica tal como se escribió.

## Lo medido

| Brazo | Exhaustividad | Semilla del panel | Padres | ρ | ρ_peor | Redocking a ≤ 2 Å | RMSD | CPU-core-h |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| `e8` | 8 | 42 | 89 | 0,392 | 0,322 | 5/5 | 0,67–0,71 Å | 3,70 |
| `e8s43` | 8 | 43 | 89 | 0,367 | 0,297 | — | — | 3,42 |
| `e16` | 16 | 42 | 89 | 0,428 | 0,357 | 5/5 | 0,68–0,70 Å | 5,56 |
| `e32` | 32 | 42 | 89 | 0,435 | 0,365 | 5/5 | 0,69–0,72 Å | 9,78 |

ρ es la de Spearman entre −E top-1 y pKi; ρ_peor, la de peor caso sobre las asignaciones de lote (F = 1015/703). Todas las poses
del redocking pasan la validez física. Las CPU-core-h de `e8`, `e16` y `e32` incluyen sus cinco redockings.

- **Primaria:** Δρ(`e32` − `e8`) = +0,043 (IC 95 % −0,006 a +0,116).
- **Declaradas:**
  - Δρ(`e16` − `e8`) = +0,036 (IC 95 % −0,008 a +0,110).
  - **Δρ(`e8s43` − `e8`) = −0,025 (IC 95 % −0,135 a +0,078): cambiar sólo la semilla mueve ρ 0,025; cuadruplicar la
    exhaustividad, 0,043. Son del mismo orden.**
  - Energía top-1 de 8 a 32: baja más de 0,1 kcal/mol en 2 padres (los dos, más de 0,5), sube más de 0,1 en otros 2; de media
    baja 0,012 kcal/mol. ρ de Spearman entre las energías de `e8` y `e32`: 0,968.
- **Control:** `e8` repite las 89 energías top-1 de `CAL-D-01-R4-2-VMAT2-8T69` con diferencia máxima 0,0 kcal/mol.
- 371 registros terminales, todos SUCCESS; ningún fallo, ninguna deriva.

## Qué significa

- **En esta serie no se demostró que la exhaustividad 8 ordene peor que la 32, ni que ordene igual.** La diferencia observada
  favorece a 32 (+0,04), pero es del mismo tamaño que la que produce cambiar la semilla, y el IC llega a +0,12.
- **La búsqueda a 8 ya había convergido en energía** para 85 de los 89 padres: lo que cambia ρ son reordenaciones pequeñas
  entre análogos con energías casi iguales, no mínimos nuevos.
- **La pose del cristal se reproduce igual a 8, 16 y 32** (5/5, RMSD 0,67–0,72 Å).
- El sello de 8T69 en Verificados (exhaustividad 8, semilla 42) no cambia: su ρ es la de `e8`, repetida aquí exacta.
- La afirmación «exhaustividad 8: sweet spot validado» ya se había retirado (SUPUESTOS-01). Esto no la valida: queda como «el
  defecto de Vina; en 8T69 subirla a 32 no cambia la pose y mueve ρ +0,04, dentro del ruido de la semilla, con un IC que no
  descarta +0,12».
- Una sola semilla por brazo: `e8s43` es una medida del ruido de semilla, no su distribución. Repetir con varias semillas por
  brazo diría si +0,04 es efecto o ruido; ya no sería ciego.

## Límites

- Un receptor (8T69), una serie congenérica de 89 padres y una caja de 30 Å de lado. No dice nada de cajas mayores (el producto
  sube a 32 por encima de 27 000 Å³), de otros receptores ni de ligandos más flexibles.
- Mide CPU-core-h, no el tiempo que espera el usuario.
- La campaña corrió en dos tramos, sobre `3ca7f633` y `c0341284`, que sólo difieren en el PDF del dossier (ver
  `DESVIACIONES.md`).
