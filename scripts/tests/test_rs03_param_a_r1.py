"""RS-03-PARAM-A-R1: el comparador de correspondencia atómica ve lo que tiene que ver (sin OpenFF)."""
from rdkit import Chem

import run_rs03_param_a_r1 as r


def _g(smiles):
    return r.grafo_rdkit(Chem.AddHs(Chem.MolFromSmiles(smiles)))


def test_identidad_no_tiene_diferencias():
    g = _g("CC(=O)Nc1ccc(O)cc1")
    assert r.diferencias(g, g) == []


def test_intercambio_de_carbonos_con_vecindario_distinto_se_ve():
    g = _g("CC(=O)Nc1ccc(O)cc1")
    i, j = r.par_mismo_elemento(g)
    assert g[0][i] == g[0][j]
    assert r.diferencias(g, r.permutar(g, i, j))


def test_intercambio_de_elementos_distintos_se_ve():
    g = _g("CCO")
    assert any("atomo" in d for d in r.diferencias(g, r.permutar(g, *r.par_distinto_elemento(g))))


def test_atomos_equivalentes_no_dan_par():
    # en el etano sin H los dos carbonos son simétricos: no hay control posible y se declara
    g = r.grafo_rdkit(Chem.MolFromSmiles("CC"))
    assert r.par_mismo_elemento(g) is None


def test_una_carga_formal_distinta_se_ve():
    a, e = _g("C[NH3+]")
    b = ([(z, 0) for z, _ in a], e)
    assert r.diferencias((a, e), b)


def test_resumir_decide_segun_el_preregistro():
    fila = {"pid": "x", "sdf_igual_al_sellado": True, "max_dif_carga_sellada": 0.0, "energia_finita": True,
            "dif_serializacion_kj_mol": 0.0, "correspondencia_fallos": [], "n_particulas": 3, "n_atomos": 3,
            "energia_kj_mol": 1.0, "controles_detectados": {"mismo_elemento": True, "distinto_elemento": True}}
    assert r.resumir([fila], [], 1, r.NAGL_SHA)["decision"] == "GO"
    assert r.resumir([dict(fila, correspondencia_fallos=["x"])], [], 1, r.NAGL_SHA)["decision"] == "NO_GO"
    assert r.resumir([fila], [], 1, "otro")["decision"] == "INCONCLUSIVE"
    assert r.resumir([dict(fila, controles_detectados={"mismo_elemento": False, "distinto_elemento": True})],
                     [], 1, r.NAGL_SHA)["decision"] == "INCONCLUSIVE"
