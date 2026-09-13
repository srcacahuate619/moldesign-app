# MF-33-H-COR

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

El indicador de validez fisica de PoseBusters que el programa venia reportando esta dominado por un defecto de la capa de RECONSTRUCCION, no por tension real del ligando dockeado. Si es asi, regenerar los hidrogenos desde la geometria de atomos pesados dockeada -manteniendolos completamente fijos- cambia la tasa de validez de forma material sin mover un solo atomo pesado.

## Protocolo

Referencia: `Ver prerregistro sellado MF-33-H-COR-PRE, anterior a esta corrida, que fija el protocolo, los dos ambitos, las cinco invariantes por pose y la lista explicita de lo que queda suspendido. Sin computo de docking: se reevaluan poses YA RETENIDAS. AMBITO A: 48 complejos y 8224 poses del brazo flexible retenidas por MF-33-B-RET-R2 -8224 y no 8215 porque R2 redockeo 1afl, que pasa de 258 a 267 poses; era la unica diferencia predicha en los limites declarados de MF-33-PB-. AMBITO B: 116 complejos del protocolo rigido, top-1 de los dos brazos, 232 poses reconstruidas desde los conf<i>.out.pdbqt en disco. Runner: scripts/run_mf33hcor_reconstruccion.py, ejecutado en el servidor 192.168.1.64, contenedor mf33hcor, imagen moldesign-lab-pb:0.6.5, 164/164 trabajos, salida 0. Consolidacion y verificacion independiente: scripts/analisis_mf33hcor_consolidado.py, que RECALCULA desde los checkpoints por pose todo lo que el artefacto afirma, contrasta complejo a complejo contra MF-33-PB y MF-33-TOP1 sellados, y reusa por composicion el McNemar exacto, el Wilson y el MDE de scripts/estadistica_fnd04.py. Los 331 archivos se bajaron con SHA-256 contrastado contra el servidor: 331 coinciden, 0 difieren, 0 faltan. MF-33-PB y MF-33-TOP1 no se tocan: quedan sellados e inmutables.`

## Gate

SIN GATE DE ACEPTACION, Y ES DELIBERADO. Un corrigendum de implementacion no se aprueba ni se rechaza: se ejecuta y se reporta, con la reconstruccion historica al lado para que la diferencia sea auditable. NO ES CIEGO Y NO LO FINGE: los 12 complejos del piloto diagnostico fueron inspeccionados antes de disenar la correccion, y la prueba tecnica previa al sellado del prerregistro miro ademas 10gs del ambito B; ese piloto DEMUESTRA EL DEFECTO Y DISENA LA CORRECCION, no estima la tasa nueva, que es lo que mide este artefacto sobre las cohortes completas. LA CONDICION DE VALIDEZ del artefacto no es un umbral de tasa sino las cinco invariantes por pose: desplazamiento pesado maximo dentro de 1e-6 A, SMILES canonico identico, carga formal identica, numero de enlaces identico y cero hidrogenos heredados del cristal. Una pose que viole cualquiera de ellas no entra en la tasa y se cuenta aparte. SEGUNDA CONDICION: la reconstruccion HISTORICA de esta tuberia debe reproducir complejo a complejo lo que sellaron MF-33-PB y MF-33-TOP1; sin eso, un cambio de tasa podria ser un cambio de tuberia. PROHIBIDO: modificar o re-sellar MF-33-PB y MF-33-TOP1; presentar la tasa corregida como si viniera de una medicion ciega; concluir nada sobre el PROTOCOLO DE DOCKING, que no se toca aqui; afirmar exactitud de pose o de union; y afirmar ventaja de un brazo sobre otro o equivalencia entre ellos.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `f003cd9e7a42f510e8120a4ecc9e4b1647dd1035`, dirty=True

## Estado

- Creado: 2026-08-23T17:37:53.643001+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T17:39:22.558970+00:00)
- Finalizado: 2026-08-23T17:40:11.914915+00:00
- Razón de la decisión: CORRECCION CONFIRMADA. La reconstruccion historica de hidrogenos contaminaba la medicion de validez fisica. Con atomos pesados IDENTICOS y los hidrogenos regenerados desde la geometria dockeada y relajados con los pesados completamente fijos, la tasa PB-valid pasa de 2.64% a 99.48% en el ambito flexible (8181 de 8224 poses) y de 12.07% a 93.10% en los top-1 rigidos (216 de 232). Las tasas historicas y las conclusiones dominadas por internal_energy QUEDAN INVALIDADAS Y REEMPLAZADAS. ESTO NO DEMUESTRA exactitud de pose, ni union, ni superioridad de ningun brazo.

POR QUE LA CORRECCION ES CREIBLE, y no solo favorable. Primero, LAS CINCO INVARIANTES SE CUMPLEN EN LAS 8456 POSES, verificadas de forma independiente por scripts/analisis_mf33hcor_consolidado.py y no por el contador del runner: desplazamiento pesado maximo 0.0 A, SMILES canonico identico, carga formal identica, numero de enlaces identico, CERO hidrogenos heredados del cristal, CERO violaciones. La molecula corregida es la misma molecula. Segundo, LA REPRODUCCION DE LO HISTORICO ES EXACTA, complejo a complejo y no en agregado: la rama HISTORICA de esta tuberia reproduce el top-1 pb_valid de MF-33-PB en los 48 complejos del ambito A y el pb_valid_fisica de MF-33-TOP1 en los 116 del ambito B, con CERO discordancias. Sin esa reproduccion, un cambio de tasa podria ser un cambio de tuberia; con ella, la unica variable que cambia es la reconstruccion de hidrogenos. Tercero, los 331 archivos se bajaron del servidor con SHA-256 contrastado: 331 coinciden, 0 difieren, 0 faltan.

EL AMBITO A CORRE SOBRE R2, NO SOBRE R1: 8224 poses, no las 8215 que sello MF-33-PB. La unica diferencia de cohorte es 1afl, que aporta 267 poses en R2 frente a 258 en R1, y ESTABA PREDICHA en los limites declarados de MF-33-PB. En consecuencia, EL 8006 DE ESTE ARTEFACTO NO ES EL 7997 DE MF-33-PB: aquel contaba internal_energy sobre 8215 poses de R1 y este sobre 8224 de R2. No es una correccion de la cifra vieja sino otra cohorte, y la caida que este corrigendum mide es 8006 -> 7 DENTRO DE LA MISMA COHORTE R2.

DOUBLE_BOND_FLATNESS: 598 -> 0, Y ESO CORRIGE UNA AFIRMACION NUESTRA. El prerregistro y el commit del corrigendum dijeron que el defecto afectaba a la energia interna. Tambien contaminaba la planaridad de dobles enlaces, que depende de los hidrogenos sustituyentes. La afirmacion previa de que solo estaba afectada la energia era incompleta y queda corregida aqui.

NO ES CIEGO Y NO LO FINGE. Los 12 complejos del piloto diagnostico fueron INSPECCIONADOS antes de disenar la correccion, y la prueba tecnica previa al sellado del prerregistro miro ademas 10gs del ambito B. Ese piloto demuestra el defecto y disena la correccion; NO estima la tasa nueva, que es lo que mide este artefacto sobre las cohortes completas. Un corrigendum de implementacion no se aprueba ni se rechaza: se ejecuta y se reporta. La decision GO es la unica etiqueta compatible con el esquema y significa AQUI «la correccion queda establecida y reemplaza a la medicion anterior», no «el sistema pasa un umbral».

SIN EVIDENCIA INTERPRETABLE DE DIFERENCIA ENTRE BRAZOS, que no es lo mismo que equivalencia. Ambito A: single 48/48 contra ensemble 47/48, tabla pareada ambos=47, solo_ensemble=0, solo_single=1, ninguno=0, McNemar exacto p=1.0, MDE 5.41 pp. Ambito B: single 106/116 contra ensemble 110/116, tabla pareada ambos=104, solo_ensemble=6, solo_single=2, ninguno=4, McNemar exacto p=0.289062, MDE 6.61 pp. Con la tasa corregida cerca del techo, este diseno no distingue entre brazos. NO se afirma que gane el single, NI que gane el ensemble, NI que sean equivalentes: lo ultimo exigiria una prueba de no-inferioridad con margen preregistrado, que aqui no existe.

LOS RECUENTOS POR CONTROL SE SOLAPAN Y NO SUMAN POSES INVALIDAS UNICAS. Una misma pose puede fallar varios controles. Ambito A: 43 poses invalidas unicas frente a una suma de 57 recuentos por control. Ambito B: 16 unicas frente a 17. Las combinaciones de controles, que si son disjuntas, se reportan en metrics.json.

EL RESIDUO CIENTIFICO ES LO QUE QUEDA VIVO, y ahora si es caracterizable. Las 43 poses del ambito A que siguen invalidas se concentran en SIETE complejos -21 de ellas en 1nm6 y 9 en 1mmq- y sus fallos son geometricos: internal_steric_clash 23, minimum_distance_to_protein 13, y un bloque de 7 poses que fallan bond_angles, bond_lengths e internal_energy A LA VEZ, siempre juntos. No es tension generalizada del ligando: es un subconjunto pequeno y localizado que merece caracterizacion posterior. Lo mismo en el ambito B, donde 14 de las 16 invalidas son contacto con la proteina.

QUE SIGUE EN PIE Y QUE NO. Se invalidan y se reemplazan: 217/8215 = 2.64%; el 97.3% de fallos por internal_energy; el 8/48 contra 10/48 de MF-33-PB; el 8.62% contra 15.52% de MF-33-TOP1; y las conclusiones «la validez fisica es deficiente», «el ensemble no la arregla» y «una minimizacion post-docking atacaria el problema». NO se ven afectados: RMSD y cobertura del oraculo, top-1, top-5 y la cascada de conversion, las coordenadas de atomos pesados. MF-33-PB y MF-33-TOP1 no se tocan: quedan sellados e inmutables con sus cifras, que este artefacto reproduce y explica. MF-33-MIN queda confirmado como CANCELLED_BEFORE_EXECUTION / SUPERSEDED_BY_MF-33-H-COR: no queda tension generalizada que minimizar.

LA CONDICION QUE NO SE PUEDE OMITIR AL CITAR ESTA CIFRA. El 99.48% es CONDICIONAL a una reconstruccion canonica de hidrogenos. El PDBQT es una representacion de atomo unido y no contiene la geometria explicita completa, asi que «el pipeline produce 99.48% de poses fisicamente validas» es una frase incorrecta sin esa condicion. La formulacion correcta es que las poses de atomos pesados son mayoritariamente compatibles con los controles fisicos de PoseBusters DESPUES de una reconstruccion canonica de hidrogenos.
- Hashes de dataset: 6 archivo(s) con SHA-256
- Hashes de assets: 4 archivo(s) con SHA-256

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
