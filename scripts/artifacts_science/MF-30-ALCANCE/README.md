# MF-30-ALCANCE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

MF-30 -evaluar un modelo generativo preentrenado, prioridad 3 de la seccion 20.11- ya no es una direccion de producto defendible: su gate esta caducado frente al mejor brazo propio, su premisa esta contradicha por evidencia externa publicada, y choca con la restriccion de que MolDesign sea 100% CPU.

## Protocolo

Referencia: `REGISTRO DE CAMBIO DE ALCANCE, SIN COMPUTO. Calcula la tabla de comparadores desde artefactos sellados -MF-09 para el gate escrito, los tres brazos de MF-33 para el comparador activo, y MF-33-A3 si esta disponible- y registra como EXTERNA, con fuente citable, la evidencia de PoseBusters (Chemical Science 15, 3130, 2024). Script: scripts/analisis_mf30_alcance.py. No modifica el texto de la seccion 20.11(c): un prerregistro o una seccion superada se documenta, no se reescribe.`

## Gate

REGISTRO DE DECISION, SIN GATES DE MEDICION. Las tres razones se documentan con su evidencia y la decision queda declarada junto con sus condiciones de reapertura, para que reabrir MF-30 no exija reconstruir el razonamiento. LIMITACION DECLARADA: las cifras de PoseBusters son externas y se citan con fuente; no las ha medido este programa. No cancela MF-30 ni cierra la seccion 20.11(c).

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `experimentos/ruta-c-molflex`, commit `8f7cbb1a87559928540577677642f0a948d7e025`, dirty=True

## Estado

- Creado: 2026-08-21T02:12:22.719362+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-21T02:12:23.272435+00:00)
- Finalizado: 2026-08-21T02:12:23.422171+00:00
- Razón de la decisión: MF-30 pasa de PRIORIDAD 3 DE LA CARTERA PESADA Y DIRECCION DE PRODUCTO a BENCHMARK EXTERNO OPCIONAL. No se cancela, no se borra y no deja hueco en la cartera. RAZON 1, EL GATE ESTA CADUCADO 8.67x. El doc 49 lo escribio como 'cobertura superior al 3/33 de MF-09', que era el techo del generador con protocolo RIGIDO y el estado del arte del programa entonces. MF-33 midio despues que el ensemble FLEXIBLE propio alcanza 26 de 33 en el mismo estrato y la misma cohorte. Un modelo generativo con 8/33 pasaria el gate escrito siendo tres veces peor que lo que ya existe en casa: es comparar contra placebo cuando ya hay tratamiento estandar. El gate exige comparador activo y el activo no es el 3/33. RAZON 2, LA PREMISA ESTA CONTRADICHA POR EVIDENCIA EXTERNA. La seccion 20.11(c) coloca al generativo como el de mayor techo, y esa premisa es anterior a que se midiera. PoseBusters -Buttenschoen, Morris y Deane, Chemical Science 15, 3130, 2024- evaluo cinco metodos de aprendizaje profundo contra los clasicos sobre 308 complejos exigiendo RMSD <=2 A Y validez fisica: AutoDock Vina 58%, Gold 55%, DiffDock 12%, siendo DiffDock el mejor de los DL. Y el modo de fallo que reporta es especifico y agrava el caso: los metodos aprendidos producen poses que puntuan bien y son fisicamente imposibles. Estas cifras son EXTERNAS, se citan con fuente y se registran como tales; la seccion 20.12 prohibe citar analogias como evidencia y esto no es una analogia sino un benchmark publicado y auditable. RAZON 3, CHOCA CON UNA RESTRICCION DE PRODUCTO DECLARADA: MolDesign es 100% CPU y la GPU es opcional, nunca limitante. Un modelo de difusion como motor convierte la GPU en requisito. La distincion que sobrevive y queda escrita: la GPU puede estar en el LABORATORIO y no en el PRODUCTO -usarla para construir o validar un artefacto entregable en CPU es compatible; entregarla como motor, no-. TRES CONDICIONES DE REAPERTURA, declaradas ahora para no reconstruir el razonamiento despues: un generativo con inferencia en CPU en tiempo razonable o un uso estrictamente de laboratorio con entregable en CPU; un gate reescrito con comparador activo del momento y el control de solapamiento del doc 49 intacto; y evidencia externa posterior que revierta el resultado de PoseBusters sobre validez fisica. Ninguna se cumple hoy. NOTA: MF-33-A3 esta corriendo y puede mover la magnitud del comparador activo si demuestra que la ventaja del brazo B era conteo de poses; eso cambiaria el 26/33 pero no la conclusion, porque incluso el brazo A -un solo conformero flexible- queda muy por encima del 3/33 del gate escrito.
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
