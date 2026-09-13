# FND-08

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El registro experimental se sostiene por si solo: un tercero que reciba unicamente el repositorio puede verificar las cifras de cada artefacto sellado sin re-ejecutar nada y sin conocer la sesion.

## Protocolo

Referencia: `Auditoria mecanica de SOLO LECTURA sobre los artefactos sellados, con scripts/auditoria_reproducibilidad.py. Es el precursor de FEP-06, que pide que un tercero reconstruya el paquete de transferencia: ese experimento depende de FEP-05, que no existe, pero la pregunta de si el registro se sostiene NO depende de nada. G2 y G3 solo aplican a artefactos con metrics.json; prerregistros y documentales quedan fuera del denominador. Cero escrituras fuera del propio directorio del experimento.`

## Gate

G1 integridad del sello: 100% de los artefactos sellados validan. G2 consistencia del recuento: si el artefacto declara n_complejos, coincide con las filas de su registro por unidad. G3 existencia del dato crudo: todo artefacto con resultados tiene al menos un archivo de datos no vacio, de modo que sus cifras sean verificables sin re-ejecutar. G4 trazabilidad del codigo: el script que produjo el resultado esta hasheado en el sello, no solo mencionado en prosa. GO exige los cuatro.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `b01064130e0cc85fb75837deedc188d0bf7766d4`, dirty=True

## Estado

- Creado: 2026-08-20T03:52:24.896820+00:00
- Status: finished
- Decisión: NO_GO
- Sellado: sí (2026-08-20T03:55:22.162498+00:00)
- Finalizado: 2026-08-20T03:55:22.335186+00:00
- Razón de la decisión: NO_GO: fallan tres de los cuatro gates, y ese es el resultado util. Precursor de FEP-06, que depende de FEP-05 y por tanto no es ejecutable todavia; la pregunta de si el registro se sostiene por si solo NO depende de nada y se responde aqui. Coste: segundos, solo lectura. G1 INTEGRIDAD DEL SELLO 93/94. Falla FND-01-SMOKE: sello scripts/experiment_manifest.py como DATASET, y cuando la herramienta se amplio con el subcomando maintain el hash dejo de coincidir. La causa raiz es una mala clasificacion -codigo sellado como dato- y maintain NO puede repararlo por diseno, porque rechaza tocar dataset_hashes. Es un artefacto cuya hipotesis literal es 'smoke test' y no sostiene ninguna cifra del programa, pero el fallo es real y queda declarado en vez de silenciado. G2 CONSISTENCIA DEL RECUENTO 23/23. Todo artefacto que declara n_complejos y tiene per_complex.jsonl con contenido coincide con el. G3 EXISTENCIA DE DATO CRUDO 60/64. Fallan FND-04, MF-26, REC-03-PRE y RS-01A-R1: declaran resultados sin ningun fichero de datos por unidad, de modo que un tercero no puede verificar sus cifras sin re-ejecutar. Los cuatro son re-analisis o corrigenda sobre material ya sellado y sus scripts SI estan hasheados, asi que son reproducibles por re-ejecucion; lo que no son es verificables por lectura. La distincion importa y no estaba declarada. G4 TRAZABILIDAD DEL CODIGO 63/64. Falla FND-02: declara resultados sin ningun script hasheado en el sello. HALLAZGO PRINCIPAL, QUE NO ERA NINGUN GATE: 10 artefactos tienen su dato crudo bajo un nombre distinto del canonico -cohort.jsonl, parejas.jsonl, corridas.jsonl, brazo_a.jsonl, union_candidates_*.jsonl- mientras la seccion 17 declara per_complex.jsonl y el skeleton vacio de ese nombre sigue en el directorio. A un tercero se le dice que busque un fichero que esta vacio junto a otro que si tiene los datos. No hay perdida de informacion, hay no conformidad de contrato, y es exactamente el tipo de friccion que hace fracasar una transferencia. CERO hashes apuntan a ficheros ausentes. NOTA DE METODO: la primera version de esta auditoria uso una lista fija de nombres de fichero y reporto 8 fallos de G3, cinco de ellos falsos porque el dato existia bajo otro nombre; y la segunda comparo n contra el mayor .jsonl del directorio y produjo 6 falsos positivos en G2 por ficheros auxiliares mas largos que la cohorte. Ambos criterios se corrigieron ANTES de sellar. Una auditoria mal calibrada es peor que ninguna, porque gasta credibilidad en defectos inexistentes.
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
