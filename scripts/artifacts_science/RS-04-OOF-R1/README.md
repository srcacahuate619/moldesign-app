# RS-04-OOF-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El NO_GO de RS-04-OOF es solido y su alcance es limitado a la feature, modelo y contrato

## Protocolo

Referencia: `Corrigendum narrativo del sello RS-04-OOF (a8c9523)`

## Gate

Narrativo: sin cambio de datos, sin re-evaluacion

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `a8c9523d99b227fbad842ab50f8ce8c392831bab`, dirty=True

## Estado

- Creado: 2026-08-17T00:01:51.225145+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T00:03:34.820551+00:00)
- Finalizado: 2026-08-17T00:03:35.183491+00:00
- Razón de la decisión: Corrigendum narrativo/estadistico confirmando NO_GO de RS-04-OOF: reduccion observada de 8 hits, bootstrap primario BCa por 38 componentes [-14,-1] excluye cero, McNemar p=0.115 (sensibilidad por complejo), mediana pareada 0.000A = ausencia de desplazamiento no equivalencia. NO_GO limitado a esta feature, modelo y contrato. Sello historico intacto.
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
