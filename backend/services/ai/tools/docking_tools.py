"""
services/ai/tools/docking_tools.py

Herramientas de docking de MolChat.

MOLCHAT-INT-001 / D-08. `run_docking` llamaba a `run_single_evaluation`, una
función privada del pipeline que **no existe** en `queue_handler`. El
`ImportError` se capturaba y el chat contestaba «Pipeline de docking no
disponible en este modo»: una capacidad rota que se comunicaba como una
capacidad ausente.

D-08 decidió que sí, MolChat lanza evaluaciones, y lo justificó por el eje
científico: la evaluación es el mecanismo por el que una respuesta deja de ser
generación y pasa a ser cálculo. De ahí los tres criterios que gobiernan este
módulo:

1. la corrida entra por `services.evaluation_submission.registrar_corrida`, la
   misma puerta que `POST /evaluation/submit` — identidad, receptor, preflight,
   persistencia y procedencia;
2. va en segundo plano: el turno declara que la lanzó y da su `task_id`, no
   bloquea la conversación ni finge que ya terminó;
3. todo número se cita a su corrida persistida. Si la corrida no ha terminado,
   falló, o no es de esta cuenta, la herramienta lo dice y se abstiene — nunca
   entrega una estimación en lugar del resultado.
"""

from __future__ import annotations

import uuid

from fastapi import HTTPException

from services.ai.tool_registry import ToolDef, get_tool_registry


SIN_IDENTIDAD = (
    "No puedo lanzar la evaluación: esta petición no trae identidad de cuenta. "
    "Una corrida pertenece a quien la pide —es lo que permite recuperarla, "
    "citarla y certificarla—, así que no la lanzo de forma anónima."
)


async def _authorize_target(target_pdb: str, user_id: str | None) -> None:
    """Aplica a MolChat el mismo contrato que usan las rutas HTTP."""
    from services.targets.access import is_rcsb_pdb_id

    if is_rcsb_pdb_id(target_pdb.strip().upper()):
        # Los receptores subidos reciben siempre un ID USR_* en ingestion_manager.
        # Evita abrir la DB para cada operación contra un PDB público de RCSB.
        return

    from core.database import get_db_session
    from db.repository import Repository
    from services.targets.access import get_target_for_user_id

    async with get_db_session() as db:
        await get_target_for_user_id(
            Repository(db), target_pdb, user_id, allow_missing=True
        )


def _cuenta(user_id: str | None) -> uuid.UUID | None:
    """La identidad autenticada, o nada. Nunca una cuenta de prueba (D-05)."""
    if not user_id:
        return None
    try:
        return uuid.UUID(str(user_id))
    except (ValueError, TypeError, AttributeError):
        return None


async def run_docking(
    smiles: str,
    target_pdb: str = "7E2Y",
    user_id: str | None = None,
) -> str:
    """Lanzar una evaluación real en segundo plano y devolver su `task_id`.

    No espera el resultado: una corrida de Vina tarda minutos y el turno del
    chat no puede quedarse colgado de ella. Devuelve el identificador con el
    que `check_docking_status` recupera después el número, ya citado.
    """
    cuenta = _cuenta(user_id)
    if cuenta is None:
        return SIN_IDENTIDAD

    from core.database import get_db_session
    from core.models import UserORM

    async with get_db_session() as db:
        usuario = await db.get(UserORM, cuenta)
        if usuario is None:
            return SIN_IDENTIDAD

        from api.routers.evaluation import (
            EvaluationSubmitRequest,
            PipelineConfigRequest,
        )
        from services import evaluation_submission

        try:
            peticion = EvaluationSubmitRequest(
                smiles=smiles,
                target_pdb_id=target_pdb.strip().upper(),
                molecule_name=None,
                # El gate runtime encontró que una corrida lanzada desde el chat
                # llegaba SIN `docking_protocol`: el pipeline sólo lo sella
                # cuando `properties` y `docking` corrieron ambas, y sin
                # configuración explícita eso no estaba garantizado. Una corrida
                # del chat con menos procedencia que una de la pestaña
                # contradice el criterio 1 de D-08 —el mismo camino—, y encima
                # en la superficie donde el número se narra.
                #
                # Los parámetros son deliberadamente modestos: el chat lanza en
                # segundo plano mientras el investigador sigue escribiendo, y no
                # es el sitio para arrancar el pipeline más caro sin pedirlo.
                pipeline_config=PipelineConfigRequest(
                    enabled_stages=[
                        "validation", "properties", "sa_filter",
                        "conformer", "docking", "xgb",
                    ],
                    stage_params={
                        "properties": {"run_admet_ai": False},
                        "conformer": {"conformers": 1},
                        "docking": {"exhaustiveness": 8, "num_poses": 5},
                    },
                    docking_engine="vina",
                    pro_selectivity=False,
                    pro_mmgbsa=False,
                ),
            )
        except Exception as exc:  # petición malformada: SMILES vacío, PDB corto
            return f"No puedo lanzar la evaluación: {str(exc)[:150]}"

        try:
            corrida = await evaluation_submission.registrar_corrida(
                data=peticion,
                db=db,
                current_user=usuario,
                client_ip=None,
                # MolChat no tiene la pantalla donde el investigador acepta el
                # preflight, así que lo comprueba el servidor antes de encolar.
                exigir_preflight=True,
            )
        except HTTPException as exc:
            return (
                "No lancé la evaluación: "
                f"{str(exc.detail)[:200]} "
                "(no la sustituyo por una estimación)."
            )
        except Exception as exc:
            from core.exceptions import MolDesignError

            motivo = (
                exc.message if isinstance(exc, MolDesignError) else str(exc)
            )
            return f"No lancé la evaluación: {motivo[:200]}"

    return (
        f"Evaluación lanzada en segundo plano contra {corrida.target_pdb_id}.\n"
        f"  task_id={corrida.task_id}\n"
        f"  molécula={corrida.canonical_smiles}\n"
        f"{corrida.aviso_de_calibracion}"
        "Todavía no hay afinidad ni score: la corrida acaba de empezar y no los "
        "estimo. Consultá el estado con check_docking_status | "
        f"task_id={corrida.task_id}, y citá cualquier número por ese task_id."
    )


async def check_docking_status(
    task_id: str = "",
    user_id: str | None = None,
) -> str:
    """Consultar una corrida lanzada desde el chat, y citarla por su `task_id`.

    La propiedad se comprueba con la misma política que `GET
    /evaluation/status/{task_id}`: `_autorizar_corrida`, extraída del router
    justamente para que no hubiera dos reglas.
    """
    cuenta = _cuenta(user_id)
    if cuenta is None:
        return SIN_IDENTIDAD
    if not task_id.strip():
        return "Necesito el task_id de la corrida para consultarla."

    task_id = task_id.strip()

    from core.database import get_db_session
    from core.models import UserORM

    async with get_db_session() as db:
        usuario = await db.get(UserORM, cuenta)
        if usuario is None:
            return SIN_IDENTIDAD

        from api.routers import evaluation as evaluation_router

        try:
            await evaluation_router._autorizar_corrida(
                task_id,
                current_user=usuario,
                db=db,
                client_ip=None,
            )
        except HTTPException as exc:
            return f"No puedo mostrar esa corrida: {str(exc.detail)[:200]}"

    from services.docking import queue_handler

    try:
        estado = await queue_handler.get_job_status(task_id)
    except Exception as exc:
        return f"No pude leer el estado de la corrida {task_id}: {str(exc)[:150]}"

    if estado is None:
        return f"No encontré la corrida {task_id}."

    situacion = getattr(estado, "status", "PENDING")

    if situacion == "FAILURE":
        motivo = getattr(estado, "error", None) or "sin motivo registrado"
        return (
            f"[corrida {task_id}] La evaluación falló: {str(motivo)[:200]}. "
            "No hay resultado que citar y no la estimo."
        )

    resultado = getattr(estado, "result", None)
    if situacion != "SUCCESS" or resultado is None:
        progreso = getattr(estado, "progress", 0)
        return (
            f"[corrida {task_id}] Sigue en curso ({situacion}, {progreso}%). "
            "Todavía no hay afinidad ni score, y no los estimo."
        )

    lineas = [f"[corrida {task_id} — resultado persistido]"]

    def _num(valor, formato: str) -> str | None:
        return format(valor, formato) if isinstance(valor, (int, float)) else None

    partes = []
    afinidad = _num(getattr(resultado, "affinity_kcal", None), ".2f")
    if afinidad:
        partes.append(f"afinidad={afinidad} kcal/mol")
    score_af = _num(getattr(resultado, "affinity_score", None), ".1f")
    if score_af:
        partes.append(f"score_afinidad={score_af}")
    total = _num(getattr(resultado, "total_score", None), ".1f")
    if total:
        partes.append(f"score_total={total}/100")
    adme = _num(getattr(resultado, "adme_score", None), ".1f")
    if adme:
        partes.append(f"ADME={adme}")
    if partes:
        lineas.append("  " + " | ".join(partes))

    procedencia = []
    version = getattr(resultado, "vina_version", None)
    if version:
        procedencia.append(f"Vina {version}")
    semilla = getattr(resultado, "vina_random_seed", None)
    if semilla is not None:
        procedencia.append(f"seed={semilla}")
    receptor = getattr(resultado, "receptor_sha256", None)
    if receptor:
        procedencia.append(f"receptor_sha256={receptor}")
    if procedencia:
        lineas.append("  Procedencia: " + " | ".join(procedencia))

    molecula = getattr(resultado, "molecule_id", None)
    if molecula is not None:
        lineas.append(f"  molecule_id={molecula}")

    lineas.append(
        "  Estos números vienen de esta corrida; citalos con su task_id."
    )
    return "\n".join(lineas)


async def get_rescoring(
    smiles: str,
    target_pdb: str = "7E2Y",
    user_id: str | None = None,
) -> str:
    """Obtener score ML de rescoring (XGBoost) para uno o varios SMILES."""
    try:
        await _authorize_target(target_pdb, user_id)
    except HTTPException:
        return "Error: receptor no disponible para esta cuenta."

    try:
        # F-14: la clase llega via el bridge (único módulo que resuelve
        # paths del sidecar), nunca con import directo de rescoring.*.
        from services.rescoring_bridge import get_model_manager_class

        ModelManager = get_model_manager_class()
        mgr = ModelManager()
        mgr.load_models()

        # Batch: multiples SMILES separados por | , o salto de linea
        sm_list = [s.strip() for s in smiles.replace("|", "\n").replace(",", "\n").split("\n") if s.strip()]
        if len(sm_list) > 1:
            try:
                results = mgr.predict_batch(sm_list, target_pdb)
                lines = [f"Rescoring XGBoost (batch {len(sm_list)}):"]
                for s, r in zip(sm_list[:12], results[:12]):
                    lines.append(f"  {s[:30]}: score={r:.2f}")
                return "\n".join(lines)
            except (AttributeError, TypeError):
                pass

        result = mgr.predict(mgr.extract_features(sm_list[0], target_pdb), sm_list[0])
        return (
            f"Rescoring XGBoost: score={result.score_a:.2f}. "
            f"GNN: {result.gnn_score or 'N/D'}."
        )
    except ImportError:
        return "Error: Módulo de rescoring no disponible."
    except Exception as e:
        return f"Error en rescoring: {str(e)[:150]}"


def register_docking_tools():
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="run_docking",
        clase="dato_persistido",
        procedencia="corrida registrada en evaluation_runs de esta cuenta",
        description=(
            "Lanza una evaluación real (docking Vina) contra un target PDB. "
            "Corre en segundo plano y devuelve un task_id: NO trae el número "
            "todavía. Nunca inventes una afinidad; usá check_docking_status "
            "con ese task_id para leer el resultado cuando exista."
        ),
        parameters={
            "smiles": {"type": "string", "required": True},
            "target_pdb": {"type": "string", "required": False},
        },
        offline=True,
        category="docking",
        fn=run_docking,
    ))
    registry.register(ToolDef(
        name="check_docking_status",
        clase="dato_persistido",
        procedencia="corrida registrada en evaluation_runs de esta cuenta",
        description=(
            "Consulta una evaluación lanzada con run_docking por su task_id y "
            "devuelve su estado o, si terminó, la afinidad y los scores "
            "persistidos con su procedencia. Si sigue en curso o falló, lo dice "
            "y no hay número que citar."
        ),
        parameters={
            "task_id": {"type": "string", "required": True},
        },
        offline=True,
        category="docking",
        fn=check_docking_status,
    ))
    registry.register(ToolDef(
        name="get_rescoring",
        clase="inferencia",
        procedencia="XGBoost + GNN locales (predicción, no medida)",
        description="Predice afinidad de un SMILES usando XGBoost + GNN (rápido, ~1s).",
        parameters={
            "smiles": {"type": "string", "required": True},
            "target_pdb": {"type": "string", "required": False},
        },
        offline=True,
        category="docking",
        fn=get_rescoring,
    ))
