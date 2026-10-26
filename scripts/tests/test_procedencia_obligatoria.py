"""SCI-B-045: un sello nuevo no puede quedar sin entradas, salidas ni versiones.

`experiment_manifest.py` está sellado como activo y no se toca; la regla vive en
`sellar_experimento.py`. Estas pruebas trabajan sobre un `ARTIFACTS_BASE` temporal, salvo la
última, que recorre los experimentos reales creados desde la fecha de corte.
"""
import json
from types import SimpleNamespace

import pytest

import sellar_experimento as se


@pytest.fixture()
def em(tmp_path):
    modulo = se._manifest_tool()
    modulo.ARTIFACTS_BASE = tmp_path / "artifacts_science"
    modulo.ARTIFACTS_BASE.mkdir()
    return modulo


def _init(em, exp_id="T-01"):
    assert em.main(["init", exp_id, "--hypothesis", "h", "--protocol", "p", "--gate", "g"]) == 0
    return em.ARTIFACTS_BASE / exp_id


def _sellar(em, exp_id, entradas=None, sin_entradas=None):
    args = SimpleNamespace(experiment_id=exp_id, entradas=entradas, sin_entradas=sin_entradas,
                           binarios=None, activos=None)
    return se.sellar(args, em)


def _cerrar(em, exp_id, decision="NO_GO"):
    args = SimpleNamespace(experiment_id=exp_id, decision=decision, razon="r", duracion_s=1.0, salidas=None)
    return se.cerrar(args, em)


def test_sellar_sin_entradas_ni_motivo_falla_y_no_sella(em):
    d = _init(em)
    assert _sellar(em, "T-01") == 1
    assert not json.loads((d / "manifest.json").read_text(encoding="utf-8")).get("sealed")
    assert not (d / se.PROCEDENCIA).exists()


def test_sellar_con_entradas_registra_hashes_y_paquetes(em, tmp_path):
    d = _init(em)
    entrada = tmp_path / "entrada.csv"
    entrada.write_text("a,b\n1,2\n", encoding="utf-8")
    assert _sellar(em, "T-01", entradas=[str(entrada)]) == 0
    p = json.loads((d / se.PROCEDENCIA).read_text(encoding="utf-8"))
    assert list(p["entradas"].values()) == [em._sha256_file(str(entrada))]
    assert p["paquetes"] and all("==" in x for x in p["paquetes"])
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    assert m["sealed"] is True and m["dataset_hashes"] == p["entradas"]


def test_un_motivo_declarado_sustituye_a_las_entradas(em):
    d = _init(em)
    assert _sellar(em, "T-01", sin_entradas="cálculo analítico, sin ficheros de entrada") == 0
    assert json.loads((d / se.PROCEDENCIA).read_text(encoding="utf-8"))["entradas_ausentes_motivo"]


def test_cerrar_exige_salidas_y_las_registra(em, tmp_path):
    d = _init(em)
    entrada = tmp_path / "e.txt"
    entrada.write_text("x", encoding="utf-8")
    assert _sellar(em, "T-01", entradas=[str(entrada)]) == 0
    assert _cerrar(em, "T-01") == 1                       # metrics.json sigue siendo {}
    (d / "metrics.json").write_text('{"n": 1}\n', encoding="utf-8")
    (d / "per_complex.jsonl").write_text('{"id": 1}\n', encoding="utf-8")
    assert _cerrar(em, "T-01") == 0
    p = json.loads((d / se.PROCEDENCIA).read_text(encoding="utf-8"))
    assert {k.rsplit("/", 1)[-1] for k in p["salidas"]} >= {"metrics.json", "per_complex.jsonl"}
    assert json.loads((d / "manifest.json").read_text(encoding="utf-8"))["decision"] == "NO_GO"
    assert se.comprobar("T-01", em) == []


def test_comprobar_ve_una_salida_cambiada(em, tmp_path):
    d = _init(em)
    entrada = tmp_path / "e.txt"
    entrada.write_text("x", encoding="utf-8")
    _sellar(em, "T-01", entradas=[str(entrada)])
    (d / "metrics.json").write_text('{"n": 1}\n', encoding="utf-8")
    _cerrar(em, "T-01")
    (d / "per_complex.jsonl").write_text('{"id": 2}\n', encoding="utf-8")
    assert any("otro hash" in f for f in se.comprobar("T-01", em))


def test_la_guarda_ve_un_sello_nuevo_sin_procedencia(em):
    d = _init(em, "T-NUEVO")
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    m.update(sealed=True, created_at="2026-10-24T00:00:00+00:00")
    (d / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
    viejo = _init(em, "T-VIEJO")
    mv = json.loads((viejo / "manifest.json").read_text(encoding="utf-8"))
    mv.update(sealed=True, created_at="2026-10-01T00:00:00+00:00")
    (viejo / "manifest.json").write_text(json.dumps(mv), encoding="utf-8")
    fallos = se.fallos_de_procedencia(em)
    assert any("T-NUEVO" in f for f in fallos)
    assert not any("T-VIEJO" in f for f in fallos)


def test_los_experimentos_reales_desde_el_corte_tienen_procedencia():
    assert se.fallos_de_procedencia() == []
