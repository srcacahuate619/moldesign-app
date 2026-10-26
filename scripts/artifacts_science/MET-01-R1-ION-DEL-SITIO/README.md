# MET-01-R1-ION-DEL-SITIO

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Conservar los iones del sitio con el Vina del producto mejora la reproducción pareada top-1 del cristal frente a retirarlos, bajo microestados y receptores congelados. Repetición de MET-01 sobre un producto que sí conserva la whitelist.

## Protocolo

Referencia: `scripts/artifacts_science/MET-01-R1-ION-DEL-SITIO/entrada/protocolo.json`

## Gate

El de MET-01: signos exactos bilaterales alfa 0.05; GO significativo a favor de CON y sin daño en todos los controles evaluables, mínimo cuatro; n principal mínimo 25 y exclusiones no mayores de 30 por ciento; si no, NO_GO o INCONCLUSIVE según protocolo preregistrado.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.11.9
- Seeds: 42
- Git: rama `claude/met-01-r1`, commit `dfdc9a269343f7993a8d36bc25e361407cf01035`, dirty=False

## Estado

- Creado: 2026-10-21T08:27:59.427250+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-10-21T16:46:24.644975+00:00)
- Finalizado: 2026-10-21T16:46:34.990504+00:00
- Razón de la decisión: Gate preregistrado de MET-01: signos exactos bilaterales, alfa 0,05. 28 de 35 entradas principales pareadas (7 excluidas, 20 %, dentro del 30 %); discordancias CON:SIN = 0:3, p = 0,25. No hay mejora a favor de conservar el ion; la diferencia observada va en contra de CON (-10,7 puntos; semillas con exito conjunto SIN 43/160, CON 34/160) y no es significativa, asi que tampoco prueba dano ni equivalencia. Controles: 4 de 6 evaluables, ninguna perdida. Se mantiene la retirada del ion y la abstencion de Preparacion; CON queda como linea base para un modelo de coordinacion (M5). PoseBusters no mira los iones escritos como ATOM: sus PASA inorganicos son vacuos. Duracion declarada: union de los tramos de medicion (piloto y confirmatoria), 5900 s; la confirmatoria se corto a las 09:33 UTC y se reanudo a las 15:45 sobre el mismo commit congelado.
- Hashes de dataset: 1016 archivo(s) con SHA-256
- Hashes de binarios: 3 archivo(s) con SHA-256
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
