from __future__ import annotations

import sys

import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

SIDECAR = "backend/sidecars/esmfold"
if SIDECAR not in sys.path:
    sys.path.insert(0, SIDECAR)

from ligand_transfer import (  # noqa: E402
    TransferenciaPeptidicaError,
    transferir_coordenadas,
)


def _pdb_sin_oxt(sequence: str) -> str:
    mol = Chem.MolFromFASTA(sequence)
    assert mol is not None
    assert AllChem.EmbedMolecule(mol, randomSeed=42) >= 0
    return "\n".join(
        line for line in Chem.MolToPDBBlock(mol).splitlines()
        if line[12:16].strip() != "OXT"
    )


def test_transfiere_coordenadas_al_grafo_y_completa_oxt():
    smiles = "C[C@H](N)C(=O)N[C@@H](C)C(=O)N[C@@H](C)C(O)=O"
    resultado = transferir_coordenadas(smiles, _pdb_sin_oxt("AAA"))

    assert resultado.mol.GetNumAtoms() == 16
    assert len(Chem.GetMolFrags(resultado.mol)) == 1
    assert Chem.MolToSmiles(resultado.mol, isomericSmiles=True) == Chem.MolToSmiles(
        Chem.MolFromSmiles(smiles), isomericSmiles=True
    )
    assert resultado.manifest["coordinates_transferred"] == 15
    assert resultado.manifest["coordinates_completed"] == 1
    assert "OXT" in resultado.manifest["completed_atom_names"]
    assert resultado.manifest["completion_method"] == "rdkit_constrained_v1"
    assert resultado.manifest["status"] == "completed"
    assert len(resultado.manifest["input_graph_hash"]) == 64
    assert resultado.manifest["input_graph_hash"] == resultado.manifest["output_graph_hash"]


def test_rechaza_estereoquimica_ambigua_y_peptido_d():
    with pytest.raises(TransferenciaPeptidicaError) as ambiguous:
        transferir_coordenadas(
            "CC(N)C(=O)NCC(O)=O",
            _pdb_sin_oxt("AA"),
        )
    assert ambiguous.value.code == "AMBIGUOUS_STEREOCHEMISTRY"

    with pytest.raises(TransferenciaPeptidicaError) as d_peptide:
        transferir_coordenadas(
            "C[C@@H](N)C(=O)N[C@@H](C)C(O)=O",
            _pdb_sin_oxt("AA"),
        )
    assert d_peptide.value.code == "D_PEPTIDE_UNSUPPORTED"


def test_no_infiere_enlaces_si_falta_backbone():
    pdb = _pdb_sin_oxt("AAA")
    pdb = "\n".join(line for line in pdb.splitlines() if line[12:16].strip() != "CA")
    with pytest.raises(TransferenciaPeptidicaError) as error:
        transferir_coordenadas(
            "C[C@H](N)C(=O)N[C@@H](C)C(=O)N[C@@H](C)C(O)=O",
            pdb,
        )
    assert error.value.code == "ATOM_MAPPING_INCOMPLETE"


def test_la_pose_de_vina_reutiliza_el_grafo_del_smiles():
    sys.path.insert(0, SIDECAR)
    try:
        from predictor import ESMFoldFastPredictor
    finally:
        sys.path.pop(0)

    smiles = "C[C@H](N)C(=O)N[C@@H](C)C(O)=O"
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None
    mol = Chem.AddHs(mol)
    assert AllChem.EmbedMolecule(mol, randomSeed=42) >= 0
    pdbqt = "MODEL 1\n" + "".join(
        line + "\n"
        for line in Chem.MolToPDBBlock(mol).splitlines()
        if line.startswith(("ATOM", "HETATM")) and line[12:16].strip() != "H"
    ) + "ENDMDL\n"
    sdf = ESMFoldFastPredictor._pose_sdf_from_pdbqt(mol, pdbqt)
    assert sdf is not None
    recovered = Chem.MolFromMolBlock(sdf, sanitize=False, removeHs=False)
    assert recovered is not None
    Chem.SanitizeMol(recovered)
    assert Chem.MolToSmiles(Chem.RemoveHs(recovered), isomericSmiles=True) == Chem.MolToSmiles(
        Chem.MolFromSmiles(smiles), isomericSmiles=True
    )
    assert recovered.GetNumHeavyAtoms() == mol.GetNumHeavyAtoms()


def test_el_mapa_de_meeko_no_intercambia_atomos_de_la_pose():
    sys.path.insert(0, SIDECAR)
    try:
        from predictor import ESMFoldFastPredictor
    finally:
        sys.path.pop(0)
    from meeko import MoleculePreparation, PDBQTWriterLegacy

    mol = Chem.AddHs(Chem.MolFromSmiles("C[C@H](N)C(=O)N[C@@H](C)C(O)=O"))
    assert AllChem.EmbedMolecule(mol, randomSeed=42) >= 0
    pdbqt = PDBQTWriterLegacy.write_string(
        MoleculePreparation().prepare(mol)[0]
    )[0]
    atom_map = ESMFoldFastPredictor._pdbqt_heavy_index_map(pdbqt, mol)
    model = "MODEL 1\n" + "\n".join(
        line for line in pdbqt.splitlines()
        if line.startswith(("ATOM", "HETATM"))
        and line[12:16].strip() != "H"
    ) + "\nENDMDL\n"

    sdf = ESMFoldFastPredictor._pose_sdf_from_pdbqt(mol, model, atom_map)
    assert sdf is not None
    recovered = Chem.MolFromMolBlock(sdf, sanitize=False, removeHs=False)
    assert recovered is not None
    Chem.SanitizeMol(recovered)
    assert recovered.GetNumAtoms() == mol.GetNumHeavyAtoms()

    expected = {}
    for line in model.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        expected[int(line[6:11])] = tuple(
            float(line[start:start + 8]) for start in (30, 38, 46)
        )
    conf = recovered.GetConformer()
    source_conf = mol.GetConformer()
    for serial, atom_idx in atom_map.items():
        actual = conf.GetAtomPosition(atom_idx)
        assert (actual.x, actual.y, actual.z) == pytest.approx(expected[serial])
        source = source_conf.GetAtomPosition(atom_idx)
        assert (actual.x, actual.y, actual.z) == pytest.approx(
            (source.x, source.y, source.z), abs=1.0e-3
        )