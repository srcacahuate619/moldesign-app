# MET-01-ION-DEL-SITIO

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Conservar los iones del sitio con el Vina del producto mejora la reproducción pareada top-1 del cristal frente a retirarlos, bajo microestados y receptores congelados.

## Protocolo

Referencia: `scripts/artifacts_science/MET-01-ION-DEL-SITIO/entrada/protocolo.json`

## Gate

Signos exactos bilaterales alfa 0.05; GO significativo a favor de CON y sin daño en todos los controles evaluables, mínimo cuatro; n principal mínimo 25 y exclusiones no mayores de 30 por ciento; si no, NO_GO o INCONCLUSIVE según protocolo preregistrado.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `sol/met-01-metales`, commit `1be6e56de10b68f2c5e9a459f7e689884e5c844b`, dirty=False

## Estado

- Creado: 2026-10-11T21:58:28.298244+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-10-11T22:22:49.160437+00:00)
- Finalizado: 2026-10-11T22:23:26.251646+00:00
- Razón de la decisión: Piloto CON invalidado: variante con Zn, ejecución sin Zn y hash idéntico a SIN por descarte de list[str] en _coerce_hotspots del producto f0e64086. Guardián detuvo 3/8 terminales (37,5 %); fase confirmatoria no iniciada, cero pares válidos. No estima el efecto del ion. Se preservan once crudos y se mantiene el gate preregistrado.
- Hashes de dataset: 249 archivo(s) con SHA-256
- Hashes de binarios: 3 archivo(s) con SHA-256
- Hashes de assets: 15 archivo(s) con SHA-256

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
