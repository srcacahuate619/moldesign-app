"""Un enlace a un documento retenido del público no es un enlace roto; uno roto sí.

La CI del repositorio público fallaba en 23 enlaces a manuscritos retenidos por
decisión (scripts/retenidos_del_publico.txt). El comprobador los acepta sólo si
el destino está en esa lista: cualquier otro destino ausente sigue fallando.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _modulo():
    spec = importlib.util.spec_from_file_location("check_docs_links", RAIZ / "scripts" / "check_docs_links.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_retenido_declarado_pasa_y_roto_sin_declarar_falla(tmp_path, monkeypatch):
    mod = _modulo()
    (tmp_path / "docs").mkdir()
    (tmp_path / "scripts").mkdir()
    (tmp_path / "docs" / "INDEX.md").write_text(
        "[manuscrito](PAPER_X.md) y [roto](NO_EXISTE.md) y [bien](INDEX.md)\n", encoding="utf-8")
    (tmp_path / "scripts" / "retenidos_del_publico.txt").write_text("# retenidos\ndocs/PAPER_X.md\n", encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(mod, "RETENIDOS", tmp_path / "scripts" / "retenidos_del_publico.txt")

    rotos = [destino for _, _, destino in mod.find_broken_links()]

    assert rotos == ["NO_EXISTE.md"]
