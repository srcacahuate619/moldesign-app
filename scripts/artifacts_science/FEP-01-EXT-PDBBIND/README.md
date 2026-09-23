# FEP-01-EXT-PDBBIND

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

En PDBBind, como en los 203 (164 ambiguos -> 54 con el proton moviendose), la mayoria de la ambiguedad tautomerica de FEP-01 no mueve protones y el bloqueo real por tautomero es una minoria

## Protocolo

Referencia: `scripts/analisis_fep01ext_tautomeros.py sellado, sin modificar (sha a40a09d2e5b0), con --workspace apuntando a un espacio cuyo FEP-01/per_complex.jsonl es el de FEP-01-PDBBIND; contenedor moldesign-science del servidor, RDKit 2025.09.6. Replica previa sobre los 203 identica por registro al sello.`

## Gate

medicion sin gate: fraccion de ambiguos en los que el proton se mueve

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `ca68d06a5d207f9a86fbb73b951ec2455ae9c5be`, dirty=False

## Estado

- Creado: 2026-09-23T06:46:20.538651+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-09-23T06:51:57.040333+00:00)
- Finalizado: 2026-09-23T06:51:57.231392+00:00
- Razón de la decisión: La hipotesis se sostiene: de los 3634 ligandos de PDBBind con tautomero ambiguo segun FEP-01, el proton se mueve en 1098 (30.2%), frente a 54/164 (32.9%) en los 203; en el 70% restante la ambiguedad no cambia que atomos donan o aceptan y no bloquea un calculo FEP. Solo 2 no ambiguos mueven el proton. Replica previa en el servidor identica al sello registro por registro (203/203). Script sellado sin modificar (a40a09d2e5b0), RDKit 2025.09.6, contenedor moldesign-science. Limitacion: 684 ligandos no canonicalizables por RDKit (KekulizeException), los mismos que FEP-01-PDBBIND no pudo leer.
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
