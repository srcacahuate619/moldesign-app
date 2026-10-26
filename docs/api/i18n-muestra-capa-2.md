# Muestra de traducción — capa 2

Semilla `20261004`; 40 cadenas únicas seleccionadas de las cuatro rutas de la capa 2. Revisadas por sentido y terminología.

| # | Fuente | Línea | Español | Inglés |
|---:|---|---:|---|---|
| 1 | `services/dossier/bloques_protocolo.py` | 112 | La corrida no registró qué modelo de rescoring se usó. | This run did not record which rescoring model was used. |
| 2 | `services/cohort/dossier.py` | 251 | «Requiere revisión» significa que la batería no corrió entera: NO es una pose aprobada. Sólo «controles superados» autoriza llamar válida a una pose. | ‘Requires review’ means the full validation battery did not run: it is NOT an approved pose. Only an explicit ‘checks passed’ verdict allows a pose to be called valid. |
| 3 | `services/dossier/preparacion.py` | 588 | Versiones de la corrida | Run versions |
| 4 | `services/dossier/model.py` | 770 | Registros HETATM retirados del ensamblaje: aguas {n1}, metales {n2}, cofactores orgánicos {n3}, otras especies {n4}. A {n5} Å o menos de la caja: retirado {n6}; conservado {n7}. | HETATM records removed from the assembly: waters {n1}, metals {n2}, organic cofactors {n3}, other species {n4}. Within {n5} Å of the box: removed {n6}; retained {n7}. |
| 5 | `services/dossier/model.py` | 1151 | Origen del receptor | Receptor source |
| 6 | `services/dossier/model.py` | 586 | pH de protonación del ligando | ligand protonation pH |
| 7 | `services/dossier/model.py` | 1396 | Motor y versión | Engine and version |
| 8 | `services/dossier/bloques_protocolo.py` | 260 | No se resolvió el perfil. | The profile could not be resolved. |
| 9 | `services/dossier/preparacion.py` | 508 | El receptor que se entregaría no contiene especies que estaban en el sitio. Hay que decidir sobre ellas antes de cualquier cálculo posterior. | The receptor to be transferred does not contain species that were in the site. Decide how to handle them before any later calculation. |
| 10 | `services/dossier/preparacion.py` | 372 | Tautómero del ligando | Ligand tautomer |
| 11 | `services/dossier/preparacion.py` | 215 | La corrida no registró qué cadenas laterales incompletas del cristal se truncaron: su receta es anterior a la v7 o el receptor se congeló antes. | This run did not record which incomplete crystal side chains were truncated: its recipe predates v7 or the receptor was frozen earlier. |
| 12 | `services/cohort/dossier.py` | 461 | No garantiza reproducibilidad bit a bit: eso depende de la versión del motor y del hardware. | Bitwise reproducibility is not guaranteed; it depends on the engine version and hardware. |
| 13 | `services/dossier/model.py` | 1296 | Versiones de preparación | Preparation versions |
| 14 | `services/cohort/dossier.py` | 498 | `rows.csv` — una línea por fila de trabajo. | `rows.csv` — one line per work row. |
| 15 | `services/dossier/model.py` | 1505 | {n1} de {n2} poses | {n1} of {n2} poses |
| 16 | `services/dossier/model.py` | 1063 | Esquema del dossier | Dossier schema |
| 17 | `services/dossier/bloques_protocolo.py` | 391 | BENCHMARK EN REVISIÓN | BENCHMARK UNDER REVIEW |
| 18 | `services/dossier/bloques_protocolo.py` | 401 | Faltó al menos un componente con peso distinto de cero en la fórmula del perfil. No se renormalizan pesos ni se sustituye un modelo por otro (§5). El caso de CA2/3DC3 es GNN-D: no existe productor de esa señal en producción —sólo aparece en los checkpoints de benchmark— y el §4.1 prohíbe sustituirla por CL-GNN. | At least one component with nonzero weight in the profile formula was missing. Weights are not renormalized, and one model is not substituted for another (§5). The CA2/3DC3 case uses GNN-D: no production component generates that signal—it appears only in benchmark checkpoints—and §4.1 prohibits substituting CL-GNN. |
| 19 | `services/cohort/dossier.py` | 380 | Ninguno de estos pasos recomienda un fármaco, un candidato clínico ni un compuesto seguro. Describen qué trabajo computacional queda justificado. | None of these steps recommends a drug, clinical candidate, or safe compound. They describe what computational work is justified. |
| 20 | `services/dossier/model.py` | 517 | La corrida no registró un hash de identidad con versión de RDKit. | This run did not record an identity hash with an RDKit version. |
| 21 | `services/dossier/bloques_protocolo.py` | 132 | La corrida no registro los pesos efectivos. | The run did not register the effective weights. |
| 22 | `services/dossier/model.py` | 535 | ABSTENCIÓN · {n1} | ABSTENTION · {n1} |
| 23 | `services/dossier/model.py` | 1158 | El caso no declaró ligando. | The case did not declare a ligand. |
| 24 | `services/dossier/model.py` | 529 | Método de completado geométrico | Geometric completion method |
| 25 | `services/dossier/bloques_protocolo.py` | 44 | Observación · afinidad AutoDock Vina | Observation · AutoDock Vina affinity |
| 26 | `services/dossier/model.py` | 1720 | Índice compuesto heredado (total_score) | Legacy composite index (total_score) |
| 27 | `services/dossier/model.py` | 516 | SHA-256 de identidad v2 | Identity v2 SHA-256 |
| 28 | `services/cohort/dossier.py` | 348 | Una métrica calculada sin cumplir sus condiciones no es una métrica aproximada: es un número que parece un resultado. | A metric calculated without meeting its conditions is not an approximate measure; it is a number that looks like a result. |
| 29 | `services/cohort/dossier.py` | 499 | `inputs/` — el archivo original tal como se subió, y el receptor preparado. | `inputs/` — the original uploaded file and the prepared receptor. |
| 30 | `services/dossier/model.py` | 1215 | La corrida no registró la huella de sus inputs; no se puede afirmar a qué hipótesis corresponde. | This run did not record its input fingerprint; it cannot be linked to a specific hypothesis. |
| 31 | `services/dossier/model.py` | 1235 | Política de heteroátomos declarada | Declared heteroatom policy |
| 32 | `services/dossier/bloques_protocolo.py` | 456 | La diana es metálica y este producto no tiene protocolo validado para ese metal. Se declara en vez de degradarse a M4 en silencio (§6.1). | The target contains a metal, and this product has no validated protocol for that metal. This is declared instead of silently falling back to M4 (§6.1). |
| 33 | `services/dossier/model.py` | 1072 | ¿Qué controles o referencias existen? | What controls or references are available? |
| 34 | `services/cohort/dossier.py` | 280 | Se imprimen las primeras {n1}. El paquete ZIP lleva `rows.csv` con todas. | The first {n1} are printed. The ZIP package includes all rows in `rows.csv`. |
| 35 | `services/dossier/model.py` | 478 | Validación del método peptídico | Peptide method validation |
| 36 | `services/dossier/model.py` | 615 | Menor carga formal entre alternativas y entrada; {n1} carece de pKa verificado. Población química no determinada. | Lowest formal charge among the alternatives and input; {n1} has no verified pKa. Chemical population is undetermined. |
| 37 | `services/dossier/preparacion.py` | 444 | structural_evidence (PoseBusters con hidrógenos reconstruidos desde el SMILES; condición MF-33-H-COR) | structural_evidence (PoseBusters with hydrogens reconstructed from SMILES; MF-33-H-COR condition) |
| 38 | `services/dossier/model.py` | 1121 | Disposición final del caso | Final case disposition |
| 39 | `services/dossier/preparacion.py` | 313 | Caja de trabajo | Search box |
| 40 | `services/dossier/model.py` | 1071 | ¿Qué justifica la elección del sistema? | What supports the choice of system? |
