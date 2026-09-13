"""ENG-002 — infraestructura de motores que se descargan bajo demanda.

ESMFold son 8.4 GB: no cabe en el instalador y por eso se descarga cuando el
investigador lo pide. Que esa promesa se cumpla exige cuatro cosas, y ninguna
estaba: saber si los archivos están, saber si el runtime puede cargarlos,
encender el proceso que los sirve, y decir en cuál de esos pasos falta algo.

Lo que estas pruebas fijan, y por qué cada una:

* **Los archivos pequeños cuentan tanto como el tensor.** `from_pretrained`
  necesita `config.json`, `vocab.txt`, `tokenizer_config.json` y
  `special_tokens_map.json`. El manifiesto bajaba sólo `pytorch_model.bin`: 8.4 GB
  que por sí solos no cargan.
* **El checkpoint se lee del disco.** El servicio hacía
  `from_pretrained("facebook/esmfold_v1")` —resolución por nombre, contra la red—
  ignorando el directorio descargado. En una aplicación que declara cero red
  implícita eso no puede quedarse.
* **Encender es explícito y verificable.** El estado sale de que `/health`
  conteste, no de que el proceso exista.
* **Cada estado trae su acción.** «No disponible» a secas manda a mirar al sitio
  equivocado: no es lo mismo que falten los pesos, que falte `transformers`, o que
  esté instalado y apagado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from services.motores import catalogo
from services.motores.catalogo import (
    CATALOGO,
    MotorDescargable,
    SidecarSpec,
    estado_de,
)

ROOT = Path(__file__).resolve().parents[2]
SIDECAR = ROOT / "backend" / "sidecars" / "esmfold"
MANIFIESTO = ROOT / "launcher-manifest.json"


def _motor_de_prueba(tmp_path: Path, archivos: tuple[str, ...]) -> MotorDescargable:
    return MotorDescargable(
        id="motor-prueba",
        etiqueta="Motor de prueba",
        familia="peptido",
        modulo_launcher="modulo-prueba",
        archivos=archivos,
        bytes_descarga=1_500_000_000,
        dependencias_python=(),
        sidecar=SidecarSpec(paquete="esmfold", app="app:app", puerto=8199),
    )


# ── El catálogo declara lo que de verdad hace falta ──────────────────────────


def test_esmfold_exige_el_tokenizer_y_no_solo_los_pesos():
    esmfold = next(m for m in CATALOGO if m.id == "esmfold")
    requeridos = set(esmfold.archivos)
    for pequeno in (
        "esmfold/models/config.json",
        "esmfold/models/vocab.txt",
        "esmfold/models/tokenizer_config.json",
        "esmfold/models/special_tokens_map.json",
    ):
        assert pequeno in requeridos, (
            f"{pequeno} hace falta para leer el checkpoint y el catálogo no lo pide: "
            "se podría dar por instalado un modelo que no carga"
        )
    assert "esmfold/models/pytorch_model.bin" in requeridos


def test_el_instalador_lleva_el_tokenizer():
    """Los KB viajan en el instalador; los GB se descargan. Sin esto, el módulo
    descargado no sirve para nada."""
    bundler = (ROOT / "scripts" / "bundle_helper.py").read_text(encoding="utf-8")
    assert "esmfold" in bundler and "tokenizer_config.json" in bundler, (
        "bundle_helper no copia los archivos pequeños de esmfold/models"
    )
    pequenos = ("config.json", "vocab.txt", "tokenizer_config.json",
                "special_tokens_map.json")
    faltan = [n for n in pequenos if not (ROOT / "esmfold" / "models" / n).is_file()]
    if faltan:
        # `esmfold/models/` se descarga desde el gestor de modelos: no viaja en
        # el repositorio. Que falte no prueba que bundle_helper esté mal -eso lo
        # comprueba la asercion de arriba, que si es reproducible-; prueba que
        # este arbol no ha descargado el modelo.
        import os

        if os.environ.get("MOLDESIGN_EXIGE_MOTORES") == "1":
            raise AssertionError(f"motores exigidos y ausentes: {', '.join(faltan)}")
        pytest.skip(
            "esmfold/models no descargado en este arbol: "
            + ", ".join(faltan)
            + ". Define MOLDESIGN_EXIGE_MOTORES=1 para exigirlo."
        )


def test_el_modulo_del_launcher_existe_en_el_manifiesto():
    manifiesto = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    ids = {m.get("id") for m in manifiesto.get("modules", [])}
    for motor in CATALOGO:
        if motor.modulo_launcher:
            assert motor.modulo_launcher in ids, (
                f"{motor.id} apunta al módulo '{motor.modulo_launcher}', que el "
                "manifiesto no ofrece: la acción «descargar» no llevaría a ningún sitio"
            )


# ── Estados: cada uno con su motivo y su acción ──────────────────────────────


def test_sin_archivos_el_estado_es_no_instalado_y_la_accion_es_descargar(tmp_path, monkeypatch):
    monkeypatch.setattr(catalogo, "directorios_de_busqueda", lambda: [tmp_path])
    estado = estado_de(_motor_de_prueba(tmp_path, ("modelo/peso.bin",)))
    assert estado.estado == "no_instalado"
    assert estado.accion == "descargar"
    assert estado.disponible is False
    assert "1.5 GB" in (estado.motivo or ""), "el tamaño se dice ANTES de descargar"


def test_una_descarga_a_medias_se_distingue_de_no_haber_empezado(tmp_path, monkeypatch):
    monkeypatch.setattr(catalogo, "directorios_de_busqueda", lambda: [tmp_path])
    (tmp_path / "modelo").mkdir()
    (tmp_path / "modelo" / "config.json").write_text("{}", encoding="utf-8")

    estado = estado_de(
        _motor_de_prueba(tmp_path, ("modelo/peso.bin", "modelo/config.json"))
    )
    assert estado.estado == "no_instalado"
    assert "incompleta" in (estado.motivo or ""), (
        "una descarga interrumpida y una descarga nunca iniciada llevan a acciones "
        "distintas y el aviso tiene que distinguirlas"
    )
    assert estado.archivos_faltantes == ("modelo/peso.bin",)


def test_faltando_una_libreria_el_motivo_no_habla_de_descargar(tmp_path, monkeypatch):
    monkeypatch.setattr(catalogo, "directorios_de_busqueda", lambda: [tmp_path])
    (tmp_path / "modelo").mkdir()
    (tmp_path / "modelo" / "peso.bin").write_text("x", encoding="utf-8")

    motor = MotorDescargable(
        id="motor-prueba", etiqueta="Motor de prueba", familia="peptido",
        modulo_launcher=None, archivos=("modelo/peso.bin",), bytes_descarga=1,
        dependencias_python=("una_libreria_que_no_existe",),
    )
    estado = estado_de(motor)
    assert estado.estado == "dependencias_faltantes"
    assert estado.accion is None, "descargar de nuevo no arreglaría una librería ausente"
    assert "una_libreria_que_no_existe" in (estado.motivo or "")


def test_instalado_y_apagado_ofrece_encender(tmp_path, monkeypatch):
    monkeypatch.setattr(catalogo, "directorios_de_busqueda", lambda: [tmp_path])
    (tmp_path / "modelo").mkdir()
    (tmp_path / "modelo" / "peso.bin").write_text("x", encoding="utf-8")

    estado = estado_de(_motor_de_prueba(tmp_path, ("modelo/peso.bin",)))
    assert estado.estado == "instalado_apagado"
    assert estado.accion == "encender"
    assert estado.disponible is False, "apagado no es disponible"


def test_encendido_es_lo_unico_que_declara_disponible(tmp_path, monkeypatch):
    monkeypatch.setattr(catalogo, "directorios_de_busqueda", lambda: [tmp_path])
    (tmp_path / "modelo").mkdir()
    (tmp_path / "modelo" / "peso.bin").write_text("x", encoding="utf-8")

    estado = estado_de(_motor_de_prueba(tmp_path, ("modelo/peso.bin",)), encendido=True)
    assert estado.estado == "listo"
    assert estado.disponible is True


# ── El servicio carga del disco, no de la red ────────────────────────────────


def _sin_comentarios(texto: str) -> str:
    """Sólo lo que se ejecuta. Un comentario que explica el defecto retirado no
    es el defecto."""
    lineas = [
        linea.split("#", 1)[0]
        for linea in texto.splitlines()
        if not linea.strip().startswith("#")
    ]
    return chr(10).join(lineas)


def test_el_sidecar_carga_del_directorio_local_y_no_por_nombre():
    fuente = _sin_comentarios((SIDECAR / "predictor.py").read_text(encoding="utf-8"))
    assert 'from_pretrained("facebook/esmfold_v1")' not in fuente, (
        "resolver el modelo por su nombre lo descarga de HuggingFace en tiempo de "
        "ejecución e ignora los pesos que el investigador ya bajó"
    )
    assert fuente.count("local_files_only=True") >= 2, (
        "tokenizer y modelo tienen que cargarse con local_files_only"
    )


def test_el_sidecar_viaja_en_el_arbol_que_el_instalador_copia():
    """Vivía en `<raíz>/esmfold/`, que `bundle_helper` no copia: el instalador
    salía sin el servicio, así que los pesos no tenían quién los sirviera."""
    assert (SIDECAR / "app.py").is_file()
    assert (SIDECAR / "predictor.py").is_file()
    assert not (ROOT / "esmfold" / "app.py").exists(), (
        "quedó una copia del servicio fuera del árbol empaquetado: dos "
        "implementaciones del mismo motor divergen en cuanto una cambia"
    )


def test_el_logger_del_sidecar_acepta_campos():
    """Reventaba en el arranque con `Logger.info() got multiple values for 'msg'`.

    El servicio se escribió con la sintaxis de structlog y `get_logger` devolvía
    un logger estándar. Fallaba en la línea que anuncia el predictor creado: el
    proceso no llegaba a servir una sola petición.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location("_esmfold_logger", SIDECAR / "logger.py")
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)

    log = modulo.get_logger("prueba")
    log.info("evento", clave="valor", numero=3)  # no debe lanzar
    log.warning("otro", motivo="x")
    log.error("malo", error="y")


# ── El supervisor: arranca de verdad, sin necesitar los 8.4 GB ───────────────


def test_el_supervisor_enciende_sondea_y_apaga(tmp_path, monkeypatch):
    """Recorre la infraestructura entera en modo stub.

    El modo stub existe justamente para esto: comprobar que el proceso se lanza,
    que `/health` contesta y que apagar deja el puerto libre, sin depender de un
    checkpoint de 8.4 GB ni de una GPU.
    """
    from services.motores.sidecar import MotorSidecar

    # La prueba se declara autonoma -"sin depender de un checkpoint de 8.4
    # GB"- pero buscaba en ROOT, donde `esmfold/models/config.json` solo
    # existe si alguien descargo el modelo. En un clon limpio `encender`
    # se negaba y la prueba fallaba por la razon equivocada. Se fabrica el
    # archivo que declara necesitar: asi comprueba la infraestructura del
    # sidecar, que es lo suyo, y no el estado de descargas de la maquina.
    (tmp_path / "esmfold" / "models").mkdir(parents=True, exist_ok=True)
    (tmp_path / "esmfold" / "models" / "config.json").write_text(
        "{}", encoding="utf-8"
    )
    monkeypatch.setattr(catalogo, "directorios_de_busqueda", lambda: [tmp_path])
    motor = MotorDescargable(
        id="esmfold-prueba", etiqueta="ESMFold", familia="peptido",
        modulo_launcher=None, archivos=("esmfold/models/config.json",),
        bytes_descarga=0, dependencias_python=(),
        sidecar=SidecarSpec(paquete="esmfold", app="app:app", puerto=8199),
    )
    sc = MotorSidecar(motor)
    try:
        assert sc.encender(modo="stub"), f"no encendió: {sc.error}"
        assert sc.responde()
        assert sc.estado().estado == "listo"
    finally:
        sc.apagar()
    assert not sc.responde(), "el proceso siguió sirviendo después de apagarlo"
