"""SCI-B-096: MF-16-R1 se reconstruye desde la salida sellada de MF-10.

El manifiesto de MF-16-R1 sella el runner de punto único de MF-16, que no produce sus
cifras. Estas pruebas fijan que `analisis_mf16_r1_desde_mf10.py` sí las produce, fila a
fila y en el resumen, y que la comparación ve un cambio de una sola energía.

Leen los artefactos sellados sin escribirlos; el control negativo trabaja sobre una copia.
"""
import json
import shutil

import analisis_mf16_r1_desde_mf10 as r1


def test_spearman_promedia_empates_y_exige_ocho_poses():
    assert r1.spearman([1, 2, 3], [1, 2, 3]) is None
    assert r1.spearman(list(range(8)), list(range(8))) == 1.0
    assert r1.spearman(list(range(8)), list(range(8))[::-1]) == -1.0
    # Con empates en las dos series, igual que scipy.stats.spearmanr (rangos medios).
    assert r1.spearman([1, 1, 2, 3, 4, 5, 6, 7], [7, 6, 5, 4, 3, 2, 1, 1]) == -0.988


def test_reconstruye_r1_entero_desde_mf10(raiz_del_repositorio):
    informe = r1.comprobar(raiz_del_repositorio)
    assert informe["filas_selladas"] == 38
    assert informe["filas_reconstruidas"] == 38
    assert informe["filas_distintas"] == []
    assert informe["solo_en_sellado"] == []
    assert informe["solo_reconstruidas"] == []
    assert informe["resumen_coincide"] is True


def test_relajado_usa_el_rmsd_despues_de_relajar(raiz_del_repositorio):
    """Con el RMSD de antes la ρ relajada no coincide: R1 compara objetos distintos, y lo declara."""
    complejos = r1._jsonl(raiz_del_repositorio / r1.MF10)
    sellado = {f["pid"]: f for f in r1._jsonl(raiz_del_repositorio / r1.R1 / "per_complex.jsonl")}
    coinciden_con_antes = sum(
        1 for c in complejos if c["pid"] in sellado
        and r1._rho(c["poses"], "rmsd_antes", "energia_despues") == sellado[c["pid"]]["rho_ff_relajado"])
    assert coinciden_con_antes < len(sellado) // 2


def test_control_negativo_una_energia_cambiada_se_detecta(raiz_del_repositorio, tmp_path):
    for rel in (r1.MF10, r1.R1 / "per_complex.jsonl", r1.R1 / "metrics.json"):
        destino = tmp_path / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(raiz_del_repositorio / rel, destino)
    fuente = tmp_path / r1.MF10
    filas = [json.loads(l) for l in fuente.read_text(encoding="utf-8").splitlines() if l.strip()]
    objetivo = next(f for f in filas if f["pid"] == "10gs")
    peor = max(objetivo["poses"], key=lambda p: p["energia_despues"])
    peor["energia_despues"] = -1e9
    fuente.write_text("".join(json.dumps(f) + "\n" for f in filas), encoding="utf-8")

    informe = r1.comprobar(tmp_path)
    assert "10gs" in informe["filas_distintas"]
    assert informe["resumen_coincide"] is False
