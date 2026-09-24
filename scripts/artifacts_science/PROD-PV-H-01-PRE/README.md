# PROD-PV-H-01-PRE

Registro experimental generado por `scripts/experiment_manifest.py` (FND-01).
Este archivo se regenera desde `manifest.json`; no editar a mano.

## Hipótesis

La representacion de hidrogenos con que produccion evalua una pose cambia el veredicto de validez fisica, y el proxy energetico RDKit del escalon 2 no es equivalente al internal_energy de PoseBusters. Si lo primero es cierto, la ruta actual -mixta: polares explicitos de Vina, no polares implicitos- discrepa de la reconstruccion canonica bajo el MISMO evaluador oficial. Si lo segundo es cierto, el proxy discrepa del evaluador oficial sobre la MISMA representacion.

## Protocolo

Referencia: `VALIDACION DE CONFORMIDAD DE LA MEDICION, no experimento de rendimiento del docking. Poses fijas y atomos pesados IDENTICOS en los tres brazos; lo unico que cambia es la representacion de hidrogenos y el evaluador. COHORTE: 116 complejos del protocolo rigido, top-1 de los dos brazos de docking, 232 poses; la misma del ambito B de MF-33-H-COR para poder contrastar. BRAZOS: A_PROD_FULL_CURRENT = PDBQT -> representacion mixta actual -> PoseBusters oficial; B_PROD_PROXY_CURRENT = PDBQT -> representacion mixta actual -> proxy RDKit propio; C_TARGET_CANONICAL = PDBQT -> reconstruccion canonica -> PoseBusters oficial. A vs C aisla el efecto de la representacion con el mismo evaluador a los dos lados; B vs A aisla el efecto del proxy sobre la misma representacion. D_PROXY_SOBRE_CANONICA se calcula como SECUNDARIO descriptivo y no responde ninguna de las dos preguntas. EVALUADOR OFICIAL: posebusters.modules.energy_ratio.check_energy_ratio con los parametros de config/dock.yml leidos del paquete instalado -UFF, 50 conformeros, umbral energy_ratio <= 100.0, energy_ratio = mol_pred_energy / ensemble_avg_energy-; NO los defaults 7.0/100 de la funcion aislada, que dock no usa. CANONICALIZACION REUTILIZADA, no reimplementada: reconstruir(..., corregida=True) de scripts/run_mf33hcor_reconstruccion.py, sellado en MF-33-H-COR con SHA-256 072746e4530ec8fc2cbdaae0356b2b71fb52b65d23e0f758e192fbbcd09b5e95, verificado en tiempo de ejecucion; el runner aborta si no coincide. LECTOR: plantilla quimica + index_map serial->indice + coordenadas leidas por columnas fijas. El PDBQT aporta SOLO coordenadas; grafo, carga y ordenes de enlace no se infieren de el. Los pseudo-atomos de pegado de macrociclo -tipo AutoDock G- se descartan por tipo, y cualquier otro serial no mapeado, mapa no biyectivo o atomo PESADO sin coordenada produce NO EVALUADA en vez de una reconstruccion heuristica. TRES COBERTURAS REPORTADAS POR SEPARADO: lector, canonicalizacion y evaluador, porque un NO EVALUADA no significa lo mismo si viene del formato, de la identidad, de la quimica, de la parametrizacion, de la generacion de conformeros o del propio PoseBusters. METRICAS POR POSE: estado, energy_ratio, mol_pred_energy, ensemble_avg_energy, num_h_added, motivo de no evaluacion, politica de H, motor con version y parametros, y tiempo. AGREGADAS: matrices de cambio A<->C y B<->A con ejemplos, asociacion descriptiva con H polares, H totales, carga, tamano y donadores, y tasa no evaluable. INVARIANTES POR POSE: desplazamiento pesado 0, SMILES isomerico identico, carga identica, enlaces identicos, cero H heredados, determinismo, y num_h_added == 0 en el brazo C como marcador de que la canonicalizacion llego entera. Runner: scripts/run_prodpvh01_representacion_h.py, SHA-256 b4957f9dbef7c7776889a94b0fa8b7e302f5121c3952403f5a2ccbb73ca848cc.`

## Gate

REGLAS DE DECISION. R1: si existe alguna pose A:PASA -> C:FALLA, la representacion mixta NO SE PROMUEVE, porque da falsa tranquilidad; es la regla que mas pesa, porque el error va en la direccion peligrosa. R2: si existe alguna A:FALLA -> C:PASA, la ruta actual produce FALSAS ALARMAS; tambien favorece canonicalizar. R3: si B discrepa de A en cualquier pose, el proxy NO PUEDE ETIQUETARSE internal_energy. R4, Y NO DEPENDE DE LOS DATOS: aunque B coincidiera en todas, sigue siendo un proxy; una formula distinta -MMFF contra UFF, 16 conformeros contra 50, (pose-min)/(media-min) contra pose/media- no se convierte en la metrica oficial por concordancia empirica, y ningun resultado de este artefacto puede promoverlo. R5: sin PoseBusters solo hay dos salidas honestas, NO EVALUADA o proxy declarado sin identidad ni autoridad de PoseBusters. CALIFICACION DEL INSTRUMENTO, OBSERVADA ANTES DEL SELLO Y NO ES RESULTADO DEL EXPERIMENTO. El lector original cubria 40/232 = 17.2% y el truncado a columnas PDB 156/232 = 67.2%, con el fallo CORRELACIONADO CON LA AROMATICIDAD -el tipo AutoDock A en las columnas 77-78-. El lector se reparo y se califico sobre la cohorte ENTERA en modo coverage-only, sin ejecutar ni leer los brazos energeticos: 232/232 en lector, 232/232 en canonicalizacion, 0 invariantes violadas, desplazamiento pesado 0.0 A, 12 pseudo-atomos de pegado descartados en los tres macrociclos. Estas cantidades se declaran aqui porque fingir que siguen ocultas seria incorrecto. En la corrida final se vuelve a reportar el flujo de elegibilidad para auditoria, pero NO se presenta como hallazgo ciego. OBSERVACIONES TECNICAS NO INTERPRETABLES, registradas para que no parezcan un descubrimiento cuando la corrida las reproduzca: en la prueba tecnica sobre casos DIAGNOSTICOS -no una muestra- el proxy dio NO_EVALUADO en 2 de 6 poses con el lector viejo, y FALLA en 2 de 10 con el reparado, donde el oficial dio PASA. No entran en ninguna conclusion. PROHIBIDO: leer los gates con --limite o --tecnico, que emiten NO_LEER_GATES_TECNICOS; promover el proxy a internal_energy por concordancia; concluir nada sobre exactitud de pose, union o protocolo de docking; y aceptar una exclusion de poses correlacionada con aromaticidad o carga.

## Ambiente

- Sistema operativo: Windows (AMD64)
- CPU: 12 núcleos
- RAM total: 32659 MB
- GPU: NVIDIA GeForce GTX 1660 SUPER
- Python: 3.14.3
- Seeds: 42
- Git: rama `codex/mejora-producto`, commit `f003cd9e7a42f510e8120a4ecc9e4b1647dd1035`, dirty=True

## Estado

- Creado: 2026-08-23T19:09:49.491193+00:00
- Status: finished
- Decisión: GO
- Sellado: sí (2026-08-23T19:09:58.315344+00:00)
- Finalizado: 2026-08-23T19:10:35.855005+00:00
- Razón de la decisión: Prerregistro sellado DESPUES de la prueba tecnica y de la calificacion del instrumento, que es el orden que este programa aprendio a golpes: sellar antes de probar no gana ceguera y cuesta un artefacto extra.

NO ES CIEGO EN UN PUNTO Y SE DICE CUAL. La cobertura del lector se observo ANTES del sello -40/232 con el lector original, 156/232 truncando, 232/232 con el reparado- porque reparar el instrumento exigia medirlo. Esas cantidades son CALIFICACION DEL INSTRUMENTO, no resultado del experimento, y fingir que siguen ocultas seria incorrecto. Lo que SI esta ciego es lo unico que importa: nadie ha ejecutado ni leido los brazos energeticos sobre la cohorte. El modo coverage-only existe precisamente para calificar el lector sin tocarlos.

POR QUE HUBO QUE REPARAR EL LECTOR ANTES DE EMPEZAR. El lector anterior hacia MolFromPDBBlock sobre las lineas del PDBQT y despues parcheaba con AssignBondOrdersFromTemplate. En un PDBQT las columnas 77-78 llevan el TIPO AUTODOCK, no el simbolo quimico: `A` es carbono aromatico, `NA` nitrogeno aceptor, `HD` hidrogeno donador. RDKit intentaba leer `A` como elemento, abortaba con `anum > -1` y devolvia None para la molecula entera. Resultado medido sobre las 232 poses: 40 legibles (17.2%), 178 muertas en la lectura y 14 en la valencia de la plantilla. El fallo estaba CORRELACIONADO CON LA AROMATICIDAD, que es la peor forma posible de perder datos: cualquier matriz A<->C calculada sobre ese 17% habria sido no interpretable, y habria parecido un resultado.

EL ARREGLO NO ES TRUNCAR. Truncar a columnas PDB quita la confusion del tipo, pero obliga a RDKit a inferir el grafo desde distancias y luego a corregirlo con la plantilla: la cobertura sube a 156/232 y los fallos de valencia suben de 14 a 70. Inferir y despues parchear no es una ruta principal aceptable. La ruta correcta ya existia en el programa: el SMILES es la autoridad quimica, index_map.json conserva la identidad atomica, y el PDBQT aporta UNICAMENTE coordenadas, leidas por columnas fijas. Es el mismo patron del corrigendum MF-33-H-COR.

CUBRE 232/232, Y LOS SEIS CASOS QUE FALTABAN ENSENARON ALGO. Con la ruta del mapa quedaban 6 poses fuera, de 1mmq, 1mmr y 1nm6, cada una con exactamente dos seriales sin entrada en el mapa. No era un mapa roto: son PSEUDO-ATOMOS DE PEGADO tipo `G` que Meeko inserta al abrir un macrociclo para hacerlo flexible. No son atomos de la molecula y por eso el mapa no los lista. Se descartan POR TIPO -no hay elemento `G`-, que es una convencion documentada del formato y no una heuristica quimica. La regla es estrecha a proposito y esta probada en las dos direcciones: descarta los de pegado y sigue abortando ante cualquier otro serial no mapeado. Ninguno de los atomos PESADOS de esos tres ligandos estaba sin mapear.

EL INSTRUMENTO QUEDA CALIFICADO: 232/232 en lector, 232/232 en canonicalizacion, cero invariantes violadas, desplazamiento pesado 0.0 A, SMILES isomerico, carga y enlaces identicos en las 232, y num_h_added == 0 en el brazo canonico, que es el marcador de que la canonicalizacion llega entera y PoseBusters no anade nada. No hay exclusion correlacionada con aromaticidad ni con carga, que era la condicion que no se podia ceder.

LA PRUEBA TECNICA PASA lo que tenia que pasar y nada mas: los tres brazos corren, las invariantes se cumplen, la salida respeta el contrato, el determinismo es exacto -PoseBusters siembra ETKDG con 42 y cachea por InChI-, el NaN sintetico da NO_EVALUADO, y --tecnico emite NO_LEER_GATES_TECNICOS. Sus casos se eligieron por DIAGNOSTICO y no por muestreo, asi que no producen lectura.

DOS OBSERVACIONES TECNICAS QUEDAN REGISTRADAS PARA QUE NO PAREZCAN UN HALLAZGO cuando la corrida completa las reproduzca: el proxy dio NO_EVALUADO en 2 de 6 poses con el lector viejo, y FALLA en 2 de 10 con el reparado, donde el evaluador oficial dio PASA. No entran en ninguna conclusion.

QUE PUEDE Y QUE NO PUEDE SALIR DE AQUI. Puede salir que procedimiento tiene derecho a llamarse internal_energy dentro del producto. NO puede salir nada sobre exactitud de pose, union, ni el protocolo de docking, que no se toca. Y por R4, que no depende de los datos, ningun resultado puede promover el proxy a metrica oficial: una formula distinta no se convierte en la oficial por concordancia empirica.
- Hashes de dataset: 2 archivo(s) con SHA-256
- Hashes de assets: 5 archivo(s) con SHA-256

## Mantenimiento del sello

- 2026-08-23T19:51:54.433736+00:00: `backend/services/chemistry/pose_physical_validity.py` `f1228446→9f06756f` — EL ASSET CAMBIO DESPUES DEL SELLO, Y CAMBIO PORQUE ESTE MISMO EXPERIMENTO LO OBLIGO. La corrida uso backend/services/chemistry/pose_physical_validity.py con SHA-256 f12284460037bcdcf54a1bae3d824e3d3bb764ccb5adc3b82110f10530e836f4, que es el hash sellado y el que queda registrado como el que produjo el resultado. Despues del sello se aplico la consecuencia de producto que la regla preregistrada del gate exigia -el escalon degradado solo emite REVISION y nunca FALLA, porque el proxy rechaza el 14.2% de las poses que el control oficial aprueba- y se cerro el docstring del modulo con el resultado de las dos deudas.

LA MEDICION NO SE VE AFECTADA, y se puede comprobar: el runner no llama a evaluar_pose_fisica, que es la unica funcion que cambio en el comportamiento. Usa leer_pose_pdbqt, proxy_tension_rdkit y clasificar_resultado_pb, que son identicas entre los dos hashes. El cambio es de EMISION DE VEREDICTO en produccion, no de calculo.

ERROR DE PROCEDIMIENTO RECONOCIDO: no se debe sellar como asset la ruta VIVA de un modulo de produccion. Un modulo de produccion cambia por definicion, y aqui cambio justamente porque el experimento cumplio su proposito. Lo correcto habria sido sellar una copia congelada dentro del artefacto y dejar la ruta viva fuera del sello. Queda anotado para los proximos. (commit 9824790076f32857bfd844e109f0988f8bdc2f4a)
- 2026-08-23T19:52:18.631791+00:00: `backend/tests/test_pose_physical_validity.py` `8c20984d→36011ab8` — MISMO CASO Y MISMA CAUSA que el modulo de produccion: el asset cambio DESPUES del sello porque el propio experimento lo obligo. Se anadio `test_el_fallback_nunca_emite_falla`, la prueba de regresion de la consecuencia de producto que disparo la regla preregistrada del gate: el escalon degradado solo emite REVISION, nunca FALLA. El hash con el que corrio el experimento queda registrado abajo.

NO AFECTA A LA MEDICION: es una prueba de contrato del modulo de produccion; el runner no la importa ni la ejecuta. La prueba anadida solo verifica un comportamiento que se implemento DESPUES de leer el resultado, y por eso no podia existir antes del sello.

Misma leccion que el otro asset: no sellar como asset la ruta viva de codigo que el propio experimento va a obligar a cambiar. (commit 9824790076f32857bfd844e109f0988f8bdc2f4a)
- 2026-09-24T04:04:33.905320+00:00: `backend/services/chemistry/pose_physical_validity.py` `9f06756f→33d4c662` — Activo cambiado despues del sello: backend/services/chemistry/pose_physical_validity.py es un modulo o documento vivo que se sello como asset (regla 4 de las reglas de metodo: no sellar un modulo de produccion vivo). El resultado sellado se produjo con la version anterior, cuyo hash queda en previous_hash; la version actual es la del commit c0a247f. Se registra el 2026-09-23, antes de la auditoria externa, para que validar_sellos.py distinga este cambio declarado de una corrupcion. No cambia ninguna cifra ni decision del experimento. (commit c0a247f)

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
