# MF-33-B-RET-R1-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La repeticion completa del brazo B MF-33, con retencion forense, reproduce su oraculo sellado y permite distinguir ganancia de generacion de ganancia entregada por score Vina.

## Protocolo

Referencia: `Repeticion tecnica completa de 48 complejos: exh8, 9 modos, seed42, caja25A, cpu1; sin rescoring; retencion PDBQT/log/per-pose/checkpoint.`

## Gate

G0: 48/48 sin fallos; G1: oraculo ENSEMBLE reproduce B sellado dentro 0.001A en >=95%; primario McNemar top1/top5/oraculo con lectura exacta de MF-33-B-RET-PRE.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `8ac7950802b398540bf72a1d2fc9484102b6100a`, dirty=True

## Estado

- Creado: 2026-08-22T04:27:06.116733+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-22T04:27:38.660646+00:00)
- Finalizado: 2026-08-22T04:27:38.831049+00:00
- Razón de la decisión: Preregistro técnico sellado: repetición completa de 48 complejos con protocolo y gate del contrato padre, reteniendo evidencia por pose y permitiendo reanudación sin sobrescribir el parcial.
- Hashes de dataset: 3 archivo(s) con SHA-256
- Hashes de assets: 4 archivo(s) con SHA-256

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
