# D-MF-HARD-EXH4-VAL

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La ejecucion descriptiva de Vina exh4 sobre val caracteriza el comportamiento fuera de train

## Protocolo

Referencia: `D-MF-HARD-EXH4 (sello train) + FORECAST.md correcciones`

## Gate

Solo 10 val, config identica, descriptivo n=5, primera y unica ejecucion exh4 sobre val, sin poder de decision

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `a0524e3fa16b8fb3f1b15b64a9bd5d6e51dc7574`, dirty=True

## Estado

- Creado: 2026-08-16T09:57:57.236353+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T10:09:14.442531+00:00)
- Finalizado: 2026-08-16T10:09:14.806110+00:00
- Razón de la decisión: Ejecucion descriptiva val completada UNA sola vez: hard 2/5 (40%, Wilson CI95 0.118-0.769), control 2/5 (40%, mismo CI); 0 fallos ITT, 76 poses, 10 corridas. n=5 sin potencia; primera y unica ejecucion de exh4 sobre val; no ciega. K=15 y claim train sellado INALTERADOS
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 11 archivo(s) con SHA-256

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
