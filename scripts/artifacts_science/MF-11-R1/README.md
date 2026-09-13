# MF-11-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El medoid geometrico con diametro controlado preserva el oraculo a un umbral mayor que identity-first

## Protocolo

Referencia: `MF-11 (NO_GO sellada, desviaciones D1/D2) + contrato original`

## Gate

Mayor umbral con 0 perdidas + degradacion mediana <=0.1A + reduccion >=10%; ablation mejor-Vina secundaria; solo train; 0 val

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `2f617ec1df1b5e70a6884e2765be122e44f4bfce`, dirty=True

## Estado

- Creado: 2026-08-16T19:26:04.167180+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T19:40:18.539411+00:00)
- Finalizado: 2026-08-16T19:40:19.115386+00:00
- Razón de la decisión: MF-11-R1 GO de desarrollo: sobre 116 complejos train y 2739 poses, la politica label-blind de diametro controlado y medoid geometrico selecciono 1.5 A mediante la regla preregistrada, reduciendo 11.90% los candidatos (2739->2413) con cero complejos cubiertos perdidos y degradacion mediana de min-RMSD 0.000 A. Val permanece excluida e inhabilitada para confirmar variantes por la desviacion D1 de MF-11; el artefacto prepara RS-01, pero no constituye validacion externa.
- Hashes de assets: 11 archivo(s) con SHA-256

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
