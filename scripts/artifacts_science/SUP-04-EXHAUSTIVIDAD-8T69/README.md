# SUP-04-EXHAUSTIVIDAD-8T69

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La exhaustividad 8 por defecto ordena la serie de 8T69 (89 Ki de VMAT2) y reproduce la pose del cristal igual que 16 y 32: subirla no cambia lo que el producto afirma

## Protocolo

Referencia: `scripts/artifacts_science/SUP-04-EXHAUSTIVIDAD-8T69/entrada/REGISTRO_PREVIO.md`

## Gate

Delta rho (e32 menos e8) con IC95 bootstrap pareado por padre: NO_GO si el IC excluye el cero por encima o el redocking de e8 deja menos semillas a <= 2 A que el de e32; GO si no es NO_GO y el IC cae dentro de +-0,10; si no, INCONCLUSIVE

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `2f5eb0e8381e6bffbb42a60bbb2656cad25edf6d`, dirty=True

## Estado

- Creado: 2026-10-26T02:49:58.904792+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-10-26T08:26:00.761726+00:00)
- Finalizado: 2026-10-26T08:26:03.401952+00:00
- Razón de la decisión: Delta rho (e32 - e8) = +0,043, IC95 -0,006 a +0,116 (89 padres): ni excluye el cero ni cabe en +-0,10. Declaradas: rho 0,392 (e8), 0,428 (e16), 0,435 (e32), 0,367 (e8 semilla 43); Delta rho por la semilla -0,025 (IC95 -0,135 a +0,078); redocking 5/5 a <= 2 A en 8, 16 y 32; 85/89 padres con la energia top-1 a < 0,1 kcal/mol. Control: e8 repite las 89 energias de CAL-D-01-R4-2.
- Hashes de dataset: 748 archivo(s) con SHA-256
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
