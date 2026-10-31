"""Compare a PubChem SMILES with a fresh editor molfile, without standardizing salts."""
from __future__ import annotations


def compare_editor_structure(reference_smiles: str, molfile: str) -> dict[str, str]:
    try:
        from rdkit import Chem, rdBase
        reference = Chem.MolFromSmiles(reference_smiles)
        drawn = Chem.MolFromMolBlock(molfile, sanitize=True, removeHs=True, strictParsing=True)
        if reference is None or drawn is None or not reference.GetNumAtoms() or not drawn.GetNumAtoms():
            return {"status": "unverifiable", "reason": "No se pudo interpretar la estructura del editor o de PubChem."}
        if any(atom.HasQuery() or atom.GetAtomicNum() == 0 for mol in (reference, drawn) for atom in mol.GetAtoms()) or any(
            bond.HasQuery() for mol in (reference, drawn) for bond in mol.GetBonds()):
            return {"status": "unverifiable", "reason": "La estructura contiene átomos o enlaces de consulta no compatibles."}
        canonical = lambda mol: Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
        ref_exact, drawn_exact = canonical(reference), canonical(drawn)
        ref_no_stereo, drawn_no_stereo = Chem.Mol(reference), Chem.Mol(drawn)
        Chem.RemoveStereochemistry(ref_no_stereo)
        Chem.RemoveStereochemistry(drawn_no_stereo)
        if canonical(ref_no_stereo) != canonical(drawn_no_stereo):
            result = "different_structure"
        elif ref_exact != drawn_exact:
            result = "different_stereochemistry"
        else:
            unspecified = any(str(stereo.specified) == "Unspecified" for mol in (reference, drawn)
                              for stereo in Chem.FindPotentialStereo(mol))
            result = "match_stereo_unspecified" if unspecified else "match"
        return {"status": result, "method": f"RDKit {rdBase.rdkitVersion}: SMILES isomérico canónico",
                "scope": "Átomos, enlaces, cargas, isótopos, fragmentos y estereoquímica representada; sin desalinización."}
    except (ImportError, ValueError, RuntimeError, TypeError):
        return {"status": "unverifiable", "reason": "No se pudo comparar el dibujo con la referencia."}
