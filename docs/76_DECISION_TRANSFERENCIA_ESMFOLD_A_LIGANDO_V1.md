# ADR científico: transferencia de ESMFold a un ligando acoplable

**Estado:** decision aceptada; implementacion contractual integrada, golden positivo y validacion cientifica pendientes
**Fecha:** septiembre de 2026  
**Afecta:** sidecar ESMFold, preparación Meeko, procedencia peptídica y dossier  
**Documento marco:** `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md`  

---

## 1. Decisión

MolDesign no completará el PDB de ESMFold y después intentará inferir desde sus
distancias qué molécula representa. La fuente de verdad química seguirá siendo:

- el grafo sanitizado del SMILES entregado por el investigador; o
- para una entrada FASTA, un grafo canónico construido de manera determinista
  para una cadena lineal de aminoácidos L estándar y terminales declarados.

ESMFold aporta **coordenadas y confianza de plegamiento**, no identidad química,
conectividad, órdenes de enlace, protonación ni estado de los terminales.

El protocolo V1 transferirá al grafo químico las coordenadas de los átomos que
ESMFold sí predice. Los átomos químicos ausentes, incluido el oxígeno terminal
equivalente a OXT, se colocarán mediante completado geométrico restringido sobre
ese mismo grafo. El ligando resultante se entregará a Meeko como SDF/MOL con
enlaces explícitos; no como un PDB al que RDKit deba adivinarle los enlaces.

---

## 2. Por qué se rechaza “añadir OXT al PDB” como solución principal

Añadir una línea OXT resolvería únicamente el ejemplo de un péptido lineal con
carboxilo C-terminal libre. No resolvería de forma general:

- estado protonado frente a carboxilato;
- amidación o modificación terminal;
- péptidos cíclicos o ramificados;
- residuos no canónicos;
- estereoquímica D/L;
- órdenes de enlace y aromaticidad de cadenas laterales;
- correspondencia exacta con la molécula solicitada.

La química no debe reconstruirse por proximidad porque dos grafos diferentes
pueden producir geometrías parecidas y porque una geometría incompleta puede
forzar valencias imposibles. El PDB de ESMFold es evidencia geométrica; el
SMILES/FASTA normalizado es identidad molecular.

---

## 3. Alcance de V1

El camino positivo `PEPTIDE_ESMFOLD_VINA_V1` sólo acepta:

- péptidos lineales;
- aminoácidos proteinogénicos estándar;
- serie L, con glicina aquiral;
- estereoquímica declarada y compatible;
- terminales que el constructor químico V1 pueda representar explícitamente;
- correspondencia uno a uno entre la secuencia extraída y el grafo de entrada.

Quedan fuera de V1 y producen abstención antes de Vina:

```text
D_PEPTIDE_UNSUPPORTED
NONCANONICAL_RESIDUE_UNSUPPORTED
CYCLIC_OR_BRANCHED_PEPTIDE_UNSUPPORTED
TERMINAL_MODIFICATION_UNSUPPORTED
AMBIGUOUS_STEREOCHEMISTRY
ATOM_MAPPING_INCOMPLETE
CHEMICAL_IDENTITY_MISMATCH
```

No se linealiza, neutraliza, amidiza ni sustituye ningún residuo en silencio.

---

## 4. Protocolo de transferencia

### 4.1. Construcción del grafo de referencia

1. Sanitizar el SMILES original y conservar su SMILES isomérico canónico,
   cargas formales y hash.
2. Extraer secuencia, orden N→C y serie L/D con `secuencia.py`.
3. Construir un péptido de referencia desde esa secuencia con información de
   residuo y nombres de átomo estándar.
4. Demostrar isomorfismo con quiralidad entre el grafo de referencia y el grafo
   del SMILES original.
5. Obtener una correspondencia explícita:

   ```text
   (residue_index, atom_name) -> input_atom_index
   ```

Para FASTA, el grafo construido pasa a ser el grafo de entrada y sus terminales
se registran como decisión del protocolo. El usuario debe poder ver esa
decisión antes de interpretar el resultado.

Si existen varias correspondencias químicamente equivalentes, se elige de
forma determinista y se registra. Si la ambigüedad cambia estereoquímica,
terminales o identidad, el pipeline se abstiene.

### 4.2. Coordenadas de ESMFold

1. Leer el PDB producido por `model.output_to_pdb`; no reimplementar atom14 o
   atom37.
2. Indexar sus átomos por cadena, posición de residuo y nombre de átomo.
3. Copiar únicamente coordenadas con correspondencia inequívoca al conformero
   del grafo químico.
4. Conservar pLDDT por residuo y promedio como señales independientes.
5. No inferir enlaces desde distancias del PDB.

### 4.3. Átomos ausentes y OXT

Los átomos presentes en el grafo químico pero ausentes en ESMFold se completan
de forma determinista:

1. generar coordenadas iniciales para el grafo completo;
2. fijar o restringir fuertemente los átomos transferidos desde ESMFold;
3. optimizar sólo los átomos ausentes y, como máximo, su vecindad inmediata;
4. preservar enlaces, cargas, quiralidad y geometría peptídica del grafo;
5. volver a comparar identidad química tras la optimización.

Para el C-terminal libre, el segundo oxígeno se coloca como parte del grupo
carboxilo/carboxilato que declara el grafo, no porque una etiqueta PDB llamada
OXT sea obligatoria. `OXT` puede añadirse al export PDB para interoperabilidad,
pero no define la química.

La primera implementación puede usar embedding/optimización restringida de
RDKit. Si no consigue una geometría válida y reproducible, se abstiene; no cae
a enlazado por proximidad.

### 4.4. Entrega a Meeko

El ligando completo se serializa como SDF o MOL con:

- conectividad y órdenes de enlace explícitos;
- conformero transferido/completado;
- estereoquímica;
- cargas formales;
- SMILES isomérico y hash originales como propiedades;
- mapa de átomos y procedencia de coordenadas.

Meeko consume ese mol o archivo soportado. No recibe el PDB incompleto de
ESMFold mediante `MolFromPDBFile`, y no intenta reconstruir enlaces a partir de
distancias.

---

## 5. Validaciones obligatorias antes de Vina

El docking sólo comienza si se cumplen todas:

1. mismo número de átomos pesados que el grafo químico esperado;
2. isomorfismo con quiralidad respecto al input;
3. ninguna valencia inválida;
4. una sola molécula conectada, salvo contraiones declarados y tratados por una
   política explícita;
5. todos los átomos requeridos tienen coordenadas finitas;
6. enlaces peptídicos y anillos conservados;
7. terminales coinciden con el input;
8. ausencia de choques intramoleculares graves introducidos por el completado;
9. preparación Meeko exitosa y trazable;
10. hash del grafo antes y después compatible con la transformación permitida.

Si falla una validación:

```text
origen = folded_structure_only
vina_affinity_kcal_mol = null
scientific_status = NOT_EVALUATED_LIGAND_RECONSTRUCTION
```

La estructura plegada y su pLDDT se conservan como evidencia válida.

---

## 6. Procedencia por átomo

El manifiesto del ligando acoplable debe indicar al menos:

```text
chemical_graph_source       smiles | fasta_constructed
coordinate_source           esmfold
coordinates_transferred     N
coordinates_completed       N
completed_atom_names        [OXT, ...]
completion_method           rdkit_constrained_v1
mapping_version             peptide_atom_map_v1
input_isomeric_smiles
output_isomeric_smiles
input_graph_hash
output_graph_hash
fold_plddt
esmfold_model_hash
```

Esto permite distinguir una coordenada predicha por ESMFold de una coordenada
añadida para completar la química.

---

## 7. Goldens

El golden existente `peptide_con_sidecar` no se reemplaza. Documenta un caso
real que llega correctamente a:

```text
origen = folded_structure_only
vina_affinity_kcal_mol = null
```

Debe conservarse como golden de abstención y como prueba de que nunca vuelve la
afinidad fabricada de `-4.0`.

Cuando se implemente este ADR se añade un segundo golden positivo:

```text
peptide_transferido_y_acoplado_v1
```

Debe demostrar, con tri-alanina y al menos un péptido más largo:

- atom count completo;
- OXT o terminal equivalente según el grafo;
- identidad isomérica conservada;
- una única molécula conectada;
- Meeko exitoso;
- Vina ejecutado realmente;
- afinidad literal conservada;
- pLDDT separado de afinidad;
- procedencia de átomos completados;
- mismo resultado contractual en backend de desarrollo y embebido.

El golden positivo no borra el negativo porque representan dos estados
distintos que el dossier debe explicar.

---

## 8. Dossier y producto mientras V1 no esté implementado

El dossier actual debe documentar honestamente:

- ESMFold cargó y produjo una estructura;
- pLDDT y tamaño de la estructura;
- la conversión a ligando acoplable no se completó;
- Vina no produjo afinidad;
- la corrida se abstuvo en la frontera estructura→ligando.

La interfaz no debe llamar a este estado “docking peptídico completado”. La
formulación correcta es “estructura peptídica generada; docking no evaluado”.

Esta abstención no bloquea las pruebas de dossier ni del runtime embebido: es un
resultado científico válido y debe viajar correctamente por ambas superficies.

---

## 9. Gates de aceptación

`PEPTIDE_ESMFOLD_VINA_V1` sólo se considera completo cuando:

1. los casos admitidos y rechazados están definidos por contrato;
2. el mapeo átomo-residuo es determinista;
3. la química del input sobrevive al traspaso;
4. OXT/terminales se completan desde el grafo, no por proximidad;
5. Meeko recibe un formato con enlaces explícitos;
6. no existe ningún fallback que fabrique afinidad;
7. el golden de abstención y el golden positivo pasan;
8. el runtime embebido reproduce ambos;
9. una cohorte peptídica posterior mide validez de poses y repetibilidad antes
   de elevar el estado científico del protocolo.

---

## 9.1 Estado medido de la implementacion

La frontera quimica V1 ya esta implementada y cubierta por pruebas unitarias:

- el grafo del SMILES es la autoridad y las coordenadas de ESMFold se transfieren
  sin inferir enlaces por proximidad;
- los estados rechazados producen una abstencion trazable;
- el SDF entregado a Meeko conserva conectividad, estereoquimica y terminales;
- la afinidad literal de Vina, cuando existe, permanece separada del pLDDT;
- el manifiesto viaja por el sidecar, el servicio, el dispatcher y el dossier.

El golden `peptide_con_sidecar` sigue siendo el caso de abstencion. Todavia no
existe en el repositorio un golden positivo que demuestre una corrida real de
ESMFold + Meeko + Vina ni una cohorte que valide poses y repetibilidad. Por ello
el estado cientifico del camino sigue siendo `EXPERIMENTAL`; no debe
presentarse como un docking peptidico validado hasta completar esos dos gates.
## 10. Consecuencia

ESMFold funciona como generador estructural en la máquina medida. Lo que falta
no es reparar el plegamiento, sino construir una frontera química explícita y
auditable entre su PDB y el ligando que consume Vina.

Elegir el grafo del usuario como fuente de verdad hace esa frontera compatible
con la identidad de MolDesign: ninguna coordenada útil justifica cambiar o
adivinar silenciosamente la molécula evaluada.
