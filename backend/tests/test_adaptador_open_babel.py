"""El adaptador de Open Babel: los cinco estados, sobre el binario de verdad.

# Qué se comprueba aquí y por qué así

Estas pruebas ejecutan el **ejecutable empaquetado**, no un doble. Un adaptador
cuya única prueba es un mock demuestra que el mock se comporta como se escribió;
lo que hace falta demostrar es que el programa que viaja en el instalador
convierte una molécula, que su hash se comprueba antes de ejecutarlo, y que
cuando falta o está alterado el sistema lo dice en vez de continuar.

Los estados degradados se construyen sobre **copias** del árbol staged, apuntadas
con `MOLDESIGN_OPENBABEL_DIR`. Nunca se toca `tools/openbabel/`: una prueba que
rompe el artefacto para comprobar que se detecta la rotura es una prueba que
deja el artefacto roto.

Si Open Babel no está staged —un clon limpio no trae binarios— las pruebas que
lo necesitan se saltan diciendo por qué, y las que sólo miran contrato siguen
corriendo. Saltar no es aprobar: `scripts/check_openbabel_boundary.py` es la
guarda que bloquea el build.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import shutil
from pathlib import Path

import pytest

from services.external_tools import open_babel
from services.external_tools.open_babel import (
    EstadoOpenBabel,
    OpenBabelNoDisponible,
)

RAIZ = Path(__file__).resolve().parents[2]
HERRAMIENTA = RAIZ / "tools" / "openbabel"

hay_herramienta = (HERRAMIENTA / "openbabel-manifest.json").is_file() and (
    HERRAMIENTA / "bin" / "obabel.exe"
).is_file()

necesita_binario = pytest.mark.skipif(
    not hay_herramienta,
    reason=(
        "tools/openbabel/ no está staged en este árbol. Ejecuta "
        "`python scripts/stage_openbabel_tool.py`. En un clon limpio es normal: "
        "los binarios no se versionan."
    ),
)

#: Una pose mínima pero real: tres átomos con coordenadas y tipos de AutoDock.
PDBQT_MINIMO = "\n".join(
    [
        "ROOT",
        "ATOM      1  C   UNL     1       0.000   0.000   0.000  1.00  0.00     0.000 C ",
        "ATOM      2  C   UNL     1       1.520   0.000   0.000  1.00  0.00     0.000 C ",
        "ATOM      3  O   UNL     1       2.100   1.080   0.000  1.00  0.00    -0.270 OA",
        "ENDROOT",
        "TORSDOF 0",
        "",
    ]
)


@pytest.fixture
def copia_de_la_herramienta(tmp_path, monkeypatch):
    """Una copia escribible del árbol staged, ya apuntada por el entorno."""
    if not hay_herramienta:
        pytest.skip("tools/openbabel/ no está staged")
    destino = tmp_path / "openbabel"
    shutil.copytree(HERRAMIENTA, destino)
    monkeypatch.setenv(open_babel.VARIABLE_DE_ENTORNO, str(destino))
    return destino


# ── AVAILABLE: el programa está, y convierte ────────────────────────────


@necesita_binario
def test_estado_available_con_verificacion_de_version():
    estado = open_babel.estado_actual(verificar_version=True)
    assert estado.estado is EstadoOpenBabel.AVAILABLE, estado.detalle
    assert estado.disponible
    assert estado.licencia_spdx == "GPL-2.0-only"
    assert estado.version_declarada == "3.1.1.23"
    # Open Babel 3.1.1 no actualizó su cadena interna de versión: contesta
    # 3.1.0. Se comprueba contra lo DECLARADO en el manifiesto, no contra un
    # número supuesto.
    assert "3.1.0" in (estado.version_reportada or "")
    assert estado.sha256 and len(estado.sha256) == 64


@necesita_binario
def test_la_ruta_publicada_es_relativa_y_no_delata_el_disco():
    estado = open_babel.estado_actual()
    assert estado.ruta_relativa == "tools/openbabel/bin/obabel.exe"
    assert ":" not in (estado.ruta_relativa or "")


@necesita_binario
def test_conversion_real_pdbqt_a_sdf():
    conversion = asyncio.run(open_babel.convertir_pdbqt_a_sdf(PDBQT_MINIMO))
    assert conversion.returncode == 0
    assert "$$$$" in conversion.contenido
    assert "V2000" in conversion.contenido
    assert open_babel.sdf_es_valido(conversion.contenido)
    # La procedencia viaja CON el resultado: quien escriba el informe no debe
    # tener que volver a preguntarle al disco quién produjo la evidencia.
    assert conversion.licencia_spdx == "GPL-2.0-only"
    assert conversion.version_declarada == "3.1.1.23"
    assert conversion.ruta_relativa == "tools/openbabel/bin/obabel.exe"
    assert len(conversion.sha256) == 64
    # Y los argumentos quedan registrados sin la ruta absoluta del ejecutable.
    assert conversion.argumentos[0] == "obabel.exe"
    assert "-ipdbqt" in conversion.argumentos and "-osdf" in conversion.argumentos


@necesita_binario
def test_la_conversion_conserva_los_atomos_de_entrada():
    """Convierte; no inventa ni descarta materia.

    Tres átomos entran, tres átomos salen. Un conversor que «arregla» la
    molécula por su cuenta cambiaría la evidencia estructural sin decirlo.
    """
    conversion = asyncio.run(open_babel.convertir_pdbqt_a_sdf(PDBQT_MINIMO))
    linea_conteo = next(
        linea for linea in conversion.contenido.splitlines() if "V2000" in linea
    )
    assert int(linea_conteo[:3]) == 3


# ── MISSING: falta el programa ──────────────────────────────────────────


def test_estado_missing_cuando_no_hay_manifiesto(tmp_path, monkeypatch):
    monkeypatch.setenv(open_babel.VARIABLE_DE_ENTORNO, str(tmp_path / "vacio"))
    estado = open_babel.estado_actual(verificar_version=True)
    assert estado.estado is EstadoOpenBabel.MISSING
    assert "instalación dañada" in estado.detalle


def test_estado_missing_cuando_falta_el_ejecutable(copia_de_la_herramienta):
    (copia_de_la_herramienta / "bin" / "obabel.exe").unlink()
    estado = open_babel.estado_actual(verificar_version=True)
    assert estado.estado is EstadoOpenBabel.MISSING
    assert "PATH" in estado.detalle
    # El manifiesto sigue leyéndose: la licencia y la procedencia se pueden
    # declarar aunque el binario no esté.
    assert estado.licencia_spdx == "GPL-2.0-only"


def test_missing_no_se_rescata_con_un_obabel_del_PATH(
    copia_de_la_herramienta, tmp_path, monkeypatch
):
    """Un binario ajeno en el PATH NO cuenta como disponible.

    Es el punto entero de la frontera: si se aceptara, el informe atribuiría el
    resultado a la versión y al hash del manifiesto mientras lo produjo otro
    programa. Se simula poniendo un `obabel.exe` en un directorio del `PATH`.
    """
    (copia_de_la_herramienta / "bin" / "obabel.exe").unlink()
    ajeno = tmp_path / "ajeno"
    ajeno.mkdir()
    impostor = ajeno / ("obabel.exe" if os.name == "nt" else "obabel")
    impostor.write_bytes(b"MZ no soy open babel")
    monkeypatch.setenv("PATH", str(ajeno) + os.pathsep + os.environ.get("PATH", ""))

    assert shutil.which("obabel") is not None, "el impostor debe estar en el PATH"
    estado = open_babel.estado_actual(verificar_version=True)
    assert estado.estado is EstadoOpenBabel.MISSING
    with pytest.raises(OpenBabelNoDisponible) as excinfo:
        asyncio.run(open_babel.convertir_pdbqt_a_sdf(PDBQT_MINIMO))
    assert excinfo.value.estado is EstadoOpenBabel.MISSING


# ── HASH_MISMATCH: el programa está, pero no es el declarado ────────────


def test_estado_hash_mismatch_con_el_ejecutable_alterado(copia_de_la_herramienta):
    exe = copia_de_la_herramienta / "bin" / "obabel.exe"
    exe.write_bytes(exe.read_bytes() + b"\x00alterado")
    estado = open_babel.estado_actual(verificar_version=True)
    assert estado.estado is EstadoOpenBabel.HASH_MISMATCH
    assert "no coincide con su manifiesto" in estado.detalle


def test_hash_mismatch_impide_la_conversion(copia_de_la_herramienta):
    """No se ejecuta un binario cuyo hash no cuadra, aunque funcionara.

    El ejecutable de la copia sigue siendo un Open Babel perfectamente
    utilizable: sólo se le han añadido bytes al final, que Windows ignora. Aun
    así no se ejecuta, porque el programa que correría no es el declarado.
    """
    exe = copia_de_la_herramienta / "bin" / "obabel.exe"
    exe.write_bytes(exe.read_bytes() + b"\x00" * 16)
    with pytest.raises(OpenBabelNoDisponible) as excinfo:
        asyncio.run(open_babel.convertir_pdbqt_a_sdf(PDBQT_MINIMO))
    assert excinfo.value.estado is EstadoOpenBabel.HASH_MISMATCH


# ── EXECUTION_FAILED: está y cuadra, pero no es el programa esperado ────


def test_estado_execution_failed_si_la_version_no_es_la_declarada(
    copia_de_la_herramienta,
):
    """El manifiesto describe un programa distinto del que hay en disco."""
    manifiesto_path = copia_de_la_herramienta / "openbabel-manifest.json"
    manifiesto = json.loads(manifiesto_path.read_text(encoding="utf-8"))
    manifiesto["version_reportada_por_el_binario"] = "9.9.9"
    manifiesto_path.write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    estado = open_babel.estado_actual(verificar_version=True)
    assert estado.estado is EstadoOpenBabel.EXECUTION_FAILED
    assert "9.9.9" in estado.detalle


def test_estado_execution_failed_si_el_ejecutable_no_arranca(copia_de_la_herramienta):
    """Un archivo con el hash correcto pero que no es un programa."""
    exe = copia_de_la_herramienta / "bin" / "obabel.exe"
    exe.write_bytes(b"no soy un ejecutable")
    manifiesto_path = copia_de_la_herramienta / "openbabel-manifest.json"
    manifiesto = json.loads(manifiesto_path.read_text(encoding="utf-8"))
    import hashlib

    manifiesto["archivos"]["bin/obabel.exe"]["sha256"] = hashlib.sha256(
        exe.read_bytes()
    ).hexdigest()
    manifiesto_path.write_text(
        json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    estado = open_babel.estado_actual(verificar_version=True)
    assert estado.estado is EstadoOpenBabel.EXECUTION_FAILED


# ── INVALID_OUTPUT: terminó bien y no produjo un SDF ────────────────────


@necesita_binario
def test_estado_invalid_output_con_entrada_que_no_es_pdbqt():
    """Medido: con basura, obabel devuelve 0 y escribe un archivo de 0 bytes.

    Ése es justo el modo de fallo peligroso — un éxito aparente con un archivo
    vacío — y el que el respaldo anterior atravesaba en silencio.
    """
    with pytest.raises(OpenBabelNoDisponible) as excinfo:
        asyncio.run(open_babel.convertir_pdbqt_a_sdf("esto no es un pdbqt\n"))
    assert excinfo.value.estado is EstadoOpenBabel.INVALID_OUTPUT


# ── El validador de SDF, con muestras que debe y no debe aceptar ────────


def test_validador_de_sdf_ve_lo_que_tiene_que_ver():
    valido = (
        "molecula\n  OpenBabel\n\n"
        "  3  2  0  0  0  0  0  0  0  0999 V2000\n"
        "    0.0000    0.0000    0.0000 C   0  0\n"
        "M  END\n$$$$\n"
    )
    assert open_babel.sdf_es_valido(valido)


@pytest.mark.parametrize(
    "muestra,motivo",
    [
        ("", "vacío"),
        ("solo texto suelto\n", "no es un SDF"),
        ("  3  2  0  0  0  0  0  0  0  0999 V2000\nM  END\n", "sin terminador"),
        ("molecula\n\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n", "cero átomos"),
        ("molecula\n\n\nM  END\n$$$$\n", "sin bloque de conteo"),
    ],
)
def test_validador_de_sdf_no_marca_de_mas(muestra, motivo):
    assert not open_babel.sdf_es_valido(muestra), f"acepta un SDF {motivo}"


# ── Contrato de licencia y procedencia ──────────────────────────────────


@necesita_binario
def test_el_manifiesto_declara_gpl_2_0_only_y_su_procedencia():
    manifiesto = json.loads(
        (HERRAMIENTA / "openbabel-manifest.json").read_text(encoding="utf-8")
    )
    assert manifiesto["licencia_spdx"] == "GPL-2.0-only", (
        "Open Babel declara GPL versión 2 sin «o posterior». Declararlo como "
        "GPL-2.0-or-later afirmaría un permiso que sus autores no dieron."
    )
    procedencia = manifiesto["procedencia"]
    assert procedencia["wheel_sha256"] == (
        "f0568906e6959fc541518c8e4cea26973e58707bd2434fb7cddfc5f745c32df7"
    )
    assert procedencia["empaquetador_commit"] == (
        "c6b2731dbd0a559ee56b8084b6d9997df1beb16f"
    )
    assert procedencia["fuentes_incorporadas_commit"] == (
        "77993b9a3b96fb9bd86249098beb97ab0fcbafc6"
    )
    assert manifiesto["version_paquete"] == "3.1.1.23", (
        "La versión se congela a propósito en 3.1.1.23: subir a 3.2.1 mezclaría "
        "una corrección arquitectónica con un cambio científico."
    )
    assert "SIN NINGUNA GARANT" in manifiesto["sin_garantia"].upper()


@necesita_binario
def test_el_texto_integro_de_la_gplv2_viaja_junto_al_programa():
    texto = (HERRAMIENTA / "LICENSE-GPL-2.0.txt").read_text(
        encoding="utf-8", errors="replace"
    )
    assert "GNU GENERAL PUBLIC LICENSE" in texto
    assert "Version 2, June 1991" in texto
    assert "NO WARRANTY" in texto


@necesita_binario
def test_hay_instrucciones_para_obtener_el_codigo_fuente_correspondiente():
    texto = (HERRAMIENTA / "README-PROCEDENCIA.md").read_text(encoding="utf-8")
    assert "77993b9a3b96fb9bd86249098beb97ab0fcbafc6" in texto
    assert "git clone" in texto
    assert "GPL-2.0-only" in texto


# ── El sistema declara su estado: preflight y capabilities ──────────────


def _control(controles, code):
    for control in controles:
        if control.code == code:
            return control
    raise AssertionError(
        f"No está el control {code}: {[c.code for c in controles]}"
    )


@necesita_binario
def test_el_preflight_declara_el_conversor_estructural():
    from services.docking.preflight import _toolchain_controls

    control = _control(_toolchain_controls("vina"), "CONVERSOR_ESTRUCTURAL_DISPONIBLE")
    assert control.state == "pasa"
    assert "3.1.1.23" in control.observation
    assert "GPL-2.0-only" in control.reason
    # Dice lo que comprobó y lo que no. Un informe que dijera «verificado» tras
    # mirar sólo el hash afirmaría de más.
    assert "no lanza procesos" in control.observation.lower()


def test_el_preflight_avisa_pero_no_bloquea_cuando_open_babel_falta(
    tmp_path, monkeypatch
):
    """Si Meeko exporta bien, Open Babel no llega a ejecutarse.

    Bloquear una corrida que iba a funcionar convertiría la comprobación en un
    estorbo. Lo que no puede pasar es que la corrida NECESITE el respaldo, no lo
    tenga y siga en silencio: de eso se encarga `vina_service`.
    """
    from services.docking.preflight import _toolchain_controls

    monkeypatch.setenv(open_babel.VARIABLE_DE_ENTORNO, str(tmp_path / "vacio"))
    control = _control(_toolchain_controls("vina"), "CONVERSOR_ESTRUCTURAL_DISPONIBLE")
    assert control.state == "advertencia"
    assert "MISSING" in control.observation
    assert "instalación dañada" in control.observation


def test_el_preflight_detecta_un_ejecutable_alterado(copia_de_la_herramienta):
    """Presente pero distinto del declarado: se dice, no se da por bueno.

    Es el tercero de los tres estados que el preflight tiene que distinguir
    —presente, ausente, alterado— y el único que un `Path.is_file()` no ve.
    """
    from services.docking.preflight import _toolchain_controls

    exe = copia_de_la_herramienta / "bin" / "obabel.exe"
    exe.write_bytes(exe.read_bytes() + b"\x00alterado")
    control = _control(_toolchain_controls("vina"), "CONVERSOR_ESTRUCTURAL_DISPONIBLE")
    assert control.state == "advertencia"
    assert "HASH_MISMATCH" in control.observation
    assert "no coincide con su manifiesto" in control.observation


def test_el_preflight_no_lanza_ningun_proceso_para_este_control(monkeypatch):
    """El presupuesto del preflight es cero subprocesos. También para esto."""
    import subprocess

    from services.docking.preflight import _toolchain_controls

    def _explota(*args, **kwargs):  # pragma: no cover - sólo si hay regresión
        raise AssertionError("el control del conversor lanzó un proceso")

    monkeypatch.setattr(subprocess, "run", _explota)
    monkeypatch.setattr(subprocess, "Popen", _explota)
    _control(_toolchain_controls("vina"), "CONVERSOR_ESTRUCTURAL_DISPONIBLE")


@necesita_binario
def test_health_publica_el_estado_del_conversor_con_su_licencia():
    """La UI necesita poder mostrarlo, y con la procedencia, no sólo un booleano."""
    from api.main import _check_open_babel_health

    salud = _check_open_babel_health()
    assert salud["status"] == "healthy"
    assert salud["estado"] == "AVAILABLE"
    assert salud["licencia_spdx"] == "GPL-2.0-only"
    assert salud["version"] == "3.1.1.23"
    assert salud["invocacion"] == "subproceso CLI"
    assert salud["programa_independiente"] is True
    assert salud["path"] == "tools/openbabel/bin/obabel.exe"


def test_health_lo_reporta_degradado_y_no_tumba_la_aplicacion(tmp_path, monkeypatch):
    """`open_babel` no es un componente `core`: que falte no impide abrir.

    El arranque ya lo exige antes, en `bundled_layout` del contenedor Tauri; y
    una corrida que necesite el respaldo se abstiene con motivo. Tumbar `/health`
    además habría dejado la aplicación sin abrir por una herramienta de respaldo.
    """
    from api import main as api_main

    monkeypatch.setenv(open_babel.VARIABLE_DE_ENTORNO, str(tmp_path / "vacio"))
    salud = api_main._check_open_babel_health()
    assert salud["status"] == "degraded"
    assert salud["estado"] == "MISSING"

    fuente = inspect.getsource(api_main.health)
    assert 'core_components = {"rdkit", "vina", "database"}' in fuente, (
        "Si `open_babel` entrara en `core_components`, una instalación sin el "
        "conversor de respaldo devolvería 503 y la aplicación no abriría."
    )
