# Seguimiento de la réplica del 15 de noviembre

Se contrastó la [réplica](REPLICA-2026-11-15.md) con las fichas terminadas, los resultados sellados y el árbol de D-01 y D-07, que quedó en `cfe898fe`. Las comprobaciones y correcciones de esta respuesta son de investigación.

| Ficha | Resultado del cotejo |
|---|---|
| D-01 | Pasan los ocho controles de firma y localización. La prueba de discrepancia entre el valor ModelCIF y el Cα revela un alcance excesivo en el rótulo actual, detallado abajo. |
| D-03 | La retirada y su declaración ya existen. Con distancias disponibles, Preparación identifica aguas que podrían puentear por geometría. Se corrigió la opción A y se repitieron 8, 11 y 13 éxitos del piloto. [Ficha](D03.md) |
| D-04 | El patrocinador declaró por potenciometría el pKa 4,55 a 25 °C. Se corrigió la sección del expediente a §4.1.6.1. La sonda de MolDesign reprodujo LogD 1,27 → 3,67 y CNS-MPO 4,24 → 4,31 bajo el modelo documentado. El repositorio del conjunto derivado publica CC BY 4.0 para `chembl25.sdf`. EMBL-EBI publica ChEMBL bajo CC BY-SA 3.0, de modo que la procedencia conserva ambos avisos. La monografía de Health Canada coincide con FDA y ambas son documentos del patrocinador. [Ficha](D04.md) · [FDA, folio 9/21](https://www.accessdata.fda.gov/drugsatfda_docs/nda/2002/20-839S019_Clopidogrel%20Bisulfate_EAfonsi.pdf) · [Conjunto derivado](https://github.com/czodrowskilab/Machine-learning-meets-pKa) · [ChEMBL, EMBL-EBI](https://www.ebi.ac.uk/chembldb/) |
| D-05 | Se repitió ProLIF 2.1.0 desde los archivos externos. Resultado NO_GO, 3/5 cristales positivos y 0/9 falsos positivos. [Ficha](D05.md) |
| D-06 | Los tiempos publicados mezclaban 57 padres y cinco redockings, salvo 8/43. Se añadieron medianas de sólo padres. Con 32 frente a 8/42 la razón es 2,03 y se conserva INCONCLUSIVE. [Ficha](D06.md) |
| D-07 | Pasan las tres pruebas del prompt y las dos de presentación. El informe histórico y el ranking de Lotes quedan fuera del cambio que revisó la réplica. [Ficha](D07.md) |
| D-08 | El 12/12 corresponde al conjunto de tres familias. Si se exige que ningún grupo UMS se active, el recuento es 11/12 por el acetato. El dossier distingue cero calculado, ausencia e histórico. Se corrigió la recomendación para añadir una nota explícita de cobertura. [Ficha](D08.md) |
| D-09 | Se identificaron el modelo y las sesiones que escribieron las actas. Se confirmó la discordancia de 7UL2 y se preparó la muestra para revisión humana. |
| Índice y limpieza | El README actual ya recogía 21 complejos de aguas, 243 corridas de 8HFI, 44 filas y 14 experimentos. `__pycache__` está ignorado por Git. El validador de enlaces de la entrega excluye el código en línea y pasó el control de SMARTS. |

## D-01 · Autorreporte frente a comprobación de Cα

Se usó el recorte real de Chai-1 0.6.1 y se cambió sólo la primera fila de `_ma_qa_metric_local.metric_value`, de 91,387 a 51, en memoria. El PDB convertido tuvo los mismos bytes. La ruta leyó el nuevo valor y conservó la fuente declarada `chai1`, `lectura: calfa` y `verificada: false`. El texto siguió diciendo que se trata del valor del Cα. La recomendación es atribuir inequívocamente al archivo el nombre Chai-1 y al caso comprobado de 0.6.1 la convención de Cα. Si se afirma que el archivo específico usa Cα, conviene exigir correspondencia entre la tabla local y el Cα del propio archivo. Esta comprobación concierne a la procedencia, con D-02 en pausa. [Lector](../../../backend/services/targets/prediccion.py#L364) · [Rótulo de Preparación](../../../backend/services/dossier/preparacion_confianza.py#L99)

## D-09 · Procedencia y contraste

El registro local de Codex identifica al modelo `gpt-6.1-sol` con esfuerzo `xhigh` en las cuatro sesiones autoras. Cada sesión dejó su acta en un archivo distinto. Las sesiones usaron el encargo, la escala y la base de evidencia comunes. Quedó sin acreditar un cegamiento verificable o una diversidad de modelo. Corregimos la expresión «dos revisores independientes» en la lectura actual del informe. Las actas y protocolos originales conservan sus bytes.

| Acta | Alias de sesión | Ruta de agente | Apertura UTC |
|---|---|---|---|
| Piloto A | Noether | `/root/revision_d09_a` | 15 nov 04:04:53 |
| Piloto B | Popper | `/root/revision_d09_b` | 15 nov 04:04:59 |
| Ampliación A entregada | Mencius | `/root/bowes_a` | 15 nov 05:18:15 |
| Ampliación B entregada | Newton | `/root/bowes_b` | 15 nov 05:18:21 |

La revisión estructural de OPRK1 confirma que **Q6Q es SR48692** en el bolsillo de NTSR1. Los 42 átomos pesados de Q6Q reproducen el centro del panel a 0,00054 Å. La distancia mínima al tramo `P41145` insertado es 22,89 Å y al tramo `P30989` más cercano, 3,10 Å. Los autores describen el intercambio de ICL3 para estabilizar el constructo. [Depósito](https://www.rcsb.org/structure/7UL2) · [Q6Q](https://www.rcsb.org/ligand/Q6Q) · [Robertson et al., fig. 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC12014012/) · [Cálculo y hash](comprobar_seguimiento_replica.py)

**6B73** aporta un receptor κ humano en estado activo ligado al agonista MP1104. Contiene una fusión citocromo b562 y tiene un nanocuerpo estabilizador. Se preselecciona para revisar ensamblaje, continuidad, contactos del ligando y preparación. **4DJH** aporta una referencia del estado antagonista con JDTic. El fenotipo de sedación tiene soporte en humanos con enadolina, un agonista κ. La estructura permite proponer un sitio para el mecanismo. Un score de Vina por sí solo carece de dirección funcional. [6B73](https://www.rcsb.org/structure/6B73) · [4DJH](https://www.rcsb.org/structure/4DJH) · [Walsh et al., PMID 11594439](https://pubmed.ncbi.nlm.nih.gov/11594439/)

La [muestra para revisión humana](D09-revision-humana.md) contiene seis de las 23 candidatas de distintas familias, las cuatro incompatibilidades y los dos controles vigentes. La selección es dirigida. Entregar al revisor únicamente la hoja de casos y registrar su dictamen antes de mostrar las actas. Publicar cada desacuerdo. Una fila revisada gana respaldo documental cuando el dictamen humano cita sitio y mecanismo correspondientes. Las filas fuera de la muestra conservan su carácter preliminar. La revisión humana queda pendiente de un revisor.

Con una afinidad sintética de −7,2 kcal/mol ante umbral −7,0 y diana principal a −8,0, OPRK1 disparó `ALERTA` y determinó el margen de 0,8 kcal/mol tanto con `sitio_adjudicado: false` como con `true`. El score se inyectó en el panel sin ejecutar docking. Al evaluar una nueva regla conviene propagar la adjudicación al emitir la alerta y al interpretar el margen, con pruebas para lista, ejecución e historial. [Lista de antidianas](../../../backend/api/routers/pro_features.py#L110) · [Alertas y margen](../../../backend/services/docking/selectivity.py#L389)

## Reproducir

```powershell
$inv = 'docs/auditorias/investigacion-1.0.4'
./python-embed/python.exe -B -I "$inv/replica_verificar.py" .
./python-embed/python.exe -B -I "$inv/comprobar_seguimiento_replica.py"
./python-embed/python.exe -B -I "$inv/comprobar_seguimiento_replica.py" --producto
```

La opción `--producto` usa el árbol de trabajo y un bucle local de asyncio. Puede requerir un entorno que permita abrir el canal interno del bucle en Windows. Sus entradas de selectividad son simuladas.
