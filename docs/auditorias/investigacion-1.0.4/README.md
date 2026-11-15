# Investigación de las decisiones de MolDesign 1.0.4

14–15 de noviembre de 2026, fecha local. Base del producto `77aeb73775fd334a24bbe5e3e7382dd2d456379e`. Los cálculos de esta entrega usan python-embed 3.11.9 en Windows. Las predicciones y corridas archivadas conservan sus entornos originales. El propietario decide qué aplicar. [Encargo](../decisiones-pendientes-1.0.4-2026-11-14.md) · [Réplica](REPLICA-2026-11-15.md) · [Seguimiento](SEGUIMIENTO-REPLICA-2026-11-15.md)

| Ficha | Propuesta para decisión | Alcance de la evidencia |
|---|---|---|
| [D-01 · Chai-1](D01.md) | Mantener la lectura local del aviso. Atribuir al archivo el nombre Chai-1 y delimitar la convención Cα a la versión comprobada. | Las dos lecturas pasan por alto residuos del sitio bajo 70 en NET y CDK2. La sonda de un archivo editado mostró que el rótulo local de Cα puede mantenerse aunque el valor de la tabla discrepe del atómico. |
| **D-02 · Calibración del aviso** | El propietario ratificó que siga en pausa. | Sin trabajo iniciado en la ficha. |
| [D-03 · Aguas](D03.md) | Mantener la retirada declarada que ya ofrece Preparación. | Piloto de 21 complejos, INCONCLUSIVE. Pasaron 8/21 en seco, 11/21 con selectivas y 13/21 con todas las aguas locales. El contraste primario dio p = 0,508 y usó oxígenos rígidos. |
| [D-04 · pKa](D04.md) | Extender la revisión de especie a entornos definidos y comprobar candidatas de amidinas y aminas alifáticas. | Contraste de 2 345 padres de ChEMBL25, por clase y con andamios retenidos. La cobertura exacta de pKa medidos fue 1/203 en MolFlex y 0/89 en 8T69. La preparación del clopidogrel seleccionó +1 pese al pKa potenciométrico 4,55. |
| [D-05 · Metales](D05.md) | Mantener abstención y medir una observación de coordinación con donante y microestado explícitos. | Censo del catálogo y prueba técnica en seis entradas. ProLIF 2.1.0 dio NO_GO con 3/5 cristales positivos y 0/9 falsos positivos. Omitió los dos casos de Zn–sulfonamida. |
| [D-06 · Exhaustividad](D06.md) | Conservar 8 como valor por defecto. | Dos series inconcluyentes para subir a 32. En la réplica de 8HFI, 243/243 corridas terminadas, Δρ +0,013 (IC 95 % −0,062 a +0,105) y 3/5 → 5/5 redockings válidos. |
| [D-07 · Índice compuesto](D07.md) | Conservar el valor histórico y revisar por separado la métrica de ranking de Lotes. | La réplica cambió el rótulo y el prompt a índice heredado en el árbol local. El índice sigue en exportaciones de Lotes y en EF/AUC bajo firmas homogéneas. |
| [D-08 · UMS](D08.md) | Añadir una nota de cobertura al mantener los SMARTS actuales. | Sensibilidad 6/12 → 12/12. Los 12 negativos carecen de sulfonamida, hidroxamato o tiol detectados. El acetato sí activa otra familia en ambos brazos. |
| [D-09 · Antidianas](D09.md) | Revisar sitio y mecanismo antes de dar significado farmacológico a alertas y márgenes. | 38/44 acuerdos de sesiones del mismo modelo, 23 candidatas preliminares y cuatro incompatibilidades. Confirmado 7UL2 y preparada una [muestra humana de 12 casos](D09-revision-humana.md). |
| [D-10 · ESMFold](D10.md) | Mantener experimental, con cualquier validación fuera de la estación por decisión del propietario. | Confirmación documental del corte de entrenamiento y sonda Meeko, sin plegado ni docking nuevos. |

## Reproducir

Desde la raíz, con el intérprete distribuido:

```powershell
$inv = 'docs/auditorias/investigacion-1.0.4'
./python-embed/python.exe -I "$inv/recalcular.py"
./python-embed/python.exe -I "$inv/medir_d09.py"
./python-embed/python.exe -I "$inv/adjudicar_d09.py"
./python-embed/python.exe -I "$inv/comprobar_d07_molchat.py"
./python-embed/python.exe -I "$inv/comprobar_d04_banda.py"
./python-embed/python.exe -I "$inv/repetir_d08.py"
./python-embed/python.exe -I "$inv/manifiesto.py" --comprobar
./python-embed/python.exe -I "$inv/comprobar_sellos.py" --check
./python-embed/python.exe scripts/sellar_experimento.py comprobar DEC-104-D08-REPLAY
```

D-01 usa el directorio `moldesign_plddt_boltz_chai` de la segunda descarga del acta. Fijar `$chai` a ese directorio para ambos análisis. La referencia 8HFI es el PDB comprimido local. Se verificaron los 167 hashes del acta antes de usar los archivos originales. [Archivo y procedimiento de verificación](../convencion-plddt-boltz-chai-2026-11-15/README.md#dónde-está-cada-cosa)

Los archivos brutos nuevos están en `evidencia-moldesign` del directorio de evidencias de esta sesión, fuera del repositorio. Fijar `$brutos` a ese directorio para reproducir los análisis:

```powershell
./python-embed/python.exe -I "$inv/medir_d01.py" $chai
./python-embed/python.exe -I "$inv/medir_d01_cdk2.py" $chai "$brutos/D01"
./python-embed/python.exe -I "$inv/medir_d03.py" analizar "$brutos/D03"
./python-embed/python.exe -I "$inv/comprobar_d03_crudos.py" "$brutos/D03"
./python-embed/python.exe -I "$inv/medir_d04.py" "$brutos/D04/chembl25.sdf"
./python-embed/python.exe -I "$inv/medir_d05.py" medir "$brutos/D05"
./python-embed/python.exe -I "$inv/medir_d06.py" analizar "$brutos/D06"
```

El verificador en modo `--check` comprobó los 14 experimentos citados y 4 034 archivos, con cero diferencias o ausencias. También se verificó el cierre de los cinco sellos nuevos. Los archivos de procedencia registran los SHA-256 de entradas y resultados. Las fuentes web se consultaron el 14–15 de noviembre de 2026, fecha local, y se identifican por DOI, PMID, versión de código o expediente. Las páginas consultadas por navegador se citan sin guardar copias ni adjudicarles un hash de descarga. [Manifiesto local](manifiesto.json)
