"""
MolChamb v2.0 — Full MM-GBSA engine with custom residue templates.

Replaces openmmforcefields/GAFF in the MM-GBSA pipeline.
Architecture:
  1. PDBFixer → clean protein (disulfides, H, missing atoms)  
  2. RDKit → ligand 3D conformer
  3. MolChamb → GFN2-xTB partial charges
  4. Custom XML → Amber residue template for ligand
  5. OpenMM → amber14-all.xml + gbn2.xml → MM-GBSA
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

from rdkit import Chem, RDLogger

RDLogger.logger().setLevel(RDLogger.ERROR)

from openmm import Platform
from openmm import unit
from openmm.app import ForceField, Modeller, PDBFile, Simulation, NoCutoff, HBonds
from openmm import NonbondedForce, LangevinMiddleIntegrator
from openmm.vec3 import Vec3
from pdbfixer import PDBFixer

# MolChamb
_SCRIPTS_DIR = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
from compute_quantum_features import compute_xtb_features


# ══════════════════════════════════════════════════════════════════════
# Protein preparation
# ══════════════════════════════════════════════════════════════════════

def prepare_protein(protein_pdb: str, output_pdb: str, ph: float = 7.4) -> str:
    fixer = PDBFixer(filename=protein_pdb)
    fixer.findMissingResidues()
    fixer.findNonstandardResidues()
    fixer.replaceNonstandardResidues()
    fixer.removeHeterogens(keepWater=False)
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(ph)
    with open(output_pdb, "w") as f:
        PDBFile.writeFile(fixer.topology, fixer.positions, f)
    return output_pdb


# ══════════════════════════════════════════════════════════════════════
# Ligand custom residue template (XML for OpenMM ForceField)
# ══════════════════════════════════════════════════════════════════════

def _amber_atom_type(mol: Chem.Mol, atom) -> str:
    """Map RDKit atom to amber14-all.xml atom type (protein-* namespace)."""
    elem = atom.GetSymbol()
    i = atom.GetIdx()
    if elem == "C":
        is_carbonyl = any(
            n.GetSymbol() == "O"
            and mol.GetBondBetweenAtoms(i, n.GetIdx()).GetBondType() == Chem.BondType.DOUBLE
            for n in atom.GetNeighbors()
        )
        if atom.GetIsAromatic():
            return "protein-CA"
        elif is_carbonyl:
            return "protein-C"
        else:
            return "protein-CT"
    elif elem == "O":
        is_carbonyl = any(
            n.GetSymbol() == "C"
            and mol.GetBondBetweenAtoms(i, n.GetIdx()).GetBondType() == Chem.BondType.DOUBLE
            for n in atom.GetNeighbors()
        )
        if any(n.GetSymbol() == "H" for n in atom.GetNeighbors()):
            return "protein-OH"
        elif is_carbonyl:
            return "protein-O"
        else:
            return "protein-OH"  # ether = hydroxyl (closest protein type avail)
    elif elem == "N":
        if atom.GetIsAromatic():
            return "protein-NB"
        elif atom.GetHybridization() == Chem.HybridizationType.SP2:
            return "protein-N"
        else:
            return "protein-N3"
    elif elem == "S":
        return "protein-S"
    elif elem == "H":
        return "protein-HC"
    else:
        # Halogens (F, Cl, Br, I) / P: no protein types exist, use CT as fallback
        return "protein-CT"


def _register_ligand_template(ff: ForceField, mol: Chem.Mol, name: str = "LIG"):
    """Register a custom Amber ResidueTemplate via XML temp file."""
    lines = [
        "<ForceField>",
        "  <Residues>",
        f'    <Residue name="{name}">',
    ]
    for atom in mol.GetAtoms():
        a_name = f"{atom.GetSymbol()}{atom.GetIdx() + 1}"
        a_type = _amber_atom_type(mol, atom)
        lines.append(f'      <Atom name="{a_name}" type="{a_type}" charge="0.0"/>')

    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        lines.append(f'      <Bond from="{i}" to="{j}"/>')

    lines.append("    </Residue>")
    lines.append("  </Residues>")
    lines.append("</ForceField>")

    xml = "\n".join(lines)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False) as f:
        f.write(xml)
        tmp = f.name
    try:
        ff.loadFile(tmp)
    finally:
        os.unlink(tmp)


# ══════════════════════════════════════════════════════════════════════
# Ligand 3D + charges
# ══════════════════════════════════════════════════════════════════════

def _parameterize_ligand(smiles: str) -> dict:
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError(f"Invalid SMILES: {smiles}")
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, randomSeed=42)
    AllChem.MMFFOptimizeMolecule(mol)

    charges = None
    try:
        xtb = compute_xtb_features(smiles)
        # FIX (Bug C): la clave correcta es "xtb_charges" (lista completa por
        # atomo, incl. H), expuesta por compute_quantum_features.py. Antes
        # buscaba "xtb_charges_mulliken" que nunca existio => caia siempre al
        # fallback Gasteiger y has_molchamb quedaba False.
        charges = xtb.get("xtb_charges", None)
    except Exception:
        pass
    if not charges:
        AllChem.ComputeGasteigerCharges(mol)
        charges = [float(a.GetProp("_GasteigerCharge")) for a in mol.GetAtoms()]

    return {"mol": mol, "charges": charges, "n_atoms": mol.GetNumAtoms()}


# ══════════════════════════════════════════════════════════════════════
# PDB helpers
# ══════════════════════════════════════════════════════════════════════

def _write_ligand_pdb(mol: Chem.Mol, out: str, start_serial: int = 1):
    conf = mol.GetConformer()
    with open(out, "w") as f:
        for i, atom in enumerate(mol.GetAtoms()):
            pos = conf.GetAtomPosition(i)
            name = f"{atom.GetSymbol()}{i + 1}"
            f.write(
                f"HETATM{start_serial + i:5d} {name:>4s} LIG L 999    "
                f"{pos.x:8.3f}{pos.y:8.3f}{pos.z:8.3f}"
                f"  1.00  0.00          {atom.GetSymbol():>2s}  \n"
            )
        for bond in mol.GetBonds():
            i = start_serial + bond.GetBeginAtomIdx()
            j = start_serial + bond.GetEndAtomIdx()
            f.write(f"CONECT{i:5d}{j:5d}\n")
        f.write("END\n")


def _merge_pdb(prot: str, lig: str, out: str):
    with open(out, "w") as f:
        with open(prot) as fp:
            for line in fp:
                if not line.startswith("END"):
                    f.write(line)
        f.write("TER\n")
        with open(lig) as fl:
            for line in fl:
                if line.startswith("HETATM"):
                    f.write(line)
        f.write("END\n")


def _find_ligand_atoms(topology) -> list[int]:
    standard = {
        "ALA", "ARG", "ASN", "ASP", "CYS", "CYX", "GLN", "GLU", "GLY",
        "HIS", "HID", "HIE", "HIP", "ILE", "LEU", "LYS", "MET", "PHE",
        "PRO", "SER", "THR", "TRP", "TYR", "VAL",
        "ASH", "GLH", "LYN", "CYM", "HOH", "WAT", "NA", "CL",
    }
    lig = []
    for i, a in enumerate(topology.atoms()):
        if a.residue.name not in standard:
            lig.append(i)
    return lig


def _override_charges(system, atom_ids: list[int], charges: list[float]):
    nb = None
    for f in system.getForces():
        if isinstance(f, NonbondedForce):
            nb = f
            break
    if nb is None:
        return
    for idx, chg in zip(atom_ids, charges):
        if idx >= system.getNumParticles():
            continue
        try:
            _, sigma, epsilon = nb.getParticleParameters(idx)
            nb.setParticleParameters(idx, chg * unit.elementary_charge, sigma, epsilon)
        except Exception:
            pass


def _compute_isolated(modeller, positions, ff, lig_ids, which, max_iter, charges=None):
    """FIX 2026-08-04: topología reducida (misma lógica que _compute_isolated_fast).
    Envuelve a la variante fast con platform CPU."""
    return _compute_isolated_fast(
        modeller, positions, ff, lig_ids, which, max_iter,
        Platform.getPlatformByName("CPU"), charges=charges,
    )


# ══════════════════════════════════════════════════════════════════════
# Main API
# ══════════════════════════════════════════════════════════════════════

def compute_mmgbsa(protein_pdb: str, ligand_smiles: str, max_iter: int = 500) -> dict:
    t0 = time.time()

    # 1. Prepare protein
    with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as f:
        prep_pdb = f.name
    prepare_protein(protein_pdb, prep_pdb)

    # 2. Ligand
    lig_data = _parameterize_ligand(ligand_smiles)
    lig_mol = lig_data["mol"]
    charges = lig_data["charges"]

    # 3. Build complex in memory (Modeller.add, not PDB merge)
    from openmm.app.topology import Topology
    from openmm.app.element import Element

    # Load prepared protein
    prot_pdb = PDBFile(prep_pdb)
    modeller = Modeller(prot_pdb.topology, prot_pdb.positions)

    # Build ligand topology with bonds
    lig_top = Topology()
    lig_chain = lig_top.addChain("L")
    lig_res = lig_top.addResidue("LIG", lig_chain)
    lig_atoms = []

    conf = lig_mol.GetConformer()
    lig_positions = []
    for i, atom in enumerate(lig_mol.GetAtoms()):
        elem = Element.getBySymbol(atom.GetSymbol())
        a = lig_top.addAtom(f"{atom.GetSymbol()}{i + 1}", elem, lig_res)
        lig_atoms.append(a)
        pos = conf.GetAtomPosition(i)
        lig_positions.append(Vec3(pos.x, pos.y, pos.z) * unit.angstrom)

    for bond in lig_mol.GetBonds():
        lig_top.addBond(lig_atoms[bond.GetBeginAtomIdx()], lig_atoms[bond.GetEndAtomIdx()])

    # Add ligand to complex
    modeller.add(lig_top, lig_positions)

    # 4. OpenMM system
    ff = ForceField("amber14-all.xml", "implicit/gbn2.xml")
    _register_ligand_template(ff, lig_mol, name="LIG")

    system = ff.createSystem(
        modeller.topology, nonbondedMethod=NoCutoff,
        constraints=HBonds, hydrogenMass=1.5 * unit.amu,
    )

    # 4. Override ligand charges
    lig_ids = _find_ligand_atoms(modeller.topology)
    has_molchamb = False
    if lig_ids and charges:
        atoms_list = list(modeller.topology.atoms())
        heavy_ids = [i for i in lig_ids if atoms_list[i].element.symbol != "H"]
        if len(charges) >= len(heavy_ids):
            _override_charges(system, heavy_ids, charges[:len(heavy_ids)])
            has_molchamb = True

    from services.chemistry.mmgbsa_integrity import validate_ligand_system
    try:
        validate_ligand_system(system, modeller.topology, lig_ids)
    except ValueError:
        try:
            os.unlink(prep_pdb)
        except OSError as exc:
            log.warning("cleanup_failed", stage="mmgbsa_integrity", error=str(exc))
        raise

    # 5. Minimize con verificación de convergencia
    integrator = LangevinMiddleIntegrator(300 * unit.kelvin, 1.0 / unit.picosecond, 0.002 * unit.picoseconds)
    sim = Simulation(modeller.topology, system, integrator, Platform.getPlatformByName("CPU"))
    sim.context.setPositions(modeller.positions)

    # Capturar energía inicial para verificar convergencia
    e0 = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
    sim.minimizeEnergy(maxIterations=max_iter)
    e_final = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
    energy_change = abs(e0 - e_final)

    # Si la energía cambió menos de 0.01 kcal/mol, la minimización no progresó
    # Posibles causas: estructura ya minimizada, topología incorrecta, o ligando no acoplado
    if energy_change < 0.01 and max_iter > 100:
        log.warning("mmgbsa_no_convergence", e0=round(e0, 2), e_final=round(e_final, 2))
        return {
            "mmgbsa": None,
            "energy_change": round(energy_change, 4),
            "time_sec": round(time.time() - t0, 2),
            "has_molchamb": False,
            "warning": "MM-GBSA no convergió — energía virtualmente sin cambio",
        }

    g_complex = sim.context.getState(getEnergy=True, getPositions=True).getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
    min_pos = sim.context.getState(getPositions=True).getPositions()

    g_protein = _compute_isolated(modeller, min_pos, ff, lig_ids, "protein", max_iter)
    g_ligand = _compute_isolated(modeller, min_pos, ff, lig_ids, "ligand", max_iter, charges)

    # Cleanup
    for f in [prep_pdb]:
        try:
            os.unlink(f)
        except OSError as e:
            log.warning("cleanup_failed", file=f, error=str(e))

    return {
        "g_complex": round(g_complex, 3),
        "g_protein": round(g_protein, 3),
        "g_ligand": round(g_ligand, 3),
        "mmgbsa": round(g_complex - g_protein - g_ligand, 3),
        "energy_change": round(energy_change, 4),
        "time_sec": round(time.time() - t0, 2),
        "has_molchamb": has_molchamb,
    }


# ══════════════════════════════════════════════════════════════════════
# GPU Auto-detect + Pose-based API
# ══════════════════════════════════════════════════════════════════════

def _get_best_platform() -> Platform:
    """Auto-detect best OpenMM platform: CUDA > OpenCL > CPU."""
    for name in ["CUDA", "OpenCL", "CPU"]:
        try:
            p = Platform.getPlatformByName(name)
            if name == "CUDA":
                print(f"  [MolChamb] Using GPU: {p.getPropertyValue('CudaDeviceName') or 'CUDA'}")
            return p
        except Exception:
            continue
    return Platform.getPlatformByName("CPU")


def compute_mmgbsa_from_pose(
    protein_pdb: str,
    ligand_smiles: str,
    pose_coordinates: list[tuple[float, float, float]],
    max_iter: int = 50,
    ligand_sdf_path: str | None = None,
) -> dict:
    """
    Compute MM-GBSA using a pre-docked ligand pose (from Vina, etc.).
    Much faster than SMILES-based because we skip conformer generation.

    Args:
        protein_pdb: Path to protein PDB file (raw, will be auto-prepared)
        ligand_smiles: SMILES of the ligand
        pose_coordinates: List of (x, y, z) tuples in Angstroms for each atom
        max_iter: Minimization iterations (50 = fast, 200 = accurate)
        ligand_sdf_path: (FIX 2026-08-04) SDF de la pose de Vina — fuente de
            la topología con coordenadas REALES. Si se provee, se usa su
            conformador para posiciones y se agregan H con addCoords=True
            (los H NO se ponen en la última posición — bug del NaN).

    Returns:
        dict with g_complex, g_protein, g_ligand, mmgbsa, time_sec, has_molchamb
    """
    t0 = time.time()
    platform = _get_best_platform()

    # 1. Prepare protein
    with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as f:
        prep_pdb = f.name
    try:
        prepare_protein(protein_pdb, prep_pdb)

        # 2. Ligand charges from MolChamb
        mol = Chem.MolFromSmiles(ligand_smiles)
        if mol is None:
            raise ValueError(f"Invalid SMILES: {ligand_smiles}")

        # ── FIX 2026-08-04 (NaN): si viene el SDF de la pose real, construir la
        # topología DESDE el SDF (que tiene el conformador 3D de Vina), agregando
        # H con coordenadas calculadas. Antes se hacía AddHs() SIN coordenadas y
        # los H extra caían todos en la última posición del pose → colapso estérico
        # → energía infinita → "Energy or force at minimization starting point is
        # infinite or NaN".
        mol_with_h = None
        if ligand_sdf_path:
            try:
                from rdkit import Chem as _Chem
                suppl = _Chem.SDMolSupplier(str(ligand_sdf_path), sanitize=False, removeHs=False)
                pose_mol = next(iter(suppl), None)
                if pose_mol is not None and pose_mol.GetNumConformers() > 0:
                    # Los H se agregan CON coordenadas calculadas (no a 0,0,0)
                    mol_with_h = _Chem.AddHs(pose_mol, addCoords=True)
                    log.info("mmgbsa_pose_sdf_used", n_atoms=mol_with_h.GetNumAtoms(),
                             has_conf=mol_with_h.GetConformer() is not None)
            except Exception as e:
                log.warning("mmgbsa_pose_sdf_invalid", error=str(e)[:200])
                mol_with_h = None

        if mol_with_h is None:
            # Sin la topología y coordenadas de la pose no se calcula desde SMILES.
            try:
                os.unlink(prep_pdb)
            except OSError:
                pass
            return {
                "mmgbsa": None, "status": "not_evaluated", "used_pose": False,
                "error": "No se dispone de una pose acoplada válida; MM-GBSA no evaluado.",
            }

        # Cargas: desde SMILES original (independiente de la topología con H)
        charges = None
        try:
            xtb = compute_xtb_features(ligand_smiles)
            charges = xtb.get("xtb_charges", None)
        except Exception:
            pass
        if not charges:
            from rdkit.Chem import AllChem
            AllChem.ComputeGasteigerCharges(mol)
            charges = [float(a.GetProp("_GasteigerCharge")) for a in mol.GetAtoms()]
        has_molchamb = charges is not None

        # 3. Build ligand topology (with pose coordinates from mol_with_h)
        from openmm.app.topology import Topology
        from openmm.app.element import Element

        lig_top = Topology()
        lig_chain = lig_top.addChain("L")
        lig_res = lig_top.addResidue("LIG", lig_chain)
        lig_atoms = []
        lig_positions = []

        # Si tenemos el mol con H y conformador real → usar SUS posiciones.
        # Si no → usar pose_coordinates (pero el conteo debe coincidir con mol_with_h).
        conf = mol_with_h.GetConformer() if mol_with_h.GetNumConformers() > 0 else None
        n_mol = mol_with_h.GetNumAtoms()

        if conf is not None:
            for i in range(n_mol):
                atom = mol_with_h.GetAtomWithIdx(i)
                elem = Element.getBySymbol(atom.GetSymbol())
                a = lig_top.addAtom(f"{atom.GetSymbol()}{i + 1}", elem, lig_res)
                lig_atoms.append(a)
                pos = conf.GetAtomPosition(i)
                lig_positions.append(Vec3(pos.x, pos.y, pos.z) * unit.angstrom)
        else:
            n_pose = len(pose_coordinates)
            for i in range(min(n_pose, n_mol)):
                atom = mol_with_h.GetAtomWithIdx(i)
                elem = Element.getBySymbol(atom.GetSymbol())
                a = lig_top.addAtom(f"{atom.GetSymbol()}{i + 1}", elem, lig_res)
                lig_atoms.append(a)
                x, y, z = pose_coordinates[i]
                lig_positions.append(Vec3(x, y, z) * unit.angstrom)
            # Add remaining atoms at last pose position (degradación)
            if n_mol > n_pose:
                last = pose_coordinates[-1] if pose_coordinates else (0, 0, 0)
                for i in range(n_pose, n_mol):
                    atom = mol_with_h.GetAtomWithIdx(i)
                    elem = Element.getBySymbol(atom.GetSymbol())
                    a = lig_top.addAtom(f"{atom.GetSymbol()}{i + 1}", elem, lig_res)
                    lig_atoms.append(a)
                    lig_positions.append(Vec3(last[0], last[1], last[2]) * unit.angstrom)

        for bond in mol_with_h.GetBonds():
            i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
            if i < len(lig_atoms) and j < len(lig_atoms):
                lig_top.addBond(lig_atoms[i], lig_atoms[j])

        # 4. Build complex
        prot_pdb = PDBFile(prep_pdb)
        modeller = Modeller(prot_pdb.topology, prot_pdb.positions)
        modeller.add(lig_top, lig_positions)

        # 5. OpenMM system with custom template (skip if unsupported atoms)
        _SUPPORTED_ELEMENTS = {"C", "H", "O", "N", "S", "P"}
        ligand_elements = {a.GetSymbol() for a in mol_with_h.GetAtoms()}
        unsupported = ligand_elements - _SUPPORTED_ELEMENTS
        if unsupported:
            # Fallback: skip MM-GBSA for molecules with halogens/metals
            try:
                os.unlink(prep_pdb)
            except OSError as e:
                log.warning("cleanup_failed", stage="unsupported_elements", error=str(e))
            return {
                "g_complex": 0.0, "g_protein": 0.0, "g_ligand": 0.0,
                "mmgbsa": None,
                "time_sec": 0.0,
                "has_molchamb": False,
                "error": f"Unsupported elements: {unsupported}",
            }

        ff = ForceField("amber14-all.xml", "implicit/gbn2.xml")
        _register_ligand_template(ff, mol_with_h, name="LIG")

        system = ff.createSystem(
            modeller.topology, nonbondedMethod=NoCutoff,
            constraints=HBonds, hydrogenMass=1.5 * unit.amu,
        )

        # 6. Override ligand charges with MolChamb
        lig_ids = _find_ligand_atoms(modeller.topology)
        if lig_ids and charges:
            atoms_list = list(modeller.topology.atoms())
            heavy_ids = [i for i in lig_ids if atoms_list[i].element.symbol != "H"]
            if len(charges) >= len(heavy_ids):
                _override_charges(system, heavy_ids, charges[:len(heavy_ids)])

        from services.chemistry.mmgbsa_integrity import validate_ligand_system
        validate_ligand_system(system, modeller.topology, lig_ids)

        # 7. Minimize with best platform
        integrator = LangevinMiddleIntegrator(300 * unit.kelvin, 1.0 / unit.picosecond, 0.002 * unit.picoseconds)
        sim = Simulation(modeller.topology, system, integrator, platform)
        sim.context.setPositions(modeller.positions)
        sim.minimizeEnergy(maxIterations=max_iter)
        state = sim.context.getState(getEnergy=True, getPositions=True)
        g_complex = state.getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
        min_pos = state.getPositions()

        # 8. Protein only + Ligand only
        g_protein = _compute_isolated_fast(modeller, min_pos, ff, lig_ids, "protein", max_iter, platform)
        g_ligand = _compute_isolated_fast(modeller, min_pos, ff, lig_ids, "ligand", max_iter, platform, charges)

        # Cleanup
        try:
            os.unlink(prep_pdb)
        except OSError as e:
            log.warning("cleanup_failed", stage="compute_mmgbsa_from_pose", error=str(e))

        return {
            "g_complex": round(g_complex, 3),
            "g_protein": round(g_protein, 3),
            "g_ligand": round(g_ligand, 3),
            "mmgbsa": round(g_complex - g_protein - g_ligand, 3),
            "time_sec": round(time.time() - t0, 2),
            "has_molchamb": has_molchamb,
        }
    finally:
        try:
            os.unlink(prep_pdb)
        except FileNotFoundError:
            pass
        except OSError as exc:
            log.warning("cleanup_failed", stage="compute_mmgbsa_from_pose", error=str(exc))


def _compute_isolated_fast(modeller, positions, ff, lig_ids, which, max_iter, platform, charges=None):
    """Energía de un subsistema aislado (proteína o ligando).

    FIX 2026-08-04 (g_ligand = +9000 kcal/mol): antes se usaba el sistema
    completo (complejo) y se anulaban cargas/LJ del otro grupo, pero los
    términos BONDED (enlaces/ángulos/torsiones) de la proteína NO se anulan
    → el g_ligand incluía la energía bonded de toda la proteína → absurdo.
    Solución: usar Modeller.delete() para eliminar el otro grupo — OpenMM
    mantiene la estructura de residuos (templates AMBER intactos).
    """
    from openmm.app import Modeller as _Modeller

    lig_set = set(lig_ids)
    all_atoms = list(modeller.topology.atoms())

    try:
        if which == "ligand":
            # Eliminar proteína → queda solo el ligando
            to_delete = [a for i, a in enumerate(all_atoms) if i not in lig_set]
            sub = _Modeller(modeller.topology, positions)
            sub.delete(to_delete)
            sub_top, sub_pos = sub.topology, sub.positions
        else:  # protein
            # Eliminar ligando → queda solo la proteína
            to_delete = [all_atoms[i] for i in lig_set if i < len(all_atoms)]
            sub = _Modeller(modeller.topology, positions)
            sub.delete(to_delete)
            sub_top, sub_pos = sub.topology, sub.positions
    except Exception as e:
        log.warning("isolated_modeller_delete_failed", which=which, error=str(e)[:200])
        raise ValueError(f"MM-GBSA no evaluado: fallo del subsistema {which}: {e}") from e

    # Crear sistema sobre la topología reducida (templates AMBER intactos)
    try:
        system = ff.createSystem(
            sub_top, nonbondedMethod=NoCutoff, constraints=HBonds,
            hydrogenMass=1.5 * unit.amu,
        )
    except Exception as e:
        log.warning("isolated_system_failed", which=which, error=str(e)[:200])
        raise ValueError(f"MM-GBSA no evaluado: fallo del subsistema {which}: {e}") from e

    # Aplicar cargas MolChamb al ligando (solo átomos pesados)
    if which == "ligand" and charges:
        nb = next((f for f in system.getForces() if isinstance(f, NonbondedForce)), None)
        if nb:
            sub_atoms = list(sub_top.atoms())
            heavy = [i for i in range(sub_top.getNumAtoms())
                     if sub_atoms[i].element.symbol != "H"]
            if len(charges) >= len(heavy):
                _override_charges(system, heavy, charges[:len(heavy)])

    integrator = LangevinMiddleIntegrator(300 * unit.kelvin, 1.0 / unit.picosecond, 0.002 * unit.picoseconds)
    sim = Simulation(sub_top, system, integrator, platform)
    sim.context.setPositions(sub_pos)
    sim.minimizeEnergy(maxIterations=max_iter // 2)
    return sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilocalories_per_mole)
