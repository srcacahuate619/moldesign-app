# VISION-MOLECULAR-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Alguna de seis alternativas para la elevacion 2D a 3D de ligandos grandes (E1 dibujo ajustado al 3D, E2 dE con xTB, E3 plegado restringido al dibujo, E4 ventana de energia, E5 enderezar cadenas y girar colas, E6 animacion por torsiones) mejora el producto 26df919c segun el criterio de su registro previo

## Protocolo

Referencia: `docs/auditorias/elevacion-grandes-2026-10-24/REGISTRO_PREVIO.md (E1-E3, fcbb9d1e), REGISTRO_PREVIO_E4.md (4517768f), REGISTRO_PREVIO_E5.md (aa22435e), REGISTRO_PREVIO_E6.md (74b2d17f)`

## Gate

Cada experimento con el criterio de su registro previo, commiteado antes de su resultado; el conjunto es GO si alguna alternativa cumple y entra en el producto

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `b468858de789b6a2252d27a3604b0b87a19cc89b`, dirty=True

## Estado

- Creado: 2026-10-25T16:39:42.626696+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-10-25T16:40:27.374706+00:00)
- Finalizado: 2026-10-25T16:40:30.107342+00:00
- Razón de la decisión: Seis alternativas para la elevacion 2D a 3D de ligandos grandes, cada una con registro previo commiteado antes de su resultado: E1 dibujo ajustado NO_GO (rescata 10 de 25, hacia falta 75 %), E2 dE con xTB parcial (ALPB = 0,69 MMFF), E3 plegado restringido NO_GO (5 de 37, hacia falta <= 4), E4 ventana de 5 kcal/mol NO_GO (abstencion 8 -> 23 en G37), E5 cadenas y colas NO_GO (8 -> 7, hacia falta <= 4), E6 torsiones NO_GO (2 cruces con linea recta, hacian falta >= 4). Ninguna entra en el producto (26df919c).
- Hashes de dataset: 13 archivo(s) con SHA-256
- Hashes de assets: 10 archivo(s) con SHA-256

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
