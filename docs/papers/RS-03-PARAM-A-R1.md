---
titulo: "La parametrización de RS-03-PARAM-A no era biyectiva en todos los ligandos: 1nw5 tiene una partícula de más"
entradilla: "RS-03-PARAM-A declaró energía finita, serialización al 100 % y mapeo biyectivo, pero no calculó la energía y su hash de símbolos no probaba la correspondencia. Medido: se sostiene en 115 de 116; en 1nw5 OpenFF añade un hidrógeno implícito y el sistema tiene 52 partículas para 51 átomos. NO_GO."
---

**NO_GO.** La afirmación de RS-03-PARAM-A («energía finita + serializable 100 %», «mapeo biyectivo») no
se sostiene para los 116 ligandos: falla en 1nw5. En los otros 115 sí se sostiene. RS-03-PARAM-A está
sellado y no cambia; esto es una medida nueva, preregistrada antes de calcular.

## Por qué se repitió

La auditoría científica (SCI-B-155 y SCI-B-156) encontró dos huecos en RS-03-PARAM-A. Su runner sólo
construía el `System` de OpenMM: nunca calculó una energía ni serializó nada, así que «energía finita y
serializable» no estaba medido. Y el `atom_order_hash` que respaldaba el «mapeo biyectivo» era el hash de
la lista de símbolos y cargas formales, que no prueba una correspondencia átomo a átomo.

## Qué se midió

Cada ligando se reconstruyó como en RS-03-PARAM-A (RDKit → `Molecule.from_rdkit` → cargas NAGL
`openff-gnn-am1bcc-1.0.0.pt` → OpenFF 2.2.1), en el mismo contenedor del servidor de laboratorio. Luego:
energía de punto único en la geometría del SDF (OpenMM, plataforma `Reference`, sin minimizar),
serialización y deserialización del `System` con la energía repetida, y una comparación índice a índice
de elementos, cargas formales y enlaces. Un control negativo por molécula intercambia dos átomos para
comprobar que el comparador lo ve.

## Qué pasó

| Puerta | Resultado |
|---|---|
| G0 entradas | 115/115 SDF con el SHA sellado; modelo NAGL `7981e7f5…` |
| G1 cargas | máx \|q − q_sellada\| = 5,0·10⁻⁷ e |
| G2 energía finita | 115/115 (de −3665 a 7325 kJ/mol, geometría del cristal sin minimizar) |
| G3 serialización | \|ΔE\| = 0,0 kJ/mol en los 115 |
| G4 correspondencia | 84/115 con el criterio preregistrado; 115/115 en elementos, cargas formales y pares de átomos |
| G5 el comparador ve | 229/229 intercambios detectados (1bcd no tiene par del mismo elemento distinguible) |

**1nw5.** Su SDF tiene 51 átomos; el azufre 7, un tiol, lleva el hidrógeno implícito y
`Molecule.from_rdkit` lo añade como átomo 51. El `System` tiene 52 partículas y no se puede evaluar con
las 51 posiciones del SDF. El propio sello de RS-03-PARAM-A registraba 51 átomos, 52 cargas y 52
partículas, y aun así declaraba el mapeo biyectivo: el hash miraba 51 símbolos.

**Los 31 que fallan G4 sin ser 1nw5** tienen exactamente los mismos pares de átomos; sólo difiere la
etiqueta del orden de enlace en los anillos aromáticos (RDKit 1,5; OpenFF los guarda kekulizados). Es una
convención del comparador, no un mapeo equivocado. Es un diagnóstico posterior, declarado, y no cambia la
decisión.

## Qué dice y qué no

- **Dice:** en 115 de 116 ligandos la parametrización es finita, serializable y conserva elementos,
  cargas y conectividad; en 1nw5 no se puede calcular con la geometría de su SDF.
- **No dice** nada de la calidad de esas energías ni de si OpenFF 2.2.1 (Sage) es adecuado para estos
  ligandos, ni de RS-03-PARAM-B (que, según la entrega de Sol, también deja 1nw5 fuera; no se verificó aquí).

Datos: `scripts/artifacts_science/RS-03-PARAM-A-R1/` (`PREREGISTRO.md`, `LECTURA.md`, `metrics.json`,
`diagnostico_1nw5.json`, `diagnostico_aromaticidad.json`).
