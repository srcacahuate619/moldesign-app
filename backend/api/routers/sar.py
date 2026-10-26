"""
api/routers/sar.py

Structure-Activity Relationship (SAR) analysis.
Dada una molecula base, retorna todos los analogos evaluados
contra el mismo target, ordenados por score con delta vs baseline.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette.concurrency import run_in_threadpool

from core.database import get_db
from core.models import MoleculeORM, UserORM
from api.dependencies import get_current_user_optional
from api.routers.evaluation_access import require_owned_molecule
from db.repository import Repository
from services.sar.comparabilidad import (
    Comparabilidad,
    comparar_corridas,
    condicion_quimica_publica,
)
from services.targets.access import require_target_object_access
from utils.instantes import instante_utc
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(prefix="/sar", tags=["SAR Analysis"])


def _finite_number(value: Any) -> float | None:
    """Normaliza métricas opcionales sin convertir ausencia en evidencia cero."""

    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _difference(value: Any, baseline: Any, *, digits: int) -> float | None:
    current = _finite_number(value)
    reference = _finite_number(baseline)
    if current is None or reference is None:
        return None
    return round(current - reference, digits)


def _best_available(values: list[Any], *, lower_is_better: bool = False) -> float | None:
    available = [number for value in values if (number := _finite_number(value)) is not None]
    if not available:
        return None
    return min(available) if lower_is_better else max(available)


def _first_available(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _huella_morgan(molecule: Any) -> Any:
    """Huella circular Morgan r=2, 1024 bits — equivalente a ECFP4.

    POR QUÉ SE CAMBIÓ. Antes se usaba `RDKFingerprint`, que enumera CAMINOS
    topológicos lineales (estilo Daylight). Es una huella legítima, pero para
    una tabla de relación estructura-actividad es la herramienta equivocada:
    una serie congenérica se diferencia por sustituyentes colgados de un
    andamio común, y lo que hay que comparar son los ENTORNOS CIRCULARES de
    cada átomo, no los caminos que los atraviesan. Con caminos, dos análogos
    que sólo difieren en un sustituyente comparten casi todos los caminos del
    andamio y la similitud se satura hacia arriba: la columna deja de
    discriminar justo entre las moléculas que el usuario está comparando.

    Morgan r=2 / 1024 bits (ECFP4) es la convención de facto en química médica
    para exactamente este uso.

    El radio y el número de bits van explícitos y no por defecto: cambiar
    cualquiera de los dos cambia todas las similitudes de la tabla, y debe ser
    una decisión visible.
    """
    from rdkit.Chem import rdFingerprintGenerator

    generador = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=1024)
    return generador.GetFingerprint(molecule)


def _tanimoto_similarity(base_fp: Any, smiles: str | None) -> float | None:
    """Devuelve similitud calculada o ``None``; un fallo nunca significa 100 %."""

    if base_fp is None or not smiles:
        return None
    try:
        from rdkit import Chem, DataStructs

        molecule = Chem.MolFromSmiles(smiles)
        if molecule is None:
            return None
        return round(
            float(DataStructs.TanimotoSimilarity(base_fp, _huella_morgan(molecule))), 3
        )
    except Exception:
        return None


#: Tope de una cohorte explícita. Cada corrida es una lectura de snapshot y una
#: huella Morgan: más de esto ya no es una tabla que alguien lea.
MAX_COHORTE_EXPLICITA = 200


async def _evaluacion_de_corrida(
    *,
    repository: Repository,
    db: AsyncSession,
    task_id: str,
    molecule_id: Any | None,
    current_user: UserORM | None,
) -> SimpleNamespace:
    """La evaluación que ESA corrida produjo, no la proyección más reciente.

    CAS-02. `evaluation_results` guarda la última evaluación de cada molécula;
    cuando el mismo ligando se reevalúa con otro protocolo, la proyección cambia
    y una tabla SAR construida sobre ella deja de describir las corridas
    originales. El snapshot inmutable de `evaluation_runs` sí conserva lo que
    cada `task_id` produjo (con las addenda verificadas, igual que el dossier).

    Una corrida ajena, desconocida o que no terminó NO se sustituye por otra: se
    rechaza nombrándola. Una cohorte explícita se cumple entera o se declara.
    """
    corrida = await repository.get_evaluation_run(task_id, molecule_id)
    if corrida is None:
        raise HTTPException(
            status_code=404,
            detail=f"La corrida {task_id} no existe o no pertenece a esta molécula.",
        )
    if corrida.status != "SUCCESS":
        raise HTTPException(
            status_code=409,
            detail=(
                f"La corrida {task_id} no terminó con éxito ({corrida.status}); "
                "no produjo una evaluación que comparar."
            ),
        )
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=corrida.molecule_id,
        current_user=current_user,
        forbidden_detail=f"No tienes permiso para consultar la corrida {task_id}.",
        missing_detail=f"La molécula de la corrida {task_id} no existe.",
    )
    molecula = await db.scalar(
        select(MoleculeORM)
        .options(selectinload(MoleculeORM.target))
        .where(MoleculeORM.id == corrida.molecule_id)
    )
    if molecula is None:
        raise HTTPException(status_code=404, detail=f"La molécula de la corrida {task_id} no existe.")
    evaluacion = SimpleNamespace(**(await repository.materialize_run_snapshot(corrida)))
    evaluacion.molecule = molecula
    evaluacion.task_id = str(corrida.task_id)
    return evaluacion


def _fila_sar(
    e: Any,
    *,
    similarity: float | None,
    base_affinity: float | None,
    es_base: bool,
    comparacion: Comparabilidad,
) -> dict[str, Any]:
    """Fila de un análogo. La comparabilidad gobierna el delta; nada se fabrica.

    SOL-04 / AMP-02 (decisión aprobada el 2026-10-02):

    - `delta_affinity` sólo existe cuando base y análogo comparten condición
      química (pH, protonación, tautómero) y protocolo estructural. En
      abstención es `None`: la afinidad cruda SIGUE visible en su columna, lo
      que no se fabrica es la resta entre especies distintas.
    - `delta_score` es SIEMPRE ausente: el score agregado no es una magnitud
      termodinámica; restar scores de modelos no mide nada.
    - El motivo de la abstención nombra los valores en conflicto y viaja en
      `comparison_reason`; `highlight` es la línea que la fila enseña.
    - La fila expone su condición química: qué especie se acopló y con qué
      carga, no sólo el SMILES que escribió el usuario.
    """
    ml_prob = _first_available(
        getattr(e, "clgnn_score", None),
        getattr(e, "xgb_score", None),
        getattr(e, "gnn_score", None),
    )
    evaluada_en = getattr(e, "evaluated_at", None)
    return {
        "molecule_id": str(e.molecule.id),
        "name": e.molecule.name or e.molecule.smiles_hash[:8],
        "smiles": e.molecule.smiles,
        "similarity": similarity,
        "total_score": e.total_score,
        "affinity_kcal": e.affinity_kcal,
        "ml_prob": ml_prob,
        "comparison_state": comparacion.estado,
        "comparison_reason": comparacion.motivo,
        "highlight": comparacion.resumen,
        "delta_score": None,
        "delta_affinity": (
            _difference(e.affinity_kcal, base_affinity, digits=2)
            if comparacion.comparable
            else None
        ),
        **condicion_quimica_publica(e),
        "molecular_weight": e.molecular_weight,
        "log_p": e.log_p,
        "tpsa": e.tpsa,
        "lipinski_pass": e.lipinski_pass,
        "ghose_pass": getattr(e, "ghose_pass", None),
        "egan_pass": getattr(e, "egan_pass", None),
        "muegge_pass": getattr(e, "muegge_pass", None),
        "muegge_score": getattr(e, "muegge_score", None),
        "fsp3": getattr(e, "fsp3", None),
        "qed": getattr(e, "qed", None),
        "sa_score": e.sa_score,
        "is_pains": getattr(e, "is_pains", False) if hasattr(e, "is_pains") else False,
        "admet_score": getattr(e, "blood_viability_score", None),
        "is_base": es_base,
        "task_id": getattr(e, "task_id", None),
        # Con su zona (UTC), también la que viene escrita en la instantánea.
        "evaluated_at": instante_utc(evaluada_en),
    }


@router.get("/{molecule_id}")
async def get_sar_table(
    molecule_id: str,
    task_id: str | None = Query(
        default=None,
        description="Corrida que sirve de base. Sin ella, la evaluación más reciente de la molécula.",
    ),
    cohort_task_ids: list[str] = Query(
        default_factory=list,
        description=(
            "Corridas que forman la cohorte, explícitas. Sin ellas, la evaluación más "
            "reciente de cada molécula contra el mismo receptor."
        ),
    ),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """
    Structure-Activity Relationship table.

    Returns all molecules evaluated against the SAME target,
    sorted by score (best first). The affinity difference against the
    baseline is ONLY computed when both runs share the same chemical
    preparation condition (pH, protonation, tautomer) and the same
    structural protocol (receptor, box, seed, effort). Otherwise the row
    declares `comparison_state="abstained"` with the reason naming both
    conflicting values — the raw affinities stay visible; the difference
    between distinct chemical species is never fabricated (SOL-04/AMP-02).

    CAS-02. Por defecto la tabla usa la proyección más reciente de cada
    molécula, que cambia al reevaluarla con otro protocolo. Con `task_id` la base
    es lo que ESA corrida produjo, y con `cohort_task_ids` el conjunto de análogos
    es el de las corridas pedidas, leídas de sus snapshots inmutables. La
    abstención sigue gobernando el delta: una cohorte explícita no vuelve
    comparable lo que no lo es. La respuesta declara de dónde salió la tabla
    (`cohort`).
    """
    from uuid import UUID

    try:
        mol_uuid = UUID(molecule_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid molecule_id")

    repository = Repository(db)

    # Get the base molecule
    await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=mol_uuid,
        current_user=current_user,
        forbidden_detail="No tienes permiso para consultar esta evaluación.",
        missing_detail="Molecule not found",
    )
    cohorte_pedida = list(dict.fromkeys(cohort_task_ids))
    if len(cohorte_pedida) > MAX_COHORTE_EXPLICITA:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Una cohorte explícita admite hasta {MAX_COHORTE_EXPLICITA} corridas; "
                f"se pidieron {len(cohorte_pedida)}."
            ),
        )
    if task_id is not None:
        base_eval = await _evaluacion_de_corrida(
            repository=repository, db=db, task_id=task_id,
            molecule_id=mol_uuid, current_user=current_user,
        )
    else:
        base_eval = await repository.get_evaluation_result(mol_uuid)
    if base_eval is None or base_eval.molecule is None:
        raise HTTPException(status_code=404, detail="Molecule not found")

    target = (
        require_target_object_access(base_eval.molecule.target, current_user)
        if base_eval.molecule.target else None
    )
    if target is None:
        raise HTTPException(
            status_code=409,
            detail="La evaluación base no conserva un receptor verificable; no se puede construir una tabla SAR comparable.",
        )
    target_pdb_id = target.pdb_id

    # Get ALL evaluations for this target from this user (or all if anonymous)
    # Limit to 50 most recent
    if cohorte_pedida:
        all_evals = []
        for tarea in cohorte_pedida:
            analogo = await _evaluacion_de_corrida(
                repository=repository, db=db, task_id=tarea,
                molecule_id=None, current_user=current_user,
            )
            receptor_del_analogo = getattr(analogo.molecule.target, "pdb_id", None)
            if str(receptor_del_analogo or "").upper() != str(target_pdb_id).upper():
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"La corrida {tarea} es contra {receptor_del_analogo or 'un receptor no verificable'}, "
                        f"no contra {target_pdb_id}: no entra en la misma tabla SAR."
                    ),
                )
            all_evals.append(analogo)
    else:
        all_evals = await repository.get_sar_analogs(
            target_pdb_id=target_pdb_id,
            user_id=current_user.id if current_user else None,
            limit=50,
        )

    # Base evaluation scores
    base_score = _finite_number(base_eval.total_score)
    base_affinity = _finite_number(base_eval.affinity_kcal)

    # ═════════════════════════════════════════════════════════════════
    # Las huellas de RDKit, todas de una vez y fuera del bucle de eventos
    # ═════════════════════════════════════════════════════════════════
    #
    # Auditoría de backend del 2026-09-04, §3.3. Este endpoint es `async def` y
    # el bucle de abajo llamaba a `_tanimoto_similarity` por análogo: un
    # `MolFromSmiles` más una huella Morgan cada vez, en el hilo del bucle de
    # eventos. Una tabla SAR de una serie madura son decenas o cientos de
    # filas, así que el coste no es el de una molécula sino el de todas — y
    # mientras se calculan, FastAPI no atiende el sondeo de progreso del
    # frontend.
    #
    # Se calculan en un solo salto al pool de hilos, sobre los SMILES ya
    # extraídos del ORM. Nada de esto toca la sesión de base de datos, que es
    # lo que haría inseguro moverlo de hilo.
    base_smiles = base_eval.molecule.smiles
    evaluaciones = [e for e in all_evals if e.molecule is not None]
    smiles_analogos = [e.molecule.smiles for e in evaluaciones]

    def _similitudes() -> list[float | None]:
        base_fp = None
        try:
            from rdkit import Chem

            base_mol = Chem.MolFromSmiles(base_smiles)
            if base_mol:
                base_fp = _huella_morgan(base_mol)
        except Exception:
            pass
        return [_tanimoto_similarity(base_fp, smiles) for smiles in smiles_analogos]

    similitudes = await run_in_threadpool(_similitudes)

    results = []
    for e, similarity in zip(evaluaciones, similitudes):
        # SOL-04 / AMP-02: cada análogo se compara contra la base con las
        # condiciones químicas y estructurales sobre la mesa — pH de
        # protonación, tautómero, receptor, caja, semilla. La abstención del
        # delta es una salida de primera clase y su motivo viaja en la fila.
        comparacion = comparar_corridas(base_eval, e)
        results.append(_fila_sar(
            e,
            similarity=similarity,
            base_affinity=base_affinity,
            es_base=(
                str(getattr(e, "task_id", "")) == str(getattr(base_eval, "task_id", ""))
                if cohorte_pedida and task_id is not None
                else str(e.molecule.id) == molecule_id
            ),
            comparacion=comparacion,
        ))

    # Sort: best score first
    results.sort(
        key=lambda r: (
            _finite_number(r["total_score"]) is not None,
            _finite_number(r["total_score"]) or 0.0,
        ),
        reverse=True,
    )

    # Compute best value per metric for highlighting
    best_of = {
        "score": _best_available([r["total_score"] for r in results]),
        "affinity": _best_available(
            [r["affinity_kcal"] for r in results],
            lower_is_better=True,
        ),
        "admet": _best_available([r["admet_score"] for r in results]),
    }

    return {
        "base_molecule_id": molecule_id,
        "target_pdb_id": target_pdb_id,
        "target_name": base_eval.molecule.target.name if base_eval.molecule.target else "Unknown",
        "total_analogs": len(results),
        "base_score": base_score,
        "base_affinity": base_affinity,
        "best_of": best_of,
        "results": results,
        "analogs": results,
        # CAS-02: de dónde salió esta tabla. «latest_projection» es la que
        # cambia al reevaluar; «explicit_runs» es lo que las corridas pedidas
        # produjeron, y es reproducible.
        "cohort": {
            "source": "explicit_runs" if cohorte_pedida else "latest_projection",
            "base_task_id": getattr(base_eval, "task_id", None) if task_id is not None else None,
            "task_ids": cohorte_pedida or None,
        },
    }
