# Contrarréplica sobre el umbral de hERG

15 de noviembre de 2026. Respuesta a la [réplica](replica-herg-umbral-2026-11-15.md) del [informe original](herg-umbral-2026-11-15/README.md). Las 24 corridas originales y su registro previo se conservan como evidencia de la preparación que ejecutó el producto. La [revisión final](revision-final-1.0.4-2026-11-15.md#1-herg--conservar-la-política-provisional-corregir-su-justificación-y-prioridades) ratifica la política provisional y añade límites de inferencia y dos defectos de preparación que requieren seguimiento propio.

**Decisión.** Conservar `score de Vina < −7,0 kcal/mol` como aviso exploratorio de hERG. La comparación es inconcluyente para cambiar el corte. Mantenerlo prioriza evitar omisiones y acepta el coste de revisar más alertas. Esa prioridad es una decisión de producto. El `−7,5` del catálogo parametriza la normalización cuando hERG es la diana principal. Que allí la penalización habitual empiece por encima de −7,0 no aporta evidencia de calibración clínica. [Rutas del producto](herg-umbral-2026-11-15/README.md#qué-calcula-el-producto)

## R1 y R2 · Semillas y alcance estadístico

Se confirman los recuentos y la objeción de diseño.

| Lectura | Bloqueadores alertados con −7,0 y −7,5 | Controles alertados con −7,0 y −7,5 |
|---|---:|---:|
| Semilla 42 para los 16, análisis primario | 7/10 y 3/10 | 3/6 y 2/6 |
| Semilla 43 en los ocho repetidos, 42 en el resto, sensibilidad post hoc | 6/10 y 3/10 | 3/6 y 2/6 |

La segunda fila mide el efecto de sustituir parcialmente la semilla. Verapamilo cambia de decisión con −7,0. Haloperidol, cisaprida y tamoxifeno mantienen la diferencia entre cortes en las dos muestras. El score se movió 0,540 kcal/mol en amiodarona y 0,451 en verapamilo, desplazamientos comparables con los 0,5 que separan los cortes. La ventana de repetición dejaba fuera a droperidol, terfenadina y ziprasidona, los tres bloqueadores que cruzaron −7,5 en el análisis primario. Por ello, el recuento 3/10 de la segunda fila contiene las mismas observaciones para esos tres compuestos. Los 2,0 kcal/mol que declara el producto corresponden a la dispersión orientativa frente a afinidades experimentales para el margen de selectividad. Las ocho parejas miden directamente el efecto de la semilla en este piloto. [Resultados de ambas semillas](herg-umbral-2026-11-15/resultados.json) · [Constante del margen](../../backend/services/docking/selectividad_margen.py#L79)

Se reproducen los McNemar bilaterales de la réplica. Entre los positivos, 4 discordancias de alerta en un solo sentido dan p = 0,125. Entre los controles, una da p = 1. Si se asigna el mismo coste a ambas clases de error, la corrección de 4 casos y la pérdida de 1 dan p = 0,375. Como los cortes son anidados, relajar el corte sólo puede añadir alertas. El efecto que interesa es cuántas añade en cada clase y a qué coste. La estimación requiere una cohorte más informativa y una regla por compuesto que especifique cómo se combinan sus semillas. Se corrige la frase del informe para limitar los cuatro casos a la semilla 42.

## R3 · Identidad del microestado

La réplica identificó tres bases terciarias neutras en el piloto y un protón en el nitrógeno de la β-lactama de amoxicilina. Los pKa acuosos o de referencia apoyan incluir en un contraste la forma protonada de la amina de haloperidol (8,35 por potenciometría), cisaprida (7,9 para la piperidina, expediente FDA) y droperidol (7,6, resultado del ensayo depositado por Settimo et al.). En disolución ideal a pH 7,4 corresponden aproximadamente a 90 %, 76 % y 61 % de forma protonada, respectivamente. Son estimaciones de especiación en solución. La unión y el medio del ensayo pueden cambiar las poblaciones. Las mediciones de microionización de amoxicilina respaldan el zwitterion con la amina primaria protonada y el carboxilato, que ronda 50 % a pH 7,4. La forma aniónica con amina primaria neutra es un segundo candidato pertinente. [Avdeef y Tsinman, tabla I](https://doi.org/10.1007/s11095-008-9679-z) · [Expediente FDA de cisaprida](https://www.accessdata.fda.gov/drugsatfda_docs/nda/pre96/020210_S000_Cisapride_BIOPHARMR.pdf) · [Ensayo de pKa de droperidol](https://pubchem.ncbi.nlm.nih.gov/bioassay/781330#sid=103305836) · [Microionización de amoxicilina](https://sioc-journal.cn/Jwk_hxxb/EN/abstract/abstract326386.shtml)

**Las tres bases.** El piloto preparó los primeros ligandos en paralelo. En los tres arranques en frío de la sonda, cisaprida, droperidol y haloperidol recibieron un solo candidato de Dimorphite-DL 2.0.2 y quedaron neutros. En tres procesos que los prepararon en serie y otros tres que cargaron la tabla antes de lanzar los cuatro ligandos en paralelo, los números de candidatos fueron 2, 4 y 2 respectivamente, y se eligió el catión en cada caso. Amiodarona, incluida como cuarto compuesto en los nueve arranques, conservó sus dos candidatos en esa serie de mediciones. El resultado concuerda con una carrera en `PKaData`. La biblioteca publica la instancia compartida antes de cargar las reglas. El pool de hilos del producto permite que otro conformador entre en esa ventana. El control que cargó las 41 reglas antes de entrar al pool reprodujo la preparación en serie. [Sonda de arranque](herg-umbral-2026-11-15/comprobar_arranque_protonacion.py) · [Llamada al pool](../../backend/chem/conformer.py#L310) · [Código de Dimorphite-DL 2.0.2](https://raw.githubusercontent.com/durrantlab/dimorphite_dl/v2.0.2/dimorphite_dl/protonate/data.py)

**Amoxicilina.** La especie del piloto se reprodujo al preparar el compuesto de forma aislada. Dimorphite-DL 2.0.2 devolvió ocho candidatos, entre ellos el zwitterion con la amina primaria protonada. Dos candidatos empataron con un catión y un anión. El selector compara **recuentos** de cargas y su desempate por SMILES eligió el protón en la β-lactama. El registro de preparación marcó `quimica_resuelta=false`. Este caso de identidad de la especie sirve para el trabajo de D-04. [Selector](../../backend/chem/ionizacion.py#L543) · [Plan de D-04](plan-d04-especie-en-revision-2026-11-15.md)

Completé nueve acoplamientos post hoc con los microestados explícitos. Usé el mismo receptor preparado 5VA1, caja, binario de Vina 1.2.7, exhaustividad 8 y dos hilos, y regeneré cada conformador con el algoritmo del producto. Cada comparación usa la misma semilla en los dos brazos. Droperidol tenía una sola semilla en el piloto. [Sonda reproducible](herg-umbral-2026-11-15/comprobar_microestados.py) · [Resultados y hashes](herg-umbral-2026-11-15/contrarreplica-resultados.json)

| Compuesto y especie probada | Semilla 42, original → alternativo | Semilla 43, original → alternativo | Efecto sobre las alertas |
|---|---:|---:|---|
| Haloperidol, amina protonada | −7,171 → −6,874 | −7,306 → −6,853 | Pierde la alerta de −7,0 en las dos semillas |
| Cisaprida, amina protonada | −7,152 → −6,669 | −7,226 → −6,663 | Pierde la alerta de −7,0 en las dos semillas |
| Droperidol, amina protonada | −7,950 → −7,845 | — | Alerta con ambos cortes en la semilla 42 |
| Amoxicilina, anión | −7,394 → −7,422 | −7,435 → −7,446 | Alerta sólo con −7,0 en las dos semillas |
| Amoxicilina, zwitterion de amina primaria | −7,394 → −7,507 | −7,435 → −7,526 | Alerta con ambos cortes en las dos semillas |

Al sustituir sólo los tres scores de las bases en la semilla 42, el recuento de positivos alertados queda en **5/10 con −7,0 y 3/10 con −7,5**. Entre los controles, −7,0 añade una alerta si se usa el anión de amoxicilina y ninguna si se usa su zwitterion, porque éste cruza ambos cortes. Son sustituciones dirigidas a partir de lo observado en la réplica. Para calibrar un corte haría falta, entre otras cosas, fijar cómo se adjudica o combina la evidencia de distintos microestados por compuesto.

La regeneración del conformador impide atribuir estas diferencias exclusivamente a la carga: se contrastó el procedimiento completo con otra especie. La carrera de inicialización y la asignación del centro de protonación son dos defectos diferentes pendientes de corrección y verificación; las advertencias propuestas en D-04 no los solucionan.

## R4 · Qué mide cada columna de Rouen

El texto completo de Rouen identifica `hERG_5VA2` y `Cav_6AGF` como los receptores modelados para las variables de docking del clasificador. `vina` corresponde a hERG basado en 5VA2 y `cav_vina` al modelo comparativo CaV1.2 construido sobre una plantilla de NaV1.4, 6AGF. En el método Vina de hERG la caja se centra en Y652 y mide 10 Å. Los autores ajustaron parámetros frente a los datos de entrenamiento. En MolDesign el receptor es 5VA1 y la caja mide 28,8 × 28,8 × 30 Å. Estas diferencias, además del desenlace TdP y la preparación, impiden trasladar el corte numérico de forma directa. El reanálisis usa los 53 compuestos de entrenamiento publicados. La mediana de las diferencias de score se calcula sobre los nueve solapamientos con el piloto. [Rouen et al., métodos y tabla 1](https://europepmc.org/articles/PMC13507445) · [Depósito 6AGF](https://www.rcsb.org/structure/6AGF) · [CSV de los autores](https://github.com/kylerouen/tdp_classifiers/blob/f85243eb5f14e3ff1e54e9abf47281ea34269d10/data/data_clean.csv)

| Columna | Receptor | Mediana de score publicado menos score local | TdP detectados con −7,0 y −7,5 | Casos sin TdP que no alertan |
|---|---|---:|---:|---:|
| `vina` | hERG, modelo 5VA2 | −3,129 kcal/mol | 31/31 y 31/31 | 1/22 y 2/22 |
| `cav_vina`, comparación post hoc | CaV1.2, modelo 6AGF | +0,373 kcal/mol | 14/31 y 11/31 | 14/22 y 15/22 |

La cercanía numérica de la segunda columna se observa entre scores calculados en **canales distintos**. Por tanto, su proximidad no establece una escala común para puntuar hERG. En la primera columna, un AUC de 0,705 convive con saturación en ambos cortes. El orden relativo y la utilidad de un punto operativo son preguntas distintas.

## R5 · Fuentes y condiciones

- **Yao et al.** El patch clamp de la tabla 2 se hizo a **25 ± 0,5 °C**, con baño externo a pH 7,4. Esa temperatura pertenece al ensayo celular. El trabajo también incluye un experimento animal con otras condiciones. [Métodos de hERG](https://pmc.ncbi.nlm.nih.gov/articles/PMC2442905/)
- **Diltiazem.** Los 6,6 µM remiten a Crumb et al. (2016), reanalizado en la figura 1D del trabajo posterior. El estudio nuevo da 8,9 µM en su resumen y 9,1 µM en el cuerpo. Para la ficha basta indicar bloqueo medido en el intervalo micromolar y citar por separado ambos experimentos. [Crumb et al.](https://doi.org/10.1016/j.vascn.2016.03.009) · [Trabajo posterior, resumen y figura 4D](https://doi.org/10.3389/fphar.2025.1674861)
- **Creanza et al.** Los dos cortes citados pertenecen a Glide y al contraste IC₅₀ ≤ 1 µM frente a > 80 µM. Definen modelos y cohortes específicos. [Tabla 3](https://pmc.ncbi.nlm.nih.gov/articles/PMC9282647/#tbl3)
- **Kramer et al.** Tanto el modelo 2 como el 5 dan AUC 0,93 frente a 0,77 del modelo de margen de hERG. Ambos incorporan CaV1.2 en su construcción. [Tabla 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC3696896/#T1)

## R6 y R7 · Presentación

En la alerta por tamoxifeno, la comparación de −7,004 con −7,0 es correcta y la presentación con un decimal oculta la diferencia. Usar tres decimales cuando el valor visible coincida con el corte evita la igualdad aparente para el score Vina registrado. En caso de empate exacto debe seguir aplicándose la desigualdad estricta. La misma comparación tiene que verse coherente en panel, mensaje del servidor y dossier. [Backend](../../backend/services/docking/selectivity.py#L138) · [Panel](../../frontend/components/interfaces/pro/ProSelectivityPanel.tsx#L462)

Para el estado sin alerta propongo «En las antidianas evaluadas, ningún score de Vina cruzó su corte». Si se obtuvo score para hERG, añadir «La ausencia de alerta no descarta bloqueo de hERG». Si falta el score de hERG, indicarlo como «hERG no evaluado». Remitiría el 3/10 a la ficha de evidencia del piloto, junto al resultado por semilla y la sensibilidad a los microestados. En el Explorador corresponde nombrar el parámetro de normalización de la diana principal para distinguirlo del corte del panel. [Veredicto actual](../../frontend/components/interfaces/pro/ProSelectivityPanel.tsx#L495) · [Etiqueta del Explorador](../../frontend/lib/resultFieldPresentation.ts#L77)
