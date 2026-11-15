"""El cambio estructural de una fila SAR se mide del grafo, no se escribe a mano."""
from services.sar.cambio_estructural import cambio_estructural


def test_un_metilo_de_mas_sale_en_la_formula_y_el_nucleo_es_la_base():
    r = cambio_estructural("c1ccccc1O", "c1ccccc1OC")
    assert r is not None
    assert r["core_heavy_atoms"] == 7 and r["base_heavy_atoms"] == 7 and r["analog_heavy_atoms"] == 8
    assert {d["element"]: d["delta"] for d in r["formula_delta"]} == {"C": 1, "H": 2}
    assert r["core_complete"] is True


def test_molecula_identica_no_tiene_cambio():
    r = cambio_estructural("CCO", "CCO")
    assert r is not None and r["formula_delta"] == []


def test_smiles_invalido_o_ausente_no_inventa():
    assert cambio_estructural("no es smiles", "CCO") is None
    assert cambio_estructural(None, "CCO") is None
