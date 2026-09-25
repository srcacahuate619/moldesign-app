import pytest

from services.chemistry.protein_surgery import metal_features


@pytest.mark.parametrize(
    ("smiles", "feature", "expected"),
    [
        ("NS(=O)(=O)c1ccccc1", "sulfonamide_count", 1),
        ("[NH-]S(=O)(=O)c1ccccc1", "sulfonamide_count", 1),
        ("CN(C)S(=O)(=O)c1ccccc1", "sulfonamide_count", 0),
        ("CC(=O)O", "carboxylate_count", 1),
        ("CC(=O)[O-]", "carboxylate_count", 1),
        ("NC(=O)O", "carboxylate_count", 0),
        ("CS", "thiol_count", 1),
        ("C[S-]", "thiol_count", 1),
        ("CC(=O)NO", "hydroxamic_acid_count", 1),
        ("CC(=O)N[O-]", "hydroxamic_acid_count", 1),
        ("Cn1ccnc1", "imidazole_count", 1),
        ("c1ncc[nH]1", "imidazole_count", 1),
        ("CNS(=O)(=O)c1ccccc1", "sulfonamide_count", 1),
        ("NS(=O)(=O)C", "sulfonamide_count", 1),
        ("CN(C)S(=O)(=O)C", "sulfonamide_count", 0),
        ("CS(=O)(=O)C", "sulfonamide_count", 0),
        ("O=C(O)c1ccccc1", "carboxylate_count", 1),
        ("O=C([O-])c1ccccc1", "carboxylate_count", 1),
        ("CC(=O)OC", "carboxylate_count", 0),
        ("NC(=O)[O-]", "carboxylate_count", 0),
        ("c1ccccc1S", "thiol_count", 1),
        ("CCSCC", "thiol_count", 0),
        ("O=CN(O)C", "hydroxamic_acid_count", 1),
        ("CC(=O)N(C)O", "hydroxamic_acid_count", 1),
        ("c1ccc2[nH]cnc2c1", "imidazole_count", 1),
        ("c1ccncc1", "imidazole_count", 0),
    ],
)
def test_metal_binding_diagnostic_groups(smiles, feature, expected):
    assert metal_features(smiles)[feature] == expected
