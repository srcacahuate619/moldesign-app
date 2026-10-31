"""Supervisor del sidecar: localización honesta y ciclo de vida real.

La prueba de fuego levanta la copia vendorizada de verdad
(`tools/molchat/`): si arranca, sirve salud+UI y se detiene sin huérfanos,
el empaquetado y el lanzador cuadran. Tarda segundos; es el coste de no
mentir sobre integraciones.
"""

import json
import shutil
import urllib.request
from pathlib import Path

import pytest

from services.molchat_host import launcher, manifest

RAIZ = Path(__file__).resolve().parents[2]
requiere_copia = pytest.mark.skipif(
    not (RAIZ / "tools" / "molchat" / manifest.NOMBRE_MANIFIESTO).is_file(),
    reason="sin sidecar vendorizado (modo ausente)",
)


@requiere_copia
def test_localizar_encuentra_la_copia_incluida(monkeypatch):
    monkeypatch.delenv("MOLDESIGN_MOLCHAT_DIR", raising=False)
    monkeypatch.delenv("MOLCHAT_PERMITIR_EXTERNO", raising=False)
    carpeta, motivo = launcher.localizar()
    assert carpeta is not None and motivo == "ok"
    assert (carpeta / manifest.NOMBRE_MANIFIESTO).is_file()


def test_localizar_sin_copia_informa_motivo(monkeypatch):
    monkeypatch.setattr(manifest, "directorio_incluido", lambda **k: None)
    carpeta, motivo = launcher.localizar()
    assert carpeta is None
    assert "ausente" in motivo


def test_localizar_rechaza_externo_sin_permiso(tmp_path, monkeypatch):
    externo = tmp_path / "externo"
    externo.mkdir()
    (externo / manifest.NOMBRE_MANIFIESTO).write_text("{}", encoding="utf-8")
    monkeypatch.setenv("MOLDESIGN_MOLCHAT_DIR", str(externo))
    monkeypatch.delenv("MOLCHAT_PERMITIR_EXTERNO", raising=False)
    carpeta, motivo = launcher.localizar()
    assert carpeta is None
    assert "MOLCHAT_PERMITIR_EXTERNO" in motivo


def test_localizar_rechaza_copia_alterada(tmp_path, monkeypatch):
    from services.molchat_host import manifest as man

    rota = tmp_path / "rota"
    rota.mkdir()
    (rota / man.NOMBRE_MANIFIESTO).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(man, "directorio_incluido", lambda **k: rota)
    carpeta, motivo = launcher.localizar()
    assert carpeta is None
    assert "alterada" in motivo or "contrato" in motivo


@requiere_copia
def test_localizar_rechaza_la_llave_sin_su_fijacion(tmp_path, monkeypatch):
    monkeypatch.delenv("MOLDESIGN_MOLCHAT_DIR", raising=False)
    monkeypatch.delenv("MOLCHAT_PERMITIR_EXTERNO", raising=False)
    monkeypatch.setattr(manifest, "FIJACION", tmp_path / "no-esta.json")
    carpeta, motivo = launcher.localizar()
    assert carpeta is None
    assert "no coincide con su fijación" in motivo


@requiere_copia
def test_localizar_rechaza_la_copia_de_otra_fijacion(tmp_path, monkeypatch):
    monkeypatch.delenv("MOLDESIGN_MOLCHAT_DIR", raising=False)
    monkeypatch.delenv("MOLCHAT_PERMITIR_EXTERNO", raising=False)
    fijacion = tmp_path / "fijacion.json"
    fijacion.write_text(json.dumps({
        "schema": manifest.ESQUEMA_FIJACION, "repositorio": "", "oficial": False,
        "commit": "0" * 40, "rama": "main", "version": "0.1.0",
        "sha256_manifiesto": "0" * 64}), encoding="utf-8")
    monkeypatch.setattr(manifest, "FIJACION", fijacion)
    carpeta, motivo = launcher.localizar()
    assert carpeta is None
    assert "el manifiesto no es el fijado" in motivo


@requiere_copia
def test_localizar_acepta_copia_externa_sin_fijacion(tmp_path, monkeypatch):
    externa = tmp_path / "externa"
    shutil.copytree(RAIZ / "tools" / "molchat", externa)
    monkeypatch.setattr(manifest, "FIJACION", tmp_path / "no-esta.json")
    monkeypatch.setenv("MOLDESIGN_MOLCHAT_DIR", str(externa))
    monkeypatch.setenv("MOLCHAT_PERMITIR_EXTERNO", "1")
    carpeta, motivo = launcher.localizar()
    assert carpeta == externa.resolve() and motivo == "ok"


@requiere_copia
def test_ciclo_de_vida_contra_la_copia_vendorizada():
    lanzador = launcher.Lanzador(arranque_timeout_s=90.0)
    try:
        url = lanzador.arrancar()
        assert lanzador.vivo()
        assert lanzador.arrancar() == url  # idempotente, sin segundo proceso
        with urllib.request.urlopen(url + "/v1/health", timeout=10) as r:
            salud = json.loads(r.read())
        assert salud["status"] == "ok"
        assert salud["contract"] == "moldesign.molchat/1"
        with urllib.request.urlopen(url + "/v1/version", timeout=10) as r:
            version = json.loads(r.read())
        assert version["molchat"] == "0.1.0"
        with urllib.request.urlopen(url + "/", timeout=10) as r:
            assert r.status == 200
            assert b"html" in r.read()[:500].lower()
        estado = lanzador.estado()
        assert estado["disponible"] and estado["en_marcha"]
        assert estado["url"] == url and estado["commit"]
    finally:
        assert lanzador.detener() == "detenido"
    assert not lanzador.vivo()
    assert lanzador.detener() == "detenido"
    assert lanzador.estado()["en_marcha"] is False


def test_singleton_por_proceso():
    primero = launcher.obtener_lanzador()
    assert launcher.obtener_lanzador() is primero


def test_salud_no_acepta_proceso_ajeno_o_contrato_incompatible(monkeypatch):
    import io

    class Respuesta(io.BytesIO):
        status = 200

    lanzador = launcher.Lanzador()
    lanzador._url = "http://127.0.0.1:59999"
    for cuerpo, esperado in [
        (b'{"status":"ok","contract":"moldesign.molchat/1"}', True),
        (b'{"status":"ok","contract":"moldesign.molchat/2"}', False),
        (b'{"status":"ok"}', False),
        (b'not json', False),
    ]:
        monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: Respuesta(cuerpo))
        assert lanzador._saludable() is esperado


def test_el_arranque_no_depende_del_entorno_del_interprete():
    """El Python empaquetado del escritorio es aislado: `PYTHONPATH` no
    existe para él y `-m` nunca añade el cwd (medido: `sys.flags.isolated=1`,
    el sidecar no arrancó en el runtime real). El argv tiene que resolver el
    paquete desde dentro del propio proceso: bootstrap `-c`, `src/` como
    `sys.argv[1]` y el resto como CLI, con el código de salida propagado.
    """
    lanzador = launcher.Lanzador(python="PY", port=1234)
    assert "sys.path.insert(0, sys.argv.pop(1))" in launcher.ARRANQUE_CMD
    assert "molchat_agent.cli" in launcher.ARRANQUE_CMD
    assert "SystemExit(main())" in launcher.ARRANQUE_CMD
    # El arranque real se valida en test_ciclo_de_vida; aquí se fija la forma
    # para que un intérprete no aislado no enmascare una regresión.
    import inspect
    codigo = inspect.getsource(lanzador.arrancar)
    assert '"-c", ARRANQUE_CMD' in codigo or "'-c', ARRANQUE_CMD" in codigo
    assert '"-m"' not in codigo
