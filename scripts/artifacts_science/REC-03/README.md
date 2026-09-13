# REC-03

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Un grid derivado de prediccion de pocket ligando-libre (MolPocket) repara el docking que el catalogo pierde en la cohorte accionable de REC-01-R1, sin degradar los targets sanos

## Protocolo

Referencia: `REC-03-PRE sellado (78bb65d, maintain ff806cc); entradas selladas REC-01-R1 y geometria_preflight.json; Vina 1.2.7 local, 4 cajas por target, 3 semillas`

## Gate

5 gates: G1 validez >=98%, G2 solo lectura del catalogo, G3 reparacion >=5 de 25 accionables, G4 no regresion >=70% del control, G5 determinismo

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `ff806cc9f65be995c334f875313305b0d983da0d`, dirty=True

## Estado

- Creado: 2026-08-17T21:24:47.375476+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-17T21:24:57.905595+00:00)
- Finalizado: 2026-08-17T21:25:14.420453+00:00
- Razón de la decisión: Fallan dos gates. G4 (no regresion) FAIL: en el control G_MP_SCORE conserva 4 de los 6 targets que repara G_CAT, por debajo de los 5 exigidos, y las dos perdidas son catastroficas (2H02 pasa de 1.338 a 61.07 A; 7JVU de 1.976 a 13.09 A). G1 (validez) FAIL: 87.1% (324/372), por debajo del 98% exigido. La validez no fallo de forma difusa: fallo entera y exclusivamente en 4 targets que perdieron sus 12 corridas cada uno mientras los otros 27 dieron 324/324 validas; como los 4 caen igual en los 4 brazos no distorsionan la comparacion, pero el prerregistro es explicito en que un fallo de validez obliga a repetir y no a interpretar, de modo que NO se emite claim. Causas diagnosticadas: 3MG0 lleva boro y Vina no tiene tipo de atomo para B (limite del motor); 6MWA (37 torsiones), 7E2Y (43) y 4CA8 (20 torsiones, 56 atomos) agotaron el timeout de 1800 s. G3 (reparacion) PASS: G_MP_SCORE repara 6 accionables, y de los 19 evaluables el techo geometrico declarado era 9, de modo que alcanza el 67% de lo que la geometria permitia; se repara donde el catalogo contenia parcialmente el ligando (5 de 6 son S2_GRAVE) y no donde la caja estaba completamente fuera. G_CAT repara 0 de 21 accionables, resultado ya determinado por construccion y declarado en el prerregistro. G5 determinismo PASS 4/4 identicos. Calibracion no buscada: con la caja exacta del catalogo, centrada a 0.00 A del ligando, el re-docking solo acierta en 6 de 8 targets sanos (75%): ese techo es del motor, no del catalogo. Conclusion registrada: la reparacion automatica global del catalogo por prediccion de pocket NO es viable con este motor; los 25 accionables siguen siendo deuda de curacion por target. Coherente con REC-07: la geometria del grid no es buen predictor de la calidad del docking, ni para condenar un grid ni para reemplazarlo.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de binarios: 1 archivo(s) con SHA-256
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
