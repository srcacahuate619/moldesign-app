# AF-01-R1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El estratificado por receptor de AF-01 contiene un bug de clasificacion (overlap==1.0 incluye subsecuencias); la correccion por igualdad literal mueve 53 complejos de seen_exact a near_identity sin afectar el resultado global

## Protocolo

Referencia: `AF-01 (parent, sellada GO) + corrigendum del maintainer; docs/49`

## Gate

Reproducir estratos 126/108/94 con rho 0.7240/0.5135/0.5395 y CIs dentro de tolerancia

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `67c4e30a09a0c4becdf58580772b9c86f949ee6a`, dirty=True

## Estado

- Creado: 2026-08-16T04:28:19.786542+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T04:32:45.300101+00:00)
- Finalizado: 2026-08-16T04:32:54.807130+00:00
- Razón de la decisión: Corrigendum: estratos corregidos por igualdad literal de secuencia (126/108/94; rho 0.7240/0.5135/0.5395) reproducidos exactamente; subanalisis estratificado de AF-01 superseded; replica global 0.6094 intacta; pre-audit reconciliado (definiciones distintas, ambas correctas)
- Hashes de assets: 9 archivo(s) con SHA-256

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
