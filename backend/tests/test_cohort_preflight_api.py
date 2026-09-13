"""
Contrato HTTP de `POST /evaluation/cohorts/preflight`.

Lo que fijan estas pruebas:

1. **Lo que no es una cohorte se rechaza en la puerta.** `ALL`, un campo
   desconocido, un flotante no finito: 422 y ningún resultado parcial. Un
   resultado parcial de algo que no es una cohorte parecería una cohorte.

2. **Lo que sí es una cohorte pero no se puede ejecutar se DECLARA.** 200 con
   `decision: blocked`, sus bloqueantes y sus filas: el cliente necesita verla
   para poder arreglarla.

3. **La ruta no ejecuta nada.** Sin docking, sin tareas de fondo, sin score.

4. **El Batch histórico sigue publicado.** Esta superficie no lo sustituye en
   este sprint.
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from api.main import app
from core.database import get_db
from services.cohort import taxonomy as tx
from tests.conftest import rdkit_available

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
IBUPROFENO = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
PARACETAMOL = "CC(=O)Nc1ccc(O)cc1"

STUDY = {
    "schema_version": 1,
    "name": "Serie de anilinas · lote 3",
    "receptor": {"pdb_id": "7e2y", "chain": "a"},
    "config": {
        "docking_engine": "vina",
        "exhaustiveness": 8,
        "num_poses": 5,
        "grid_center": [10.0, 11.0, 12.0],
        "grid_size": [22.0, 22.0, 22.0],
        "seed": 42,
    },
}

CSV = "\n".join(
    [
        "name,smiles,active,control_role",
        f"aspirina,{ASPIRINA},1,reference",
        f"ibuprofeno,{IBUPROFENO},0,none",
        f"paracetamol,{PARACETAMOL},,none",
    ]
).encode("utf-8")


@pytest.fixture(scope="module")
def client() -> TestClient:
    async def _sin_db():
        # Este contrato ejercita el preflight puro con un receptor PDB público.
        # La autorización DB sólo se usa para identificadores privados USR_*.
        yield None

    app.dependency_overrides[get_db] = _sin_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


def _post(client: TestClient, *, study=None, contenido: bytes = CSV, nombre="cohorte.csv"):
    return client.post(
        "/evaluation/cohorts/preflight",
        files={"file": (nombre, contenido, "text/csv")},
        data={"study": json.dumps(study if study is not None else STUDY)},
    )


def _con(config=None, receptor=None, **overrides) -> dict:
    estudio = {**STUDY, **overrides}
    if config:
        estudio["config"] = {**STUDY["config"], **config}
    if receptor:
        estudio["receptor"] = {**STUDY["receptor"], **receptor}
    return estudio


# ── 1. Camino feliz ──────────────────────────────────────────────────


@rdkit_available
def test_csv_valido_devuelve_una_cohorte_lista_y_normalizada(client):
    respuesta = _post(client)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()

    assert cuerpo["schema_version"] == 1
    assert cuerpo["decision"] == "ready"
    assert cuerpo["blockers"] == []
    assert cuerpo["cohort_fingerprint"].startswith("sha256:")

    # El estudio vuelve NORMALIZADO: lo que se firmó, no lo que se escribió.
    assert cuerpo["normalized_study"]["receptor"] == {"pdb_id": "7E2Y", "chain": "A"}

    resumen = cuerpo["summary"]
    assert resumen["total_rows"] == 3
    assert resumen["eligible_rows"] == 3
    assert resumen["input_coverage"] == 1.0
    assert resumen["input_coverage_denominator"] == 3
    assert resumen["explicit_reference_controls"] == 1

    assert [fila["row_index"] for fila in cuerpo["rows"]] == [0, 1, 2]
    assert cuerpo["rows"][0]["active_label"] is True
    assert cuerpo["rows"][2]["active_label"] is None


@rdkit_available
def test_una_cohorte_bloqueada_se_devuelve_entera_con_su_diagnostico(client):
    contenido = "\n".join(["name,smiles", "rota,CCX", "vacia,"]).encode("utf-8")

    respuesta = _post(client, contenido=contenido)

    # 200, no 4xx: esto SÍ es una cohorte. Una que no se puede ejecutar.
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["decision"] == "blocked"
    assert tx.SIN_MOLECULAS_ELEGIBLES in cuerpo["blockers"]
    assert cuerpo["summary"]["total_rows"] == 2
    assert cuerpo["summary"]["input_coverage"] == 0.0
    assert len(cuerpo["rows"]) == 2


# ── 9, 10 y 11. Lo que no llega a ser una cohorte ────────────────────


@pytest.mark.parametrize("valor", ["ALL", "all", " All "])
def test_receptor_all_se_rechaza(client, valor):
    respuesta = _post(client, study=_con(receptor={"pdb_id": valor}))

    assert respuesta.status_code == 422
    assert "ALL" in json.dumps(respuesta.json(), ensure_ascii=False)


def test_una_lista_de_receptores_no_define_una_cohorte(client):
    respuesta = _post(client, study=_con(receptor={"pdb_id": "7E2Y,3PP0"}))

    assert respuesta.status_code == 422


def test_campo_desconocido_en_el_estudio_se_rechaza(client):
    respuesta = _post(client, study=_con(num_workers=6))

    assert respuesta.status_code == 422
    detalle = json.dumps(respuesta.json(), ensure_ascii=False)
    # Workers es operacional: cambia cuánto tarda, no qué se calcula.
    assert "num_workers" in detalle


def test_campo_desconocido_en_la_configuracion_se_rechaza(client):
    respuesta = _post(client, study=_con(config={"early_exit": True}))

    assert respuesta.status_code == 422
    assert "early_exit" in json.dumps(respuesta.json(), ensure_ascii=False)


@pytest.mark.parametrize(
    "literal",
    [
        '{"schema_version":1,"name":"c","receptor":{"pdb_id":"7E2Y"},'
        '"config":{"docking_engine":"vina","exhaustiveness":8,"num_poses":5,'
        '"grid_size":[NaN,22,22]}}',
        '{"schema_version":1,"name":"c","receptor":{"pdb_id":"7E2Y"},'
        '"config":{"docking_engine":"vina","exhaustiveness":8,"num_poses":5,'
        '"grid_center":[Infinity,0,0]}}',
        # Sin literal `Infinity`: `1e400` se desborda a inf al parsear, así que
        # el rechazo tiene que estar también en el tipo, no sólo en el parser.
        '{"schema_version":1,"name":"c","receptor":{"pdb_id":"7E2Y"},'
        '"config":{"docking_engine":"vina","exhaustiveness":8,"num_poses":5,'
        '"grid_center":[1e400,0,0]}}',
    ],
    ids=["nan", "infinity", "desbordamiento"],
)
def test_valores_no_finitos_se_rechazan(client, literal):
    respuesta = client.post(
        "/evaluation/cohorts/preflight",
        files={"file": ("cohorte.csv", CSV, "text/csv")},
        data={"study": literal},
    )

    assert respuesta.status_code == 422


def test_caja_con_lado_cero_se_rechaza_en_vez_de_pasar_por_centinela(client):
    respuesta = _post(client, study=_con(config={"grid_size": [0.0, 0.0, 0.0]}))

    assert respuesta.status_code == 422
    assert "grid_size" in json.dumps(respuesta.json(), ensure_ascii=False)


@pytest.mark.parametrize(
    "config",
    [
        {"exhaustiveness": 0},
        {"exhaustiveness": 999},
        {"num_poses": 0},
        {"num_poses": 50},
        {"docking_engine": "autodock-gpu"},
    ],
)
def test_parametros_fuera_de_los_limites_del_producto_se_rechazan(client, config):
    assert _post(client, study=_con(config=config)).status_code == 422


def test_la_configuracion_hay_que_declararla_entera(client):
    # Sin `exhaustiveness`. No hay valor por defecto a propósito: una cohorte
    # identificada por un ajuste que nadie declaró cambiaría de identidad el día
    # que cambie ese ajuste.
    estudio = {**STUDY, "config": {"docking_engine": "vina", "num_poses": 5}}

    assert _post(client, study=estudio).status_code == 422


def test_un_study_que_no_es_json_se_rechaza(client):
    respuesta = client.post(
        "/evaluation/cohorts/preflight",
        files={"file": ("cohorte.csv", CSV, "text/csv")},
        data={"study": "no soy json"},
    )

    assert respuesta.status_code == 422


def test_un_archivo_con_mas_filas_que_el_limite_se_rechaza(client):
    from services.cohort.schemas import MAX_COHORT_ROWS

    filas = ["name,smiles"] + [f"m{i},{ASPIRINA}" for i in range(MAX_COHORT_ROWS + 1)]
    respuesta = _post(client, contenido="\n".join(filas).encode("utf-8"))

    assert respuesta.status_code == 422
    # No se recorta en silencio: se dice cuántas trae y cuál es el límite.
    assert str(MAX_COHORT_ROWS) in json.dumps(respuesta.json(), ensure_ascii=False)


# ── 13. Determinismo a través de HTTP ────────────────────────────────


@rdkit_available
def test_dos_llamadas_iguales_devuelven_el_mismo_fingerprint(client):
    primera = _post(client).json()
    segunda = _post(client).json()

    assert primera["cohort_fingerprint"] == segunda["cohort_fingerprint"]
    # `generated_at` es lo ÚNICO que puede diferir.
    primera.pop("generated_at")
    segunda.pop("generated_at")
    assert primera == segunda


# ── 17. La ruta no ejecuta nada ──────────────────────────────────────


@rdkit_available
def test_la_ruta_no_lanza_docking_ni_tareas_de_fondo(client, monkeypatch):
    import asyncio

    import services.docking.vina_service as vina

    def _prohibido(*args, **kwargs):
        raise AssertionError("La comprobación previa NO ejecuta ni encola nada.")

    monkeypatch.setattr(vina, "run_vina_docking", _prohibido)
    monkeypatch.setattr(asyncio, "create_task", _prohibido)

    respuesta = _post(client)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    # Ni un identificador de tarea, ni un score, ni una métrica de cribado.
    for prohibido in ("task_id", "batch_id", "total_score", "score", "ef_metrics", "affinity"):
        assert prohibido not in json.dumps(cuerpo).lower()


# ── 18. El Batch histórico sigue en pie ──────────────────────────────


def test_los_endpoints_batch_historicos_siguen_publicados():
    esquema = app.openapi()

    assert "post" in esquema["paths"]["/evaluation/batch"]
    assert "get" in esquema["paths"]["/evaluation/batch/{batch_id}"]
    assert "get" in esquema["paths"]["/evaluation/batch/{batch_id}/export"]
    # Y la superficie nueva convive con ella, no la reemplaza todavía.
    assert "post" in esquema["paths"]["/evaluation/cohorts/preflight"]


def test_la_ruta_de_cohortes_no_pisa_ninguna_ruta_de_batch():
    from fastapi.routing import APIRoute

    rutas = {
        (metodo, ruta.path)
        for ruta in app.routes
        if isinstance(ruta, APIRoute)
        for metodo in ruta.methods
        if metodo not in {"HEAD", "OPTIONS"}
    }

    assert ("POST", "/evaluation/cohorts/preflight") in rutas
    assert ("POST", "/evaluation/batch") in rutas
    assert ("GET", "/evaluation/batch/{batch_id}") in rutas


def test_los_extractores_del_batch_historico_siguen_intactos():
    # 5B migrará la interfaz; hasta entonces el Batch conserva su propia ingesta
    # con pérdida. Fundirla con la de cohortes habría cambiado uno de los dos
    # contratos, y este sprint no puede tocar el histórico.
    from api.routers import batch

    for nombre in ("_extract_from_csv", "_extract_from_excel", "_extract_smiles_from_sdf"):
        assert callable(getattr(batch, nombre))

    moleculas, etiquetas = batch._extract_from_csv(
        f"smiles,name,active\n{ASPIRINA},aspirina,1\n"
    )
    assert moleculas == [{"smiles": ASPIRINA, "name": "aspirina"}]
    assert etiquetas == {"aspirina": True}
