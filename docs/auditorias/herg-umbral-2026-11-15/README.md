# Umbral de alerta de hERG en MolDesign

15 de noviembre de 2026. Base de producto `ffddd7e92d60d2ec0f8c9ecb8879c3388de3ffd5`. [Registro previo](PROTOCOLO.md) · [Script de reproducción](medir.py)

**Decisión operativa.** Conservar **score de Vina < −7,0 kcal/mol** para la alerta exploratoria de hERG. La evidencia es inconcluyente para cambiar el corte. Mantenerlo prioriza evitar omisiones y acepta el coste de revisar más alertas. El −7,5 de la diana principal es un parámetro del normalizador. [Contrarréplica](../contrarreplica-herg-umbral-2026-11-15.md)

## Qué calcula el producto

| Ruta | Valor de 5VA1 | Qué hace |
|---|---:|---|
| Panel de selectividad | −7,0 kcal/mol | Emite alerta de docking si el score de Vina es estrictamente menor. La lista y la ejecución del panel, el streaming y el docking individual de la antidiana usan el panel predeterminado. El score también va al margen exploratorio, que se calcula con independencia de cruzar el corte. [Panel](../../../backend/services/docking/selectivity.py#L68) · [Regla y margen](../../../backend/services/docking/selectivity.py#L426) · [API](../../../backend/api/routers/pro_features.py#L86) |
| hERG como objetivo principal | −7,5 kcal/mol | Parámetro de normalización del score de afinidad. Para un ligando ordinario con recuento de átomos pesados, la tolerancia de 0,5 kcal/mol hace que la penalización empiece por encima de −7,0. La alternativa sin ese dato centra una sigmoide en el parámetro. Es el valor general de 379/381 entradas del catálogo. [Fila de 5VA1](../../../curated_targets.json#L24943) · [Uso en scoring](../../../backend/scoring/engine.py#L488) · [Normalizador](../../../backend/scoring/normalizer.py#L12) |

La etiqueta genérica «umbral de afinidad registrado» facilita leer ambos valores como si gobernaran la alerta. La corrección de presentación es distinguir «corte de alerta exploratoria hERG (score de Vina)» y «parámetro de normalización de afinidad de la diana principal». Igualar los dos números modificaría un cálculo distinto. El cambio de política de alerta afectaría exactamente a scores en [−7,5; −7,0), incluido −7,5. [Etiqueta del Explorador](../../../frontend/lib/resultFieldPresentation.ts#L77)

La sonda de contrato devolvió −7,0 tanto en el panel por defecto como al pedir 5VA1 por ID, aun con un repositorio que declaraba −7,5. En el normalizador, una sonda de 30 átomos pesados y score −6,8 pasó de 20,93 a 22,27 sobre 100 al mover su parámetro de −7,5 a −7,0. Se ejecutaron 23 pruebas de antidianas, paridad de sitio y veredicto. [Sonda reproducible](medir.py)

## Evidencia experimental publicada

- **El poro tiene respaldo estructural.** 5VA1 describe hERG humano con la compuerta intracelular abierta y sin inhibidor en el depósito. El control 8ZYQ contiene pimozida en el poro. En la auditoría de MolDesign, la pimozida proyectada cae completa dentro de la caja de 5VA1 y el redocking de 8ZYQ dio 1,7 Å. Son controles de sitio y pose. [Wang y MacKinnon](https://pubmed.ncbi.nlm.nih.gov/28431243/) · [Depósito 8ZYQ](https://www.rcsb.org/structure/8ZYQ) · [Evidencia local de la caja](../investigacion-1.0.4/D09.md)
- **El corte depende del método y de la conformación.** Creanza et al. ajustaron umbrales con ChEMBL25 usando Glide y GOLD. En Glide obtuvieron −6,012 kcal/mol para 5VA1 y −8,967 para su 5VA1-IFD-1 al separar compuestos con IC₅₀ ≤ 1 µM de compuestos con IC₅₀ > 80 µM. [Creanza et al., tabla 3](https://pmc.ncbi.nlm.nih.gov/articles/PMC9282647/#tbl3)
- **Bloqueo y torsade son desenlaces distintos.** En las mediciones multicanal de 55 fármacos de Kramer et al., el AUC del modelo de margen hERG fue 0,77 y el de los modelos 2 y 5, con información de CaV1.2, fue 0,93. Verapamilo ilustra la diferencia. La guía ICH E14/S7B (R1), Q&A 1.3 y 2.1, relaciona la IC₅₀ funcional, la exposición libre y los fármacos de referencia medidos con protocolo comparable. [Kramer et al., tabla 1](https://pmc.ncbi.nlm.nih.gov/articles/PMC3696896/#T1) · [ICH E14/S7B (R1)](https://www.ema.europa.eu/en/documents/scientific-guideline/ich-e14-s7b-r1-qas-clinical-nonclinical-evaluation-qt-qtc-interval-prolongation-and-proarrhythmic-potential-non-antiarrhythmic-drugs-questions-answers-step-5_en.pdf)

### Reanálisis de 53 fármacos de Rouen et al.

Se aplicaron los dos cortes a `vina`, columna de hERG del modelo basado en 5VA2 con caja Vina de 10 Å centrada en Y652. La etiqueta de referencia es TdP en el conjunto de entrenamiento publicado. En los nueve solapamientos con el piloto local, la mediana de score publicado menos score local es −3,129 kcal/mol. La otra columna, `cav_vina`, corresponde al modelo CaV1.2 basado en 6AGF. Su diferencia mediana de +0,373 kcal/mol compara dos canales. [Métodos de Rouen et al.](https://europepmc.org/articles/PMC13507445) · [Contraste de las columnas](../contrarreplica-herg-umbral-2026-11-15.md)

| Corte estricto | Casos TdP alertados | Casos sin TdP que no alertaron |
|---|---:|---:|
| < −7,0 | 31/31 | 1/22 |
| < −7,5 | 31/31 | 2/22 |

Sólo cambia diltiazem (−7,381 kcal/mol). Su etiqueta de TdP es negativa. Los experimentos de Crumb et al. y el estudio posterior midieron bloqueo hERG en el intervalo micromolar. Los dos cortes saturan la alerta en la columna `vina` y dejan sin alertar a lo sumo dos de los 22 casos sin TdP. [Datos de Rouen et al., revisión fija](https://github.com/kylerouen/tdp_classifiers/blob/f85243eb5f14e3ff1e54e9abf47281ea34269d10/data/data_clean.csv) · [Crumb et al.](https://doi.org/10.1016/j.vascn.2016.03.009) · [Experimento posterior](https://pmc.ncbi.nlm.nih.gov/articles/PMC12640937/)

### Piloto con Vina de MolDesign y patch clamp publicado

Se acoplaron los 16 compuestos de Yao et al. con Vina 1.2.7 instrumentado del producto, receta 7, receptor de cuatro cadenas `7f29ccf5…`, caja 28,8 × 28,8 × 30 Å, exhaustividad 8 y semilla 42. El patch clamp de Yao se hizo a 25 ± 0,5 °C con baño externo a pH 7,4. El corte analítico experimental es IC₅₀ ≤ 10 µM dentro de ese estudio. Los tres límites inferiores de IC₅₀ superan el corte. [Yao et al., métodos y tabla 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC2442905/) · [Registro previo](PROTOCOLO.md)

| Corte estricto de Vina | Alertas en los 10 bloqueadores | Alertas en los 6 controles | Sensibilidad, IC 95 % de Wilson | Especificidad, IC 95 % de Wilson |
|---|---:|---:|---:|---:|
| < −7,0 | 7/10 | 3/6 | 70 % (40–89 %) | 50 % (19–81 %) |
| < −7,5 | 3/10 | 2/6 | 30 % (11–60 %) | 67 % (30–90 %) |

Los cuatro bloqueadores que cruzaron sólo −7,0 en semilla 42 fueron haloperidol (0,015 µM, score −7,171), cisaprida (0,091 µM, −7,152), tamoxifeno (0,777 µM, −7,142) y verapamilo (0,94 µM, −7,196). El McNemar exacto bilateral entre positivos da p = 0,125. La alerta adicional entre controles es amoxicilina (IC₅₀ > 50 000 µM, −7,394). Moxifloxacino (235 µM, −8,044) activa ambos cortes. Amiodarona (0,546 µM, −6,834) queda fuera de ambos. Con IC₅₀ ≤ 1 µM, se detectan 7/8 frente a 3/8. Al excluir 5–20 µM se detectan 7/9 frente a 3/9. Entre las 13 IC₅₀ no censuradas, ρ = 0,39 entre −score y −log₁₀ IC₅₀ (p descriptiva = 0,19). La cohorte pequeña, el receptor rígido, la asignación de microestados del producto y la variación por semilla delimitan la inferencia. El valor de 10 µM sirve para esta comparación y la sensibilidad observada carece de validación poblacional. [Yao et al., tabla 2](https://pmc.ncbi.nlm.nih.gov/articles/PMC2442905/) · [Dependencia del protocolo de patch clamp, Milnes et al.](https://doi.org/10.1016/j.vascn.2010.02.007)

Se repitieron ocho moléculas próximas a los cortes. Sustituir por la semilla 43 esas ocho observaciones baja el recuento con −7,0 a 6/10 positivos. Con −7,5 queda en 3/10, ya que sus tres positivos quedaron fuera de la ventana de repetición. Verapamilo cambió de −7,196 a −6,745 y dejó de alertar. Las 24 corridas compartieron receptor, caja y binario. Se verificó el SHA-256 de cada traza de Vina. [Resultados, microestados y hashes](resultados.json)

En el piloto se acoplaron neutros haloperidol, cisaprida y droperidol. La sonda posterior reprodujo la pérdida de candidatos al preparar los primeros ligandos en paralelo antes de completar la carga de reglas de Dimorphite-DL. En serie y con precarga se eligieron sus cationes. Haloperidol y cisaprida protonados dejaron de cruzar −7,0 en las dos semillas. El zwitterion con la amina primaria protonada de amoxicilina cruzó ambos cortes en las dos semillas. Con los cationes explícitos de las tres bases, el recuento de positivos de la semilla 42 pasó a 5/10 frente a 3/10. La asignación del microestado cambia los recuentos del piloto. [Contrarréplica y contraste de preparación](../contrarreplica-herg-umbral-2026-11-15.md)

### Redondeo en la alerta

La decisión se toma con el score completo, pero el mensaje de backend y el frontend muestran un decimal. Tamoxifeno dio −7,004 en semilla 43. Dispara la alerta y el texto actual pone «−7.0 kcal/mol < umbral −7.0». Para que la interfaz explique su decisión, conviene mostrar el score con la precisión registrada al lado del límite o indicar que la comparación usa el valor previo al redondeo. [Mensajes del backend](../../../backend/services/docking/selectivity.py#L138) · [Mensajes del panel](../../../frontend/components/interfaces/pro/ProSelectivityPanel.tsx#L462)

## Reproducir

Los archivos brutos se guardaron fuera de Git en `evidencia-moldesign/HERG-UMBRAL`. Contienen el archivo versionado de Rouen, las respuestas de PubChem para los 16 CIDs, los resultados por corrida y las trazas del motor. Los hashes están en [resultados](resultados.json). Desde la raíz, con `$datos` fijado a ese directorio:

```powershell
$script = 'docs/auditorias/herg-umbral-2026-11-15/medir.py'
./python-embed/python.exe -B -I $script contrato
./python-embed/python.exe -B -I $script publicada $datos
./python-embed/python.exe -B -I $script local $datos
```

Con los datos brutos del piloto ya presentes, estas son las sondas de la contrarréplica. Cada invocación de la sonda de arranque crea un proceso nuevo. El [resumen verificable](contrarreplica-resultados.json) incluye los valores, las especies, los hashes y el reanálisis de ambas columnas de Rouen.

```powershell
$microestados = 'docs/auditorias/herg-umbral-2026-11-15/comprobar_microestados.py'
./python-embed/python.exe -B -I $microestados $datos bases
./python-embed/python.exe -B -I $microestados $datos amoxicilina

$arranque = 'docs/auditorias/herg-umbral-2026-11-15/comprobar_arranque_protonacion.py'
foreach ($modo in 'serie', 'paralelo-frio', 'paralelo-caliente') {
    foreach ($repeticion in 1..3) {
        ./python-embed/python.exe -B -I $arranque $datos $modo $repeticion
    }
}
```
