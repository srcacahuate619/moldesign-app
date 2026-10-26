# REC-07-R1 — REC-07 con la cisteína catalítica dentro del receptor

**Estado:** preregistrado, **sin ejecutar**.
**Fecha de preregistro:** 2026-10-22.
**Nivel de madurez (doc. 49 §3):** E2, como REC-07. **No** promueve a producción.
**Origen:** SCI-B-022 (auditoría científica, Fase B), fase 1b del plan de arreglos
(`docs/102_FASE_1B_CORRECCIONES.md`).
**Corrige:** [`REC-07`](../REC-07/) (sellado; no se toca).

## 1. Qué se sabe ya (honestidad sobre el cegamiento)

Esta repetición **no es ciega**. Se conoce el resultado de REC-07 (contacto en las 15
corridas, distancias top-1 de 0,42 a 1,17 Å en `G_DB`, GO) y se conoce su defecto:

- el filtro de altloc de `run_rec07_grid_5tun.py` elige por residuo la variante mayoritaria
  **contando los átomos sin altloc**. En la Cys25 de 5TUN, N, C y O no tienen altloc y CA,
  CB y SG vienen en A y en B con ocupancia 0,50: gana el vacío (3 contra 3), y CA, CB y SG se
  descartan;
- Meeko (`-a`) descarta después el residuo incompleto. **El receptor sellado de REC-07
  (`eceefe6d…`) no contiene ningún átomo de la Cys25.** Lo comprobé sobre el fichero de
  trabajo original, con ese mismo SHA-256;
- el «contacto a 0,42 Å» de REC-07 es, por tanto, un ligando ocupando el hueco de la
  cisteína. G4 y G5 comparaban la proximidad a un punto cuyo residuo no existía.

El preparador de producción (`backend/services/docking/preparer.py`) no tiene este defecto:
conserva siempre los átomos sin altloc y elige entre variantes no vacías. El defecto es del
experimento, no del producto.

No se ha ejecutado ningún docking sobre el receptor corregido antes de este preregistro.

## 2. Qué cambia frente a REC-07, y nada más

1. **Altloc coherente**, con la regla de `preparer.py`: átomos sin altloc siempre; entre las
   variantes no vacías, la de mayor ocupación acumulada, con desempate en A; la elegida se
   normaliza a altloc vacío. En la Cys25 elige A, que es la convención que REC-07 ya
   declaraba en su §3 (`Cys25:SG` en (16.591, 140.606, 16.594)).
2. **Gate G0, nuevo:** el receptor acoplado contiene `Cys25:SG`, `His162:NE2` y
   `Asn182:ND2` a ≤ 0,01 Å de sus coordenadas del PDB (altloc A). Si no, el runner aborta y
   no acopla.
3. Las 15 corridas y las 3 de determinismo se lanzan en paralelo (10 hilos, cada corrida con
   `--cpu 1`). No cambia ningún resultado: cada corrida es independiente.

**Todo lo demás se importa del runner sellado** (`run_rec07_grid_5tun.py`, SHA-256 en el
manifiesto de REC-07): los tres brazos (`G_DB`, `G_MP`, `G_ADAPT`) con sus centros y
tamaños, las semillas {42, 43, 44, 45, 46}, `exhaustiveness = 32`, `num_modes = 9`, el
umbral de contacto de 5,0 Å, los 15 hotspots, la tríada, la geometría por brazo y la lectura
de poses. El ligando es **el mismo fichero** que acopló REC-07 (`E6C.pdbqt`, SHA-256
`e82cbe4e…`), copiado en `entrada/` y verificado por hash antes de usarlo. El PDB de 5TUN es
el de `data/target_library/03_protease/5TUN.pdb` (SHA-256 `f5187b04…`), copiado en
`entrada/`. La distancia se mide a la `Cys25:SG` **del receptor acoplado**.

## 3. Gates (los de REC-07, más G0)

| ID | Gate | Criterio |
|---|---|---|
| G0 | **Ancla en el receptor** | la tríada está en el receptor acoplado, a ≤ 0,01 Å del PDB |
| G1 | Contención | el grid recomendado contiene 15/15 hotspots y 3/3 de la tríada |
| G2 | Ancla | `d(centro, Cys25 SG)` no mayor que la de `G_DB` |
| G3 | Validez de docking | las 15 corridas: `rc = 0`, 1–9 modos, scores finitos, geometría parseable |
| G4 | Contacto catalítico | top-1 a ≤ 5,0 Å de `Cys25:SG` en ≥ 3 de 5 semillas, en el grid recomendado |
| G5 | No regresión | tasa de contacto no menor que `G_DB` y mediana no peor en más de 1,0 Å |
| G6 | Determinismo | semilla 42 repetida en los tres brazos: mismo top-1 y misma distancia |
| G7 | Sólo lectura | `curated_targets.json` y `.csv` conservan su SHA-256 |

**GO** = los ocho pasan. **NO_GO** = falla G4 o G5 con G0 y G3 superados: con la cisteína
presente, el grid no lleva a E64c al nucleófilo. **INCONCLUSIVE** = falla G0 o G3 (no hay
receptor o corridas válidas sobre las que decidir). La regla de selección del grid (§6 de
REC-07: entre los que cumplen G1 y G2, el de menor volumen) no se toca; G1 y G2 son
geométricos y salen igual que en REC-07.

## 4. Lo que se espera, y por qué se dice antes

La geometría de los brazos (G1, G2) no depende del receptor y debe repetir REC-07 al
milésimo. Lo único abierto es el docking. Con la cisteína presente, el ligando ya no puede
ocupar su hueco, así que las distancias de 0,4–1,2 Å de REC-07 **no pueden repetirse**: una
distancia top-1 por debajo de ~3 Å a un átomo del receptor indicaría un choque, no un
contacto. Se espera contacto a 3–5 Å si el grid lleva al sitio, y no contacto si REC-07
dependía del hueco. Las dos salidas se publican.

## 5. Prohibiciones

- No se tocan los artefactos de REC-07 ni el catálogo.
- No se exploran otros paddings, centros, ligandos, exhaustividades ni semillas.
- No se cambia el umbral de 5,0 Å ni la regla de selección después de ver resultados.
- Vina es docking no covalente; E64c es covalente: el criterio sigue siendo contacto, no
  enlace. No se afirma exactitud de pose (5TUN es APO).

## 6. Artefactos

```text
scripts/artifacts_science/REC-07-R1/
  PREREGISTRO.md
  entrada/5TUN.pdb, entrada/E6C.pdbqt
  5TUN_filtrado.pdb, 5TUN_receptor.pdbqt   el receptor que se acopló
  manifest.json, metrics.json, per_complex.jsonl (15), failures.jsonl, README.md
```

Ejecutor: `scripts/run_rec07r1_grid_5tun.py --workers 10`. Pruebas del filtro y del aborto:
`scripts/tests/test_rec07r1_receptor.py`.
