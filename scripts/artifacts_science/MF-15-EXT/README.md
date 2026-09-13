# MF-15-EXT

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El embudo medido sobre el conjunto v2 se sostiene con 4.6x mas poses

## Protocolo

Referencia: `medicion: relectura del material sellado de MF-02D + MF-02F (~751 poses por complejo); Spearman por radio con metrica ingenua y corregida por simetria`

## Gate

medicion sin gates; verificacion: reproducir el Spearman global de MF-09

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:53:01.444425+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-19T03:53:02.243291+00:00)
- Finalizado: 2026-08-19T03:53:02.423666+00:00
- Razón de la decisión: Reproduce el Spearman de MF-09 al tercer decimal (0.1858 frente a 0.186 en COLOCACION), lo que verifica la lectura del material. Con 751 poses por complejo: rho global 0.186 en COLOCACION y 0.507 en CONTROL; a R<=4 A baja a 0.279 y a R<=6 A a 0.140. Corregir simetria no lo mueve (0.1858 en ambas metricas), asi que el embudo es invariante a esa eleccion. A R<=2 A siguen sin existir complejos medibles en COLOCACION incluso con 751 poses, porque en 30 de 33 no hay ninguna pose ahi (MF-09).
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
