# RS-03-PARAM-B-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La referencia AM1-BCC estratificada caracteriza las cargas NAGL por atomo sin usarse como selector (prohibido RMSD/Top-1)

## Protocolo

Referencia: `RS-03-PARAM-PRE sellado (7dfa3b8) sub-prerregistro B; contenedor Ubuntu, AmberTools antechamber+sqm, Sage 2.2.1`

## Gate

Cero val40/test/CONFIRM; reporte por atomo/estrato/dipolo/energias; sin seleccion por RMSD/Top-1; sin claim de aceptacion NAGL

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `7dfa3b845a0622fce2a1315275381e1d7d5b933f`, dirty=True

## Estado

- Creado: 2026-08-17T03:56:14.825136+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T04:01:58.909506+00:00)
- Finalizado: 2026-08-17T04:01:59.063833+00:00
- Razón de la decisión: Sub-prerregistro procedimental: contrato refinado del PRE maestro (7dfa3b8) con entorno contenedor Ubuntu real. Sin resultados.
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
