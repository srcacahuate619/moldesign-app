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


def test_una_ruta_absoluta_es_un_enlace_roto_aunque_exista_aqui(tmp_path, monkeypatch):
    mod = _modulo()
    (tmp_path / "docs").mkdir()
    existe = tmp_path / "existe.json"
    existe.write_text("{}", encoding="utf-8")
    (tmp_path / "docs" / "INDEX.md").write_text(
        f"[aqui]({existe.as_posix()}) y [disco](F:/Backups/x.json) y [raiz](/etc/x) y [bien](INDEX.md) "
        "y [`F:/Backups/x.json`](INDEX.md)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(mod, "RETENIDOS", tmp_path / "scripts" / "retenidos_del_publico.txt")

    rotos = [destino for _, _, destino in mod.find_broken_links()]

    assert rotos == [existe.as_posix(), "F:/Backups/x.json", "/etc/x"]


# ── Un bloque de código no contiene enlaces (patrones.md de D-04, 2026-11-15) ────────────────────────────────────


def _con_docs(mod, tmp_path, monkeypatch, texto: str):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "INDEX.md").write_text(texto, encoding="utf-8")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod, "DOCS", tmp_path / "docs")
    monkeypatch.setattr(mod, "RETENIDOS", tmp_path / "scripts" / "retenidos_del_publico.txt")
    return [destino for _, _, destino in mod.find_broken_links()]


SMARTS = "[NX4+;!H0]-[CX4]-[CX3](=[OX1])-[OX2;H0]-[#6]"


def test_un_smarts_en_un_bloque_cercado_no_es_un_enlace(tmp_path, monkeypatch):
    mod = _modulo()
    texto = f"Motivos:\n\n```text\n{SMARTS}\n```\n\ny [roto](NO_EXISTE.md)\n"
    assert _con_docs(mod, tmp_path, monkeypatch, texto) == ["NO_EXISTE.md"]


def test_el_mismo_smarts_fuera_de_un_bloque_si_se_toma_por_enlace(tmp_path, monkeypatch):
    """Control negativo: demuestra que el detector sigue viendo lo que tiene que ver, y que la prueba de arriba prueba algo."""
    mod = _modulo()
    assert _con_docs(mod, tmp_path, monkeypatch, f"{SMARTS}\n") == ["=[OX1]"]


def test_un_enlace_roto_dentro_de_un_bloque_no_cuenta_pero_fuera_si(tmp_path, monkeypatch):
    mod = _modulo()
    texto = "~~~\n[ejemplo](NO_EXISTE.md)\n~~~\n[fuera](TAMPOCO.md)\n"
    assert _con_docs(mod, tmp_path, monkeypatch, texto) == ["TAMPOCO.md"]


def test_una_valla_sin_cerrar_no_esconde_el_resto_del_archivo(tmp_path, monkeypatch):
    mod = _modulo()
    texto = "```\ncódigo sin cerrar\n[roto](NO_EXISTE.md)\n"
    assert _con_docs(mod, tmp_path, monkeypatch, texto) == ["NO_EXISTE.md"]


def test_una_valla_de_otro_tipo_no_cierra_el_bloque(tmp_path, monkeypatch):
    mod = _modulo()
    texto = "```\n~~~\n[dentro](NO_EXISTE.md)\n```\n[fuera](OTRO.md)\n"
    assert _con_docs(mod, tmp_path, monkeypatch, texto) == ["OTRO.md"]
