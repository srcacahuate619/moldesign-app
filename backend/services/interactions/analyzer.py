"""
services/interactions/analyzer.py

Protein-Ligand Interaction Fingerprint (PLIF) analysis using ProLIF.

Generates detailed interaction data for the frontend visualization:
- Hydrogen bonds (with donor-hydrogen-acceptor geometry)
- Hydrophobic contacts
- Pi-stacking (face-to-face and edge-to-face)
- Salt bridges (with distance)
- Cation-pi interactions
- Halogen bonds

Each interaction includes:
- Residue information (name, number, chain)
- Atom-level detail (ligand atom, protein atom)
- Distance in Angstroms
- For H-bonds: D-H...A angle

Reference: Bouysset & Fiorentino (2024) ProLIF v2.0
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class Interaction:
    type: str                # "hbond", "hydrophobic", "pi_stacking", "salt_bridge", "cation_pi", "halogen"
    residue_name: str        # e.g. "ASP"
    residue_number: int
    residue_chain: str
    ligand_atom: str         # e.g. "O4"
    protein_atom: str        # e.g. "OD2"
    distance: float          # Angstroms
    angle: float | None = None  # degrees (for H-bonds only)
    strength: str = "weak"   # "weak", "moderate", "strong"
    # 3D coordinates for 3D viewer rendering (fix #6)
    lig_x: float = 0.0
    lig_y: float = 0.0
    lig_z: float = 0.0
    prot_x: float = 0.0
    prot_y: float = 0.0
    prot_z: float = 0.0


@dataclass
class InteractionReport:
    molecule_id: str
    target_pdb_id: str
    pose_rank: int
    interactions: list[Interaction] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)  # count per type
    pharmacophore_features: dict[str, list[tuple[float, float, float]]] = field(default_factory=dict)
    # donor, acceptor, hydrophobic, aromatic, positive, negative → list of (x,y,z) coords


def analyze_complex(
    protein_pdb_path: str | Path,
    ligand_sdf_path: str | Path,
    molecule_id: str = "",
    target_pdb_id: str = "",
    pose_rank: int = 1,
) -> InteractionReport:
    """
    Analyze protein-ligand interactions using ProLIF.

    Args:
        protein_pdb_path: Path to the prepared protein PDB file
        ligand_sdf_path: Path to the docked ligand SDF file
        molecule_id: Molecule UUID for reporting
        target_pdb_id: Target PDB ID
        pose_rank: Which pose (1 = best)

    Returns:
        InteractionReport with detailed interaction data
    """
    report = InteractionReport(
        molecule_id=molecule_id,
        target_pdb_id=target_pdb_id,
        pose_rank=pose_rank,
    )

    try:
        import prolif
        from prolif.plotting.network import LigNetwork
        from rdkit import Chem
    except ImportError:
        log.warning("prolif_not_available")
        return _fallback_analysis(protein_pdb_path, ligand_sdf_path, report)

    try:
        # Load protein and ligand
        protein = prolif.Molecule(str(protein_pdb_path))
        ligand_mol = Chem.SDMolSupplier(str(ligand_sdf_path))[0]
        if ligand_mol is None:
            log.warning("ligand_sdf_parse_failed", path=str(ligand_sdf_path))
            return _fallback_analysis(protein_pdb_path, ligand_sdf_path, report)

        ligand = prolif.Molecule.from_rdkit(ligand_mol)

        # Compute interaction fingerprint
        fp = prolif.Fingerprint([
            "HBDonor", "HBAcceptor", "Hydrophobic",
            "PiStacking", "PiCation", "CationPi",
            "Anionic", "Cationic",
            "XBAcceptor", "XBDonor",
        ])
        fp.run_from_iterable([ligand], protein)

        if len(fp.ifp) == 0:
            log.info("no_interactions_found", molecule_id=molecule_id)
            return report

        # Parse fingerprint data
        frame = fp.to_dataframe()
        interaction_counts = {}
        pharmacophore = {
            "donor": [],
            "acceptor": [],
            "hydrophobic": [],
            "aromatic": [],
            "positive": [],
            "negative": [],
        }

        for (ligand_key, protein_key), data in fp.ifp.items():
            for interaction_type, has_int in data.items():
                if not has_int:
                    continue

                interaction_counts[interaction_type] = interaction_counts.get(interaction_type, 0) + 1

                # Extract residue info from protein key
                residue_info = _parse_prolif_key(protein_key)
                ligand_info = _parse_prolif_key(ligand_key)

                interaction = _classify_interaction(
                    interaction_type=interaction_type,
                    residue_info=residue_info,
                    ligand_info=ligand_info,
                    protein=protein,
                    ligand=ligand,
                    residue_key=protein_key,
                    ligand_key=ligand_key,
                )

                if interaction:
                    report.interactions.append(interaction)

        # Pharmacophore features extraction
        try:
            pharmacophore = _extract_pharmacophore_features(ligand_mol)
        except Exception:
            pass

        report.summary = interaction_counts
        report.pharmacophore_features = pharmacophore

        log.info(
            "interaction_analysis_complete",
            molecule_id=molecule_id,
            total_interactions=len(report.interactions),
            types=list(interaction_counts.keys()),
        )

    except Exception as e:
        log.error("interaction_analysis_error", error=str(e), molecule_id=molecule_id)
        return _fallback_analysis(protein_pdb_path, ligand_sdf_path, report)

    return report


def _parse_prolif_key(key: str) -> dict[str, Any]:
    """Parse ProLIF key like 'ALA100.A' → {name, number, chain, atom}"""
    import re
    # Pattern: RESNAME NUM . CHAIN ( atom )
    # e.g. "ASP189.A" or "ASP189.A.O"
    match = re.match(r"([A-Z]{3})(\d+)\.([A-Za-z0-9])(?:\.(\w+))?", key)
    if match:
        return {
            "name": match.group(1),
            "number": int(match.group(2)),
            "chain": match.group(3),
            "atom": match.group(4) or "",
        }
    return {"name": key, "number": 0, "chain": "", "atom": ""}


def _classify_interaction(
    interaction_type: str,
    residue_info: dict,
    ligand_info: dict,
    protein,
    ligand,
    residue_key: str,
    ligand_key: str,
) -> Interaction | None:
    """Classify a ProLIF interaction into a standardized Interaction object."""

    type_map = {
        "HBDonor": "hbond",
        "HBAcceptor": "hbond",
        "Hydrophobic": "hydrophobic",
        "PiStacking": "pi_stacking",
        "PiCation": "cation_pi",
        "CationPi": "cation_pi",
        "Anionic": "salt_bridge",
        "Cationic": "salt_bridge",
        "XBAcceptor": "halogen",
        "XBDonor": "halogen",
    }

    strength_map = {
        "hbond": "moderate",
        "hydrophobic": "weak",
        "pi_stacking": "moderate",
        "salt_bridge": "strong",
        "cation_pi": "moderate",
        "halogen": "weak",
    }

    itype = type_map.get(interaction_type, "hydrophobic")

    # Estimate distance from coordinates if available
    distance = _estimate_distance(protein, residue_key, ligand, ligand_key)

    # Extract 3D coordinates for frontend rendering
    lig_xyz = _get_atom_coords(ligand, ligand_key)
    prot_xyz = _get_atom_coords(protein, residue_key)

    # El ángulo D-H⋯A sólo es calculable con hidrógenos explícitos, y el
    # receptor no llega aquí protonado: `_estimate_hbond_angle` devuelve `None`
    # a propósito, en vez del 180.0° constante que devolvía antes. La distancia
    # D⋯A —que es la que decide si hay contacto— se sigue midiendo.
    angle = None
    if itype == "hbond":
        angle = _estimate_hbond_angle(protein, residue_key, ligand, ligand_key)

    return Interaction(
        type=itype,
        residue_name=residue_info.get("name", "UNK"),
        residue_number=residue_info.get("number", 0),
        residue_chain=residue_info.get("chain", "?"),
        ligand_atom=ligand_info.get("atom", "?"),
        protein_atom=residue_info.get("atom", "?"),
        distance=round(distance, 2) if distance else 0.0,
        angle=round(angle, 1) if angle else None,
        strength=strength_map.get(itype, "weak"),
        lig_x=lig_xyz[0] if lig_xyz else 0.0,
        lig_y=lig_xyz[1] if lig_xyz else 0.0,
        lig_z=lig_xyz[2] if lig_xyz else 0.0,
        prot_x=prot_xyz[0] if prot_xyz else 0.0,
        prot_y=prot_xyz[1] if prot_xyz else 0.0,
        prot_z=prot_xyz[2] if prot_xyz else 0.0,
    )


def _estimate_distance(protein, res_key, ligand, lig_key) -> float:
    """Estimate distance between interacting atoms."""
    try:
        res_xyz = protein[res_key].xyz
        lig_xyz = ligand[lig_key].xyz
        return float(np.linalg.norm(res_xyz - lig_xyz))
    except Exception:
        return 0.0


def _estimate_hbond_angle(protein, res_key, ligand, lig_key) -> None:
    """El ángulo D-H⋯A. Devuelve `None`: sin hidrógenos no es calculable.

    ═══════════════════════════════════════════════════════════════════════
    LO QUE HACÍA ESTA FUNCIÓN, Y POR QUÉ NO SERVÍA
    ═══════════════════════════════════════════════════════════════════════

    Colocaba un hidrógeno ficticio a 1.0 Å del donador **sobre el propio
    vector D→A**, y después medía el ángulo entre D-H y H⋯A:

        h_xyz  = donor + (vec_da / dist) * 1.0
        vec_dh = h_xyz - donor      =  û           (unitario en dirección D→A)
        vec_ha = acceptor - h_xyz   =  (dist−1)·û  (el MISMO unitario)

    Los dos vectores son colineales por construcción, así que cos θ ≡ 1,
    arccos(1) = 0, y `180.0 − 0.0` devolvía **exactamente 180.0 para todo
    puente de hidrógeno**. No era una estimación mala: era una tautología.

    Comprobado sobre 2000 geometrías aleatorias: todos los valores caen entre
    179.998° y 180.000°, y esa variación es ruido de coma flotante, no
    geometría.

    Un ángulo de 180.0° con un decimal, en pantalla, junto a una distancia
    medida de verdad, se lee como una medición. Los puentes de hidrógeno reales
    en interfaces proteína-ligando rara vez son lineales: caen entre ~130° y
    ~165° según la hibridación del donador.

    ═══════════════════════════════════════════════════════════════════════
    POR QUÉ `None` Y NO UNA ESTIMACIÓN MEJOR
    ═══════════════════════════════════════════════════════════════════════

    El ángulo D-H⋯A necesita la posición del hidrógeno, y el hidrógeno depende
    de la geometría del donador —sp² plano en una amida, sp³ rotable en un
    hidroxilo— y de la red de enlaces alrededor. No se deduce de las
    coordenadas de dos átomos pesados. Con el receptor preparado sin
    hidrógenos explícitos, la respuesta honesta es que no se sabe.

    La distancia D⋯A **sí** se mide y se sigue reportando: es la que decide si
    hay contacto. Lo que se retira es el ángulo, no el puente.

    Para recuperarlo haría falta protonar el receptor —`reduce`, `pdbfixer` o
    similar— y conservar esos hidrógenos hasta aquí.
    """
    return None


def _get_atom_coords(mol, key: str) -> tuple[float, float, float] | None:
    """Extract 3D coordinates of an atom from a ProLIF molecule by residue key."""
    try:
        xyz = mol[key].xyz
        return (float(xyz[0]), float(xyz[1]), float(xyz[2]))
    except Exception:
        return None


def _extract_pharmacophore_features(ligand_mol) -> dict[str, list[tuple[float, float, float]]]:
    """Extract pharmacophore feature coordinates from ligand."""
    from rdkit.Chem import ChemicalFeatures

    features = {
        "donor": [],
        "acceptor": [],
        "hydrophobic": [],
        "aromatic": [],
        "positive": [],
        "negative": [],
    }

    try:
        conf = ligand_mol.GetConformer()
        feat_factory = ChemicalFeatures.BuildFeatureFactory()

        feats = feat_factory.GetFeaturesForMol(ligand_mol)
        for f in feats:
            pos = f.GetPos()
            family = f.GetFamily()
            coord = (round(pos.x, 2), round(pos.y, 2), round(pos.z, 2))

            if family == "Donor":
                features["donor"].append(coord)
            elif family == "Acceptor":
                features["acceptor"].append(coord)
            elif family == "Hydrophobe":
                features["hydrophobic"].append(coord)
            elif family == "Aromatic":
                features["aromatic"].append(coord)
            elif family == "PosIonizable":
                features["positive"].append(coord)
            elif family == "NegIonizable":
                features["negative"].append(coord)
    except Exception:
        # Fallback: extract from atom types
        conf = ligand_mol.GetConformer()
        for atom in ligand_mol.GetAtoms():
            pos = conf.GetAtomPosition(atom.GetIdx())
            coord = (round(pos.x, 2), round(pos.y, 2), round(pos.z, 2))

            atomic_num = atom.GetAtomicNum()
            if atomic_num in (7, 8) and atom.GetTotalNumHs() > 0:
                features["donor"].append(coord)
            elif atomic_num in (7, 8):
                features["acceptor"].append(coord)
            elif atomic_num == 6 and atom.GetIsAromatic():
                features["aromatic"].append(coord)

    return features


def _fallback_analysis(protein_pdb_path, ligand_sdf_path, report):
    """Simple distance-based fallback when ProLIF is unavailable."""
    try:
        from rdkit import Chem

        # Parse protein
        with open(protein_pdb_path) as f:
            pdb_lines = f.readlines()

        protein_atoms = []
        for line in pdb_lines:
            if line.startswith("ATOM") or line.startswith("HETATM"):
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    atom_name = line[12:16].strip()
                    res_name = line[17:20].strip()
                    res_num = int(line[22:26])
                    chain = line[21:22].strip()
                    protein_atoms.append({
                        "x": x, "y": y, "z": z,
                        "atom": atom_name, "residue": res_name,
                        "residue_num": res_num, "chain": chain,
                    })
                except (ValueError, IndexError):
                    continue

        # Parse ligand
        ligand = Chem.SDMolSupplier(str(ligand_sdf_path))[0]
        if ligand is None:
            return report

        conf = ligand.GetConformer()
        summary = {}

        for atom in ligand.GetAtoms():
            lig_pos = conf.GetAtomPosition(atom.GetIdx())
            lig_name = atom.GetSymbol() + str(atom.GetIdx())

            for prot in protein_atoms:
                dx = lig_pos.x - prot["x"]
                dy = lig_pos.y - prot["y"]
                dz = lig_pos.z - prot["z"]
                dist = np.sqrt(dx*dx + dy*dy + dz*dz)

                if dist < 3.2:  # H-bond range
                    # Check if donor/acceptor
                    donor = atom.GetAtomicNum() in (7, 8)
                    acceptor = prot["atom"][0] in ("O", "N")
                    if donor or acceptor:
                        itype = "hbond"
                    else:
                        itype = "hydrophobic"

                    summary[itype] = summary.get(itype, 0) + 1
                    report.interactions.append(Interaction(
                        type=itype,
                        residue_name=prot["residue"],
                        residue_number=prot["residue_num"],
                        residue_chain=prot["chain"],
                        ligand_atom=lig_name,
                        protein_atom=prot["atom"],
                        distance=round(dist, 2),
                        strength="moderate" if itype == "hbond" else "weak",
                        lig_x=round(lig_pos.x, 2),
                        lig_y=round(lig_pos.y, 2),
                        lig_z=round(lig_pos.z, 2),
                        prot_x=round(prot["x"], 2),
                        prot_y=round(prot["y"], 2),
                        prot_z=round(prot["z"], 2),
                    ))
                elif dist < 4.0:
                    summary["hydrophobic"] = summary.get("hydrophobic", 0) + 1
                    report.interactions.append(Interaction(
                        type="hydrophobic",
                        residue_name=prot["residue"],
                        residue_number=prot["residue_num"],
                        residue_chain=prot["chain"],
                        ligand_atom=lig_name,
                        protein_atom=prot["atom"],
                        distance=round(dist, 2),
                        strength="weak",
                        lig_x=round(lig_pos.x, 2),
                        lig_y=round(lig_pos.y, 2),
                        lig_z=round(lig_pos.z, 2),
                        prot_x=round(prot["x"], 2),
                        prot_y=round(prot["y"], 2),
                        prot_z=round(prot["z"], 2),
                    ))

        report.summary = summary
    except Exception as e:
        log.warning("fallback_analysis_failed", error=str(e))

    return report
