# MF-01-UNION

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Las poses existentes pueden materializarse en una union trazable sin re-docking, con geometrias y enlace a provenance

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md 15 (entregable 4) + MF-01/DESIGN.md`

## Gate

2739+730 poses, 156 complejos, 447 corridas, 0 colisiones, 0 sin provenance, determinismo byte a byte, sin acceso a test

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `00af7fa74fd9afe231a1fae341fc276336553002`, dirty=True

## Estado

- Creado: 2026-08-16T04:45:36.612063+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T04:48:46.619516+00:00)
- Finalizado: 2026-08-16T04:48:54.031468+00:00
- Razón de la decisión: PASS OPERACIONAL: union materializada 2739+730 poses, 156 complejos, 447/447 corridas de provenance, 0 colisiones, 100% PDBQT real, determinismo byte a byte, sin acceso a test. NOTA: el gate CIENTIFICO de MF-01 permanece NO_GO (MolFlex 0 complejos en D-MF-HARD; decision en RS-01); este GO es exclusivamente operacional sobre el artefacto
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 11 archivo(s) con SHA-256

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
