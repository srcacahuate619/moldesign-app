# MF-02C-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Completar la aplicacion del pipeline MolFlex congelado a los 66 complejos de train que no corrieron en MF-02B deja el conjunto homogeneo sin degradar la cobertura del oraculo

## Protocolo

Referencia: `MF-02C-PRE/PREREGISTRO.md; refina MF-02-PRE sellado (a09b770); reutiliza sin modificar el runner sellado de MF-02B (1af5dab)`

## Gate

G1 validez >=95%, G2 no regresion de la union, G3 cobertura de train >=90%

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `1af5dab5b2ea445cdd71e7b4e1392aaef5b1123c`, dirty=True

## Estado

- Creado: 2026-08-17T23:56:01.314632+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T23:56:01.860884+00:00)
- Finalizado: 2026-08-17T23:56:02.022967+00:00
- Razón de la decisión: Prerregistro sellado antes de ejecutar: cohorte de 66 (los de train que no corrieron en MF-02B), protocolo byte-identico por reutilizacion del runner sellado, metrica de union nunca sustitucion, y tres gates. Se declara explicitamente fuera de alcance la reconstruccion de poses_train.jsonl con features y cualquier medicion de precision condicional o de selector, para que el GO no se lea como que el dataset ya esta reconstruido.
- Hashes de dataset: 1 archivo(s) con SHA-256
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
