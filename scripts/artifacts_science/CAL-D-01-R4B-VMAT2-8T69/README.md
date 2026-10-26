# CAL-D-01-R4B-VMAT2-8T69

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Reanálisis enmendado de CAL-D-01-R4 sin el compuesto 4-67 (fallo persistente del producto): con los 88 scores ya medidos, el límite inferior del IC95 % de rho y el de rho de peor caso son > 0. No es confirmatorio: la enmienda se redactó después de ver los scores.

## Protocolo

Referencia: `scripts/artifacts_science/CAL-D-01-R4B-VMAT2-8T69/entrada/protocolo.json`

## Gate

R4 con una sola enmienda: un fallo persistente del producto en un compuesto, declarado con su nombre, no impide el criterio si quedan >= 85 padres evaluados; el criterio P1 (IC95 inferior de rho y de rho_peor > 0, puerta de pose superada) no cambia. Decisión INCONCLUSIVE por construcción: criterio enmendado tras ver los datos; no promociona.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `claude/cal-d-01-r4`, commit `764846d596f325916a39b783efda3f788a1b03f2`, dirty=False

## Estado

- Creado: 2026-10-22T13:25:40.640646+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-10-22T13:28:49.328912+00:00)
- Finalizado: 2026-10-22T13:28:49.515360+00:00
- Razón de la decisión: Reanalisis de R4 sin el compuesto 4-67 (fallo persistente del producto: Timeout de 1200 s en los dos intentos). 88 padres; puerta de pose superada (5 de 5). rho = 0,391 IC95 [0,219; 0,537]; rho de peor caso = 0,320 IC95 [0,139; 0,473]; ambos limites inferiores > 0, asi que el criterio enmendado se cumple. La enmienda (un fallo persistente del producto, declarado, no impide el criterio si quedan >= 85 padres) se redacto despues de ver los scores: no es confirmatorio y no promociona a Verificados. Decision INCONCLUSIVE por construccion. No se acoplo nada; los numeros coinciden exactamente con R4.
- Hashes de dataset: 5 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

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
