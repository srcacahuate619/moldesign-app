# D-04 · Cuándo declarar la especie de una amina en revisión

15 de noviembre de 2026. Respuesta al [encargo de 1.0.4](../../encargos/ENCARGO_D04_ESPECIE_EN_REVISION_20261115.md). Base `ffddd7e9`, Python 3.11.9, RDKit 2025.09.6 y Dimorphite-DL 2.0.2. [Registro previo](PROTOCOLO.md) · [Medidas, condiciones y fuentes](pka-por-clase.csv) · [Resultados regenerables](resultados.json) · [Manifiesto](manifiesto.json)

**Recomendación.** Añadir dos motivos de revisión, uno para **α-aminoéster con esa amina protonada** y otro para **N-alquilmorfolina no fusionada con el N del anillo protonado**. Conservar las α-aminoamidas como observación informativa en la ficha. Para las demás familias, la evidencia medida quedó por debajo del criterio de admisión.

## Lo que se midió

El criterio previo exige al menos tres padres y dos fuentes directas independientes con temperatura y fuerza iónica conocidas o deducibles. Pide una mediana ≤ 8,9 y al menos dos tercios de padres a ese lado del corte. La banda 5,9–8,9 identifica coexistencia apreciable a pH 7,4. Debajo de 5,9, una monobase ideal está mayoritariamente neutra, lo que también justifica revisión si se acopló el catión. El contraste de ChEMBL es descriptivo y usa los padres con clase `amina_alifatica` en el conjunto sellado de 2 345. [Protocolo](PROTOCOLO.md) · [Censo, filas y pKa](censo-chembl.json) · [Umbral de Preparación](../../../backend/services/dossier/preparacion.py#L1037)

| Entorno | Padres A en banda y rango de pKa | ChEMBL25 en banda / con motivo | Dictamen para 1.0.4 |
|---|---|---:|---|
| α-aminoéster | 14/14, 7,10–7,90, mediana 7,60 | 1/1 | **GO**. Declarar revisión. La serie primaria se compone de ésteres de aminoácidos con amina primaria. |
| α-aminocetona / α-aminoaldehído | 2/2, 7,49–8,75. Ambos son cetonas. | 7/8 | **INCONCLUSIVE**. Obtener una tercera medida A y cobertura de aldehídos antes de extender. |
| N-alquilmorfolina | 3/3, 7,42–7,75, mediana 7,445 | 20/28 | **GO**. Declarar revisión para el patrón acotado. Los ocho padres restantes de ChEMBL están por debajo de 5,9. |
| Morfolina NH | 1/1, 8,72 | 5/5 | **INCONCLUSIVE**. Mantener como caso de frontera. La cifra de 8,72 es para la morfolina sin sustituir y hay otros valores publicados. |
| Propargilamina | 2/2, 7,12–7,44. Ambas N-sustituidas. | 0/1 | **INCONCLUSIVE**. Ambos fármacos son ejemplos medidos. Falta un tercer padre A y una medida primaria de la amina primaria con condiciones. |
| β-sulfona | 0 A. Hay medidas publicadas de 5,4 en el anillo y 7,8 en la fenilsulfona abierta. | 1/2 | **INCONCLUSIVE**. Conservar ambos resultados como nivel B hasta verificar condiciones y diversidad de serie. |
| α-aminoamida | 1/1, mediana 8,005 de dos medidas de lidocaína | 30/41 | **INCONCLUSIVE**. Informativa. Lidocaína y bupivacaína ilustran coexistencia a pH 7,4 y predominio del catión en agua. |
| Oxetano en β | 0 A. El caso 4a de una morfolina unida a oxetano tiene 4,61 medido. | 2/8 | **INCONCLUSIVE**. Mantener como candidato. Falta la medida de la oxetan-3-ilamina y una serie con condiciones verificadas. |

Los 14 ésteres tienen un límite inferior exacto del 95 % de 0,77 para el recuento en banda. En N-alquilmorfolina, con sólo tres padres, es 0,29. El intervalo describe esos recuentos bajo un modelo binomial. La búsqueda dirigida y el parentesco de los ésteres impiden generalizarlo como tasa de acierto. El glicinato etílico dio 7,90 a 25 °C e I = 0,10 M. La N-etilmorfolina dio 7,75 ± 0,01 a 25 °C e I = 0,10 M de KNO₃, en la titulación del ligando libre. [Doğan, tabla 2](https://arastirmax.com/en/system/files/dergiler/5672/makaleler/21/3/arastirmax-bazi-amino-asitlerin-etil-metil-esterlerinin-protonasyon-sabitlerinin-su-ortaminda-potansiyometrik-yontemle-tayini.pdf) · [Edsall y Blanchard, tabla III](https://doi.org/10.1021/ja01333a019) · [N-etilmorfolina, tabla 1](https://doi.org/10.5012/bkcs.2005.26.4.614) · [Houston, tabla 9](https://repository.gatech.edu/bitstreams/11072616-aa06-47a3-8911-6345c45f71ca/download) · [Titulación de MOPS, tabla 1](https://doi.org/10.1021/je0500983)

El clopidogrel salió catión en el producto. Hay un pKa **experimental comunicado por el patrocinador**, 4,55 por potenciometría a 25 °C, con fuerza iónica e incertidumbre sin declarar. Se mantiene nivel C y queda fuera de la regla de admisión. El límite es la trazabilidad de la medición publicada. [Expediente FDA, §4.1.6.1](https://www.accessdata.fda.gov/drugsatfda_docs/nda/2002/20-839S019_Clopidogrel%20Bisulfate_EAfonsi.pdf)

## Patrones y coste para 1.0.4

Los controles son estructurales. Los patrones nuevos no marcaron ninguna de las 17 especies correctas del repositorio. Un α-aminoéster que sale neutro queda fuera del motivo. Esto ocurrió con el 4-nitrofenil glicinato, que sí coincidió al forzar el catión para el control SMARTS. La N-arilmorfolina queda fuera del patrón y la tabla tampoco la reconoce como amina alifática. La morfolina NH, un anillo fusionado, una oxazolidina y una tiomorfolina tienen controles separados. [Patrones, métricas y fronteras](patrones.md) · [SMILES y resultados por control](controles.json) · [Registro de centros](../../../backend/chem/ionizacion.py#L124)

Si se adoptan los dos motivos, se añaden en `especie_en_revision.py`, con sus regresiones y traducciones en dossier y elevación. La revisión modifica el estado «Especie» y puede mover la instantánea del expediente de una corrida afectada. Es una modificación de presentación sin efecto en receptor, preparación de ligando, ranking, LogD, CNS-MPO o score. Para retirar o estrechar cualquiera de los avisos, servirían mediciones A de nuevas series con pKa > 8,9 o falsos positivos verificados en especies acopladas reales. Verificar los goldens y las dos series de impacto previstas antes de la integración. [Textos propuestos](textos.md) · [Plan de implementación y pruebas](../plan-d04-especie-en-revision-2026-11-15.md) · [Límites y fuentes incompletas](NO-VERIFICADO.md)

## Reproducción

Obtener el [SDF fuente](../investigacion-1.0.4/D04-ChEMBL-registro.md) con su huella indicada. Ejecutar desde la raíz. El script regenera CSV, controles, resultados y censo. Los ensayos de preparación llaman a la función del producto en serie a pH 7,4. El censo compara por huella cada fila con la fila sellada y aplica la proyección neutra como búsqueda de motivos potenciales.

```powershell
$ficha = 'docs/auditorias/investigacion-d04-2026-11-15'
$env:MOLDESIGN_TESTING = '1'
$env:ENVIRONMENT = 'testing'
./python-embed/python.exe -B -X utf8 -I "$ficha/comprobar.py" $sdf
./python-embed/python.exe -B -I "$ficha/manifiesto.py" --check
```
