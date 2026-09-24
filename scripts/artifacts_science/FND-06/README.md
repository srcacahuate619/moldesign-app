# FND-06

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La provenance de poses es recuperable parcialmente para las 4300 historicas y el contrato nuevo garantiza 100% para futuras

## Protocolo

Referencia: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md FND-06`

## Gate

Contrato implementado; cobertura historica documentada por campo/fuente; poses futuras 100% trazables

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `0a67bf89e41d2accc87c7f52365ec8c91c52f639`, dirty=False

## Estado

- Creado: 2026-08-16T02:22:16.614345+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-16T03:25:16.164881+00:00)
- Finalizado: 2026-08-16T03:25:23.244665+00:00
- Razón de la decisión: FND-06: contrato de provenance implementado, wiring 3/3 generadores, validador endurecido, cobertura historica documentada (unknowns honestos), determinismo verificado
- Hashes de dataset: 4 archivo(s) con SHA-256
- Hashes de assets: 14 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-08-16T04:17:52.859510+00:00: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` `5b95ffd8→686c0a39` — Documento vivo del programa actualizado: reformulacion AF-01 (replica sellada de Fase A, holdout 328) en commit 2ba4a1d (commit 2ba4a1d)
- 2026-08-16T04:17:53.131951+00:00: `scripts/artifacts_science/manifest.schema.json` `7f721c10→97c19323` — Tool de manifest extendido con subcomando maintain (commit 8999ec4) (commit 8999ec4b908d59683f311fb84c4c42fb7c6b040f)
- 2026-08-16T04:17:53.131951+00:00: `scripts/experiment_manifest.py` `634fba9a→c88d890e` — Tool de manifest extendido con subcomando maintain (commit 8999ec4) (commit 8999ec4b908d59683f311fb84c4c42fb7c6b040f)
- 2026-08-16T08:42:08.021421+00:00: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` `686c0a39→f7a1d62c` — Documento vivo del programa ampliado por el maintainer: resultados sellados del entregable 7 + Cartera I (seccion topografica 18.2.1) (commit c8265c1f06e6a56cae204065f77e5c018a28f63c)
- 2026-08-18T20:22:10.765887+00:00: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` `f7a1d62c→3c8bab59` — El doc 49 es documento vivo (README, seccion 'Politica futura'); cambio al documentar los resultados sellados de MF-08, MF-02F, MF-09, MF-02A-EXT, RC-F0-V2, RS-14, MF-09-SYM, RC-F0-SYM, MF-10, MF-10-CAL, MF-13 y RS-14-R1, mas la nueva 5.1 sobre el sesgo de simetria (commit 6bae87c3cda6de687a37b19f2b7dd219cd53e053)
- 2026-08-19T03:55:21.371808+00:00: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` `3c8bab59→fd27bd0c` — Documento vivo (README, Politica futura): cambio al anadir la seccion 20 de transferencia interdisciplinar, la 20.11 sobre enlaces rotables, y los resultados sellados del bloque del 2026-08-18 (commit 82997dab038ccaaeb206f0bad446291dd933e176)
- 2026-09-24T04:04:29.760679+00:00: `docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md` `fd27bd0c→64761646` — Activo cambiado despues del sello: docs/49_PROGRAMA_EXPERIMENTAL_CIENTIFICO.md es un modulo o documento vivo que se sello como asset (regla 4 de las reglas de metodo: no sellar un modulo de produccion vivo). El resultado sellado se produjo con la version anterior, cuyo hash queda en previous_hash; la version actual es la del commit 1b03189. Se registra el 2026-09-23, antes de la auditoria externa, para que validar_sellos.py distinga este cambio declarado de una corrupcion. No cambia ninguna cifra ni decision del experimento. (commit 1b03189)

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
