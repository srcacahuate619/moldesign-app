# MET-02-SEMILLA

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Con la regla de metales en dos niveles medida desde el ligando del cristal (878c215b), ninguna entrada primaria cambia de estado de metales y cofactores sólo por la semilla de Vina; con la de antes (861f6a0e, mínimo pose/cristal) se cuenta cuántas cambian. Panel: 41 entradas del inventario de metales + 1RKP y 4NY4, semillas 42, 7, 13, 101 y 2026, configuración de un caso.

## Protocolo

Referencia: `scripts/artifacts_science/MET-02-SEMILLA/entrada/protocolo.json`

## Gate

GO: H2 sin excepciones, H3 en todas las primarias del inventario salvo diferencias declaradas del criterio, >= 30 primarias evaluables y pose top-1 idéntica entre brazos en >= 95 % de los pares; NO_GO: alguna primaria cambia con la semilla con la regla de después; INCONCLUSIVE en otro caso.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `a3c3e9c0e75ed32aa65b48a8d087f3a4d8e0b538`, dirty=True

## Estado

- Creado: 2026-10-23T02:32:14.141834+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-10-23T04:56:13.326059+00:00)
- Finalizado: 2026-10-23T04:56:22.528143+00:00
- Razón de la decisión: H2 se cumple: con la regla en dos niveles ninguna de las 41 entradas evaluables cambia de estado con la semilla (0/41, IC95 0-0,086), y la pose top-1 es idéntica entre brazos en 205/205 pares. H3 falla, 37/39: en 5E92 y 9GKV el ligando del cristal coordina el metal (1,94 y 2,15 Å) y la regla nueva da REVISAR porque el lector de coordenadas toma el elemento de las columnas 77-79, que incluyen la carga (MG2, ZN0). Es un defecto de implementación, no una diferencia declarada del criterio, así que cuenta como fallo. Con la regla de antes tampoco cambia ninguna entrada con la semilla en este panel (0/41). 1VKG y 5I3T no son evaluables (Meeko).
- Hashes de dataset: 432 archivo(s) con SHA-256
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
