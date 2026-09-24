"""El validador de sellos para forks tiene que demostrar que ve (AGENTS.md, restricción 2).

Un guardián que aprobara todo pasaría en verde sobre un sello roto. Se le da un
árbol sintético con un fichero de cada clase y se comprueba que clasifica cada
uno como debe: lo alterado y lo ausente sin declarar son fallos; lo no
distribuido declarado y la divergencia con copia conservada, no.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import types
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _modulo():
    spec = importlib.util.spec_from_file_location("validar_sellos", RAIZ / "scripts" / "validar_sellos.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


@pytest.fixture
def arbol(tmp_path, monkeypatch):
    vs = _modulo()
    (tmp_path / "datos").mkdir()
    (tmp_path / "datos" / "bueno.txt").write_bytes(b"bueno\r\n")
    (tmp_path / "datos" / "alterado.txt").write_bytes(b"cambiado\n")
    (tmp_path / "datos" / "vivo.txt").write_bytes(b"version nueva\n")
    exp = tmp_path / "artifacts" / "EXP-1"
    (exp / "sellado_original" / "datos").mkdir(parents=True)
    (exp / "sellado_original" / "datos" / "vivo.txt").write_bytes(b"version sellada\n")
    manifest = {"sealed": True, "dataset_hashes": {
        "datos/bueno.txt": _sha(b"bueno\r\n"),
        "datos/alterado.txt": _sha(b"original\n"),
        "privado/pdbbind/1abc.pdb": _sha(b"no viaja"),
        "datos/perdido.txt": _sha(b"nadie lo tiene"),
        "datos/vivo.txt": _sha(b"version sellada\n"),
    }}
    (exp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    tabla = {"entradas": [{"prefijo": "privado/pdbbind/", "clase": "NO_REDISTRIBUIBLE", "motivo": "licencia",
                           "como_obtenerlo": "descargarlo"}],
             "divergencias_declaradas": [{"experimento": "EXP-1", "ruta": "datos/vivo.txt",
                                          "hash_sellado": _sha(b"version sellada\n"),
                                          "copia_conservada": "artifacts/EXP-1/sellado_original/datos/vivo.txt",
                                          "motivo": "prueba"}]}
    (tmp_path / "tabla.json").write_text(json.dumps(tabla), encoding="utf-8")

    real = vs._cargar_manifest_tool()
    falso = types.SimpleNamespace(
        _load_schema=lambda: {}, _validate=lambda *a: None, _git_toplevel=lambda: str(tmp_path),
        _resolve_stored_path=real._resolve_stored_path, _sha256_file=real._sha256_file)
    monkeypatch.setattr(vs, "_cargar_manifest_tool", lambda: falso)
    monkeypatch.setattr(vs, "ARTEFACTOS", tmp_path / "artifacts")
    monkeypatch.setattr(vs, "TABLA", tmp_path / "tabla.json")
    monkeypatch.setattr(vs, "RAIZ", tmp_path)
    return vs


def test_clasifica_cada_fichero_como_debe(arbol):
    totales, info = arbol.revisar()

    assert totales["VERIFICADO"] == 1
    assert totales["EN_COPIA"] == 1
    assert totales["NO_DISTRIBUIDO"] == 1
    assert totales["DISTINTO"] == 1
    assert totales["AUSENTE"] == 1
    assert sorted(info["fallos"]["EXP-1"]) == ["AUSENTE: datos/perdido.txt", "DISTINTO: datos/alterado.txt"]


def test_una_divergencia_sin_copia_valida_sigue_siendo_un_fallo(arbol):
    copia = arbol.RAIZ / "artifacts" / "EXP-1" / "sellado_original" / "datos" / "vivo.txt"
    copia.write_bytes(b"alguien toco la copia\n")

    _, info = arbol.revisar()

    assert "DISTINTO: datos/vivo.txt" in info["fallos"]["EXP-1"]


def test_el_repositorio_real_valida_entero():
    """La misma comprobación que la CI: los 167 sellos, desde este árbol."""
    totales, info = _modulo().revisar()

    assert not info["fallos"], f"sellos que no validan: {sorted(info['fallos'])[:10]}"
    assert totales["sellados"] >= 167
