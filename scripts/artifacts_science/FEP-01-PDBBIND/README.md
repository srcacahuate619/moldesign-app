# FEP-01-PDBBIND

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

En PDBBind completo (5332 complejos) la ambigüedad tautomérica sigue siendo el cuello de FEP-01, como en los 203 de molflex (164/203 ambiguos, ninguno declarado)

## Protocolo

Referencia: `scripts/analisis_fep_pdbbind.py 01 sobre el script sellado analisis_fep01_integridad.py sin modificar, universo data/pdbbind, en el contenedor moldesign-science (Linux, RDKit 2026.03.1) del servidor 192.168.1.64 con 3 procesos. Antes, réplica sobre los 203 con --comparar-con FEP-01/metrics.json; si no reproduce, no se interpreta la extensión. listo_para_fep exige el mapping de index_map.json, que no existe en PDBBind: se informa aparte resumen_sin_mapping (no estereo_indefinido y no tautomero_ambiguo)`

## Gate

medición sin gate: se informan las fracciones de tautómero ambiguo y estereoquímica indefinida; el criterio de mapping se declara no aplicable

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `52b3768704b39347684a9269b41d380691c72d1d`, dirty=False

## Estado

- Creado: 2026-09-22T22:21:11.469045+00:00
- Status: created
- Decisión: PENDING

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
