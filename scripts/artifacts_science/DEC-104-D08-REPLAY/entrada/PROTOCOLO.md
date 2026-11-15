# Protocolo de los contrastes de bajo coste

Base del producto `77aeb73775fd334a24bbe5e3e7382dd2d456379e`. El trabajo documental usa el árbol de esa revisión. Los cálculos locales usan python-embed 3.11.9. Se conocen las observaciones publicadas en el encargo, por lo que toda relectura de esas cohortes es descriptiva.

## D-09 · Adjudicación documental

Piloto de nueve filas del Bowes-44. Controles internos HTR2B/7SRQ y KCNH2/5VA1. Candidatos con mecanismo y sitio que requieren contraste SCN5A/6LQA, CACNA1C/8WE8, GABRA1/9EQG, PTGS2/5IKR y PDE3A/7KWE. Casos sin entrada utilizable CHRNA4 y KV sin gen. Selección dirigida para cubrir poro, sitio alostérico, sitio de una enzima y ausencia de estructura o identidad. No se estima tasa de adjudicación del panel.

Dos lecturas independientes, con actas separadas. Para cada fila se requiere una fuente primaria humana o funcional sobre reacción y mecanismo, más el depósito y su artículo sobre el sitio ocupado por la molécula que define la caja. Se contrasta especie, subunidad, conformación y ligando. A = mecanismo adverso respaldado y el sitio de la caja corresponde al mecanismo. B = correspondencia plausible con una brecha identificada. C = evidencia de un sitio diferente o entidad incorrecta. U = identidad, estructura o fuente insuficiente. Sólo A/A permite recomendar true, B y C mantienen false, y sin estructura se conserva el campo ausente. Un desacuerdo se publica como tal y requiere resolución antes de adjudicar. No se infiere potencia, agonismo ni riesgo clínico de un score. Potencia estadística no aplicable a la adjudicación dirigida.

## D-08 · Controles de cobertura SMARTS

Antes y después, sobre el mismo SMILES y con RDKit del producto. Candidato de laboratorio, cargado únicamente en memoria. Para tiol se compara la rama alifática neutra con `[C;!$(C=O)]-[SX1-]` y la aromática con `[c]-[SX1-]`, conservando las exclusiones de los patrones neutros aplicables. Para hidroxamato se compara `[CX3](=[OX1])-[NX3]-[OX1-]`. Para sulfonamida primaria se compara `[SX4](=[OX1])(=[OX1])-[NX2-;H1]` si RDKit asigna X2 al nitrógeno del control. Se registra desacuerdo de valencia como fallo del candidato. Las ramas neutras del producto quedan como control de conservación.

Positivos dirigidos (neutral/anión): metanosulfonamida `CS(=O)(=O)N` / `CS(=O)(=O)[NH-]`, bencenosulfonamida `O=S(=O)(N)c1ccccc1` / `O=S(=O)([NH-])c1ccccc1`, acetohidroxamato `CC(=O)NO` / `CC(=O)N[O-]`, benzohidroxamato `O=C(NO)c1ccccc1` / `O=C(N[O-])c1ccccc1`, etanotiol `CCS` / `CC[S-]`, tiofenol `Sc1ccccc1` / `[S-]c1ccccc1`.

Negativos para la alerta de estas tres familias: acetamida `CC(=O)N`, acetamidato `CC(=O)[NH-]`, acetato `CC(=O)[O-]`, metanosulfonato `CS(=O)(=O)[O-]`, sulfona `CS(=O)(=O)C`, sulfóxido `CS(=O)C`, tioéter `CSC`, disulfuro `CSSC`, tioacetato `CC(=O)[S-]`, fenolato `[O-]c1ccccc1`, sulfuro inorgánico `[S-2]`, N-metoxiacetamida `CC(=O)NOC`. Otros grupos UMS pueden activarse y se consignan.

Métrica por familia y conjunto, sensibilidad antes/después y especificidad frente a los negativos, con detalle por compuesto. GO de este control de cobertura sólo con todos los positivos y ningún negativo, más equivalencia del efecto sobre el orden M4 por inspección de dependencia de la fórmula. NO_GO si falla un control con entradas válidas. INCONCLUSIVE si falla el runtime o falta un dato del contrato. El conjunto dirigido no tiene potencia para estimar rendimiento poblacional ni coordinación real. No se ejecuta docking.

## D-01 · Relectura descriptiva

Se vuelven a contar las cinco muestras de los tres casos archivados (CDK2 apo, CDK2 con ligando y NET apo), semilla 42, Chai-1 0.6.1. Se informa por muestra el recuento de valores < 70 por lectura cuando los valores individuales estén disponibles. Referencia experimental y análisis discriminante se reservan a una cohorte independiente con correspondencia de residuos predefinida. Las muestras comparten secuencia y semilla de ejecución y no constituyen 15 proteínas independientes. Sin potencia confirmatoria ni criterio de equivalencia en esta relectura.
