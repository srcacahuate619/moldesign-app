"""SCI-B-076: el GO de MF-12 se decide con el intervalo de la precisión balanceada.

El runner sellado pasó al bootstrap la diferencia de aciertos (exactitud). Estas pruebas
fijan que las predicciones de valtest se recuperan del propio `per_complex.jsonl` sellado
(se reproduce todo lo que el sello publica) y que el IC del estimando prerregistrado es
otro, aunque también excluye el cero.

Leen los artefactos sellados sin escribirlos; el control negativo trabaja sobre una copia.
"""
import json
import math
import shutil

import analisis_mf12_ci_balanceada as mf12


def test_precision_balanceada_y_su_indefinicion():
    assert mf12.precision_balanceada([True, True, False, False], [True, False, False, False]) == 0.75
    assert math.isnan(mf12.precision_balanceada([True, True], [True, False]))
    # El baseline mayoritario vale 0,5 por construcción.
    assert mf12.diferencia_balanceada([(True, True, True), (False, False, True)]) == 0.5


def test_reproduce_mf12_y_da_el_ic_prerregistrado(raiz_del_repositorio):
    salida = mf12.analizar(raiz_del_repositorio)
    for nivel in ("L", "L+S"):
        assert all(salida[nivel]["reproduce_lo_sellado"].values()), nivel
    l = salida["L"]
    assert l["n_valtest"] == 87
    assert l["dif_precision_balanceada"] == 0.1536
    assert l["ci95_bca_precision_balanceada"] == [0.0493, 0.2446]
    assert l["excluye_cero"] is True
    # El intervalo publicado es otro: el de la diferencia de exactitud.
    assert l["ci95_bca_precision_balanceada"] != l["ci95_bca_exactitud_sellado"]


def test_control_negativo_un_desenlace_cambiado_rompe_la_reproduccion(raiz_del_repositorio, tmp_path):
    for nombre in ("per_complex.jsonl", "metrics.json"):
        destino = tmp_path / mf12.MF12 / nombre
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raiz_del_repositorio / mf12.MF12 / nombre, destino)
    fuente = tmp_path / mf12.MF12 / "per_complex.jsonl"
    filas = [json.loads(l) for l in fuente.read_text(encoding="utf-8").splitlines() if l.strip()]
    for r in filas:
        if r["split"] == "train":
            r["convierte"] = not r["convierte"]
            break
    fuente.write_text("".join(json.dumps(r) + "\n" for r in filas), encoding="utf-8")

    salida = mf12.analizar(tmp_path)
    assert not all(salida["L"]["reproduce_lo_sellado"].values())
