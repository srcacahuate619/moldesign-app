# RS-01B

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La deduplicacion mejora Top-1 OOF sin degradar RMSD pareado

## Protocolo

Referencia: `RS-01 preregistro sellado + RS-01A sellada`

## Gate

+3 Top-1 OOF Y mediana pareada RMSD <=0.1 A; bootstrap BCa por 38 componentes 10k; val/test/CONFIRM intocados

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `97970ce5ecedafa0017528f8b4ff78d1c7fdc1f2`, dirty=True

## Estado

- Creado: 2026-08-16T21:12:18.565232+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-16T21:44:16.592082+00:00)
- Finalizado: 2026-08-16T21:44:17.051882+00:00
- Razón de la decisión: NO_GO operacional: la deduplicacion con umbral anidado obtuvo 43/116 aciertos Top-1 OOF frente a 47/116 del brazo original, delta=-4, incumpliendo el gate preregistrado de >=+3. La mediana pareada dRMSD fue 0.000 A y cumplio el limite de 0.1 A. El bootstrap primario por componentes [-8.80, 4.00] y McNemar exacto bilateral p=0.480682 no establecen superioridad ni degradacion estadistica. El artefacto deduplicado queda opcional y no se adopta como entrada predeterminada de v0.6.
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
