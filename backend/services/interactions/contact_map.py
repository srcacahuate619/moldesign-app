"""Depict explicit contact atom groups on the exact SDF analyzed, without rescoring."""
from __future__ import annotations

import hashlib
from numbers import Integral
from pathlib import Path

from services.interactions.analyzer import InteractionReport
from utils.logger import get_logger

log = get_logger(__name__)


def build_contact_map(ligand_sdf_path: str | Path, report: InteractionReport) -> dict:
    """Only bound, valid indices can highlight an atom. Drawing uses a copy."""
    content = Path(ligand_sdf_path).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    unavailable = {"status": "unavailable", "analysis_ligand_sha256": digest}
    if report.ligand_source_sha256 != digest:
        return {**unavailable, "reason": "UNBOUND_ATOM_INDICES"}
    try:
        from rdkit import Chem, rdBase
        from rdkit.Chem import rdDepictor
        from rdkit.Chem.Draw import rdMolDraw2D

        # Identical input/parser to analyze_complex and its distance fallback.
        original = Chem.SDMolSupplier(str(ligand_sdf_path), removeHs=False)[0]
        if original is None or not original.GetNumAtoms() or not original.GetNumConformers():
            return {**unavailable, "reason": "NO_DRAWABLE_POSE"}
        count = original.GetNumAtoms()
        if count > 250:
            return {**unavailable, "reason": "TOO_MANY_ATOMS_FOR_2D"}
        expanded_count = Chem.AddHs(original, addCoords=True).GetNumAtoms()
        mappings = []
        highlighted: set[int] = set()
        for index, contact in enumerate(report.interactions):
            indices = contact.ligand_atom_indices
            valid = bool(indices) and all(isinstance(i, Integral) and not isinstance(i, bool)
                                          and 0 <= i < expanded_count for i in indices)
            drawn = sorted(set(int(i) for i in indices if i < count)) if valid else []
            reason = None if drawn else "NO_DRAWABLE_ATOMS" if valid else "INVALID_OR_MISSING_INDICES"
            highlighted.update(drawn)
            mappings.append({"contact_index": index, "atom_indices": drawn,
                             "hidden_hydrogen_indices": sorted(set(int(i) for i in indices if i >= count)) if valid else [],
                             "reason": reason})

        molecule = Chem.Mol(original)
        for atom in molecule.GetAtoms():
            atom.SetIntProp("_MolDesignContactIndex", atom.GetIdx())
        molecule.RemoveAllConformers()
        rdDepictor.Compute2DCoords(molecule)
        molecule = rdMolDraw2D.PrepareMolForDrawing(molecule, addChiralHs=False)
        # A renderer that changes the indexing cannot silently reinterpret contacts.
        if molecule.GetNumAtoms() != count or any(
            not molecule.GetAtomWithIdx(i).HasProp("_MolDesignContactIndex")
            or molecule.GetAtomWithIdx(i).GetIntProp("_MolDesignContactIndex") != i
            or molecule.GetAtomWithIdx(i).GetAtomicNum() != original.GetAtomWithIdx(i).GetAtomicNum()
            for i in range(count)
        ):
            return {**unavailable, "reason": "ATOM_MAPPING_CHANGED"}
        width, height = 900, 520
        drawer = rdMolDraw2D.MolDraw2DSVG(width, height)
        options = drawer.drawOptions()
        options.prepareMolsBeforeDrawing = False
        options.addAtomIndices = True
        options.padding = 0.12
        options.setBackgroundColour((1.0, 1.0, 1.0))
        drawer.DrawMolecule(molecule, highlightAtoms=sorted(highlighted),
                            highlightAtomColors={i: (0.65, 0.88, 0.72) for i in highlighted},
                            highlightBonds=[])
        atoms = []
        for i in range(count):
            position = drawer.GetDrawCoords(i)
            atoms.append({"index": i, "element": molecule.GetAtomWithIdx(i).GetSymbol(),
                          "x": float(position.x), "y": float(position.y)})
        drawer.FinishDrawing()
        svg = drawer.GetDrawingText()
        return {"status": "ready", "reason": None, "svg": svg,
                "svg_sha256": hashlib.sha256(svg.encode("utf-8")).hexdigest(),
                "width": width, "height": height, "atoms": atoms, "contacts": mappings,
                "highlighted_atom_indices": sorted(highlighted), "analysis_ligand_sha256": digest,
                "atom_index_basis": "rdkit_analysis_sdf_zero_based", "renderer": f"rdkit:{rdBase.rdkitVersion}"}
    except Exception as exc:
        log.warning("contact_map_unavailable", error=str(exc))
        return {**unavailable, "reason": "DEPICTION_UNAVAILABLE"}
