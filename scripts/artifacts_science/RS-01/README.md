# RS-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La union deduplicada MF-11-R1 cambia el comportamiento de v0.6 (RS-01A in-sample) y el cross-fitting OOF muestra si la deduplicacion mejora Top-1 sin degradar RMSD (RS-01B)

## Protocolo

Referencia: `docs/49 RS-01 reformulado + MF-11-R1 sellada + bloqueadores B1-B7 (IT1); sello PARAGUAS DE PREREGISTRO: las ejecuciones y resultados se sellan por separado como RS-01A y RS-01B`

## Gate

Preregistro completo; RS-01A in-sample con lecturas A0/A1/A2 (A1 primaria); RS-01B OOF con folds del fold_plan (38 componentes, 55/16/15/15/15), gate OPERACIONAL +3 Top-1 y degradacion <=0.1A + bootstrap por 38 componentes (10000 replicas, BCa) y McNemar exacto; val descriptivo; test y D-RC-CONFIRM sellados e intocados

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9 (python-embed/python.exe, runtime planificado verificado en IT1)
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `c35e62ade4c9a864f7eaf832be8b5250df032958`, dirty=True

## Estado

- Creado: 2026-08-16T19:58:53.270297+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T20:27:16.674391+00:00)
- Finalizado: 2026-08-16T20:27:17.151107+00:00
- Razón de la decisión: Preregistro RS-01A/B sellado como paraguas tras IT1+IT2: A0/A1/A2 definidos, fold_plan 55/16/15/15/15 con claim near-identity-receptor-disjoint + Murcko-disjoint, n_estimators=52 sin ES, vista cache train-only sin leer val/test, bootstrap BCa global por 38 componentes 10000 replicas con fallback percentil, contingencias cerradas (U=None, todos los medoides empatados, mascaras de fuentes). Las ejecuciones y resultados se sellan aparte como RS-01A y RS-01B.
- Hashes de dataset: 4 archivo(s) con SHA-256
- Hashes de modelos: 2 archivo(s) con SHA-256
- Hashes de assets: 7 archivo(s) con SHA-256

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
