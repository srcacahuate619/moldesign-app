# -*- coding: utf-8 -*-
"""
test_molflex_curve_gate.py — Pruebas del gate corregido de la curva
D-MF-HARD (enmienda auditada 2026-08-16).

Solo stdlib; fixtures sinteticos de PDBQT. Ejecutar:

    python scripts/test_molflex_curve_gate.py

Imprime "OK  <prueba>" por cada prueba que pasa y un resumen final. Exit 0 si
todas pasan; exit 1 y detalle del fallo en caso contrario.

Cubre la enmienda auditada del gate:
  (a) 1 modelo emitido -> valido
  (b) 4 modelos emitidos -> valido; identidades SOLO para emitidos
      (sin model_idx fantasma 4..8)
  (c) 9 modelos emitidos -> valido
  (d) 0 modelos emitidos -> invalido (detencion)
  (e) >9 modelos emitidos -> invalido (detencion)
  (f) score no finito (nan/inf) -> invalido (detencion)
  (g) REMARK VINA RESULT ausente -> invalido (detencion)
  (h) geometria rota (coords no numericas) -> invalido (detencion)
  (i) scores EXCLUSIVAMENTE de REMARK VINA RESULT del archivo
  (j) formato real de Vina (ROOT/ENDROOT/TORSDOF + padding NUL) -> valido
  (k) out_valido: integracion con el work dir (gate corregido)
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import run_molflex_curve as rmc  # noqa: E402

PRUEBAS = []


def prueba(func):
    PRUEBAS.append(func)
    return func


def _atomo(serial, x, y, z, elem="C"):
    return (f"ATOM  {serial:5d}  {elem:<3s} UNL     1    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     0.220 {elem:<2s}")


def _fixture(n, score_fun=None, geom_roto=None, sin_remark=None,
             formato_real=False):
    """PDBQT sintetico con n bloques MODEL...ENDMDL.
    score_fun(i): score del modelo i (default -8.0 - i).
    geom_roto: indice de modelo con geometria rota.
    sin_remark: set de indices sin REMARK VINA RESULT."""
    lineas = []
    for i in range(n):
        lineas.append(f"MODEL {i + 1}")
        if i not in (sin_remark or set()):
            s = score_fun(i) if score_fun else -8.0 - i
            lineas.append(f"REMARK VINA RESULT: {s:8.3f}      0.000      0.000")
        if formato_real:
            lineas.append("ROOT")
        if geom_roto == i:
            lineas.append("ATOM  XX    C   UNL     1    ABCDEFG  1.000  "
                          "2.000  1.00  0.00     0.220 C ")
        else:
            lineas.append(_atomo(1, 7.0 + i, 11.0, 24.0))
            lineas.append(_atomo(2, 8.0 + i, 12.0, 25.0, "O"))
        if formato_real:
            lineas.append("ENDROOT")
            lineas.append("TORSDOF 0")
            lineas.append("\x00" * 51)
        lineas.append("ENDMDL")
    return "\n".join(lineas) + "\n"


@prueba
def t_1_modelo_valido():
    r = rmc.parse_vina_output(_fixture(1))
    assert r["ok"] is True, f"ok esperado True: {r}"
    assert r["n_models"] == 1, r
    assert r["models"][0]["score"] == -8.0, r
    assert r["errores"] == [], r
    assert len(r["models"][0]["atoms"]) == 2, r


@prueba
def t_4_modelos_validos_identidades_solo_emitidos():
    r = rmc.parse_vina_output(_fixture(4))
    assert r["ok"] is True, r
    assert r["n_models"] == 4, r
    scores = [m["score"] for m in r["models"]]
    assert scores == [-8.0, -9.0, -10.0, -11.0], r
    ids = {rmc.identidad_pose("1aaq", 3, m) for m in range(r["n_models"])}
    assert ids == {"train|1aaq|molflex|curve30_conf3.out|0",
                   "train|1aaq|molflex|curve30_conf3.out|1",
                   "train|1aaq|molflex|curve30_conf3.out|2",
                   "train|1aaq|molflex|curve30_conf3.out|3"}, ids
    # Nada de model_idx fantasma 4..8:
    fantasma = {rmc.identidad_pose("1aaq", 3, m) for m in range(4, 9)}
    assert not ids & fantasma, f"identidades fantasma: {ids & fantasma}"


@prueba
def t_9_modelos_validos():
    r = rmc.parse_vina_output(_fixture(9))
    assert r["ok"] is True, r
    assert r["n_models"] == 9, r


@prueba
def t_0_modelos_invalido():
    r = rmc.parse_vina_output("")
    assert r["ok"] is False, r
    assert r["n_models"] == 0, r
    assert any("gate:cero_modelos" in e for e in r["errores"]), r
    # Archivo con solo encabezados y sin atomos: tambien invalido.
    r2 = rmc.parse_vina_output("REMARK VINA RESULT:    -8.000      0.000      0.000\n")
    assert r2["ok"] is False, r2
    assert any("gate:sin_atomos" in e for e in r2["errores"]), r2


@prueba
def t_mas_de_9_modelos_invalido():
    r = rmc.parse_vina_output(_fixture(10))
    assert r["ok"] is False, r
    assert r["n_models"] == 10, r
    assert any("gate:mas_de_9_modelos" in e for e in r["errores"]), r


@prueba
def t_score_no_finito_invalido():
    r_nan = rmc.parse_vina_output(
        _fixture(3, score_fun=lambda i: [-8.0, float("nan"), -6.0][i]))
    assert r_nan["ok"] is False, r_nan
    assert any("gate:score_no_finito" in e for e in r_nan["errores"]), r_nan
    r_inf = rmc.parse_vina_output(
        _fixture(3, score_fun=lambda i: [-8.0, float("inf"), -6.0][i]))
    assert r_inf["ok"] is False, r_inf
    assert any("gate:score_no_finito" in e for e in r_inf["errores"]), r_inf


@prueba
def t_sin_remark_invalido():
    r = rmc.parse_vina_output(_fixture(2, sin_remark={1}))
    assert r["ok"] is False, r
    assert any("gate:sin_remark" in e for e in r["errores"]), r


@prueba
def t_geometria_rota_invalida():
    r = rmc.parse_vina_output(_fixture(2, geom_roto=1))
    assert r["ok"] is False, r
    assert any("gate:geometria_rota" in e for e in r["errores"]), r


@prueba
def t_scores_exclusivamente_remak():
    # El parser solo ve el archivo: el score de cada modelo DEBE ser el valor
    # exacto del REMARK (nunca una tabla stdout, que puede listar mas modos).
    r = rmc.parse_vina_output(
        _fixture(3, score_fun=lambda i: [-5.496, -4.799, -4.782][i]))
    assert [m["score"] for m in r["models"]] == [-5.496, -4.799, -4.782], r


@prueba
def t_formato_real_vina_con_padding_nul():
    r = rmc.parse_vina_output(_fixture(2, formato_real=True))
    assert r["ok"] is True, r
    assert r["n_models"] == 2, r
    assert len(r["models"][0]["atoms"]) == 2, r


@prueba
def t_out_valido_integracion_work_dir():
    work_original = rmc.WORK
    with tempfile.TemporaryDirectory(prefix="curve_gate_") as td:
        rmc.WORK = Path(td)
        try:
            (rmc.WORK / "1aaq").mkdir(parents=True)
            (rmc.WORK / "1aaq" / "curve30_conf0.out.pdbqt").write_text(
                _fixture(4), encoding="utf-8")
            assert rmc.out_valido("1aaq", 0) is True
            (rmc.WORK / "1aaq" / "curve30_conf1.out.pdbqt").write_text(
                _fixture(10), encoding="utf-8")
            assert rmc.out_valido("1aaq", 1) is False
            assert rmc.out_valido("1aaq", 2) is False  # inexistente
        finally:
            rmc.WORK = work_original


def main() -> int:
    fallos = 0
    for p in PRUEBAS:
        try:
            p()
            print(f"OK  {p.__name__}")
        except AssertionError as e:
            fallos += 1
            print(f"FAIL {p.__name__}: {e}")
        except Exception as e:
            fallos += 1
            print(f"ERROR {p.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(PRUEBAS) - fallos}/{len(PRUEBAS)} pruebas OK")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
