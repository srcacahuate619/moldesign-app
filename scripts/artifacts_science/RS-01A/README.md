# RS-01A

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La union deduplicada MF-11-R1 cambia el comportamiento in-sample del checkpoint v0.6 congelado

## Protocolo

Referencia: `RS-01 preregistro sellado (d320bcd) + MF-11-R1`

## Gate

A0 reproduce el historico; A1 primaria reporta cambios con McNemar; A2 sensibilidad; 31 empates contrafactual completo; declaracion in-sample

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `a4fd528d8fde5403d2ca0f0b800a03ef60921ea2`, dirty=False

## Estado

- Creado: 2026-08-16T20:43:22.951736+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T20:59:20.862407+00:00)
- Finalizado: 2026-08-16T20:59:27.837571+00:00
- Razón de la decisión: GO procedimental de auditoria in-sample: A0 reprodujo exactamente las metricas historicas; A1 observo -4 hits Top-1, 0 recuperaciones, mediana pareada dRMSD 0.000 A y cero perdidas de cobertura del oraculo. McNemar p=0.25 y el intervalo agrupado de hits [-10, 0] no excluyo cero. El contrafactual completo mostro sensibilidad al desempate de fuente. Este GO certifica la ejecucion de la auditoria, no demuestra equivalencia, compatibilidad cientifica ni mejora generalizable.
- Hashes de dataset: 117 archivo(s) con SHA-256
- Hashes de modelos: 2 archivo(s) con SHA-256
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
