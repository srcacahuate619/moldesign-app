# AF-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La Fase A reproduce con inputs congelados y su holdout tiene solapamiento por receptor con el desarrollo

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md AF-01 reformulado + docs/44_RELEASE_BASELINE_2026-08-15.md`

## Gate

GO=REPRODUCED_WITH_SCOPE_LIMITATION si Spearman reproduce 0.6094 (+-0.005); NO_GO=P0 si no

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `2ba4a1dde8623da3a1875a67163434c575500a96`, dirty=True

## Estado

- Creado: 2026-08-16T04:02:38.611442+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T04:18:32.361077+00:00)
- Finalizado: 2026-08-16T04:18:41.028268+00:00
- Razón de la decisión: AF-01 replica sellada de Fase A: Spearman 0.6094 reproducido con delta 0.0 (CI95 0.5282-0.6791, n=328, seed 42, inputs congelados); REPRODUCED_WITH_SCOPE_LIMITATION — solapamiento por receptor documentado (estratos 179/55/94: 0.7138/0.3626/0.5395); el resultado NO es receptor-disjoint ni universal sobre targets nuevos; 0.8732 permanece INVALIDATED
- Hashes de dataset: 2 archivo(s) con SHA-256
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
