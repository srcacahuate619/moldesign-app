# MF-12-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Prerregistro de MF-12: se puede predecir el fallo de colocacion antes de dockear

## Protocolo

Referencia: `MF-12-PRE/PREREGISTRO.md`

## Gate

G1 validez, G2 superioridad sobre baseline mayoritario en el nivel L, G3 honestidad de niveles

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:52:57.835075+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:52:58.601732+00:00)
- Finalizado: 2026-08-19T03:52:58.789349+00:00
- Razón de la decisión: Prerregistro escrito antes de ejecutar. Declara el problema de fuga -tres predictores de MF-24 usan la pose cristalografica y la caja misma es center_from_crystal_ligand-, separa dos niveles de disponibilidad, y declara el efecto minimo detectable (0.136) ANTES de correr, aplicando por primera vez la regla que la seccion 20.9 propuso a partir del fallo de RS-14. Declara ademas una prediccion tibia (GO marginal o NO_GO, 0.55-0.65 en L) que el resultado contradijo.
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
