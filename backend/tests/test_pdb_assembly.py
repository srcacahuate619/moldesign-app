"""Contrato del ensamblado PDB local para el visor de resultados."""

from __future__ import annotations

from rdkit import Chem
from rdkit.Chem import AllChem

from services.docking.pdb_assembly import merge_protein_ligand_pdb


def _ligand_sdf() -> str:
    molecule = Chem.AddHs(Chem.MolFromSmiles("CCO"))
    assert AllChem.EmbedMolecule(molecule, randomSeed=7) == 0
    return Chem.MolToMolBlock(molecule) + "\n$$$$\n"


def test_merge_preserves_receptor_and_offsets_ligand_serials():
    protein = (
        "ATOM      7  CA  ALA A   1       1.000   2.000   3.000  1.00 20.00           C\n"
        "END\n"
    )

    assembled = merge_protein_ligand_pdb(protein, _ligand_sdf())

    assert assembled.startswith("ATOM      7")
    assert assembled.endswith("END\n")
    ligand_atoms = [line for line in assembled.splitlines() if line.startswith("HETATM")]
    assert ligand_atoms
    assert all(int(line[6:11]) > 7 for line in ligand_atoms)
    assert all(line[17:20] == "LIG" and line[21] == "L" for line in ligand_atoms)


def test_merge_returns_empty_when_pose_is_not_parseable():
    assert merge_protein_ligand_pdb("ATOM      1  N   ALA A   1\n", "not-an-sdf") == ""
