"""QA-S04: semilla fija, elegible y exportada; no repara resultados históricos."""
import csv
import io
import json
import uuid
from types import SimpleNamespace

import pytest
import base64
import re
import zlib

from core.models import CohortRunORM
from services.cohort import execution as ex
from services.cohort.fingerprint import FingerprintRow, cohort_fingerprint
from tests.test_cohort_preflight import estudio, preflight, csv_bytes, ASPIRINA
from tests.test_cohort_execution import entorno, evaluador, _congelar, _abrir_y_esperar, STUDY
from tests.test_cohort_dossier_api import _abrir_zip

def _pdf_text(data):
    """Inspecciona los streams ASCII85/Flate de estos PDF de ReportLab."""
    streams=[]
    for raw in re.findall(rb"stream\r?\n(.*?)endstream", data, re.S):
        try:
            decoded=zlib.decompress(base64.a85decode(raw.strip(), adobe=True))
        except (ValueError, zlib.error):
            continue
        streams.append(decoded.decode("latin-1"))
    assert streams, "PDF sin streams legibles del productor ReportLab"
    return "\n".join(streams)


@pytest.mark.parametrize("requested, effective, origin", [(0,42,"default"), (None,42,"default"), (73,73,"explicit")])
def test_preflight_congela_semilla_antes_de_firmar(requested, effective, origin):
    result = preflight(csv_bytes("smiles", ASPIRINA), study=estudio(config={"seed":requested}))
    assert result.normalized_study.config.seed == effective
    assert result.seed_resolution == {"requested":requested, "effective":effective, "origin":origin}
    rows = [FingerprintRow(r.canonical_smiles or r.input_smiles, r.active_label, r.control_role) for r in result.rows]
    assert cohort_fingerprint(result.normalized_study, rows) == result.cohort_fingerprint
    repeat = preflight(csv_bytes("smiles", ASPIRINA), study=estudio(config={"seed":requested}))
    assert repeat.cohort_fingerprint == result.cohort_fingerprint


def test_cero_y_predeterminada_identifican_la_misma_ciencia():
    content = csv_bytes("smiles", ASPIRINA)
    assert preflight(content, study=estudio(config={"seed":0})).cohort_fingerprint == preflight(content).cohort_fingerprint


def test_no_se_inicia_cohorte_historica_con_cero():
    with pytest.raises(ex.ExecutionBlocked):
        ex.resolve_effective_config({**STUDY, "config":{**STUDY["config"], "seed":0}}, None)


@pytest.mark.asyncio
async def test_cero_se_persiste_por_fila_antes_de_ejecutar(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client=entorno.app()
    cohort=_congelar(client, study={**STUDY, "config":{**STUDY["config"], "seed":0}})
    queued=client.post(f"/evaluation/cohorts/{cohort['id']}/runs")
    assert queued.status_code == 202, queued.text
    run=await entorno.corrida(queued.json()["run_id"])
    rows=await entorno.filas(queued.json()["run_id"])
    assert run.effective_config_json["seed"] == 42
    assert run.effective_config_json["seed_origin"] == "default"
    assert run.effective_config_json["row_seeds"] == {str(r.source_row_index):42 for r in rows}


@pytest.mark.asyncio
@pytest.mark.parametrize("lang, expected", [("es","predeterminada"),("en","default")])
async def test_paquete_semilla_por_fila_en_csv_pdf_readme(entorno, evaluador, lang, expected):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client=entorno.app(localization_middleware=True)
    cohort=_congelar(client, study={**STUDY, "config":{**STUDY["config"], "seed":0}})
    _,run_id=await _abrir_y_esperar(entorno,client,cohort["id"])
    response=client.post(f"/evaluation/cohort-runs/{run_id}/dossier/package", headers={"Accept-Language":lang})
    assert response.status_code == 200, response.text
    _,_,files=_abrir_zip(response.content)
    rows=list(csv.DictReader(io.StringIO(files["rows.csv"].decode("utf-8"))))
    assert rows and all(r["effective_vina_seed"] == "42" and r["seed_origin"] == "default" for r in rows)
    readme=files["README.md"].decode("utf-8")
    pdf=_pdf_text(files["dossier.pdf"])
    assert expected in readme and expected in pdf
    for r in rows:
        assert f"{int(r['source_row_index'])+1}: 42" in readme
    assert "Audited cohort evidence package" in readme if lang == "en" else "Paquete de evidencia auditada de cohorte" in readme


@pytest.mark.asyncio
async def test_semilla_historica_no_reconstruible_sin_modificar(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client=entorno.app(localization_middleware=True)
    cohort=_congelar(client)
    _,run_id=await _abrir_y_esperar(entorno,client,cohort["id"])
    async with entorno.factory() as db:
        run=await db.get(CohortRunORM,uuid.UUID(run_id))
        historical={**run.effective_config_json,"seed":0}
        historical.pop("row_seeds",None)
        historical.pop("seed_origin",None)
        run.effective_config_json=historical
        await db.commit()
    response=client.post(f"/evaluation/cohort-runs/{run_id}/dossier/package",headers={"Accept-Language":"en"})
    _,_,files=_abrir_zip(response.content)
    evidence=json.loads(files["evidence.json"])
    assert all(r["effective_vina_seed"] is None and r["seed_status"] == "not_reconstructible" for r in evidence["molecules"])
    assert "seed cannot be reconstructed" in files["README.md"].decode("utf-8")
    pdf=_pdf_text(files["dossier.pdf"])
    assert "seed cannot be reconstructed" in pdf
    assert (await entorno.corrida(run_id)).effective_config_json == historical


def test_exporta_semilla_observada_del_resultado_exactamente():
    from services.cohort.evidence import build_molecule_evidence
    from core.models import CohortRunRowORM
    rid=uuid.uuid4()
    row=CohortRunRowORM(source_row_index=0,canonical_smiles=ASPIRINA,status="completed",result_id=rid,control_role="none")
    result=SimpleNamespace(vina_random_seed=73,affinity_kcal=-5.0)
    evidence=build_molecule_evidence([row],{rid:result},effective_config={"seed":73,"seed_origin":"explicit","row_seeds":{"0":73}})
    assert evidence[0]["observed_vina_seed"] == 73
    assert evidence[0]["effective_vina_seed"] == 73
