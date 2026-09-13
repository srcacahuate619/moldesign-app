# MF-21

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El ensemble ETKDG ya contiene un conformero suficientemente parecido al bioactivo como para que el docking rigido funcione

## Protocolo

Referencia: `medicion: RMSD alineado (GetBestRMS) entre cada conformero ETKDG de ENTRADA y el ligando cristalografico; sin docking nuevo`

## Gate

medicion sin gates; el mejor conformero es el suelo teorico del docking rigido

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:06.296447+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:07.046698+00:00)
- Finalizado: 2026-08-19T03:53:07.238604+00:00
- Razón de la decisión: En 23 de los 30 complejos que fallan (77%) el ensemble contiene un conformero a <=2 A alineado del bioactivo, con mediana del mejor en 1.364 A. En CONTROL la mediana es 0.360 A con 6 conformeros bajo 1.5 A; en los que fallan, la mediana de conformeros bajo 1.5 A es 1: el bueno esta, pero diluido. CORRIGENDUM INCLUIDO EN ESTE SELLO: la primera version uso el glob conf*.rigid.pdbqt, que tambien captura conf{N}.relax.rigid.pdbqt -poses YA DOCKEADAS Y RELAJADAS, salida del pipeline-. Eso medía lo que el docking logro, no lo que el generador ofrece, e inflaba el techo de 23 a 24 complejos y producia casos espectaculares falsos (1l83 a 0.014 A era una pose relajada, no un conformero). Corregido con regex estricta. Advertencia: tener el conformero a <=2 A es condicion NECESARIA, no suficiente; MF-22 midio despues que en COLOCACION la conversion es 0 en todas las bandas de calidad conformacional, incluida 0.0-0.5 A.
- Hashes de assets: 1 archivo(s) con SHA-256

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
