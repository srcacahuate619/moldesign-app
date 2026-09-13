# MF-33-EXT-MOD

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

Sobre los 116 se pueden contestar tres cosas que los 33 no permitian: si la ventaja del ensemble es general o esta concentrada en el estrato dificil; si los seis predictores de MF-33-DOSIS replican y sobreviven en los 68 fuera de muestra; y si el fenomeno es de DOSIS o de ACIERTO.

## Protocolo

Referencia: `Ver prerregistro MF-33-EXT-MOD-PRE, sellado con MF-33-EXT por la mitad (10 de 116). Sin computo nuevo. Bloque 1: curva_oraculo[0] es el resultado de un solo conformero y el oraculo final el del ensemble, comparacion pareada. Bloque 2: los seis predictores sobre los 116, declarados REPLICACION. Bloque 3: los cinco prospectivos sobre los 68 que no estan en la cohorte de 48. Bloque 4: primer_dock_que_cubre contra una geometrica con p por maxima verosimilitud. Script: scripts/analisis_mf33ext_moderadores.py.`

## Gate

Bloque 1 con umbrales de 5 y 15 pp fijados antes: A concentrado, B general, C grande e impredecible. Bloque 2 es REPLICACION y la conclusion se toma del bloque 3. Bloque 3 es la regla de decision. Bloque 4: ACIERTO si la observada no se separa de la geometrica y el primer acierto no se concentra en 1; DOSIS si crece por encima; HETEROGENEIDAD si se queda por debajo.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `22193cfdfcf710fda66261a98cc025774bf913d8`, dirty=True

## Estado

- Creado: 2026-08-21T15:10:31.718608+00:00
- Status: finished
- Decisión: INCONCLUSIVE
- Sellado: sí (2026-08-21T15:10:32.543710+00:00)
- Finalizado: 2026-08-21T15:40:18.648950+00:00
- Razón de la decisión: TRES BLOQUES DAN RESULTADO Y UNO FALLO EN SU EJECUCION; por eso INCONCLUSIVE. BLOQUE 1, ESCENARIO B - EFECTO GENERAL. Cobertura single 0.6897 contra ensemble 0.9224 sobre los 116: delta de 23.28 pp, por encima del umbral de 15 fijado antes de ver dato alguno. En COLOCACION el delta es de 42.42 pp (0.3636 -> 0.7879). El efecto NO esta concentrado en el estrato dificil: es del metodo. La regeneracion de la cohorte queda justificada por la regla preregistrada. BLOQUE 3 NO SE EJECUTO, y es un defecto de mi analisis. Cuatro de los cinco predictores prospectivos tienen n=0 en los 68 fuera de muestra -torsdof, rot_bonds, diversidad, n_heavy-, porque el script los lee de MF-33-DOSIS, que solo cubrio los 48. El bloque que iba a ser la unica regla de decision con valor prospectivo evaluo UN predictor de cinco, y no porque los otros fallaran sino porque nunca se midieron ahi. El unico que corrio, n_conformeros, ESTA CONFUNDIDO POR CONSTRUCCION en este contraste: SINGLE usa 1 conformero y ENSEMBLE usa K, asi que el beneficio esta acotado por K -con K=1 los dos brazos son el mismo objeto-. El prerregistro lo declaro no circular heredando el diseno de MF-33-DOSIS, donde K si estaba igualado entre brazos; ese traslado fue un error mio. Da rho=0.538 p=2e-06, y rho=0.4766 p=6e-05 excluyendo los 3 con K=1, asi que el confundido no lo explica entero, pero NO autoriza a declararlo candidato a politica adaptativa. Arreglo anotado: calcular los cuatro restantes sobre los 116, que es parseo y RDKit sin docking. BLOQUE 4 - LA DISTRIBUCION DEL PRIMER ACIERTO SE DESVIA DE UNA GEOMETRICA HOMOGENEA, Y ESO ES TODO LO QUE SE PUEDE AFIRMAR. Contraste formal anadido tras el sellado inicial, porque la version anterior de esta razon afirmaba 'dos poblaciones mezcladas, una que el primer conformero resuelve y otra con p cercano a cero'. ESA AFIRMACION SE RETIRA: inventaba un mecanismo que estos datos no identifican. LO MEDIDO: chi-cuadrado sobre la distribucion del primer acierto entre los 107 cubiertos da chi2=11.04 con 3 gl y p=0.026, asi que la geometrica homogenea se rechaza, pero el efecto es MODERADO. Y la mayor contribucion al rechazo es el EXCESO EN k=1 -80 observados contra 64.9 esperados-, que tiene una explicacion mucho mas simple que la heterogeneidad: conf0 NO ES UNA EXTRACCION INTERCAMBIABLE, es el primer conformero de ETKDG y puede ser sistematicamente mejor que uno al azar. El segundo contraste, complejos nunca cubiertos, da 9 observados contra 4.36 esperados bajo la geometrica con el K propio de cada complejo: razon de 2x, unas 2.2 desviaciones, sugerente y no decisivo. FORMULACION RESISTENTE, y es la que va al paper: 'la distribucion del primer acierto se desvia sustancialmente de un proceso geometrico homogeneo, de forma compatible con una fuerte heterogeneidad entre complejos en la probabilidad de rescate conformacional'. Eso dice mucho sin inventar el mecanismo. EXPLICACIONES ALTERNATIVAS QUE ESTOS DATOS NO SEPARAN, y se declaran: p_i distinta entre complejos; dependencia entre conformeros; orden no intercambiable -que es justo lo que el exceso en k=1 sugiere-; una mezcla facil/dificil/refractario; o realmente un componente con p cercano a cero. Afirmar especificamente una mezcla de dos poblaciones exigiria ajustar un modelo hurdle o beta-geometrico, que no se ha hecho y que el paper principal no necesita. LO QUE SI SE SOSTIENE, y por convergencia y no por el modelo: NUEVE complejos no se cubren con ningun K -1afl, 1bq4, 1d7i, 1d9i, 1dgm, 1elb, 1ew8, 1fkh, 1jq8-, los SIETE de MF-33-CRUCES estan todos dentro y CUATRO de los seis cristales absurdos de REC-09 tambien. Tres lineas independientes senalan el mismo conjunto. Eso es evidencia convergente sobre QUE complejos son, independiente de que modelo genere la curva. LIMITES: el bloque 2 es replicacion y no descubrimiento; el orden de conformeros es por indice y no por calidad, que es a la vez una decision de diseno y una explicacion alternativa de la desviacion observada.
- Hashes de dataset: 2 archivo(s) con SHA-256
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
