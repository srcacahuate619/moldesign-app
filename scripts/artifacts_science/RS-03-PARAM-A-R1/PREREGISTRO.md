# RS-03-PARAM-A-R1 — preregistro (2026-10-22, antes de cualquier cálculo)

**Origen:** SCI-B-155 y SCI-B-156 (Fase B de la auditoría científica, fase 1b). RS-03-PARAM-A
declaró «energía finita + serializable 100 %» y «mapeo biyectivo + atom_order_hash», pero su
runner sólo construye el `System` (no calcula energía ni serializa) y el `atom_order_hash` es el
hash de la lista de símbolos y cargas formales, que no prueba una correspondencia átomo a átomo.
RS-03-PARAM-A está sellado y no se toca: esto es una medida nueva.

## Qué se mide

Para cada uno de los 116 ligandos de train de RS-03-PARAM-A, reconstruido como él:
`Chem.SDMolSupplier(removeHs=False, sanitize=True)` → `Molecule.from_rdkit(allow_undefined_stereo=True)`
→ cargas NAGL `openff-gnn-am1bcc-1.0.0.pt` normalizadas a la carga formal igual que el original →
`ForceField("openff-2.2.1.offxml").create_openmm_system(..., charge_from_molecules=[mol])`.

- **SCI-B-155 (energía y serialización).** Energía potencial de punto único en la geometría del
  SDF, plataforma `Reference` de OpenMM, sin minimizar. Después `XmlSerializer.serialize` del
  `System`, `deserialize`, contexto nuevo con las mismas posiciones y la misma energía otra vez.
- **SCI-B-156 (correspondencia atómica).** Índice a índice entre la molécula RDKit y la de OpenFF:
  número atómico, carga formal, y el conjunto de enlaces (pares de índices con su orden). Si todo
  coincide, la identidad de índices es un isomorfismo de grafos con elementos y cargas, que es lo
  que «biyectivo» tendría que querer decir. Además, nº de partículas del `System` = nº de átomos.
- **Control negativo de 156**, por molécula: se intercambian dos átomos del mismo elemento con
  vecindarios distintos en la copia de OpenFF (`remap`); el comparador tiene que detectarlo. Y un
  intercambio de dos elementos distintos. Si una molécula no tiene un par elegible del primer
  tipo, se declara.

## Entorno

Contenedor `moldesign-science:latest` del servidor de laboratorio (el mismo de RS-03-PARAM-A):
Python 3.11.15, openff-toolkit 0.18.0, openmm 8.5.2, rdkit 2026.03.1, openff-interchange 0.5.2,
openff-nagl-models 2025.9.0. El original no registró las versiones del toolkit; sí el SHA del
modelo NAGL (`7981e7f5…`), que es una puerta.

## Puertas (fijadas antes de ejecutar)

| | Criterio |
|---|---|
| G0 entradas | 116/116 SDF con el mismo SHA-256 que `RS-03-PARAM-A/per_complex.jsonl`; SHA del modelo NAGL igual |
| G1 reproducción de cargas | máx \|q − q_sellada\| ≤ 1e-5 e en los 116 (el sello redondea a 6 decimales) |
| G2 energía finita | 116/116 energías finitas |
| G3 serialización | 116/116 con \|E_deserializado − E\| ≤ 1e-6 kJ/mol |
| G4 correspondencia | 116/116 con elementos, cargas formales y enlaces idénticos índice a índice, y partículas = átomos |
| G5 el comparador ve | 100 % de los controles negativos ejecutados detectados |

**Decisión.** GO si pasan todas. NO_GO si falla G2, G3 o G4 en algún ligando (se informa cuántos
y cuáles): la afirmación del sello no se sostiene para ellos. INCONCLUSIVE si fallan G0, G1 o G5:
no se estaría midiendo lo mismo que el original o el comparador no ve.

**No dice:** si la energía es buena ni si Sage es adecuado para estos ligandos; nada sobre RS-03-PARAM-B.
Sin docking. Presupuesto: < 1 h de CPU en el servidor (4 núcleos).
