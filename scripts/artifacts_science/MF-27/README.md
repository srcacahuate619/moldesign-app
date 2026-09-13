# MF-27

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Dentro del grupo de alta flexibilidad, algo distinto de las torsiones separa a los que convierten

## Protocolo

Referencia: `medicion: pool train + val+test (203 complejos), subgrupo con >=13 torsiones, contraste de predictores entre convertidos y no`

## Gate

medicion sin gates; MDE declarado 0.227 para n=52

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:11.003399+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:11.824034+00:00)
- Finalizado: 2026-08-19T03:53:12.024227+00:00
- Razón de la decisión: En el grupo de >=13 torsiones (52 complejos, 14 convierten) las TORSIONES dejan de discriminar (15.5 frente a 16.0, cociente 0.97). Las dos senales grandes son ocupacion de caja (0.55) y calidad del conformero (0.59). El radio de giro (0.83) discrimina mas que el numero de atomos (0.89): no es el tamano del ligando sino cuanto se extiende. 1b2h tiene 21 torsiones -el maximo del grupo- y convierte, con enterramiento 2.52 y radio de giro bajo. Se junto train con val+test deliberadamente para no repetir el error de MF-26. Advertencias: MDE 0.227 con n=52, asi que solo las senales de cociente ~0.5 son fiables; ocupacion de caja y radio de giro son casi la misma variable (una es el cubo de la otra normalizada) y no cuentan como dos evidencias.
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
