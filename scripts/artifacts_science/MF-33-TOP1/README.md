# MF-33-TOP1

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La ganancia del ensemble de conformeros, que MF-33 midio sobre la COBERTURA DEL ORACULO, llega tambien a lo que el usuario recibe -el top-1 por score-. MF-09 midio top-1 acierta 0/33 y top-20 2/33 en el estrato dificil, asi que subir el techo podria no mover la entrega.

## Protocolo

Referencia: `SIN COMPUTO DE DOCKING. Los conf<i>.out.pdbqt del protocolo congelado estan en disco para los 116 de train con sus scores y 9 modelos por corrida. Dos brazos pareados: SINGLE con las 9 poses de conf0.out, ENSEMBLE con las Kx9 de todos. Por brazo: top1 -rmsd de la pose de mejor score-, top5 -mejor rmsd entre las 5 de mejor score- y oraculo. Se anade pb_valid_fisica de posebusters_metrica sobre el top-1 de cada brazo. Script: scripts/analisis_mf33top1_llega_al_selector.py.`

## Gate

McNemar exacto pareado sobre acierta <=2 A, por separado en top1, top5 y oraculo. TRES LECTURAS ESCRITAS ANTES: LA VENTAJA LLEGA AL USUARIO si mejora oraculo Y top1 con p<0.05; EL CUELLO SE DESPLAZA A LA SELECCION si mejora oraculo y no top1; SIN EFECTO EN ESTE PROTOCOLO si no mejora el oraculo. LIMITACION CENTRAL DECLARADA: estas poses son del protocolo RIGIDO. Las flexibles del brazo B no existen -run_mf28_roadmap.py las escribio en un TemporaryDirectory-, asi que esto NO mide el brazo del paper: mide si el MECANISMO llega al selector en el unico protocolo cuyas poses sobrevivieron.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `38a6bc2e12e64269919856d8063a5f8f6a36a8a1`, dirty=True

## Estado

- Creado: 2026-08-21T04:29:47.625321+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-21T04:29:49.212395+00:00)
- Finalizado: 2026-08-21T05:42:51.538018+00:00
- Razón de la decisión: El gate preregistrado da LA_VENTAJA_LLEGA_AL_USUARIO, y esa etiqueta se conserva porque se escribio antes de mirar, PERO NO DEBE USARSE COMO TITULAR EN TEXTO EXTERNO: como afirmacion cientifica sobrepasa lo medido. La formulacion correcta es que LA GANANCIA EN COBERTURA DEL ORACULO SE PROPAGA SOLO PARCIALMENTE a las predicciones mejor ranqueadas. LA ATENUACION AGUAS ABAJO ES EL RESULTADO: oraculo +26.72 pp (35 -> 66 de 116, b=31 c=0, p=0.0), top-5 +15.52 pp (35 -> 53, b=20 c=2, p=0.000121), top-1 +11.21 pp (22 -> 35, b=13 c=0, p=0.000244). De los +31 complejos ganados a nivel de oraculo sobreviven 18 a top-5 -58% de la ganancia- y solo 13 a top-1 -42%-. FORMULACION PUBLICABLE, SIN CAUSALIDAD, y es la que hay que usar: 'aunque el muestreo por ensemble aumento la cobertura del oraculo, la fraccion de complejos cubiertos que se realiza en top-1 bajo del 62.9% al 53.0%, ampliando el hueco oraculo-a-top-1 de 13 a 31 complejos'. Los cuatro numeros son el hecho observado; estan RELACIONADOS MATEMATICAMENTE y la causalidad NO esta demostrada. La interpretacion se separa y va aparte: 'aumentar la cobertura de candidatos parece imponer una carga mayor sobre la seleccion de pose'. ENMIENDA DEL 2026-08-21, SEGUNDA: la version anterior de esta razon decia que mejorar la generacion AGRAVA el cuello de seleccion PORQUE el oraculo sube mas rapido que la capacidad de elegir. Eso afirmaba causalidad que estos datos no establecen y se retira. SUTILEZA QUE UN REVISOR SENALARA Y HAY QUE ANTICIPAR: 53.0% NO significa que el selector sea peor. El selector del brazo ensemble se enfrenta a un PROBLEMA DISTINTO -espacio de candidatos mucho mayor y potencialmente mas cuencas competitivas-, asi que la caida de 62.9% a 53.0% no demuestra por si sola que el algoritmo de ranking se haya degradado intrinsecamente. Lo que si demuestra, y basta para identificar seleccion como el siguiente cuello: LA CAPACIDAD DEL PIPELINE DE CONVERTIR COBERTURA DISPONIBLE EN TOP-1 NO ESCALA PROPORCIONALMENTE CON EL AUMENTO DE COBERTURA. LO QUE ESTO CIERRA Y LO QUE DEJA EXPUESTO: cierra la amenaza T1 del paper a nivel de mecanismo, porque el efecto no vive exclusivamente en una metrica de oraculo. Y deja expuestos dos cuellos posteriores que quedaban ocultos detras del de generacion: (1) SELECCION, con 31 complejos que contienen una solucion correcta que no llega a top-1 y que estan nominalmente identificados en per_complex.jsonl; (2) VALIDEZ FISICA. Falta contestar T1 sobre el brazo FLEXIBLE, que es el del paper; para eso esta sellado MF-33-B-RET-PRE. EN COLOCACION NO HAY SENAL Y ERA PREVISIBLE: 0 de 33 en los tres campos para ambos brazos, porque el protocolo rigido tiene techo de 1/33 en el estrato dificil segun el brazo C de MF-33. HALLAZGO LATERAL DE PRIMER ORDEN, exploratorio: la validez fisica del top-1 entregado es del 8.62% en single y del 15.52% en ensemble; mas del 84% de lo que el pipeline entrega no pasa PoseBusters, con internal_energy dominando. Importa para no optimizar una metrica intermedia: un selector que pase de 35 a 55 entregando poses invalidas no habria mejorado el producto. LIMITES: protocolo rigido y no flexible; se ordena por score de Vina sin rescoring; SINGLE usa conf0 por indice y no por calidad; el ensemble selecciona sobre un pool K veces mayor, que es el fenomeno y no un confundido.
- Hashes de dataset: 1 archivo(s) con SHA-256
- Hashes de assets: 2 archivo(s) con SHA-256

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
