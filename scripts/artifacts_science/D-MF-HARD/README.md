# D-MF-HARD

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Existe una cohorte dificil bien definida (rot_bonds>=15) con controles faciles emparejados en train+val para medir regresiones de MolFlex sin re-docking

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md (D-MF-HARD, entregable 6) + MF-01/MF-01-UNION`

## Gate

22 hard + 22 controles emparejados, universo 156, 0 denylist, 0 test, determinismo byte a byte, oracle_gap no decide nada

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `c04b3d7ba01b1c4d48713d5d1ac0aba803e6c54a`, dirty=True

## Estado

- Creado: 2026-08-16T05:13:15.701226+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T05:15:36.591375+00:00)
- Finalizado: 2026-08-16T05:15:36.978264+00:00
- Razón de la decisión: PASS OPERACIONAL: cohorte 22 hard (17 train + 5 val) + 22 controles emparejados sin reemplazo; universo 156; 0 denylist; 0 test; historical_timeout solo de registros originales; oracle_gap secundario y sin poder de decision; determinismo byte a byte. Sin resultado cientifico todavia; val (5 dificiles) es solo verificacion piloto
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
