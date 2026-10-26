# MET-02-R1-SEMILLA

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con el lector de coordenadas arreglado (f7c46736), la regla de metales en dos niveles da en las 41 entradas evaluables de MET-02 un estado que no cambia con la semilla y que coincide con el inventario de metales (ABSTENCION si el ligando del cristal coordina algún ion, REVISAR si no), con la misma pose top-1 que el brazo de antes de MET-02.

## Protocolo

Referencia: `scripts/artifacts_science/MET-02-R1-SEMILLA/entrada/protocolo.json`

## Gate

GO: H2 sin excepciones, H3 sin discrepancias no explicadas por una diferencia declarada del criterio, H4 >= 95 % y >= 30 primarias evaluables; NO_GO: alguna primaria cambia con la semilla o una discrepancia de H3 sin explicar; INCONCLUSIVE en otro caso.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `01cfdbcaf3594c2e8fd9c08cb61239d4edbae99a`, dirty=True

## Estado

- Creado: 2026-10-23T04:59:52.885532+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-10-23T06:22:00.702771+00:00)
- Finalizado: 2026-10-23T06:22:00.837060+00:00
- Razón de la decisión: Con el lector de coordenadas arreglado (f7c46736), la regla de metales en dos niveles: ninguna de las 41 entradas primarias evaluables cambia de estado con la semilla (0/41, IC95 0-0,086); el estado coincide con el inventario de metales en 39/39; la pose top-1 es idéntica a la del brazo antes de MET-02 en 205/205. Cambian respecto de la regla de antes 4PHL, 4QGE, 5A2R, 6KE5 y 8WGR (ABSTENCION a REVISAR, ligando sin coordinar), 1RKP (a REGISTRADO) y 4NY4 (a REVISAR por el Fe del hemo coordinado). 1VKG y 5I3T no evaluables (Meeko).
- Hashes de dataset: 217 archivo(s) con SHA-256
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
