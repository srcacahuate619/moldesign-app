"""
El Batch histórico sigue FUNCIONANDO, no sólo publicado.

# Por qué esta prueba existe

Sprint 5B añade `POST /evaluation/cohorts` al mismo router padre que
`/evaluation/batch`. La promesa del sprint es que el Batch no se toca, y
comprobar esa promesa listando rutas del OpenAPI es comprobar muy poco: una
ruta puede existir y devolver 500 en la primera línea.

Así que aquí se EJERCITA: se sube un archivo, se acepta el trabajo, se consulta
el estado y se exportan los resultados. El docking se sustituye —esta prueba no
es un banco de acoplamiento— pero todo lo demás es el código real.

# Lo que NO valida

Que el cribado sea científicamente útil. `total_score` sigue siendo el orden
principal del Batch y sigue siendo la razón por la que existe el trabajo de
cohortes. Comprobar que el legado funciona no es aprobarlo.
"""

from __future__ import annotations

import asyncio
import io
import uuid

import pytest
from fastapi.testclient import TestClient

from api.routers import batch as batch_mod
from core.database import get_db
from tests.conftest import rdkit_available

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
IBUPROFENO = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
PARACETAMOL = "CC(=O)Nc1ccc(O)cc1"


@pytest.fixture
def client(monkeypatch):
    """
    App real con la DB neutralizada y el docking sustituido.

    `get_db` se sobrescribe porque el modo de pruebas rechaza a propósito la
    base de escritorio persistente, y `_process_batch` se sustituye porque este
    archivo comprueba la SUPERFICIE del Batch, no el acoplamiento.
    """
    from api.main import app

    async def _sin_db():
        yield None

    app.dependency_overrides[get_db] = _sin_db

    lanzados: list[tuple] = []

    async def _falso_process_batch(batch_id, molecules, targets, num_workers, early_exit, has_labels):
        lanzados.append((batch_id, molecules, targets, num_workers, early_exit, has_labels))

    monkeypatch.setattr(batch_mod, "_process_batch", _falso_process_batch)

    # `TestClient(app)` SIN `with`: el gestor de contexto dispara el lifespan, y
    # el lifespan abre la base de escritorio, que el modo de pruebas rechaza a
    # propósito. Aquí se quiere el router real, no el arranque de la aplicación.
    cliente = TestClient(app)
    cliente.lanzados = lanzados  # type: ignore[attr-defined]
    try:
        yield cliente
    finally:
        app.dependency_overrides.pop(get_db, None)
        batch_mod._batches.clear()


def _subir(client: TestClient, contenido: bytes, nombre: str = "moleculas.csv", **params):
    return client.post(
        "/evaluation/batch",
        files={"file": (nombre, contenido, "text/csv")},
        params={"target_pdb_id": "7E2Y", "early_exit": "false", **params},
    )


# ── El camino real: subir → estado → exportar ────────────────────────


@rdkit_available
def test_subir_un_csv_acepta_el_trabajo_y_devuelve_un_batch_id(client):
    csv = "\n".join(
        ["smiles,name,active", f"{ASPIRINA},aspirina,1", f"{IBUPROFENO},ibuprofeno,0"]
    ).encode("utf-8")

    respuesta = _subir(client, csv)

    assert respuesta.status_code == 200, respuesta.text
    cuerpo = respuesta.json()
    assert uuid.UUID(cuerpo["batch_id"])
    assert cuerpo["total_molecules"] == 2
    assert cuerpo["targets"] == ["7E2Y"]
    assert cuerpo["status"] == "running"
    assert cuerpo["has_active_labels"] is True

    # El trabajo se encoló de verdad, con lo que se parseó.
    assert len(client.lanzados) == 1  # type: ignore[attr-defined]
    _, moleculas, targets, _, _, _ = client.lanzados[0]  # type: ignore[attr-defined]
    assert [m["name"] for m in moleculas] == ["aspirina", "ibuprofeno"]
    assert targets == ["7E2Y"]


@rdkit_available
def test_el_estado_del_batch_se_puede_consultar(client):
    csv = f"smiles,name\n{ASPIRINA},aspirina\n".encode("utf-8")
    batch_id = _subir(client, csv).json()["batch_id"]

    respuesta = client.get(f"/evaluation/batch/{batch_id}")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["batch_id"] == batch_id
    assert cuerpo["status"] == "running"
    assert cuerpo["total"] == 1
    assert cuerpo["targets"] == ["7E2Y"]


def test_un_batch_inexistente_es_404(client):
    assert client.get(f"/evaluation/batch/{uuid.uuid4()}").status_code == 404


@rdkit_available
def test_los_formatos_historicos_se_siguen_ingiriendo(client):
    smi = f"{ASPIRINA} aspirina\n{IBUPROFENO} ibuprofeno\n".encode("utf-8")

    respuesta = _subir(client, smi, "moleculas.smi")

    assert respuesta.status_code == 200
    assert respuesta.json()["total_molecules"] == 2


@rdkit_available
def test_un_formato_no_soportado_sigue_dando_400(client):
    assert _subir(client, b"cualquier cosa", "moleculas.docx").status_code == 400


@rdkit_available
def test_un_archivo_sin_smiles_validos_sigue_dando_400(client):
    assert _subir(client, b"smiles,name\n,\n").status_code == 400


@rdkit_available
def test_exportar_en_csv_produce_la_tabla_rankeada(client):
    """
    El export se ejercita sobre un batch COMPLETADO.

    Se inyecta el resultado en el estado en memoria en vez de esperar a un
    docking real: lo que esta prueba comprueba es que el exportador sigue
    produciendo su tabla, no que Vina funcione.
    """
    csv = f"smiles,name\n{ASPIRINA},aspirina\n".encode("utf-8")
    batch_id = _subir(client, csv).json()["batch_id"]

    batch_mod._batches[batch_id]["status"] = "completed"
    batch_mod._batches[batch_id]["results"] = [
        {"name": "peor", "smiles": IBUPROFENO, "total_score": 41.0, "affinity_kcal": -6.1},
        {"name": "mejor", "smiles": ASPIRINA, "total_score": 72.5, "affinity_kcal": -8.3},
    ]

    respuesta = client.get(f"/evaluation/batch/{batch_id}/csv")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    lineas = respuesta.text.strip().splitlines()
    assert lineas[0].startswith("Rank,Name,SMILES,TotalScore")
    # El orden del Batch histórico es `total_score` descendente. Sigue siéndolo:
    # esta prueba lo constata, no lo aprueba.
    assert '"mejor"' in lineas[1]
    assert '"peor"' in lineas[2]


def test_exportar_un_batch_en_curso_sigue_dando_400(client):
    batch_id = str(uuid.uuid4())
    batch_mod._batches[batch_id] = {
        "id": batch_id, "status": "running", "results": [], "total": 1,
        # BATCH-BE-002: el registro lleva dueño. El cliente de esta prueba no
        # tiene sesión, así que el cribado es del espacio anónimo.
        "completed": 0, "targets": ["7E2Y"], "owner_id": "demo",
    }

    assert client.get(f"/evaluation/batch/{batch_id}/csv").status_code == 400
    assert client.get(f"/evaluation/batch/{batch_id}/export").status_code == 400


@rdkit_available
def test_el_export_a_excel_funciona_o_lo_dice_con_claridad(client):
    """
    El export a Excel importa `openpyxl` DENTRO de la función.

    `openpyxl==3.1.5` está declarado en `backend/requirements.txt`, pero el
    intérprete embebido de este repositorio no lo trae. El Batch lo maneja bien:
    contesta 500 con una frase accionable en vez de reventar con un traceback.
    La prueba acepta las dos ramas porque las dos son comportamiento correcto —
    lo que no aceptaría es un fallo mudo.
    """
    csv = f"smiles,name\n{ASPIRINA},aspirina\n".encode("utf-8")
    batch_id = _subir(client, csv).json()["batch_id"]
    batch_mod._batches[batch_id]["status"] = "completed"
    batch_mod._batches[batch_id]["results"] = [
        {"name": "aspirina", "smiles": ASPIRINA, "total_score": 72.5, "affinity_kcal": -8.3}
    ]

    respuesta = client.get(f"/evaluation/batch/{batch_id}/export")

    try:
        import openpyxl  # noqa: F401

        disponible = True
    except ImportError:
        disponible = False

    if disponible:
        assert respuesta.status_code == 200
        assert respuesta.content[:2] == b"PK"  # un .xlsx es un ZIP
    else:
        assert respuesta.status_code == 500
        assert "openpyxl" in respuesta.json()["detail"]


# ── El motor de fondo, con el docking sustituido ─────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_el_procesado_de_fondo_recorre_las_moleculas_y_acumula_resultados(monkeypatch):
    """
    `_process_batch` con `_run_full_evaluation_async` sustituido.

    Es la única parte del Batch que no se puede ejercitar de verdad sin correr
    Vina. Se comprueba que el bucle sigue recorriendo, contando y acumulando.
    """
    batch_id = str(uuid.uuid4())
    batch_mod._batches[batch_id] = {
        "id": batch_id, "targets": ["7E2Y"], "total": 2, "total_molecules": 2,
        "completed": 0, "failed": 0, "skipped_early_exit": 0, "invalid_input": 0,
        "status": "running", "results": [], "num_workers": 1, "early_exit": False,
        "has_labels": False, "ef_metrics": None,
    }

    async def _falsa_evaluacion(*args, **kwargs):
        return {"molecule_id": str(uuid.uuid4()), "total_score": 60.0, "affinity_kcal": -7.5}

    import services.docking.queue_handler as qh

    monkeypatch.setattr(qh, "_run_full_evaluation_async", _falsa_evaluacion, raising=False)

    try:
        await batch_mod._process_batch(
            batch_id,
            [
                {"smiles": ASPIRINA, "name": "aspirina", "original": ASPIRINA, "is_active": None},
                {"smiles": PARACETAMOL, "name": "paracetamol", "original": PARACETAMOL, "is_active": None},
            ],
            ["7E2Y"],
            num_workers=1,
            early_exit=False,
            has_labels=False,
        )
    finally:
        estado = batch_mod._batches.pop(batch_id)

    # Terminó y contabilizó las dos moléculas, con éxito o con fallo declarado.
    assert estado["status"] == "completed"
    assert estado["completed"] == 2
    assert len(estado["results"]) == 2


# ── Convivencia con la superficie nueva ──────────────────────────────


def test_batch_y_cohortes_conviven_sin_pisarse():
    from fastapi.routing import APIRoute

    from api.main import app

    rutas = {
        (metodo, ruta.path)
        for ruta in app.routes
        if isinstance(ruta, APIRoute)
        for metodo in ruta.methods
        if metodo not in {"HEAD", "OPTIONS"}
    }

    for esperada in [
        ("POST", "/evaluation/batch"),
        ("GET", "/evaluation/batch/{batch_id}"),
        ("GET", "/evaluation/batch/{batch_id}/export"),
        ("GET", "/evaluation/batch/{batch_id}/csv"),
        ("POST", "/evaluation/cohorts"),
        ("GET", "/evaluation/cohorts"),
        ("GET", "/evaluation/cohorts/{cohort_id}"),
        ("POST", "/evaluation/cohorts/preflight"),
    ]:
        assert esperada in rutas, esperada


def test_el_estado_del_batch_sigue_siendo_en_memoria():
    """
    Se constata la limitación, no se arregla.

    El Batch histórico guarda sus cribados en un `dict` de módulo y los pierde
    al reiniciar. Es una de las razones por las que existen las cohortes; este
    sprint le da durabilidad a la superficie NUEVA y deja la vieja como está.
    """
    assert isinstance(batch_mod._batches, dict)
    assert isinstance(batch_mod._batch_lock, asyncio.Lock)
