# MF-11

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El clustering label-blind por RMSD pocket-frame a 2.0A reduce candidatos redundantes de la union sin perder cobertura de oraculo

## Protocolo

Referencia: `docs/49 15 (entregable 9) + MF-01-UNION/DESIGN.md`

## Gate

0 complejos cubiertos perdidos; reduccion reportada; determinismo byte a byte; label-blind verificado

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `37e35913c9ef92705ad4a284fd96197e8c37b022`, dirty=True

## Estado

- Creado: 2026-08-16T18:52:57.502583+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-16T19:16:23.017694+00:00)
- Finalizado: 2026-08-16T19:16:23.477065+00:00
- Razón de la decisión: MF-11 NO_GO: el clustering label-blind identity-first a 2.0 A redujo 23.55% los candidatos y fue determinista, pero perdio 2/108 complejos cubiertos (1alw, 1bcd), incumpliendo el gate primario de preservacion exacta del oraculo. El artefacto permanece como caracterizacion de una politica lossy, no como dataset recomendado para rescoring. Desviaciones registradas: D1 val procesado junto con train; D2 primera identidad en vez de medoid geometrico.
- Hashes de assets: 12 archivo(s) con SHA-256

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
