# CAMPANA-2-PLAN

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La cascada v0.6 + decidibilidad + strain + MM-GBSA selectivo puede mejorar la seleccion de poses sin costo indiscriminado

## Protocolo

Referencia: `docs/49 Campaña 2 + RS-01B sellada (NO_GO)`

## Gate

Inventario completo con preguntas abiertas; preregistros base sin ejecutar; orden strain -> decidibilidad -> MM-GBSA respetado

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `144705075ade1f9e2c464c9d4ddacbfd09769acf`, dirty=True

## Estado

- Creado: 2026-08-16T21:54:04.975589+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T22:21:04.523471+00:00)
- Finalizado: 2026-08-16T22:21:05.001687+00:00
- Razón de la decisión: Plan de Campana 2 sellado tras IT1/DECISIONS del maintainer: QA-1 union original primaria; QA-2 provenance estricta de cargas + RS-03-PARAM (OpenFF Sage+NAGL congelado, AM1-BCC) como prerrequisito; QA-3 router presupuestario con umbrales solo del outer-train y 30% de mayor riesgo; QA-4 single-trajectory maxIter=200 timeout 300s top-2/600s; QA-5 MMFF94s con topologia autoritativa, solo H optimizados, sin UFF, sin truncar strain; QA-6 cross-fitting completo con gate operacional (>=50/116, mediana pareada <=+0.1A, cobertura >=95%, costes P95). RS-04-QC tecnico previo sin labels.
- Hashes de assets: 7 archivo(s) con SHA-256

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
