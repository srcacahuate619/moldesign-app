# MF-33-B-RET-PARTIAL

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El resultado parcial de MF-33-B-RET puede preservarse como evidencia de ejecucion incompleta sin interpretacion cientifica.

## Protocolo

Referencia: `Snapshot inmutable del output local previo; no reejecutar, completar ni derivar una decision desde el parcial.`

## Gate

INCONCLUSIVE obligatorio: n=43/48 y ausencia de retencion por-pose/raw impiden evaluar el gate preregistrado.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `8ac7950802b398540bf72a1d2fc9484102b6100a`, dirty=True

## Estado

- Creado: 2026-08-22T04:24:34.475692+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-22T04:25:05.556413+00:00)
- Finalizado: 2026-08-22T04:25:05.744058+00:00
- Razón de la decisión: Snapshot forense de 43/48 registros: sin cinco PIDs y sin datos por-pose/geometria cruda, no permite aplicar el gate de MF-33-B-RET-PRE. Se preserva sin inferencia; MF-33-B-RET-R1 es la unica repeticion valida.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 3 archivo(s) con SHA-256

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
