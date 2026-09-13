# MF-02A

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El eje conformacional esta agotado: anadir conformeros no mejora la disponibilidad de la conformacion bioactiva

## Protocolo

Referencia: `medicion declarada en MF-02-PRE seccion 4; curva de RMSD minimo ALINEADO (GetBestRMS) del ensemble ETKDG frente al cristal, sobre los 116 de train`

## Gate

medicion sin gates

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:21.707281+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:22.514168+00:00)
- Finalizado: 2026-08-19T03:53:22.695526+00:00
- Razón de la decisión: Artefacto que quedo sin sellar en su momento y se sella ahora para cerrar la trazabilidad de la linea. Midio la curva del techo conformacional sobre los 116 de train y concluyo saturacion entre 60 y 90 conformeros. CORRECCION POSTERIOR YA SELLADA: MF-02A-EXT rehizo la medicion sobre 5,316 complejos de PDBBind y mostro que la saturacion declarada aqui era en parte artefacto del tamano de muestra -sobre 4,636 complejos la curva sigue subiendo 86.2 -> 87.2 -> 88.1%- y que train es mas dificil que PDBBind (77.6% frente a 83.9% a K30). La conclusion cualitativa se mantiene; "satura" era demasiado fuerte.
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
