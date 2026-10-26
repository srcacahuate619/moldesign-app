"""SCI-B-088 y SCI-B-092: qué radios de MF-15 y MF-15-EXT se pueden leer.

Fija, sobre las salidas selladas, que en el estrato difícil no hay ningún complejo medible a
2 Å o menos, que a 3 Å hay dos, y que el conjunto que contribuye cambia con el radio: la
secuencia de medianas no es una curva pareada. Si una regeneración de los artefactos
cambiara esa cobertura, las correcciones de los papers habría que revisarlas.
"""
import json
import shutil

import analisis_mf15_cobertura_por_radio as mf15


def test_cobertura_del_estrato_dificil(raiz_del_repositorio):
    salida = mf15.analizar(raiz_del_repositorio)
    for exp in ("MF-15", "MF-15-EXT"):
        dificil = salida[exp]["COLOCACION"]
        assert dificil["complejos"] == 33
        assert dificil["radios_sin_complejos_medibles"] == ["2.0"]
        assert dificil["por_radio"]["3.0"]["medibles"] == 2
        assert dificil["medibles_en_todos_los_radios_con_medida"] == 2
    # Las cifras de la tabla por radios del paper de MF-15-EXT, con su cobertura.
    ext = salida["MF-15-EXT"]["COLOCACION"]["por_radio"]
    assert (ext["4.0"]["medibles"], ext["4.0"]["rho_mediana"]) == (11, 0.279)
    assert (ext["6.0"]["medibles"], ext["6.0"]["rho_mediana"]) == (27, 0.14)


def test_el_control_si_tiene_radios_cortos(raiz_del_repositorio):
    salida = mf15.analizar(raiz_del_repositorio)
    assert salida["MF-15"]["CONTROL"]["por_radio"]["2.0"]["medibles"] == 8


def test_control_negativo_una_rho_a_dos_angstrom_se_ve(raiz_del_repositorio, tmp_path):
    ruta, campo = mf15.FUENTES["MF-15"]
    for exp, (r, _) in mf15.FUENTES.items():
        destino = tmp_path / r
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raiz_del_repositorio / r, destino)
    filas = [json.loads(l) for l in (tmp_path / ruta).read_text(encoding="utf-8").splitlines() if l.strip()]
    objetivo = next(f for f in filas if f["estrato"] == "COLOCACION")
    objetivo[campo]["2.0"] = {"n": 9, "rho": 0.5}
    (tmp_path / ruta).write_text("".join(json.dumps(f) + "\n" for f in filas), encoding="utf-8")

    dificil = mf15.analizar(tmp_path)["MF-15"]["COLOCACION"]
    assert dificil["radios_sin_complejos_medibles"] == []
    assert dificil["por_radio"]["2.0"]["medibles"] == 1
