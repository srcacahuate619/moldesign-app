# FEP-04

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Se puede acompanar la pose entregada de una confianza que calibra: abstenerse en los casos menos confiables sube la precision del resto

## Protocolo

Referencia: `medicion sobre los 203: tres senales calculables sin conocer la respuesta (margen de score entre modos distintos, dispersion del top-5, modos empatados a 1 kcal/mol) y curva riesgo-cobertura`

## Gate

medicion sin gates; metrica primaria de incertidumbre segun la seccion 5 del doc. 49

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:20.476473+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:21.312069+00:00)
- Finalizado: 2026-08-19T03:53:21.502228+00:00
- Razón de la decisión: LAS TRES SENALES FUNCIONAN. Precision del top-1 global 0.330; abstenerse en el 75% menos confiable la sube a 0.620 con modos empatados, 0.600 con margen y 0.580 con dispersion del top-5. Los intervalos de Wilson de los extremos apenas se solapan ([0.269,0.398] frente a [0.482,0.741]). Las tres son GRATIS: se calculan de las poses ya generadas, sin modelo entrenado ni informacion del cristal. Segundo hallazgo con consecuencia de producto: top-1 acierta 0.330, top-5 acierta 0.465 y el oraculo es 0.615. Entregar cinco alternativas en vez de una sube la cobertura util 13 puntos sin tocar el motor. Es un cambio de diseno, no de investigacion: dejar de entregar una pose y entregar K con confianza. Limitaciones: la curva es OPTIMISTA porque las senales se observan sobre los mismos datos donde se mide -un uso en produccion exige calibrar en train y medir en val/test-; a cobertura 25% quedan n=50 con CI de +-13 puntos, asi que la forma de la curva es solida pero el valor puntual no; y no se combinaron las tres senales. Nota posterior: FND-03 midio rangos por semilla de hasta 4 A por complejo, asi que esta confianza deberia incorporar repeticiones.
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
