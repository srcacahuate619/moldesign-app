# RS-08

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El router de decidibilidad accionable (solved/rescoring_actionable@2/sampling_needed) captura mas fallos recuperables que margin-only al mismo presupuesto

## Protocolo

Referencia: `CAMPANA-2-PLAN sellado (41b7f09) QA-3 + prerregistro RS-08`

## Gate

>=+3 fallos recuperables@2 vs margin-only; sin aumento de falsos escalamientos; bootstrap 38 componentes; drift presupuesto 25-35%

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `a8c9523d99b227fbad842ab50f8ce8c392831bab`, dirty=True

## Estado

- Creado: 2026-08-17T00:01:53.135510+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-17T00:03:35.759220+00:00)
- Finalizado: 2026-08-17T00:23:06.408698+00:00
- Razón de la decisión: Gate de desarrollo FAIL: fallos recuperables@2 router 3 vs margin-only 5 (requiere >=+3; BCa 38 componentes [-6,0] no excluye cero; McNemar p=0.5). Falsos escalamientos 14 vs 15 (cumple, -1). Sensibilidad: el router solo gana en presupuestos 10-20% (+1). Drift global 38.79% fuera de [25,35]. Solo 9/116 complejos son actionable@2 (47 solved, 60 sampling): espacio de mejora minimo y margin-only ya captura 5/9. GO limitado a router: NO. v0.6 sigue como selector; cascada con RS-03 pendiente de RS-03-PARAM.
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
