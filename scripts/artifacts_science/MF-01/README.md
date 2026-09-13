# MF-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Las fuentes existentes difieren en cobertura de oraculo por estrato de flexibilidad sobre train/val

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md MF-01 + FND-06 provenance`

## Gate

Tabla de cobertura reproducible; sin scoring ni union en esta fase

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `67c4e30a09a0c4becdf58580772b9c86f949ee6a`, dirty=True

## Estado

- Creado: 2026-08-16T04:27:47.300365+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-16T19:16:45.813859+00:00)
- Finalizado: 2026-08-16T19:16:46.232047+00:00
- Razón de la decisión: MF-01 NO_GO (gate cientifico, entregable 10): MolFlex aporto 0 complejos nuevos en D-MF-HARD con las poses existentes; la curva 5/15/30 sellada mostro cobertura hard 17.6% a K15 frente a 64.7% de Vina flexible exh4 (entregable 8 sellado GO) con ~1/3 del coste; la union sin MolFlex cubre 69.2%. Decision: NO ampliar MolFlex. Insumos: entregables 7 (K=15 sellado), 8 (train GO + val descriptivo), 9 (MF-11 NO_GO sellado).
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
