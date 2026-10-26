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
import hashlib
import math

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
    # Full groups from the detector, never inferred from an atom label or proximity.
    ligand_atom_indices: tuple[int, ...] = ()
    protein_atom_indices: tuple[int, ...] = ()
    definition: str | None = None
    geometry: dict[str, float] = field(default_factory=dict)


@dataclass
class InteractionReport:
    molecule_id: str
    target_pdb_id: str
    pose_rank: int
    interactions: list[Interaction] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    pharmacophore_features: dict[str, list[tuple[float, float, float]]] = field(default_factory=dict)
    engine: str = "no_evaluado"
    hydrogen_model: str | None = None
    ligand_source_sha256: str | None = None
    coverage: str = "not_declared"


def analyze_complex(
    protein_pdb_path: str | Path,
    ligand_sdf_path: str | Path,
    molecule_id: str = "",
    target_pdb_id: str = "",
    pose_rank: int = 1,
) -> InteractionReport:
    """Analiza la pose real y declara si ProLIF o el respaldo produjo los contactos."""
    report = InteractionReport(
        molecule_id=molecule_id, target_pdb_id=target_pdb_id, pose_rank=pose_rank,
    )
    try:
        report.ligand_source_sha256 = hashlib.sha256(Path(ligand_sdf_path).read_bytes()).hexdigest()
        import prolif
        from rdkit import Chem

        # El PDB crudo puede contener el ligando del cristal y aguas. No son
        # residuos del receptor que se acopló y jamás deben contarse como tales.
        atom_lines = [
            line for line in Path(protein_pdb_path).read_text(encoding="utf-8").splitlines()
            if line.startswith("ATOM  ")
        ]
        if not atom_lines:
            raise ValueError("El receptor no tiene átomos ATOM")
        protein_mol = Chem.MolFromPDBBlock(
            "\n".join(atom_lines) + "\nEND\n", removeHs=False, sanitize=True,
        )
        if protein_mol is None:
            raise ValueError("RDKit no pudo interpretar el receptor")
        ligand_mol = Chem.SDMolSupplier(str(ligand_sdf_path), removeHs=False)[0]
        if ligand_mol is None:
            raise ValueError("RDKit no pudo interpretar la pose")
        numeros_originales = _renumerar_residuos_negativos(protein_mol)
        # H geométricos de RDKit: no implica estado de protonación a pH 7.4.
        protein_mol = Chem.AddHs(protein_mol, addCoords=True)
        ligand_mol = Chem.AddHs(ligand_mol, addCoords=True)
        protein = prolif.Molecule.from_rdkit(protein_mol)
        ligand = prolif.Molecule.from_rdkit(ligand_mol)
        fingerprint = prolif.Fingerprint([
            "HBDonor", "HBAcceptor", "Hydrophobic", "PiStacking",
            "PiCation", "CationPi", "Anionic", "Cationic",
            "XBAcceptor", "XBDonor",
        ], count=False)
        ifp = fingerprint.generate(ligand, protein, metadata=True)
        nombres = {
            "HBDonor": "hbond", "HBAcceptor": "hbond",
            "Hydrophobic": "hydrophobic", "PiStacking": "pi_stacking",
            "PiCation": "cation_pi", "CationPi": "cation_pi",
            "Anionic": "salt_bridge", "Cationic": "salt_bridge",
            "XBAcceptor": "halogen", "XBDonor": "halogen",
        }
        for (_lig_res, prot_res), tipos in ifp.items():
            for nombre, evidencias in tipos.items():
                tipo = nombres.get(nombre)
                if tipo is None:
                    continue
                for evidencia in evidencias:
                    li = evidencia["parent_indices"]["ligand"][0]
                    pi = evidencia["parent_indices"]["protein"][0]
                    lp = ligand_mol.GetConformer().GetAtomPosition(li)
                    pp = protein_mol.GetConformer().GetAtomPosition(pi)
                    distancia = evidencia.get("distance")
                    if distancia is None:
                        distancia = float(np.linalg.norm(np.array([lp.x-pp.x, lp.y-pp.y, lp.z-pp.z])))
                    angle = evidencia.get("angle")
                    report.interactions.append(Interaction(
                        type=tipo,
                        residue_name=prot_res.name,
                        residue_number=numeros_originales.get(
                            ((prot_res.chain or "").strip(), int(prot_res.number)), int(prot_res.number)),
                        residue_chain=prot_res.chain or "",
                        ligand_atom=f"{ligand_mol.GetAtomWithIdx(li).GetSymbol()}{li}",
                        protein_atom=f"{protein_mol.GetAtomWithIdx(pi).GetSymbol()}{pi}",
                        distance=round(float(distancia), 2),
                        angle=round(float(angle), 1) if angle is not None else None,
                        strength="strong" if tipo == "salt_bridge" else "moderate" if tipo == "hbond" else "weak",
                        lig_x=round(lp.x, 2), lig_y=round(lp.y, 2), lig_z=round(lp.z, 2),
                        prot_x=round(pp.x, 2), prot_y=round(pp.y, 2), prot_z=round(pp.z, 2),
                        ligand_atom_indices=tuple(int(i) for i in evidencia["parent_indices"]["ligand"]),
                        protein_atom_indices=tuple(int(i) for i in evidencia["parent_indices"]["protein"]),
                        definition=nombre,
                        geometry={key: float(value) for key, value in evidencia.items()
                                  if isinstance(value, (int, float, np.number)) and not isinstance(value, bool)
                                  and math.isfinite(float(value))},
                    ))
                    report.summary[tipo] = report.summary.get(tipo, 0) + 1
        report.pharmacophore_features = _extract_pharmacophore_features(ligand_mol)
        report.engine = f"prolif:{prolif.__version__}"
        report.hydrogen_model = "rdkit_add_hs_coordinates"
        report.coverage = "first_match_per_type_and_residue"
        return report
    except Exception as exc:
        log.warning("prolif_analysis_unavailable", error=str(exc))
        return _fallback_analysis(protein_pdb_path, ligand_sdf_path, report)


def _renumerar_residuos_negativos(mol) -> dict[tuple[str, int], int]:
    """Da un número positivo a cada residuo con número negativo, sólo para ProLIF.

    ProLIF guarda el número de residuo como entero sin signo (`ResidueGroup`,
    uint32) y con un residuo en -1 lanza OverflowError. La receta del catálogo
    retira los cierres ACE/NME, que es donde más se ve, pero un receptor ya
    preparado (camino B o C) los conserva —cdk2 de OpenFF trae ACE A:-1— y
    entonces toda la corrida caía al análisis por distancias, sin química
    (FEP-09, 2026-10-11). Devuelve {(cadena, número provisional): número
    original} para que el informe diga el residuo del archivo, no el provisional.
    """
    infos = [a.GetPDBResidueInfo() for a in mol.GetAtoms()]
    infos = [i for i in infos if i is not None]
    if not any(i.GetResidueNumber() < 0 for i in infos):
        return {}
    siguiente = max(i.GetResidueNumber() for i in infos)
    provisional: dict[tuple[str, int, str], int] = {}
    for info in infos:
        numero = info.GetResidueNumber()
        if numero >= 0:
            continue
        clave = (info.GetChainId(), numero, info.GetInsertionCode())
        if clave not in provisional:
            siguiente += 1
            provisional[clave] = siguiente
        info.SetResidueNumber(provisional[clave])
    # La cadena en blanco es " " en RDKit y "" en ProLIF.
    return {(cadena.strip(), nuevo): numero for (cadena, numero, _), nuevo in provisional.items()}


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
    """Contactos por distancias, sin inferir enlaces H ni química no medida."""
    report.engine = "distancias_sin_quimica"
    report.hydrogen_model = None
    report.coverage = "atom_pairs_within_cutoffs"
    try:
        report.ligand_source_sha256 = hashlib.sha256(Path(ligand_sdf_path).read_bytes()).hexdigest()
        from rdkit import Chem

        protein_atoms = []
        for line in Path(protein_pdb_path).read_text(encoding="utf-8").splitlines():
            if not line.startswith("ATOM  "):
                continue
            element = line[76:78].strip().upper() or line[12:16].strip()[:1].upper()
            if element == "H":
                continue
            try:
                protein_atoms.append({
                    "xyz": np.array([float(line[30:38]), float(line[38:46]), float(line[46:54])]),
                    "element": element,
                    "atom": line[12:16].strip(),
                    "residue": line[17:20].strip(),
                    "residue_num": int(line[22:26]),
                    "chain": line[21:22].strip(),
                })
            except (ValueError, IndexError):
                continue

        ligand = Chem.SDMolSupplier(str(ligand_sdf_path), removeHs=False)[0]
        if ligand is None:
            return report
        conf = ligand.GetConformer()
        for atom in ligand.GetAtoms():
            if atom.GetAtomicNum() == 1:
                continue
            pos = conf.GetAtomPosition(atom.GetIdx())
            lig_xyz = np.array([pos.x, pos.y, pos.z])
            lig_element = atom.GetSymbol().upper()
            for prot in protein_atoms:
                dist = float(np.linalg.norm(lig_xyz - prot["xyz"]))
                if dist < 1.5:
                    continue  # colisión, no interacción favorable
                if lig_element == "C" and prot["element"] == "C" and dist < 4.0:
                    tipo = "hydrophobic"
                elif lig_element in ("N", "O") and prot["element"] in ("N", "O") and dist < 3.5:
                    tipo = "polar_contact"  # sin H/ángulo no es un puente de H
                else:
                    continue
                report.summary[tipo] = report.summary.get(tipo, 0) + 1
                report.interactions.append(Interaction(
                    type=tipo,
                    residue_name=prot["residue"],
                    residue_number=prot["residue_num"],
                    residue_chain=prot["chain"],
                    ligand_atom=f"{lig_element}{atom.GetIdx()}",
                    protein_atom=prot["atom"],
                    distance=round(dist, 2),
                    strength="weak",
                    lig_x=round(pos.x, 2), lig_y=round(pos.y, 2), lig_z=round(pos.z, 2),
                    prot_x=round(float(prot["xyz"][0]), 2),
                    prot_y=round(float(prot["xyz"][1]), 2),
                    prot_z=round(float(prot["xyz"][2]), 2),
                    ligand_atom_indices=(atom.GetIdx(),),
                    definition=f"{lig_element}_{prot['element']}_distance",
                    geometry={"distance": dist, "minimum_inclusive_distance": 1.5,
                              "maximum_exclusive_distance": 4.0 if tipo == "hydrophobic" else 3.5},
                ))
    except Exception as exc:
        log.warning("fallback_analysis_failed", error=str(exc))
    return report
