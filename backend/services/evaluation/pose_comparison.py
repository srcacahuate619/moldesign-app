"""La evidencia estructural de una corrida y la comparación de dos de sus poses, derivadas en el backend.

`derive_structural_evidence` es el espejo, campo por campo, de `deriveStructuralEvidence` en
`frontend/lib/structuralEvidence.ts`: la pestaña Evaluación sigue leyendo la suya, y quien no tiene pantalla
(MolChat, un informe, otra integración) lee esta. Dos implementaciones del mismo veredicto se desincronizan; lo
que las mantiene iguales es un archivo dorado compartido (`backend/tests/data/pose_comparison_golden.json`) que la
prueba de cada lado exige reproducir byte a byte (ver `test_pose_comparison.py` y `structuralEvidence.test.ts`).

Reglas que no se negocian (las mismas de la pantalla):
- una pose es «físicamente válida» SÓLO con `passed`; `review` y `not_evaluated` nunca lo son;
- Vina top-1 se conserva y se enseña siempre, aunque el selector sugiera otra o se abstenga;
- la pose sugerida que no pasó NO se sustituye: se declara revisión y las alternativas se listan sin elegir;
- nada se inventa: lo que la corrida no persistió sale `None`.

Diferencia declarada con la versión de JavaScript: aquí un número es un `int`/`float` finito (o una cadena que lo
es). `Number(true)` y `Number("")` valen 1 y 0 en JavaScript; aquí son «sin dato». Ningún contrato del backend
escribe esos valores.

`compare_two_poses` es nuevo: dice qué separa a dos poses concretas con lo que el contrato ya trae. No añade
umbrales propios ni elige una pose.
"""
from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping

PHYSICAL_STATUSES = ("passed", "failed", "review", "not_evaluated")
SELECTION_STATUSES = ("selected", "abstained", "unavailable", "error")
#: Kcal/mol: la misma distancia con la que la pantalla llama «casi empate» a dos poses.
NEAR_TIE_KCAL = 1


def _finite_or_none(value: Any) -> float | int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = value
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    return number if math.isfinite(number) else None


def _count_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _physical(value: Any) -> str:
    return value if value in PHYSICAL_STATUSES else "not_evaluated"


def _selection(value: Any) -> str:
    return value if value in SELECTION_STATUSES else "unavailable"


def is_physically_valid(status: Any) -> bool:
    """Sólo `passed`. Es la regla que impide llamar válido a lo que nadie midió."""
    return status == "passed"


def _engine_label(engine: Any) -> str | None:
    if isinstance(engine, list):
        return " · ".join(str(item) for item in engine) if engine else None
    return engine


def _round3(value: float) -> float:
    """`Number(value.toFixed(3))` de JavaScript: se redondea el valor binario exacto, no su forma corta, y un
    empate exacto va hacia arriba (para una diferencia no negativa, como la de las poses ordenadas, es lo mismo)."""
    return float(Decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))


def _get(mapping: Any, key: str) -> Any:
    return mapping.get(key) if isinstance(mapping, Mapping) else None


def derive_structural_evidence(result: Mapping[str, Any] | None) -> dict[str, Any]:
    """La vista de la evidencia estructural de un resultado (`EvaluationResultRead` como diccionario)."""
    evidence = _get(result, "structural_evidence")
    contract = _get(result, "pose_selection")

    poses = sorted(
        (pose for pose in (_get(result, "docking_poses") or [])
         if isinstance(pose, Mapping) and isinstance(pose.get("affinity"), (int, float))
         and not isinstance(pose.get("affinity"), bool) and math.isfinite(pose["affinity"])),
        key=lambda pose: pose["affinity"])

    # ── 1. Generación ──
    poses_produced = _finite_or_none(_get(evidence, "poses_produced"))
    poses_produced = len(poses) if poses_produced is None else poses_produced
    top_affinity = poses[0]["affinity"] if poses else _finite_or_none(_get(result, "affinity_kcal"))
    affinity_gap = _round3(poses[1]["affinity"] - poses[0]["affinity"]) if len(poses) > 1 else None

    vina_version = _get(result, "vina_version")
    seed = _finite_or_none(_get(result, "vina_random_seed"))
    parsing_source = _get(result, "parsing_source")
    provenance_present = sum(1 for value in (vina_version, seed, parsing_source) if value is not None and value != "")
    protocol = _get(result, "docking_protocol")

    generation = {
        "status": ("absent" if poses_produced == 0 else "partial" if top_affinity is None
                   else "ok" if provenance_present == 3 else "partial"),
        "poses_produced": poses_produced,
        "top_affinity": top_affinity,
        "affinity_gap": affinity_gap,
        "engine": _get(result, "engine_used"),
        "vina_version": vina_version,
        "seed": seed,
        "parsing_source": parsing_source,
        "receptor_sha256": _get(evidence, "receptor_sha256"),
        "receptor_source": _get(evidence, "receptor_source"),
        "conformers": _count_or_none(_get(protocol, "conformers_generated")),
        "conformers_requested": _count_or_none(_get(protocol, "conformers_requested")),
        "restarts": None,
        "provenance_present": provenance_present,
        "provenance_total": 3,
    }

    # ── 2. Selección ──
    sel_status = _selection(_get(contract, "status"))
    vina_top1_rank = _finite_or_none(_get(contract, "vina_top1_rank"))
    if vina_top1_rank is None:
        vina_top1_rank = _finite_or_none(_get(evidence, "primary_pose_rank"))
    if vina_top1_rank is None and poses:
        vina_top1_rank = poses[0].get("rank")
    suggested_rank = _finite_or_none(_get(contract, "selected_pose_rank"))
    would_have = _finite_or_none(_get(contract, "would_have_suggested_rank"))

    pose_scores = []
    for entry in (_get(contract, "pose_scores") or []):
        rank, score = _finite_or_none(_get(entry, "rank")), _finite_or_none(_get(entry, "score"))
        if rank is not None and score is not None:
            pose_scores.append({"rank": rank, "score": score})

    model = _get(contract, "model")
    fallback = _get(contract, "strategy_is_fallback")
    selection = {
        "status": sel_status,
        "vina_top1_rank": vina_top1_rank,
        "suggested_rank": suggested_rank,
        "would_have_suggested_rank": would_have,
        "confidence": _finite_or_none(_get(contract, "confidence")),
        "abstention_threshold": _finite_or_none(_get(model, "abstention_threshold")),
        "abstained": _get(contract, "abstained") is True,
        "abstention_reason": _get(contract, "abstention_reason"),
        "is_fallback": fallback if fallback is not None else sel_status != "selected",
        "diverges_from_vina_top1": (suggested_rank is not None and vina_top1_rank is not None
                                    and suggested_rank != vina_top1_rank),
        "model_name": _get(model, "name"),
        "model_version": _get(model, "version"),
        "model_sha256": _get(model, "model_sha256"),
        "detail": _get(contract, "detail"),
        "warnings": [item for item in (_get(contract, "warnings") or []) if item],
        "pose_scores": pose_scores,
    }

    # ── 3. Controles físicos ──
    poses_evaluated = _finite_or_none(_get(evidence, "poses_evaluated")) or 0
    stage_status = _physical(_get(evidence, "stage_status"))

    physical_poses = []
    for entry in (_get(evidence, "poses") or []):
        checks = _get(entry, "checks") or []
        states = [_get(check, "estado") for check in checks]
        physical_poses.append({
            "rank": _finite_or_none(_get(entry, "rank")),
            "status": _physical(_get(entry, "status")),
            "affinity": _finite_or_none(_get(entry, "observed_vina_affinity_kcal_mol")),
            "engine": _get(entry, "engine"),
            "failing_checks": [item for item in (_get(entry, "checks_que_fallan") or []) if item],
            "passed_count": states.count("PASA"),
            "failed_count": states.count("FALLA"),
            "not_evaluated_count": states.count("NO_EVALUADO"),
            "detail": _get(entry, "detail"),
            "reason_code": _get(entry, "reason_code"),
        })

    declared_suggested_status = _get(contract, "suggested_pose_physical_status")
    if declared_suggested_status:
        suggested_status = _physical(declared_suggested_status)
    elif suggested_rank is not None:
        suggested_status = next((p["status"] for p in physical_poses if p["rank"] == suggested_rank), None)
    else:
        suggested_status = None

    physical = {
        "status": ("absent" if evidence is None else {"passed": "ok", "failed": "failed", "review": "review"}.get(stage_status, "absent")),
        "stage_status": stage_status if evidence is not None else "not_evaluated",
        "poses_produced": poses_produced,
        "poses_evaluated": poses_evaluated,
        "engine": _engine_label(_get(evidence, "validation_engine")),
        "reason_code": _get(evidence, "reason_code"),
        "detail": _get(evidence, "detail"),
        "receptor_sha256": _get(evidence, "receptor_sha256"),
        "poses": physical_poses,
        "suggested_pose_status": suggested_status,
        "needs_review": (_get(contract, "physical_review") is True
                         or (suggested_rank is not None and not is_physically_valid(suggested_status))),
    }

    # ── 4. Decisión justificable ──
    alternatives = [rank for rank in (_finite_or_none(_get(item, "rank"))
                                      for item in (_get(contract, "physically_valid_alternatives") or [])) if rank is not None]
    near_tie_count = 0 if top_affinity is None else sum(1 for pose in poses if pose["affinity"] - top_affinity <= NEAR_TIE_KCAL)

    established = []
    if poses_produced > 0:
        established.append("poses_generated")
    if poses_evaluated > 0:
        established.append("physical_checks_run")
    if sel_status in ("selected", "abstained"):
        established.append("selector_ran")
    if generation["receptor_sha256"]:
        established.append("provenance_sealed")

    uncertainties = []
    if evidence is None or poses_evaluated == 0:
        uncertainties.append("no_physical_validation")
    elif poses_evaluated < physical["poses_produced"]:
        uncertainties.append("partial_coverage")
    if suggested_rank is not None and not is_physically_valid(suggested_status):
        uncertainties.append("suggested_pose_not_passed")
    if sel_status == "abstained":
        uncertainties.append("selector_abstained")
    if sel_status == "unavailable":
        uncertainties.append("selector_unavailable")
    if sel_status == "error":
        uncertainties.append("selector_error")
    if selection["diverges_from_vina_top1"]:
        uncertainties.append("selection_diverges")
    if poses_produced == 1:
        uncertainties.append("single_pose")
    elif near_tie_count > 1:
        uncertainties.append("near_tie")
    if provenance_present < 3:
        uncertainties.append("incomplete_provenance")
    if seed is None:
        uncertainties.append("no_seed")

    if poses_produced == 0 or stage_status == "failed":
        next_step = "abstain"
    elif stage_status != "passed" or physical["needs_review"] or sel_status == "error":
        next_step = "review"
    else:
        next_step = "proceed_within_protocol"

    decision = {"established": established, "uncertainties": uncertainties, "alternatives": alternatives, "next_step": next_step}

    # ── Comparación: top-1, sugerida y alternativas, en una sola tabla ──
    score_by_rank = {entry["rank"]: entry["score"] for entry in pose_scores}
    physical_by_rank = {p["rank"]: p["status"] for p in physical_poses if p["rank"] is not None}
    comparison = []
    for pose in poses:
        status = physical_by_rank.get(pose.get("rank"), "not_evaluated")
        comparison.append({
            "rank": pose.get("rank"),
            "affinity": pose["affinity"],
            "selector_score": score_by_rank.get(pose.get("rank")),
            "physical_status": status,
            "is_vina_top1": vina_top1_rank is not None and pose.get("rank") == vina_top1_rank,
            "is_suggested": suggested_rank is not None and pose.get("rank") == suggested_rank,
            "is_alternative": pose.get("rank") in alternatives,
            "physically_valid": is_physically_valid(status),
        })

    return {
        "has_anything": poses_produced > 0 or evidence is not None or contract is not None,
        "is_legacy_run": evidence is None and (sel_status == "unavailable" or contract is None),
        "generation": generation,
        "selection": selection,
        "physical": physical,
        "decision": decision,
        "comparison": comparison,
    }


def _ligand_species(result: Mapping[str, Any] | None) -> dict[str, Any]:
    """La especie que se acopló frente a la que se escribió: un contacto iónico sólo vale para ella.

    No lleva SMILES (se lee en el dossier); dice si la protonación cambió la entrada, con qué motor y a qué pH, y cuántas
    alternativas quedaron sin evaluar. Una corrida que no guardó el estado del ligando no inventa nada."""
    state = _get(result, "ligand_state")
    if not isinstance(state, Mapping) or not state:
        return {"available": False, "reason_code": "LIGAND_STATE_NOT_STORED"}
    protonation = state.get("protonacion") if isinstance(state.get("protonacion"), Mapping) else {}

    def flag(value: Any) -> bool | None:
        return value if isinstance(value, bool) else None

    def number(value: Any) -> float | None:
        return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None

    alternatives = protonation.get("alternativas")
    engine = protonation.get("motor")
    return {
        "available": True,
        "changed_from_input": flag(state.get("cambio_respecto_a_la_entrada")),
        "protonation_applied": flag(protonation.get("aplicada")),
        "protonation_engine": engine[:40] if isinstance(engine, str) else None,
        "protonation_ph": number(protonation.get("ph")),
        "alternatives_not_evaluated": alternatives if isinstance(alternatives, int) and not isinstance(alternatives, bool) else None,
    }


_CHECK_RESULTS = {"PASA": "passed", "FALLA": "failed", "NO_EVALUADO": "not_evaluated"}


def _checks_detail(entry: Any) -> list[dict[str, str]]:
    """Los controles físicos de una pose con su resultado; un estado que no se conoce sale `unknown`, no `passed`."""
    detail = []
    for check in (_get(entry, "checks") or [])[:60]:
        name = _get(check, "check")
        if isinstance(name, str) and name.strip():
            detail.append({"check": name.strip()[:60], "result": _CHECK_RESULTS.get(_get(check, "estado"), "unknown")})
    return detail


def _vina_rmsd_between(result: Mapping[str, Any] | None, top1_rank: Any, left_pose: Any, right_pose: Any,
                       left: int, right: int, both_found: bool) -> dict[str, Any]:
    """Las cotas de RMSD de Vina (`rmsd l.b.` y `rmsd u.b.`) sólo son contra la mejor pose de ESA búsqueda.

    Describen la distancia entre dos poses únicamente cuando una de ellas es la mejor pose de una corrida de Vina
    de un solo conformador (su propio RMSD es 0 por definición): entonces las cotas de la otra son sus cotas contra
    ella. En cualquier otro caso (conjunto de conformadores, otro motor, ninguna es la mejor) no hay una medida
    entre estas dos poses y se dice por qué. Son cotas, no un intervalo de confianza: el RMSD con simetría de la
    molécula queda entre `lb` y `ub`.
    """
    def unavailable(code: str) -> dict[str, Any]:
        return {"available": False, "reason_code": code, "reference_rank": None, "other_rank": None,
                "lower_bound_angstrom": None, "upper_bound_angstrom": None}

    if not both_found:
        return unavailable("POSE_NOT_FOUND")
    if left == right:
        return unavailable("SAME_POSE")
    protocol = _get(result, "docking_protocol")
    engine = _get(protocol, "engine")
    if not isinstance(engine, str) or not engine.strip():
        return unavailable("ENGINE_NOT_DECLARED")
    if engine.strip().lower() != "vina":
        return unavailable("ENGINE_NOT_VINA")
    generated = _count_or_none(_get(protocol, "conformers_generated"))
    if generated is None:
        return unavailable("CONFORMERS_NOT_DECLARED")
    if generated != 1 or any(isinstance(pose, Mapping) and pose.get("conformer_index") is not None
                             for pose in (left_pose, right_pose)):
        return unavailable("ENSEMBLE_RUN")
    if top1_rank not in (left, right):
        return unavailable("NEITHER_IS_VINA_BEST")
    reference, other = (left_pose, right_pose) if top1_rank == left else (right_pose, left_pose)
    ref_lb, ref_ub = _finite_or_none(reference.get("rmsd_lb")), _finite_or_none(reference.get("rmsd_ub"))
    if ref_lb is None or ref_ub is None or ref_lb != 0 or ref_ub != 0:
        return unavailable("REFERENCE_RMSD_NOT_ZERO")
    lower, upper = _finite_or_none(other.get("rmsd_lb")), _finite_or_none(other.get("rmsd_ub"))
    if lower is None or upper is None:
        return unavailable("RMSD_NOT_REPORTED")
    return {"available": True, "reason_code": None,
            "reference_rank": top1_rank, "other_rank": right if top1_rank == left else left,
            "lower_bound_angstrom": lower, "upper_bound_angstrom": upper}


def compare_two_poses(result: Mapping[str, Any] | None, left: int, right: int) -> dict[str, Any]:
    """Qué separa a dos poses de una corrida, con lo que el contrato ya trae.

    `left` y `right` son rangos de la corrida (1 = la primera pose del archivo de poses). Una pose que la corrida
    no tiene sale `found: false` y no contribuye a ninguna diferencia. No se elige ganadora: se dice cuál tiene
    la mejor energía de Vina y, aparte, qué dicen los controles físicos y el selector.
    """
    view = derive_structural_evidence(result)
    raw = {pose.get("rank"): pose for pose in (_get(result, "docking_poses") or []) if isinstance(pose, Mapping)}
    rows = {row["rank"]: row for row in view["comparison"]}
    physical = {p["rank"]: p for p in view["physical"]["poses"] if p["rank"] is not None}
    scores = {entry["rank"]: entry["score"] for entry in view["selection"]["pose_scores"]}
    raw_physical = {entry.get("rank"): entry for entry in (_get(_get(result, "structural_evidence"), "poses") or [])
                    if isinstance(entry, Mapping)}

    def describe(rank: int) -> dict[str, Any]:
        row, check, source = rows.get(rank), physical.get(rank), raw.get(rank)
        if row is None:
            return {"rank": rank, "found": False}
        return {
            "rank": rank, "found": True,
            "vina_affinity_kcal_mol": row["affinity"],
            "selector_score": scores.get(rank),
            "physical_status": row["physical_status"],
            "physically_valid": row["physically_valid"],
            "failing_checks": check["failing_checks"] if check else [],
            "checks_passed": check["passed_count"] if check else None,
            "checks_failed": check["failed_count"] if check else None,
            "checks_not_evaluated": check["not_evaluated_count"] if check else None,
            "physical_reason_code": check["reason_code"] if check else None,
            # Cada control con su resultado, tal como la corrida lo guardó; vacío si no guardó el detalle.
            "checks_detail": _checks_detail(raw_physical.get(rank)),
            "is_vina_top1": row["is_vina_top1"],
            "is_suggested": row["is_suggested"],
            "is_physically_valid_alternative": row["is_alternative"],
            # RMSD de Vina contra su mejor pose (modo 1): cotas que Vina da por pose, no una medida entre estas dos.
            "vina_rmsd_lb_vs_best": _finite_or_none(source.get("rmsd_lb")) if source else None,
            "vina_rmsd_ub_vs_best": _finite_or_none(source.get("rmsd_ub")) if source else None,
        }

    a, b = describe(left), describe(right)
    both = a["found"] and b["found"]
    rmsd_between = _vina_rmsd_between(result, view["selection"]["vina_top1_rank"], raw.get(left), raw.get(right),
                                      left, right, both)
    delta = _round3(b["vina_affinity_kcal_mol"] - a["vina_affinity_kcal_mol"]) if both else None
    if not both:
        better = None
    elif delta == 0:
        better = "equal"
    else:
        better = left if delta > 0 else right  # delta = right - left; positivo: left tiene la energía más baja
    validities = (a.get("physically_valid"), b.get("physically_valid"))
    if not both:
        agreement = "unavailable"
    elif all(validities):
        agreement = "both_passed"
    elif not any(validities):
        agreement = "neither_passed"
    else:
        agreement = "only_left_passed" if validities[0] else "only_right_passed"

    return {
        "left": a, "right": b,
        "difference": {
            "right_minus_left_vina_kcal_mol": delta,
            "lower_vina_energy": better,
            "physical_agreement": agreement,
            "within_near_tie": None if delta is None else abs(delta) <= NEAR_TIE_KCAL,
            "vina_rmsd_between_poses": rmsd_between,
        },
        "selection": {key: view["selection"][key] for key in (
            "status", "suggested_rank", "would_have_suggested_rank", "abstained", "abstention_reason",
            "diverges_from_vina_top1", "is_fallback", "confidence", "abstention_threshold", "detail")},
        "vina_top1_rank": view["selection"]["vina_top1_rank"],
        "poses_produced": view["generation"]["poses_produced"],
        "decision": view["decision"],
        "legacy_run": view["is_legacy_run"],
        "ligand_species": _ligand_species(result),
        "stage": {"status": view["physical"]["stage_status"], "poses_evaluated": view["physical"]["poses_evaluated"],
                  "engine": view["physical"]["engine"], "reason_code": view["physical"]["reason_code"]},
    }
