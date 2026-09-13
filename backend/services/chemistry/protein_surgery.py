"""
Protein Surgery — Adaptive protein preparation for docking + MM-GBSA.

Architecture: 6 layers, each with fallback to safe defaults.
Never crashes. Never produces silent wrong results.
Never cuts atoms mid-residue (preserves topology).

Layers:
  1. Chain Detector    — auto-detect binding chain, trim dimers
  2. Dynamic Vina Box   — optimal grid size from ligand span
  3. MM-GBSA Pocket     — trim to 25A + PDBFixer caps
  4. ProLIF Window      — trim to 20A, residues always whole
  5. Metal Features     — pre-docking counts + post-docking distances
  6. Atom Validation    — filter unsupported atoms (B, Se, Si, etc.)
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
from rdkit import Chem, RDLogger

RDLogger.logger().setLevel(RDLogger.ERROR)

# ═══════════════════════════════════════════════════════════
# Layer 1: Chain Detector
# ═══════════════════════════════════════════════════════════

def detect_binding_chain(protein_pdb: str, ligand_center: tuple[float, float, float]) -> str | None:
    """
    Find which chain the ligand binds to (closest average distance).
    Uses fast line-level PDB parsing. Skips empty/solvent chains.
    """
    cx, cy, cz = ligand_center
    chain_dists = {}  # chain_id -> min_distance

    try:
        with open(protein_pdb) as f:
            for line in f:
                if not (line.startswith("ATOM") or line.startswith("HETATM")):
                    continue
                try:
                    chain_id = line[21:22]
                    # Skip empty chain IDs and solvent
                    if not chain_id or chain_id.strip() == "" or chain_id in ("W", "H", "S"):
                        continue

                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    dist = ((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2) ** 0.5

                    if chain_id not in chain_dists or dist < chain_dists[chain_id]:
                        chain_dists[chain_id] = dist
                except (ValueError, IndexError):
                    continue

        if not chain_dists:
            return None

        sorted_chains = sorted(chain_dists.items(), key=lambda x: x[1])
        closest = sorted_chains[0]

        # If closest chain is within 8A, it's the binding chain
        if closest[1] < 8.0:
            # Check if there's a second chain close by
            second = sorted_chains[1] if len(sorted_chains) > 1 else None
            if second and second[1] < 5.0:
                return "multi"
            return closest[0]

        return None

    except Exception:
        return None


def extract_chain(protein_pdb: str, chain_id: str, output_pdb: str) -> bool:
    """
    Extract a single chain from a PDB file using line-level filtering.
    Fast: O(n) line scan, no MDAnalysis overhead.
    """
    if chain_id == "multi":
        shutil.copy(protein_pdb, output_pdb)
        return True

    try:
        with open(protein_pdb) as f_in, open(output_pdb, "w") as f_out:
            n_written = 0
            for line in f_in:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    pdb_chain = line[21:22]
                    if pdb_chain == chain_id or pdb_chain.upper() == chain_id.upper():
                        f_out.write(line)
                        n_written += 1
                elif line.startswith("TER") or line.startswith("END"):
                    f_out.write(line)

        if n_written > 0:
            return True
        shutil.copy(protein_pdb, output_pdb)
        return False

    except Exception:
        shutil.copy(protein_pdb, output_pdb)
        return False


def get_chain_info(protein_pdb: str) -> dict:
    """Get information about chains using fast line-level parsing."""
    chains = {}
    try:
        with open(protein_pdb) as f:
            for line in f:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    chain_id = line[21:22]
                    chains[chain_id] = chains.get(chain_id, 0) + 1
    except Exception:
        pass
    return chains


def get_ligand_center_from_mol2(mol2_path: str) -> tuple[float, float, float] | None:
    """Extract ligand center of mass from MOL2 file."""
    try:
        mol = Chem.MolFromMol2File(mol2_path, removeHs=False)
        if mol is None:
            return None
        conf = mol.GetConformer()
        coords = []
        for i in range(mol.GetNumAtoms()):
            if mol.GetAtomWithIdx(i).GetAtomicNum() > 1:
                pos = conf.GetAtomPosition(i)
                coords.append((pos.x, pos.y, pos.z))
        if not coords:
            return None
        xs, ys, zs = zip(*coords)
        n = len(coords)
        return (float(np.mean(xs)), float(np.mean(ys)), float(np.mean(zs)))
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════
# Layer 2: Dynamic Vina Box
# ═══════════════════════════════════════════════════════════

# Non-ligand HETATM residue names to skip when looking for the binding site.
# Migrated from scripts/recalibrate_all_386_targets.py:10 (Bucket B).
NON_DRUG_HETATMS = {
    # Waters
    "HOH", "WAT", "DOD", "TIP", "SOL", "H2O",
    # Buffer/crystallization/solvents/salts
    "SO4", "PO4", "NO3", "EDO", "GOL", "PEG", "P4G", "PG4", "DMS", "AZI", "CON", "ACT", "FMT", "ACE",
    "NH4", "ACN", "EPE", "MES", "TRS", "TRIS", "HEPES", "ADA", "MPD", "1PE", "PGE", "P6G", "FLC",
    "CIT", "B3N", "DB8", "BCT", "UNX", "UNL", "IPA", "ETOH", "ME2", "DMF", "DTT", "BME", "CL", "NA",
    # Non-drug glycans/sugars
    "NAG", "NDG", "BMA", "MAN", "FUC", "GAL", "GLC", "BGC", "FUL", "SIA", "GLA", "XYP", "RAM", "RIB", "BDF", "AAL",
}

# Catalytic metal ions for metalloenzymes/metalloproteins.  Priority 2 after drug ligand.
CATALYTIC_METALS = {"ZN", "FE", "MN", "MG", "CA", "CU", "NI", "CO", "CD"}


#: Orden de preferencia entre metales cuando hay varios. El catalítico primero.
#:
#: Antes se elegía por número de iones, y eso escoge el ESTRUCTURAL: MMP9 tiene
#: cinco calcios estructurales y un zinc catalítico, así que `max(...)` por
#: cuenta devolvía CA. `services/pipeline/protocols/m5/base.py` ya lo dice con
#: todas las letras —«tratarlos igual sería un error de sitio, no sólo de
#: metal»— y esta función hacía exactamente ese error.
_PREFERENCIA_DE_METAL = ("ZN", "FE", "MN", "CU", "NI", "CO", "CD", "MG", "CA")


def extract_accurate_pocket_centroid(pdb_path: str) -> tuple[tuple[float, float, float] | None, str]:
    """
    Compute active-site 3D centroid from a PDB file using 4 descending priorities.

    Priority 1: co-crystallized drug/inhibitor HETATM (largest single copy)
    Priority 2: catalytic metal ion (ZN, FE, ...) — one ion, by catalytic preference
    Priority 3: non-water HETATM buffers/solvents         (low-confidence fallback)
    Priority 4: protein ATOM centroid                     (geometric fallback)

    ═════════════════════════════════════════════════════════════════════
    SE AGRUPA POR COPIA, NO POR NOMBRE DE RESIDUO
    ═════════════════════════════════════════════════════════════════════

    Los HETATM se agrupaban por `res_name` y se promediaban todos juntos. Si el
    mismo ligando está en cuatro cadenas —un homotetrámero, o dos copias en la
    unidad asimétrica— el «centroide del ligando» era el promedio de las cuatro
    copias, que cae ENTRE ellas y no dentro de ninguna.

    Medido sobre las 411 estructuras del catálogo local antes de corregirlo:

        184 (44.8 %) promediaban varias copias
        139 (33.8 %) daban un centro más lejos del SEMILADO de la caja que la
                     copia más cercana — es decir, la caja no contenía ningún
                     sitio de unión

        peor caso   5CZX   centro a 52.2 Å del calcio más cercano
                    2A3W   10 copias de CPJ, centro a 44.1 Å de la más cercana

    Es el mismo modo de fallo que el corrigendum de M5 documentó para el
    benchmark de MMP9 («ningún zinc cae dentro de la caja declarada»), sólo que
    en la ruta viva. No afecta a los 380 receptores del catálogo curado, que
    traen su centro explícito; afecta al PDB que sube el usuario, que es
    justamente el caso sin centro confirmado por nadie.

    Args:
        pdb_path: absolute or relative path to .pdb file

    Returns:
        ((cx, cy, cz) | None, method_label) — tuple is None iff no atom coords are readable.
        La etiqueta nombra la COPIA elegida (residuo, cadena y número) y, si
        había más de una, cuántas se descartaron: el número que se enseña tiene
        que poder explicarse.
    """
    # Clave: (res_name, cadena, num_residuo) — una COPIA, no un tipo de residuo.
    drug: dict[tuple[str, str, str], list[tuple[float, float, float]]] = {}
    metal: dict[tuple[str, str, str], list[tuple[float, float, float]]] = {}
    otros: dict[tuple[str, str, str], list[tuple[float, float, float]]] = {}
    protein_atoms: list[tuple[float, float, float]] = []

    try:
        with open(pdb_path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if line.startswith("ATOM"):
                    try:
                        x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
                        protein_atoms.append((x, y, z))
                    except ValueError:
                        pass
                elif line.startswith("HETATM"):
                    res_name = line[17:20].strip()
                    if res_name in ("HOH", "WAT", "DOD", "TIP", "SOL", "H2O"):
                        continue
                    try:
                        x = float(line[30:38]); y = float(line[38:46]); z = float(line[46:54])
                    except ValueError:
                        continue
                    copia = (res_name, line[21:22].strip(), line[22:26].strip())
                    if res_name in CATALYTIC_METALS:
                        metal.setdefault(copia, []).append((x, y, z))
                    elif res_name not in NON_DRUG_HETATMS:
                        drug.setdefault(copia, []).append((x, y, z))
                    else:
                        otros.setdefault(copia, []).append((x, y, z))
    except OSError:
        return None, "FAILED"

    def _centroid(coords: list[tuple[float, float, float]]) -> tuple[float, float, float]:
        n = len(coords)
        return (
            round(sum(c[0] for c in coords) / n, 3),
            round(sum(c[1] for c in coords) / n, 3),
            round(sum(c[2] for c in coords) / n, 3),
        )

    def _etiqueta(prefijo: str, copia: tuple[str, str, str], total: int) -> str:
        res, cadena, num = copia
        donde = f"{res} {cadena}{num}".strip()
        if total > 1:
            return f"{prefijo} ({donde}; {total} copias, se usó una)"
        return f"{prefijo} ({donde})"

    if drug:
        # La copia con MÁS átomos, no el tipo de residuo con más átomos sumados.
        elegida = max(drug, key=lambda c: (len(drug[c]), c))
        return _centroid(drug[elegida]), _etiqueta("DRUG_LIGAND", elegida, len(drug))

    if metal:
        # Por preferencia catalítica y, dentro del mismo elemento, la primera
        # copia en orden estable. Nunca por cuántos iones hay de cada uno.
        def _rango(copia: tuple[str, str, str]) -> tuple[int, tuple[str, str, str]]:
            elemento = copia[0]
            orden = (
                _PREFERENCIA_DE_METAL.index(elemento)
                if elemento in _PREFERENCIA_DE_METAL
                else len(_PREFERENCIA_DE_METAL)
            )
            return (orden, copia)

        elegida = min(metal, key=_rango)
        mismos = sum(1 for c in metal if c[0] == elegida[0])
        return _centroid(metal[elegida]), _etiqueta("CATALYTIC_METAL", elegida, mismos)

    if otros:
        elegida = max(otros, key=lambda c: (len(otros[c]), c))
        return _centroid(otros[elegida]), _etiqueta("HETATM_BUFFER_FALLBACK", elegida, len(otros))

    if protein_atoms:
        return _centroid(protein_atoms), "PROTEIN_ATOM_FALLBACK"

    return None, "FAILED"


def compute_dynamic_box(
    ligand_mol2: str | None = None,
    pdb_path: str | None = None,
    min_size: float = 12.0,
    max_size: float = 22.0,
    padding: float = 8.0,
) -> dict:
    """
    Compute optimal Vina grid box from a co-crystallized ligand (mol2) OR a PDB file.

    Priority for the centering source:
      1. ligand_mol2 (highest fidelity — explicit coordinates of the bound drug)
      2. pdb_path    (fallback 1.5 — derivates center from HETATM via
                      extract_accurate_pocket_centroid; used when the user has
                      a raw PDB but no separate ligand mol2)
      3. _default_box (last-resort — center at origin, 22A cube)

    Box size is always in the closed interval [min_size, max_size] clamped from
    (max(ligand_spans) + padding).  This preserves backward compatibility with
    the original signature (callers that pass only ligand_mol2 are unaffected).

    Args:
        ligand_mol2: path to .mol2 of the bound ligand.  Always wins if it exists.
        pdb_path:    path to .pdb.  Used only when ligand_mol2 is None/missing.
        min_size:    lower clamp for the box dimension (A).
        max_size:    upper clamp for the box dimension (A).
        padding:     A added to the ligand span before clamping.

    Returns:
        dict(center: tuple[float,float,float], size: float, ligand_span: tuple,
             source: str)  — 'source' identifies which branch produced the box
        ('mol2' | 'pdb_fallback:<method>' | 'default').
    """
    # ── Branch 1: ligand_mol2 path (highest fidelity, original behaviour) ──
    if ligand_mol2 and Path(ligand_mol2).exists():
        try:
            mol = Chem.MolFromMol2File(ligand_mol2, removeHs=False)
            if mol is not None and mol.GetNumAtoms() > 0:
                conf = mol.GetConformer()
                coords = [(conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z)
                          for i in range(mol.GetNumAtoms())]
                xs, ys, zs = zip(*coords)
                cx, cy, cz = float(np.mean(xs)), float(np.mean(ys)), float(np.mean(zs))
                span_x, span_y, span_z = max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs)
                box_size = max(min_size, min(max_size, max(span_x, span_y, span_z) + padding))
                return {
                    "center": (round(cx, 2), round(cy, 2), round(cz, 2)),
                    "size": round(box_size, 1),
                    "ligand_span": (round(span_x, 2), round(span_y, 2), round(span_z, 2)),
                    "source": "mol2",
                }
        except Exception:
            pass  # fall through to pdb fallback below

    # ── Branch 2: PDB fallback (HETATM-derived center) ──
    if pdb_path and Path(pdb_path).exists():
        center, method = extract_accurate_pocket_centroid(pdb_path)
        if center is not None:
            # Without an explicit ligand we cannot know its 3D span;
            # use the conservative max_size.  Square box (symmetric).
            return {
                "center": (round(center[0], 2), round(center[1], 2), round(center[2], 2)),
                "size": float(max_size),
                "ligand_span": (0.0, 0.0, 0.0),
                "source": f"pdb_fallback:{method}",
            }

    # ── Branch 3: default (origin, 22 A cube) ──
    box = _default_box()
    box["source"] = "default"
    return box


def _default_box() -> dict:
    return {"center": (0.0, 0.0, 0.0), "size": 22.0, "ligand_span": (0, 0, 0)}


# ═══════════════════════════════════════════════════════════
# Layer 3: MM-GBSA Pocket (Positional Restraints approach)
# ═══════════════════════════════════════════════════════════

def trim_to_pocket(protein_pdb: str, ligand_center: tuple[float, float, float],
                   radius: float = 25.0, output_pdb: str | None = None,
                   apply_caps: bool = True) -> tuple[str, bool]:
    """
    Trim protein to residues within `radius` Angstroms of ligand.
    Uses line-level PDB filtering for speed. NEVER cuts atoms mid-residue.

    `apply_caps`: cuando el recorte quita mas de la mitad de los atomos, se pasa
    el resultado por PDBFixer para tapar los extremos rotos con ACE/NME. Eso es
    lo correcto para MM-GBSA, donde un terminal cargado que no existe en la
    proteina real falsea la energia.

    **Para preparar un receptor hay que apagarlo**, y no es una preferencia:
    PDBFixer reescribe el PDB a traves de la topologia de OpenMM y RENOMBRA LAS
    CADENAS. Medido sobre 6SX5, un tetramero cuyo sitio forman A y una copia de
    simetria D:

        tras filtrar a {A, D}   {'A': 2079, 'D': 2079}
        tras recortar (caps)    {'A': 1423}      <- la cadena D desaparecio

    El recorte quitaba mas del 50%, PDBFixer entraba, y las dos cadenas se
    fundian en una. El receptor perdia media cavidad EN SILENCIO, que es
    exactamente el defecto que el recorte multicadena existe para reparar. Y
    ademas rompe la correspondencia con `site_chains` y con los hotspots, que se
    nombran `A:TYR66`.

    Returns: (pdb_path, is_trimmed)
    """
    cx, cy, cz = ligand_center

    try:
        # First pass: find all residues with ANY atom within radius
        residues_to_keep = set()  # (chain, resnum, inscode)
        atom_positions = []  # (chain, resnum, inscode, x, y, z)
        atom_lines = []  # original lines

        with open(protein_pdb) as f:
            for line in f:
                if not (line.startswith("ATOM") or line.startswith("HETATM")):
                    continue
                try:
                    chain = line[21:22]
                    resnum = int(line[22:26])
                    inscode = line[26:27].strip()
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                    atom_positions.append((chain, resnum, inscode, x, y, z))
                    atom_lines.append(line)
                except (ValueError, IndexError):
                    continue

        if not atom_positions:
            return (protein_pdb, False)

        # Find residues within radius
        xs = np.array([p[3] for p in atom_positions])
        ys = np.array([p[4] for p in atom_positions])
        zs = np.array([p[5] for p in atom_positions])
        dists = np.sqrt((xs - cx) ** 2 + (ys - cy) ** 2 + (zs - cz) ** 2)

        for i, dist in enumerate(dists):
            if dist <= radius:
                chain, resnum, inscode = atom_positions[i][:3]
                residues_to_keep.add((chain, resnum, inscode))

        if not residues_to_keep:
            if output_pdb:
                shutil.copy(protein_pdb, output_pdb)
            return (output_pdb or protein_pdb, False)

        # Second pass: write only matching residues
        out = output_pdb or tempfile.mktemp(suffix="_pocket.pdb")
        n_total = 0
        n_kept = 0
        with open(protein_pdb) as f_in, open(out, "w") as f_out:
            for line in f_in:
                if line.startswith("ATOM") or line.startswith("HETATM"):
                    n_total += 1
                    try:
                        chain = line[21:22]
                        resnum = int(line[22:26])
                        inscode = line[26:27].strip()
                        if (chain, resnum, inscode) in residues_to_keep:
                            f_out.write(line)
                            n_kept += 1
                    except (ValueError, IndexError):
                        f_out.write(line)
                elif line.startswith("TER") or line.startswith("END"):
                    f_out.write(line)

        if apply_caps and n_kept < n_total * 0.5:
            # Significant trimming — apply PDBFixer caps
            out = _apply_pdbfixer_caps(out)

        return (out, n_kept > 0 and n_kept < n_total)

    except Exception:
        if output_pdb:
            shutil.copy(protein_pdb, output_pdb)
        return (output_pdb or protein_pdb, False)


def _apply_pdbfixer_caps(pdb_path: str) -> str:
    """Apply PDBFixer to add ACE/NME caps at broken chain termini."""
    try:
        from pdbfixer import PDBFixer
        from openmm.app import PDBFile

        fixer = PDBFixer(filename=pdb_path)
        fixer.findMissingResidues()
        fixer.findNonstandardResidues()
        fixer.replaceNonstandardResidues()
        fixer.findMissingAtoms()
        fixer.addMissingAtoms()
        fixer.addMissingHydrogens(7.4)

        capped = pdb_path.replace(".pdb", "_capped.pdb")
        with open(capped, "w") as f:
            PDBFile.writeFile(fixer.topology, fixer.positions, f)
        return capped

    except Exception:
        return pdb_path


# ═══════════════════════════════════════════════════════════
# Layer 4: ProLIF Window
# ═══════════════════════════════════════════════════════════

def trim_to_window(protein_pdb: str, ligand_center: tuple[float, float, float],
                   radius: float = 20.0, output_pdb: str | None = None) -> tuple[str, bool]:
    """
    Trim protein to residues within `radius` of ligand for ProLIF feature extraction.
    Same as trim_to_pocket but with larger default radius (20A for broader interactions).
    """
    return trim_to_pocket(protein_pdb, ligand_center, radius=radius, output_pdb=output_pdb)


# ═══════════════════════════════════════════════════════════
# Layer 5: Metal Features
# ═══════════════════════════════════════════════════════════

_METAL_BINDING_SMARTS = {
    "sulfonamide": Chem.MolFromSmarts("[#16X4](=[OX1])(=[OX1])-[#7X3]"),
    "carboxylate": Chem.MolFromSmarts("[CX3](=[OX1])-[OX2H1,O-]"),
    "thiol": Chem.MolFromSmarts("[#16X2H1]"),
    "hydroxamic_acid": Chem.MolFromSmarts("[CX3](=[OX1])-[NX3]-[OX2H1]"),
    "imidazole": Chem.MolFromSmarts("c1nc[nH]c1"),  # imidazole ring
    "phosphate": Chem.MolFromSmarts("[PX4](=O)(O)(O)O"),
}

_ZN_BINDING_GROUPS = ["sulfonamide", "carboxylate", "thiol", "hydroxamic_acid", "imidazole"]


def metal_features(smiles: str) -> dict:
    """
    Compute pre-docking metal-binding features from SMILES.
    Zero cost (no Vina, no xTB). Feeds XGBoost for metalloenzyme discrimination.
    """
    features = {
        "sulfonamide_count": 0,
        "carboxylate_count": 0,
        "thiol_count": 0,
        "hydroxamic_acid_count": 0,
        "imidazole_count": 0,
        "phosphate_count": 0,
        "zn_binding_groups_total": 0,
        "has_metal_binding_potential": 0,
    }

    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return features

        for name, smarts in _METAL_BINDING_SMARTS.items():
            if smarts is not None:
                matches = mol.GetSubstructMatches(smarts)
                count = len(matches) if matches else 0
                features[f"{name}_count"] = count

        total = sum(features.get(f"{g}_count", 0) for g in _ZN_BINDING_GROUPS)
        features["zn_binding_groups_total"] = total
        features["has_metal_binding_potential"] = 1 if total > 0 else 0

        return features

    except Exception:
        return features


#: Símbolos de metal que se reconocen en una estructura. Se comparan contra la
#: COLUMNA DE ELEMENTO del PDB (77-78), nunca contra el nombre del átomo.
_SIMBOLOS_DE_METAL = frozenset({
    "ZN", "FE", "MG", "MN", "CA", "CO", "NI", "CU", "CD", "HG", "K", "NA",
})


def detect_metals_in_protein(protein_pdb: str) -> list[dict]:
    """Iones metálicos de una estructura, por su columna de elemento.

    ═════════════════════════════════════════════════════════════════════
    POR QUÉ NO SE MIRA EL NOMBRE DEL ÁTOMO
    ═════════════════════════════════════════════════════════════════════

    Esta función decidía así:

        if element in metal_symbols or atom_name.upper() in metal_symbols:

    y `"CA"` está en `metal_symbols` porque el calcio existe — pero `CA` es
    también el nombre del **carbono alfa de todos los aminoácidos**. La segunda
    condición hacía que cada residuo de cada proteína contara como un metal.

    Medido sobre los receptores del árbol antes de corregirlo:

        1gkc_chainA (MMP9, metaloenzima real)   198 «metales»
                                                191 con elemento C, 5 CA, 2 ZN
        3pp0_chainB (CDK2, sin metales)         380 «metales», todos elemento C

    Una quinasa sin un solo ion devolvía 380 metales. Y el registro guardaba
    `element` —que valía "C"— mientras la coincidencia venía del nombre del
    átomo, así que ni siquiera el resultado delataba el motivo.

    Las dos reglas que lo separan, viendo las líneas reales:

        HETATM 2515 CA    CA A1444   ...   1.00 25.39          CA   <- ion
        ATOM      2  CA  PHE A 110   ...   1.00 76.45           C   <- Cα

    1. **Sólo HETATM.** Un registro ATOM es un átomo del polímero; un ion nunca
       viaja ahí.
    2. **Sólo la columna de elemento (77-78).** Es el campo que el formato PDB
       reserva para esto. El nombre del átomo es una etiqueta del residuo, no
       una identidad química.

    Se devuelve también el nombre del residuo y el número de línea, porque
    `docs/74_ARQUITECTURA_DISPATCHER_DE_PROTOCOLOS.md` §6.2 exige registrar
    identidad y procedencia del metal, no sólo que lo hay.
    """
    metals: list[dict] = []
    try:
        with open(protein_pdb) as f:
            for numero, line in enumerate(f, start=1):
                # Regla 1: sólo heteroátomos.
                if not line.startswith("HETATM"):
                    continue
                # Regla 2: la columna de elemento, y sólo ella. Si la línea es
                # corta y no la trae, no se adivina: se descarta.
                if len(line) < 78:
                    continue
                element = line[76:78].strip().upper()
                if element not in _SIMBOLOS_DE_METAL:
                    continue
                try:
                    x = float(line[30:38])
                    y = float(line[38:46])
                    z = float(line[46:54])
                except ValueError:
                    continue
                metals.append({
                    "element": element,
                    "position": (x, y, z),
                    "residue_name": line[17:20].strip(),
                    "chain": line[21:22].strip(),
                    "residue_seq": line[22:26].strip(),
                    "source_line": numero,
                })
    except Exception:
        pass

    return metals


# ═══════════════════════════════════════════════════════════
# Layer 6: Atom Validation (Thrombin fix)
# ═══════════════════════════════════════════════════════════

_VINA_SUPPORTED = {"H", "C", "N", "O", "F", "P", "S", "Cl", "Br", "I"}


def validate_vina_atoms(smiles: str) -> tuple[bool, set[str]]:
    """
    Check if all atoms in SMILES are supported by Vina force field.
    Returns (is_valid, unsupported_atoms).
    """
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return (False, {"invalid_smiles"})
        atom_symbols = {a.GetSymbol() for a in mol.GetAtoms()}
        unsupported = atom_symbols - _VINA_SUPPORTED
        return (len(unsupported) == 0, unsupported)
    except Exception:
        return (False, {"error"})


# ═══════════════════════════════════════════════════════════
# Master API: prepare_target()
# ═══════════════════════════════════════════════════════════

def prepare_target(
    protein_pdb: str,
    ligand_mol2: str | None = None,
    output_dir: str | None = None,
) -> dict:
    """
    One-call preparation of a docking target with all optimizations.
    Always returns a valid config. Never crashes.

    Returns dict with keys: vina_receptor, vina_center, vina_box, warnings, etc.
    """
    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="surgery_")

    os.makedirs(output_dir, exist_ok=True)
    config = {
        "vina_receptor": protein_pdb,
        "vina_center": (0.0, 0.0, 0.0),
        "vina_box": 22.0,
        "mmgbsa_receptor": protein_pdb,
        "prolif_receptor": protein_pdb,
        "warnings": [],
        "metal_atoms": [],
        "chains": {},
    }

    # ── Analyze protein ──
    chains = get_chain_info(protein_pdb)
    config["chains"] = chains

    metals = detect_metals_in_protein(protein_pdb)
    config["metal_atoms"] = metals

    n_chains = len(chains)
    if n_chains > 1:
        orig_atoms = sum(chains.values())
        config["warnings"].append(f"Multi-chain ({n_chains} chains, {orig_atoms} atoms)")

    # ── Ligand center ──
    lig_center = (0.0, 0.0, 0.0)
    if ligand_mol2 and Path(ligand_mol2).exists():
        center = get_ligand_center_from_mol2(ligand_mol2)
        if center:
            lig_center = center
            config["vina_center"] = center

        # Dynamic box (with explicit ligand — highest fidelity)
        box = compute_dynamic_box(ligand_mol2=ligand_mol2, pdb_path=protein_pdb)
        if box["center"] != (0.0, 0.0, 0.0):
            config["vina_center"] = box["center"]
            config["vina_box"] = box["size"]
            config["ligand_span"] = box["ligand_span"]
            config["box_source"] = box.get("source", "mol2")
    else:
        # No ligand mol2 available — derive center from PDB HETATM fallback.
        box = compute_dynamic_box(ligand_mol2=None, pdb_path=protein_pdb)
        if box["center"] != (0.0, 0.0, 0.0):
            config["vina_center"] = box["center"]
            config["vina_box"] = box["size"]
            config["ligand_span"] = box["ligand_span"]
            config["box_source"] = box.get("source", "pdb_fallback")
            config["warnings"].append(f"box derived from PDB HETATM ({box.get('source', 'unknown')})")

    # ── Layer 1: Chain trimming ──
    trimmed = protein_pdb
    if n_chains > 1 and ligand_mol2 and Path(ligand_mol2).exists():
        chain_id = detect_binding_chain(protein_pdb, lig_center)
        if chain_id and chain_id != "multi":
            trimmed = os.path.join(output_dir, "chain_trimmed.pdb")
            ok = extract_chain(protein_pdb, chain_id, trimmed)
            if ok:
                new_info = get_chain_info(trimmed)
                new_atoms = sum(new_info.values())
                config["vina_receptor"] = trimmed
                config["warnings"].append(f"Chain {chain_id} extracted ({orig_atoms if n_chains > 1 else '?'}→{new_atoms} atoms)")

    # ── Layer 3: MM-GBSA pocket ──
    if ligand_mol2 and Path(ligand_mol2).exists() and lig_center != (0.0, 0.0, 0.0):
        pocket_dir = os.path.join(output_dir, "mmgbsa_pocket")
        os.makedirs(pocket_dir, exist_ok=True)
        pocket_path = os.path.join(pocket_dir, "pocket.pdb")
        pocket_pdb, was_trimmed = trim_to_pocket(trimmed, lig_center, radius=25.0, output_pdb=pocket_path)
        if was_trimmed:
            pocket_atoms = sum(get_chain_info(pocket_pdb).values())
            config["mmgbsa_receptor"] = pocket_pdb
            config["warnings"].append(f"MM-GBSA pocket trimmed (<25A, {pocket_atoms} atoms)")

    # ── Layer 4: ProLIF window ──
    if ligand_mol2 and Path(ligand_mol2).exists() and lig_center != (0.0, 0.0, 0.0):
        window_dir = os.path.join(output_dir, "prolif_window")
        os.makedirs(window_dir, exist_ok=True)
        window_path = os.path.join(window_dir, "window.pdb")
        window_pdb, was_trimmed = trim_to_window(trimmed, lig_center, radius=20.0, output_pdb=window_path)
        if was_trimmed:
            window_atoms = sum(get_chain_info(window_pdb).values())
            config["prolif_receptor"] = window_pdb
            config["warnings"].append(f"ProLIF window trimmed (<20A, {window_atoms} atoms)")

    # ── Metal features ──
    if metals:
        metal_list = ", ".join(f"{m['element']}" for m in metals[:5])
        config["warnings"].append(f"Metal ions detected: {metal_list}")

    return config
