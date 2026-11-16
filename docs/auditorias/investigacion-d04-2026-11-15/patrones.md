# Patrones y controles de D-04

Aplicar los patrones al SMILES registrado tras la preparación. El átomo cero de cada patrón de coincidencia es el N que debe estar protonado. Excluir la molécula si contiene `[CX3](=O)[OX1-]`. Esta guarda deja los zwitteriones carboxílicos fuera del alcance. MES, MOPS y MOPSO son sulfonatos y permiten estudiar los dos estados del N como una pregunta aparte. Se aplica la misma exclusión de N unido directamente a un aromático que para la amina alifática del producto. En morfolina, `R1` delimita el anillo a seis átomos, cada uno perteneciente a exactamente un anillo. `-[CX4;!R]` acota la sustitución del N a carbono saturado exocíclico. [Regla de origen](../../../backend/chem/ionizacion.py#L124) · [Sonda, patrones completos y guarda](comprobar.py)

## Motivos propuestos

```text
[NX4+;!H0;!$(N[a]);!$(N~[N,O,S,P]);!$(N-[C,S,P]=[O,N,S])]-[CX4]-[CX3](=[OX1])-[OX2;H0]-[#6]
[NX4+;H1;R1;!$(N[a])]1(-[CX4;!R])[CX4;R1][CX4;R1][OX2;H0;R1][CX4;R1][CX4;R1]1
```

La primera línea identifica un α-aminoéster. La segunda reconoce N-alquilmorfolina. La tabla siguiente cubre las dos propuestas y las seis alternativas exploradas. Las métricas identifican estructuras con la etiqueta asignada del panel dirigido, no el acierto de una predicción de protonación. Los 107 controles incluyen 36 filas tomadas de los tests del repositorio, 36 construidas para las fronteras y 35 compuestos con fuentes. Las listas pueden incluir una misma estructura como prueba sintética y ejemplo publicado.

| Patrón | Sensibilidad estructural | Especificidad estructural |
|---|---:|---:|
| α-aminoéster | 17/17 | 90/90 |
| α-aminocetona/aldehído | 4/4 | 103/103 |
| N-alquilmorfolina | 6/6 | 101/101 |
| Morfolina NH | 2/2 | 105/105 |
| Propargilamina | 5/5 | 102/102 |
| β-sulfona | 4/4 | 103/103 |
| α-aminoamida | 4/4 | 103/103 |
| Oxetano en β | 2/2 | 105/105 |

También comprobé la especie preparada de los 35 compuestos con fuente. Hubo 34 preparaciones y 33 conservaron el motivo esperado. El 4-nitrofenil glicinato salió neutro, por lo que el motivo queda fuera incluso si el catión explícito coincide. La propargilamina simple tiene cuatro átomos pesados y el validador exige cinco. Su catión de control verifica la topología y no corresponde a una corrida posible por esa ruta. [Controles con ambos SMILES](controles.json)

## Fronteras y falsas alarmas

- El α-aminoéster excluye carbonilo en β, α-aminoamida, cetona, carbamato y ácido carboxílico. Se probó un zwitterion carboxílico que también contiene el motivo del éster y quedó fuera por la guarda. El patrón podría marcar un éster de una amina con pKa alto en una familia química distinta. El corpus dirigido no estima la frecuencia de ese caso.
- El patrón de N-alquilmorfolina excluye NH sin sustituir, N-arilo, N-acilo, azepano, oxazolidina, tiomorfolina y el caso fusionado. La sonda de centros del producto devuelve una amina alifática con pKa 9,8 para NH, la fusionada, tiomorfolina, oxetan-3-ilamina y oxazolidina. Devuelve cero centros para los controles N-fenilo y N-acetilo. Esta diferencia explica qué candidatos siguen abiertos aunque la clase general los detecte.
- La β-sulfona reconoce el dióxido de tiomorfolina. Para el brazo acíclico se exige el trayecto N–C–C–S y un enlace S–C. Por eso quedan fuera la tiomorfolina sin oxidar, el sulfóxido, sulfonato, sulfonamida y las posiciones α y γ. El soporte experimental para usarlo como motivo de producto sigue siendo insuficiente.
- La regla para propargilamina requiere un triple enlace a partir del carbono β y separa alquinilos más distantes, alquenos, N-arilo y amonios cuaternarios. La regla de oxetano exige un N unido directamente a C3 del anillo y excluye el análogo con un metileno interpuesto y el oxetan-2-ilamonio. El ejemplo 4a del estudio de Bull coincide en oxetano y queda fuera de N-alquilmorfolina porque el carbono unido al N también forma parte de un anillo.
- La regla de α-aminoamida reconoce el N básico a un carbono del carbonilo de amida. Los resultados de lidocaína a pH 7,4 con los pKa 7,95 y 8,06 implican alrededor de 22 % y 18 % de neutro bajo el modelo ideal. Con pKa 8,21, la bupivacaína daría alrededor de 13 %. La incertidumbre de estas fracciones y la variabilidad de condiciones justifican tratarlas como ejemplos informativos. [Mediciones y condiciones](pka-por-clase.csv)
