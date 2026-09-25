"""Regresiones de identidad del receptor preparado (DOCK-001 y DOCK-004)."""

from __future__ import annotations

from services.docking.preparer import _filter_pdb_content, receptor_recipe_hash
from utils.file_handlers import StoragePath


def _atom(serial, name, residue, seq, altloc=" ", occupancy=1.0, icode=" "):
    return (
        f"ATOM  {serial:5d} {name:4s}{altloc}{residue:3s} A{seq:4d}{icode}   "
        f"{serial:8.3f}{0.0:8.3f}{0.0:8.3f}{occupancy:6.2f}{20.0:6.2f}           C"
    )


def test_altloc_conserva_atom_base_y_una_variante():
    lines = []
    for seq, residue, base, alternatives in (
        (110, "VAL", ("N", "CA", "C", "O", "CB"), ("CG1", "CG2")),
        (111, "SER", ("N", "CA", "C", "O", "CB"), ("OG",)),
    ):
        for name in base:
            lines.append(_atom(len(lines) + 1, name, residue, seq))
        for variant, occupancy in (("A", 0.6), ("B", 0.4)):
            for name in alternatives:
                lines.append(_atom(len(lines) + 1, name, residue, seq, variant, occupancy))
    result = _filter_pdb_content("\n".join(lines), "A")
    for seq, expected in ((110, {"N", "CA", "C", "O", "CB", "CG1", "CG2"}),
                          (111, {"N", "CA", "C", "O", "CB", "OG"})):
        atoms = [line for line in result.splitlines() if line.startswith("ATOM")
                 and int(line[22:26]) == seq]
        assert {line[12:16].strip() for line in atoms} == expected
        assert len(atoms) == len(expected)
        assert all(line[16] == " " for line in atoms)


def test_recipe_distingue_fuente_cadenas_caja_y_cofactores(monkeypatch):
    from services.docking import preparer

    monkeypatch.setattr(preparer.importlib.metadata, "version", lambda _: "0.7.1")
    base = dict(
        source_content="ATOM A",
        chains={"A", "B"},
        cofactors_whitelist=["HEM", "FE"],
        center=(10.0, 20.0, 30.0),
        size=(20.0, 20.0, 20.0),
    )
    original = receptor_recipe_hash(**base)
    assert len(original) == 64
    assert original == receptor_recipe_hash(**{**base, "chains": {"B", "A"},
                                               "cofactors_whitelist": ["FE", "HEM"]})
    for changed in (
        {"source_content": "ATOM B"},
        {"chains": {"A"}},
        {"cofactors_whitelist": ["FE"]},
        {"center": (11.0, 20.0, 30.0)},
        {"size": (21.0, 20.0, 20.0)},
    ):
        assert receptor_recipe_hash(**{**base, **changed}) != original
    assert StoragePath.target_prepared("5va1", original) != StoragePath.target_prepared(
        "5va1", receptor_recipe_hash(**{**base, "center": (11.0, 20.0, 30.0)})
    )



def test_residuo_perdido_en_la_caja_es_critico():
    from services.docking.preparer import _residuos_eliminados

    source = "\n".join([
        _atom(1, "CA", "LYS", 42),
        _atom(2, "CA", "ALA", 43),
    ])
    prepared = _atom(2, "CA", "ALA", 43)
    removed = _residuos_eliminados(
        source, prepared, center=(1.0, 0.0, 0.0), size=(20.0, 20.0, 20.0),
    )
    assert len(removed) == 1
    assert removed[0]["name"] == "LYS"
    assert removed[0]["site_critical"] is True
    assert removed[0]["distance_to_box_A"] == 0.0


def test_residuo_perdido_fuera_del_sitio_conserva_distancia():
    from services.docking.preparer import _residuos_eliminados

    removed = _residuos_eliminados(
        _atom(100, "CA", "ALA", 5), "",
        center=(0.0, 0.0, 0.0), size=(10.0, 10.0, 10.0),
    )
    assert removed[0]["site_critical"] is False
    assert removed[0]["distance_to_box_A"] == 95.0


def test_caja_dinamica_elige_copia_del_ligando_proxima_al_catalogo():
    from services.docking.preparer import source_for_dynamic_box

    protein = _atom(1, "CA", "ALA", 1)
    ligand_a = _atom(2, "C1", "LIG", 501).replace("ATOM  ", "HETATM", 1)
    ligand_b = _atom(3, "C1", "LIG", 501).replace("ATOM  ", "HETATM", 1)
    ligand_b = ligand_b[:21] + "B" + ligand_b[22:30] + f"{40.0:8.3f}" + ligand_b[38:]
    source = source_for_dynamic_box(
        "\n".join([protein, ligand_a, ligand_b]), {"A", "B"}, "LIG", (40.0, 0.0, 0.0),
    )
    hetatm = [line for line in source.splitlines() if line.startswith("HETATM")]
    assert len(hetatm) == 1
    assert hetatm[0][21] == "B"
    assert float(hetatm[0][30:38]) == 40.0
