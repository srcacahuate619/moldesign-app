# RS-04-QC

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El strain MMFF94s es tecnicamente viable sobre las poses train de la union original

## Protocolo

Referencia: `CAMPANA-2-PLAN sellado (41b7f09) IT1 QA-5/QA-6`

## Gate

Mapeo biyectivo >=99%; pesados no se mueven; cobertura >=95%; determinismo; cold-start P95 <=5s/ligando; cacheado P95 <=100ms/pose y <=3s/complejo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `41b7f09d1a864e9c8fde60bc0fc4c5dc7215c519`, dirty=True

## Estado

- Creado: 2026-08-16T22:40:29.779294+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T22:57:44.374672+00:00)
- Finalizado: 2026-08-16T22:57:44.736359+00:00
- Razón de la decisión: QC tecnico PASS: mapeo biyectivo 99.49% (>=99%), pesados no se mueven (0.0A exacto), cobertura MMFF94s 116/116 ligandos (>=95%, sin UFF), determinismo byte-identico, cold-start P95 55.7ms (<=5s), cacheado P95 68.0ms/pose (<=100ms) y 1726ms/complejo (<=3s). 14 poses degeneradas (1kpm, 1nm6) parametrizadas como no computables. RS-04 OOF puede proceder.
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
