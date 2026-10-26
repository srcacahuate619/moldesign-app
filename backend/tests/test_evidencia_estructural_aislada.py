"""La validación estructural corre en un proceso hijo con plazo, y vencido se detiene sin tocar el docking.

CAL-D-01-R4: con el compuesto 4-67 (biciclo[1.1.1]pentano), el `energy_ratio` de PoseBusters no termina su embebido
ETKDG. Corría en un hilo: la evaluación caía por Timeout a los 1200 s y el hilo seguía gastando CPU y frenando los
compuestos siguientes. Un proceso hijo sí se puede matar.
"""

from __future__ import annotations

import asyncio
import sys

import pytest

from services.chemistry import structural_evidence as se
from tests.test_structural_evidence import _pdbqt_desde_smiles, _pose, rdkit_available, receptor  # noqa: F401


def _sin_hora(d):
    if isinstance(d, dict):
        return {k: _sin_hora(v) for k, v in d.items() if k != "evaluated_at"}
    if isinstance(d, list):
        return [_sin_hora(x) for x in d]
    return d


@rdkit_available
def test_aislada_da_lo_mismo_que_en_el_proceso(receptor):  # noqa: F811
    argumentos = dict(poses=[_pose(1, _pdbqt_desde_smiles()[0])], target_pdb_id=None,
                      receptor_sha256=receptor.sha256, receptor_bytes=receptor.bytes)
    directa = se.build_structural_evidence(**argumentos)
    aislada = asyncio.run(se.construir_evidencia_aislada(**argumentos))
    assert _sin_hora(aislada) == _sin_hora(directa)


@rdkit_available
def test_al_vencer_el_plazo_se_detiene_y_se_declara_no_evaluada(receptor):  # noqa: F811
    from services.docking.desktop_process_registry import _processes

    evidencia = asyncio.run(se.construir_evidencia_aislada(
        poses=[_pose(1, _pdbqt_desde_smiles()[0])], target_pdb_id=None, receptor_sha256=receptor.sha256,
        receptor_bytes=receptor.bytes, task_id="tarea-plazo", plazo_s=0.05))
    assert evidencia["stage_status"] == se.STAGE_NOT_EVALUATED
    assert evidencia["reason_code"] == se.VALIDADOR_EXCEDIO_EL_PLAZO
    assert evidencia["poses_produced"] == 1
    assert "NO se ve afectado" in evidencia["detail"]
    assert "tarea-plazo" not in _processes


def test_cancelar_mata_el_proceso_de_validacion_de_esa_tarea():
    from services.docking.desktop_process_registry import register_process, unregister_process
    from services.docking.queue_handler import cancel_active_structural_evidence

    async def caso():
        proceso = await asyncio.create_subprocess_exec(sys.executable, "-c", "import time; time.sleep(60)")
        register_process("tarea-cancelada", "structural_evidence", proceso)
        try:
            assert cancel_active_structural_evidence("tarea-cancelada") == 1
            await asyncio.wait_for(proceso.wait(), timeout=10)
        finally:
            unregister_process("tarea-cancelada", "structural_evidence", proceso)
        return proceso.returncode

    assert asyncio.run(caso()) is not None


def test_sin_poses_no_lanza_ningun_proceso():
    evidencia = asyncio.run(se.construir_evidencia_aislada(poses=[], target_pdb_id=None, receptor_sha256=None))
    assert evidencia["reason_code"] == se.SIN_POSES


def test_la_razon_nueva_es_una_abstencion_declarada():
    assert se.VALIDADOR_EXCEDIO_EL_PLAZO in se.ABSTENTION_REASONS
