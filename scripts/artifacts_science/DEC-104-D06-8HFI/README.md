# DEC-104-D06-8HFI

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Exhaustividad 32 cambia Spearman de top-1 contra pKi en 8HFI

## Protocolo

Referencia: `scripts/artifacts_science/DEC-104-D06-8HFI/entrada/REGISTRO.md`

## Gate

IC95 pareado y margen de 0.10 con control estructural y escenarios de potencia

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `f0c64ee099f14667b12f8ae1b68d32750307b0e1`, dirty=True

## Estado

- Creado: 2026-11-15T04:34:46.947117+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-11-15T04:35:11.894269+00:00)
- Finalizado: 2026-11-15T15:29:25.073130+00:00
- Razón de la decisión: 243 de 243 corridas exitosas y receptor identico. Delta rho e32-e8 = 0.0133208, IC 95 % [-0.0623785, 0.1046783], fuera del margen de equivalencia por el extremo superior. Redocking valido 3/5 con e8 y 5/5 con e32.
- Hashes de dataset: 5 archivo(s) con SHA-256

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
