"""
Contrato del paquete reproducible y de su verificador.

El criterio de salida de `docs/53 §6.6` es concreto: **una tercera persona debe
poder detectar cualquier archivo ausente o modificado.** Estas pruebas lo
ejercitan en los dos sentidos —el paquete íntegro verifica, el alterado no— y
cubren los ataques que un verificador ingenuo dejaría pasar: zip-slip, rutas
absolutas, duplicados y archivos colados.

También fijan el determinismo: con el reloj congelado, el mismo caso produce el
mismo ZIP byte a byte. Sin eso el verificador no distinguiría un cambio real de
un cambio de hora.
"""

from __future__ import annotations

import hashlib
import io
import json
import warnings
import zipfile

import pytest

from services.dossier.model import Artefacto, build_case_dossier
from services.dossier.package import CHECKSUMS_NAME, construir_paquete, raiz_paquete, sanitizar
from services.dossier.pdf import render_dossier_pdf
from services.dossier.taxonomy import Estado
from services.dossier.verify import verificar_paquete
from tests.fixtures_dossier import caso_completo, caso_parcial


def _artefactos(con_poses: bool = True) -> list[Artefacto]:
    return [
        Artefacto(
            "outputs", "poses.sdf", "chemical/x-mdl-sdfile", "eval_result.poses_file_path",
            Estado.REGISTRADO if con_poses else Estado.NO_DISPONIBLE,
            b"pose-sdf\n" if con_poses else None,
            None if con_poses else "La corrida no serializó poses.",
        ),
        Artefacto(
            "inputs", "ligand.smi", "chemical/x-daylight-smiles", "molecule.smiles",
            Estado.REGISTRADO, b"CC(=O)Oc1ccccc1C(=O)O\n",
        ),
    ]


def _paquete(datos=None, con_poses: bool = True) -> tuple[bytes, list, str]:
    datos = datos or caso_completo()
    dossier = build_case_dossier(**datos)
    pdf = render_dossier_pdf(dossier).getvalue()
    return construir_paquete(
        dossier=dossier,
        pdf_bytes=pdf,
        projection_json=datos["projection"].model_dump_json(indent=2),
        artefactos=_artefactos(con_poses),
    )


def _rehacer(zip_bytes: bytes, transform) -> bytes:
    """Reconstruye un ZIP aplicando `transform(nombre, datos)`. `None` lo omite."""
    origen = zipfile.ZipFile(io.BytesIO(zip_bytes))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as destino:
        for info in origen.infolist():
            resultado = transform(info.filename, origen.read(info.filename))
            if resultado is None:
                continue
            destino.writestr(*resultado)
    return buf.getvalue()


# ── 1. Estructura ────────────────────────────────────────────────────


class TestEstructura:
    def test_arbol_del_paquete(self):
        datos, entradas, raiz = _paquete()
        nombres = sorted(zipfile.ZipFile(io.BytesIO(datos)).namelist())

        assert raiz.startswith("moldesign_case_")
        esperados = {
            f"{raiz}/README.md",
            f"{raiz}/dossier.pdf",
            f"{raiz}/manifest.json",
            f"{raiz}/{CHECKSUMS_NAME}",
            f"{raiz}/case/case_snapshot.json",
            f"{raiz}/case/dossier_model.json",
            f"{raiz}/run/protocol.json",
            f"{raiz}/run/reproduce.md",
            f"{raiz}/evidencia/evidence_summary.json",
            f"{raiz}/inputs/ligand.smi",
            f"{raiz}/outputs/poses.sdf",
        }
        assert esperados <= set(nombres), esperados - set(nombres)

    def test_una_sola_raiz_y_ningun_directorio_suelto(self):
        datos, _, raiz = _paquete()
        for nombre in zipfile.ZipFile(io.BytesIO(datos)).namelist():
            assert nombre.startswith(f"{raiz}/")
            assert not nombre.endswith("/")

    def test_la_raiz_se_sanitiza(self):
        assert "/" not in raiz_paquete("caso/../../x", "t")
        assert ".." not in raiz_paquete("caso/../../x", "t")
        assert sanitizar("  Serie A / B  ") == "Serie-A-B"
        assert sanitizar("") == "sin-nombre"

    def test_el_manifiesto_declara_rol_tamano_y_hash(self):
        datos, _, raiz = _paquete()
        with zipfile.ZipFile(io.BytesIO(datos)) as zf:
            manifiesto = json.loads(zf.read(f"{raiz}/manifest.json"))

        assert manifiesto["manifest_version"] == 1
        for entrada in manifiesto["files"]:
            assert set(entrada) >= {
                "path", "rol", "media_type", "tamano", "sha256", "fuente", "estado",
            }
            assert "\\" not in entrada["path"], "los paths se normalizan con /"
            if entrada["estado"] == "REGISTRADO":
                assert entrada["sha256"] and entrada["tamano"] is not None

    def test_un_artefacto_ausente_se_declara_no_disponible(self):
        """No se fabrica un marcador que parezca el artefacto."""
        datos, entradas, raiz = _paquete(con_poses=False)
        with zipfile.ZipFile(io.BytesIO(datos)) as zf:
            nombres = zf.namelist()
            manifiesto = json.loads(zf.read(f"{raiz}/manifest.json"))
            readme = zf.read(f"{raiz}/README.md").decode("utf-8")

        assert f"{raiz}/outputs/poses.sdf" not in nombres
        poses = next(e for e in manifiesto["files"] if e["path"] == "outputs/poses.sdf")
        assert poses["estado"] == "NO_DISPONIBLE"
        assert poses["sha256"] is None
        assert poses["razon"]
        # Y la ausencia se explica en el README, no sólo en el JSON.
        assert "outputs/poses.sdf" in readme

    def test_checksums_ordenado_y_normalizado(self):
        datos, _, raiz = _paquete()
        with zipfile.ZipFile(io.BytesIO(datos)) as zf:
            lineas = zf.read(f"{raiz}/{CHECKSUMS_NAME}").decode("utf-8").strip().split("\n")

        assert lineas == sorted(lineas)
        for linea in lineas:
            sha, path = linea.split("  ", 1)
            assert len(sha) == 64
            assert "\\" not in path
            assert not path.startswith("/")
        # No se hashea a sí mismo.
        assert not any(l.endswith(CHECKSUMS_NAME) for l in lineas)

    def test_checksums_cubre_el_manifiesto(self):
        """
        El manifiesto no se declara a sí mismo, pero no queda sin comprobar.
        """
        datos, _, raiz = _paquete()
        with zipfile.ZipFile(io.BytesIO(datos)) as zf:
            lineas = zf.read(f"{raiz}/{CHECKSUMS_NAME}").decode("utf-8")
        assert "manifest.json" in lineas

    def test_modificar_el_manifiesto_sin_actualizar_checksums_invalida(self):
        """El manifiesto define la confianza del paquete y debe estar hasheado."""
        original, _, _ = _paquete()

        def modificar(nombre, datos):
            if nombre.endswith("manifest.json"):
                manifiesto = json.loads(datos)
                manifiesto["case_id"] = "caso-alterado"
                return nombre, json.dumps(manifiesto, ensure_ascii=False).encode("utf-8")
            return nombre, datos

        resultado = verificar_paquete(_rehacer(original, modificar))
        assert not resultado.valido
        assert any("manifest.json" in e and "checksums" in e for e in resultado.errores)


# ── 2. Determinismo ──────────────────────────────────────────────────


class TestDeterminismo:
    def test_mismo_caso_y_mismo_reloj_producen_el_mismo_zip(self):
        primero, _, _ = _paquete()
        segundo, _, _ = _paquete()
        assert hashlib.sha256(primero).hexdigest() == hashlib.sha256(segundo).hexdigest()

    def test_los_timestamps_del_zip_estan_congelados(self):
        datos, _, _ = _paquete()
        for info in zipfile.ZipFile(io.BytesIO(datos)).infolist():
            assert info.date_time == (1980, 1, 1, 0, 0, 0)

    def test_el_orden_de_entradas_es_estable(self):
        primero = zipfile.ZipFile(io.BytesIO(_paquete()[0])).namelist()
        segundo = zipfile.ZipFile(io.BytesIO(_paquete()[0])).namelist()
        assert primero == segundo == sorted(primero)


# ── 3. Sin filtraciones ──────────────────────────────────────────────


class TestSinFiltraciones:
    def test_no_hay_rutas_locales_ni_secretos_en_el_paquete(self):
        from pathlib import Path
        import re

        datos, _, _ = _paquete()
        with zipfile.ZipFile(io.BytesIO(datos)) as zf:
            textos = [
                zf.read(n).decode("utf-8", "ignore")
                for n in zf.namelist()
                if not n.endswith(".pdf")
            ]
        todo = "\n".join(textos)

        assert str(Path.home()) not in todo
        assert re.search(r"[A-Za-z]:\\\\Users", todo) is None
        for secreto in ("api_key", "OPENAI_API_KEY", "Bearer ", "-----BEGIN"):
            assert secreto not in todo

    def test_no_se_incluye_ningun_env_ni_base_de_datos(self):
        datos, _, _ = _paquete()
        for nombre in zipfile.ZipFile(io.BytesIO(datos)).namelist():
            assert not nombre.endswith((".env", ".db", ".sqlite", ".sqlite3"))


# ── 4. Verificador: paquete íntegro ──────────────────────────────────


class TestVerificadorIntegro:
    def test_el_paquete_recien_creado_es_valido(self):
        datos, _, _ = _paquete()
        resultado = verificar_paquete(datos)
        assert resultado.valido, resultado.errores
        assert resultado.manifest_version == 1
        assert resultado.archivos_presentes == resultado.archivos_declarados

    def test_el_paquete_parcial_tambien_verifica(self):
        """Un artefacto ausente DECLARADO no invalida el paquete."""
        datos, _, _ = _paquete(caso_parcial(), con_poses=False)
        resultado = verificar_paquete(datos)
        assert resultado.valido, resultado.errores

    def test_el_informe_dice_valido(self):
        datos, _, _ = _paquete()
        assert "VÁLIDO" in verificar_paquete(datos).informe()


# ── 5. Verificador: paquete alterado ─────────────────────────────────


class TestVerificadorDetectaAlteraciones:
    def test_archivo_modificado(self):
        original, _, raiz = _paquete()

        def modificar(nombre, datos):
            if nombre.endswith("README.md"):
                return nombre, datos + b"\n<!-- alterado -->\n"
            return nombre, datos

        resultado = verificar_paquete(_rehacer(original, modificar))
        assert not resultado.valido
        assert any("README.md" in e for e in resultado.errores)

    def test_archivo_faltante(self):
        original, _, _ = _paquete()

        def borrar(nombre, datos):
            return None if nombre.endswith("run/protocol.json") else (nombre, datos)

        resultado = verificar_paquete(_rehacer(original, borrar))
        assert not resultado.valido
        assert any("Falta el archivo declarado" in e for e in resultado.errores)

    def test_archivo_adicional_no_declarado(self):
        original, _, raiz = _paquete()
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as origen:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as destino:
                for nombre in origen.namelist():
                    destino.writestr(nombre, origen.read(nombre))
                destino.writestr(f"{raiz}/extra/colado.txt", b"no declarado\n")

        resultado = verificar_paquete(buf.getvalue())
        assert not resultado.valido
        assert any("colado.txt" in e for e in resultado.errores)

    def test_entrada_duplicada(self):
        original, _, raiz = _paquete()
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as origen:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as destino:
                for nombre in origen.namelist():
                    destino.writestr(nombre, origen.read(nombre))
                # La misma ruta dos veces: el lector ingenuo sólo ve la última.
                # El aviso de `zipfile` es DESEADO aquí —el zip malicioso se
                # fabrica a propósito— y se silencia sólo en esta línea para que
                # no se confunda con un aviso nuevo en la salida de la suite.
                # Silenciarlo global taparía duplicados accidentales.
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    destino.writestr(f"{raiz}/README.md", b"duplicado\n")

        resultado = verificar_paquete(buf.getvalue())
        assert not resultado.valido
        assert any("duplicada" in e.lower() for e in resultado.errores)

    def test_path_traversal(self):
        """Zip-slip: la razón por la que el verificador nunca extrae."""
        original, _, raiz = _paquete()
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as origen:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as destino:
                for nombre in origen.namelist():
                    destino.writestr(nombre, origen.read(nombre))
                destino.writestr(f"{raiz}/../../escapado.txt", b"zip slip\n")

        resultado = verificar_paquete(buf.getvalue())
        assert not resultado.valido
        assert any("escape de directorio" in e for e in resultado.errores)

    def test_ruta_absoluta(self):
        original, _, _ = _paquete()
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as origen:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as destino:
                for nombre in origen.namelist():
                    destino.writestr(nombre, origen.read(nombre))
                destino.writestr("/etc/passwd", b"absoluta\n")

        resultado = verificar_paquete(buf.getvalue())
        assert not resultado.valido
        assert any("absoluta" in e for e in resultado.errores)

    def test_manifiesto_de_version_futura_no_se_da_por_bueno(self):
        original, _, raiz = _paquete()

        def subir_version(nombre, datos):
            if nombre.endswith("manifest.json"):
                manifiesto = json.loads(datos)
                manifiesto["manifest_version"] = 99
                return nombre, json.dumps(manifiesto).encode("utf-8")
            return nombre, datos

        resultado = verificar_paquete(_rehacer(original, subir_version))
        assert not resultado.valido
        assert any("v99" in e for e in resultado.errores)

    def test_manifiesto_ausente(self):
        original, _, _ = _paquete()

        def borrar(nombre, datos):
            return None if nombre.endswith("manifest.json") else (nombre, datos)

        resultado = verificar_paquete(_rehacer(original, borrar))
        assert not resultado.valido
        assert any("manifest.json" in e for e in resultado.errores)

    def test_zip_corrupto(self):
        resultado = verificar_paquete(b"esto no es un zip")
        assert not resultado.valido
        assert any("no es un ZIP" in e for e in resultado.errores)

    def test_un_artefacto_declarado_ausente_que_SI_aparece_es_incoherente(self):
        """Declarar `NO_DISPONIBLE` y luego incluirlo miente sobre el paquete."""
        original, _, raiz = _paquete(con_poses=False)
        buf = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as origen:
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as destino:
                for nombre in origen.namelist():
                    destino.writestr(nombre, origen.read(nombre))
                destino.writestr(f"{raiz}/outputs/poses.sdf", b"aparecido\n")

        resultado = verificar_paquete(buf.getvalue())
        assert not resultado.valido
        assert any("SÍ lo contiene" in e for e in resultado.errores)


# ── 6. CLI ───────────────────────────────────────────────────────────


class TestCli:
    def test_la_cli_devuelve_0_para_un_paquete_valido(self, tmp_path):
        import subprocess
        import sys
        from pathlib import Path

        datos, _, _ = _paquete()
        destino = tmp_path / "paquete.zip"
        destino.write_bytes(datos)
        script = Path(__file__).resolve().parents[2] / "scripts" / "verify_dossier_package.py"

        proceso = subprocess.run(
            [sys.executable, str(script), str(destino)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            # La consola de Windows usa una página de códigos que destroza los
            # acentos al capturar. Se fija UTF-8 para leer lo que el verificador
            # escribe de verdad, no lo que sobrevive al terminal.
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        assert proceso.returncode == 0, proceso.stdout + proceso.stderr
        assert "VÁLIDO" in proceso.stdout

    def test_la_cli_devuelve_1_para_un_paquete_alterado(self, tmp_path):
        import subprocess
        import sys
        from pathlib import Path

        original, _, _ = _paquete()

        def modificar(nombre, datos):
            return (nombre, datos + b"x") if nombre.endswith("README.md") else (nombre, datos)

        destino = tmp_path / "alterado.zip"
        destino.write_bytes(_rehacer(original, modificar))
        script = Path(__file__).resolve().parents[2] / "scripts" / "verify_dossier_package.py"

        proceso = subprocess.run(
            [sys.executable, str(script), str(destino)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"},
        )
        assert proceso.returncode == 1
        assert "INVÁLIDO" in proceso.stdout

    def test_la_cli_distingue_no_poder_leer_de_estar_mal(self, tmp_path):
        """Exit 2: «no pude comprobarlo» no es «lo comprobé y está mal»."""
        import subprocess
        import sys
        from pathlib import Path

        script = Path(__file__).resolve().parents[2] / "scripts" / "verify_dossier_package.py"
        proceso = subprocess.run(
            [sys.executable, str(script), str(tmp_path / "no-existe.zip")],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        assert proceso.returncode == 2
