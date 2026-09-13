# MF-31

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La ocupacion de caja gobierna el fallo: es una palanca, no solo un marcador

## Protocolo

Referencia: `medicion: reanalisis de la intervencion sellada de MF-08 (144 corridas, cajas 20/30/adaptativa); test transversal y test pareado de dosis-respuesta`

## Gate

medicion sin gates; rho negativo y sustancial en el test pareado => palanca; rho ~0 => marcador

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:12.213773+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-19T03:53:13.006982+00:00)
- Finalizado: 2026-08-19T03:53:13.183548+00:00
- Razón de la decisión: LA OCUPACION ES UN MARCADOR, NO UNA PALANCA. El test transversal da rho 0.384 entre ocupacion y oraculo sobre 144 corridas, confirmando la correlacion. Pero el test pareado de dosis-respuesta -B30 a B_ADAPT, donde el cambio de ocupacion VARIA entre complejos porque la caja adaptativa se ajusta al ligando- da rho -0.054 global, +0.150 en COLOCACION (signo CONTRARIO al predicho) y -0.216 en CONTROL. Los tres cerca de cero y sin coherencia de signo. Y sin embargo apretar la caja SI mejora el oraculo: delta mediano -0.379 A con CI95 [-0.713, -0.204] y mejoran 27 de 48. El efecto es real pero NO es proporcional a cuanto se aprieta. Eso explica el resultado que MF-08 dejo sin explicar: convirtio 3 de 33 moviendo la mediana 0.82 A; si la ocupacion fuera la palanca, la ganancia se habria concentrado donde la caja se apreto mas, y no lo hizo. No invalida MF-12: predecir no requiere causalidad y un marcador sirve perfectamente para triage.
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
