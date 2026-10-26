"""La puerta de importancia Vina exige que el SHAP sea del modelo distribuido (SCI-A-056).

`shap_analysis.json` no declara qué modelo explica y se calculó sobre 692/173
muestras; el modelo distribuido se entrenó con 429/108. La puerta daba PASS con la
cuota de otro modelo. Ahora, sin el SHA-256 del modelo dentro del SHAP, el veredicto
es NO_VERIFICABLE (exit 3), y `--permitir-no-verificable` sale con 0 diciéndolo.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_vina_importance_gate.py"


@pytest.fixture()
def gate(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("check_vina_importance_gate", _SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modelo = tmp_path / "model_a_universal.json"
    modelo.write_text('{"learner": "sintetico"}', encoding="utf-8")
    informe = tmp_path / "training_report.json"
    informe.write_text(json.dumps({
        "training_context": {"feature_set_definition": "B=4"},
        "models": {"model_a_universal": {"n_train": 429, "n_val": 108}},
    }), encoding="utf-8")
    monkeypatch.setattr(modulo, "MODEL_PATH", modelo)
    monkeypatch.setattr(modulo, "TRAINING_REPORT_PATH", informe)
    monkeypatch.setattr(modulo, "SHAP_PATH", tmp_path / "shap_analysis.json")
    modulo.sha_del_modelo = hashlib.sha256(modelo.read_bytes()).hexdigest()
    return modulo


def _correr(gate, monkeypatch, capsys, shap: dict, *argumentos: str) -> tuple[int, dict]:
    gate.SHAP_PATH.write_text(json.dumps(shap), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["check_vina_importance_gate.py", *argumentos])
    codigo = gate.main()
    return codigo, json.loads(capsys.readouterr().out)


_CUOTA_BAJA = {"group_importance": {"Vina (B)": 0.09, "Shell (D)": 1.96, "ECIF (E)": 0.95},
               "n_samples_train": 692, "n_samples_val": 173}


def test_sin_el_hash_del_modelo_no_es_pass(gate, monkeypatch, capsys):
    codigo, informe = _correr(gate, monkeypatch, capsys, _CUOTA_BAJA)
    assert codigo == 3
    assert informe["verdict"] == "NO_VERIFICABLE"
    assert informe["binding"]["samples"] == {"shap_train_val": [692, 173], "model_train_val": [429, 108]}


def test_la_bandera_sale_con_cero_pero_lo_dice(gate, monkeypatch, capsys):
    codigo, informe = _correr(gate, monkeypatch, capsys, _CUOTA_BAJA, "--permitir-no-verificable")
    assert codigo == 0
    assert informe["verdict"] == "NO_VERIFICABLE"


def test_con_el_hash_de_otro_modelo_tampoco(gate, monkeypatch, capsys):
    codigo, informe = _correr(gate, monkeypatch, capsys, {**_CUOTA_BAJA, "model_sha256": "0" * 64})
    assert (codigo, informe["verdict"]) == (3, "NO_VERIFICABLE")


def test_ligado_al_modelo_decide_por_la_cuota(gate, monkeypatch, capsys):
    ligado = {**_CUOTA_BAJA, "model_sha256": gate.sha_del_modelo}
    assert _correr(gate, monkeypatch, capsys, ligado)[0] == 0
    alta = {**ligado, "group_importance": {"Vina (B)": 1.0, "Shell (D)": 1.0}}
    codigo, informe = _correr(gate, monkeypatch, capsys, alta, "--permitir-no-verificable")
    assert (codigo, informe["verdict"]) == (1, "FAIL")      # la bandera no tapa un FAIL


def test_los_artefactos_versionados_hoy_no_estan_ligados():
    """El estado real del árbol: si alguien recalcula el SHAP ligado, esta prueba avisa."""
    artefactos = _SCRIPT.parents[1] / "artifacts"
    shap = json.loads((artefactos / "shap_analysis.json").read_text(encoding="utf-8"))
    assert "model_sha256" not in shap
    assert [shap["n_samples_train"], shap["n_samples_val"]] == [692, 173]
