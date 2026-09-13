"""The stacking gate must prove that it detects the failures it names."""
from __future__ import annotations

import json
from pathlib import Path

import check_stacking_weights_ui as gate


def test_current_contract_is_consistent():
    assert gate.comparar() == []


def test_gate_detects_an_unsealed_registry_edit(tmp_path, monkeypatch):
    data = json.loads(gate.REGISTRY.read_text(encoding="utf-8"))
    data["parameters"]["stacking_default"]["versions"][0]["value"]["clgnn"] = 0.2
    broken = tmp_path / "registry.json"
    broken.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(gate, "REGISTRY", broken)
    problems = gate.validar_contrato_canonico(set(gate.pesos_de_la_interfaz()))
    assert any("re-sellar" in problem for problem in problems)


def test_gate_detects_checkpoint_bytes_different_from_manifest(tmp_path, monkeypatch):
    broken = tmp_path / "gnn_v2_cl_best.pt"
    broken.write_bytes(b"not-the-released-checkpoint")
    monkeypatch.setattr(gate, "MODELO_CLGNN", broken)
    problems = gate.validar_contrato_canonico(set(gate.pesos_de_la_interfaz()))
    assert any("SHA CL-GNN" in problem for problem in problems)