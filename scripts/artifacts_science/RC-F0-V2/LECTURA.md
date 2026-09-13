# RC-F0-V2 — El conjunto de poses reconstruido, con el generador aplicado a los tres splits

## Decisión: GO — los siete gates pasan

| Gate | Criterio | Resultado |
|---|---|---|
| G1 | reproducir v1 línea a línea desde los registros | **2739/730/831 idénticos**, split por scaffold 116/40/47 reproducido |
| G2 | integridad del caché de features | SHA-256 de los tres splits coinciden |
| G2b | el extractor v0.5 reproduce el caché sellado | **2087/2087 idénticas** |
| G3 | ningún complejo cambia de split | 0 movidos |
| G4 | las poses v1 conservadas mantienen etiqueta y features base | 0 discrepancias |
| G5 | cobertura v2 ≥ v1 en cada split | ✓ en los tres |
| G6 | cero poses sin features, cero NaN | 34,302/34,302 |

## El conjunto

| Split | Poses | Complejos | Oráculo v1 | Oráculo v2 |
|---|---:|---:|---:|---:|
| train | 18,812 | 116 | 67.2% | **79.3%** |
| val | 7,493 | 40 | 75.0% | **87.5%** |
| test | 7,997 | 47 | 87.2% | **97.9%** |

**34,302 poses** con **224 features** cada una: 2,087 conservadas de v1 (`flexible_redock` 1,534 + `ruta_a` 553) y **32,215 nuevas** de `molflex`.

Los porcentajes de cobertura coinciden **exactamente** con los medidos por la vía independiente sobre el material crudo (`MF-02D/pocket_frame.jsonl` y `MF-02E/pocket_frame.jsonl`). Dos caminos de código distintos, el mismo número.

## Por qué el gate de reproducción era el más importante

Antes de añadir una sola pose se reprodujo el conjunto v1 **línea a línea** desde los registros intermedios: densidad de clúster, división por grupo de scaffold con semilla 42 y emisión en orden canónico. Sin eso, ante cualquier diferencia posterior no habría forma de distinguir «las poses nuevas» de «entendí mal el contrato».

Lo mismo vale para G2b: las 2,087 poses heredadas **se recalcularon** en vez de copiarse del caché, y coinciden con él átomo por átomo. Reusar el caché habría sido más barato; recalcular permite **demostrar** que el extractor sigue produciendo lo mismo.

## Lo que cambia, y hay que decirlo

**La tarea es distinta.** Se pasa de rankear ~9 candidatos por complejo a ~169. El conjunto v2 **no es v1 ampliado**: es una tarea más parecida a la de producción. Queda **prohibido** comparar cifras de v0.6 entre v1 y v2 sin re-entrenar bajo el mismo protocolo — v0.6 fue entrenado sobre v1.

**El gradiente entre splits persiste.** train (79.3%) < val (87.5%) < test (97.9%). Era así antes (67.2 / 75.0 / 87.2) y sigue siéndolo. El split se hizo por grupo de scaffold, y los scaffolds difíciles quedaron concentrados en train. Cualquier selector entrenado ahí y evaluado en test tiene el generador a favor, y esa ventaja **no es del selector**.

**Test queda casi saturado**: 46 de 47 complejos con pose buena disponible. Lo que quede por ganar ahí es puramente selección; ya no hay techo de generación.

## Lo que este experimento NO hace

- **No entrena ni evalúa ningún selector.** La reapertura de la cartera D y la medición de precisión condicional van en su propio prerregistro, que deberá declarar el cambio de denominador con la cifra correcta.
- **No aplica la deduplicación de MF-11-R1.** Su umbral de 1.5 Å se eligió sobre la unión v1 (2,739 poses de train) con una regla explícita —mayor umbral con 0 pérdidas, degradación mediana ≤0.1 y reducción ≥10%—. La v2 es **6.9× más densa** (18,812 poses de train): reusar el *código* es reutilización, reusar el *umbral* sin re-derivarlo sería extrapolarlo a otro régimen. La re-derivación merece su propio prerregistro.
- **No toca `D-RC-CONFIRM`.**

## Archivos

- `metrics.json` — gates, cobertura por split, conteos y SHA-256 de cada archivo emitido.
- `per_complex.jsonl` (203) — por complejo: poses v1/v2, oráculo v1/v2 y cobertura.
- Datos en `data/pose_selector_dataset/v2/`: `poses_{train,val,test}.jsonl` (34,302) y `features_rich_v2.jsonl` (40 MB, 215 ricas por pose). Fuera del árbol de artefactos por tamaño (§17 del doc. 49).
- `scripts/build_dataset_v2.py`, `scripts/build_features_v2.py`, `scripts/verificar_reproduccion_dataset.py`.
