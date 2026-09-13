# MF-13 — Los dos fallos coexisten: ~70% búsqueda, ~30% puntuación (o preparación)

## Diagnóstico: MIXTO — y por un solo complejo

| Gate | Criterio | Resultado |
|---|---|---|
| G1 validez | ≥95% de complejos con score finito del cristal | PASS — **116/116** |
| G2 diagnóstico | fracción de COLOCACION donde el cristal relajado gana al mejor dock | **0.697** |

Umbrales preregistrados: **≥0.70 → BÚSQUEDA**, **≤0.30 → PUNTUACIÓN**, intermedio →
**MIXTO**. El resultado es **23 de 33 = 0.6970**, tres milésimas por debajo del corte.
Con 24 de 33 (0.727) habría sido BÚSQUEDA.

**Se predijo BÚSQUEDA y no se acertó.** El prerregistro prohíbe mover el umbral
después de ver la fracción, así que el diagnóstico queda MIXTO. 10 min, 116 complejos.

## Los números

| Estrato | n | Cristal local gana | Ventaja local mediana | Percentil del cristal | Deriva local |
|---|---:|---:|---:|---:|---:|
| COLOCACION | 33 | **23 (0.697)** | **+2.39 kcal/mol** | 0.0 | 0.322 Å |
| CONTROL | 15 | 8 (0.533) | +0.64 | 0.0 | 0.304 Å |
| RESTO | 68 | 45 (0.662) | +0.86 | 0.0 | 0.253 Å |

## Lo que MIXTO significa aquí, que no es «no sabemos»

La banda 0.30–0.70 estaba en el prerregistro precisamente para este caso: **los dos
modos de fallo son reales y conviven**. No es un resultado nulo, es la medición de la
mezcla.

**En ~70% de los complejos difíciles el fallo es de búsqueda, y es flagrante.** El
percentil mediano del cristal es **0.0 en los tres estratos**: en el complejo mediano,
la pose cristalográfica puntúa mejor que **todas** las poses dockeadas. La ventaja
mediana es +2.39 kcal/mol y llega a +8.80. Y la deriva local de 0.32 Å confirma que el
cristal **es un mínimo local estable** de la función de Vina.

Es decir: el óptimo de la función está donde debe estar, y el buscador nunca llega —
con 86 confórmeros, 9 modos por confórmero, tres tamaños de caja y ~751 poses por
complejo.

**En ~30% el decoy gana, y ahí ninguna búsqueda ayuda:**

| Complejo | Cristal local | Mejor dock | Desventaja | RMSD top-1 |
|---|---:|---:|---:|---:|
| `1fkh` | −1.631 | −9.249 | **−7.62** | 7.87 |
| `1eld` | −4.793 | −9.372 | −4.58 | 6.32 |
| `1afl` | −4.707 | −8.651 | −3.94 | 11.45 |
| `1jq8` | −7.679 | −10.712 | −3.03 | 4.02 |
| `1ew8` | −2.181 | −4.687 | −2.51 | 3.96 |

Más `1ew9`, `1d9i`, `1dgm`, y dos empates prácticos: `1l83` (−0.30) y `1d7i` (−0.14).

## La pista que no se buscaba: parte de ese 30% no es puntuación, es preparación

Un cristal que puntúa **−1.63** (`1fkh`) o **−2.18** (`1ew8`) kcal/mol no es un fallo
de la función de puntuación: es un sistema mal montado. Ningún ligando cristalizado
une así de mal.

En esos complejos lo más probable es que **falte algo del receptor** —un cofactor, un
metal, una agua estructural— o que la protonación esté mal. Eso no es cartera C: es
**`REC-04` y `REC-05`**, que ya eran la prioridad de la cartera B por la §19.1.

Se registra como **hipótesis, no como conclusión**: este experimento no la puso a
prueba y separarla exige su propio diseño.

## La comprobación de cordura, declarada y cumplida

El prerregistro predijo que **CONTROL se comportaría al revés** que COLOCACION, porque
allí la pose dockeada ya está cerca de la nativa y viene optimizada. Observado: 0.533
frente a 0.697. La inversión sale en la dirección declarada, lo que dice que el
montaje mide lo que cree medir.

## Sondeo declarado

El sondeo de 3 complejos previo al prerregistro **descubrió y corrigió un defecto del
montaje**: `--local_only` no escribe `REMARK VINA RESULT`, así que el score de la pose
relajada devolvía nulo y había que re-puntuarla —el mismo patrón que ya usa `molflex`.
Sin ese arreglo, el gate se habría evaluado sobre la comparación cruda en lugar de la
justa.

## Consecuencia para el programa, con su prohibición

`MF-09` decía «es muestreo, no puntuación». `MF-13` lo matiza: **es muestreo en ~2/3 y
puntuación —o preparación— en ~1/3**.

El prerregistro prohíbe la lectura fácil: un componente de búsqueda **no** autoriza
reabrir `MF-03`, `MF-04`, `MF-05`, `MF-07` ni `MF-12`. Esos ajustan **parámetros del
mismo buscador**, y `MF-02F` ya mostró que triplicar los reinicios no basta. Un
componente de búsqueda justifica un **buscador distinto**, no más parámetros del mismo.

## Lo que este experimento NO dice

- **No mide si Vina puede encontrar la pose**, sólo si la reconoce cuando se la dan.
- **No compara funciones de puntuación**: si se quisiera una alternativa, exige su
  propio experimento.
- **No toca val, test ni `D-RC-CONFIRM`.**

## Archivos

- `PREREGISTRO.md` (en `MF-13-PRE`, escrito y con hash registrado antes de ejecutar).
- `metrics.json` — resumen por estrato, fracciones, ventajas medianas, percentiles, deriva local y diagnóstico.
- `per_complex.jsonl` (116) — score del cristal, del cristal relajado y del mejor dock, ventaja, percentil y deriva.
- `scripts/run_mf13_score_nativo.py`.
