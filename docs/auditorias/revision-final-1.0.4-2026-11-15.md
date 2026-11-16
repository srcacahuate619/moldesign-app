# Revisión final de la investigación de MolDesign 1.0.4.0

15 de noviembre de 2026. Revisión solicitada por el propietario de las recomendaciones de GPT 6.1 Sol, sobre el árbol `4b8eaf3e229b89aa4032c8e6bbd6711cadf0b5aa`. Se revisaron y guardaron individualmente **los 23 problemas: hERG, D-01 a D-10 y B-1 a B-12**. Este documento distingue la revisión de la evidencia, la recomendación de producto y la implementación. Los experimentos originales y sus sellos se conservan; las rectificaciones se registran aquí y en el [resumen de entrega](cierre-investigacion-1.0.4-2026-11-15.md). Es una segunda revisión por un asistente LLM con cotejo de fuentes y sondas reproducibles; no constituye revisión independiente por un laboratorio o expertos humanos.

## 1. hERG — conservar la política provisional; corregir su justificación y prioridades

**Dictamen: aceptado con correcciones.** Mantener `Vina < −7,0 kcal/mol` para la alerta exploratoria y `−7,5` como parámetro de normalización de la diana principal. Son funciones distintas. La coincidencia de −7,0 con el inicio de la penalización ordinaria del normalizador es una coincidencia de implementación, sin valor de validación farmacológica. No hay un corte de bloqueo hERG validado para esta configuración del producto.

La elección provisional conserva una política más sensible a cruzar el corte y admite más alertas; no demuestra mejor utilidad clínica, mejor clasificación poblacional ni que −7,0 sea óptimo. Los 7/10 frente a 3/10 describen las preparaciones originales de la semilla 42. Las sustituciones dirigidas de microestados dan 5/10 frente a 3/10, y tampoco constituyen validación independiente. Los p de McNemar se pueden reproducir, pero **un p no significativo no establece equivalencia**. En las comparaciones separadas por clase, el anidamiento obliga a que toda discordancia vaya en un solo sentido; esos p no eligen un punto operativo. Una decisión de utilidad requiere prevalencia, costes y validación externa definidos.

La interpretación de `cav_vina` en la contrarréplica es correcta: la proximidad numérica entre canales distintos no vuelve transferible el corte. La fuente de Yao mide inhibición funcional a 25 ± 0,5 °C; el desenlace TdP del conjunto de Rouen y un score de docking no son intercambiables. [Yao, métodos y tabla 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC2442905/) · [Creanza, modelos y tabla 3](https://pmc.ncbi.nlm.nih.gov/articles/PMC9282647/)

**Corrección de prioridad.** La carrera de inicialización de Dimorphite-DL y la elección del protón de amoxicilina deben figurar como defectos de preparación pendientes, con seguimiento propio. Las nuevas advertencias de D-04 no reparan ninguno. El código 2.0.2 publica `_instance` antes de completar las reglas, compatible con la sonda de arranque archivada. Antes de usar nuevas corridas para decidir un corte, hay que resolver esa carrera y comprobar que la identidad química coincide entre arranque en frío, ejecución en serie y ejecución en paralelo. Amoxicilina requiere adjudicar el centro de carga; el recuento global de cargas no basta. [Código de la dependencia](https://raw.githubusercontent.com/durrantlab/dimorphite_dl/v2.0.2/dimorphite_dl/protonate/data.py) · [Sondas y resultados](herg-umbral-2026-11-15/contrarreplica-resultados.json)

El contraste de microestados regenera los conformadores. Por tanto mide el cambio conjunto de especie y geometría inicial bajo el procedimiento, sin aislar un efecto físico de la protonación ni demostrar qué especie se une experimentalmente.

**Presentación.** Aprobaría distinguir ambos parámetros y declarar que la ausencia de alerta no descarta bloqueo. El caso −7,004 exige mostrar la diferencia sin alterar la desigualdad estricta. Tres decimales bastan para ese registro; una regla general debe aumentar precisión hasta distinguir valor y corte, o decir explícitamente que el redondeo los hace coincidir. No presentar los 3/10 omitidos como tasa aplicable a futuros compuestos. [Contrarréplica revisada](contrarreplica-herg-umbral-2026-11-15.md)

Estado: revisión documental y de código cerrada. Implementación y aceptación del candidato pendientes; esta revisión no modifica el motor.

## 2. D-04 — acotar los avisos a la evidencia y corregir el estado de carga

**Dictamen: aceptado con reducción de alcance.** La opción A puede proponer revisión de especie. El GO del protocolo significa que una rama cumplió el criterio interno para proponer un aviso. No valida un predictor de pKa, una tasa de error química ni toda la clase que aceptaba el SMARTS original.

Los 14 padres A de α-aminoéster son ésteres metílicos/etílicos con **amina primaria**, de siete aminoácidos. La segunda fuente reevalúa dos ejemplos; no aporta otra serie diversa de 14. El SMARTS original acepta aminas secundarias y terciarias, otros ésteres y carbonos α más sustituidos. Para presentar una propuesta implementable respaldada por lo medido, acoto la amina a `NH3+`, el carbono α a CH/CH2 y el éster a metilo/etilo. Quedan pendientes las extensiones, incluido clopidogrel: su dato experimental comunicado por el patrocinador es pertinente para revisar ese compuesto, pero no constituye una validación de toda la familia terciaria. [Doğan, métodos y tabla 2](https://arastirmax.com/en/system/files/dergiler/5672/makaleler/21/3/arastirmax-bazi-amino-asitlerin-etil-metil-esterlerinin-protonasyon-sabitlerinin-su-ortaminda-potansiyometrik-yontemle-tayini.pdf) · [Extracción original y condiciones](investigacion-d04-2026-11-15/medidas.json)

En N-alquilmorfolina, los tres padres A son N-metilo, N-etilo y MOPS. El patrón original admitía sustituciones en los carbonos del anillo y ramificación en el carbono unido al N sin medidas A para esas extensiones. Acoto el anillo a cuatro CH2, sin fusión, y el carbono exocíclico unido al N a CH3/CH2. Esto conserva los tres ejemplos A. Los sustituyentes más remotos siguen delimitando un aviso precautorio; no se adjudica un pKa a una molécula nueva. [Sari y Covington, mediciones acuosas](https://pubs.acs.org/doi/10.1021/je0500983)

Patrones finales propuestos, sobre el SMILES de la especie acoplada y con la misma exclusión molecular de carboxilatos del protocolo:

α-aminoéster: `[NX4+;H3]-[CX4;H1,H2]-[CX3](=[OX1])-[OX2;H0]-[$([CH3]),$([CH2]-[CH3])]`

N-alquilmorfolina: `[NX4+;H1;R1]1(-[CX4;!R;H2,H3])[CH2;R1][CH2;R1][OX2;H0;R1][CH2;R1][CH2;R1]1`

Esta acotación es **posterior** al análisis original. No se reescribe su protocolo ni se atribuyen a los patrones nuevos sus métricas antiguas. La sonda nueva conserva los 17 padres A pertinentes, marca 0/17 especies correctas versionadas, relee los 107 controles y supera 10 fronteras adicionales. Retira dos coincidencias del panel original: 4-nitrofenil glicinato y clopidogrel. Las cifras 1/1 y 20/28 de ChEMBL describen los patrones originales; no se transfieren a esta acotación sin recalcular. [Sonda](revision-final-1.0.4/comprobar_d04.py) · [Salida por compuesto](revision-final-1.0.4/d04-alcance.json)

**Corrección del texto químico.** En MOPS y MES, la forma con N protonado es zwitteriónica y al desprotonar ese N queda un anión. El texto «fracción neutra» confunde la carga del centro con la de la molécula. Usar:

> Especie en revisión: se acopló este nitrógeno protonado. En compuestos publicados con un entorno semejante, a pH 7,4 puede coexistir una proporción apreciable con ese nitrógeno sin protonar. El pKa por clase no resuelve la distribución de esta molécula.

Nombrar el entorno específico y mantener la referencia experimental en el detalle. Un porcentaje obtenido con Henderson–Hasselbalch corresponde al modelo ideal y a las condiciones del pKa usado; no describe por sí solo el sitio de unión. El umbral de aproximadamente 3 % a ±1,5 unidades es una política de revisión, sin calibración biológica.

Mantengo inconcluyentes las otras seis ramas. La falta de tres referencias A no demuestra que su especie sea correcta. La guarda global de carboxilatos deja fuera incluso motivos distantes de un carboxilato: es una abstención de alcance intencional que debe documentarse. También corrijo «modificación de presentación»: puede cambiar el estado de Preparación y el dossier, aunque no cambie scores. Requiere pruebas de estado y regresión de las salidas afectadas al implementarse.

Estado: revisión y nueva sonda cerradas. El manifiesto original verificó sus 14 artefactos y tres referencias antes de esta revisión. Las medidas y el informe original se conservan íntegros; esta sección sustituye su propuesta de alcance para la entrega final.

## 3. D-01 — mantener la métrica local y ajustar una afirmación del rótulo

**Dictamen: aceptado con una corrección adicional.** El árbol `4b8eaf3e` ya identifica Chai-1 como declaración de `_struct.title`, comprueba la coincidencia local con Cα y evita inferir versión o convención verificada. La advertencia inicial de la réplica sobre un valor local alterado ya tiene corrección y prueba. Repetí los diez controles seleccionados de firma: pasan. El exportador 0.6.1 efectivamente usa el centro del token, Cα en proteínas. [Exportador versionado](https://raw.githubusercontent.com/chaidiscovery/chai-lab/v0.6.1/chai_lab/data/io/cif_utils.py)

Encontré un límite residual que la recomendación anterior no identificaba. El código supone que, si los factores B varían dentro del residuo, el Cα no puede coincidir con la media. Eso no se sigue: valores por encima y debajo pueden compensarse. En una sonda sintética sobre el recorte real, conservé el Cα y el valor local, y cambié dos átomos a valor local ±1. En los **90 residuos** el factor B varía, pero su media coincide con el Cα (diferencia máxima 2,85 × 10⁻¹⁴); el dossier todavía dice «no es la media». Es un contraejemplo del rótulo, sin nueva predicción ni cambio de estado del sitio. [Sonda](revision-final-1.0.4/comprobar_d01.py) · [Salida](revision-final-1.0.4/d01-media.json)

Texto que aprobaría: **«pLDDT leído de _ma_qa_metric_local; los valores leídos coinciden con el factor B de los Cα correspondientes. El archivo declara Chai-1 y no acredita su versión».** Eliminar la negación de la media de la afirmación sobre este archivo. La diferencia entre Cα y media en las salidas reales de 0.6.1 puede permanecer en la explicación del experimento. Conservar las dos traducciones y comprobar el dossier al implementar.

El contraste NET/CDK2 no permite escoger una métrica por rendimiento predictivo: hay dos proteínas, muestras correlacionadas, estados experimentales distintos y referencias de CDK2 anteriores al entrenamiento. Coincidir en el aviso en esos sitios no demuestra equivalencia. Mantener la lectura local es continuidad y procedencia, no calibración del corte 70.

Estado: revisión cerrada; corrección residual del texto identificada y reproducida, pendiente de implementación.

## 4. D-02 — pausa ratificada

**Dictamen: mantener la pausa solicitada por el propietario.** D-01 no la cierra indirectamente. El 70 sigue siendo un umbral interpretativo del pLDDT trasladado a un aviso de revisión; no se ha establecido su sensibilidad para fallos de docking ni su equivalencia entre modelos. La falta de aviso no certifica un sitio. No se inicia una calibración nueva en esta revisión.

Estado: pregunta pausada por decisión explícita; alcance de la entrega revisado.

## 5. D-03 — conservar la receta; la evidencia no establece que el agua sea inútil

**Dictamen: aceptado, con precisión de alcance.** Las métricas selladas contienen 8/21 éxitos sin aguas, 11/21 con selectivas y 13/21 con todas las locales; las discordancias primarias son 6 a favor y 3 en contra, p exacta 0,5078125. Mantener la receta del catálogo y su declaración es defendible. No concluir equivalencia ni ausencia de beneficio a partir de ese p.

Los 315 acoplamientos son repeticiones de 21 complejos de sólo dos familias. Ni las semillas ni los complejos emparentados ofrecen 315 unidades independientes para generalizar a receptores. Las aguas se eligieron usando el ligando cristalino, de modo que el experimento tiene información que no se tiene para un ligando nuevo. Un brazo de oxígenos OA rígidos, sin H orientados, tampoco prueba el tratamiento termodinámico del agua. El resultado de todas las aguas permanece descriptivo; no se convierte retrospectivamente en la comparación principal por tener más éxitos.

La documentación oficial confirma que el protocolo de aguas desplazables citado está calibrado con la función AutoDock4 y desaconseja trasladarlo a las funciones Vina/Vinardo. Distinguir el ejecutable de Vina de la función de puntuación que emplea evita prometer que MolDesign ya ofrece ese método. [Documentación oficial](https://autodock-vina.readthedocs.io/en/stable/docking_hydrated.html)

Los tamaños propuestos de 127/515 son escenarios bajo una discordancia supuesta y unidades independientes. Para una confirmación hay que incorporar la agrupación por diana/serie y separar el conjunto que diseña el selector del que lo evalúa. No son garantías de potencia para el catálogo. La conservación de agua de los caminos propios B/C sigue siendo una decisión registrada del usuario.

Estado: revisión cerrada; mantener la implementación actual. [Ficha y protocolo originales](investigacion-1.0.4/D03.md)

## 6. D-05 — mantener abstención y limitar el NO_GO a la configuración probada

**Dictamen: aceptado con matiz.** La detección 3/5 y los dos fallos Zn–sulfonamida impiden incorporar directamente la configuración ensayada como comprobación suficiente de coordinación. El NO_GO corresponde a ProLIF 2.1.0 con esos grafos, microestados y parámetros, no a la imposibilidad de construir una huella válida con la biblioteca. El SMARTS instalado excluye ciertos N neutros junto a heteroátomos con doble enlace; cambiar la especie química puede cambiar el reconocimiento. Exigir adjudicación del donante antes de atribuir una omisión únicamente al detector.

Los 0/9 falsos positivos incluyen controles trasladados 30 Å: comprueban el corte geométrico, pero no estiman especificidad ante heteroátomos cercanos que no coordinan. N/O/S a ≤2,8 Å es un contacto candidato, no una prueba universal de coordinación para Zn, Mg, Ca y K. Conservar metal, carga, ligando, distancias y, cuando proceda, ángulos permite revisar el caso; no basta añadir `MetalAcceptor` a la lista de interacciones.

Ratifico la lectura de AutoDock4Zn: en su validación cruzada, 45 % frente a 45 % de RMSD global <2 Å, y 75 % frente a 37 % de RMSD de coordinación <1 Å comparado con Vina. El beneficio de esa geometría no valida M5 ni un ranking de afinidad del catálogo. [Santos-Martins et al., tabla 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC4144784/#T2)

Estado: revisión cerrada; mantener revisión/abstención y el tratamiento actual. La extensión de M5 y una comprobación de coordinación requieren evidencia específica. [Ficha y datos](investigacion-1.0.4/D05.md)

## 7. D-06 — conservar exhaustividad 8; separar pose, orden y coste

**Dictamen: aceptado.** Recalculé desde las 243 filas los cuatro coeficientes de 8HFI y las medianas de los 57 padres. Δρ(32−8) = 0,0133208; las medianas son 35,875 s y 72,688 s. Comprobé además que ningún padre cambia el SMILES de su microestado entre brazos, un control pertinente tras el hallazgo de hERG. Esto no demuestra corrección química de los estados, pero descarta ese cambio registrado como explicación de la diferencia entre brazos. [Recuento independiente](revision-final-1.0.4/cifras.json)

El IC sellado [−0,0624; 0,1047] no permite declarar mejora ni equivalencia bajo el margen fijado. En 8T69 sucede lo mismo para la decisión general. Pasar de 3/5 a 5/5 redockings describe un único ligando de referencia; no valida una mejora poblacional por cinco réplicas independientes de dianas. La búsqueda adicional puede ayudar a una pose sin mejorar el orden de Ki.

Mantener 8 conserva coste y las condiciones del sello de 8T69. No implica que 8 sea suficiente para cualquier ligando o caja. La razón de tiempos 2,03 se midió bajo carga concurrente y no predice por sí sola la latencia de otro equipo. Una política adaptativa necesitaría datos por dificultad de búsqueda y su propio registro.

Estado: revisión cerrada; conservar la recomendación. [Ficha](investigacion-1.0.4/D06.md)

## 8. D-07 — conservar el campo histórico y actualizar el inventario al código actual

**Dictamen: aceptado con actualización.** El inventario original declara su base `77aeb737`; no describe íntegramente `4b8eaf3e`. En el código actual, tanto `_orden_exportado` como `_compute_ef_metrics` en `batch.py` usan `affinity_kcal`, más negativo primero. EF/AUC niega la afinidad y ya no elige métrica según homogeneidad de pesos. La columna `TotalScore` sigue exportándose. La entrega anterior sólo destacaba el cambio de EF/AUC; también está cambiado el orden exportado.

Mantener `total_score` para lectura y verificación históricas es razonable. No reinterpretar un índice antiguo como score Vina ni recalcular documentos firmados. SUP-02 no demostró una mejora de la fórmula compuesta; tampoco prueba que jamás pueda mejorar otra población. Cambiar una fórmula necesita una versión propia y evidencia adicional.

La presentación sigue incompleta mientras un CSV/XLSX use `TotalScore` sin explicar que es un índice heredado. Recomiendo declarar esa semántica y `ranking_policy`/`score_basis` en cada exportación o metadato acompañante, preservando compatibilidad cuando existan consumidores del encabezado. Los filtros y resúmenes históricos que aún usan el campo deben conservar la misma identificación. La ausencia de una ruta activa de MolChat hacia el índice no elimina las rutas de Historial, SAR y API que documenta la ficha.

Estado: revisión cerrada. Inventario de entrega actualizado; no se propone cambiar la fórmula ni retirar campos. [Ficha histórica](investigacion-1.0.4/D07.md) · [Código actual](../../backend/api/routers/batch.py)

## 9. D-08 — conservar SMARTS; precisar qué componente queda en cero

**Dictamen: aceptado con corrección de semántica.** Reconté 6/12 → 12/12 reconocimientos de la familia esperada, 12/12 negativos sin las tres familias ensayadas y 11/12 sin ningún grupo UMS. El acetato pertenece a otra familia. Son controles estructurales dirigidos, sin medida de afinidad ni de coordinación.

La nota propuesta debe referirse a **`ums_warhead`**, porque el UMS combinado también contiene donantes y MolChamb: puede ser distinto de cero aunque no se reconozca un grupo. Además, `detect_warheads` devuelve todas las claves falsas ante un SMILES ilegible. Un cero sólo significa «sin coincidencia» si consta una evaluación válida; la ausencia o el fallo de evaluación requieren su estado propio.

Texto que aprobaría: «Cobertura del componente de grupos de unión a Zn: las formas aniónicas explícitas de sulfonamida, hidroxamato y tiol ensayadas pueden no reconocerse en esta versión. En una entrada válida, `ums_warhead = 0` significa que no coincidió ningún patrón cubierto; no descarta coordinación». Mantener separadas las señales calculada, ausente e histórica y nombrar el SMILES realmente evaluado, que en M5 es el de entrada.

Confirmo que M4 no incorpora `ums_finite` a la fórmula de orden. En M5, una ampliación sí puede cambiar el resultado y requiere versión, controles de solapamiento y evaluación del perfil. Un GO del detector por sí solo no autoriza ese cambio de score.

Estado: revisión cerrada; mantener los patrones y precisar la nota. [Ficha](investigacion-1.0.4/D08.md) · [Recuento](revision-final-1.0.4/cifras.json)

## 10. D-09 — separar sitio pendiente de sitio incompatible conocido

**Dictamen: corregir prioridad y tratamiento.** Reconté las 44 filas: 38 acuerdos, incluidos 25 A/A (dos son controles actuales), cuatro C/C, cinco B/B y cuatro U/U; hay seis desacuerdos. Ratifico que son sesiones del mismo modelo y evidencia compartida. Ese acuerdo no equivale a revisión independiente por expertos ni autoriza promocionar automáticamente las 23 candidatas. La muestra humana de 12 casos cubre sólo esas 12 adjudicaciones; no validaría por arrastre las otras 32.

La propuesta «conservar la afinidad exploratoria» requiere precisar **qué entidad se acopló**. Para un sitio no revisado puede conservarse el score con procedencia y alcance. Para una incompatibilidad ya demostrada, conservarlo bajo la identidad farmacológica equivocada seguiría siendo engañoso aunque se añada una advertencia.

| Fila | Dictamen final para la presentación |
|---|---|
| **OPRK1 / 7UL2** | Prioridad más alta. El depósito es NTSR1 con un segmento κ insertado. Repetí la geometría: caja a 0,000535 Å del centro de Q6Q, contacto NTSR1 a 3,104 Å y segmento κ a 22,891 Å. No presentarlo como resultado de unión a κ. Recomiendo deshabilitar esa asociación como antidiana OPRK1 hasta sustituirla y validar su preparación/sitio. Conservar las corridas históricas identificando la discordancia. 6B73/4DJH son candidatas a estudiar, no reemplazos ya validados. |
| **SCN5A / 6LQA** | La estructura es NaV1.5 con quinidina; conservar un estudio del poro bajo esa descripción sería posible. No adjudicarlo al ensayo «site 2» de batracotoxina sin evidencia de correspondencia. |
| **OPRM1 / 8Y72** | La caja del modulador alostérico positivo BMS-986122 no es una medición del bolsillo ortostérico. Un score allí no determina agonismo ni depresión respiratoria. Reasignar explícitamente el mecanismo o dejar esa inferencia sin evaluar. |
| **GRIN1 / 9GJ1** | Resolver la diferencia entre sitio de glicina de GluN1 y el ensayo competitivo referido al sitio de glutamato. No tratar como intercambiables los dos sitios del receptor NMDA. |

[Depósito 7UL2](https://www.rcsb.org/structure/7UL2) · [Geometría repetida](revision-final-1.0.4/d09-geometria.json) · [6LQA](https://www.rcsb.org/structure/6LQA) · [8Y72](https://www.rcsb.org/structure/8Y72) · [9GJ1](https://www.rcsb.org/structure/9GJ1)

El aviso «sitio no adjudicado» ya se propaga a las alertas del árbol actual. Actualizar así el inventario histórico de opciones. Su presencia no elimina la incompatibilidad conocida. Aun con un sitio adjudicado, una pose o afinidad no identifica el efecto funcional de un ligando nuevo: agonista, antagonista y modulador requieren evidencia adicional. Tampoco convierte el margen entre receptores en una medida experimental de selectividad.

Las otras candidatas permanecen como triaje documental con sus referencias. Para decidir cada una exigir identidad de proteína/constructo, sitio, ligando, mecanismo y tratamiento del receptor; el redocking sólo comprueba una parte. Las 109 cajas sin `site_ligand` del catálogo conservan su condición geométrica de Demostración.

Estado: revisión de las recomendaciones cerrada; las adjudicaciones pendientes no se dan por resueltas. Las cuatro incompatibilidades requieren tratamiento explícito antes de presentar el panel como farmacológicamente adjudicado. [Ficha original](investigacion-1.0.4/D09.md)

## 11. D-10 — mantener experimental; corregir qué verifica la guardia

**Dictamen: aceptado con un pendiente de contrato explícito.** Se respeta la decisión de no ejecutar la validación de ESMFold en la estación. Los enlaces marcados rotables por Meeko sólo muestran libertad configurada; no prueban que Vina explore todas esas torsiones, que destruya el plegado ni que ese plegado mejore la pose. Una fecha posterior al corte PDB tampoco garantiza independencia de homólogos o secuencias relacionadas.

El diseño de cuatro brazos propuesto es útil. El brazo con geometría unida es un control privilegiado que conoce la respuesta estructural; no debe presentarse como rendimiento alcanzable en uso prospectivo. Cinco semillas por complejo miden repetibilidad, sin multiplicar el número de complejos independientes. Los 49–122 h son una proyección aritmética de tiempos supuestos, no un presupuesto medido. El pLDDT puede evaluarse como discriminador de éxito, con intervalos y agrupación por proteína; su AUC no calibraría probabilidades.

**Pendiente de esta versión:** `test_peptido_abstencion_negativa.py::test_la_interfaz_dice_lo_que_si_hace` exige el texto de conversión no soportada en `DockingEnginePanel`, que no se monta. El menú activo usa `op_esm_desc` y describe plegado seguido de Vina con abstención. Conservar un componente muerto porque una prueba lo lee no prueba el contrato visible. Recomiendo alinear ADR, guardia y texto del menú activo con la transferencia implementada y su condición experimental; después podrá retirarse el componente. Esto es comprobación de la promesa visible, sin ejecutar el estudio de poses ni cambiar la decisión de pausa.

Estado: revisión cerrada; validación científica aplazada según instrucción, guardia de interfaz pendiente de alinear. [Ficha](investigacion-1.0.4/D10.md) · [Prueba actual](../../backend/tests/test_peptido_abstencion_negativa.py) · [ADR 76](../76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md)

## 12. B-1 — convención del selector de pose

**Dictamen: aceptado y ya documentado.** `sqrt(mean(d**2))` sobre una matriz N×3 divide la suma por 3N; el RMSD 3D por átomo divide por N. Por tanto, el umbral interno 2 equivale a 2√3 = 3,4641 Å bajo la misma correspondencia atómica. El docstring actual lo expresa. Conservar la convención del modelo congelado; no presentarla como el criterio habitual de RMSD ≤2 Å. No se ha repetido el entrenamiento ni se deduce de esta identidad la calidad del selector. [Implementación](../../rescoring/pose_selector/selector.py)

Estado: revisión cerrada; sin cambio recomendado de fórmula.

## 13. B-2 — tensión del conformador del ensemble

**Dictamen: aceptado.** `ensemble.py` ordena las poses por afinidad Vina y desempata por conformador y rango original; la energía MMFF se registra aparte. Una suma de energía del conformador de entrada y score de docking no queda justificada por el informe. Además, no identifica necesariamente la tensión de la geometría acoplada respecto a un mínimo comparable. Mantener orden y trazabilidad; cualquier corrección energética necesita definición física, protocolo y contraste propios. [Orden actual](../../backend/services/docking/ensemble.py)

Estado: revisión cerrada; conservar comportamiento.

## 14. B-3 — boro y selenio

**Dictamen: aceptado.** Mantener la abstención de la etapa que no puede parametrizar o preparar. `MMFF_NO_PARAMETRIZA` devuelve una ausencia de evaluación; no debe convertirse en cero de energía ni en un aprobado de validez. El fallo de Meeko y el de MMFF son etapas distintas, por lo que conservar sus motivos separados es correcto. Esta revisión coteja las rutas y la evidencia archivada, sin nuevas corridas de bortezomib/ebselen. [Validador](../../backend/services/chemistry/pose_physical_validity.py)

Estado: revisión cerrada; cobertura nueva aplazada.

## 15. B-4 — caps del receptor

**Dictamen: aceptado.** La llamada del preparador mantiene `apply_caps=False`, coherente con el fallo de fusión de cadenas registrado. No inferir que dejar extremos sin cap produce un sistema químicamente resuelto: deben persistir los límites de terminales y las decisiones del modo de preparación. Cualquier reactivación requiere comprobar identidad de cadenas y conservación del sitio además de que el archivo se lea. [Preparador](../../backend/services/docking/preparer.py)

Estado: revisión cerrada; conservar desactivación.

## 16. B-5 — constantes térmicas

**Dictamen: aceptado con límite interpretativo.** Las pruebas actuales fijan RT a aproximadamente 310,15 K y RT·ln(10) alrededor de 298 K para sus respectivos usos. Pasaron al repetirlas. La diferencia entre 1,3633 y 1,364 es pequeña y no justifica recalcular registros por sí sola. Aclarar la temperatura no convierte un score Vina en ΔG experimental ni una transformación exponencial en Ki o selectividad medidos: mantener la condición aparente/exploratoria en la salida. [Pruebas](../../backend/tests/test_constantes_termicas.py)

Estado: revisión cerrada; conservar valores y explicación de sus límites.

## 17. B-6 — componentes sin montar

**Dictamen: aceptar las cuatro retiradas; corregir el cierre del componente restante.** Conservar temporalmente `DockingEnginePanel` evita romper la prueba actual, pero no cierra la deuda: esa prueba vigila una superficie que no ve el usuario. La acción final recomendada es trasladar el contrato al menú activo, con controles negativos y ambos idiomas, y entonces retirar el componente. No reutilizarlo para ofrecer motores que el producto no ejecuta. La revisión de D-10 describe la discrepancia concreta.

Estado: revisión cerrada; guardia activa y retirada posterior pendientes. [Registro de decisiones](auditoria-cientifica-1.0.4-2026-11-13.md#registro-de-decisiones)

## 18. B-7 — proveedor por defecto y privacidad

**Dictamen: corregir el texto en ambos idiomas.** La página local sigue afirmando Qwen2.5 1.5B por omisión. La configuración normal de MolChat declara `provider=None`, `active_id` no elige ninguno y el modo alojado recibe el proveedor de cada llamada. La existencia de proveedores locales no implica que uno venga activo.

Texto propuesto: «Sin configuración previa, MolChat no tiene un proveedor de IA activo. La persona elige y configura el proveedor; si es remoto, se aplican la autorización de destino y los controles del producto». Evitar «siempre comienza sin proveedor»: una cuenta o un operador pueden haber configurado uno. La revisión del código no acredita que la página pública desplegada ya haya cambiado. [Página local](../../site/privacy/index.html#es-ai) · [Configuración](../../tools/molchat/src/molchat_agent/config.py) · [Registro](../../tools/molchat/src/molchat_agent/providers/registry.py)

Estado: revisión cerrada; corrección documental del producto pendiente.

## 19. B-8 — integridad histórica y verificación fuera del repositorio

**Dictamen: conservar originales, pero separar las dos preguntas.** Mantener bytes y `log_sha256` de las corridas antiguas conserva su integridad. Eso no obliga a distribuir sin revisión rutas personales: si se necesita una copia redactada, debe ser un derivado identificado, con huellas y explicación propias, sin hacerse pasar por el original ni alterar certificados anteriores.

El segundo pendiente no se resuelve conservando bytes. La receta actual aún remite a `python scripts/verify_dossier_package.py <archivo>.zip`; el paquete no aporta por esa mención el script ni sus dependencias. Recomiendo distribuir un verificador compatible y versionado junto a los paquetes nuevos, o indicar con exactitud dónde obtenerlo, su revisión y requisitos. Para prometer verificación autónoma sin red, la primera opción debe probarse fuera del checkout. Que el verificador del desarrollador funcione no prueba esa transferencia.

Estado: revisión cerrada; integridad histórica aceptada, disponibilidad externa del verificador pendiente. [Contrato](../56_DOSSIER_REPRODUCIBLE_CONTRACT.md) · [Receta de exportación](../../backend/services/dossier/package.py)

## 20. B-9 — ProDy

**Dictamen: congelar el runtime de esta entrega salvo que se prepare y acepte un candidato distinto.** El lock embebido mantiene ProDy 2.3.1 para Windows. El ayudante de RTMScore que lo importa queda excluido del runtime por `bundle_helper.py`; la ruta peptídica usa `--read_pdb` y evita la lectura por ProDy. Esto apoya retirarlo en una limpieza medida, pero no demuestra aún cómo queda un instalador regenerado sin el paquete.

No borrarlo a mano de `python-embed`. Si se decide retirar, modificar la fuente del lock, reconstruir, generar el SBOM correspondiente y pasar las rutas que consumen Meeko y el bundle. El SBOM debe describir lo que se entrega incluso cuando una dependencia no se usa. Esta revisión no convierte el inventario de imports en una prueba de arranque de ese candidato.

Estado: revisión cerrada; conservar el entorno actual para la recomendación de esta entrega. [Exclusión del ayudante](../../scripts/bundle_helper.py) · [Lock](../../backend/requirements-embed.lock.txt)

## 21. B-10 — worktrees y ramas

**Dictamen: conservarlos durante el cierre.** El inventario vivo ya difiere de la lista histórica de la guía; `git worktree list` registra, entre otros, receptores, MolChat, PDF, publicación y vídeo. Una rama guarda commits, pero no preserva archivos ignorados ni modificaciones sin commit. La recomendación de decidir por worktree sigue siendo correcta.

Antes de retirar uno se necesita inventario de cambios y datos ignorados, destino de archivo verificable y decisión del propietario. No se deduce permiso de eliminación de esta revisión. Tampoco se condiciona la investigación científica a limpiar worktrees ajenos al candidato.

Estado: revisión cerrada; sin retirada ni modificación de worktrees.

## 22. B-11 — falta evidencia del candidato y el comprobador estático es parcial

**Dictamen: corregir el alcance de la comprobación anterior.** La configuración vigente sí contiene 16 comandos y declara la versión Store 1.0.4.0. `check_release_pipeline.py` pasa, pero verifica la presencia y orden de sólo **9 de esos 16 comandos**. Hice 16 controles negativos en memoria, retirando un comando por vez: sigue pasando sin `check:runtime-arbol`, `check:openbabel-fuente`, `check:molcy-motor`, `check:openbabel`, **`check:evaluation-runtime`**, `check:exported-api-url` o `check:no-remote-assets`. La sonda no modifica Tauri ni ejecuta el build. [Sonda](revision-final-1.0.4/comprobar_b11.py) · [Resultado de las 16 omisiones](revision-final-1.0.4/b11-cobertura-guardia.json)

Por tanto, retirar la frase que pueda leerse como «las 16 puertas están protegidas por ese comprobador». Recomiendo ampliar su lista y controles negativos para las puertas obligatorias, incluida la 12. La configuración correcta de hoy y una guardia contra regresiones son evidencias diferentes. Tampoco una pasada estática demuestra que los 16 comandos hayan ejecutado con éxito.

En las tres ubicaciones consultadas no hay candidato 1.0.4.0. Esto sólo describe esas ubicaciones; no es una búsqueda de todos los discos ni evidencia del portal. El envío requiere identificar el candidato por hash/revisión, ejecutar sus puertas, humo de escritorio, aceptación en VM y comprobaciones acordadas. WACK local figura en Microsoft como deprecado y opcional; la certificación oficial ocurre al enviar a Partner Center. Si el proyecto conserva WACK como condición interna, se cumple o se modifica esa condición explícitamente; no se presenta como certificación oficial. [Microsoft, validación local](https://learn.microsoft.com/en-us/windows/msix/package/packaging-uwp-apps#validate-your-app-package-locally)

**No doy conformidad de distribución con esta revisión documental.** Mi recomendación es resolver los defectos de identidad/preparación y las promesas de presentación señalados, o limitar explícitamente la funcionalidad afectada, antes de aceptar el candidato. La aprobación científica de un informe no sustituye la ejecución del cierre de versión.

Estado: revisión cerrada; build, aceptación y envío pendientes. No se construyó ni publicó un instalador.

## 23. B-12 — verificaciones visibles

**Dictamen: aceptado, con criterio de cierre concreto.** Estas comprobaciones siguen abiertas; las pruebas de código no acreditan lo que verá una instalación nueva.

| Verificación | Evidencia mínima para cerrarla |
|---|---|
| Molcy | Fotograma del vídeo generado con el candidato, con etiqueta Demostración en ambos idiomas y con título personalizado. |
| Comparador | Recorrido completo en escritorio con dos corridas reales, identidad de receptor/ligando, cambio de pose y correspondencia entre valores y vista. |
| MolChat | Instalación limpia, configuración/ausencia de proveedor, consentimiento del destino cuando proceda, persistencia y rollback del candidato. |
| Título del depósito | Correspondencia del título completo entre catálogo, interfaz y salida prevista; registrar cualquier abreviación intencional. |

Cada evidencia debe identificar paquete, versión, escenario y resultado. Las verificaciones en desarrollo conservan ese alcance y no se elevan a aceptación del MSIX.

Estado: revisión cerrada; ejecución de las verificaciones pendiente. [Registro de versión](../versions/1.0.4_cambios.md)

## Alcance de la entrega y comprobaciones

La investigación queda revisada para su presentación con estos dictámenes. «Revisión cerrada» significa que se evaluó la recomendación y se resolvió qué conclusión sustenta la evidencia; no significa que se implementó el cambio ni que se respondió una pregunta que sigue inconcluyente o pausada. Esta revisión no ejecutó nuevos dockings, no validó ESMFold, no modificó código de producción y no construyó ni publicó un instalador.

Las correcciones de mayor prioridad son la identidad OPRK1/7UL2, los dos defectos de preparación identificados en hERG, el alcance y el texto de D-04, el rótulo residual de D-01 y las guardias de interfaz y release. Las propuestas de implementación figuran en cada problema. Mantener los criterios actuales de agua, metales y exhaustividad no implica que las alternativas sean equivalentes o inútiles.

| Comprobación ejecutada en esta revisión | Resultado y límite |
|---|---|
| Sellos de los experimentos citados | 14 experimentos, 4 034 archivos, sin diferencias ni ausencias. Es integridad, no repetición del docking. |
| Manifiesto original de la ampliación D-04 | 14 artefactos y tres referencias locales verificados. No se reescribieron el protocolo ni el informe. |
| Pruebas de firma de Chai/ModelCIF seleccionadas | 10 aprobadas, 33 no seleccionadas y una advertencia. La sonda nueva detecta un caso que no cubren. |
| Enriquecimiento, constantes térmicas y normalizador | 36 pruebas aprobadas. No se ejecutó la suite completa ni se mide con ellas la validez farmacológica de hERG. |
| Sondas y recuentos de esta revisión | D-01: contraejemplo de 90 residuos; D-04: alcance por compuesto; D-03/05/06/08/09 y hERG: recuentos; D-09: geometría repetida con el método archivado; B-11: 16 omisiones en memoria, siete no detectadas. |
| Integridad de la entrega documental | Los 23 apartados están presentes y los 17 enlaces nuevos a sus secciones coinciden con sus títulos. `git diff --check` no detecta defectos. El comprobador global de enlaces devuelve un falso positivo en el SMARTS de `investigacion-d04-2026-11-15/patrones.md`: interpreta `=[OX1]` dentro de un bloque de código como ruta. No se alteró ese artefacto para ocultar el fallo del comprobador. |

Una comprobación asíncrona adicional del contrato de hERG se interrumpió al quedar detenida al crear el bucle de `asyncio` de Windows; no se cuenta como aprobada. El contraste numérico del normalizador se ejecutó después sobre sus funciones puras. La literatura se cotejó con páginas primarias y tablas accesibles: no se obtuvo la captura visual del PDF de Doğan ni se volvió a recuperar el suplemento de ESMFold. Para esos límites se conserva la extracción/procedencia anterior y no se atribuye una verificación nueva que no ocurrió.

Para repetir las sondas desde la raíz con el entorno embebido existente:

```powershell
.\python-embed\python.exe -B -I docs/auditorias/revision-final-1.0.4/comprobar_d01.py
.\python-embed\python.exe -B -I docs/auditorias/revision-final-1.0.4/comprobar_d04.py
.\python-embed\python.exe -B -I docs/auditorias/revision-final-1.0.4/comprobar_cifras.py
.\python-embed\python.exe -B -I docs/auditorias/revision-final-1.0.4/comprobar_d09.py
.\python-embed\python.exe -B -I docs/auditorias/revision-final-1.0.4/comprobar_b11.py
.\python-embed\python.exe -B -I docs/auditorias/revision-final-1.0.4/manifiesto.py --check
```

Las sondas D-01 y B-11 reproducen defectos de la revisión indicada: sus aserciones dejarán de cumplirse cuando se corrijan. En ese caso se registra una nueva comprobación, sin regenerar silenciosamente este manifiesto. D-09 reutiliza explícitamente el cálculo geométrico archivado; no se presenta como implementación independiente. Los resultados nuevos sólo se escriben en `revision-final-1.0.4/`.

Pruebas ejecutadas desde `backend/`, con el entorno de pruebas `MOLDESIGN_TESTING=1` que configura `tests/conftest.py`:

```powershell
..\python-embed\python.exe -B -I -m pytest tests/test_prediccion_fuente_declarada.py -k 'TestLaFirmaDeChai or TestModelCIF' -q --disable-warnings
..\python-embed\python.exe -B -I -m pytest tests/test_fase3_enriquecimiento.py tests/test_constantes_termicas.py tests/test_normalizer.py -q --disable-warnings
```

El [manifiesto de esta revisión](revision-final-1.0.4/manifiesto.json) registra el informe, las sondas, sus resultados y las entradas usadas, con hashes separados de los originales. Las rectificaciones del acta de entrega, la guía y el registro de versión apuntan a este dictamen; no sustituyen retroactivamente la evidencia histórica.
