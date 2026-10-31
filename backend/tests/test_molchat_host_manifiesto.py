"""El verificador del sidecar MolChat: integridad, localización y abstención.

El manifiesto del fixture se construye con `hashlib` directamente (no con
el módulo bajo prueba): la prueba demostraría poco si ambos lados
compartieran la aritmética.
"""

import hashlib
import json
from pathlib import Path

import pytest

from services.molchat_host import manifest

RAIZ = Path(__file__).resolve().parents[2]
requiere_copia = pytest.mark.skipif(
    not (RAIZ / "tools" / "molchat" / manifest.NOMBRE_MANIFIESTO).is_file(),
    reason="sin sidecar vendorizado (modo ausente)")


def _sellar(carpeta: Path, archivos: dict[str, bytes]) -> dict:
    declarados = {}
    for ruta, datos in archivos.items():
        destino = carpeta / ruta
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(datos)
        declarados[ruta] = {"bytes": len(datos),
                            "sha256": hashlib.sha256(datos).hexdigest()}
    cuerpo = "".join(f"{r}\0{declarados[r]['sha256']}\n" for r in sorted(declarados))
    conjunto = hashlib.sha256(cuerpo.encode("utf-8")).hexdigest()
    manifiesto = {"schema": manifest.ESQUEMA, "programa": "MolChat",
                  "version": "0.1.0", "licencia_spdx": "GPL-3.0-or-later",
                  "licencia_texto": "LICENSE",
                  "fuente": {"proyecto": "moldesign-molchat",
                             "commit": "a" * 40, "rama": "main"},
                  "invocacion": "sidecar", "no_se_enlaza": "nada",
                  "contrato": {"agente_plataforma": manifest.CONTRATO_SIDECAR},
                  "requisitos": {"python": ">=3.11", "dependencias": []},
                  "excluidos": [], "archivos": declarados,
                  "sha256_conjunto": conjunto}
    (carpeta / manifest.NOMBRE_MANIFIESTO).write_text(
        json.dumps(manifiesto), encoding="utf-8")
    return manifiesto


def test_copia_integra_pasa_y_cualquiera_rota_no(tmp_path):
    carpeta = tmp_path / "molchat"
    carpeta.mkdir()
    _sellar(carpeta, {"LICENSE": b"GPL", "src/molchat_agent/x.py": b"v = 1\n"})
    assert manifest.verificar_integridad(carpeta) == []
    (carpeta / "src" / "molchat_agent" / "x.py").write_bytes(b"v = 2\n")
    assert manifest.verificar_integridad(carpeta) == ["src/molchat_agent/x.py difiere del manifiesto"]
    (carpeta / "src" / "molchat_agent" / "x.py").write_bytes(b"v = 1\n")
    (carpeta / "intruso.py").write_bytes(b"x\n")
    assert manifest.verificar_integridad(carpeta) == ["sobra intruso.py: no está en el manifiesto"]
    (carpeta / "intruso.py").unlink()
    (carpeta / "LICENSE").unlink()
    assert manifest.verificar_integridad(carpeta) == ["falta LICENSE"]


def test_manifiesto_editado_o_ausente_se_abstiene(tmp_path):
    carpeta = tmp_path / "molchat"
    carpeta.mkdir()
    assert manifest.verificar_integridad(carpeta) == [
        f"falta {manifest.NOMBRE_MANIFIESTO}"]
    assert manifest.manifiesto_de(carpeta) == {}
    _sellar(carpeta, {"a.py": b"x\n"})
    ruta = carpeta / manifest.NOMBRE_MANIFIESTO
    ruta.write_text("no json", encoding="utf-8")
    assert manifest.verificar_integridad(carpeta) == [
        f"{manifest.NOMBRE_MANIFIESTO} ilegible"]
    assert manifest.manifiesto_de(carpeta) == {}
    datos = {"schema": "otro/9", "archivos": {}}
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    assert manifest.verificar_integridad(carpeta) == ["esquema desconocido: 'otro/9'"]
    sellado = _sellar(carpeta, {"a.py": b"x\n"})
    sellado["sha256_conjunto"] = "0" * 64
    ruta.write_text(json.dumps(sellado), encoding="utf-8")
    assert manifest.verificar_integridad(carpeta) == [
        "sha256_conjunto no corresponde a la lista de archivos"]


def test_bytecode_del_interprete_no_cuenta_pero_nada_mas(tmp_path):
    carpeta = tmp_path / "molchat"
    pycache = carpeta / "src" / "__pycache__"
    pycache.mkdir(parents=True)
    _sellar(carpeta, {"src/a.py": b"x\n"})
    (pycache / "a.pyc").write_bytes(b"bytecode")
    assert manifest.verificar_integridad(carpeta) == []
    (carpeta / "a.pyc").write_bytes(b"bytecode")
    assert manifest.verificar_integridad(carpeta) == ["sobra a.pyc: no está en el manifiesto"]


def test_localizacion_por_variable_y_por_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("MOLDESIGN_MOLCHAT_DIR", raising=False)
    monkeypatch.delenv("MOLDESIGN_OPENBABEL_DIR", raising=False)
    assert manifest.directorio_incluido(raiz=tmp_path) is None
    staged = tmp_path / "tools" / "molchat"
    staged.mkdir(parents=True)
    assert manifest.directorio_incluido(raiz=tmp_path) is None  # sin manifiesto no cuenta
    _sellar(staged, {"a.py": b"x\n"})
    assert manifest.directorio_incluido(raiz=tmp_path) == staged.resolve()
    externo = tmp_path / "externo"
    externo.mkdir()
    _sellar(externo, {"a.py": b"x\n"})
    monkeypatch.setenv("MOLDESIGN_MOLCHAT_DIR", str(externo))
    assert manifest.directorio_incluido(raiz=tmp_path) == externo.resolve()


def test_externo_solo_con_permiso_explicito(monkeypatch):
    monkeypatch.delenv("MOLCHAT_PERMITIR_EXTERNO", raising=False)
    assert manifest.molchat_externo_permitido() is False
    monkeypatch.setenv("MOLCHAT_PERMITIR_EXTERNO", "1")
    assert manifest.molchat_externo_permitido() is True


def _fijar(carpeta, ruta, **cambios):
    """Una fijación honesta para `carpeta`; `cambios` la estropea a propósito."""
    datos = (carpeta / manifest.NOMBRE_MANIFIESTO).read_bytes()
    fijacion = {"schema": manifest.ESQUEMA_FIJACION,
                "repositorio": manifest.REPOSITORIO_OFICIAL, "oficial": True,
                "commit": "a" * 40, "rama": "main", "version": "0.1.0",
                "sha256_manifiesto": hashlib.sha256(datos).hexdigest(), **cambios}
    ruta.write_text(json.dumps(fijacion), encoding="utf-8")
    return ruta


def test_fijacion_coincide_con_la_copia_y_cualquier_cambio_no(tmp_path):
    carpeta = tmp_path / "molchat"
    carpeta.mkdir()
    _sellar(carpeta, {"LICENSE": b"GPL", "src/molchat_agent/x.py": b"v = 1\n"})
    ruta = _fijar(carpeta, tmp_path / "fijacion.json")
    assert manifest.verificar_fijacion(carpeta, ruta) == []
    otro_commit = _fijar(carpeta, tmp_path / "otro.json", commit="b" * 40)
    assert manifest.verificar_fijacion(carpeta, otro_commit) == [
        f"el commit {'a' * 12} no es el fijado {'b' * 12}"]
    manifiesto = json.loads((carpeta / manifest.NOMBRE_MANIFIESTO).read_text(encoding="utf-8"))
    manifiesto["version"] = "9.9.9"
    (carpeta / manifest.NOMBRE_MANIFIESTO).write_text(json.dumps(manifiesto), encoding="utf-8")
    assert manifest.verificar_fijacion(carpeta, ruta) == ["el manifiesto no es el fijado"]


def test_fijacion_ausente_ilegible_o_de_otro_esquema_cierra_la_llave(tmp_path):
    carpeta = tmp_path / "molchat"
    carpeta.mkdir()
    _sellar(carpeta, {"LICENSE": b"GPL"})
    sin_fijar = ["sin fijación de la llave (backend/data/molchat_fijacion.json)"]
    assert manifest.verificar_fijacion(carpeta, tmp_path / "no-esta.json") == sin_fijar
    ilegible = tmp_path / "rota.json"
    ilegible.write_text("no json", encoding="utf-8")
    assert manifest.verificar_fijacion(carpeta, ilegible) == sin_fijar
    otro = _fijar(carpeta, tmp_path / "otro-esquema.json", schema="otro/9")
    assert manifest.verificar_fijacion(carpeta, otro) == [
        "fijación de esquema desconocido: 'otro/9'"]


def test_oficial_compara_la_url_sin_barra_final_ni_sufijo_git():
    assert manifest.es_oficial(manifest.REPOSITORIO_OFICIAL)
    assert manifest.es_oficial(manifest.REPOSITORIO_OFICIAL + ".git")
    assert manifest.es_oficial(manifest.REPOSITORIO_OFICIAL + ".git/")
    assert not manifest.es_oficial("https://github.com/otro/moldesign-molchat")
    assert not manifest.es_oficial("")
    assert not manifest.es_oficial(None)


@requiere_copia
def test_fijacion_real_encaja_con_la_copia_incluida():
    carpeta = manifest.directorio_incluido(solo_incluido=True)
    assert carpeta is not None
    assert manifest.verificar_fijacion(carpeta) == []
