"""SCORE-015 / PROV-005: la ausencia de xTB no genera números."""
from __future__ import annotations

import hashlib
import importlib
import inspect
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from services.docking import queue_handler


def _modulo():
    return importlib.import_module("compute_quantum_features")


def test_sin_xtb_no_hay_score_ni_fila_de_cache(monkeypatch, tmp_path):
    quantum = _modulo()
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(quantum, "_find_xtb", lambda: None)
    assert quantum.compute_quantum_score("c1ccccc1") is None
    path = quantum.quantum_cache_path()
    if path.exists():
        with sqlite3.connect(path) as conn:
            assert conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 0


def test_la_clave_de_cache_nueva_no_reutiliza_valor_legacy(monkeypatch, tmp_path):
    quantum = _modulo()
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    path = quantum.quantum_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE cache (key TEXT PRIMARY KEY, score REAL, ts REAL)")
        old_key = hashlib.sha256(b"c1ccccc1").hexdigest()
        conn.execute("INSERT INTO cache VALUES (?, ?, ?)", (old_key, 0.3872, 0.0))
    monkeypatch.setattr(quantum, "_find_xtb", lambda: None)
    assert quantum.compute_quantum_score("c1ccccc1") is None


def test_os_es_import_global_en_legacy():
    function = inspect.unwrap(queue_handler._run_full_evaluation_async)
    assert "os" not in function.__code__.co_varnames


def test_xtb_recibe_carga_formal_del_smiles(monkeypatch, tmp_path):
    from types import SimpleNamespace

    quantum = _modulo()
    monkeypatch.setattr(quantum, "_find_xtb", lambda: "xtb-falso")
    monkeypatch.setattr(quantum, "_get_xtb_home", lambda: str(tmp_path))
    llamada = {}

    def fake_run(cmd, **kwargs):
        llamada["cmd"] = cmd
        return SimpleNamespace(returncode=1, stdout=b"")

    monkeypatch.setattr(quantum.subprocess, "run", fake_run)
    quantum.compute_xtb_features("CC(=O)[O-]")
    cmd = llamada["cmd"]
    assert cmd[cmd.index("--chrg") + 1] == "-1"
