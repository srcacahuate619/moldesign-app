"""
El protocolo se sella en los dos caminos, y dice lo que se ejecutó.

# Los dos fallos

**Uno: un camino no lo sellaba.** `docking_protocol` lo escribía sólo
`services/pipeline/runner.py`, el modo PRO. El camino normal
—`services/docking/queue_handler.py`, el que corre cuando el usuario no abre el
modal avanzado— llamaba a `upsert_evaluation_result` sin ese argumento. Cero
apariciones. Como el argumento es opcional y el repositorio no sobrescribe con
`None`, no había error ni aviso: la columna quedaba NULL, y el dossier la lee.

**Dos: el que sí lo sellaba, sellaba lo pedido.** El protocolo se construía
desde `stage_params`. Pero con `docking_engine="qvina2"` y el binario ausente,
`vina_service` cae a Vina con exhaustiveness=4 — y el sello seguía diciendo
«qvina2» con el exhaustiveness solicitado. Un sello que describe una corrida que
no ocurrió es peor que no tener sello.
"""

from __future__ import annotations

import inspect
from pathlib import Path

from core.models import DockingPose, DockingResult
from services.docking.protocolo import (
    CONTRATO,
    construir_protocolo,
    es_motor_peptidico,
)

RAIZ = Path(__file__).resolve().parents[1]


def _docking(**kwargs) -> DockingResult:
    base = dict(
        best_affinity=-8.5,
        poses=[DockingPose(rank=1, affinity=-8.5, rmsd_lb=0.0, rmsd_ub=0.0)],
        vina_random_seed=42,
        engine_efectivo="vina",
        exhaustiveness_efectiva=8,
        num_poses_solicitadas=5,
    )
    base.update(kwargs)
    return DockingResult(**base)


# ── El contrato ────────────────────────────────────────────────────────────

def test_el_protocolo_lleva_lo_que_se_ejecuto():
    p = construir_protocolo(docking=_docking(), docking_engine="vina")
    assert p["contract"] == CONTRATO
    assert p["engine"] == "vina"
    assert p["exhaustiveness"] == 8
    assert p["num_poses"] == 5
    assert p["seed"] == 42
    assert "solicitado" not in p, "sin discrepancia no se escribe el bloque"


def test_el_respaldo_de_qvina2_queda_declarado():
    """El fallo concreto: se pidió qvina2 y corrió Vina con exhaustiveness 4."""
    p = construir_protocolo(
        docking=_docking(engine_efectivo="vina_fallback_from_qvina2",
                         exhaustiveness_efectiva=4),
        docking_engine="qvina2",
        docking_params={"engine": "qvina2", "exhaustiveness": 8, "num_poses": 5},
    )
    assert p["engine"] == "vina_fallback_from_qvina2"
    assert p["exhaustiveness"] == 4
    assert p["solicitado"] == {"engine": "qvina2", "exhaustiveness": 8}


def test_un_motor_peptidico_no_lo_pisa_el_nombre_de_vina():
    """`docking_engine` vale «vina» por defecto también en la ruta peptídica."""
    p = construir_protocolo(
        docking=_docking(engine_efectivo=None),
        peptide_engine="esmfold",
        docking_engine="vina",
        docking_params={"engine": "vina"},
    )
    assert p["engine"] == "esmfold"


def test_diffpepdock_no_es_un_motor_peptidico():
    """ENG-003: estaba en la lista sin implementación detrás."""
    assert not es_motor_peptidico("diffpepdock")
    assert es_motor_peptidico("esmfold")
    assert not es_motor_peptidico(None)
    assert not es_motor_peptidico("vina")


def test_se_declara_lo_pedido_y_lo_conseguido_del_ensemble():
    """22 confórmeros de 30 no es lo mismo que 22 pedidos."""
    p = construir_protocolo(
        docking=_docking(),
        conformer_ctx={"conformers_requested": 30, "conformers_generated": 22,
                       "conformer_warnings": ["macrociclo"]},
    )
    assert p["conformers_requested"] == 30
    assert p["conformers_generated"] == 22
    assert p["conformer_warnings"] == ["macrociclo"]


def test_sin_ensemble_se_declara_uno_y_uno():
    """El camino normal genera un confórmero. Se dice, no se omite."""
    p = construir_protocolo(docking=_docking())
    assert p["conformers_requested"] == 1
    assert p["conformers_generated"] == 1


# ── Los dos caminos, en el código ──────────────────────────────────────────

def test_los_dos_caminos_sellan_el_protocolo():
    """La regresión concreta: `queue_handler` no lo escribía nunca."""
    for modulo in ("services/docking/queue_handler.py", "services/pipeline/runner.py"):
        fuente = (RAIZ / modulo).read_text(encoding="utf-8")
        assert "construir_protocolo(" in fuente, f"{modulo} no construye el protocolo"
        assert "docking_protocol=docking_protocol" in fuente, (
            f"{modulo} lo construye pero no lo pasa a upsert_evaluation_result"
        )


def test_el_docking_result_transporta_lo_ejecutado():
    """Sin estos campos, el protocolo sólo puede repetir lo que se pidió."""
    for campo in ("engine_efectivo", "exhaustiveness_efectiva", "num_poses_solicitadas"):
        assert campo in DockingResult.model_fields, campo


def test_vina_service_rellena_lo_ejecutado():
    fuente = (RAIZ / "services" / "docking" / "vina_service.py").read_text(encoding="utf-8")
    assert "engine_efectivo=effective_engine_identity" in fuente
    assert "exhaustiveness_efectiva=effective_exhaustiveness" in fuente


def test_el_repositorio_no_borra_el_protocolo_con_none():
    """El upsert se llama varias veces por evaluación; un None intermedio no borra."""
    from db.repository import Repository

    fuente = inspect.getsource(Repository.upsert_evaluation_result)
    assert "if docking_protocol is not None:" in fuente
