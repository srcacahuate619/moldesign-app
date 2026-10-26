"""Contact localization must be bound to the analyzed pose, not inferred from chemistry."""
import hashlib

import pytest
from rdkit import Chem

from services.interactions.analyzer import Interaction, InteractionReport, _fallback_analysis
from services.interactions.contact_map import build_contact_map


def pose(tmp_path, smiles="OCCO"):
    molecule = Chem.MolFromSmiles(smiles)
    conformer = Chem.Conformer(molecule.GetNumAtoms())
    for i in range(molecule.GetNumAtoms()):
        conformer.SetAtomPosition(i, (1.5*i, 0.0, 0.0))
    molecule.AddConformer(conformer)
    path = tmp_path / "pose.sdf"
    path.write_text(Chem.MolToMolBlock(molecule) + "\n$$$$\n", encoding="utf-8")
    return path, molecule


def contact(indices):
    return Interaction(type="polar_contact", residue_name="SER", residue_number=1,
                       residue_chain="A", ligand_atom="O0", protein_atom="OG",
                       distance=2.9, ligand_atom_indices=tuple(indices))


def report(path, *contacts):
    return InteractionReport("qa", "TEST", 1, interactions=list(contacts),
                             ligand_source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def test_only_named_oxygen_is_highlighted_and_pose_bytes_do_not_change(tmp_path):
    path, molecule = pose(tmp_path)
    original = path.read_bytes()
    data = build_contact_map(path, report(path, contact([0])))
    assert data["status"] == "ready"
    assert data["highlighted_atom_indices"] == [0]
    assert data["atoms"][0]["element"] == data["atoms"][3]["element"] == "O"
    assert path.read_bytes() == original
    assert len(data["atoms"]) == molecule.GetNumAtoms()
    assert data["svg_sha256"] == hashlib.sha256(data["svg"].encode()).hexdigest()


@pytest.mark.parametrize("indices", [[], [-1], [4000], [True], [0.5], [0, 4000]])
def test_missing_or_invalid_indices_never_paint_an_atom(tmp_path, indices):
    path, _ = pose(tmp_path)
    data = build_contact_map(path, report(path, contact(indices)))
    assert data["status"] == "ready"
    assert data["highlighted_atom_indices"] == []
    assert data["contacts"][0]["reason"] == "INVALID_OR_MISSING_INDICES"


def test_a_different_pose_hash_abstains_even_when_atom_counts_match(tmp_path):
    path, _ = pose(tmp_path)
    recorded = report(path, contact([0]))
    path.write_text(path.read_text().replace("0.0000", "9.0000", 1), encoding="utf-8")
    assert build_contact_map(path, recorded)["reason"] == "UNBOUND_ATOM_INDICES"


def test_whole_ring_group_is_localized_not_just_its_first_atom(tmp_path):
    path, _ = pose(tmp_path, "c1ccccc1")
    data = build_contact_map(path, report(path, contact(range(6))))
    assert data["highlighted_atom_indices"] == list(range(6))


def test_added_hydrogens_are_declared_without_moving_them_onto_another_atom(tmp_path):
    path, molecule = pose(tmp_path)
    added_h = molecule.GetNumAtoms()
    data = build_contact_map(path, report(path, contact([3, added_h]), contact([added_h])))
    assert data["highlighted_atom_indices"] == [3]
    assert data["contacts"][0]["hidden_hydrogen_indices"] == [added_h]
    assert data["contacts"][1]["atom_indices"] == []
    assert data["contacts"][1]["reason"] == "NO_DRAWABLE_ATOMS"


def test_reordering_equivalent_atoms_in_the_renderer_is_detected(tmp_path, monkeypatch):
    from rdkit.Chem.Draw import rdMolDraw2D
    path, _ = pose(tmp_path)
    prepare = rdMolDraw2D.PrepareMolForDrawing
    monkeypatch.setattr(rdMolDraw2D, "PrepareMolForDrawing",
                        lambda mol, **kw: Chem.RenumberAtoms(prepare(mol, **kw), [3, 2, 1, 0]))
    assert build_contact_map(path, report(path, contact([0])))["reason"] == "ATOM_MAPPING_CHANGED"


def test_distance_fallback_has_explicit_indices_without_claiming_hydrogen_bond(tmp_path):
    path, _ = pose(tmp_path, "O")
    pdb = tmp_path / "protein.pdb"
    pdb.write_text("ATOM      1  N   ALA A   1       2.900   0.000   0.000  1.00 20.00           N\n", encoding="utf-8")
    detected = _fallback_analysis(pdb, path, InteractionReport("qa", "TEST", 1))
    assert detected.engine == "distancias_sin_quimica"
    assert [c.type for c in detected.interactions] == ["polar_contact"]
    assert detected.interactions[0].ligand_atom_indices == (0,)
    assert detected.interactions[0].angle is None
    assert build_contact_map(path, detected)["highlighted_atom_indices"] == [0]


def test_producer_preserves_the_full_detector_group_and_zero_geometry(tmp_path, monkeypatch):
    import prolif
    from typing import NamedTuple
    from services.interactions.analyzer import analyze_complex
    class Residue(NamedTuple):
        name: str
        number: int
        chain: str
    class Fingerprint:
        def __init__(self, _types, *, count):
            assert count is False
        def generate(self, _ligand, _protein, *, metadata):
            assert metadata
            return {(None, Residue("TYR", 1, "A")): {"PiStacking": ({
                "parent_indices": {"ligand": tuple(range(6)), "protein": (0,)},
                "distance": 3.6, "plane_angle": 0.0},)}}
    monkeypatch.setattr(prolif, "Fingerprint", Fingerprint)
    path, _ = pose(tmp_path, "c1ccccc1")
    receptor = Chem.MolFromSmiles("CC")
    conformer = Chem.Conformer(2);conformer.SetAtomPosition(0, (0,0,3.6));conformer.SetAtomPosition(1, (1.5,0,3.6));receptor.AddConformer(conformer)
    pdb = tmp_path / "receptor.pdb"
    pdb.write_text(Chem.MolToPDBBlock(receptor).replace("HETATM", "ATOM  "), encoding="utf-8")
    detected = analyze_complex(pdb, path)
    assert detected.engine.startswith("prolif:")
    assert detected.interactions[0].ligand_atom_indices == tuple(range(6))
    assert detected.interactions[0].geometry["plane_angle"] == 0.0
    assert build_contact_map(path, detected)["highlighted_atom_indices"] == list(range(6))


def test_large_depictions_abstain_without_losing_the_contact_report(tmp_path):
    path, _ = pose(tmp_path, "C"*251)
    detected = report(path, contact([0]))
    assert build_contact_map(path, detected)["reason"] == "TOO_MANY_ATOMS_FOR_2D"
    assert len(detected.interactions) == 1
