# Error del pKa único por clase en ChEMBL25

DEC-104-D04-CHEMBL. pH de decisión 7,4. Compuestos neutros con un solo centro reconocido, valores por padre como mediana de sus registros. MAE y sesgo de la tabla sobre todos los padres admitidos. La mejora es el MAE de la tabla menos el MAE de la mediana ajustada, sólo en andamios retenidos. [Método](D04-ChEMBL-registro.md) · [Salida](../../../scripts/artifacts_science/DEC-104-D04-CHEMBL/metrics.json)

| Clase | n | MAE de tabla | Sesgo de tabla | n evaluación | Mejora MAE | Cumple |
|---|---:|---:|---:|---:|---:|---|
| Ácido carboxílico | 269 | 0,97 | −0,16 | 91 | +0,03 | |
| Amidina | 100 | 3,78 | +3,71 | 27 | +1,81 | Sí |
| Amina alifática | 855 | 1,89 | +1,70 | 241 | +0,51 | Sí |
| Anilina | 134 | 2,13 | −1,10 | 41 | −0,33 | |
| Biguanida | 6 | 1,40 | +0,85 | 5 | −0,65 | |
| Fenol | 165 | 2,59 | +2,14 | 111 | +0,28 | |
| Fosfato | 13 | 3,05 | −3,05 | 4 | −0,25 | |
| Guanidina | 123 | 2,53 | +2,42 | 24 | +0,74 | |
| Imidazol | 48 | 1,85 | +1,11 | 16 | +0,68 | |
| Piridina | 417 | 1,98 | −0,90 | 119 | +0,22 | |
| Sulfonamida arilo | 98 | 3,27 | +3,26 | 54 | +0,26 | |
| Sulfonamida primaria arilo | 74 | 1,15 | +0,72 | 34 | −0,64 | |
| Sulfonilurea arilo | 11 | 0,40 | −0,11 | 7 | +0,02 | |
| Tetrazol | 32 | 0,65 | +0,44 | 9 | −0,32 | |

Se excluyeron 1 360 registros por carga o mezcla. Tras agrupar por compuesto, quedaron fuera 2 753 padres por asignación no unívoca y 84 por mediciones con rango > 1 unidad. Se conserva el número de fila del SDF por medición y la temperatura cuando consta. El expediente cumple la atribución identificando a Baltruschat y Czodrowski y ChEMBL25 como origen. [Datos por padre](../../../scripts/artifacts_science/DEC-104-D04-CHEMBL/per_complex.jsonl) · [Licencia del directorio de datos](https://github.com/czodrowskilab/Machine-learning-meets-pKa/tree/master/datasets)
