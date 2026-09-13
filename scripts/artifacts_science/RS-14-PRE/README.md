# RS-14-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con el denominador corregido (conjunto v2, cobertura del oraculo 79.3% y MolFlex aplicado a 116 de 116), un selector entrenado bajo el protocolo congelado de v0.6 supera al baseline de vina_score en precision condicional, evaluado leave-one-complex-out

## Protocolo

Referencia: `RS-14-PRE/PREREGISTRO.md; datos RC-F0-V2 solo train; features 224 raw con la transformacion documentada de v0.6; XGBRanker rank:pairwise con sus hiperparametros; LOCO 116 x 3 semillas; nulo por permutacion dentro de complejo`

## Gate

G1 validez de los 348 ajustes, G2 condicional > baseline con CI95 BCa pareado excluyendo cero, G3 condicional observada > percentil 95 del nulo, G4 determinismo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `0bf3cd2621784b12ad092b200586a3d16aba3a2d`, dirty=True

## Estado

- Creado: 2026-08-18T07:27:55.241290+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T07:27:55.821416+00:00)
- Finalizado: 2026-08-18T07:27:55.984908+00:00
- Razón de la decisión: Prerregistro de la REAPERTURA de la cartera D, autorizada por el maintainer, sellado antes de ejecutar. Declara lo que la seccion 19.1 exige: que cambio en el denominador. MolFlex pasa de aplicarse a 13 de 116 complejos a los 116; la cobertura del oraculo de train sube de 67.2 a 79.3 por ciento; las poses por complejo pasan de ~9 a ~162 y el conjunto de train de 2739 a 18812 poses. No es mas de lo mismo: en 38 complejos de v1 no existia pose que seleccionar y los experimentos que fallaron midieron Top-1 global sobre ese universo. La expectativa esta acotada por MF-09, que midio a nivel de pose que en los complejos cubiertos el top-1 por score acierta 7 de 15 y el top-5 acierta 14, es decir 8 de 15 recuperables. Diseno: solo train, val y test intactos; features 224 raw con la transformacion exacta de v0.6 (z por columna dentro de cada complejo mas rangos percentiles sobre las 9 de PCT_RAW); XGBRanker rank:pairwise con los hiperparametros congelados; leave-one-complex-out 116 por semilla, tres semillas. El gate se evalua sobre la PRECISION CONDICIONAL y no sobre Top-1 global, como exige la seccion 9, con la cobertura declarada como covariable. Control de nulo imprescindible por el regimen p mayor que n: 200 permutaciones que barajan las etiquetas DENTRO de cada complejo, preservando grupos y numero de poses, y la condicional observada debe superar el percentil 95. Prohibido comparar con cifras de v1 porque v0.6 se entreno sobre v1 y la tarea cambio de 9 a 162 candidatos.
- Hashes de dataset: 3 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

## Flujo de trabajo

1. `init`: crea este directorio con `manifest.json` prellenado y skeletons vacíos.
2. Ejecutar el experimento: escribir `metrics.json`, `per_complex.jsonl` y `failures.jsonl`.
3. `validate`: verifica `manifest.json` contra `manifest.schema.json`.
4. `seal`: registra los SHA-256 de datasets/modelos/binarios/assets y congela el manifest.
5. `finish`: escribe la decisión (GO/NO_GO/INCONCLUSIVE), la razón y la duración.
6. `maintain`: documenta de forma auditada los assets sellados que cambian tras el sello.

Después del `seal`, `validate` falla si cualquier archivo sellado cambia o desaparece.

## Inmutabilidad post-seal

- No se permite volver a sellar un experimento ya sellado (protege el cegamiento FND-05).
- `finish` y `maintain` son las únicas operaciones que modifican `manifest.json` después del sellado.
- `maintain` solo actualiza `assets_hashes` y registra cada cambio en `seal_maintenance`; datasets/modelos/binarios son inmutables.
- El README.md regenerado por `seal`/`finish`/`maintain` es la excepción documentada a la regla anterior.
- Los artefactos de producción permanecen fuera de este árbol (docs/49, sección 17).

## Archivos

- `manifest.json`: registro único del experimento (config, hashes, código, ambiente, salida).
- `metrics.json`: métricas agregadas del experimento.
- `per_complex.jsonl`: una línea JSON por complejo evaluado.
- `failures.jsonl`: una línea JSON por fallo.
- `README.md`: este archivo.
