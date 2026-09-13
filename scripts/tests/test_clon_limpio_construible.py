"""Un clon limpio tiene que poder construir, y decirlo cuando no puede.

Estas pruebas cubren la vía que NO depende de que publiquemos nada: el
intérprete embebido reconstruido desde python.org y PyPI. Ninguna toca la red
—las que lo harían están marcadas y se saltan— porque una suite que descarga
2,2 GB no se ejecuta y una prueba que no se ejecuta no protege nada.

    python -m pytest scripts/tests/test_clon_limpio_construible.py -q
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import bootstrap_dev_tree as boot
import provision_python_embed as prov

RAIZ = Path(__file__).resolve().parents[2]


# ── Los orígenes declarados ──────────────────────────────────────────────


def test_los_origenes_son_oficiales_y_estan_fijados():
    """Nada se descarga de un sitio sin nombre ni sin hash."""
    for item in (prov.CPYTHON, prov.PIP):
        assert item.url.startswith("https://"), item.url
        assert len(item.sha256) == 64, f"{item.nombre}: hash de {len(item.sha256)}"
        assert item.bytes > 0
        assert item.procedencia, f"{item.nombre} no dice de dónde sale"

    # python.org y PyPI, no un espejo de alguien.
    assert prov.CPYTHON.url.startswith("https://www.python.org/ftp/python/")
    assert prov.PIP.url.startswith("https://files.pythonhosted.org/")


def test_la_version_del_interprete_es_la_del_lockfile():
    """El lockfile dice contra qué intérprete se midió. Deben coincidir.

    Si divergen, se reconstruiría un `python-embed` de otra serie y el bytecode
    precompilado del bundle llevaría el número mágico equivocado — que se
    ignora en silencio, que es la peor forma de fallar.
    """
    cabecera = prov.LOCKFILE.read_text(encoding="utf-8")[:1200]
    assert f"CPython {prov.VERSION_PYTHON}" in cabecera, (
        f"el lockfile no declara CPython {prov.VERSION_PYTHON} en su cabecera"
    )
    assert prov.VERSION_PYTHON.startswith(prov.SERIE_PYTHON)
    assert boot.PYTHON_EMBEBIDO == prov.SERIE_PYTHON, (
        "el bootstrap y el aprovisionador no esperan la misma serie de Python"
    )


def test_los_casos_especiales_dicen_por_que_lo_son():
    """Un caso especial sin motivo escrito se convierte en folclore."""
    assert prov.CASOS_ESPECIALES, "sin casos especiales, `pip install -r` falla"
    nombres = {n for n, _, _ in prov.CASOS_ESPECIALES}
    assert nombres == {"llama_cpp_python", "pdbfixer"}, (
        "cambió la lista de paquetes que PyPI no resuelve: vuelve a medirla con "
        "`pip install --dry-run --only-binary=:all: -r requirements-embed.lock.txt`"
    )
    for nombre, origen, motivo in prov.CASOS_ESPECIALES:
        assert origen.startswith("https://"), f"{nombre}: origen sin URL"
        assert len(motivo) > 60, f"{nombre}: el motivo no explica nada"


def test_todo_lo_del_lockfile_se_reparte_sin_perder_nada():
    """La partición no puede tragarse un paquete en silencio."""
    paquetes = prov.paquetes_del_lock()
    normales, apartados = prov.particionar(paquetes)
    # `pip` se instala antes que nada y por eso no está en ninguna lista.
    pips = [p for p in paquetes if prov._nombre_de(p) == "pip"]
    assert len(normales) + len(apartados) + len(pips) == len(paquetes), (
        "la partición pierde o duplica paquetes"
    )
    assert set(apartados) == {n for n, _, _ in prov.CASOS_ESPECIALES}


# ── El recibo y el estado del árbol ──────────────────────────────────────


def test_el_recibo_de_fuente_no_lleva_reloj(tmp_path, monkeypatch):
    """Dos aprovisionamientos del mismo lockfile escriben el mismo recibo.

    Con marca de tiempo, «el mismo inventario» dejaría de poder comprobarse.
    """
    destino = tmp_path / "python-embed"
    destino.mkdir()
    monkeypatch.setattr(prov, "DESTINO", destino)
    uno = prov.escribir_recibo(dependencias=True).read_bytes()
    dos = prov.escribir_recibo(dependencias=True).read_bytes()
    assert uno == dos

    cuerpo = json.loads(uno.decode("utf-8"))
    assert cuerpo["lockfile_sha256"] == prov.sha256(prov.LOCKFILE)
    assert cuerpo["dependencias_instaladas"] is True
    assert "no_garantiza" in cuerpo, (
        "el recibo tiene que decir qué NO garantiza: no reproduce bytes"
    )
    urls = {d["url"] for d in cuerpo["descargas"]}
    assert prov.CPYTHON.url in urls and prov.PIP.url in urls


def test_un_arbol_de_fuente_no_se_llama_ajeno(tmp_path):
    """`DESDE_FUENTE` es una procedencia válida, no un accidente.

    Antes de distinguirlos, un árbol reconstruido por la vía documentada se
    reportaba como AJENO —«piezas que no puso ningún artefacto»— y parecía roto.
    """
    embed = tmp_path / "python-embed"
    embed.mkdir()
    (embed / "python.exe").write_bytes(b"MZ")

    assert boot.medir(tmp_path).codigo == boot.AJENO

    (embed / boot.NOMBRE_RECIBO_FUENTE).write_text(
        json.dumps({"formato": 1, "via": "orígenes oficiales (python.org + PyPI)"}),
        encoding="utf-8",
    )
    estado = boot.medir(tmp_path)
    assert estado.codigo == boot.DESDE_FUENTE
    assert "python.org" in estado.detalle


def test_sin_interprete_el_estado_es_ausente(tmp_path):
    """Y `--check` no inventa nada sobre un árbol vacío."""
    assert boot.medir(tmp_path).codigo == boot.AUSENTE


# ── La puerta del build ──────────────────────────────────────────────────


def test_la_puerta_del_build_existe_y_va_la_primera():
    """Las otras doce dan por hecho el runtime; ésta comprueba el suelo."""
    guarda = RAIZ / "frontend" / "scripts" / "check-runtime-arbol.mjs"
    assert guarda.is_file(), "falta la guarda del árbol"

    conf = json.loads(
        (RAIZ / "frontend" / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8")
    )
    cadena = conf["build"]["beforeBuildCommand"].split(" && ")
    assert cadena[0] == "npm run check:runtime-arbol", (
        f"la primera puerta es {cadena[0]!r}; si no va antes que las demás, el "
        "fallo por runtime ausente vuelve a aparecer disfrazado de error de CSP"
    )

    paquete = json.loads(
        (RAIZ / "frontend" / "package.json").read_text(encoding="utf-8")
    )
    orden = paquete["scripts"]["check:runtime-arbol"]
    assert "check-runtime-arbol.mjs" in orden
    assert "python-embed" not in orden, (
        "la guarda no puede invocarse con el intérprete que comprueba si existe"
    )


@pytest.mark.skipif(sys.platform != "win32", reason="la guarda es de la build Windows")
def test_la_puerta_diagnostica_un_arbol_sin_interprete(tmp_path):
    """Sobre un árbol sin `python-embed`, el mensaje nombra la solución."""
    guarda = RAIZ / "frontend" / "scripts" / "check-runtime-arbol.mjs"
    falso = tmp_path / "frontend" / "scripts"
    falso.mkdir(parents=True)
    (falso / "check-runtime-arbol.mjs").write_bytes(guarda.read_bytes())
    (tmp_path / "scripts").mkdir()

    proceso = subprocess.run(
        ["node", str(falso / "check-runtime-arbol.mjs")],
        capture_output=True, text=True, timeout=120,
    )
    assert proceso.returncode == 1
    salida = proceso.stdout + proceso.stderr
    assert "provision_python_embed.py" in salida, (
        "el diagnóstico no dice cómo arreglarlo"
    )
    assert "python-embed" in salida


# ── La oferta de fuente, visible desde un clon ───────────────────────────


def test_la_oferta_de_fuente_esta_versionada():
    """Un clon tiene que poder leer QUÉ se ofrece, aunque no traiga los .tar.gz.

    Medido el 2026-09-06: la oferta entera vivía en `dist/`, que está en
    `.gitignore`, así que sólo existía en la máquina del mantenedor.
    """
    import verify_release_source_offer as oferta_module

    assert oferta_module.OFERTA_VERSIONADA.is_file(), (
        "la declaración de la oferta GPL no está versionada"
    )
    documento = json.loads(
        oferta_module.OFERTA_VERSIONADA.read_text(encoding="utf-8-sig")
    )
    assert documento["licencia_spdx"] == "GPL-2.0-only"
    assert documento["procedencia"]["fuentes_incorporadas_repo"].startswith("https://")
    for nombre in oferta_module.ARTEFACTOS:
        entrada = documento["artefactos"][nombre]
        assert len(entrada["sha256"]) == 64, f"{nombre} sin SHA-256"

    # Y el binario que se ofrece reconstruir es el que se distribuye.
    manifiesto = json.loads(
        (RAIZ / "tools" / "openbabel" / "openbabel-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    ejecutable = manifiesto["ejecutable"]
    assert (
        documento["binario_distribuido"]["sha256"]
        == manifiesto["archivos"][ejecutable]["sha256"]
    )
    entrada_oferta = manifiesto["archivos"].get("SOURCE-OFFER.json")
    assert entrada_oferta is not None, (
        "el manifiesto de la herramienta no protege su oferta de fuente"
    )
    assert entrada_oferta["sha256"] == oferta_module.sha256(
        oferta_module.OFERTA_VERSIONADA
    )
    serializado = json.dumps(manifiesto, ensure_ascii=False)
    assert "D:\\\\" not in serializado and "C:\\\\" not in serializado, (
        "el manifiesto p?blico no puede depender de la ruta de la m?quina"
    )


def test_permitir_artefactos_ausentes_no_dice_verificado(capsys):
    """Saltar no es aprobar: tiene que decir qué NO comprobó."""
    import verify_release_source_offer as oferta

    if (oferta.DIRECTORIO / oferta.ARTEFACTOS[0]).is_file():
        pytest.skip("esta máquina sí tiene los artefactos de fuente")

    codigo = oferta.comprobar(permitir_ausentes=True)
    salida = capsys.readouterr().out
    assert codigo == 0
    assert "NO están en este árbol" in salida
    assert "Saltar no es aprobar" in salida
    assert "verificada" not in salida.lower().split("saltar")[0], (
        "no puede anunciar verificación de lo que no miró"
    )

    assert oferta.comprobar(permitir_ausentes=False) == 1, (
        "sin la bandera, la ausencia de las fuentes tiene que bloquear"
    )


# ── Los dos defectos que sólo aparecieron al correrlo de verdad ──────────
#
# Los dos se descubrieron el 2026-09-06 aprovisionando el árbol entero, después
# de que las once pruebas de arriba estuvieran verdes. Ninguna los habría visto:
# uno vive en el `finally` de una instalación de veinte minutos y el otro en
# cómo pip informa de lo que instaló. Quedan aquí para que no vuelvan.


def test_no_se_usa_mkstemp_para_el_archivo_de_requisitos():
    """`mkstemp` devuelve un descriptor ABIERTO y Windows no borra eso.

    Medido: los 170 paquetes se instalaron bien y la corrida murió después, en
    el `finally`, con WinError 32 — «el proceso no tiene acceso al archivo
    porque está siendo utilizado por otro proceso». Se perdieron los dos casos
    especiales y el recibo, veinte minutos después de haber hecho el trabajo.
    """
    fuente = Path(prov.__file__).read_text(encoding="utf-8")
    # La LLAMADA, no la palabra: el comentario que explica el defecto la
    # nombra, y una prueba que se dispara con su propia documentación no
    # comprueba nada.
    assert "tempfile.mkstemp(" not in fuente, (
        "vuelve a usarse mkstemp: en Windows su descriptor abierto impide "
        "borrar el archivo y tumba la corrida al final"
    )
    assert "TemporaryDirectory" in fuente


def test_el_inventario_se_lee_de_pip_list_y_no_de_pip_freeze():
    """`pip freeze` miente por omisión sobre cuatro paquetes.

    Medido sobre un árbol correctamente aprovisionado con los 173: `freeze`
    omite pip, setuptools y wheel, y escribe `pdbfixer @ https://…` en vez de
    `pdbfixer==1.12.0` por venir de una URL. El informe anunciaba cuatro
    ausencias falsas. Un comprobador que dice que falta lo que está es tan
    inútil como el que dice que está lo que falta.
    """
    fuente = Path(prov.__file__).read_text(encoding="utf-8")
    assert '"pip", "list", "--format=json"' in fuente, (
        "el informe tiene que preguntar con `pip list --format=json`"
    )
    assert '"pip", "freeze"' not in fuente


def test_la_descarga_de_pdbfixer_va_fijada_por_hash():
    """Todo lo que se baja se verifica; un tarball de GitHub también."""
    origenes = {n: o for n, o, _ in prov.CASOS_ESPECIALES}
    pdbfixer = origenes["pdbfixer"]
    assert "#sha256=" in pdbfixer, (
        "el tarball de pdbfixer se descarga sin hash: un tag de git se puede "
        "mover y nadie se enteraría"
    )
    assert len(pdbfixer.split("#sha256=")[1]) == 64
