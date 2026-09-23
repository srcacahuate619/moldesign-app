# FEP-07-PDBBIND

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

PDBBind permite muchos mas calculos FEP ejecutables hoy que los 75 de los 203, y declarar tautomeros desbloquea una fraccion mayor que reparar receptores

## Protocolo

Referencia: `scripts/analisis_fep_ejecutable_hoy.py sellado, sin modificar (sha d5c06e4c4936), ejecutado desde un espacio de trabajo cuyo FEP-03/parejas.jsonl son los 21 shards de FEP-03-PDBBIND y cuyos FEP-01-EXT/FEP-02-EXT son las extensiones a PDBBind; replica previa identica al sello (75 ejecutables hoy).`

## Gate

medicion sin gate: parejas ejecutables hoy, bloqueadas por tautomero y por receptor

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/release-hygiene`, commit `ca68d06a5d207f9a86fbb73b951ec2455ae9c5be`, dirty=True

## Estado

- Creado: 2026-09-23T06:46:21.324400+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-09-23T06:51:58.202476+00:00)
- Finalizado: 2026-09-23T06:51:58.397061+00:00
- Razón de la decisión: La hipotesis se sostiene: de las 3299 parejas aptas de FEP-03-PDBBIND, 2243 (68%) son ejecutables hoy sobre 1114 complejos, frente a 75 en los 203; declarar tautomeros desbloquea 656 mas (hasta 2899) y reparar receptores solo recuperaria 400. Confirma el orden del roadmap: declarar tautomeros primero. Las 21 parejas aptas de galectina-3 (6qln-6qlu), la cohorte recomendada, son las 21 ejecutables hoy. Replica previa identica al sello (91 parejas, 75 ejecutables). Limitacion declarada por el script: ejecutable hoy significa sin los dos bloqueos medidos, no listo para produccion; con el criterio completo de FEP-02 en ambos extremos quedan 875.
- Hashes de assets: 6 archivo(s) con SHA-256

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
