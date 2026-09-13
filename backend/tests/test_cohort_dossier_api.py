"""
Gate 1 (5D) de extremo a extremo: evidencia, dossier PDF y paquete verificable.

Reutiliza el entorno de `test_cohort_execution` —SQLite de archivo, app real,
evaluador sustituido en un solo punto— porque el contrato que se comprueba aquí
empieza en una corrida de verdad: sin corrida no hay evidencia que resumir.

Lo que protegen, en orden de gravedad:

1. **El resultado pertenece a ESTA ejecución.** `result_id` sale de lo que
   devolvió el pipeline, no de «el más reciente de esta molécula».
2. **El receptor del ZIP es el congelado**, byte a byte, con su SHA.
3. **Adulterar cualquier archivo —el manifiesto incluido— invalida el paquete**,
   y lo detecta el MISMO verificador que valida los paquetes de caso.
4. **Una ausencia se declara, no se fabrica.**
"""

from __future__ import annotations

import hashlib
import io
import json
import uuid
import zipfile

import pytest

from core.models import CohortRunORM
from services.cohort import execution as ex
from services.dossier.verify import verificar_paquete
from tests.conftest import rdkit_available

# Fixtures y helpers compartidos. pytest los descubre al importarlos aquí.
from tests.test_cohort_execution import (  # noqa: F401
    CSV,
    _abrir_y_esperar,
    _congelar,
    entorno,
    evaluador,
)


def _abrir_zip(datos: bytes):
    with zipfile.ZipFile(io.BytesIO(datos)) as zf:
        raiz = zf.namelist()[0].split("/")[0]
        nombres = {n[len(raiz) + 1:] for n in zf.namelist() if not n.endswith("/")}
        contenido = {n: zf.read(f"{raiz}/{n}") for n in nombres}
    return raiz, nombres, contenido


# ── result_id ────────────────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_result_id_es_el_de_esta_ejecucion_no_el_mas_reciente(entorno, evaluador, monkeypatch):
    """
    El `result_id` sale de lo que devolvió ESTA llamada al pipeline.

    Buscar «el resultado más reciente de esta molécula» devolvería el de otra
    corrida —o el de una evaluación individual que comparte molécula— y la
    evidencia describiría un cálculo que no es el suyo.
    """
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)

    devueltos: dict[str, dict[str, str]] = {}

    async def _con_result_id(*, canonical_smiles, molecule_name, receptor, config, user_id):
        ids = {"molecule_id": str(uuid.uuid4()), "evaluation_result_id": str(uuid.uuid4())}
        devueltos[canonical_smiles] = ids
        return ids

    monkeypatch.setattr(ex, "_evaluate_one", _con_result_id)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    filas = {f.source_row_index: f for f in await entorno.filas(run_id)}
    for indice in (0, 1):
        esperado = devueltos[filas[indice].canonical_smiles]
        assert str(filas[indice].result_id) == esperado["evaluation_result_id"]
        assert str(filas[indice].molecule_id) == esperado["molecule_id"]
    # La duplicada hereda el resultado de su ejecutora, no uno nuevo.
    assert filas[2].result_id == filas[0].result_id
    assert filas[2].molecule_id == filas[0].molecule_id


# ── Evidencia ────────────────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_la_evidencia_declara_cobertura_con_denominadores(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    respuesta = client.get(f"/evaluation/cohort-runs/{run_id}/evidence")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    cobertura = cuerpo["coverage"]
    assert cobertura["source_rows"] == 5
    assert cobertura["eligible_rows"] == 3
    assert cobertura["not_eligible_rows"] == 2
    assert cobertura["unique_molecules_executed"] == 2
    assert cobertura["completed_rows"] == 2
    assert cobertura["duplicate_reused_rows"] == 1
    # Los denominadores, explícitos y no derivados por el lector.
    assert cobertura["denominators"]["eligible_over_source"] == {
        "numerator": 3,
        "denominator": 5,
        "value": 0.6,
    }
    assert len(cuerpo["molecules"]) == 3
    # Sin etiquetas útiles, las métricas se abstienen con razón estable.
    assert cuerpo["labeled_metrics"]["status"] == "not_evaluated"
    assert cuerpo["labeled_metrics"]["reason_code"] in (
        "MUESTRA_INSUFICIENTE",
        "SIN_ETIQUETAS",
        "SIN_NEGATIVOS",
        "SIN_POSITIVOS",
        "SIN_AFINIDAD",
    )


@rdkit_available
@pytest.mark.asyncio
async def test_la_evidencia_no_devuelve_total_score_como_conclusion(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    plano = json.dumps(client.get(f"/evaluation/cohort-runs/{run_id}/evidence").json()).lower()

    for prohibido in ("total_score", "mejor fármaco", "probabilidad de éxito"):
        assert prohibido not in plano
    assert "observed_vina_affinity_kcal_mol" in plano
    # «ranking» sólo puede aparecer NEGADO, dentro de los límites declarados.
    cuerpo = client.get(f"/evaluation/cohort-runs/{run_id}/evidence").json()
    assert not any("ranking" in json.dumps(m).lower() for m in cuerpo["molecules"])
    assert any("no hay puntuación agregada ni ranking" in limite.lower()
               for limite in cuerpo["limits"])


@rdkit_available
@pytest.mark.asyncio
async def test_el_unico_orden_ofrecido_se_llama_afinidad_vina_observada(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    ok = client.get(
        f"/evaluation/cohort-runs/{run_id}/evidence",
        params={"sort": "afinidad_vina_observada"},
    )
    assert ok.status_code == 200
    assert ok.json()["sorted_by"] == "afinidad_vina_observada"

    for inventado in ("mejores", "score", "probabilidad", "exito"):
        malo = client.get(
            f"/evaluation/cohort-runs/{run_id}/evidence", params={"sort": inventado}
        )
        assert malo.status_code == 422, inventado


# ── Dossier PDF ──────────────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_el_dossier_pdf_se_renderiza(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    respuesta = client.post(f"/evaluation/cohort-runs/{run_id}/dossier/preview")

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"] == "application/pdf"
    assert respuesta.content[:5] == b"%PDF-"
    assert len(respuesta.content) > 3000


# ── Paquete verificable ──────────────────────────────────────────────


@rdkit_available
@pytest.mark.asyncio
async def test_el_zip_lleva_el_receptor_congelado_y_lo_valida_el_mismo_verificador(
    entorno, evaluador
):
    await entorno.crear_target()
    receptor = entorno.preparar_receptor(contenido=b"ATOM  receptor preparado v1\n")
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    respuesta = client.post(f"/evaluation/cohort-runs/{run_id}/dossier/package")

    assert respuesta.status_code == 200
    datos = respuesta.content
    assert datos[:2] == b"PK"
    raiz, nombres, contenido = _abrir_zip(datos)

    for esperado in (
        "dossier.pdf", "cohort.json", "preflight.json", "run.json", "evidence.json",
        "rows.csv", "manifest.json", "checksums.sha256", "README.md",
        "inputs/receptor_prepared.pdbqt",
    ):
        assert esperado in nombres, esperado
    # El archivo original también viaja, tal como se subió.
    assert any(n.startswith("inputs/") and n.endswith(".csv") for n in nombres)

    # El receptor del ZIP es EL congelado, byte a byte, y su SHA cuadra con el
    # que la corrida declaró.
    pdbqt = contenido["inputs/receptor_prepared.pdbqt"]
    assert pdbqt == receptor
    corrida = await entorno.corrida(run_id)
    assert bytes(corrida.receptor_prepared_bytes) == pdbqt

    manifiesto = json.loads(contenido["manifest.json"])
    declarado = next(
        f for f in manifiesto["files"] if f["path"] == "inputs/receptor_prepared.pdbqt"
    )
    assert declarado["sha256"] == hashlib.sha256(pdbqt).hexdigest()
    assert corrida.receptor_provenance_json["prepared_sha256"] == "sha256:" + declarado["sha256"]

    # Y el MISMO verificador del dossier de caso lo valida: un solo protocolo.
    veredicto = verificar_paquete(datos)
    assert veredicto.valido, veredicto.errores


@rdkit_available
@pytest.mark.asyncio
async def test_adulterar_cualquier_archivo_del_zip_lo_invalida(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])
    datos = client.post(f"/evaluation/cohort-runs/{run_id}/dossier/package").content

    def _reescribir(objetivo: str, nuevo: bytes) -> bytes:
        salida = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(datos)) as origen:
            with zipfile.ZipFile(salida, "w", zipfile.ZIP_DEFLATED) as destino:
                for info in origen.infolist():
                    crudo = origen.read(info.filename)
                    destino.writestr(
                        info, nuevo if info.filename.endswith(objetivo) else crudo
                    )
        return salida.getvalue()

    assert verificar_paquete(datos).valido

    # Un artefacto cualquiera…
    assert not verificar_paquete(_reescribir("rows.csv", b"adulterado\n")).valido
    # …el receptor…
    assert not verificar_paquete(
        _reescribir("inputs/receptor_prepared.pdbqt", b"OTRO RECEPTOR\n")
    ).valido
    # …el PDF…
    assert not verificar_paquete(_reescribir("dossier.pdf", b"%PDF-falso\n")).valido
    # …y el MANIFIESTO, que es lo que un atacante retocaría para tapar lo
    # anterior. `checksums.sha256` se calcula DESPUÉS e incluye el manifiesto,
    # que es exactamente lo que hace que esto se detecte.
    falso = json.dumps({"manifest_version": 1, "root": "x", "files": []}).encode("utf-8")
    assert not verificar_paquete(_reescribir("manifest.json", falso)).valido


@rdkit_available
@pytest.mark.asyncio
async def test_una_corrida_sin_receptor_congelado_declara_no_disponible(entorno, evaluador):
    """
    Corrida anterior al corrigendum de 5C: sin bytes de receptor.

    El manifiesto lo declara `NO_DISPONIBLE` con su razón, y **no** se sustituye
    por el archivo del catálogo, que pudo repararse desde entonces. Una ausencia
    declarada sigue siendo un paquete válido; una ausencia rellenada sería un
    paquete que miente.
    """
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    _, run_id = await _abrir_y_esperar(entorno, client, cohorte["id"])

    async with entorno.factory() as session:
        corrida = await session.get(CohortRunORM, uuid.UUID(run_id))
        corrida.receptor_prepared_bytes = None
        await session.commit()

    datos = client.post(f"/evaluation/cohort-runs/{run_id}/dossier/package").content
    _, nombres, contenido = _abrir_zip(datos)

    manifiesto = json.loads(contenido["manifest.json"])
    declarado = next(
        f for f in manifiesto["files"] if f["path"] == "inputs/receptor_prepared.pdbqt"
    )
    assert declarado["estado"] == "NO_DISPONIBLE"
    assert declarado["sha256"] is None
    assert "repreparado" in (declarado["razon"] or "")
    # Declarado pero NO fabricado.
    assert "inputs/receptor_prepared.pdbqt" not in nombres
    # Y el paquete sigue siendo verificable.
    assert verificar_paquete(datos).valido


@rdkit_available
@pytest.mark.asyncio
async def test_una_corrida_no_terminal_no_produce_dossier(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    client = entorno.app()
    cohorte = _congelar(client)
    respuesta = client.post(f"/evaluation/cohorts/{cohorte['id']}/runs")
    run_id = respuesta.json()["run_id"]  # queda `queued`: el fixture no encola

    preview = client.post(f"/evaluation/cohort-runs/{run_id}/dossier/preview")
    paquete = client.post(f"/evaluation/cohort-runs/{run_id}/dossier/package")

    for fallo in (preview, paquete):
        assert fallo.status_code == 409
        assert fallo.json()["detail"]["code"] == "CORRIDA_NO_TERMINAL"
        assert "queued" in fallo.json()["detail"]["message"]


@rdkit_available
@pytest.mark.asyncio
async def test_la_evidencia_y_el_dossier_respetan_la_propiedad(entorno, evaluador):
    await entorno.crear_target()
    entorno.preparar_receptor()
    ana = await entorno.crear_usuario("ana")
    bruno = await entorno.crear_usuario("bruno")
    cliente_ana = entorno.app(ana)
    cohorte = _congelar(cliente_ana)
    _, run_id = await _abrir_y_esperar(entorno, cliente_ana, cohorte["id"])

    cliente_bruno = entorno.app(bruno)
    # Ajena e inexistente contestan lo mismo: un 403 confirmaría que existe.
    assert cliente_bruno.get(f"/evaluation/cohort-runs/{run_id}/evidence").status_code == 404
    assert cliente_bruno.post(f"/evaluation/cohort-runs/{run_id}/dossier/preview").status_code == 404
    assert cliente_bruno.post(f"/evaluation/cohort-runs/{run_id}/dossier/package").status_code == 404
    assert cliente_ana.get(f"/evaluation/cohort-runs/{run_id}/evidence").status_code == 200
