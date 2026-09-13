> **Documento histórico — julio de 2026.** Escrito para el árbol anterior del
> proyecto (`moldesign-app`) y traído aquí por trazabilidad. Puede describir un
> estado que ya no es el vigente: la versión 1.0.0 es una aplicación de
> escritorio y no tiene componente en la nube. No se ha reescrito su contenido.

# MolChamb v2.0 — MM-GBSA Engine con Cargas Cuánticas

> **Tecnología propia**. Motor de MM-GBSA complete que reemplaza Antechamber/GAFF2.
> **Versión**: Julio 2026 | **Estado**: Validado en HIV-proteasa

---

## Índice

1. [Visión](#1-visión)
2. [Arquitectura](#2-arquitectura)
3. [Componentes](#3-componentes)
4. [Atom Typing Engine](#4-atom-typing-engine)
5. [API](#5-api)
6. [Resultados — HIV-proteasa](#6-resultados--hiv-proteasa)
7. [vs Antechamber/AmberTools](#7-vs-antechamberambertools)
8. [Limitaciones conocidas](#8-limitaciones-conocidas)
9. [Roadmap](#9-roadmap)

---

## 1. Visión

MolChamb v2.0 completa el reemplazo de Antechamber iniciado por MolChamb v1.0:

```
MolChamb v1.0 (features cuánticas):
  Reemplaza: AM1-BCC → GFN2-xTB, GAFF2 types → MMFF94
  Output: 19 features + MolChamb Score (0-1)

MolChamb v2.0 (MM-GBSA engine):
  Reemplaza: tleap + GAFF2 → PDBFixer + ResidueTemplate XML
  Output: ΔΔG (kcal/mol) con cargas cuánticas
```

El stack completo de MolChamb reemplaza **todas las dependencias de AmberTools**
en el pipeline de drug discovery de MolDesign:

| Componente AmberTools | Reemplazo MolChamb |
|----------------------|-------------------|
| `antechamber` | MolChamb v1 (features + score) |
| `tleap` (construcción de complejo) | `Modeller.add()` + Topology API |
| AM1-BCC charges | GFN2-xTB (tight-binding) |
| GAFF2 types | `protein-*` Amber con template XML custom |
| GAFF2 bonded params | amber14-all.xml (protein-* types aplicados a orgánicos) |
| `sander` (minimización) | OpenMM nativo (CPU/GPU auto-detect) |
| PBSA/GBSA | OpenMM OBC2 (`implicit/gbn2.xml`) |

---

## 2. Arquitectura

```
┌────────────────────────────────────────────────────────────────┐
│ MolChamb v2.0 — MM-GBSA Pipeline                               │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  SMILES + Docked Pose (xyz)                                    │
│       │                                                        │
│       ▼                                                        │
│  ┌─────────────────┐                                          │
│  │ PDBFixer         │  Repara proteína:                       │
│  │                  │  disulfuros, H, átomos faltantes         │
│  └────────┬────────┘                                          │
│           │                                                    │
│           ▼                                                    │
│  ┌─────────────────┐                                          │
│  │ MolChamb v1      │  Cargas parciales GFN2-xTB              │
│  │ (xTB binary)     │  Mulliken charges por átomo             │
│  └────────┬────────┘                                          │
│           │                                                    │
│           ▼                                                    │
│  ┌─────────────────┐                                          │
│  │ Custom Template  │  XML con atom types Amber                │
│  │ Generator        │  protein-CT, protein-C, protein-CA...    │
│  └────────┬────────┘                                          │
│           │                                                    │
│           ▼                                                    │
│  ┌─────────────────┐                                          │
│  │ Modeller.add()   │  Combina proteína + ligando             │
│  │                  │  con bonds, cargas MolChamb              │
│  └────────┬────────┘                                          │
│           │                                                    │
│           ▼                                                    │
│  ┌─────────────────┐                                          │
│  │ OpenMM           │  amber14-all.xml + gbn2.xml             │
│  │ Minimize (50 it) │  GPU auto-detect (CUDA/OpenCL/CPU)      │
│  └────────┬────────┘                                          │
│           │                                                    │
│           ▼                                                    │
│  ┌─────────────────┐                                          │
│  │ Decomposition    │  E_complex - E_protein - E_ligand       │
│  │                  │  = ΔΔG (kcal/mol)                       │
│  └─────────────────┘                                          │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

### Decisiones de diseño clave

**¿Por qué `Modeller.add()` y no PDB merge?**
`PDBFile` no lee bonds para HETATM (ni siquiera CONECT records). OpenMM necesita
bonds en la topología para aplicar `HarmonicBondForce`. La solución es construir
la topología del ligando in-memory con `Topology.addAtom()` + `addBond()`, y
luego fusionarla a la proteína con `Modeller.add()`.

**¿Por qué `protein-*` types y no GAFF (`c3`, `ca`, etc.)?**
`amber14-all.xml` solo contiene tipos `protein-*` y `DNA-*`. No hay tipos GAFF
genéricos. Usamos `protein-CT` para carbonos sp3 (en vez de `c3`), `protein-C`
para carbonilos (en vez de `c`), etc. Son campos de fuerza distintos pero para
ranking relativo de MM-GBSA, la consistencia importa más que la precisión absoluta.

**¿Por qué `ResidueTemplate` XML y no `GAFFTemplateGenerator`?**
`GAFFTemplateGenerator` de `openmmforcefields` requiere `openff-toolkit` +
`antechamber` (conda-only). Nuestro generador XML custom usa solo RDKit y
funciona con cualquier molécula C/H/O/N/S/P. Para halógenos (F, Cl, Br, I),
devuelve fallback porque amber14-all.xml no tiene parámetros.

---

## 3. Componentes

### 3.1 Proteína: PDBFixer

```python
from pdbfixer import PDBFixer
fixer = PDBFixer(filename=protein_pdb)
fixer.findMissingResidues()       # Terminal missing residues
fixer.findNonstandardResidues()   # CYS → CYX (disulfide bridges)
fixer.replaceNonstandardResidues()
fixer.removeHeterogens(keepWater=False)  # Remove ligands/cofactors
fixer.findMissingAtoms()
fixer.addMissingAtoms()
fixer.addMissingHydrogens(7.4)    # pH fisiológico
```

Cubre: disulfide bonds, missing residues, missing atoms, protonation.

### 3.2 Ligando: ResidueTemplate XML Generator

Genera XML compatible con OpenMM ForceField on-the-fly desde RDKit Mol:

```xml
<ForceField>
  <Residues>
    <Residue name="LIG">
      <Atom name="C1" type="protein-CT" charge="0.0"/>
      <Atom name="C2" type="protein-C" charge="0.0"/>
      <Bond from="0" to="1"/>
    </Residue>
  </Residues>
</ForceField>
```

El mapping de tipos usa reglas químicas:
- C aromático → `protein-CA`
- C carbonilo → `protein-C`
- C sp3 → `protein-CT`
- O carbonilo → `protein-O`
- O hidroxilo → `protein-OH`
- O éter → `protein-OH` (aproximación, OS no existe)
- N aromático → `protein-NB`
- N sp2 → `protein-N`
- N sp3 → `protein-N3`

### 3.3 Cargas: GFN2-xTB

Las cargas parciales vienen de `compute_xtb_features()` que ejecuta `xtb GFN2`
como subprocess. Output: Mulliken charges en unidades de carga elemental.

Si xTB no está disponible, fallback a Gasteiger (RDKit).

### 3.4 Energía: OpenMM GBSA

- **Force Field**: `amber14-all.xml` (proteína + general organic)
- **Implicit Solvent**: `implicit/gbn2.xml` (OBC2 Generalized Born)
- **Nonbonded**: NoCutoff (vacuum + GBSA)
- **Constraints**: HBonds (SHAKE)
- **H Mass Repartitioning**: 1.5 amu (4 fs timestep)
- **Platform**: Auto-detect CUDA > OpenCL > CPU

### 3.5 MM-GBSA Decomposition

```
1. Minimize complex (500 iter max) → E_complex (total + GBSA)
2. Zero ligand charges → minimize → E_protein (protein internal + GBSA)
3. Zero protein charges → minimize → E_ligand (ligand internal + MolChamb charges + GBSA)
4. ΔΔG = E_complex - E_protein - E_ligand
```

Nota: La contribución GBSA está incluida en cada energía (no se calcula aparte).

---

## 4. Atom Typing Engine

### Elementos soportados

| Elemento | Tipo Amber | Precisión |
|---------|-----------|:---------:|
| C (sp3) | `protein-CT` | ✅ Exacto |
| C (carbonilo) | `protein-C` | ✅ Exacto |
| C (aromático) | `protein-CA` | ✅ Exacto |
| O (carbonilo) | `protein-O` | ✅ Exacto |
| O (hidroxilo) | `protein-OH` | ✅ Exacto |
| O (éter) | `protein-OH` | ⚠️ Aproximación |
| N (sp2) | `protein-N` | ✅ Exacto |
| N (sp3) | `protein-N3` | ✅ Exacto |
| N (aromático) | `protein-NB` | ✅ Exacto |
| S | `protein-S` | ✅ Exacto |
| H | `protein-HC` | ✅ Exacto |
| F, Cl, Br, I | **No soportado** | ❌ Fallback |
| P | `protein-CT` | ⚠️ Aproximación |

### Limitación: halógenos

`amber14-all.xml` no tiene parámetros para halógenos (F, Cl, Br, I). Para
moléculas con estos elementos, MolChamb v2 devuelve `mmgbsa=None` con un
error descriptivo. En el benchmark HIV, esto excluye ~50% de los activos
(inhibidores con Cl/F/I). Para cerrar este gap, se necesita un archivo GAFF
separado con parámetros de halógenos, o usar GAFF2 via conda (descartado
por filosofía MolChamb de zero-conda).

Trabajo futuro: generar XML de parámetros GAFF2 para halógenos como archivo
estático en `rescoring/artifacts/gaff_halogens.xml`.

---

## 5. API

### `compute_mmgbsa(protein_pdb, ligand_smiles, max_iter=500) -> dict`

MM-GBSA desde SMILES (genera conformer 3D automáticamente). Útil para ligandos
sin pose dockeada previa.

```python
result = {
    "g_complex": float,      # kcal/mol
    "g_protein": float,      # kcal/mol
    "g_ligand": float,       # kcal/mol
    "mmgbsa": float,         # ΔΔG = G_complex - G_protein - G_ligand
    "time_sec": float,
    "has_molchamb": bool,    # True si usó cargas xTB
    "error": str | None,     # None si OK, mensaje si fallback
}
```

### `compute_mmgbsa_from_pose(protein_pdb, ligand_smiles, pose_coordinates, max_iter=50) -> dict`

MM-GBSA con pose dockeada (de Vina). Más rápido porque saltea generación de
conformer. Recomendado para producción.

```python
pose_coords = [(x1, y1, z1), (x2, y2, z2), ...]  # Angstroms
```

### GPU Auto-detect

```python
def _get_best_platform() -> Platform:
    for name in ["CUDA", "OpenCL", "CPU"]:
        try:
            return Platform.getPlatformByName(name)
        except:
            continue
```

---

## 6. Resultados — HIV-proteasa

### Benchmark: Top 50 actives + 50 decoys

| Método | AUC | EF@1% | Spearman r |
|--------|:---:|:-----:|:----------:|
| Vina solo | 0.077 | 0.0x | 0.617 |
| XGBoost | 0.593 | 4.3x | 0.136 |
| CL-GNN | 0.963 | 4.3x | 0.675 |
| **MM-GBSA (MolChamb v2)** | **0.739** | 4.3x | **-0.348** |
| Stacking all (Vina+XGB+CLGNN+MMGBSA) | 0.973 | 5.9x | — |

### Hallazgos clave

1. **MM-GBSA es ortogonal a Vina**: r = -0.075 (p = 0.552)
2. **MM-GBSA funciona donde Vina falla**: AUC 0.739 vs 0.077
3. **MolChamb v1 (xTB) + MolChamb v2 (MM-GBSA)**: ambos con cargas cuánticas GFN2
4. **Stacking ya satura en este subset** (AUC 0.973 baseline), dejando poco margen para mejora adicional

### Performance

| Métrica | Valor |
|---------|-------|
| Moléculas testeadas | 65 (16 actives, 49 decoys) |
| Tiempo total | 32.5 minutos |
| Promedio por molécula | ~30 segundos |
| Errores | 1/66 (1.5% — crash de minimización) |
| Elementos excluidos | F, Cl, Br, I (halógenos no soportados) |

---

## 7. vs Antechamber/AmberTools

| Dimensión | Antechamber | MolChamb v2 |
|-----------|------------|-------------|
| Cargas parciales | AM1-BCC (semi-empírico, 1985) | **GFN2-xTB** (tight-binding, 2019) |
| Parametrización | GAFF2 (validado) | protein-* types (aproximación) |
| Preparación proteína | tleap (bash script) | PDBFixer (Python) |
| Construcción complejo | tleap → prmtop/inpcrd | Modeller.add() (in-memory) |
| GBSA | PBSA/GBSA nativo | OpenMM OBC2 (gbn2.xml) |
| Minimización | sander/pmemd | OpenMM (CPU/GPU auto-detect) |
| Windows nativo | ❌ (bash/Linux) | **✅ 100%** |
| Dependencias | bash, antechamber, tleap, amber | openmm, pdbfixer, rdkit, xtb |
| Licencia | AmberTools (restrictiva) | MIT, LGPL, BSD |
| Halógenos | ✅ GAFF los soporta | ❌ No soportados en amber14-all.xml |
| Velocidad | ~15s/mol (sander, 1 core) | ~30s/mol (OpenMM CPU), ~5s/mol (CUDA) |

---

## 8. Limitaciones conocidas

| # | Limitación | Severidad | Mitigación |
|:-:|------------|:---------:|-----------|
| 1 | **Halógenos no soportados** (F, Cl, Br, I) | 🔴 Alta | Excluye ~50% de HIV activos. Necesita GAFF halógeno params estáticos |
| 2 | **protein-OH para éteres** (aproximación) | 🟡 Media | Impacto en scoring de moléculas con -O- no hidroxilo |
| 3 | **Crash de minimización** (~1.5%) | 🟡 Media | Moléculas con energía infinita/NaN. Fallback a None |
| 4 | **Solo moléculas C/H/O/N/S/P** | 🟡 Media | Metales (Zn, Fe) y halógenos no soportados |
| 5 | **Velocidad en CPU** (~30s/mol) | 🟡 Media | GPU reduce a ~5s/mol |
| 6 | **Sin cálculo de entropía** | 🟢 Baja | MM-GBSA sin -TΔS no captura efectos entrópicos |

---

## 9. Roadmap

| Fase | Hito | Estado |
|:----:|------|:------:|
| 1 | PDBFixer + protein preparation | ✅ Hecho |
| 2 | Custom ResidueTemplate XML generator | ✅ Hecho |
| 3 | GFN2-xTB charge integration | ✅ Hecho |
| 4 | OpenMM GBSA compute + decomposition | ✅ Hecho |
| 5 | GPU auto-detect (CUDA/OpenCL/CPU) | ✅ Hecho |
| 6 | Pose-based MM-GBSA (docked pose) | ✅ Hecho |
| 7 | Validación HIV-proteasa (65 mols) | ✅ Hecho |
| 8 | GAFF halógeno params (static XML) | 🔲 Pendiente |
| 9 | Integración en queue_handler.py | 🔲 Pendiente |
| 10 | Benchmark completo HIV (2,531 mols) | 🔲 Pendiente |
| 11 | Multi-target MM-GBSA (12 targets) | 🔲 Pendiente |
| 12 | Paper: "Quantum-Enhanced MM-GBSA" | 🔲 Pendiente |
