"""LUNA-04 — un campo que el contrato no conoce no se acepta y se ignora.

# El fallo

`POST /evaluation/submit` con `docking_engine: "diffdock"` en la RAÍZ del cuerpo
devolvía **202**. El modelo no declara ese campo (el motor vive dentro de
`pipeline_config`) y Pydantic descarta por defecto lo que no conoce, así que la
petición se aceptaba y la corrida salía con Vina. La versión anidada sí daba 422.
La corrida no se etiquetó como DiffDock —el sello usa el motor efectivo—, pero el
cliente creyó haber pedido un motor que no se ejecutó: aceptar en silencio lo que
se va a ignorar es una mentira de procedencia por omisión.

No era sólo el motor. Cualquier campo con el nombre equivocado se descartaba igual:
`exhaustiveness` en la raíz (que cambia el protocolo), o un `target_id` donde el
campo es `target_pdb_id`. De hecho una prueba existente
(`test_api_phase5_security.py`) pasaba `target_id=` creyendo ejercitar el receptor,
y nunca lo ejercitó: el modelo lo ignoraba, y la prueba seguía verde.

# La regla

Los modelos de petición de la ruta de evaluación son **cerrados**
(`extra="forbid"`): un campo desconocido es un 422 que lo nombra. Eso cubre
`EvaluationSubmitRequest` (también `/evaluation/evaluate`, que lo comparte),
`PreflightRequest` y `PipelineConfigRequest`.

Lo que NO cambia: el preflight sigue aceptando `docking_engine` en la raíz —es parte
de su contrato— y un motor no ejecutable ahí sale como bloqueante dentro del
informe, no como 422 (un informe que explica por qué no se puede es más útil que un
rechazo sin informe).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from api.routers.evaluation import (
    EvaluationSubmitRequest,
    PipelineConfigRequest,
    PreflightRequest,
)

#: Campos que no pertenecen a la raíz de /submit. Todos se descartaban en silencio.
RAIZ_DESCONOCIDA = [
    {"docking_engine": "diffdock"},   # el caso de la auditoría
    {"docking_engine": "vina"},       # el motor se declara en pipeline_config
    {"exhaustiveness": 64},           # cambiaría el protocolo… si se leyera
    {"num_poses": 3},
    {"target_id": "7E2Y"},            # el nombre equivocado que ya pasó
]

#: Exactamente lo que el cliente de escritorio envía a /submit (`lib/api.ts`) y el
#: `pipeline_config` que construye `ProEvaluation.tsx`: el control positivo.
CUERPO_REAL_DEL_CLIENTE = {
    "smiles": "CC(=O)Oc1ccccc1C(=O)O",
    "target_pdb_id": "7E2Y",
    "chain": "A",
    "is_control": False,
    "grid_center": [1.0, 2.0, 3.0],
    "grid_size": [20.0, 20.0, 20.0],
    "custom_hotspots": ["ARG-1"],
    "pipeline_config": {
        "enabled_stages": ["validation", "properties", "sa_filter", "conformer", "docking", "xgb", "clgnn"],
        "stage_params": {
            "docking": {"exhaustiveness": 8, "num_poses": 5},
            "properties": {"run_admet_ai": False},
        },
        "docking_engine": "vina",
        "pro_workers": 2,
        "pro_parallel_docks": 1,
        "pro_selectivity": False,
        "pro_anti_targets": [],
        "pro_mmgbsa": False,
        "pro_mmgbsa_steps": 1000,
        "gnn_precision": "fp32",
    },
    "preflight_fingerprint": "sha256:" + "a" * 64,
}


def _tipos(excepcion: ValidationError) -> set[str]:
    return {e["type"] for e in excepcion.errors()}


# ── el modelo ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("extra", RAIZ_DESCONOCIDA)
def test_submit_rechaza_un_campo_desconocido_en_la_raiz(extra):
    with pytest.raises(ValidationError) as salida:
        EvaluationSubmitRequest.model_validate({"smiles": "CCO", **extra})
    assert "extra_forbidden" in _tipos(salida.value)
    assert {e["loc"][-1] for e in salida.value.errors()} >= set(extra), (
        "el error tiene que NOMBRAR el campo, no sólo rechazar"
    )


def test_submit_rechaza_un_campo_desconocido_dentro_de_pipeline_config():
    with pytest.raises(ValidationError) as salida:
        EvaluationSubmitRequest.model_validate(
            {"smiles": "CCO", "pipeline_config": {"exhaustiveness": 64}}
        )
    assert "extra_forbidden" in _tipos(salida.value)
    with pytest.raises(ValidationError):
        PipelineConfigRequest.model_validate({"docking_engin": "vina"})  # errata


def test_el_cuerpo_real_del_cliente_sigue_siendo_valido():
    """Control positivo: cerrar el modelo no puede romper al cliente que existe."""
    peticion = EvaluationSubmitRequest.model_validate(CUERPO_REAL_DEL_CLIENTE)
    assert peticion.pipeline_config is not None
    assert peticion.pipeline_config.docking_engine == "vina"


def test_el_motor_nuevo_sigue_rechazandose_dentro_de_pipeline_config():
    """No se perdió la validación que ya existía al añadir la nueva."""
    with pytest.raises(ValidationError):
        EvaluationSubmitRequest.model_validate(
            {"smiles": "CCO", "pipeline_config": {"docking_engine": "diffdock"}}
        )


# ── el preflight ─────────────────────────────────────────────────────────


def test_el_preflight_sigue_aceptando_docking_engine_en_la_raiz():
    """Es parte de su contrato (`lib/preflight.ts` lo envía siempre)."""
    peticion = PreflightRequest.model_validate({
        "smiles": "CCO", "target_pdb_id": "7E2Y", "docking_engine": "vina",
        "exhaustiveness": 8, "num_poses": 5, "conformers": 1,
    })
    assert peticion.docking_engine == "vina"
    # Un motor no ejecutable en la raíz NO es un 422: sale como bloqueante dentro del
    # informe (test_evaluation_preflight.py); aquí sólo se comprueba que el modelo lo deja pasar.
    assert PreflightRequest.model_validate(
        {"smiles": "CCO", "target_pdb_id": "7E2Y", "docking_engine": "diffdock"}
    ).docking_engine == "diffdock"


@pytest.mark.parametrize(
    "extra",
    [{"peptide_docking_engine": "diffpepdock"}, {"seed": 7}, {"target_id": "7E2Y"}],
)
def test_el_preflight_rechaza_un_campo_que_no_tiene(extra):
    """`peptide_docking_engine` en la raíz del preflight se ignoraba y el informe
    mostraba Vina sin bloqueantes: el cliente creía haber comprobado otra cosa."""
    with pytest.raises(ValidationError) as salida:
        PreflightRequest.model_validate(
            {"smiles": "CCO", "target_pdb_id": "7E2Y", **extra}
        )
    assert "extra_forbidden" in _tipos(salida.value)


# ── el HTTP: 422 antes de abrir la base y antes de registrar nada ────────


@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient

    from api.dependencies import get_current_user_optional
    from api.main import app
    from core.database import get_db
    from services import evaluation_submission

    registradas: list = []

    async def espia(**kwargs):  # si llega aquí, la petición se aceptó
        registradas.append(kwargs)
        raise AssertionError("una petición con campos desconocidos llegó a registrar_corrida")

    monkeypatch.setattr(evaluation_submission, "registrar_corrida", espia)
    # Una petición inválida no debe abrir la base de datos real del usuario.
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_current_user_optional] = lambda: None
    try:
        yield TestClient(app, raise_server_exceptions=False), registradas
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.mark.parametrize("ruta", ["/evaluation/submit", "/evaluation/evaluate"])
@pytest.mark.parametrize("extra", RAIZ_DESCONOCIDA)
def test_http_rechaza_con_422_y_nombra_el_campo(cliente, ruta, extra):
    http, registradas = cliente
    respuesta = http.post(ruta, json={"smiles": "CCO", **extra})
    assert respuesta.status_code == 422, respuesta.text
    campos = {d["loc"][-1] for d in respuesta.json()["detail"]}
    assert campos >= set(extra)
    assert registradas == []


def test_http_preflight_rechaza_un_campo_desconocido(cliente):
    http, _ = cliente
    respuesta = http.post(
        "/evaluation/preflight",
        json={"smiles": "CCO", "target_pdb_id": "7E2Y", "peptide_docking_engine": "diffpepdock"},
    )
    assert respuesta.status_code == 422, respuesta.text
    assert "peptide_docking_engine" in {d["loc"][-1] for d in respuesta.json()["detail"]}
