# RS-09

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El selector v0.6 de produccion es robusto a rotacion/traslacion rigida, al orden de poses y a perturbacion debil sigma=0.1A sobre la cohorte de complejos train con receptor disponible (109/116; 7 molflex puros sin receptor declarados no cubiertos): invarianza 1e-6, orden 109/109, flips ok->mal <=2, >=60% de cambios en terciles 1-2 de margen, drift=0, aislamiento SHA

## Protocolo

Referencia: `scripts/artifacts_science/RS-09-PRE/PREREGISTRO.md`

## Gate

GO si G1-G6 PASS sobre la cobertura efectiva (109/116 con receptor); NO_GO si algun gate falla

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9 (python-embed)
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `93541c9dc610d56014d19b73a2b72527d36abe41`, dirty=True

## Estado

- Creado: 2026-08-17T07:42:30.000000+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-17T07:43:38.879691+00:00)
- Finalizado: 2026-08-17T07:43:44.326601+00:00
- Razón de la decisión: G3 FALLA: 9 flips ok->mal bajo perturbacion sigma=0.1A (criterio <=2). G1 (invarianza rigida 109/109, max_dif=0.0), G2 (orden 109/109), G4 (95.65% cambios en terciles 1-2), G5 (drift=0) y G6 (SHA) PASS. El selector es robusto por construccion a R+t y al orden, pero sensible a perturbacion atomica; los cambios se concentran en margenes bajos (43% tercil 1 vs 3% tercil 3) => robustez condicional al margen. Cobertura 109/116 (93.97%): 7 complejos molflex puros sin receptor (10gs, 184l, 187l, 188l, 1a30, 1a99, 1ai4) declarados NO cubiertos por indisponibilidad de datos (WORK_V3 inexistente), no como fallos. Coords canonicas: lig_pos gnn_train.pt (2739/2739). Receptores con fallback vina_redock_work/dmfhard_curve_work verificado por match atomico <=1e-3 A. Detalle: scripts/artifacts_science/RS-09/DESIGN.md
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de modelos: 1 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

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
