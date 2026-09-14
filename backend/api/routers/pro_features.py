"""
api/routers/pro_features.py

PRO mode endpoints: multi-target selectivity, MM-GBSA rescoring,
hardware-adaptive configuration.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import get_settings
from core.database import get_db
from core.models import UserORM
from db.repository import Repository
from api.dependencies import get_current_user_optional
from api.routers.evaluation_access import require_owned_molecule
from services.targets.access import (
    get_target_for_user,
    require_target_object_access,
    target_is_accessible,
)
from services.docking.selectivity import (
    run_selectivity_panel,
    seleccionar_anti_dianas,
    ANTI_TARGET_PANEL,
)
from services.docking.anti_target_sitio import (
    AntiDianaSinSitio,
    resolver_sitio_de_anti_diana,
)
from services.chemistry.mmgbsa_contrato import (
    MMGBSA_CONDICION,
    elementos_no_parametrizables,
    motivo_de_no_parametrizable,
)
from services.docking.selectividad_margen import (
    margen_de_selectividad,
    veredicto_de_margen,
)
from scoring.mmgbsa import is_gpu_available
from utils.file_handlers import StoragePath
from utils.local_storage import exists, read_text
from utils.logger import get_logger
from core.database import get_db_session

log = get_logger(__name__)
router = APIRouter(prefix="/pro", tags=["PRO Features"])
settings = get_settings()


@router.get("/anti-targets")
async def list_anti_targets(
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List available anti-targets: hardcoded defaults + user-uploaded from DB."""
    targets = [
        {
            "pdb_id": t["pdb_id"],
            "name": t["name"],
            "category": t.get("category", "Safety"),
            "risk": t.get("risk", ""),
            "threshold_kcal": t["affinity_threshold"],
            "source": "default",
        }
        for t in ANTI_TARGET_PANEL
    ]

    # Append DB-backed anti-targets
    try:
        repo = Repository(db)
        db_anti = await repo.get_anti_targets()
        for t in db_anti:
            if not target_is_accessible(t, current_user):
                continue
            targets.append({
                "pdb_id": t.pdb_id,
                "name": t.name,
                "category": "Custom",
                "risk": getattr(t, "anti_target_risk", None) or f"Target subido por el usuario: {t.name}",
                "threshold_kcal": t.affinity_threshold or -7.0,
                "source": "user",
            })
    except Exception as exc:  # noqa: BLE001 - degradacion declarada, no silencio
        # Degradar a solo el panel por defecto es aceptable: el usuario sigue
        # pudiendo evaluar. Hacerlo EN SILENCIO no lo es —vería menos
        # anti-targets de los que tiene y no sabría por qué—, y es la misma
        # familia de defecto que B1: un fallo que nadie registra no existe.
        log.warning(
            "anti_targets_de_usuario_no_listados",
            error=f"{type(exc).__name__}: {exc}",
            devueltos=len(targets),
        )

    return {"anti_targets": targets}


@router.post("/selectivity/{molecule_id}")
async def run_selectivity(
    molecule_id: str,
    num_workers: int = Query(2, ge=1, le=4, description="Parallel docking workers"),
    anti_targets: str | None = Query(None, description="Comma-separated anti-target PDB IDs"),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Run selectivity panel: dock the molecule against anti-targets
    to compute a safety profile.

    Uses configurable parallel workers to adapt to user's CPU.
    """
    from uuid import UUID

    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid molecule_id")

    repository = Repository(db)
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=mol_uuid,
        current_user=current_user,
        forbidden_detail="No tienes permiso para operar esta evaluación.",
        missing_detail="Evaluation not found",
    )
    evaluation = await repository.get_evaluation_result(mol_uuid)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    if evaluation.molecule is None:
        raise HTTPException(status_code=404, detail="Molecule data missing")

    smiles = evaluation.molecule.smiles
    smiles_hash = evaluation.molecule.smiles_hash
    target = (
        require_target_object_access(evaluation.molecule.target, current_user)
        if evaluation.molecule.target else None
    )
    target_pdb = target.pdb_id if target else "7E2Y"
    on_affinity = evaluation.affinity_kcal or 0.0

    anti_ids = anti_targets.split(",") if anti_targets else None
    for target_id in anti_ids or []:
        await get_target_for_user(
            repository, target_id, current_user, allow_missing=True
        )

    result = await run_selectivity_panel(
        smiles=smiles,
        smiles_hash=smiles_hash,
        on_target_pdb=target_pdb,
        on_target_affinity=on_affinity,
        num_workers=num_workers,
        anti_targets=anti_ids,
        # El panel resuelve `site_chains` de cada anti-diana contra el catálogo.
        # Sin el repositorio, hERG (5VA1) y NaV1.5 (6MVW) se preparaban con una
        # sola cadena teniendo el sitio declarado en dos y tres.
        repository=repository,
    )

    # Persistencia del panel. Aqui habia un tercer `except Exception: pass`
    # sobre la misma escritura -el mismo defecto B1 en un endpoint distinto-.
    from core.database import commit_with_retry

    persistido = False
    try:
        evaluation.selectivity_ratio = result.selectivity_ratio
        evaluation.selectivity_delta_delta_g = result.delta_delta_g_kcal
        evaluation.selectivity_ran = True
        # El veredicto sale de ΔΔG, no del cociente de energías libres. Ver
        # `services/docking/selectividad_margen.py`.
        evaluation.selectivity_verdict = veredicto_de_margen(result.delta_delta_g_kcal)
        evaluation.anti_target_results = result.off_targets
        await commit_with_retry(db)
        persistido = True
    except Exception as exc:  # noqa: BLE001 - se reporta, no se traga
        log.error(
            "selectividad_no_persistida",
            molecule_id=molecule_id,
            error=f"{type(exc).__name__}: {exc}",
        )

    return {
        "molecule_id": molecule_id,
        "persisted": persistido,
        "on_target": {
            "pdb_id": result.on_target_pdb,
            "affinity_kcal": result.on_target_affinity,
        },
        # `selectivity_ratio` viaja para no romper clientes antiguos, pero no
        # decide nada: ΔΔG es la magnitud con sentido físico.
        "selectivity_ratio": result.selectivity_ratio,
        "selectivity_delta_delta_g": result.delta_delta_g_kcal,
        "peor_anti_diana": result.peor_anti_diana,
        "selectivity_verdict": veredicto_de_margen(result.delta_delta_g_kcal),
        "off_targets": result.off_targets,
        "safety_flags": result.safety_flags,
        "execution_time_s": result.execution_time_s,
        # Cobertura: el cociente es un mínimo sobre lo que se llegó a evaluar.
        # Con anti-dianas sin sitio o desconocidas puede ser optimista, y sin
        # estos dos números el lector no tiene cómo saberlo.
        "anti_dianas_evaluadas": result.anti_dianas_evaluadas,
        "anti_dianas_solicitadas": result.anti_dianas_solicitadas,
    }


@router.post("/selectivity/stream/{molecule_id}")
async def run_selectivity_stream(
    molecule_id: str,
    num_workers: int = Query(2, ge=1, le=4, description="Parallel docking workers"),
    anti_targets: str | None = Query(None, description="Comma-separated anti-target PDB IDs"),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE Stream of selectivity calculations: docks anti-targets one by one (or in parallel)
    and emits real-time updates as each anti-target completes.
    """
    from uuid import UUID
    import json
    import time
    import asyncio

    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid molecule_id")

    repository = Repository(db)
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=mol_uuid,
        current_user=current_user,
        forbidden_detail="No tienes permiso para operar esta evaluación.",
        missing_detail="Evaluation not found",
    )
    evaluation = await repository.get_evaluation_result(mol_uuid)
    if evaluation is None or evaluation.molecule is None:
        raise HTTPException(status_code=404, detail="Evaluation or molecule missing")

    smiles = evaluation.molecule.smiles
    smiles_hash = evaluation.molecule.smiles_hash
    target = (
        require_target_object_access(evaluation.molecule.target, current_user)
        if evaluation.molecule.target else None
    )
    target_pdb = target.pdb_id if target else "7E2Y"
    on_affinity = evaluation.affinity_kcal or 0.0

    anti_ids = anti_targets.split(",") if anti_targets else None
    for target_id in anti_ids or []:
        await get_target_for_user(
            repository, target_id, current_user, allow_missing=True
        )
    # Misma selección que el panel no-stream: las anti-dianas del usuario se
    # resuelven contra el catálogo en vez de caerse del filtro en silencio.
    targets_list, anti_dianas_desconocidas = await seleccionar_anti_dianas(
        anti_ids, repository
    )

    async def event_generator():
        start_time = time.monotonic()
        # El total incluye las que no se van a poder evaluar: contando sólo las
        # acoplables, la barra llegaría al 100 % y el usuario creería que se
        # evaluó todo lo que pidió.
        total_targets = len(targets_list) + len(anti_dianas_desconocidas)

        yield f"data: {json.dumps({'type': 'start', 'total': total_targets})}\n\n"

        sem = asyncio.Semaphore(num_workers)
        off_target_results = []
        safety_flags = []
        worst_off_affinity = 0.0
        peor_anti_diana: str | None = None

        for pid in anti_dianas_desconocidas:
            no_evaluada = {
                "pdb_id": pid, "name": pid, "category": "Safety", "risk": "",
                "affinity": None, "poses": 0, "threshold": -7.0,
                "status": "desconocida",
                "error": "no está en el panel ni en el catálogo de este equipo",
            }
            off_target_results.append(no_evaluada)
            safety_flags.append(
                f"NO EVALUADA {pid}: se pidió como anti-diana y no está en este "
                f"equipo. El cociente de selectividad NO la incluye."
            )
            yield f"data: {json.dumps({'type': 'target', 'result': no_evaluada})}\n\n"

        from services.docking.vina_service import run_vina_docking

        for idx, at in enumerate(targets_list):
            pdb_id = at["pdb_id"]
            res = None
            # El sitio real del receptor, resuelto contra el catálogo. Ver
            # `services/docking/anti_target_sitio.py`.
            sitio = await resolver_sitio_de_anti_diana(at, repository)
            if isinstance(sitio, AntiDianaSinSitio):
                res = {
                    "pdb_id": pdb_id,
                    "name": at["name"],
                    "category": at.get("category", "Safety"),
                    "risk": at.get("risk", ""),
                    "affinity": None,
                    "poses": 0,
                    "threshold": at.get("affinity_threshold", -7.0),
                    "status": "sin_sitio",
                    "error": sitio.motivo,
                }
                off_target_results.append(res)
                yield f"data: {json.dumps({'type': 'target', 'index': idx, 'result': res})}\n\n"
                continue
            async with sem:
                try:
                    docking = await run_vina_docking(
                        smiles_hash=smiles_hash,
                        smiles=smiles,
                        target_pdb_id=pdb_id,
                        target_chain=sitio.chain,
                        target_center=sitio.center,
                        target_size=sitio.size,
                        site_chains=sitio.site_chains,
                    )
                    res = {
                        "pdb_id": pdb_id,
                        "name": at["name"],
                        "category": at.get("category", "Safety"),
                        "risk": at.get("risk", ""),
                        "affinity": docking.best_affinity if docking else None,
                        "poses": len(docking.poses) if docking and docking.poses else 0,
                        "threshold": at["affinity_threshold"],
                        "status": "ok",
                    }
                except Exception as e:
                    error_msg = str(e)[:200]
                    status_str = "failed"
                    reason = error_msg
                    if "VinaExecutable" in str(type(e).__name__) or "vina" in error_msg.lower():
                        status_str = "no_vina"
                        reason = "Vina no encontrado"
                    elif "timeout" in error_msg.lower():
                        status_str = "timeout"
                        reason = "Timeout -- docking excedió el tiempo límite"

                    res = {
                        "pdb_id": pdb_id,
                        "name": at["name"],
                        "category": at.get("category", "Safety"),
                        "risk": at.get("risk", ""),
                        "affinity": None,
                        "poses": 0,
                        "threshold": at["affinity_threshold"],
                        "status": status_str,
                        "error": reason,
                    }

            off_target_results.append(res)

            # Safety metrics check for this target
            aff = res.get("affinity")
            threshold = res.get("threshold", -7.0)
            if aff is not None:
                if aff < threshold:
                    safety_flags.append(
                        f"ALERTA {res['name']}: afinidad {aff:.1f} kcal/mol < umbral {threshold:.1f}. "
                        f"Riesgo: {res.get('risk', 'Desconocido')}"
                    )
                if aff < worst_off_affinity:
                    worst_off_affinity = aff
                    peor_anti_diana = res.get("name") or res.get("pdb_id")
            else:
                safety_flags.append(f"Sin datos para {res['name']} -- no se pudo evaluar")

            # Stream individual progress event
            chunk_data = {
                "type": "anti_target",
                "anti_target": res,
                "completed": idx + 1,
                "total": total_targets,
            }
            yield f"data: {json.dumps(chunk_data)}\n\n"

        # Calculate final metrics
        # Misma métrica que el panel no-stream: ΔΔG en kcal/mol. Antes esta
        # ruta repetía el cociente ΔG_on/ΔG_off por su cuenta.
        margen = margen_de_selectividad(
            on_affinity, worst_off_affinity if worst_off_affinity < 0 else None, peor_anti_diana
        )
        delta_delta_g = margen.delta_delta_g if margen else None

        selectivity_ratio = None
        if on_affinity is not None and worst_off_affinity < 0:
            selectivity_ratio = round(on_affinity / worst_off_affinity, 2)

        verdict_str = veredicto_de_margen(delta_delta_g)
        elapsed = time.monotonic() - start_time

        # ── Persistencia del resultado de selectividad ──────────────────────
        #
        # DOC 71, DEFECTOS B1 y B2. Aqui habia un `except Exception: pass`
        # alrededor de la UNICA escritura de este resultado. Si el commit
        # fallaba -y con SQLite, escribir desde una segunda sesion mientras la
        # respuesta esta en streaming es justo cuando falla- el flujo seguia
        # emitiendo `done` con los numeros, la interfaz los pintaba, y la base
        # no se enteraba nunca.
        #
        # De ahi salen los dos defectos que el informe listo por separado:
        #   B1  el dossier lee `selectivity_ran = False` y declara "la corrida no
        #       registro un panel de anti-targets", que desde su punto de vista
        #       es literalmente cierto;
        #   B2  el resultado solo vive en el estado del componente, asi que
        #       desaparece al cambiar de pestana.
        #
        # Son la misma causa vista desde dos sitios, como sospechaba el doc 71.
        #
        # Ahora se reintenta con `commit_with_retry` -lo que usa el pipeline para
        # exactamente este bloqueo de SQLite-, se registra el fallo, y sobre todo
        # SE LE DICE AL CLIENTE: un resultado que no se pudo guardar no puede
        # presentarse como si lo estuviera.
        persistido = False
        error_al_guardar = None
        try:
            from core.database import commit_with_retry, get_db_session
            async with get_db_session() as db2:
                repo2 = Repository(db2)
                eval_to_update = await repo2.get_evaluation_result(mol_uuid)
                if eval_to_update:
                    eval_to_update.selectivity_ratio = selectivity_ratio
                    eval_to_update.selectivity_delta_delta_g = delta_delta_g
                    eval_to_update.selectivity_ran = True
                    eval_to_update.selectivity_verdict = verdict_str
                    eval_to_update.anti_target_results = off_target_results
                    await commit_with_retry(db2)
                    persistido = True
                else:
                    error_al_guardar = "la evaluacion ya no existe"
        except Exception as exc:  # noqa: BLE001 - se reporta, no se traga
            error_al_guardar = f"{type(exc).__name__}: {exc}"
            log.error(
                "selectividad_no_persistida",
                molecule_id=str(mol_uuid),
                anti_targets=len(off_target_results),
                error=error_al_guardar,
            )

        final_data = {
            "type": "done",
            "selectivity_ratio": selectivity_ratio,
            "selectivity_delta_delta_g": delta_delta_g,
            "peor_anti_diana": peor_anti_diana,
            "selectivity_verdict": verdict_str,
            "off_targets": off_target_results,
            "safety_flags": safety_flags,
            "execution_time_s": round(elapsed, 1),
            # El cliente necesita saberlo para no prometer permanencia.
            "persisted": persistido,
            "persist_error": error_al_guardar,
        }
        yield f"data: {json.dumps(final_data)}\n\n"

    from starlette.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")


async def _persistir_anti_target(db, evaluation, resultado: dict) -> bool:
    """Escribe UN anti-target en la evaluacion, fusionando con los que ya estan.

    # Por que persiste el servidor y no el cliente

    DOC 71, B2. El panel de selectividad guardaba desde el navegador: el
    endpoint que hacia el docking devolvia el resultado y se desentendia. Si el
    usuario cerraba la pestana, cambiaba de vista o se le caia la conexion entre
    un anti-target y el siguiente, ese docking -que ya se habia PAGADO en CPU-
    se perdia sin dejar rastro.

    Quien hace el trabajo es quien lo guarda. Asi el resultado sobrevive aunque
    el cliente desaparezca a mitad de la tanda, que es exactamente lo que pasa
    al cambiar de pestana en un panel que se desmonta.

    La fusion es por `pdb_id` para que reacoplar un objetivo lo actualice en vez
    de duplicarlo, y para que dos escrituras concurrentes no se pisen.
    """
    from core.database import commit_with_retry

    if not isinstance(resultado, dict) or not resultado.get("pdb_id"):
        return False

    previos = {
        r.get("pdb_id"): r
        for r in (evaluation.anti_target_results or [])
        if isinstance(r, dict) and r.get("pdb_id")
    }
    previos[resultado["pdb_id"]] = resultado
    evaluation.anti_target_results = list(previos.values())
    evaluation.selectivity_ran = True

    try:
        await commit_with_retry(db)
        return True
    except Exception as exc:  # noqa: BLE001 - se reporta, no se traga
        log.error(
            "anti_target_no_persistido",
            molecule_id=str(getattr(evaluation, "molecule_id", "")),
            pdb_id=resultado.get("pdb_id"),
            error=f"{type(exc).__name__}: {exc}",
        )
        return False


@router.post("/selectivity/dock-target/{molecule_id}")
async def dock_single_anti_target(
    molecule_id: str,
    target_pdb_id: str = Query(..., description="Anti-target PDB ID"),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Dock molecule against a single anti-target for progressive modal updates.
    """
    from uuid import UUID
    from services.docking.vina_service import run_vina_docking

    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid molecule_id")

    repository = Repository(db)
    await get_target_for_user(
        repository, target_pdb_id, current_user, allow_missing=True
    )
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=mol_uuid,
        current_user=current_user,
        forbidden_detail="No tienes permiso para operar esta evaluación.",
        missing_detail="Evaluation or molecule missing",
    )
    evaluation = await repository.get_evaluation_result(mol_uuid)
    if evaluation is None or evaluation.molecule is None:
        raise HTTPException(status_code=404, detail="Evaluation or molecule missing")

    smiles = evaluation.molecule.smiles
    smiles_hash = evaluation.molecule.smiles_hash

    # Find anti-target config
    at = next((t for t in ANTI_TARGET_PANEL if t["pdb_id"] == target_pdb_id), None)
    if at is None:
        # SIN caja inventada. Aquí había `center=(0,0,0)` y `size=20³` para
        # cualquier receptor desconocido: eso acopla contra el ORIGEN del
        # sistema de coordenadas —espacio vacío en casi cualquier PDB— y
        # devuelve la afinidad resultante como un dato de seguridad. El
        # resolvedor toma la caja del catálogo y, si no hay ninguna calibrada,
        # se abstiene.
        at = {
            "pdb_id": target_pdb_id,
            "name": f"Target {target_pdb_id}",
            "category": "Custom",
            "risk": "Anti-diana no estándar",
            "affinity_threshold": -7.0,
        }

    sitio = await resolver_sitio_de_anti_diana(at, repository)
    if isinstance(sitio, AntiDianaSinSitio):
        raise HTTPException(
            status_code=422,
            detail=(
                f"No se puede evaluar {target_pdb_id} como anti-diana: {sitio.motivo}"
            ),
        )

    try:
        docking = await run_vina_docking(
            smiles_hash=smiles_hash,
            smiles=smiles,
            target_pdb_id=target_pdb_id,
            target_chain=sitio.chain,
            target_center=sitio.center,
            target_size=sitio.size,
            site_chains=sitio.site_chains,
        )
        res = {
            "pdb_id": target_pdb_id,
            "name": at["name"],
            "category": at.get("category", "Safety"),
            "risk": at.get("risk", ""),
            "affinity": docking.best_affinity if docking else None,
            "poses": len(docking.poses) if docking and docking.poses else 0,
            "threshold": at["affinity_threshold"],
            "status": "ok",
        }
    except Exception as e:
        error_msg = str(e)[:200]
        status_str = "failed"
        reason = error_msg
        if "VinaExecutable" in str(type(e).__name__) or "vina" in error_msg.lower():
            status_str = "no_vina"
            reason = "Vina no encontrado"
        elif "timeout" in error_msg.lower():
            status_str = "timeout"
            reason = "Timeout -- docking excedió tiempo límite"

        # El fallo NO se traga: se convierte en el resultado del anti-target,
        # con su motivo, y se persiste igual que un exito. Un objetivo que no
        # se pudo acoplar es informacion -el panel lo muestra en rojo- y no un
        # hueco que el usuario deba interpretar.
        #
        # Se registra ademas en el servidor: un fallo de Vina que solo ve el
        # navegador no aparece en `backend.latest.log`, y es justo lo que hace
        # falta para diagnosticar por que un panel sale incompleto.
        log.warning(
            "anti_target_fallido",
            molecule_id=molecule_id,
            pdb_id=target_pdb_id,
            estado=status_str,
            motivo=reason,
        )
        res = {
            "pdb_id": target_pdb_id,
            "name": at["name"],
            "category": at.get("category", "Safety"),
            "risk": at.get("risk", ""),
            "affinity": None,
            "poses": 0,
            "threshold": at["affinity_threshold"],
            "status": status_str,
            "error": reason,
        }

    # El trabajo ya esta hecho: se guarda aqui, no cuando al navegador le
    # parezca. Si esto falla, el cliente se entera por `persisted` y puede
    # reintentar; lo que no puede es creer que quedo guardado.
    persistido = await _persistir_anti_target(db, evaluation, res)
    return {"target": res, "persisted": persistido}


from pydantic import BaseModel, Field


class SaveSelectivityRequest(BaseModel):
    off_targets: list[dict]
    selectivity_ratio: float | None = None
    selectivity_delta_delta_g: float | None = None
    selectivity_verdict: str | None = None
    safety_flags: list[str] = Field(default_factory=list)


@router.post("/selectivity/save/{molecule_id}")
async def save_selectivity_results_endpoint(
    molecule_id: str,
    payload: SaveSelectivityRequest,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    from uuid import UUID
    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid molecule_id")

    repository = Repository(db)
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=mol_uuid,
        current_user=current_user,
        forbidden_detail="No tienes permiso para modificar esta evaluación.",
        missing_detail="Evaluation not found",
    )
    evaluation = await repository.get_evaluation_result(mol_uuid)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    # ── El panel se guarda POR ANTI-TARGET, segun van saliendo ──────────────
    #
    # DOC 71, DEFECTO B2. El panel de selectividad se desmonta al cambiar de
    # pestana, asi que su estado en memoria muere. La unica forma de que el
    # resultado sobreviva es que cada anti-target este ya escrito cuando eso
    # ocurre, y que al volver se lea de la base y no de la memoria.
    #
    # Por eso este endpoint FUSIONA en vez de reemplazar. El cliente manda la
    # lista acumulada tras cada docking, pero dos guardados pueden llegar
    # desordenados -o uno tardio traer menos objetivos que otro ya escrito- y
    # reemplazar a ciegas perderia trabajo ya hecho. La clave de fusion es el
    # `pdb_id`; gana el ultimo que llega para ese objetivo.
    previos = {
        r.get("pdb_id"): r
        for r in (evaluation.anti_target_results or [])
        if isinstance(r, dict) and r.get("pdb_id")
    }
    for r in payload.off_targets:
        if isinstance(r, dict) and r.get("pdb_id"):
            previos[r["pdb_id"]] = r
    fusionados = list(previos.values())

    evaluation.selectivity_ratio = payload.selectivity_ratio
    evaluation.selectivity_delta_delta_g = payload.selectivity_delta_delta_g
    evaluation.selectivity_ran = True
    # Sin ΔΔG no se inventa un veredicto a partir del cociente: se declara que
    # no hay datos suficientes. Derivarlo del cociente sería seguir usando la
    # magnitud equivocada por la puerta de atrás.
    evaluation.selectivity_verdict = (
        payload.selectivity_verdict
        or veredicto_de_margen(payload.selectivity_delta_delta_g)
    )
    evaluation.anti_target_results = fusionados

    # `commit_with_retry` y no `commit`: es la misma contencion de SQLite que ya
    # obligo al pipeline a usarlo. Un fallo aqui borraba el unico rastro del
    # panel, y el dossier declaraba despues que nunca se corrio.
    from core.database import commit_with_retry

    await commit_with_retry(db)

    log.info(
        "selectividad_guardada",
        molecule_id=molecule_id,
        recibidos=len(payload.off_targets),
        total_persistido=len(fusionados),
    )
    return {
        "success": True,
        "molecule_id": molecule_id,
        # El cliente necesita saber cuantos hay GUARDADOS, no cuantos mando.
        "anti_targets_persistidos": len(fusionados),
    }


@router.post("/mmgbsa/{molecule_id}")
async def run_mmgbsa_endpoint(
    molecule_id: str,
    pose_rank: int = Query(1, ge=1, le=5, description="Which pose to rescore (1=best)"),
    num_steps: int = Query(1000, ge=500, le=5000, description="Minimization steps"),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Run MM-GBSA binding free energy calculation on a docked pose.

    Uses OpenMM with GPU auto-detection (CUDA > OpenCL > CPU).
    """
    from uuid import UUID

    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid molecule_id")

    repository = Repository(db)
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=mol_uuid,
        current_user=current_user,
        forbidden_detail="No tienes permiso para operar esta evaluación.",
        missing_detail="Evaluation not found",
    )
    evaluation = await repository.get_evaluation_result(mol_uuid)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")

    if evaluation.molecule is None or evaluation.molecule.target is None:
        raise HTTPException(status_code=404, detail="Molecule or target missing")

    target = require_target_object_access(evaluation.molecule.target, current_user)
    smiles_hash = evaluation.molecule.smiles_hash

    # ── ¿Se puede parametrizar este ligando? Se pregunta ANTES ───────────
    #
    # `molchamb_v2` ya rechazaba todo lo que no fuera C/H/O/N/S/P, pero lo hacía
    # después de preparar el receptor, generar la pose y construir el sistema
    # OpenMM — minutos de trabajo— y devolvía `Unsupported elements: {'Cl'}`
    # por la vía de un fallo genérico. En química médica los halógenos no son
    # un caso raro, así que ese camino no era la excepción: era la norma para
    # una fracción grande de las moléculas que la gente evalúa.
    #
    # Preguntar primero cuesta un parseo de SMILES y convierte un fallo opaco
    # de tres minutos en una frase inmediata que explica la causa.
    no_parametrizables = elementos_no_parametrizables(evaluation.molecule.smiles)
    if no_parametrizables:
        log.info(
            "mmgbsa_no_parametrizable",
            molecule_id=molecule_id,
            elementos=sorted(no_parametrizables),
        )
        raise HTTPException(
            status_code=422,
            detail=motivo_de_no_parametrizable(no_parametrizables),
        )

    # ── Get protein PDB ──────────────────────────────────────────
    protein_pdb = None
    try:
        prepared_path = StoragePath.target_prepared(target.pdb_id)
        if await exists(prepared_path):
            protein_pdb = await read_text(prepared_path)
        else:
            raw_path = StoragePath.target_raw(target.pdb_id)
            if await exists(raw_path):
                protein_pdb = await read_text(raw_path)
    except Exception as e:
        log.warning("storage_protein_not_found", error=str(e))

    # Fallback to local target_library directory
    if protein_pdb is None:
        target_lib = Path("data/target_library")
        if target_lib.exists():
            for pfile in target_lib.glob(f"**/{target.pdb_id}.pdb"):
                try:
                    protein_pdb = pfile.read_text(encoding="utf-8", errors="ignore")
                    break
                except Exception:
                    pass

    if protein_pdb is None:
        # Fallback 2: search data/targets
        local_target = Path(f"data/targets/{target.pdb_id}.pdb")
        if local_target.exists():
            try:
                protein_pdb = local_target.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass

    if protein_pdb is None:
        raise HTTPException(status_code=503, detail=f"Estructura PDB del receptor {target.pdb_id} no disponible")

    # ── Get ligand SDF ───────────────────────────────────────────
    sdf_content = None
    try:
        poses_path = StoragePath.docking_poses(smiles_hash, target.pdb_id)
        if await exists(poses_path):
            sdf_content = await read_text(poses_path)
    except Exception:
        pass

    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = None
    if sdf_content:
        supplier = Chem.SDMolSupplier()
        supplier.SetData(sdf_content)
        mols = [m for m in supplier if m is not None]
        if mols and pose_rank <= len(mols):
            mol = mols[pose_rank - 1]

    if mol is None:
        # Generate on-the-fly 3D conformer SDF if docked pose SDF not in storage
        m = Chem.MolFromSmiles(evaluation.molecule.smiles)
        if m:
            m = Chem.AddHs(m)
            status_embed = AllChem.EmbedMolecule(m, AllChem.ETKDG())
            if status_embed != -1:
                AllChem.MMFFOptimizeMolecule(m)
                mol = m

    if mol is None:
        raise HTTPException(status_code=503, detail="No se pudo generar ni obtener la pose 3D del ligando para MM-GBSA")

    # ── FIX MM-GBSA (2026-08-04, -11351 kcal/mol): usar la pose REAL y el
    # ΔG de unión correcto (g_complex - g_protein - g_ligand), NO run_mmgbsa
    # de scoring/mmgbsa.py que era protein-only y reportaba la energía total
    # del complejo como si fuera ΔG (por eso salían valores absurdos de miles
    # de kcal/mol). compute_mmgbsa_from_pose (molchamb_v2.py) coloca el
    # ligando en la pose dockeada real y resta proteína/ligando aislados.
    # Ver docs/36 UI-2 BUG-2 + SC-10.
    tmp_dir: Path | None = None
    try:
        from services.chemistry.molchamb_v2 import compute_mmgbsa_from_pose

        # Extraer coordenadas (x,y,z) de la pose seleccionada del SDF
        conf = mol.GetConformer()
        if conf is None:
            raise ValueError("Conformer no disponible en la pose")
        pose_coords = [
            (float(conf.GetAtomPosition(i).x),
             float(conf.GetAtomPosition(i).y),
             float(conf.GetAtomPosition(i).z))
            for i in range(mol.GetNumAtoms())
        ]

        # Guardar el PDB de proteína en temp para compute_mmgbsa_from_pose
        import tempfile
        tmp_dir = Path(tempfile.mkdtemp())
        protein_path = tmp_dir / "protein.pdb"
        protein_path.write_text(protein_pdb, encoding="utf-8")

        # FIX NaN (2026-08-04): guardar el SDF del pose y pasarlo como
        # ligand_sdf_path para que compute_mmgbsa_from_pose construya la
        # topología DESDE el SDF (conformador real de Vina) y agregue H con
        # coordenadas (addCoords=True). Sin esto, los H sin coordenadas caían
        # todos en la última posición del pose → colapso → NaN.
        ligand_sdf_tmp = tmp_dir / "pose.sdf"
        try:
            writer = Chem.SDWriter(str(ligand_sdf_tmp))
            writer.write(mol)
            writer.close()
        except Exception:
            ligand_sdf_tmp = None

        # ── FUERA DEL BUCLE DE EVENTOS ──────────────────────────────────────
        #
        # `compute_mmgbsa_from_pose` minimiza con OpenMM: entre decenas de
        # segundos y varios minutos, todo dentro de una llamada síncrona. Este
        # endpoint es `async def`, así que la llamada corría EN el bucle de
        # eventos y lo dejaba parado todo ese tiempo: mientras el usuario
        # esperaba su MM-GBSA, el backend no contestaba absolutamente nada más
        # —ni el sondeo del trabajo cada 2 s, ni `/health`, ni el dossier—.
        # La interfaz lo enseñaba como una aplicación colgada, y el fallo real
        # quedaba tapado detrás de eso.
        #
        # `anyio.to_thread` es el mismo mecanismo que usa FastAPI para los
        # endpoints `def`; aquí sólo se aplica a la parte cara.
        from anyio.to_thread import run_sync

        result = await run_sync(
            functools.partial(
                compute_mmgbsa_from_pose,
                str(protein_path),
                evaluation.molecule.smiles,
                pose_coords,
                max_iter=num_steps,
                ligand_sdf_path=(
                    str(ligand_sdf_tmp) if ligand_sdf_tmp and ligand_sdf_tmp.exists() else None
                ),
            ),
        )

        mmgbsa_total = result.get("mmgbsa")
        if mmgbsa_total is None:
            # Fallback: si no convergió o falló, devolver error claro en vez de
            # un valor absurdo. El frontend muestra el error en el modal.
            raise HTTPException(
                status_code=422,
                detail=f"MM-GBSA no produjo ΔG válido: {result.get('error', 'sin convergencia')}",
            )

        # ── Se guarda, porque costo minutos de minimizacion ─────────────────
        #
        # Este endpoint calculaba y devolvia SIN PERSISTIR. El valor vivia solo
        # en el estado del componente, asi que recargar la pagina o volver a la
        # evaluacion desde el historial lo borraba, y habia que repetir mil
        # pasos de minimizacion. Peor: el dossier lee `mmgbsa_score` del ORM, de
        # modo que el informe declaraba «no calculado» un MM-GBSA que el usuario
        # habia visto en pantalla.
        #
        # Es el mismo defecto que B1/B2 sobre una operacion mas cara. Quien hace
        # el trabajo es quien lo guarda.
        from core.database import commit_with_retry

        persistido = False
        try:
            evaluation.mmgbsa_score = round(mmgbsa_total, 3)
            await commit_with_retry(db)
            persistido = True
        except Exception as exc:  # noqa: BLE001 - se reporta, no se traga
            log.error(
                "mmgbsa_no_persistido",
                molecule_id=molecule_id,
                error=f"{type(exc).__name__}: {exc}",
            )

        # Descomposición física real (vdW + electrostática + GB + SASA) no está
        # en compute_mmgbsa_from_pose; estimar componentes del g_complex no es
        # correcto. Devolvemos el ΔG total + el breakdown de g_complex/g_protein
        # para que el frontend no invente descomposiciones falsas.
        return {
            "molecule_id": molecule_id,
            "persisted": persistido,
            "pose_rank": pose_rank,
            "delta_g_total_kcal": round(mmgbsa_total, 3),
            "delta_g_vdw": None,
            "delta_g_electrostatic": None,
            "delta_g_gb_polar": None,
            "delta_g_nonpolar_sasa": None,
            "components": {
                "g_complex": result.get("g_complex"),
                "g_protein": result.get("g_protein"),
                "g_ligand": result.get("g_ligand"),
                "delta_g": round(mmgbsa_total, 3),
            },
            "minimized": True,
            "platform": result.get("platform", "CPU"),
            "execution_time_s": result.get("time_sec"),
            "warnings": [],
            # `condicion_de_validez` no es una nota al pie: es la mitad del
            # dato. Viaja al modal, al DOT y al dossier junto al ΔG.
            "condicion_de_validez": MMGBSA_CONDICION,
            "note": "ΔG = g_complex - g_protein - g_ligand (pose real de docking). "
                    "La descomposición por contribución requiere MM-GBSA por residuo "
                    "(no disponible en este endpoint).",
        }
    except HTTPException:
        raise
    except Exception as e:
        log.warning("mmgbsa_from_pose_failed", error=str(e)[:300])
        raise HTTPException(status_code=500, detail=f"MM-GBSA falló: {str(e)[:200]}")
    finally:
        # `tmp_dir` puede seguir siendo None: el fallo pudo ocurrir antes de
        # crearlo (import, conformador ausente). Se comprueba en vez de confiar
        # en que el `except` de abajo atrape el NameError, que era lo que hacía.
        if tmp_dir is not None:
            import shutil

            shutil.rmtree(tmp_dir, ignore_errors=True)


@router.get("/gpu")
async def gpu_status() -> dict[str, Any]:
    """Check GPU availability for acceleration features."""
    return {
        "openmm_gpu": is_gpu_available(),
        "torch_cuda": _check_torch_cuda(),
        "platforms": _get_openmm_platforms(),
    }


def _check_torch_cuda() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def _get_openmm_platforms() -> list[str]:
    try:
        import openmm
        return [
            openmm.Platform.getPlatform(i).getName()
            for i in range(openmm.Platform.getNumPlatforms())
        ]
    except ImportError:
        return []


# ═══════════════════════════════════════════════════════════════════════════
# ADMET-AI POST-DOCKING
# ═══════════════════════════════════════════════════════════════════════════
#
# POR QUE EXISTE. ADMET-AI es opt-in en las opciones avanzadas, y esa decision
# se toma ANTES de ejecutar. Quien no lo marco se quedaba sin perfil ADMET para
# siempre: la unica forma de tenerlo era volver a acoplar la molecula entera
# —minutos de Vina— para recalcular algo que solo depende del SMILES.
#
# Este endpoint es el mismo trato que ya tiene MM-GBSA: un modulo caro que se
# pide despues, sobre una corrida que ya existe, y que se PERSISTE porque quien
# hace el trabajo es quien lo guarda.
#
# TRES COSAS QUE PROTEGE:
#
# 1. **El mismo calculo que el pipeline.** Llama a `calculate_properties(...,
#    run_admet_ai=True)` y persiste con `Repository.upsert_evaluation_result`,
#    que es el mapeo canonico. Escribir las columnas a mano aqui crearia una
#    segunda copia del mapeo, y dos copias divergen —es exactamente el defecto
#    que costo doce minutos de build en el gate del dossier embebido—.
#
# 2. **No inventa un perfil.** Si ADMET-AI no esta disponible, `predict_admet_ai`
#    devuelve `None` en vez de valores simulados y el indice sale `None`. Aqui se
#    comprueba DESPUES de correr: si no hay indice, se responde que no se pudo
#    evaluar en vez de declarar exito sobre un perfil vacio.
#
# 3. **No pisa el docking ni la marca de control.** `upsert_evaluation_result`
#    solo escribe lo que recibe, asi que la evidencia de acoplamiento sigue
#    intacta; pero `is_control` SI se escribe siempre, y por eso se le reenvia
#    el valor que ya tenia el registro. Sin eso, calcular ADMET sobre un control
#    lo convertiria en una molecula normal.


@router.post(
    "/admet/{molecule_id}",
    summary="Perfil ADMET de una molecula ya evaluada, calculado despues del acoplamiento",
)
async def run_admet_endpoint(
    molecule_id: str,
    recalcular: bool = Query(
        False,
        description=(
            "Vuelve a calcularlo aunque ya haya un perfil guardado. Por omision "
            "se devuelve el que hay: el modelo tarda y el resultado es el mismo."
        ),
    ),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Calcula el perfil ADMET de una molecula ya evaluada, y lo guarda."""
    from uuid import UUID

    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid molecule_id")

    repository = Repository(db)
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=mol_uuid,
        current_user=current_user,
        forbidden_detail="No tienes permiso para operar esta evaluacion.",
        missing_detail="Evaluation not found",
    )
    evaluation = await repository.get_evaluation_result(mol_uuid)
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    if evaluation.molecule is None:
        raise HTTPException(status_code=404, detail="Molecule missing")

    smiles = evaluation.molecule.smiles

    def _perfil(origen: Any) -> dict[str, Any]:
        """Lo que la interfaz necesita, leido de una sola fuente."""
        return {
            "blood_viability_score": getattr(origen, "blood_viability_score", None),
            "blood_solubility_logs": getattr(origen, "blood_solubility_logs", None),
            "blood_ppb_category": getattr(origen, "blood_ppb_category", None),
            "blood_bbb_permeable": getattr(origen, "blood_bbb_permeable", None),
            "blood_bbb_motivo": getattr(origen, "blood_bbb_motivo", None),
            "blood_cns_mpo": getattr(origen, "blood_cns_mpo", None),
            "blood_hia_permeable": getattr(origen, "blood_hia_permeable", None),
            "blood_systemic_reactivity": list(
                getattr(origen, "blood_systemic_reactivity", None) or []
            ),
            "blood_tabpfn_estado": getattr(origen, "blood_tabpfn_estado", None),
        }

    # Ya calculado: se devuelve tal cual. Repetirlo costaria la carga del modelo
    # para obtener el mismo numero, y en una maquina virtual eso son minutos.
    if not recalcular and evaluation.blood_viability_score is not None:
        return {
            "molecule_id": molecule_id,
            "estado": "ya_calculado",
            "persistido": True,
            **_perfil(evaluation),
        }

    # ── FUERA DEL BUCLE DE EVENTOS ──────────────────────────────────────────
    #
    # La primera prediccion carga el ensamble de Chemprop y domina el reloj de
    # la llamada. Este endpoint es `async def`: correrlo aqui dejaria el backend
    # sin contestar nada mas mientras dura —ni el sondeo de la corrida, ni
    # `/health`—, que es el mismo defecto que ya se corrigio en MM-GBSA.
    from anyio.to_thread import run_sync

    from chem.properties import calculate_properties

    try:
        props = await run_sync(
            functools.partial(calculate_properties, smiles, run_admet_ai=True)
        )
    except Exception as exc:  # noqa: BLE001 - se reporta, no se traga
        log.error(
            "admet_post_docking_fallo",
            molecule_id=molecule_id,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise HTTPException(
            status_code=422,
            detail=f"El perfil ADMET no se pudo calcular ({type(exc).__name__}).",
        )

    # NO se declara exito sobre un perfil vacio. `predict_admet_ai` devuelve
    # `None` cuando el modelo no esta disponible —a proposito, para que nadie
    # confunda un hueco con un valor—, y eso llega aqui como indice nulo.
    if props.blood_viability_score is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "ADMET-AI no esta disponible en esta instalacion, asi que no hay "
                "perfil que calcular. No se devuelve un perfil vacio como si lo "
                "fuera."
            ),
        )

    persistido = False
    try:
        # El mapeo canonico, el mismo que usa el pipeline. `is_control` se
        # reenvia porque `upsert_evaluation_result` lo escribe SIEMPRE y su
        # valor por omision convertiria un control en molecula normal.
        await repository.upsert_evaluation_result(
            molecule_id=mol_uuid,
            properties=props,
            is_control=bool(evaluation.is_control),
        )
        from core.database import commit_with_retry

        await commit_with_retry(db)
        persistido = True
    except Exception as exc:  # noqa: BLE001 - se reporta, no se traga
        log.error(
            "admet_post_docking_no_persistido",
            molecule_id=molecule_id,
            error=f"{type(exc).__name__}: {exc}",
        )

    log.info("admet_post_docking", molecule_id=molecule_id, persistido=persistido)
    return {
        "molecule_id": molecule_id,
        "estado": "calculado",
        # Se dice si quedo guardado. Un perfil que el usuario ve pero que el
        # dossier no leera es peor que uno que no se calculo.
        "persistido": persistido,
        **_perfil(props),
    }
