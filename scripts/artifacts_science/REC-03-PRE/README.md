# REC-03-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La reparacion del grid por prediccion de pocket ligando-libre (MolPocket) es evaluable con un techo geometrico declarado de 10/25; el prerregistro congela cohorte, brazos, metrica y gates antes de ejecutar docking

## Protocolo

Referencia: `REC-03-PRE/PREREGISTRO.md; entradas selladas REC-01 y REC-01-R1 (4a4fbc7); geometria_preflight.json computado y declarado antes de ejecutar`

## Gate

Prerregistro completo: 5 gates definidos (G1 validez >=98%, G2 solo lectura, G3 reparacion >=5/25, G4 no regresion >=70% del control, G5 determinismo), techo geometrico y prohibiciones declaradas antes de cualquier corrida de docking

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `1bbe44ebafaffa388a015979f03571d65e437cb7`, dirty=True

## Estado

- Creado: 2026-08-17T15:54:44.921948+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-17T15:55:12.086041+00:00)
- Finalizado: 2026-08-17T15:55:24.328829+00:00
- Razón de la decisión: Prerregistro completo y sellado antes de ejecutar docking: cohorte congelada (25 accionables de REC-01-R1 + 12 control S0 por muestreo seed 42 sobre 218 elegibles, cero solapamiento con train/test), 4 cajas por target con el TAMANO del catalogo fijo (unica variable = el centro), brazo derivado G_MP_SCORE seleccionado por score de Vina y nunca por posicion del ligando, metrica CalcRMS in situ con exito <=2.0 A en >=2 de 3 semillas, y 5 gates numericos. Se declara por adelantado el techo geometrico de la reparacion: solo 10 de los 25 accionables tienen contencion total del ligando en alguno de los 3 pockets, de modo que 15 son irreparables por geometria antes de docking. Se declara tambien que MolPocket top-1 pierde 93 de los 218 targets sanos por contencion, y que el fracaso de G_CAT en los 11 S1 esta determinado por construccion. Prohibido usar la posicion del ligando para elegir caja, pocket o pose. MolPocket es admisible como brazo reparador por ser ligando-libre (detect_pockets solo lee lineas ATOM); los hotspots del catalogo quedan prohibidos por ser derivados del ligando nativo.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-08-17T18:44:14.373432+00:00: `scripts/run_rec03_grid_repair.py` `2e24961a→7779ebe3` — Cascada de preparacion determinista anadida tras el sello: reparacion de valencia del ligando (Normalizer + N cuaternario, con guardia de sanidad que rechaza carbonos cargados) y desempate de tautomero de histidina fijando HIE con cap de 3 rondas. Son arreglos de preparacion, no de criterio: cohorte, brazos, tamano de caja, metrica CalcRMS, umbral 2.0 A, semillas y los 5 gates quedan exactamente como se sellaron. Los targets que aun asi no preparan se excluyen y se reportan como no evaluables, contando como no reparados. (commit ee84997993d83297e41d28802c6a8a51b69092e7)

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
