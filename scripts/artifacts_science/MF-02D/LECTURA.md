# MF-02D — El material está; la cobertura que prometí, no

## Decisión: NO_GO

| Gate | Criterio | Resultado |
|---|---|---|
| G1 validez | ≥95% completan sin error | PASS — 116/116 |
| G2 **material** | todo complejo con éxito deja sus poses en disco | PASS — 116/116, **17,596 poses** dockeadas |
| G3 **reproducción** | reproduce la decisión de MF-02B en los 38 sin cobertura | PASS — **38/38 exacto, cero discrepancias** |
| G4 no regresión | la unión no reduce la cobertura de ningún complejo | PASS — 0 pérdidas |
| G5 **cobertura** | cobertura de train con la unión ≥90% | **FAIL — 79.3%** |

El experimento **produjo lo que tenía que producir** —el material de referencia, 116 complejos con sus poses, `index_map.json`, receptor y centro de caja— y demostró que el pipeline es determinista hasta la última decisión. Pero **falla el gate de cobertura**, y falla porque el umbral se fijó sobre una cifra que estaba mal medida.

## Por qué el umbral estaba mal puesto

Puse G5 en ≥90% porque MF-02B decía 93.1%. Ese 93.1% se calculó con `rmsd_best_to_crystal` de MolFlex, que usa `AllChem.GetBestRMS` y **alinea las dos moléculas antes de comparar**. El dataset de poses etiqueta con `rmsd_pose_pocket`: RMSD en el marco del pocket, **sin alinear**.

El propio repositorio lo dejó escrito como lección de auditoría el 2026-08-14, en el docstring de la función:

> «`rmsd_pesados` usa `AllChem.GetBestRMS`, que ALINEA los dos mols y oculta desplazamientos — una pose movida ~4 Å del pocket puede reportar RMSD ~0. GetBestRMS sigue siendo correcto para cobertura de conformeros; para poses dockeadas usar ESTA función.»

Comparar el RMSD alineado contra el umbral de 2.0 Å del dataset es apples-to-oranges, y sesga siempre en la misma dirección: el alineado es **≤** el de pocket, nunca mayor.

`10gs` es el caso de manual: MolFlex reporta **2.755 Å** alineado; la pose entregada está a **7.83 Å** del sitio bioactivo. La geometría interna del ligando es correcta — simplemente está en otro sitio.

## La métrica correcta, y el número que sí vale

**Primaria**: mínimo `rmsd_pose_pocket` sobre **todas** las poses dockeadas (`conf*.out.pdbqt`, todos los MODEL de todos los conformeros). Es el conjunto exacto que consume `build_pose_selector_dataset.py` en su fuente S2, así que es el oráculo que tendrá el dataset reconstruido.

| | Alineado (heredado, **inflado**) | Marco de pocket (**correcto**) |
|---|---:|---:|
| Cobertura del oráculo en train | 67.2% → **93.1%** | 67.2% → **79.3%** (78 → 92 de 116) |
| Complejos recuperados de los 38 | 30 | **14** |

**12 complejos que la métrica alineada contaba como recuperados no se sostienen**: `1a30`, `1afk`, `1amw`, `1d7i`, `1dgm`, `1ew8`, `1ew9`, `1fh7`, `1fkg`, `1mmr`, `1njs`, `1nw5`.

La ganancia real es de **+12 puntos**, no de +26. Sigue siendo un cambio material del denominador, y sigue siendo cierto que MolFlex se había aplicado a 13 de 116 complejos. Pero el titular anterior era casi el doble de lo que hay.

## Qué sobrevive

- **El material.** 17,596 poses sobre 116 complejos (mediana 171 por complejo), con su mapa de índices y su receptor. Es válido, es reutilizable y no depende de qué métrica se use para juzgarlo. Ese era el producto de este experimento y está entregado.
- **El determinismo.** 38 de 38 complejos reproducen la decisión de MF-02B átomo por átomo. El pipeline no tiene variabilidad oculta.
- **El hallazgo cualitativo**: aplicar el generador a los complejos que nunca lo recibieron recupera cobertura que el conjunto sellado no tenía.

## Qué no sobrevive

El número. `93.1%` no es la cobertura del oráculo de train; es **79.3%**. Y cualquier cosa que se construya encima —reconstrucción del dataset, reapertura de la cartera D, cálculo de precisión condicional— tiene que partir de 79.3%.

## Coste

Mediana **319 s por complejo**, ~13.4 h de CPU en total, 1.35 h de reloj con 10 procesos. El material vive en `data/molflex_train_v2/` (fuera del árbol de artefactos, §17 del doc. 49; ignorado por git por tamaño).

## Archivos

- `PREREGISTRO.md` (en `MF-02D-PRE`, sellado antes de ejecutar).
- `metrics.json` — gates, cobertura en ambas métricas (la alineada se conserva **solo como auditoría**, etiquetada como tal), reproducción de MF-02B y coste.
- `pocket_frame.jsonl` (116) — por complejo: oráculo de generación y de top-K en marco de pocket, número de poses dockeadas, y qué habría contado la métrica alineada.
- `per_complex.jsonl` (116) — resumen por complejo con ambas métricas.
- `corridas.jsonl` (116) — una línea por ejecución de MolFlex.
- `scripts/run_mf02d_generacion_registro.py`, `scripts/analisis_pocket_mf02d.py`.
