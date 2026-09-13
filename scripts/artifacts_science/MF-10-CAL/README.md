# MF-10-CAL

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El suelo del instrumento y la convergencia del minimizador determinan si el NO_GO de MF-10 es una medicion valida

## Protocolo

Referencia: `MF-10-CAL-PRE/PREREGISTRO.md; contenedor moldesign-lab; constructor de sistema de MF-10 reutilizado por import`

## Gate

C1 reportar la deriva del cristal, C2 deriva mediana < 1.0 A, C3 mejora <= 0.1 A al multiplicar por 20 el presupuesto

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `23ac6d11cfadfdbd1d98de59392ebdaa66539cee`, dirty=True

## Estado

- Creado: 2026-08-18T20:19:48.660157+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-18T20:19:49.226187+00:00)
- Finalizado: 2026-08-18T20:19:49.360823+00:00
- Razón de la decisión: Los tres gates pasan. C1/C2: el cristal minimizado bajo el protocolo identico de MF-10 se desplaza 0.401 A de mediana (p90 0.787, max 1.939), muy por debajo del ~1 A que MF-10 habria necesitado convertir; el instrumento tenia resolucion de sobra y el NO_GO de MF-10 es un negativo real, no ceguera del aparato. C3: multiplicar el presupuesto por 20 (500 -> 10000 iteraciones) mejora el delta mediano solo 0.061 A, por debajo del umbral preregistrado de 0.1 A, asi que MF-10 midio con el minimizador esencialmente convergido. Matiz que forma parte del sello: el efecto del presupuesto NO es cero -con 5-7 poses parecia nulo y con las 21 validas se ve pequeno pero real-, y aun a 10000 iteraciones el delta llega a -0.111 A, un orden de magnitud corto. Los 9 complejos que fallan son los mismos que en MF-10 con el mismo error de plantilla, lo que confirma que la causa es la preparacion del receptor.
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
