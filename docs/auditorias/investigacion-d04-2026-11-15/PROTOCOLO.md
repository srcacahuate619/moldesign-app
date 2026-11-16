# D-04 · Registro previo de los entornos de aminas

15 de noviembre de 2026, fecha local. Pregunta y entregables del [encargo](../../encargos/ENCARGO_D04_ESPECIE_EN_REVISION_20261115.md). Base `ffddd7e92d60d2ec0f8c9ecb8879c3388de3ffd5`, Python embebido 3.11.9, RDKit 2025.09.6. Los valores preliminares impresos en el encargo ya son conocidos. El registro se firma antes de buscar sus nuevas fuentes, ejecutar las sondas y abrir los valores de las filas de ChEMBL para estas clases. La investigación anterior sobre la clase amplia y las sondas de hERG orientan la pregunta.

## P1 y P2 · Evidencia y regla de decisión

- Búsqueda dirigida por los nombres, derivados cercanos y nombres genéricos del encargo, con `pKa`, `dissociation constant`, `potentiometric` y `aqueous`. Buscar también trabajos por serie y rastrear sus referencias. Incluir padres distintos con una medición acuosa experimental y adjudicar la amina por estructura, especie, pH medido y método del artículo. Excluir cálculos, medios mixtos sin extrapolación a agua, pKa de otro sitio y duplicados de la misma medida del recuento A. Para padres con más de un valor A, conservar todos y usar la mediana por padre. Usar 20–30 °C para la comparación primaria y documentar aparte las demás temperaturas.
- Nivel A según el encargo, medida primaria con temperatura y fuerza iónica numérica, extrapolación explícita a fuerza iónica cero, o composición y concentración del electrolito que permitan calcularla. Nivel B para compilaciones con referencia y medidas primarias parciales que no permiten el criterio A. Nivel C para modelos, monografías sin primaria comprobada y documentos de patrocinador. Registrar ausencias, inclusive si parecen plausibles. La compilación IUPAC puede servir de índice bibliográfico conforme a su licencia. La admisión y cada texto de producto se fundamentan en medidas primarias citables y no en datos que requieran redistribuir esa compilación.
- Por patrón o subgrupo prespecificado, reportar n de padres A, mediana, intervalo observado, proporción en la banda cerrada 5,9–8,9 y proporción con pKa ≤ 8,9. Ambas proporciones sirven a preguntas distintas. El tope 8,9 es el de Preparación y corresponde aproximadamente a un 3 % de neutro para una monobase ideal a pH 7,4. Un pKa inferior a 5,9 también es motivo de revisión si se acopló el catión, porque el estado mayoritario esperado en solución es neutro.
- **GO** para proponer revisión si hay ≥ 3 padres A y ≥ 2 fuentes primarias independientes, mediana ≤ 8,9 y al menos dos tercios de los padres A en pKa ≤ 8,9. **NO_GO** con ese mínimo de padres y fuentes si la mediana excede 8,9 y menos de dos tercios quedan bajo el tope. **INCONCLUSIVE** en los demás casos. Cero coincidencias entre las 17 especies correctas verificadas, cero fallos en negativos dirigidos de frontera y correspondencia con el centro protonado son condiciones adicionales para recomendar un patrón implementable. Los controles de estructura no demuestran sensibilidad para detectar pKa incorrectos.
- La búsqueda es dirigida y carece de potencia para estimar prevalencia. Con 3/3 resultados, el IC bilateral exacto del 95 % de la proporción es aproximadamente 0,29–1. Publicar recuento e intervalo para los datos A disponibles. P5 es un censo descriptivo de un conjunto ya fijado. Sus valores son nivel B como máximo y no cambian el dictamen primario.

## P3 a P5 · Patrones y sondas fijados

`N` en la tabla es la abreviatura de `[NX4+;!H0;!$(N[a]);!$(N~[N,O,S,P]);!$(N-[C,S,P]=[O,N,S])]`. Aplicar a la especie acoplada. Excluir moléculas con carboxilato y centro catiónico de estos motivos con una guarda molecular `[CX3](=O)[OX1-]`, porque no se adjudica el equilibrio de un zwitterion con esta regla. En P5 se mide el **motivo estructural potencial del padre**, con la proyección neutra del mismo átomo N y la misma topología. Las filas P5 carecen de la especie acoplada y su estructura se recupera por identidad del SDF y el código original. Reportar aparte el recuento de especies preparado por el producto sólo si se ejecuta.

| Rama | Criterio SMARTS inicial |
|---|---|
| α-aminoéster | `N-[CX4]-[CX3](=[OX1])-[OX2;H0]-[#6]` |
| α-aminocetona/aldehído | `N-[CX4]-[CX3H0](=[OX1])-[#6]` o `N-[CX4]-[CX3H1](=[OX1])` |
| N-alquilmorfolina | `[NX4+;H1;R1;!$(N[a])]1(-[CX4;!R])[CX4;R1][CX4;R1][OX2;H0;R1][CX4;R1][CX4;R1]1` |
| Morfolina NH | El mismo anillo sin la rama del N y con `H2` en lugar de `H1`. |
| Morfolina N-arilo y fusionada | Controles estructurales de frontera, separados de N-alquil no fusionada. La fusión incluye cualquier átomo del anillo con más de una pertenencia a anillo. |
| Propargilamina | `N-[CX4]-[CX2]#[CX2]`. Reportar la amina primaria por separado de las N-sustituidas. |
| β-sulfona | `N-[CX4]-[CX4]-[SX4](=[OX1])(=[OX1])-[#6]`. Reportar cíclicas y acíclicas. |
| α-aminoamida | `N-[CX4]-[CX3](=[OX1])-[#7]`. Zona gris, contar y evaluar como rama propia. |
| Oxetano en β | `N-[CX4;R1]1[CX4;R1][OX2;H0;R1][CX4;R1]1`. Zona gris, contar y evaluar como rama propia. |

Fijar los positivos dirigidos a partir de nombres del encargo y variantes estructurales de frontera sin dato de pKa. Anotar su condición de referencia. Probar las 17 especies correctas, 2 errores, 5 aminas con atractor y los negativos versionados del test. Entre los negativos de frontera probar amina ordinaria, anilinio, amonio cuaternario, zwitterión, carbonilos en β, amidas, sulfonamidas, sulfóxidos, distancia al alquino y al menos un anillo distinto por morfolina, oxetano y β-sulfona. Una familia puede ser un negativo local para otra y pertenecer a su propia hipótesis. Usar los SMILES de corridas donde existen. Generar en serie, a pH 7,4, la especie del producto para los compuestos con identidad química y registrar el SMILES resultante. Si un ejemplo entró neutro o el producto eligió otro N, informar ese límite además del patrón sobre el catión explícito.

Para P5 usar las 2 345 filas selladas de `DEC-104-D04-CHEMBL/per_complex.jsonl` y verificar la huella del SDF fuente. Probar que la intersección por ID neutralizado recupera el mismo total antes de contar ramas. Reportar el denominador y las reglas de neutralización de ese cálculo. Cualquier corrección de los SMARTS posterior a los controles va en una enmienda con ambos resultados, sin cambiar los cortes P2.

## P6 y P7 · Entrega

Entregar el texto para cada motivo que supere ambos controles. Si una familia queda inconcluyente, indicar qué le falta, con sus datos verificables y la cifra por clase. Registrar los consumidores y el efecto esperado en la presentación del dossier. El criterio aplicado en docking sigue el de la compilación distribuida. La investigación no modifica código de producto ni experimentos sellados. El manifiesto enlazará la salida con fuentes y versiones.
