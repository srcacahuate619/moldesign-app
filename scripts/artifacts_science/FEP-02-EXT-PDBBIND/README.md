# FEP-02-EXT-PDBBIND

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

En PDBBind, como en los 203 (86 con huecos -> 41 con hueco en el sitio), menos de la mitad de los huecos de cadena caen en el sitio de union

## Protocolo

Referencia: `scripts/analisis_fep02ext_huecos_sitio.py sellado, sin modificar (sha fbaaaf09c1e5), --workspace con FEP-02/per_complex.jsonl de FEP-02-PDBBIND; mismo contenedor; replica previa identica al sello.`

## Gate

medicion sin gate: fraccion de huecos en el sitio

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `ca68d06a5d207f9a86fbb73b951ec2455ae9c5be`, dirty=True

## Estado

- Creado: 2026-09-23T06:46:20.941428+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-09-23T06:51:57.566394+00:00)
- Finalizado: 2026-09-23T06:51:57.777722+00:00
- Razón de la decisión: La hipotesis se sostiene: de los 1677 complejos de PDBBind con huecos de cadena, 468 (27.9%) los tienen en el sitio (8 A), 592 en la periferia y 617 lejos; 633 de 4610 huecos caen en el sitio. En los 203 era 47.7%: a escala, la mayoria de los huecos no obliga a reparar antes de declarar el receptor. Replica previa identica al sello (203/203). Script sellado sin modificar (fbaaaf09c1e5). Limitacion declarada por el propio script: un hueco lejano no garantiza que la estructura sirva para la dinamica global.
- Hashes de assets: 3 archivo(s) con SHA-256

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
