"""Vendorizado del sidecar: el productor decide, el host verifica.

El `--write` contra el repositorio real se ejecuta a mano al vendorizar (y
queda clavado por `test_copia_real_verifica`); aquí se prueba la fontanería
(productor por subproceso, negativa a borrar lo ajeno, rechazos) y cada
comprobación del `--check` sobre fixtures. Los payloads con barras se
ensamblan en runtime para no ensuciar este fichero.
"""

import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
BS = chr(92)


def _cargar():
    spec = importlib.util.spec_from_file_location(
        "_stage_molchat", RAIZ / "scripts" / "stage_molchat.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


stage = _cargar()


COPIA = RAIZ / "tools" / "molchat" / "molchat-manifest.json"
requiere_copia = pytest.mark.skipif(
    not COPIA.is_file(), reason="sin sidecar vendorizado (modo ausente)")


@requiere_copia
def test_copia_real_verifica():
    assert stage.verificar() == []


def test_write_rechaza_fuente_ajena_o_antigua(tmp_path):
    with pytest.raises(SystemExit, match="no es un repositorio git"):
        stage.escribir(tmp_path)
    repo = tmp_path / "fuente"
    (repo / ".git").mkdir(parents=True)
    with pytest.raises(SystemExit, match="anterior al productor"):
        stage.escribir(repo)


def test_write_invoca_al_productor_y_verifica(tmp_path, monkeypatch):
    repo = tmp_path / "fuente"
    (repo / ".git").mkdir(parents=True)
    productor = repo / "scripts" / "make_manifest.py"
    productor.parent.mkdir(parents=True)
    productor.write_text("print('productor')\n", encoding="utf-8")
    llamadas = []
    real_run = subprocess.run

    def falso_run(cmd, **kwargs):
        llamadas.append(cmd)
        salida = Path(cmd[cmd.index("--out") + 1])
        salida.mkdir(parents=True, exist_ok=True)
        (salida / "molchat-manifest.json").write_text(
            json.dumps({"version": "0.1.0",
                        "fuente": {"rama": "main", "commit": "c" * 40},
                        "archivos": {}}), encoding="utf-8")

        class Hecho:
            returncode = 0
            stderr = ""
            stdout = ""
        return Hecho()

    monkeypatch.setattr(subprocess, "run", falso_run)
    monkeypatch.setattr(stage, "DESTINO", tmp_path / "out")
    monkeypatch.setattr(stage._manifiesto, "FIJACION", tmp_path / "fijacion.json")
    monkeypatch.setattr(stage, "verificar", lambda destino=None: [])
    stage.escribir(repo)
    assert llamadas[0][0] == sys.executable
    assert str(productor) in llamadas[0]
    assert "--fuente" in llamadas[0] and str(repo) in llamadas[0]


def test_fallo_del_productor_conserva_la_copia_anterior(tmp_path, monkeypatch):
    repo = tmp_path / "fuente"
    (repo / ".git").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "make_manifest.py").write_text("x\n", encoding="utf-8")
    destino = tmp_path / "out"
    destino.mkdir()
    (destino / "molchat-manifest.json").write_text("manifiesto anterior", encoding="utf-8")
    (destino / "archivo.py").write_text("copia anterior", encoding="utf-8")

    def falla_despues_de_borrar(cmd, **_kwargs):
        salida = Path(cmd[cmd.index("--out") + 1])
        if salida.exists():
            for archivo in salida.iterdir():
                if archivo.is_file():
                    archivo.unlink()
        return subprocess.CompletedProcess(cmd, 1, "", "bloqueado")

    monkeypatch.setattr(stage, "DESTINO", destino)
    monkeypatch.setattr(subprocess, "run", falla_despues_de_borrar)
    with pytest.raises(SystemExit, match="bloqueado"):
        stage.escribir(repo)
    assert (destino / "molchat-manifest.json").read_text(encoding="utf-8") == "manifiesto anterior"
    assert (destino / "archivo.py").read_text(encoding="utf-8") == "copia anterior"


@pytest.mark.parametrize("fallo", ["directorio_activo", "instalacion_nueva"])
def test_bloqueo_al_instalar_conserva_la_copia_anterior(tmp_path, monkeypatch, fallo):
    repo = tmp_path / "fuente"
    (repo / ".git").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "make_manifest.py").write_text("x\n", encoding="utf-8")
    destino = tmp_path / "out"
    destino.mkdir()
    (destino / "molchat-manifest.json").write_text("anterior", encoding="utf-8")
    rename = Path.rename

    def productor(cmd, **_kwargs):
        salida = Path(cmd[cmd.index("--out") + 1])
        salida.mkdir()
        (salida / "molchat-manifest.json").write_text("nuevo", encoding="utf-8")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    def bloqueado(self, target):
        if (fallo == "directorio_activo" and self == destino) or (fallo == "instalacion_nueva" and self.name == "nuevo"):
            raise PermissionError("en uso")
        return rename(self, target)

    monkeypatch.setattr(stage, "DESTINO", destino)
    monkeypatch.setattr(stage, "verificar", lambda _destino: [])
    monkeypatch.setattr(subprocess, "run", productor)
    monkeypatch.setattr(Path, "rename", bloqueado)
    with pytest.raises((SystemExit, PermissionError)):
        stage.escribir(repo)
    assert (destino / "molchat-manifest.json").read_text(encoding="utf-8") == "anterior"


def test_write_no_borra_lo_ajeno(tmp_path, monkeypatch):
    repo = tmp_path / "fuente"
    (repo / ".git").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "make_manifest.py").write_text("x\n", encoding="utf-8")
    ajeno = tmp_path / "out"
    ajeno.mkdir()
    (ajeno / "notas.txt").write_text("mio\n", encoding="utf-8")
    monkeypatch.setattr(stage, "DESTINO", ajeno)
    with pytest.raises(SystemExit, match="no lo borro"):
        stage.escribir(repo)
    assert (ajeno / "notas.txt").read_text(encoding="utf-8") == "mio\n"


def test_forma_exige_esquema_contrato_y_origen():
    base = {"schema": stage.ESQUEMA, "programa": "p", "version": "0.1.0",
            "licencia_spdx": stage.LICENCIA_SPDX, "licencia_texto": "LICENSE",
            "fuente": {"proyecto": "moldesign-molchat", "commit": "c" * 40,
                       "rama": "main"},
            "invocacion": "i", "no_se_enlaza": "n",
            "contrato": {"agente_plataforma": stage.CONTRATO_SIDECAR},
            "archivos": {}, "sha256_conjunto": "0" * 64}
    assert stage.problemas_de_forma(base) == []
    assert stage.problemas_de_forma({}) != []
    assert any("schema" in p for p in stage.problemas_de_forma(
        {**base, "schema": "otro/9"}))
    assert any("contrato" in p for p in stage.problemas_de_forma(
        {**base, "contrato": {"agente_plataforma": "otro/9"}}))
    assert any("commit" in p for p in stage.problemas_de_forma(
        {**base, "fuente": {"commit": "corto"}}))


def test_contenido_ve_licencia_rutas_e_indispensables(tmp_path):
    assert stage.problemas_de_contenido({}) != []
    assert any("LICENSE no es" in p for p in stage.problemas_de_contenido(
        {"LICENSE": b"no es la licencia"}))
    unidad = "D" + ":/moldesign-build/backend"
    unc = BS * 2 + "server" + BS + "share"
    errores = stage.problemas_de_contenido(
        {"src/molchat_agent/x.py": f"a = '{unidad}'\nb = '{unc}'\n".encode("utf-8")})
    assert sum("concreta" in e for e in errores) == 2, errores


def test_contenido_ignora_escapes_unicode_de_bundles():
    escapes = BS * 2 + "u00C0-" + BS * 2 + "u00D6"
    cola = BS * 2 + "uFFFD" + BS * 2 + "-.0-9" + BS * 2 + "u00B7"
    errores = stage.problemas_de_contenido(
        {"ui/dist/assets/bundle.js": f"var r='{escapes}{cola}';\n".encode("utf-8")})
    assert [e for e in errores if "concreta" in e] == []


def _fuente_con_productor(tmp_path):
    repo = tmp_path / "fuente"
    (repo / ".git").mkdir(parents=True)
    (repo / "scripts").mkdir()
    (repo / "scripts" / "make_manifest.py").write_text("x\n", encoding="utf-8")
    return repo


def _productor_que_entrega(monkeypatch, repositorio, commit="c" * 40):
    """Productor falso: escribe un manifiesto con el origen indicado en `--out`."""
    def falso_run(cmd, **_kwargs):
        salida = Path(cmd[cmd.index("--out") + 1])
        salida.mkdir(parents=True, exist_ok=True)
        (salida / "molchat-manifest.json").write_text(json.dumps(
            {"version": "0.1.0",
             "fuente": {"rama": "master", "commit": commit, "repositorio": repositorio},
             "archivos": {}}), encoding="utf-8")

        class Hecho:
            returncode = 0
            stderr = ""
            stdout = ""
        return Hecho()
    monkeypatch.setattr(subprocess, "run", falso_run)


@pytest.fixture
def fijacion_aislada(tmp_path, monkeypatch):
    """La fijación real vive en backend/data: las pruebas que escriben la apuntan a una copia."""
    ruta = tmp_path / "fijacion" / "molchat_fijacion.json"
    monkeypatch.setattr(stage._manifiesto, "FIJACION", ruta)
    return ruta


def test_write_fija_la_llave_incluida(tmp_path, monkeypatch, fijacion_aislada):
    repo = _fuente_con_productor(tmp_path)
    destino = tmp_path / "out"
    _productor_que_entrega(monkeypatch, stage._manifiesto.REPOSITORIO_OFICIAL + ".git")
    monkeypatch.setattr(stage, "DESTINO", destino)
    monkeypatch.setattr(stage, "verificar", lambda destino=None: [])
    stage.escribir(repo)
    fijacion = json.loads(fijacion_aislada.read_text(encoding="utf-8"))
    assert fijacion["schema"] == stage._manifiesto.ESQUEMA_FIJACION
    assert fijacion["sha256_manifiesto"] == hashlib.sha256(
        (destino / "molchat-manifest.json").read_bytes()).hexdigest()
    assert fijacion["commit"] == "c" * 40
    assert fijacion["oficial"] is True


def test_repositorio_ajeno_no_es_oficial(tmp_path, monkeypatch, fijacion_aislada):
    repo = _fuente_con_productor(tmp_path)
    monkeypatch.setattr(stage, "DESTINO", tmp_path / "out")
    _productor_que_entrega(monkeypatch, "https://github.com/otro/moldesign-molchat.git")
    monkeypatch.setattr(stage, "verificar", lambda destino=None: [])
    stage.escribir(repo)
    fijacion = json.loads(fijacion_aislada.read_text(encoding="utf-8"))
    assert fijacion["repositorio"] == "https://github.com/otro/moldesign-molchat.git"
    assert fijacion["oficial"] is False


def test_destino_de_prueba_no_toca_copia_ni_fijacion(tmp_path, monkeypatch, fijacion_aislada):
    repo = _fuente_con_productor(tmp_path)
    fijacion_aislada.parent.mkdir(parents=True)
    fijacion_aislada.write_text("fijada antes", encoding="utf-8")
    incluida = tmp_path / "incluida"
    incluida.mkdir()
    (incluida / "molchat-manifest.json").write_text("copia incluida", encoding="utf-8")
    monkeypatch.setattr(stage, "DESTINO", incluida)
    _productor_que_entrega(monkeypatch, stage._manifiesto.REPOSITORIO_OFICIAL)
    monkeypatch.setattr(stage, "verificar", lambda destino=None: [])
    prueba = tmp_path / "prueba"
    stage.escribir(repo, destino=prueba)
    assert (prueba / "molchat-manifest.json").is_file()
    assert (incluida / "molchat-manifest.json").read_text(encoding="utf-8") == "copia incluida"
    assert fijacion_aislada.read_text(encoding="utf-8") == "fijada antes"


def test_verificar_copia_incluida_exige_su_fijacion(tmp_path, monkeypatch):
    monkeypatch.setattr(stage, "DESTINO", tmp_path / "nunca")
    monkeypatch.setattr(stage._manifiesto, "verificar_integridad", lambda _carpeta: [])
    monkeypatch.setattr(stage._manifiesto, "manifiesto_de", lambda _carpeta: {
        "schema": stage.ESQUEMA, "programa": "p", "version": "0.1.0",
        "licencia_spdx": stage.LICENCIA_SPDX, "licencia_texto": "LICENSE",
        "fuente": {"proyecto": "moldesign-molchat", "commit": "c" * 40, "rama": "master"},
        "invocacion": "i", "no_se_enlaza": "n",
        "contrato": {"agente_plataforma": stage.CONTRATO_SIDECAR},
        "archivos": {}, "sha256_conjunto": "0" * 64})
    monkeypatch.setattr(stage, "problemas_de_contenido", lambda _contenido: [])
    monkeypatch.setattr(stage._manifiesto, "FIJACION", tmp_path / "sin-fijacion.json")
    assert any("sin fijación" in p for p in stage.verificar(tmp_path / "nunca"))
    # Una carpeta de prueba no exige fijación: no es la copia que MolDesign publica.
    assert stage.verificar(tmp_path / "otra") == []


def test_ruta_relativa_a_la_copia_incluida_tambien_fija(tmp_path, monkeypatch, fijacion_aislada):
    repo = _fuente_con_productor(tmp_path)
    monkeypatch.setattr(stage, "DESTINO", tmp_path / "out")
    _productor_que_entrega(monkeypatch, stage._manifiesto.REPOSITORIO_OFICIAL)
    monkeypatch.setattr(stage, "verificar", lambda destino=None: [])
    monkeypatch.chdir(tmp_path)
    stage.escribir(repo, destino=Path("out"))
    assert fijacion_aislada.is_file()
