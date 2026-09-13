# RS-01A-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El p de McNemar reportado en RS-01A estaba duplicado por un factor 2 sobre binomtest ya bilateral

## Protocolo

Referencia: `RS-01A sellada (2943a38) + RS-01B`

## Gate

p corregido b=4 c=0 -> 0.125 reproducido; sello historico RS-01A intacto

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `97970ce5ecedafa0017528f8b4ff78d1c7fdc1f2`, dirty=True

## Estado

- Creado: 2026-08-16T21:39:55.411691+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T21:44:07.205309+00:00)
- Finalizado: 2026-08-16T21:44:07.606993+00:00
- Razón de la decisión: Corrigendum estadistico: el p de McNemar de RS-01A estaba duplicado por un factor 2 sobre binomtest (ya bilateral); corregido b=4 c=0 -> p=0.125. Ningun gate ni decision cambia; el sello historico de RS-01A (2943a38) permanece intacto sin maintain.
- Hashes de assets: 8 archivo(s) con SHA-256

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
