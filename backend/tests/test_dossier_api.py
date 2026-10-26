"""
Contrato HTTP del dossier: autorización, errores distinguibles y legado intacto.

Estas pruebas ejercitan el router a través de la app real, con las dependencias
de base de datos sobrescritas. Lo que fijan:

1. **Autorización.** Un dossier lleva SMILES, poses y procedencia. Que su ruta
   sea nueva no la exime de `require_owned_molecule`.
2. **Errores que se distinguen.** 404, 403 y 409 significan cosas distintas y el
   cliente tiene que poder actuar sobre cada uno.
3. **El 409 del `task_id`.** Empaquetar en silencio un resultado de otra corrida
   produciría un dossier que afirma describir algo que no describe.
4. **Que `/blockchain/certificate` siga existiendo.** La superficie nueva no
   sustituye a la anterior en este sprint.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from api.dependencies import get_current_user_optional
from api.routers import evaluation_dossier as router_mod
from core.database import get_db
from tests.fixtures_dossier import (
    molecula,
    proyeccion_completa,
    resultado_completo,
    target_completo,
)

MOLECULE_ID = uuid.UUID("11111111-2222-4333-8444-555555555555")


class _DbFalsa:
    """
    Sustituto mínimo de la sesión.

    Devuelve la molécula y el resultado que se le den, sin tocar SQLite: estas
    pruebas comprueban el CONTRATO del router, no el ORM.
    """

    def __init__(self, molecule, eval_result):
        self._molecule = molecule
        self._eval_result = eval_result

    async def get(self, modelo, identificador):
        return self._molecule

    async def scalar(self, stmt):
        texto = str(stmt).lower()
        if "evaluation_runs" in texto or "evaluationrun" in texto:
            return None
        if "evaluation_results" in texto or "evaluationresult" in texto:
            return self._eval_result
        return self._molecule


def _app(
    molecule=None, eval_result=None, autorizado: bool = True, *, localization_middleware: bool = False,
) -> TestClient:
    """App mínima con sólo el router del dossier y sus dependencias falseadas."""
    aplicacion = FastAPI()
    aplicacion.include_router(router_mod.router, prefix="/evaluation")
    if localization_middleware:
        from api.middleware import register_middleware

        register_middleware(aplicacion)

    db = _DbFalsa(molecule, eval_result)
    aplicacion.dependency_overrides[get_db] = lambda: db
    aplicacion.dependency_overrides[get_current_user_optional] = lambda: None

    async def _require(**kwargs):
        if not autorizado:
            raise HTTPException(status_code=403, detail="No tienes permiso.")
        if molecule is None:
            raise HTTPException(status_code=404, detail="No existe la molécula solicitada.")
        return molecule

    router_mod.require_owned_molecule = _require  # type: ignore[assignment]
    return TestClient(aplicacion)


@pytest.fixture
def proyeccion() -> dict:
    return proyeccion_completa().model_dump(mode="json")


class TestAutorizacion:
    def test_sin_permiso_devuelve_403(self, proyeccion):
        cliente = _app(molecula(), resultado_completo(), autorizado=False)
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion)
        assert respuesta.status_code == 403

    def test_molecula_inexistente_devuelve_404(self, proyeccion):
        cliente = _app(None, None)
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion)
        assert respuesta.status_code == 404

    def test_sin_resultado_de_evaluacion_devuelve_404(self, proyeccion):
        """Una molécula sin corrida no tiene evidencia que documentar."""
        cliente = _app(molecula(), None)
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion)
        assert respuesta.status_code == 404
        assert "resultado" in respuesta.json()["detail"].lower()


class TestConflictoDeCorrida:
    def test_task_id_discordante_devuelve_409(self, proyeccion):
        resultado = resultado_completo()
        resultado.task_id = "task-de-otra-corrida"
        cliente = _app(molecula(), resultado)

        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/package", json=proyeccion)

        assert respuesta.status_code == 409
        assert "no corresponde" in respuesta.json()["detail"]

    def test_task_id_coincidente_no_bloquea(self, proyeccion):
        cliente = _app(molecula(), resultado_completo())
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion)
        assert respuesta.status_code == 200


class TestSalidas:
    def test_preview_devuelve_pdf_inline(self, proyeccion):
        cliente = _app(molecula(), resultado_completo())
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion)

        assert respuesta.status_code == 200
        assert respuesta.headers["content-type"].startswith("application/pdf")
        assert respuesta.headers["content-disposition"].startswith("inline;")
        assert respuesta.content.startswith(b"%PDF")

    def test_package_devuelve_zip_adjunto(self, proyeccion):
        cliente = _app(molecula(), resultado_completo())
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/package", json=proyeccion)

        assert respuesta.status_code == 200
        assert respuesta.headers["content-type"] == "application/zip"
        assert respuesta.headers["content-disposition"].startswith("attachment;")
        assert respuesta.content[:2] == b"PK"

    def test_el_paquete_de_la_ruta_lleva_la_auditoria_de_preparacion(self, proyeccion):
        """Punto 3: quien reciba el ZIP lee el veredicto sin recalcularlo (necesita otro disco)."""
        import io
        import json
        import zipfile

        cliente = _app(molecula(), resultado_completo())
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/package", json=proyeccion)

        with zipfile.ZipFile(io.BytesIO(respuesta.content)) as zf:
            raiz = zf.namelist()[0].split("/")[0]
            auditoria = json.loads(zf.read(f"{raiz}/preparacion/audit.json"))
            manifiesto = json.loads(zf.read(f"{raiz}/manifest.json"))
        assert auditoria["schema"] == "preparacion/v1"
        assert auditoria["estado"] in ("BLOQUEADO", "REVISION", "TRANSFERIBLE")
        assert manifiesto["preparacion"]["estado"] == auditoria["estado"]
        # Y el crudo depositado se declara: presente si la receta coincide, ausente con su razón.
        origen = next(f for f in manifiesto["files"] if f["path"].endswith("_source.pdb"))
        assert origen["estado"] == "REGISTRADO" or origen["razon"]

    def test_el_paquete_devuelto_verifica(self, proyeccion):
        """El extremo a extremo: lo que sale por HTTP es íntegro."""
        from services.dossier.verify import verificar_paquete

        cliente = _app(molecula(), resultado_completo())
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/package", json=proyeccion)
        resultado = verificar_paquete(respuesta.content)
        assert resultado.valido, resultado.errores

    def test_accept_language_en_traduce_el_zip_pdf_y_modelo_sin_traducir_el_nombre(self, proyeccion):
        import io
        import json
        import zipfile

        pypdf = pytest.importorskip("pypdf", reason="extracción semántica del PDF")
        PdfReader = pypdf.PdfReader
        from services.dossier.verify import verificar_paquete

        nombre = "2 elegidos de 8 del catálogo: Aspirina"
        proyeccion["name"] = nombre
        cliente = _app(molecula(), resultado_completo(), localization_middleware=True)
        respuesta = cliente.post(
            f"/evaluation/dossier/{MOLECULE_ID}/package",
            json=proyeccion,
            headers={"Accept-Language": "en"},
        )

        assert respuesta.status_code == 200
        assert respuesta.headers["content-language"] == "en"
        assert verificar_paquete(respuesta.content).valido
        with zipfile.ZipFile(io.BytesIO(respuesta.content)) as archivo:
            raiz = archivo.namelist()[0].split("/")[0]
            readme = archivo.read(f"{raiz}/README.md").decode("utf-8")
            receta = archivo.read(f"{raiz}/run/reproduce.md").decode("utf-8")
            modelo = json.loads(archivo.read(f"{raiz}/case/dossier_model.json"))
            manifiesto = json.loads(archivo.read(f"{raiz}/manifest.json"))
            pdf = PdfReader(io.BytesIO(archivo.read(f"{raiz}/dossier.pdf")))
            texto_pdf = "\n".join(pagina.extract_text() or "" for pagina in pdf.pages)
        texto_pdf_plano = " ".join(texto_pdf.split())

        assert "# Reproducible dossier" in readme
        assert nombre in readme
        assert modelo["case"]["name"] == nombre
        assert modelo["glosario"]["NO_EVALUADO"] == "The control was not evaluated in this run."
        assert "It does not declare itself" in manifiesto["exclusiones"]["manifest.json"]
        assert "client (validated projection)" in next(
            entrada["fuente"] for entrada in manifiesto["files"]
            if entrada["path"] == "case/case_snapshot.json"
        )
        assert "COMPUTATIONAL EVIDENCE DOSSIER" in texto_pdf
        assert nombre in texto_pdf
        assert "The verifiable counterpart to `dossier.pdf`" in readme
        assert "How to reproduce this run" in receta
        assert "This document describes the evidence produced by a run" in texto_pdf_plano
        assert "Technical status, scientific disposition, and human review" in texto_pdf_plano
        assert "Este documento describe" not in texto_pdf_plano
        assert "El estado técnico" not in texto_pdf_plano

    def test_el_nombre_de_archivo_va_saneado(self, proyeccion):
        """
        Un nombre con comillas o saltos podría inyectar cabeceras.
        """
        proyeccion["name"] = 'Caso "raro"\r\ncon salto; y punto y coma'
        cliente = _app(molecula(), resultado_completo())
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion)

        disposicion = respuesta.headers["content-disposition"]
        assert "\r" not in disposicion and "\n" not in disposicion
        assert disposicion.count('"') == 2

    def test_no_se_filtran_rutas_internas_en_los_errores(self, proyeccion):
        cliente = _app(None, None)
        detalle = cliente.post(
            f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion
        ).json()["detail"]
        assert ":\\" not in detalle and "/home/" not in detalle


class TestValidacionDeEntrada:
    def test_una_proyeccion_con_ruta_local_se_rechaza(self, proyeccion):
        proyeccion["name"] = "D:\\casos\\secreto"
        cliente = _app(molecula(), resultado_completo())
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion)
        assert respuesta.status_code == 422

    def test_un_campo_desconocido_se_rechaza(self, proyeccion):
        proyeccion["storage"] = {"path": "D:\\casos\\x"}
        cliente = _app(molecula(), resultado_completo())
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/preview", json=proyeccion)
        assert respuesta.status_code == 422


class TestLegadoIntacto:
    def test_las_rutas_de_certificado_siguen_registradas(self):
        """La superficie nueva no retira la anterior en este sprint."""
        from api.routers.blockchain import router as blockchain_router

        # El router de blockchain lleva su propio prefijo.
        rutas = {r.path for r in blockchain_router.routes}
        assert "/blockchain/certificate/{molecule_id}" in rutas
        assert "/blockchain/certificate/{molecule_id}/preview" in rutas

    def test_el_generador_legado_sigue_existiendo(self):
        from services.blockchain import pdf_generator

        assert callable(pdf_generator.generate_certificate_pdf)

    def test_el_dossier_esta_bajo_evaluation(self):
        from api.routers.evaluation import router as evaluation_router

        rutas = {r.path for r in evaluation_router.routes}
        assert "/evaluation/dossier/{molecule_id}/preview" in rutas
        assert "/evaluation/dossier/{molecule_id}/package" in rutas


# ── P0-D: los artefactos estructurales llegan al ZIP ─────────────────


class TestArtefactosEstructuralesEnElZip:
    """
    El ZIP lleva la evidencia estructural EN CRUDO.

    El PDF es una lectura de estos archivos; incluirlos permite comprobar que el
    documento no añadió, quitó ni suavizó nada. Los ausentes se DECLARAN con su
    razón: el lector tiene que poder distinguir «no se generó» de «se me olvidó
    incluirlo».
    """

    def _zip(self, resultado, proyeccion):
        import io
        import zipfile

        cliente = _app(molecula(), resultado)
        respuesta = cliente.post(f"/evaluation/dossier/{MOLECULE_ID}/package", json=proyeccion)
        assert respuesta.status_code == 200, respuesta.text
        return zipfile.ZipFile(io.BytesIO(respuesta.content))

    def test_los_dos_contratos_viajan_en_crudo(self, proyeccion):
        import json

        with self._zip(resultado_completo(), proyeccion) as z:
            raiz = z.namelist()[0].split("/")[0]
            nombres = {n.split("/", 1)[1] for n in z.namelist()}
            fisica = json.loads(z.read(f"{raiz}/evidencia/structural_evidence.json"))
            seleccion = json.loads(z.read(f"{raiz}/evidencia/pose_selection.json"))
            modelo = json.loads(z.read(f"{raiz}/evidencia/pose_selector_model.json"))
            indice = json.loads(z.read(f"{raiz}/evidencia/pose_index.json"))
            protocolo = json.loads(z.read(f"{raiz}/run/protocol.json"))

        assert "evidencia/structural_evidence.json" in nombres
        # Tal y como los persistió el backend, sin reinterpretar.
        assert fisica["stage_status"] == "review"
        assert [p["rank"] for p in fisica["poses"]] == [1, 2, 3]
        assert seleccion["selected_pose_rank"] == 2
        assert seleccion["vina_top1_rank"] == 1
        # El modelo del selector, con su hash, sellado aparte.
        assert modelo["name"] == "pose_selector_v06"
        assert modelo["model_sha256"] == "b" * 64
        # La configuración NO se duplica: vive en `run/protocol.json`, y allí
        # cada parámetro lleva además su estado.
        assert protocolo["parametros"]["Semilla aleatoria"]["valor"] == "42"
        assert "config/run_config.json" not in nombres

        # El índice apunta a cada bloque exacto; el SDF sólo se anuncia cuando
        # está disponible y representa realmente la colección.
        assert indice["contrato"] == "pose_index/v2"
        assert indice["archivo_sdf_de_coleccion"] is None
        assert "outputs/pose_rank_001.pdbqt" in nombres
        assert indice["vina_top1_rank"] == 1
        assert indice["pose_sugerida_rank"] == 2
        assert indice["alternativas_fisicamente_validas"] == [1, 3]
        papeles = {p["rank"]: p for p in indice["poses"]}
        assert papeles[1]["archivo_pdbqt"] == "outputs/pose_rank_001.pdbqt"
        assert papeles[2]["es_sugerida"] is True
        assert papeles[2]["physical_status"] == "failed"
        assert papeles[1]["es_alternativa"] is True

    def test_una_corrida_antigua_declara_los_contratos_ausentes(self, proyeccion):
        import json

        from tests.fixtures_dossier import resultado_antiguo

        antiguo = resultado_antiguo()
        antiguo.task_id = proyeccion["run"]["task_id"] if proyeccion.get("run") else antiguo.task_id
        with self._zip(antiguo, proyeccion) as z:
            raiz = z.namelist()[0].split("/")[0]
            nombres = {n.split("/", 1)[1] for n in z.namelist()}
            manifiesto = json.loads(z.read(f"{raiz}/manifest.json"))

        # El archivo NO está…
        assert "evidencia/structural_evidence.json" not in nombres
        # …pero el manifiesto lo declara, con su razón.
        declarados = {f["path"]: f for f in manifiesto["files"]}
        entrada = declarados["evidencia/structural_evidence.json"]
        assert entrada["estado"] == "NO_EVALUADO"
        assert "anterior a la etapa" in entrada["razon"]
        seleccion = declarados["evidencia/pose_selection.json"]
        assert seleccion["estado"] == "NO_EVALUADO"
        assert "fallback" in seleccion["razon"].lower()

    def test_el_manifiesto_declara_rol_tamano_y_hash_de_cada_artefacto(self, proyeccion):
        import hashlib
        import json

        with self._zip(resultado_completo(), proyeccion) as z:
            raiz = z.namelist()[0].split("/")[0]
            manifiesto = json.loads(z.read(f"{raiz}/manifest.json"))
            for archivo in manifiesto["files"]:
                if archivo["estado"] != "REGISTRADO":
                    continue
                crudo = z.read(f"{raiz}/{archivo['path']}")
                assert hashlib.sha256(crudo).hexdigest() == archivo["sha256"], archivo["path"]
                assert archivo["tamano"] == len(crudo)
                assert archivo["rol"]


@pytest.mark.asyncio
async def test_ligandos_del_paquete_salen_del_snapshot_aunque_cambie_la_fila(monkeypatch):
    from utils import local_storage

    async def sin_archivo(_ruta):
        raise FileNotFoundError
    monkeypatch.setattr(local_storage, "read_text", sin_archivo)
    mol = molecula()
    mol.smiles = "CCO"
    resultado = resultado_completo()
    artefactos = await router_mod._artefactos(resultado, target_completo(), mol)
    por_nombre = {a.nombre: a for a in artefactos}
    assert por_nombre["ligand.smi"].contenido == b"CC(=O)Oc1ccccc1C(=O)O\n"
    assert por_nombre["ligand_docked.smi"].contenido == b"CC(=O)Oc1ccccc1C(=O)O\n"
    assert por_nombre["ligand.smi"].fuente == "eval_result.ligand_state.smiles_entrada"


@pytest.mark.asyncio
async def test_artefactos_ejecutados_exigen_hash_y_llevan_bytes_exactos(monkeypatch):
    """Un paquete transfiere los inputs reales; nunca sustituye un archivo mutado."""
    import hashlib
    from services.dossier.taxonomy import Estado
    from utils import local_storage

    raw = {
        "runs/docking/a/3F75/one/poses.sdf": b"poses\r\n",
        "runs/docking/a/3F75/one/vina.log": b"vina log\n",
        "runs/receptors/r.pdbqt": b"receptor\n",
        "ligands/a/conformer.sdf": b"conformer\n",
        "ligands/a/vina_input.pdbqt": b"ligand\n",
    }

    async def fake_read_bytes(path):
        return raw[path]

    monkeypatch.setattr(local_storage, "read_bytes", fake_read_bytes)
    digest = lambda path: hashlib.sha256(raw[path]).hexdigest()
    result = SimpleNamespace(
        poses_file_path="runs/docking/a/3F75/one/poses.sdf",
        receptor_path="runs/receptors/r.pdbqt",
        receptor_sha256=digest("runs/receptors/r.pdbqt"),
        docking_protocol={"execution_provenance": {
            "poses_sha256": digest("runs/docking/a/3F75/one/poses.sdf"),
            "ligand_input_path": "ligands/a/conformer.sdf",
            "ligand_input_sha256": digest("ligands/a/conformer.sdf"),
            "ligand_pdbqt_path": "ligands/a/vina_input.pdbqt",
            "ligand_pdbqt_sha256": digest("ligands/a/vina_input.pdbqt"),
            "log_path": "runs/docking/a/3F75/one/vina.log",
            "log_sha256": digest("runs/docking/a/3F75/one/vina.log"),
        }},
    )
    items = await router_mod._artefactos(result, SimpleNamespace(pdb_id="3F75"), None)
    by_name = {item.nombre: item for item in items}
    for name, path in (
        ("poses.sdf", "runs/docking/a/3F75/one/poses.sdf"),
        ("vina.log", "runs/docking/a/3F75/one/vina.log"),
        ("3F75_prepared.pdbqt", "runs/receptors/r.pdbqt"),
        ("ligand_input.sdf", "ligands/a/conformer.sdf"),
        ("ligand_input.pdbqt", "ligands/a/vina_input.pdbqt"),
    ):
        assert by_name[name].estado == Estado.REGISTRADO
        assert by_name[name].contenido == raw[path]

    raw["ligands/a/conformer.sdf"] = b"mutado\n"
    items = await router_mod._artefactos(result, SimpleNamespace(pdb_id="3F75"), None)
    by_name = {item.nombre: item for item in items}
    assert by_name["ligand_input.sdf"].estado == Estado.NO_DISPONIBLE
    assert by_name["ligand_input.sdf"].contenido is None
