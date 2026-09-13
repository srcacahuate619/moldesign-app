# MF-02D-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Aplicar el pipeline MolFlex congelado a los 116 de train conservando las poses produce el material de referencia del programa y reproduce el hallazgo de MF-02B

## Protocolo

Referencia: `MF-02D-PRE/PREREGISTRO.md; refina MF-02-PRE (a09b770); sustituye a MF-02C-PRE que no llego a ejecutarse; molflex congelado docs/40 con --keep`

## Gate

G1 validez >=95%, G2 material en disco, G3 reproduccion de MF-02B sin discrepancias, G4 no regresion, G5 cobertura >=90%

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `1af5dab5b2ea445cdd71e7b4e1392aaef5b1123c`, dirty=True

## Estado

- Creado: 2026-08-17T23:59:10.361436+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T23:59:10.983287+00:00)
- Finalizado: 2026-08-17T23:59:11.138981+00:00
- Razón de la decisión: Prerregistro sellado antes de ejecutar. Corre los 116 y no solo los 66 que faltaban porque el pipeline es determinista y la reproduccion de MF-02B se convierte en gate G3, no en subproducto: un experimento que produce el material de referencia del programa debe demostrar que reproduce el hallazgo que lo motivo. Documenta que MF-02C-PRE queda sellado y sin ejecucion porque su runner descartaba las poses, y que un prerregistro superado se documenta y no se reescribe. Declara fuera de alcance la reconstruccion del dataset de features y toda evaluacion de selector.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
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
