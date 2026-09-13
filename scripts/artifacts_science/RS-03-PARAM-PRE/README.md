# RS-03-PARAM-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La parametrizacion OpenFF Sage + NAGL congelado sobre los 116 ligandos train es una base fisica correcta (cobertura, determinismo, carga, cero fallback) que reemplaza el tipado heuristico

## Protocolo

Referencia: `CAMPANA-2-PLAN sellado (41b7f09) IT1 QA-2; politica de prerregistro separado del laboratorio`

## Gate

Ver §4 del PREREGISTRO: cobertura >=95% global y >=90% por estrato; |sum q - formal| <= 1e-4; determinismo <=1e-6; cero fallback silencioso; cero val40/test/CONFIRM

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `89ee66ba41b89eccee2e85d54eac032dd7d62869`, dirty=True

## Estado

- Creado: 2026-08-17T00:32:21.371251+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T00:33:33.939585+00:00)
- Finalizado: 2026-08-17T00:33:34.368408+00:00
- Razón de la decisión: Prerregistro GO procedimental: contrato de RS-03-PARAM congelado (hipotesis, 6 estratos, 11 requisitos primarios, regla AM1-BCC estratificada, forecast, caveat RS-08, politica de prerregistro separado). Sin resultados. La ejecucion es RS-03-PARAM (experimento separado) y requiere autorizacion de instalacion del entorno (openff-toolkit, openff-nagl-models, AmberTools, modelo NAGL).
- Hashes de assets: 3 archivo(s) con SHA-256

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
