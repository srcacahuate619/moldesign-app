# MF-19

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Si al buscador se le entrega el conformero CRISTALOGRAFICO y se le congelan las torsiones, la colocacion queda reducida a 6 grados de libertad. Si asi acierta, la colocacion rigida esta resuelta y el fallo del programa es de busqueda conformacional; si falla, el fallo es de colocacion pura e inculpa al buscador o al paisaje, no al conformero.

## Protocolo

Referencia: `REGISTRO RETROACTIVO, declarado como tal: ejecutado el 2026-08-19 con scripts/run_mf19_rigido_cristal.py, resultados en scratch/mf19_resultados sin manifest. NO existe prerregistro separado; la regla de lectura y la prohibicion viven en el metrics.json que produjo el runner y se sellan tal cual. Diseno: 48 complejos (33 COLOCACION + 15 CONTROL), dos brazos sobre el MISMO conformero cristalografico -flexible con sus torsiones activas, y rigido con TODAS las torsiones congeladas, 6 GDL-; exh=8, num_modes=9, semilla 42, caja 25 A.`

## Gate

Regla de lectura declarada en el propio metrics.json: 'rigido acierta en la mayoria => la colocacion en 6 GDL esta resuelta y el fallo es busqueda conformacional; rigido falla => el fallo es de COLOCACION pura'. PROHIBICION declarada en el metrics.json: el conformero de entrada es el CRISTALOGRAFICO, de modo que esto NO es una politica de produccion y mide un TECHO -que pasaria si el generador de conformeros fuera perfecto-. SIN PRERREGISTRO SEPARADO: sus lecturas son post-hoc por construccion.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `6a3caa8ac15867ff371733814834fbe33a35ece5`, dirty=True

## Estado

- Creado: 2026-08-20T05:07:25.614409+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T05:07:26.233410+00:00)
- Finalizado: 2026-08-20T05:07:26.432445+00:00
- Razón de la decisión: REGISTRO RETROACTIVO de un experimento ejecutado el 2026-08-19 que el doc 49 citaba en su seccion 20.1 y describia como 'en curso' en la 20.2, sin artefacto. CON EL CONFORMERO CRISTALOGRAFICO, EL RIGIDO GANA AL FLEXIBLE. En COLOCACION: rigido acierta 24 de 33 frente a 21 del flexible, top-1 22 frente a 14, y mejor RMSD mediano 0.379 A frente a 1.665. En CONTROL: rigido 15 de 15 frente a 13, aunque el top-1 se invierte (10 frente a 11). Por la regla de lectura declarada en el propio runner, el rigido acierta en la mayoria y por tanto LA COLOCACION EN 6 GDL ESTA RESUELTA: el fallo del programa es de busqueda conformacional, no de colocacion pura. APARENTE CONTRADICCION CON MF-33, QUE SE RESUELVE Y ES EL HALLAZGO. MF-33 midio que el rigido alcanza 1 de 33 y el flexible 26 de 33 sobre los mismos complejos. Aqui el rigido gana. La diferencia es el CONFORMERO DE ENTRADA: MF-19 usa el CRISTALOGRAFICO -exacto- y MF-33 usa los ETKDG -aproximados, con el mejor a 1.364 A de mediana segun MF-21-. La sintesis es que el docking rigido es EXQUISITAMENTE SENSIBLE A LA CALIDAD DEL CONFORMERO: con el exacto rinde 24 de 33 y con el mejor disponible del ensemble rinde 1 de 33. Eso explica por que el diseno de MolFlex era razonable -si el ensemble contuviera el conformero correcto, dockear rigido seria optimo- y por que aun asi no funciona: MF-21 midio que el ensemble contiene un conformero a <=2 A alineado en 23 de 30 fallos, pero '<=2 A alineado' NO es 'suficientemente exacto para docking rigido'. PROHIBICION QUE VIAJA CON EL RESULTADO, declarada en el metrics.json original: el conformero de entrada es el cristalografico, esto NO es una politica de produccion y mide un TECHO. Queda prohibido citar el 24 de 33 como rendimiento alcanzable. LIMITACION ESTRUCTURAL: sin prerregistro separado, sus lecturas son post-hoc por construccion. Sellarlo respalda la cita del doc 49; no le concede estatus de experimento preregistrado.
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
