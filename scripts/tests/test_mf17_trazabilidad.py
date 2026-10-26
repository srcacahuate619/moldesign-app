"""SCI-B-101 y SCI-B-102: MF-17 contra sus fuentes selladas."""
import analisis_mf17_trazabilidad as a


def test_un_r50_distinto_se_ve():
    r = a.comparar_r50({"x": {"r50": 2.0}, "y": {"r50": None}}, {"x": {"r50": 3.0}})
    assert r["distintos"] == [("x", 2.0, 3.0)] and r["faltan_en_mf14"] == ["y"]


def test_mf17_uso_el_mismo_r50_que_mf14_sellado():
    r = a.analizar()
    assert r["r50_contra_mf14_sellado"] == {"iguales": 48, "distintos": [], "faltan_en_mf14": []}
    assert set(r["pids_de_mf09_ausentes_por_fuente"].values()) == {0}
    assert r["n_por_mecanismo"]["RESUELTO"]["rho_embudo"] == 16
    assert r["n_por_mecanismo"]["FALLA"]["r50"] == 26
