# PROD-PV-H-01

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La representacion de hidrogenos con que produccion evalua una pose cambia el veredicto de validez fisica, y el proxy energetico RDKit del escalon 2 no es equivalente al internal_energy de PoseBusters. Si lo primero es cierto, la ruta mixta discrepa de la canonica bajo el MISMO evaluador oficial; si lo segundo, el proxy discrepa del evaluador oficial sobre la MISMA representacion.

## Protocolo

Referencia: `Ver prerregistro sellado PROD-PV-H-01-PRE, anterior a esta corrida, que fija los tres brazos, los parametros oficiales leidos de config/dock.yml, las cinco reglas de decision, las tres coberturas reportadas por separado y la calificacion del instrumento. Runner: scripts/run_prodpvh01_representacion_h.py, SHA-256 b4957f9dbef7c7776889a94b0fa8b7e302f5121c3952403f5a2ccbb73ca848cc, congelado ANTES del sello del prerregistro. Cohorte: 116 complejos del protocolo rigido, top-1 de los dos brazos de docking, 232 poses; la misma del ambito B de MF-33-H-COR. Sin computo de docking: se reevaluan poses ya retenidas. La canonicalizacion se reutiliza de run_mf33hcor_reconstruccion.py con su hash sellado verificado en ejecucion.`

## Gate

IDENTICO al de PROD-PV-H-01-PRE y no se toca. R1: alguna A:PASA -> C:FALLA obliga a no promover la representacion mixta. R2: alguna A:FALLA -> C:PASA demuestra falsas alarmas de la ruta actual. R3: si B discrepa de A en cualquier pose, el proxy no puede etiquetarse internal_energy. R4, independiente de los datos: el proxy sigue siendo proxy aunque coincida en todas. R5: sin PoseBusters solo NO EVALUADA o proxy declarado sin autoridad de PoseBusters. La cobertura del lector se declaro en el prerregistro como calificacion del instrumento, observada antes del sello, y NO se presenta aqui como hallazgo ciego.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `f003cd9e7a42f510e8120a4ecc9e4b1647dd1035`, dirty=True

## Estado

- Creado: 2026-08-23T19:21:55.226173+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T19:22:03.494933+00:00)
- Finalizado: 2026-08-23T19:22:36.565194+00:00
- Razón de la decisión: LAS DOS DEUDAS QUEDAN RESUELTAS, Y EN DIRECCIONES DISTINTAS. La representacion de hidrogenos NO cambio ningun veredicto en esta cohorte; el proxy energetico SI discrepa del evaluador oficial, y siempre en la direccion de FALSA ALARMA. Cobertura 232/232 en lector, canonicalizacion y evaluador, con cero invariantes violadas.

DEUDA 1, REPRESENTACION: SIN EFECTO DETECTABLE, PERO EL DISENO NO TUVO PODER PARA DETECTARLO, y esto es lo primero que hay que decir. A vs C da 0 discordantes sobre 232, asi que R1 y R2 no se disparan. Pero la razon honesta no es que las dos representaciones sean equivalentes: es que LAS 232 POSES PASAN el control oficial en los DOS brazos. Sin una sola pose que falle, la comparacion no tuvo ningun caso discriminante. El energy_ratio oficial se mueve entre -20.3 y 19.1 contra un umbral de 100.0, es decir un orden de magnitud por debajo del corte. LO QUE SE PUEDE AFIRMAR es que sobre esta cohorte la representacion mixta no produjo ni una falsa tranquilidad ni una falsa alarma. LO QUE NO SE PUEDE AFIRMAR es que las dos representaciones sean equivalentes en general: eso exigiria una cohorte con poses que fallen, y aqui no la hay.

DEUDA 2, PROXY: R3 SE DISPARA CON 33 DE 232. El proxy discrepa del evaluador oficial en 33 poses, y las 33 van en la MISMA direccion: proxy FALLA donde el oficial PASA. Es decir, el proxy no es conservador ni ruidoso: RECHAZA POSES BUENAS. Sus razones en esos 33 casos van de 124.3 a 18 582 565, contra su umbral de 100.0, mientras el oficial las situa holgadamente dentro de rango. La causa es la que ya estaba documentada y ahora esta medida: no comparten campo de fuerza -MMFF contra UFF-, ni tamano de ensemble -16 contra 50-, ni la cantidad comparada -(pose-min)/(media-min) contra pose/media-, y el 100.0 de cada uno se aplica a cosas distintas. EL PROXY NO PUEDE ETIQUETARSE `internal_energy`, y por R4 -que no depende de los datos- tampoco podria aunque hubiera coincidido en las 232.

CONSECUENCIA DE PRODUCTO, y estaba preregistrada. La regla decia: cualquier proxy FALLA -> PoseBusters canonico PASA demuestra falso rechazo y obliga a que el fallback solo emita REVISION, nunca FALLA. Se cumple 33 veces sobre 232, el 14.2%. El escalon 2 no puede seguir emitiendo un veredicto de FALLA.

EL INSTRUMENTO HUBO QUE REPARARLO ANTES, y sin eso este artefacto no habria significado nada. El lector anterior leia las columnas 77-78 del PDBQT como simbolo quimico cuando ahi vive el tipo AutoDock: cubria 40 de 232 poses, y el fallo estaba CORRELACIONADO CON LA AROMATICIDAD. Cualquier matriz calculada sobre ese 17% habria parecido un resultado y no lo habria sido. El lector reparado -plantilla quimica, index_map serial->indice, coordenadas por columnas fijas, pseudo-atomos de pegado de macrociclo descartados por tipo- cubre 232/232. Esa calificacion se observo ANTES del sello, se declaro en el prerregistro y NO se presenta como hallazgo ciego.

LAS TRES COBERTURAS, por separado porque un NO EVALUADA no significa lo mismo segun de donde venga: lector 232/232, canonicalizacion 232/232, evaluador 232/232 finitos. Invariantes: desplazamiento pesado 0.0 A, SMILES isomerico, carga y enlaces identicos en las 232, y num_h_added == 0 en el brazo canonico, que confirma que la canonicalizacion llega entera y PoseBusters no anade ni relaja nada encima.

QUE NO SALE DE AQUI. Nada sobre exactitud de pose, union ni protocolo de docking. Nada sobre la bateria completa de PoseBusters: esto mide el control energetico y solo ese. Y nada que promueva el proxy: por R4, la concordancia empirica no convierte una formula distinta en la metrica oficial.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-08-23T19:51:54.660267+00:00: `backend/services/chemistry/pose_physical_validity.py` `f1228446→9f06756f` — EL ASSET CAMBIO DESPUES DEL SELLO, Y CAMBIO PORQUE ESTE MISMO EXPERIMENTO LO OBLIGO. La corrida uso backend/services/chemistry/pose_physical_validity.py con SHA-256 f12284460037bcdcf54a1bae3d824e3d3bb764ccb5adc3b82110f10530e836f4, que es el hash sellado y el que queda registrado como el que produjo el resultado. Despues del sello se aplico la consecuencia de producto que la regla preregistrada del gate exigia -el escalon degradado solo emite REVISION y nunca FALLA, porque el proxy rechaza el 14.2% de las poses que el control oficial aprueba- y se cerro el docstring del modulo con el resultado de las dos deudas.

LA MEDICION NO SE VE AFECTADA, y se puede comprobar: el runner no llama a evaluar_pose_fisica, que es la unica funcion que cambio en el comportamiento. Usa leer_pose_pdbqt, proxy_tension_rdkit y clasificar_resultado_pb, que son identicas entre los dos hashes. El cambio es de EMISION DE VEREDICTO en produccion, no de calculo.

ERROR DE PROCEDIMIENTO RECONOCIDO: no se debe sellar como asset la ruta VIVA de un modulo de produccion. Un modulo de produccion cambia por definicion, y aqui cambio justamente porque el experimento cumplio su proposito. Lo correcto habria sido sellar una copia congelada dentro del artefacto y dejar la ruta viva fuera del sello. Queda anotado para los proximos. (commit 9824790076f32857bfd844e109f0988f8bdc2f4a)
- 2026-08-23T19:52:18.863728+00:00: `backend/tests/test_pose_physical_validity.py` `8c20984d→36011ab8` — MISMO CASO Y MISMA CAUSA que el modulo de produccion: el asset cambio DESPUES del sello porque el propio experimento lo obligo. Se anadio `test_el_fallback_nunca_emite_falla`, la prueba de regresion de la consecuencia de producto que disparo la regla preregistrada del gate: el escalon degradado solo emite REVISION, nunca FALLA. El hash con el que corrio el experimento queda registrado abajo.

NO AFECTA A LA MEDICION: es una prueba de contrato del modulo de produccion; el runner no la importa ni la ejecuta. La prueba anadida solo verifica un comportamiento que se implemento DESPUES de leer el resultado, y por eso no podia existir antes del sello.

Misma leccion que el otro asset: no sellar como asset la ruta viva de codigo que el propio experimento va a obligar a cambiar. (commit 9824790076f32857bfd844e109f0988f8bdc2f4a)

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
