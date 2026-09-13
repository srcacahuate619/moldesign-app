# MF-20

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Una sola causa -la degeneracion del paisaje de puntuacion- explica los negativos de las carteras C y D a la vez

## Protocolo

Referencia: `medicion correlacional: clustering de poses del conjunto v2 a 2.0 A con el contrato de MF-11-R1; degeneracion = modos distintos empatados a D kcal/mol del mejor`

## Gate

medicion sin gates; hipotesis nueva, falsable

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:05.154807+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-19T03:53:05.931086+00:00)
- Finalizado: 2026-08-19T03:53:06.102799+00:00
- Razón de la decisión: HIPOTESIS REFUTADA en su forma interesante. La degeneracion ABSOLUTA separa (31 modos empatados a 2 kcal/mol en los no cubiertos frente a 9 en los cubiertos) pero es un ARTEFACTO DE MUESTREO: los no cubiertos tienen 252 poses medianas frente a 100, y 187 modos frente a 42. Normalizando, la FRACCION de modos empatados en la cima es 0.239 en los no cubiertos y 0.292 en los cubiertos: no solo no es mayor, es ligeramente MENOR. Lo unico no confundido -que en 32 de 32 complejos COLOCACION ninguno de los modos empatados a 1 kcal/mol es bueno- es MF-09 dicho de otra forma y no constituye informacion nueva. Limitacion declarada de antemano: la degeneracion se mide con la MISMA funcion cuyo fallo se investiga, asi que no distingue "el paisaje es degenerado" de "la funcion no resuelve": son la misma afirmacion vista de dos lados.
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
