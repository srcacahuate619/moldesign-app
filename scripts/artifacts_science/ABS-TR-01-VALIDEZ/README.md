# ABS-TR-01-VALIDEZ

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La decision de Preparacion (detenerse, avisar, seguir) sobre los 29 sistemas reales de ABS-TR-01 coincide con la del panel ciego de revisores: falso bloqueo con limite superior unilateral 95 % <= 10 % y ninguna falsa autorizacion

## Protocolo

Referencia: `scripts/artifacts_science/ABS-TR-01-VALIDEZ/entrada/REGISTRO_PREVIO.md`

## Gate

NO_GO si falsa autorizacion en un sistema que detienen los cinco revisores o limite inferior 95 % del falso bloqueo > 10 %; GO si limite superior <= 10 % y ninguna falsa autorizacion; si no, INCONCLUSIVE

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `claude/abs-tr-01-validez`, commit `be59c74a1db3160668d1f9c51a82504f437e8fd0`, dirty=True

## Estado

- Creado: 2026-10-22T16:38:20.802644+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-10-22T16:56:54.198948+00:00)
- Finalizado: 2026-10-22T16:56:54.310453+00:00
- Razón de la decisión: Sin falsa autorizacion (0/10; Preparacion nunca dice seguir), pero falso bloqueo 3/18 = 16,7 % (limite unilateral 95 % 4,7-37,7 %): por encima del objetivo del 10 % en la estimacion puntual y sin potencia para concluir con 18 negativos. 4 de 10 sistemas que el panel detiene pasan con aviso (4NY4, 6SXC, 6HW5, 3G0E). 8WTW sin auditoria: el producto falla al preparar el receptor.
- Hashes de dataset: 120 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

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
