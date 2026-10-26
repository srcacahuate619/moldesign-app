"""El ensemble guarda su corrida CON la procedencia de ejecución.

Defecto visto en dev (2026-10-06): una evaluación en modo ensamble se guardaba en
Moldex, pero Molcy la mostraba apagada («no conserva receptor, poses o caja
verificables»). `run_ensemble_docking` construía el `DockingResult` de la piscina
sin `execution_provenance`: la corrida quedaba sin caja, sin `receptor_prep` y sin
toolchain. Moldex la listaba, pero nada que exigiera una caja verificable podía
usarla.
"""
from __future__ import annotations

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from api.routers import molcy
from core.models import DockingPose, DockingResult
from services.docking.ensemble import run_ensemble_docking
from services.docking.protocolo import construir_protocolo

CAJA = {"box_center": [27.713, 3.188, -43.66], "box_size": [30.0, 30.0, 30.0]}


def _procedencia(indice: int, **cambios) -> dict:
    base = {
        **CAJA,
        "cpu": 8,
        "app_version": "1.0.1",
        "git_commit": "abc1234",
        "receta_receptor": "v3",
        "receptor_sha256": "a" * 64,
        "receptor_prep": {"source": "meeko_report", "recipe_hash": "r" * 64},
        "toolchain": {"vina": "1.2.7", "meeko": "0.6.1"},
        "search_trace": {"binary_sha256": f"traza{indice}"},
        "ligand_input_sha256": f"lig{indice}",
        "ligand_input_path": f"ligands/h__c{indice}/conformer.sdf",
        "ligand_pdbqt_sha256": f"pdbqt{indice}",
        "ligand_pdbqt_path": f"ligands/h__c{indice}/ligand.pdbqt",
        "log_path": f"runs/{indice}/vina.log",
        "log_sha256": f"log{indice}",
        "poses_sha256": f"poses{indice}",
    }
    base.update(cambios)
    return base


def _resultado(afinidad: float, procedencia: dict | None, indice: int = 0) -> DockingResult:
    pose = DockingPose(rank=1, affinity=afinidad, rmsd_lb=0.0, rmsd_ub=0.0)
    return DockingResult(
        best_affinity=afinidad, poses=[pose, pose.model_copy(update={"rank": 2})],
        parsing_source="sdf", poses_file_path=f"runs/docking/h__c{indice}/poses.sdf",
        engine_efectivo="vina", exhaustiveness_efectiva=32, num_poses_solicitadas=9,
        vina_version="1.2.7", vina_random_seed=42,
        receptor_sha256="a" * 64, receptor_path=f"runs/receptors/{'a' * 64}.pdbqt",
        execution_provenance=procedencia,
    )


async def _ensamblar(procedencias: list[dict | None]) -> DockingResult:
    por_hash = {f"h__c{i}": p for i, p in enumerate(procedencias)}

    async def dock(smiles_hash, smiles=None):
        indice = int(smiles_hash.rsplit("c", 1)[1])
        return _resultado(-9.0 + indice * 0.1, por_hash[smiles_hash], indice)

    return await run_ensemble_docking(
        smiles="CCO",
        conformeros=[{"indice": i, "smiles_hash": f"h__c{i}", "semilla": 1000 + i,
                      "energia": 5.5 + i} for i in range(len(procedencias))],
        num_poses=4, dock_una=dock,
    )


@pytest.mark.asyncio
async def test_la_piscina_conserva_la_caja_el_receptor_preparado_y_el_toolchain():
    resultado = await _ensamblar([_procedencia(i) for i in range(3)])

    procedencia = resultado.execution_provenance
    assert procedencia is not None
    assert procedencia["box_center"] == CAJA["box_center"]
    assert procedencia["box_size"] == CAJA["box_size"]
    assert procedencia["receptor_sha256"] == "a" * 64
    assert procedencia["receptor_prep"]["recipe_hash"] == "r" * 64
    assert procedencia["toolchain"]["vina"] == "1.2.7"
    assert procedencia["app_version"] == "1.0.1"
    assert "campos_heterogeneos" not in procedencia


@pytest.mark.asyncio
async def test_lo_de_una_sola_corrida_no_se_atribuye_a_la_piscina():
    """Un `poses_sha256` a nivel de piscina diría que UN archivo contiene las poses
    entregadas, y las entregadas salen de K archivos."""
    resultado = await _ensamblar([_procedencia(i) for i in range(3)])

    procedencia = resultado.execution_provenance
    for campo in ("poses_sha256", "log_sha256", "log_path", "ligand_input_sha256",
                  "ligand_pdbqt_sha256", "search_trace"):
        assert campo not in procedencia, campo
    # Cada corrida de Vina conserva lo suyo, con su índice.
    por_conformacion = procedencia["por_conformacion"]
    assert [c["indice"] for c in por_conformacion] == [0, 1, 2]
    assert [c["poses_sha256"] for c in por_conformacion] == ["poses0", "poses1", "poses2"]
    assert por_conformacion[1]["log_path"] == "runs/1/vina.log"
    assert "search_trace" not in por_conformacion[0]


@pytest.mark.asyncio
async def test_sin_procedencia_en_las_corridas_no_se_inventa_ninguna():
    resultado = await _ensamblar([None, None])
    assert resultado.execution_provenance is None


@pytest.mark.asyncio
async def test_dos_cajas_distintas_no_comparten_piscina():
    cambiada = _procedencia(1, box_center=[27.713, 3.188, -40.0])
    with pytest.raises(RuntimeError, match="box_center"):
        await _ensamblar([_procedencia(0), cambiada, _procedencia(2)])


@pytest.mark.asyncio
async def test_la_caja_se_compara_como_la_huella_del_cache_a_tres_decimales():
    casi = _procedencia(1, box_center=[27.71301, 3.18799, -43.66001])
    resultado = await _ensamblar([_procedencia(0), casi])
    assert resultado.execution_provenance["box_center"] == CAJA["box_center"]
    assert "campos_heterogeneos" not in resultado.execution_provenance


@pytest.mark.asyncio
async def test_un_campo_de_entorno_distinto_ni_se_hereda_ni_tumba_la_corrida():
    """Un resultado del caché puede venir de otra versión de la app."""
    resultado = await _ensamblar([
        _procedencia(0), _procedencia(1, git_commit="def5678"), _procedencia(2),
    ])

    procedencia = resultado.execution_provenance
    assert procedencia["git_commit"] is None
    assert procedencia["campos_heterogeneos"] == ["git_commit"]
    # La caja sí coincide y se conserva.
    assert procedencia["box_center"] == CAJA["box_center"]


@pytest.mark.asyncio
async def test_si_una_corrida_no_trae_la_caja_no_se_afirma_con_la_de_otra():
    """Dato ausente no es incompatibilidad, pero tampoco se rellena."""
    sin_caja = {k: v for k, v in _procedencia(1).items() if k not in CAJA}
    resultado = await _ensamblar([_procedencia(0), sin_caja])

    procedencia = resultado.execution_provenance
    assert procedencia["box_center"] is None and procedencia["box_size"] is None
    assert set(procedencia["campos_heterogeneos"]) == {"box_center", "box_size"}


def _fuente_de_molcy(monkeypatch, snapshot: dict) -> dict:
    run = SimpleNamespace(molecule_id=uuid.uuid4(), task_id=str(uuid.uuid4()),
                          snapshot_json=snapshot)

    class DB:
        async def execute(self, _statement):
            return SimpleNamespace(all=lambda: [(run, "ensamble", "1J38")])

    class Repo:
        def __init__(self, _db): pass
        async def get_all_targets(self): return []

    monkeypatch.setattr(molcy, "Repository", Repo)
    return asyncio.run(molcy.fuentes(SimpleNamespace(id=uuid.uuid4()), DB()))["moldex"][0]


def _instantanea_de(resultado: DockingResult) -> dict:
    """Lo que el pipeline persiste de la corrida: el protocolo sellado más las rutas."""
    return {
        "receptor_path": resultado.receptor_path,
        "receptor_sha256": resultado.receptor_sha256,
        "poses_file_path": resultado.poses_file_path,
        "docking_protocol": construir_protocolo(docking=resultado),
    }


@pytest.mark.asyncio
async def test_una_evaluacion_de_ensamble_guardada_es_fuente_de_molcy(monkeypatch):
    resultado = await _ensamblar([_procedencia(i) for i in range(3)])

    fuente = await asyncio.to_thread(_fuente_de_molcy, monkeypatch, _instantanea_de(resultado))

    assert fuente["disponible"] is True
    assert fuente["motivo"] is None
    # La piscina no tiene un SDF único: «resultado» no se ofrece, sólo lo que se
    # puede verificar (receptor y caja).
    assert fuente["escenas_disponibles"] == ["receptor"]


@pytest.mark.asyncio
async def test_sin_la_procedencia_la_misma_evaluacion_seguia_apagada(monkeypatch):
    """Control: el estado previo al arreglo, con la procedencia ausente."""
    resultado = (await _ensamblar([_procedencia(i) for i in range(3)])).model_copy(
        update={"execution_provenance": None})

    fuente = await asyncio.to_thread(_fuente_de_molcy, monkeypatch, _instantanea_de(resultado))

    assert fuente["disponible"] is False
    assert fuente["escenas_disponibles"] == []


@pytest.mark.asyncio
async def test_por_conformacion_trae_lo_que_solo_el_ensemble_sabe():
    """De cuántas candidatas salen las entregadas debe constar como dato, no como aviso."""
    resultado = await _ensamblar([_procedencia(i) for i in range(3)])

    por_conformacion = resultado.execution_provenance["por_conformacion"]
    assert [c["semilla_conformacional"] for c in por_conformacion] == [1000, 1001, 1002]
    assert [c["energia_mmff"] for c in por_conformacion] == [5.5, 6.5, 7.5]
    assert [c["num_poses"] for c in por_conformacion] == [2, 2, 2]
    assert por_conformacion[1]["poses_file_path"] == "runs/docking/h__c1/poses.sdf"
    assert por_conformacion[2]["mejor_afinidad_kcal_mol"] == pytest.approx(-8.8)
    assert sum(c["num_poses"] for c in por_conformacion) == 6


@pytest.mark.asyncio
async def test_lo_que_no_se_midio_no_se_escribe_como_cero():
    """Una conformación sin energía MMFF (la de partida) no lleva `energia_mmff: null`."""
    por_hash = {"h__c0": _procedencia(0)}

    async def dock(smiles_hash, smiles=None):
        return _resultado(-9.0, por_hash[smiles_hash])

    resultado = await run_ensemble_docking(
        smiles="CCO", conformeros=[{"indice": 0, "smiles_hash": "h__c0",
                                    "semilla": 42, "energia": None}],
        num_poses=4, dock_una=dock)

    entrada = resultado.execution_provenance["por_conformacion"][0]
    assert "energia_mmff" not in entrada
    assert entrada["semilla_conformacional"] == 42
