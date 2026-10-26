"""
El tautómero que acopla una cohorte se declara, viaja a cada fila y entra en la huella.

El 2026-10-10 el defecto del producto pasó de «canonico» a «entrada» (decisión
del propietario). Las cohortes no declaraban el modo, así que una cohorte
congelada antes habría acoplado otra especie con la misma huella: justo lo que
`services/cohort/schemas.py` dice que no puede pasar. Estas pruebas fijan:

1. Sin declarar vale «canonico», lo que acoplaban esas cohortes, y su huella no
   cambia.
2. «entrada» cambia la huella; «canonico» declarado no.
3. El modo llega explícito al pipeline de cada fila, también al reanudar.
"""

from __future__ import annotations

import json
import uuid

import pytest
from pydantic import ValidationError

from services.cohort import execution as ex
from services.cohort import runs as run_repo
from services.cohort.fingerprint import FingerprintRow, canonical_cohort_document, cohort_fingerprint
from services.cohort.schemas import TAUTOMERO_SIN_DECLARAR, CohortStudy, modo_tautomero_de
from services.docking.protocolo import resolver_modo_tautomero
from tests.conftest import rdkit_available
from tests.test_cohort_execution import CSV, STUDY, _congelar, entorno  # noqa: F401

VORINOSTAT = "O=C(CCCCCCC(=O)Nc1ccccc1)NO"
FILAS = [FingerprintRow(molecule=VORINOSTAT, active_label=None, control_role="none")]


def _estudio(**config) -> CohortStudy:
    return CohortStudy.model_validate({**STUDY, "config": {**STUDY["config"], **config}})


# ── 1-2. Huella ──────────────────────────────────────────────────────


def test_sin_declarar_vale_el_canonico_de_antes():
    assert TAUTOMERO_SIN_DECLARAR == "canonico"
    assert _estudio().config.tautomero is None
    assert modo_tautomero_de(_estudio().config.model_dump()) == "canonico"
    assert modo_tautomero_de({}) == "canonico"
    assert modo_tautomero_de(None) == "canonico"


def test_la_huella_de_una_cohorte_sin_el_campo_no_cambia():
    """El documento es byte a byte el de antes del campo: no aparece la clave."""
    documento = canonical_cohort_document(_estudio(), FILAS)

    assert "tautomero" not in documento
    assert json.loads(documento)["config"] == {
        "docking_engine": "vina",
        "exhaustiveness": 8,
        "grid_center": [10.0, 11.0, 12.0],
        "grid_size": [22.0, 22.0, 22.0],
        "num_poses": 5,
        "seed": 42,
    }


def test_el_canonico_declarado_es_la_misma_cohorte_que_sin_declarar():
    assert cohort_fingerprint(_estudio(tautomero="canonico"), FILAS) == cohort_fingerprint(
        _estudio(), FILAS
    )


def test_acoplar_el_escrito_es_otra_cohorte():
    entrada = _estudio(tautomero="entrada")

    assert cohort_fingerprint(entrada, FILAS) != cohort_fingerprint(_estudio(), FILAS)
    assert json.loads(canonical_cohort_document(entrada, FILAS))["config"]["tautomero"] == "entrada"


def test_un_modo_desconocido_se_rechaza():
    with pytest.raises(ValidationError):
        _estudio(tautomero="dominante")


# ── 3. Ejecución ─────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("declarado", "efectivo"),
    [(None, "canonico"), ("canonico", "canonico"), ("entrada", "entrada")],
)
def test_la_configuracion_efectiva_congela_el_modo(declarado, efectivo):
    config = dict(STUDY["config"])
    if declarado is not None:
        config["tautomero"] = declarado

    efectiva = ex.resolve_effective_config({**STUDY, "config": config}, None)

    assert efectiva.tautomero == efectivo
    assert efectiva.as_dict()["tautomero"] == efectivo


@pytest.mark.asyncio
@pytest.mark.parametrize("modo", ["canonico", "entrada"])
async def test_cada_fila_pide_el_modo_de_la_cohorte_explicito(monkeypatch, modo):
    """Omitido, el conformador usaría el defecto del producto («entrada»)."""
    recibido = {}

    async def _pipeline(**kwargs):
        recibido.update(kwargs)
        return {"molecule_id": str(uuid.uuid4()), "task_id": str(uuid.uuid4())}

    monkeypatch.setattr("services.pipeline.runner.run_pipeline", _pipeline)
    config = ex.resolve_effective_config(
        {**STUDY, "config": {**STUDY["config"], "tautomero": modo}}, None
    )

    await ex._evaluate_one(
        canonical_smiles=VORINOSTAT,
        molecule_name="vorinostat",
        receptor=ex.ReceptorProvenance(
            pdb_id="7E2Y",
            chain="A",
            prepared_sha256="sha256:" + "a" * 64,
            prepared_size_bytes=10,
            prepared_object="targets/7E2Y/prepared.pdbqt",
            source_sha256=None,
            catalog_target_id=None,
            prepared_bytes=b"RECEPTOR\n",
        ),
        config=config,
        user_id=None,
    )

    conformador = recibido["stage_params"]["conformer"]
    assert conformador["tautomero"] == modo
    assert resolver_modo_tautomero(conformador) == modo
    assert recibido["pipeline_config"]["stage_params"]["conformer"]["tautomero"] == modo


@rdkit_available
@pytest.mark.asyncio
async def test_la_corrida_congela_el_modo_declarado(entorno, monkeypatch):  # noqa: F811
    configs = []

    async def _no_encolar(run_id, *, workers):
        return None

    async def _falso(*, canonical_smiles, molecule_name, receptor, config, user_id):
        configs.append(config)
        return {"molecule_id": str(uuid.uuid4()), "task_id": str(uuid.uuid4())}

    monkeypatch.setattr(run_repo, "schedule", _no_encolar)
    monkeypatch.setattr(ex, "_evaluate_one", _falso)
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(
        client, study={**STUDY, "config": {**STUDY["config"], "tautomero": "entrada"}}
    )

    respuesta = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")
    assert respuesta.status_code == 202, respuesta.text
    run_id = respuesta.json()["run_id"]
    await run_repo.execute_run(uuid.UUID(run_id), workers=1)

    assert cohorte["preflight"]["normalized_study"]["config"]["tautomero"] == "entrada"
    assert (await entorno.corrida(run_id)).effective_config_json["tautomero"] == "entrada"
    assert configs and {c.tautomero for c in configs} == {"entrada"}


@rdkit_available
@pytest.mark.asyncio
async def test_reanudar_una_corrida_sin_el_campo_acopla_el_canonico(entorno, monkeypatch):  # noqa: F811
    """Una corrida congelada antes del campo no cambia de química al reanudarse."""
    configs = []

    async def _no_encolar(run_id, *, workers):
        return None

    async def _falso(*, canonical_smiles, molecule_name, receptor, config, user_id):
        configs.append(config)
        return {"molecule_id": str(uuid.uuid4()), "task_id": str(uuid.uuid4())}

    monkeypatch.setattr(run_repo, "schedule", _no_encolar)
    monkeypatch.setattr(ex, "_evaluate_one", _falso)
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    respuesta = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")
    assert respuesta.status_code == 202, respuesta.text
    run_id = respuesta.json()["run_id"]

    from core.models import CohortRunORM

    async with entorno.factory() as session:
        corrida = await session.get(CohortRunORM, uuid.UUID(run_id))
        antigua = dict(corrida.effective_config_json)
        antigua.pop("tautomero")
        corrida.effective_config_json = antigua
        await session.commit()

    await run_repo.execute_run(uuid.UUID(run_id), workers=1)

    assert configs and {c.tautomero for c in configs} == {"canonico"}
