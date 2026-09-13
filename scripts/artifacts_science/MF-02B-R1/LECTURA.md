# MF-02B-R1 — La decisión se sostiene; la magnitud era el doble de la real

## Qué cambia

| | MF-02B (alineado) | Corregido (marco de pocket) |
|---|---:|---:|
| Recuperados de los 38 sin cobertura | 30 | **14** |
| Cobertura del oráculo en train | 67.2% → **93.1%** | 67.2% → **79.3%** |
| Ganancia | +26 puntos | **+12 puntos** |
| Control (12 cubiertos) | 9 entregan ≤2 Å | 8 |

**El gate preregistrado era «≥10 de los 38». El número corregido es 14: PASA.** La decisión **GO de MF-02B se sostiene**, y lo que este corrigendum corrige es la magnitud, no el desenlace.

No toqué el umbral al reevaluar. Cambiarlo después de ver el resultado sería exactamente el vicio que el prerregistro existe para impedir.

## Por qué estaba mal

MF-02B midió con `rmsd_best_to_crystal` de MolFlex → `AllChem.GetBestRMS`, que **alinea** las moléculas antes de comparar. El conjunto de poses etiqueta con `rmsd_pose_pocket`, **sin alinear**. Medir «¿la geometría interna coincide?» y compararlo contra un umbral que pregunta «¿está en el sitio correcto?» son dos cosas distintas.

La advertencia estaba escrita en el propio repositorio desde el 2026-08-14, en el docstring de la función que debí usar:

> «GetBestRMS ALINEA los dos mols y oculta desplazamientos — una pose movida ~4 Å del pocket puede reportar RMSD ~0. Para poses dockeadas usar ESTA función.»

**El sesgo mediano es de 1.002 Å** y tiene signo conocido: el alineado es siempre ≤ el de pocket. Por construcción MF-02B solo podía sobreestimar, y de hecho **16 complejos pierden el estatus de recuperados y ninguno lo gana**:

`1a30`, `1afk`, `1afl`, `1amw`, `1d7i`, `1dgm`, `1eld`, `1ele`, `1ew8`, `1ew9`, `1fh7`, `1fkg`, `1mmr`, `1njs`, `1nm6`, `1nw5`.

`10gs` es el caso didáctico: 2.755 Å alineado, **7.83 Å** en marco de pocket. El ligando tiene la conformación correcta y está en otro sitio.

## Sobre qué se recalculó

**Nada se volvió a ejecutar.** MF-02D reprodujo MF-02B **exactamente** —38 de 38 complejos, cero discrepancias— y conservó las poses. Son las mismas poses; cambia solo la regla con que se juzgan.

Y se juzgaron con una definición **más generosa** que la de MF-02B: mínimo sobre las **17,596 poses dockeadas** (todos los MODEL de todos los conformeros), no sobre el top-K entregado. Aun siendo más generosa, el número baja de 30 a 14. La corrección no depende de haber elegido un criterio más estricto.

## Qué sigue siendo cierto

- MolFlex se había aplicado a **13 de los 116** complejos de train; en los otros 103 la cobertura era la de `flexible_redock`.
- Aplicarlo recupera cobertura que el conjunto sellado no tenía: **+12 puntos**, de 67.2% a 79.3%.
- El conjunto sobre el que se evaluaron `RS-01`, `RS-04-OOF` y `RS-08` **seguía siendo incompleto**. El agujero era de 12 puntos, no de 26, pero era real: en 38 de 116 complejos no había pose que seleccionar.
- `MF-02A` no está afectado. Allí el alineamiento es **correcto a propósito** —mide disponibilidad conformacional, geometría interna libre en el espacio— y así quedó declarado en su prerregistro antes de ejecutar. La conclusión de que el eje conformacional está agotado se mantiene intacta.

## Qué deja de ser cierto

El 93.1%. Cualquier cosa construida encima —reconstrucción del dataset, cálculo de precisión condicional, reapertura de la cartera D— parte de **79.3%**.

## Archivos

- `PREREGISTRO.md` — la corrección declarada antes de recalcular, con el gate original intacto.
- `metrics.json` — cifras antes/después, complejos que caen, sesgo mediano.
- `per_complex.jsonl` (50) — por complejo: RMSD alineado de MF-02B, oráculo en marco de pocket sobre todas las poses y sobre el top-K, y ambos veredictos.
- Material y análisis: `MF-02D/pocket_frame.jsonl`, `scripts/analisis_pocket_mf02d.py`.
