# D-MF-HARD-CURVE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La curva anidada 5/15/30 en D-MF-HARD train muestra en que K se satura la cobertura de MolFlex

## Protocolo

Referencia: `docs/49 + FORECAST.md (entregable 7) + D-MF-HARD/DESIGN.md`

## Gate

Pilot verificado con gate corregido (enmienda auditada 2026-08-16: rc=0, 1<=n_models_emitted<=9, scores FINITOS exclusivamente de REMARK VINA RESULT, identidades solo para modelos emitidos, provenance 14 campos con seed 42/42 y experiment_id); 34 train completados ITT (deviations y technical_retries fuera del ITT); regla de decision aplicada; 0 val tocado

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6a208e0a5ae8beefb058540d5555f48332226221`, dirty=True

## Estado

- Creado: 2026-08-16T06:14:08.229538+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T07:58:31.957226+00:00)
- Finalizado: 2026-08-16T07:58:40.093111+00:00
- Razón de la decisión: K=15 fijado y sellado para VALIDACION PILOTO (regla corregida aplicada: pierde 1/4 hard <=1, degradacion mediana 0.013A, 0 controles perdidos). GO NO rehabilita MolFlex en D-MF-HARD: cobertura hard 3/17 = NO_GO; K30 no es equivalente (mejora varios hard y anade 1b2h como 4o cubierto); mediana pareada 15->30 0.000A vs media -0.289A documentadas
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 15 archivo(s) con SHA-256

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
