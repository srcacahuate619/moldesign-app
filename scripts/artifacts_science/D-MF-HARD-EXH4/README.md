# D-MF-HARD-EXH4

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Vina flexible exh4 con seed explicito produce cobertura comparable a MolFlex K15 en D-MF-HARD train

## Protocolo

Referencia: `FORECAST.md (correcciones 47a24a8) + docs/49`

## Gate

34/34 train gate enmendado; G1 ejecucion; G2 cuatro niveles; comparacion CPU-ajustada vs MolFlex K15; cobertura/N descriptiva; 0 val

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `47a24a8dff4cd6fc28285f6a1e661a371634a1d1`, dirty=True

## Estado

- Creado: 2026-08-16T09:33:05.884412+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T09:59:04.655296+00:00)
- Finalizado: 2026-08-16T09:59:12.868052+00:00
- Razón de la decisión: En D-MF-HARD train, AutoDock Vina 1.2.7 con ligando flexible, receptor rigido, exhaustiveness 4 y seed 42 fue superior a MolFlex K15 en cobertura hard: 11/17 frente a 3/17; discordancias b=8, c=0; McNemar exacto bilateral p=0.0078125. El coste hard fue 0.670 CPU-h medido frente a 2.214 CPU-h P50 estimado para MolFlex, sin tradeoff de coste bajo el estimador preregistrado. El claim se limita a esta cohorte de desarrollo y a redocking/generacion con pocket conocida, box y conformacion inicial cristalograficos. Frente a la union en hard y frente a MolFlex K15 en controles, el resultado permanece inconcluso. Sensibilidad: Bonferroni post hoc sobre 6 comparaciones G2, p_adj=0.046875 (no parte del preregistro).
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 13 archivo(s) con SHA-256

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
