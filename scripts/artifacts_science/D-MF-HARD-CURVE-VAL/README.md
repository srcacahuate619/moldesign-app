# D-MF-HARD-CURVE-VAL

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La validacion piloto de val con K=15 describe el comportamiento fuera de train

## Protocolo

Referencia: `D-MF-HARD-CURVE (sello train K=15, commit f31bfeb) + FORECAST.md`

## Gate

Solo K=15, solo 5+5 val, config identica, descriptivo n=5, K inmutable tras el resultado

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `f31bfeb94e16c3ecdc9135edf5affe7079198457`, dirty=True

## Estado

- Creado: 2026-08-16T08:02:33.121514+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T08:16:45.698222+00:00)
- Finalizado: 2026-08-16T08:16:46.065903+00:00
- Razón de la decisión: Validacion piloto descriptiva completada UNA sola vez con K=15: hard 2/5 (40%, CI95 0.118-0.769), controles 4/5 (80%, CI95 0.376-0.964); 0 fallos ITT; n=5 sin potencia (intervalos se solapan con train); K permanece 15 e inmutable; K30 no abierto
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 12 archivo(s) con SHA-256

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
