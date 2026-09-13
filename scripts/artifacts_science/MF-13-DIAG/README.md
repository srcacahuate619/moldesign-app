# MF-13-DIAG

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El decoy que gana en el ~30% de MF-13 esta en un bolsillo distinto y mas enterrado, no es un fallo genuino de la funcion

## Protocolo

Referencia: `medicion: cruce de MF-13 con los receptores de molflex_train_v2; enterramiento, aguas, metales y distancia entre centroides; sin computo nuevo`

## Gate

medicion sin gates; lectura declarada: delta de enterramiento positivo y centroides lejanos => sitio competidor; si no, fallo de puntuacion sin explicar

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6bae87c3cda6de687a37b19f2b7dd219cd53e053`, dirty=True

## Estado

- Creado: 2026-08-19T03:52:58.985964+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-19T03:52:59.770535+00:00)
- Finalizado: 2026-08-19T03:52:59.978308+00:00
- Razón de la decisión: La hipotesis del bolsillo competidor queda REFUTADA. En el grupo donde gana el decoy: delta de enterramiento 0.000, distancia entre centroides 1.95 A y solo 2 de 17 complejos en sitio distinto (>8 A). El decoy ganador esta a ~2 A de la pose nativa con el mismo enterramiento. Antes se habian descartado otras dos hipotesis: faltan metales o cofactores (FALSO, el PDBQT ya los contiene: 1ew8 tiene sus 4 Zn) y las aguas chocan con la nativa (MARGINAL: 5 de 10 fallos tienen 1-2 aguas a <2.5 A y 0 de 10 aciertos tienen alguna, senal real pero insuficiente para 7 kcal/mol). Con tres hipotesis alternativas caidas, ese ~30% parece un fallo genuino de la funcion de puntuacion: poses vecinas que Vina prefiere sobre la nativa sin ser mejores por ningun criterio geometrico. Ahi ni mas busqueda ni mejor preparacion ayudan.
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
