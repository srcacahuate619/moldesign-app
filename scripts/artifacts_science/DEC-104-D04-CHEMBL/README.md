# DEC-104-D04-CHEMBL

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El error de pKa de la tabla depende de la clase y del entorno

## Protocolo

Referencia: `scripts\artifacts_science\DEC-104-D04-CHEMBL/entrada/REGISTRO.md`

## Gate

Comparacion de mediana por clase en andamios retenidos y cobertura en las dos cohortes

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `f0c64ee099f14667b12f8ae1b68d32750307b0e1`, dirty=True

## Estado

- Creado: 2026-11-15T05:25:34.944263+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-11-15T05:25:36.150544+00:00)
- Finalizado: 2026-11-15T15:06:04.966991+00:00
- Razón de la decisión: Amidina y amina_alifatica pasan el gate de mejora descriptiva y merecen contraste microscopico; la cobertura directa de ambos corpus no autoriza sustituir valores
- Hashes de dataset: 2 archivo(s) con SHA-256

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
