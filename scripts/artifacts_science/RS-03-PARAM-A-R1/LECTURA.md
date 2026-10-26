# RS-03-PARAM-A-R1 — lectura

**Decisión preregistrada: NO_GO.** Falla G4 (correspondencia) y, por el mismo ligando, el
recuento completo de G0–G3: **1nw5 no tiene correspondencia uno a uno.** Su SDF tiene 51 átomos;
el azufre 7, un tiol, lleva un hidrógeno implícito, y `Molecule.from_rdkit` lo añade como átomo
51. El `System` tiene 52 partículas y no se puede evaluar con las 51 posiciones del SDF. El
propio sello de RS-03-PARAM-A lo registraba (`n_atoms` 51, 52 cargas, 52 partículas) y aun así
declaró «mapeo biyectivo» en los 116: el `atom_order_hash` miraba 51 símbolos.

## Los otros 115

| Puerta | Resultado en los 115 |
|---|---|
| G0 entradas | 115/115 SDF con el SHA sellado; modelo NAGL `7981e7f5…` |
| G1 cargas | máx \|q − q_sellada\| = 5.0e-7 e |
| G2 energía | 115/115 finitas (de −3665 a 7325 kJ/mol, geometría del cristal sin minimizar) |
| G3 serialización | \|ΔE\| = 0.0 kJ/mol en los 115 |
| G4 correspondencia | 84/115 con el criterio preregistrado; 115/115 en elementos, cargas formales y pares de átomos |
| G5 controles | 229/229 intercambios detectados (1bcd no tiene par del mismo elemento distinguible) |

**Lo que el criterio preregistrado no previó** (diagnóstico posterior, declarado, que no cambia la
decisión): los 31 ligandos que fallan G4 sin ser 1nw5 tienen exactamente los mismos pares de
átomos; sólo difiere la etiqueta del orden de enlace en los anillos aromáticos (RDKit 1.5;
OpenFF los guarda kekulizados: 126 pasan a simple y 52 a doble). Es una convención del
comparador, no un mapeo equivocado. `diagnostico_aromaticidad.json` y `diagnostico_1nw5.json`.

## Qué dice para SCI-B-155 y SCI-B-156

- **155:** «energía finita + serializable 100 %» no se había calculado. Medido: se sostiene en 115
  de 116; en 1nw5 no se puede calcular con la geometría del SDF.
- **156:** el hash de símbolos no probaba la biyección, y de hecho no la había en 1nw5. En los
  otros 115 la identidad de índices conserva elementos, cargas y conectividad.

**No dice** nada sobre la calidad de las energías ni sobre RS-03-PARAM-B (que también deja 1nw5
fuera, según la entrega de Sol).
