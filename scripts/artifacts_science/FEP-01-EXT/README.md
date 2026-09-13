# FEP-01-EXT

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La ambiguedad tautomerica que FEP-01 conto (164 de 203) tiene CONSECUENCIA medible: en una fraccion sustancial de los ligandos el tautomero que el pipeline lee del fichero coloca los protones en atomos distintos de los que elegiria un canonicalizador estandar, de modo que el patron donador/aceptor con el que se dockeo no es el que se declararia para FEP+.

## Protocolo

Referencia: `Extension de FEP-01 sobre su misma cohorte de 203. Para cada ligando se compara el tautomero TAL COMO ESTA EN EL FICHERO -el que lee mf.leer_ligando y dockea el pipeline- contra el canonico de rdMolStandardize.TautomerEnumerator.Canonicalize. LA COMPARACION ES ATOMO POR ATOMO, no por conteo de HBD/HBA: un sondeo previo sobre 5 ligandos mostro casos con tautomero distinto y los MISMOS totales de donadores y aceptores, porque el proton se mueve de un atomo a otro sin cambiar la suma. Se compara GetTotalNumHs() por atomo pesado, que localiza el proton. Si el canonicalizador no preserva la indexacion en algun ligando se declara INDEXACION_NO_PRESERVADA y ese caso sale del denominador en vez de compararse mal. Solo lectura; cero escrituras fuera del directorio del experimento.`

## Gate

MEDICION SIN GATES DE DECISION, declarada como tal. G1 validez: >=95% de los 203 procesables. G2 descriptivo: fraccion con SMILES canonico distinto del actual. G3 LA CANTIDAD DE INTERES: fraccion donde algun atomo pesado cambia su numero de hidrogenos, con la mediana de atomos afectados. Cruce obligatorio con FEP-01: cuantos de los que ese experimento marco ambiguos mueven realmente el proton, y -mas importante- cuantos que NO marco ambiguos si lo mueven. LIMITACION QUE FORMA PARTE DEL RESULTADO Y SE DECLARA ANTES: el tautomero canonico NO es 'el correcto'; es una heuristica de puntuacion, no una prediccion de la poblacion dominante a pH fisiologico, la misma limitacion que FEP-01 declaro para la enumeracion. Se mide DESACUERDO entre el fichero y un canonicalizador estandar, NO error. Un desacuerdo alto no significa que el docking este mal: significa que hay una decision que nadie tomo explicitamente y que para FEP+ hay que tomar y declarar. PROHIBIDO concluir que las poses dockeadas son incorrectas a partir de este experimento.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `c578cc67572801d2ea0ab44d62c605e7bf0c0a82`, dirty=True

## Estado

- Creado: 2026-08-20T04:07:52.060236+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-20T04:08:47.964018+00:00)
- Finalizado: 2026-08-20T04:08:48.684720+00:00
- Razón de la decisión: MEDICION SIN GATES, declarada como tal. Validez 203/203. LA AMBIGUEDAD DE FEP-01 SE REDUCE A UN TERCIO CUANDO SE MIDE SU CONSECUENCIA. FEP-01 conto 164 de 203 con mas de un tautomero enumerable. Aqui: 84 de 203 (41.4%) tienen SMILES canonico distinto del que hay en el fichero, pero solo en 54 de 203 (26.6%) EL PROTON SE MUEVE REALMENTE de atomo -mediana 2 atomos afectados, maximo 4-. Los otros 30 son desacuerdo sin consecuencia: el canonicalizador reordena o kekuliza sin cambiar donde esta el hidrogeno. LA COMPARACION POR CONTEO HABRIA FALLADO. Un sondeo previo sobre 5 ligandos mostro casos con tautomero distinto y los MISMOS totales de HBD y HBA, porque el proton se mueve de un atomo a otro sin cambiar la suma; por eso la medicion es GetTotalNumHs por atomo pesado y no un conteo agregado. Contar donadores y aceptores habria dado cero senal donde si la hay. LA BANDERA DE FEP-01 NO TIENE FALSOS NEGATIVOS: de los 54 donde el proton se mueve, los 54 estaban marcados como ambiguos; cero complejos no marcados mueven el proton. La bandera es conservadora y sana, y su exceso -110 marcados sin desacuerdo- son casos donde el fichero YA coincide con el canonico. CONSECUENCIA OPERATIVA PARA H2: declarar tautomero para 54 complejos es un tercio del trabajo que sugeria FEP-01, y la lista esta identificada por pid. 30 de los 54 estan en train y 24 en valtest. Los tres con mas atomos afectados son 1m0n, 1m0o y 1m0q, con 4 atomos movidos cada uno y patron N/N/O identico entre ellos: son analogos de la misma serie, de modo que el defecto es de la serie y no del complejo. LIMITACION DECLARADA ANTES DE CORRER Y QUE FORMA PARTE DEL RESULTADO: el tautomero canonico NO es 'el correcto'. Es una heuristica de puntuacion, no una prediccion de la poblacion dominante a pH fisiologico -la misma limitacion que FEP-01 declaro para la enumeracion-. Lo medido es DESACUERDO entre el fichero y un canonicalizador estandar, NO error. Queda expresamente PROHIBIDO concluir desde aqui que las poses dockeadas de esos 54 son incorrectas: lo que se concluye es que en 54 complejos hay una decision quimica que nadie tomo explicitamente. INCIDENCIA REGISTRADA: RDKit emitio avisos de kekulizacion en unos pocos ligandos; ninguno produjo error ni salio del denominador, pero su canonicalizacion pudo estar degradada y no se ha comprobado uno a uno.
- Hashes de dataset: 1 archivo(s) con SHA-256
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
