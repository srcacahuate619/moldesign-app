"""MF-33-EXT-MOD-R1: la reproducción ve diferencias y la decisión sigue el preregistro."""
import run_mf33extmod_r1 as r


def test_la_reproduccion_ve_un_valor_distinto():
    sellado = {"x": {"torsdof": 3, "rot_bonds": 2, "n_heavy": 10, "diversidad": 1.0}}
    assert r.reproduccion({"x": dict(sellado["x"])}, sellado) == []
    assert r.reproduccion({"x": dict(sellado["x"], diversidad=1.001)}, sellado)
    assert r.reproduccion({"x": dict(sellado["x"], torsdof=4)}, sellado)


def test_decision_segun_el_preregistro():
    nada = {k: {} for k in r.CUATRO + ["n_conformeros"]}
    assert r.decidir(True, True, nada) == "NO_GO"
    assert r.decidir(True, True, dict(nada, rot_bonds={"significativo_tras_FDR": True})) == "GO"
    # n_conformeros solo no cuenta: está confundido con la dosis
    assert r.decidir(True, True, dict(nada, n_conformeros={"significativo_tras_FDR": True})) == "NO_GO"
    assert r.decidir(False, True, dict(nada, rot_bonds={"significativo_tras_FDR": True})) == "INCONCLUSIVE"
