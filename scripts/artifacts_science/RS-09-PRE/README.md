# RS-09-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El selector v0.6 de produccion es robusto a rotacion/traslacion rigida, al orden de poses y a perturbacion debil sigma=0.1A sobre la cohorte completa de 116 complejos train (invarianza 1e-6, orden 116/116, flips ok->mal <=2, >=60% de cambios en terciles 1-2 de margen, drift=0, aislamiento SHA)

## Protocolo

Referencia: `scripts/artifacts_science/RS-09-PRE/PREREGISTRO.md`

## Gate

GO si G1-G6 PASS; NO_GO si algun gate falla (evidencia de bug con reporte)

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `93541c9dc610d56014d19b73a2b72527d36abe41`, dirty=True

## Estado

- Creado: 2026-08-17T07:26:21.850245+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T07:26:22.329472+00:00)
- Finalizado: 2026-08-17T07:26:22.464906+00:00
- Razón de la decisión: Prerregistro procedimental sellado: hipotesis, metodos A/B/C, cohorte 116 train, gates G1-G6. Nada ejecutado bajo este registro. Ejecucion en RS-09 (run_rs09_robustez.py) con sello aparte.
- Hashes de assets: 1 archivo(s) con SHA-256

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
