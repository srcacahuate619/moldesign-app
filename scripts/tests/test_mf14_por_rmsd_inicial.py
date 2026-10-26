"""SCI-B-083: el radio nominal de MF-14 no es el RMSD de partida.

Fija, sobre las réplicas selladas, que con r = 0,5 Å la mediana del RMSD de partida es
0,935 Å en el estrato difícil, y lo que queda de la lectura de «rugosidad» al agrupar por el
RMSD real: por debajo de 0,75 Å no vuelven 14 de 74 réplicas, y salen de 5 de 30 complejos.
"""
import json
import shutil

import analisis_mf14_por_rmsd_inicial as mf14


def test_el_radio_nominal_no_es_el_rmsd_de_partida(raiz_del_repositorio):
    dificil = mf14.analizar(raiz_del_repositorio)["COLOCACION"]
    medio = dificil["por_r_nominal"]["0.5"]
    assert medio["replicas"] == 198
    assert medio["fraccion_vuelve"] == 0.778
    assert medio["rmsd_inicial_mediano"] == 0.935
    assert medio["rmsd_inicial_max"] > 2.5


def test_por_debajo_de_075_el_fallo_se_concentra_en_pocos_complejos(raiz_del_repositorio):
    salida = mf14.analizar(raiz_del_repositorio)
    cerca = salida["COLOCACION"]["por_rmsd_inicial"]["0-0.75"]
    assert (cerca["replicas"], cerca["vuelven"]) == (74, 60)
    assert (cerca["complejos"], cerca["complejos_con_algun_fallo"]) == (30, 5)
    control = salida["CONTROL"]["por_rmsd_inicial"]["0-0.75"]
    assert (control["replicas"], control["vuelven"], control["complejos_con_algun_fallo"]) == (58, 55, 1)


def test_las_bandas_cubren_todas_las_replicas(raiz_del_repositorio):
    salida = mf14.analizar(raiz_del_repositorio)
    for est in ("COLOCACION", "CONTROL"):
        assert sum(b["replicas"] for b in salida[est]["por_rmsd_inicial"].values()) == salida[est]["replicas"]


def test_control_negativo_un_rmsd_de_partida_cambiado_se_ve(raiz_del_repositorio, tmp_path):
    destino = tmp_path / mf14.MF14
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(raiz_del_repositorio / mf14.MF14, destino)
    filas = [json.loads(l) for l in destino.read_text(encoding="utf-8").splitlines() if l.strip()]
    for f in filas:
        if f["estrato"] == "COLOCACION":
            for p in f["puntos"]:
                if p["r_nominal"] == 0.5:
                    p["rmsd_inicial"] = 0.5
    destino.write_text("".join(json.dumps(f) + "\n" for f in filas), encoding="utf-8")
    assert mf14.analizar(tmp_path)["COLOCACION"]["por_r_nominal"]["0.5"]["rmsd_inicial_mediano"] == 0.5
