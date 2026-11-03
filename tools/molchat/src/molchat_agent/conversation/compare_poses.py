"""Compare two poses of a finished evaluation: the lock's structural evidence plus the contacts each pose makes.

MolChat does not own the science. The energy, the physical checks and the selector come from
``GET /evaluation/pose-comparison/{task_id}``, which MolDesign derives from the same contract the
Evaluation and Moldex tabs show. The contacts come from ``GET /evaluation/interactions/{molecule_id}``
(one call per pose, ProLIF on the person's machine, a few seconds each). What MolChat adds is the
difference between the two contact lists, computed here in code so the model never subtracts sets.

The result is built from an allowlist, never by filtering. Nothing here picks a winner: the energy
difference says which pose Vina scored lower, the physical status says what PoseBusters measured,
and the contacts describe geometry. A pose the run does not have, a check the run did not persist
or a contact analysis that failed is reported as such and is never read as good.
"""
from __future__ import annotations

import asyncio
import math
import re
from typing import Any

import httpx

from ..bridge import MolDesignBridge
from .tool_loop import Tool

#: Appended to the system prompt of the hosted chat. Static: no user data is formatted in.
COMPARE_GUIDANCE = (
    "Si el usuario pide comparar dos poses de una evaluación terminada (por ejemplo la pose 1 con la 2), usa "
    "compare_poses con su task_id y los dos rangos, y explica solo con los hechos devueltos. Di primero cuál tiene "
    "la energía de Vina más baja y por cuánto, y luego, aparte, qué dicen los controles físicos de cada una: una "
    "pose es físicamente válida solo si pasó; «revisión» y «no evaluada» no lo son. Si el selector sugirió otra "
    "pose o se abstuvo, dilo. Describe los contactos compartidos y exclusivos con su tipo, residuo y distancia en Å "
    "y aclara que describen geometría, no cuál pose es la real. No declares ganadora: Vina no mide afinidad real y "
    "una diferencia menor de 1 kcal/mol es un casi empate. Si faltan datos (corrida anterior, pose sin controles, "
    "contactos no disponibles), dilo en lugar de suponerlos. Usa contacts «omitir» si el usuario pide solo la "
    "energía y la validez física. Para decir cuánto se separan las dos poses, usa "
    "difference.pose_rmsd_between_poses si available es verdadero (RMSD medido de las coordenadas guardadas); si no "
    "existe o no está disponible, usa difference.vina_rmsd_between_poses: si available es verdadero, cita sus dos cotas "
    "como cotas (no como intervalo de confianza ni como prueba de cuál es la correcta); si es falso, di el motivo y no "
    "estimes la separación. Explica cómo cambia la orientación con los contactos exclusivos y los residuos, sin inventar "
    "giros ni ángulos. Si preguntan qué controles físicos superó cada pose, enumera checks_detail de cada una con su "
    "resultado; si viene vacío, di que la corrida solo guardó el recuento y no el detalle. Si el análisis de contactos "
    "de una pose devuelve cero, no lo presentes como ausencia de interacción: di que no es concluyente y por qué. Si "
    "el usuario pide repetir o desarrollar cifras de una comparación anterior, vuelve a llamar a compare_poses con los "
    "mismos argumentos (solo lee) en lugar de citarlas de memoria. Distingue los contactos compartidos (mismo tipo y mismo "
    "residuo) de los residuos en común (el residuo está en las dos poses, aunque con otro tipo): da las dos cifras y nombra "
    "los residuos de residues_with_different_types. Si dos tipos de contacto se apoyan en los mismos átomos "
    "(overlapping_criteria), cuéntalos como un solo contacto con dos criterios. Al citar un contacto di sus átomos y "
    "ángulos (atoms, angles_degrees) si vienen; si el átomo de la proteína de un contacto halógeno es un carbono, dilo: "
    "no es un aceptor con par solitario (O, N, S). Un contacto iónico vale para la especie que se acopló (ligand_species), "
    "no para la molécula en general. Si piden algo que los datos no pueden dar (un "
    "intervalo de confianza, cuál es la pose experimentalmente correcta), di que no se puede y conserva las cifras que "
    "sí están verificadas. ")

_TASK_ID = re.compile(r"[A-Za-z0-9_.:-]{1,128}")
_MOLECULE_ID = re.compile(r"[0-9a-fA-F-]{32,36}")
_LIST_CAP = 20

#: What each uncertainty code means, in the lock's words. The host writes this, not the model.
UNCERTAINTY_TEXT = {
    "no_physical_validation": "La corrida no tiene controles físicos de sus poses.",
    "partial_coverage": "Los controles físicos no cubrieron todas las poses producidas.",
    "suggested_pose_not_passed": "La pose que sugirió el selector no superó los controles físicos.",
    "selector_abstained": "El selector de poses se abstuvo.",
    "selector_unavailable": "El selector de poses no estaba disponible en esta corrida.",
    "selector_error": "El selector de poses falló.",
    "selection_diverges": "La pose sugerida por el selector no es la de menor energía de Vina.",
    "single_pose": "La corrida produjo una sola pose.",
    "near_tie": "Hay más de una pose a menos de 1 kcal/mol de la mejor: casi empate.",
    "incomplete_provenance": "Falta parte de la procedencia de la corrida (versión de Vina, semilla o fuente de análisis).",
    "no_seed": "La corrida no registró la semilla.",
}

_CHECK_RESULTS = frozenset({"passed", "failed", "not_evaluated"})

_READING_RULES = (
    "La energía de Vina compara poses de la misma molécula en el mismo receptor; no es energía libre ni afinidad medida.",
    "Físicamente válida significa que superó los controles que se evaluaron; no significa que la pose sea la correcta.",
    "Los contactos describen geometría; una diferencia de contactos no dice cuál pose es la real.",
    "Un contacto compartido es el mismo tipo en el mismo residuo; un residuo puede estar en las dos poses con otro tipo "
    "en cada una, y entonces cuenta como residuo en común y no como contacto compartido.",
    "Un contacto iónico (puente salino, catión–π) vale para la especie que se acopló, no para otras formas de la molécula.",
    "No se declara ganadora: ausente o no evaluado nunca se lee como bueno.",
)

#: Why MolDesign has no RMSD between this pair of poses. Vina's bounds are always against the best pose of
#: its own search, so they only describe a pair when one of the two is that pose.
_RMSD_UNAVAILABLE = {
    "NEITHER_IS_VINA_BEST": "ninguna de las dos es la mejor pose de Vina: sus cotas son contra esa mejor pose, no entre ellas",
    "ENSEMBLE_RUN": "la corrida usó varios conformadores del ligando y las cotas de cada pose son dentro de su propia búsqueda",
    "ENGINE_NOT_VINA": "la corrida no la hizo Vina",
    "ENGINE_NOT_DECLARED": "la corrida no declara el motor que produjo las poses",
    "CONFORMERS_NOT_DECLARED": "la corrida no declara cuántos conformadores usó",
    "REFERENCE_RMSD_NOT_ZERO": "la mejor pose no trae RMSD 0 contra sí misma, así que las cotas no se pueden leer como una distancia entre las dos",
    "RMSD_NOT_REPORTED": "la corrida no guardó las cotas de RMSD de esa pose",
    "SAME_POSE": "son la misma pose",
    "POSE_NOT_FOUND": "falta una de las dos poses",
}


def _rmsd_between(raw: Any) -> dict[str, Any]:
    """Vina's RMSD bounds for this pair, only when MolDesign says they describe it; the sentence is the host's."""
    if isinstance(raw, dict) and raw.get("available") is True:
        ref, other = raw.get("reference_rank"), raw.get("other_rank")
        lower, upper = _number(raw.get("lower_bound_angstrom")), _number(raw.get("upper_bound_angstrom"))
        if type(ref) is int and type(other) is int and lower is not None and upper is not None:
            return {
                "available": True, "reference_rank": ref, "other_rank": other,
                "lower_bound_angstrom": lower, "upper_bound_angstrom": upper,
                "meaning": (f"Vina da las cotas de la pose {other} contra su mejor pose, la {ref}: entre ambas, el RMSD queda "
                            f"entre {lower} Å (cota inferior: empareja átomos del mismo elemento sin importar el orden) y "
                            f"{upper} Å (cota superior: compara cada átomo con el que ocupa su mismo lugar en la molécula). "
                            "Son cotas, no un intervalo de confianza, y no dicen cuál de las dos poses es la correcta."),
            }
    code = _text(raw.get("reason_code"), 40) if isinstance(raw, dict) else None
    why = _RMSD_UNAVAILABLE.get(code or "", "MolDesign no declaró de dónde salen esas cotas")
    return {"available": False, "reason_code": code, "meaning": f"No hay un RMSD de Vina entre estas dos poses: {why}."}


#: Why MolDesign could not measure the distance between the two poses from their stored coordinates.
_POSE_RMSD_UNAVAILABLE = {
    "POSES_NOT_AVAILABLE": "la corrida no conserva el archivo de poses",
    "POSE_NOT_IN_SDF": "una de las poses no está en el archivo de poses",
    "POSE_UNREADABLE": "una de las poses no se puede leer",
    "POSES_NOT_THE_SAME_MOLECULE": "las dos poses no tienen el mismo grafo molecular",
    "RMSD_NOT_COMPUTABLE": "el cálculo falló",
    "RMSD_NOT_FINITE": "el cálculo no dio un número",
    "SAME_POSE": "son la misma pose",
}


def _pose_rmsd(raw: Any, left: int | None, right: int | None) -> dict[str, Any] | None:
    """The distance between the two poses measured from the run's stored coordinates, or ``None`` if the lock does not
    report one at all (an older MolDesign). The sentence is the host's: what was measured and what it does not say."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raw = {}  # reported, but not in a shape that can be a measurement
    value, in_order, atoms = _number(raw.get("rmsd_angstrom")), _number(raw.get("rmsd_atom_order_angstrom")), _count(raw.get("heavy_atoms"))
    if raw.get("available") is True and value is not None and in_order is not None and atoms:
        pair = f"las poses {left} y {right}" if left is not None and right is not None else "las dos poses"
        return {
            "available": True, "rmsd_angstrom": value, "rmsd_atom_order_angstrom": in_order, "heavy_atoms": atoms,
            "meaning": (f"Distancia entre {pair}: RMSD de {value} Å en {atoms} átomos pesados, medido de las coordenadas guardadas "
                        "de la corrida en el marco del receptor, sin superponer, con la correspondencia atómica del grafo de la "
                        f"molécula (entre las equivalentes por simetría, la de menor distancia); con el mismo orden de átomos son "
                        f"{in_order} Å. Mide cuánto se separan las dos poses; no dice cuál es la correcta."),
        }
    code = _text(raw.get("reason_code"), 40)
    why = _POSE_RMSD_UNAVAILABLE.get(code or "", "MolDesign no declaró el motivo")
    return {"available": False, "reason_code": code, "meaning": f"No se midió la distancia entre estas dos poses: {why}."}


def _species(raw: Any) -> dict[str, Any]:
    """Which chemical species the run docked, as the lock declares it (no SMILES): an ionic contact only holds for that
    species. An older MolDesign does not report it, and then nothing is assumed."""
    if not isinstance(raw, dict) or raw.get("available") is not True:
        return {"available": False}
    return {"available": True, "changed_from_input": _flag(raw.get("changed_from_input")),
            "protonation_applied": _flag(raw.get("protonation_applied")),
            "protonation_engine": _text(raw.get("protonation_engine"), 40),
            "protonation_ph": _number(raw.get("protonation_ph")),
            "alternatives_not_evaluated": _count(raw.get("alternatives_not_evaluated"))}


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return None
    return value


def _count(value: Any) -> int | None:
    return value if type(value) is int and value >= 0 else None


def _text(value: Any, limit: int) -> str | None:
    return value.strip()[:limit] or None if isinstance(value, str) else None


def _flag(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None


def _pose(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict) or type(raw.get("rank")) is not int:
        return {"found": False}
    if raw.get("found") is not True:
        return {"rank": raw["rank"], "found": False}
    checks = raw.get("failing_checks")
    detail = raw.get("checks_detail")
    return {
        "rank": raw["rank"], "found": True,
        "vina_affinity_kcal_mol": _number(raw.get("vina_affinity_kcal_mol")),
        "selector_score": _number(raw.get("selector_score")),
        "physical_status": _text(raw.get("physical_status"), 20),
        # Derived here from the status, not copied: only ``passed`` is valid, whatever the flag says.
        "physically_valid": raw.get("physical_status") == "passed",
        "failing_checks": [text for item in (checks[:10] if isinstance(checks, list) else []) if (text := _text(item, 60))],
        "checks_passed": _count(raw.get("checks_passed")),
        "checks_failed": _count(raw.get("checks_failed")),
        "checks_not_evaluated": _count(raw.get("checks_not_evaluated")),
        # Each control with the result the run stored; an unknown result is "unknown", never "passed". Empty when the
        # run kept only the counts.
        "checks_detail": [{"check": name, "result": item["result"] if item.get("result") in _CHECK_RESULTS else "unknown"}
                          for item in (detail[:60] if isinstance(detail, list) else [])
                          if isinstance(item, dict) and (name := _text(item.get("check"), 60))],
        "is_vina_top1": _flag(raw.get("is_vina_top1")),
        "is_suggested": _flag(raw.get("is_suggested")),
        "is_physically_valid_alternative": _flag(raw.get("is_physically_valid_alternative")),
        "vina_rmsd_lb_vs_best": _number(raw.get("vina_rmsd_lb_vs_best")),
        "vina_rmsd_ub_vs_best": _number(raw.get("vina_rmsd_ub_vs_best")),
    }


def build_comparison_facts(task_id: str, data: dict[str, Any]) -> dict[str, Any]:
    """The comparable facts of two poses, from an allowlist; see the module docstring."""
    difference = data.get("difference") if isinstance(data.get("difference"), dict) else {}
    selection = data.get("selection") if isinstance(data.get("selection"), dict) else {}
    decision = data.get("decision") if isinstance(data.get("decision"), dict) else {}
    stage = data.get("stage") if isinstance(data.get("stage"), dict) else {}
    codes = [code for code in (decision.get("uncertainties") if isinstance(decision.get("uncertainties"), list) else [])
             if isinstance(code, str)][:12]
    alternatives = decision.get("alternatives")
    rmsd = _rmsd_between(difference.get("vina_rmsd_between_poses"))
    poses = {"left": _pose(data.get("left")), "right": _pose(data.get("right"))}
    measured = _pose_rmsd(difference.get("pose_rmsd_between_poses"), poses["left"].get("rank"), poses["right"].get("rank"))
    return {
        "status": "ok", "task_id": task_id, "source": "MolDesign GET /evaluation/pose-comparison",
        "poses": poses,
        "difference": {
            "right_minus_left_vina_kcal_mol": _number(difference.get("right_minus_left_vina_kcal_mol")),
            "lower_vina_energy": difference.get("lower_vina_energy") if type(difference.get("lower_vina_energy")) is int
                                 or difference.get("lower_vina_energy") == "equal" else None,
            "physical_agreement": _text(difference.get("physical_agreement"), 30),
            "within_near_tie": _flag(difference.get("within_near_tie")),
            "near_tie_threshold_kcal_mol": 1,
            "vina_rmsd_between_poses": rmsd,
            # Present only when MolDesign reports it (an older one does not): the distance measured from the coordinates.
            **({"pose_rmsd_between_poses": measured} if measured is not None else {}),
        },
        "selector": {
            "status": _text(selection.get("status"), 20), "suggested_rank": _count(selection.get("suggested_rank")),
            "would_have_suggested_rank": _count(selection.get("would_have_suggested_rank")),
            "abstained": _flag(selection.get("abstained")), "abstention_reason": _text(selection.get("abstention_reason"), 120),
            "diverges_from_vina_top1": _flag(selection.get("diverges_from_vina_top1")),
            "is_fallback": _flag(selection.get("is_fallback")),
        },
        "vina_top1_rank": _count(data.get("vina_top1_rank")),
        "poses_produced": _count(data.get("poses_produced")),
        "physical_stage": {"status": _text(stage.get("status"), 20), "poses_evaluated": _count(stage.get("poses_evaluated")),
                           "engine": _text(stage.get("engine"), 80), "reason_code": _text(stage.get("reason_code"), 80)},
        "next_step": _text(decision.get("next_step"), 40),
        "alternatives": [rank for rank in (alternatives[:10] if isinstance(alternatives, list) else []) if type(rank) is int],
        "uncertainties": [{"code": code, "meaning": UNCERTAINTY_TEXT.get(code)} for code in codes],
        "legacy_run": _flag(data.get("legacy_run")),
        "ligand_species": _species(data.get("ligand_species")),
        "reading_rules": [*_READING_RULES, *([measured["meaning"]] if measured is not None else []), rmsd["meaning"]],
    }


def _contacts_of(report: Any) -> dict[tuple[str, str], dict[str, Any]] | None:
    """One entry per (type, residue): ProLIF already keeps the first match per type and residue; a distance-only
    fallback can repeat, so the closest distance stands. ``None`` when the report is not a usable contact list."""
    interactions = report.get("interactions") if isinstance(report, dict) else None
    if not isinstance(interactions, list):
        return None
    found: dict[tuple[str, str], dict[str, Any]] = {}
    for item in interactions[:2000]:
        if not isinstance(item, dict):
            continue
        kind, residue = _text(item.get("type"), 30), _text(item.get("residue"), 20)
        if kind is None or residue is None:
            continue
        distance = _number(item.get("distance"))
        entry = found.get((kind, residue))
        if entry is None or (distance is not None and (entry["distance"] is None or distance < entry["distance"])):
            found[(kind, residue)] = {"distance": distance, **_atoms_of(item)}
    return found


#: The angles ProLIF reports for a contact (``DHA_angle``, ``AXD_angle``, ``XAR_angle``...), nothing else of its geometry.
_ANGLE_KEY = re.compile(r"[A-Za-z_]{1,30}_angle")


def _indices(value: Any) -> tuple[int, ...]:
    return tuple(i for i in (value[:8] if isinstance(value, list) else []) if type(i) is int and i >= 0)


def _atoms_of(item: dict[str, Any]) -> dict[str, Any]:
    """The atoms and angles the detector used for a contact, when MolDesign reports them: the evidence a person needs
    to check a contact by hand. Without atom indices (a distance-only fallback) no atom is claimed."""
    ligand, protein = _indices(item.get("ligand_atom_indices")), _indices(item.get("protein_atom_indices"))
    if not ligand or not protein:
        return {}
    geometry = item.get("geometry")
    angles = {key: round(number, 1) for key, value in (geometry.items() if isinstance(geometry, dict) else [])
              if isinstance(key, str) and _ANGLE_KEY.fullmatch(key) and (number := _number(value)) is not None}
    return {"ligand_atom": _text(item.get("ligand_atom"), 12), "protein_atom": _text(item.get("protein_atom"), 12),
            "ligand_atom_indices": ligand, "protein_atom_indices": protein, "angles": dict(sorted(angles.items())[:6])}


def _described(entry: dict[str, Any]) -> dict[str, Any]:
    """The atoms and angles of a contact in the shape the answer cites; empty when MolDesign gave no atom indices."""
    if not entry.get("ligand_atom_indices"):
        return {}
    described: dict[str, Any] = {
        "atoms": f"{entry.get('ligand_atom') or '?'}–{entry.get('protein_atom') or '?'}",
        "ligand_atom_indices": list(entry["ligand_atom_indices"]), "protein_atom_indices": list(entry["protein_atom_indices"])}
    if entry.get("angles"):
        described["angles_degrees"] = dict(entry["angles"])
    return described


def _overlapping(side: str, contacts: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
    """Two contact types of one residue that rest on common atoms of the ligand and of the protein: an N–H⁺ and a
    carboxylate pass the ionic and the hydrogen-bond criteria with the same pair, which is one contact seen twice."""
    by_residue: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for (kind, residue), entry in contacts.items():
        if entry.get("ligand_atom_indices"):
            by_residue.setdefault(residue, []).append((kind, entry))
    found: list[dict[str, Any]] = []
    for residue, items in sorted(by_residue.items()):
        items.sort(key=lambda item: item[0])
        for position, (first_kind, first) in enumerate(items):
            for second_kind, second in items[position + 1:]:
                if (set(first["ligand_atom_indices"]) & set(second["ligand_atom_indices"])
                        and set(first["protein_atom_indices"]) & set(second["protein_atom_indices"])):
                    found.append({"side": side, "residue": residue, "types": [first_kind, second_kind],
                                  "ligand_atom": first.get("ligand_atom"), "protein_atom": first.get("protein_atom")})
    return found


def _rounded(distance: float | int | None) -> float | None:
    return None if distance is None else round(float(distance), 2)


def zero_contacts_caution(ranks: list[int | None], engine: str | None, chemistry: str | None) -> str:
    """What a list with no typed contacts does and does not say. The host writes it; the model does not decide it.

    MolDesign reads the receptor from the PDBQT the docking used. Until 2026-11-02 that left it with single bonds only,
    no aromaticity and no charges, and a real 8T69 run gave zero contacts for poses that touch the pocket; the report
    now says which chemistry it perceived, and a list read without it is never a finding about the pose."""
    which = ", ".join(f"la pose {rank}" if rank is not None else "una de las poses" for rank in ranks)
    fell_back = bool(engine) and not engine.startswith("prolif")
    if fell_back:
        how = "El análisis usó el respaldo por distancias, que no tipifica contactos."
    elif chemistry == "standard_residue_templates":
        how = ("ProLIF no encontró ningún par de átomos que cumpliera sus criterios de tipo, distancia y ángulo, con la "
               "química estándar de los residuos del receptor.")
    else:
        how = ("El análisis no percibió la aromaticidad ni las cargas del receptor, así que no pudo detectar apilamiento "
               "aromático, catión–π ni puentes salinos.")
    return (f"Cero contactos tipificados en {which}. {how} Eso no prueba que no haya interacción con el receptor: puede "
            "ser que ningún contacto cumpliera los criterios configurados o un límite de la preparación del análisis. No lo "
            "leas como ausencia de interacción ni como comparación concluyente; revisa la pose en Moldex antes de decidir.")


def build_contact_diff(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """The contacts two poses share and the ones only one has, computed here, never by the model."""
    a, b = _contacts_of(left), _contacts_of(right)
    if a is None or b is None:
        return {"status": "unavailable", "message": "MolDesign no devolvió una lista de contactos utilizable para las dos poses."}

    def by_type(contacts: dict[tuple[str, str], dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for kind, _residue in contacts:
            counts[kind] = counts.get(kind, 0) + 1
        return dict(sorted(counts.items()))

    def one(keys: list[tuple[str, str]], contacts: dict[tuple[str, str], dict[str, Any]]) -> list[dict[str, Any]]:
        return [{"type": kind, "residue": residue, "distance_angstrom": _rounded(contacts[(kind, residue)]["distance"]),
                 **_described(contacts[(kind, residue)])} for kind, residue in keys[:_LIST_CAP]]

    def types_of(contacts: dict[tuple[str, str], dict[str, Any]], residue: str) -> list[str]:
        return sorted(kind for kind, other in contacts if other == residue)

    def by_residue(key: tuple[str, str]) -> tuple[str, str]:
        return key[1], key[0]  # by residue, then type

    shared = sorted(a.keys() & b.keys(), key=by_residue)
    only_left, only_right = sorted(a.keys() - b.keys(), key=by_residue), sorted(b.keys() - a.keys(), key=by_residue)
    residues_left, residues_right = {residue for _kind, residue in a}, {residue for _kind, residue in b}
    # The same residue can be in both poses with another contact type in each; it is then a residue in common but not a
    # shared contact. Said apart so that the two counts are never mistaken for each other.
    different = [{"residue": residue, "left_types": types_of(a, residue), "right_types": types_of(b, residue),
                  "shared_types": sorted(set(types_of(a, residue)) & set(types_of(b, residue)))}
                 for residue in sorted(residues_left & residues_right) if types_of(a, residue) != types_of(b, residue)]
    conditions = {key: _text(left.get(key), 80) for key in
                  ("engine", "hydrogen_model", "contact_coverage", "receptor_chemistry", "pose_identity_verification")}
    silent = [(side, report) for side, contacts, report in (("left", a, left), ("right", b, right)) if not contacts]
    return {
        "status": "ok",
        "source": "MolDesign GET /evaluation/interactions",
        "conditions": conditions,
        # A list with zero typed contacts is not a finding about the pose: say so before anyone reads it as one.
        "conclusive": not silent,
        "no_typed_contacts_in": [side for side, _report in silent],
        "caution": zero_contacts_caution([_count(report.get("pose_rank")) for _side, report in silent],
                                         conditions.get("engine"), conditions.get("receptor_chemistry")) if silent else None,
        "left": {"total": len(a), "by_type": by_type(a)},
        "right": {"total": len(b), "by_type": by_type(b)},
        "shared": [{"type": kind, "residue": residue, "left_distance_angstrom": _rounded(a[(kind, residue)]["distance"]),
                    "right_distance_angstrom": _rounded(b[(kind, residue)]["distance"]),
                    **{f"{side}_{key}": value for side, contacts in (("left", a), ("right", b))
                       for key, value in _described(contacts[(kind, residue)]).items()}}
                   for kind, residue in shared[:_LIST_CAP]],
        "only_left": one(only_left, a), "only_right": one(only_right, b),
        "shared_count": len(shared), "only_left_count": len(only_left), "only_right_count": len(only_right),
        "residues_in_both": sorted(residues_left & residues_right)[:_LIST_CAP],
        "residues_in_both_count": len(residues_left & residues_right),
        "residues_with_different_types": different[:_LIST_CAP],
        "overlapping_criteria": [*_overlapping("left", a), *_overlapping("right", b)][:_LIST_CAP],
        "residues_only_left": sorted(residues_left - residues_right)[:_LIST_CAP],
        "residues_only_right": sorted(residues_right - residues_left)[:_LIST_CAP],
        "truncated": any(len(items) > _LIST_CAP for items in (shared, only_left, only_right)),
        "note": ("Un contacto cuenta una vez por tipo y residuo: compartido es el mismo tipo en el mismo residuo, y un residuo "
                 "en común puede traer otro tipo en cada pose. Dos tipos que se apoyan en los mismos átomos "
                 "(overlapping_criteria) son dos criterios sobre un mismo contacto. Describe geometría de cada pose; no dice "
                 "cuál es la real."),
    }


async def _get(bridge: MolDesignBridge, path: str, params: dict[str, Any]) -> tuple[int | None, Any]:
    try:
        response = await bridge.client.get(path, params=params, timeout=60, follow_redirects=False,
                                           headers={"Authorization": f"Bearer {bridge.token}"})
        if response.status_code != 200:
            return response.status_code, None
        if len(response.content) > 5_000_000:
            return None, None
        return 200, response.json()
    except (httpx.RequestError, ValueError):
        return None, None


def _refusal(status: int | None, task_id: str) -> dict[str, Any]:
    if status in (403, 404):
        return {"status": "not_found", "task_id": task_id}
    if status == 409:
        return {"status": "not_ready", "task_id": task_id,
                "message": "La evaluación todavía no tiene un resultado terminado con poses que comparar."}
    if status == 422:
        return {"status": "invalid", "message": "MolDesign no aceptó esos rangos de pose."}
    return {"status": "unavailable", "message": "No se pudo consultar la comparación en MolDesign."}


async def _contacts(bridge: MolDesignBridge, task_id: str, molecule_id: str, left: int, right: int) -> dict[str, Any]:
    path = f"/evaluation/interactions/{molecule_id}"
    (_, a), (_, b) = await asyncio.gather(
        _get(bridge, path, {"pose_rank": left, "task_id": task_id}), _get(bridge, path, {"pose_rank": right, "task_id": task_id}))
    if a is None or b is None:
        failed = left if a is None else right
        return {"status": "unavailable",
                "message": f"MolDesign no pudo calcular los contactos de la pose {failed}; la comparación de energía y de controles sigue siendo válida."}
    return build_contact_diff(a, b)


_IONIC = ("salt_bridge", "cation_pi")


def contact_reading(facts: dict[str, Any]) -> str:
    """How the contact counts were taken and what an ionic contact assumes, in the host's words.

    A model can say "three contacts in common" and "four residues in common" in one answer and leave the reader to guess
    why, count an N–H⁺···O⁻ pair twice (as a salt bridge and as a hydrogen bond), or present a salt bridge as a property of
    the molecule when it only holds for the species that was docked. No number check sees any of those."""
    contacts = facts.get("contacts")
    if not isinstance(contacts, dict) or contacts.get("status") != "ok" or contacts.get("conclusive") is False:
        return ""
    left, right = (facts["poses"][side].get("rank") for side in ("left", "right"))
    sentences: list[str] = []
    different = contacts.get("residues_with_different_types") or []
    if different:
        shown = "; ".join(f"{item['residue']} (pose {left}: {', '.join(item['left_types'])}; pose {right}: {', '.join(item['right_types'])})"
                          for item in different[:6])
        sentences.append(f"Contactos compartidos (mismo tipo y mismo residuo): {contacts['shared_count']}. Residuos presentes en las dos "
                         f"poses: {contacts['residues_in_both_count']}; con otro tipo de contacto en cada una: {shown}.")
    for item in [i for i in contacts.get("overlapping_criteria") or [] if set(i["types"]) == {"hbond", "salt_bridge"}][:4]:
        pose = left if item["side"] == "left" else right
        sentences.append(f"En la pose {pose}, con {item['residue']}, el puente salino y el enlace de hidrógeno se apoyan en los mismos "
                         f"átomos (ligando {item['ligand_atom']}, proteína {item['protein_atom']}): son dos criterios sobre un mismo "
                         "contacto, no dos contactos independientes.")
    species = facts.get("ligand_species") or {}
    ionic = sorted({kind for side in ("left", "right") for kind in (contacts.get(side) or {}).get("by_type", {}) if kind in _IONIC})
    if ionic and species.get("changed_from_input") is True:
        how = []
        if species.get("protonation_engine") and species.get("protonation_ph") is not None:
            how.append(f"protonación asignada con {species['protonation_engine']} a pH {str(species['protonation_ph']).replace('.', ',')}")
        if species.get("alternatives_not_evaluated"):
            how.append(f"{species['alternatives_not_evaluated']} alternativas sin evaluar")
        sentences.append(f"Los contactos iónicos ({', '.join(ionic)}) valen para la especie que se acopló, que MolDesign declara distinta "
                         f"de la entrada{' (' + '; '.join(how) + ')' if how else ''}; no prueban que esa especie predomine en el medio.")
    return " ".join(sentences)


def comparison_limits(facts: dict[str, Any]) -> str:
    """The physical status of each pose as MolDesign declares it, for the host to append to the answer.

    A model can call a pose valid when it did not pass; no check on numbers sees that. This is the lock's own
    sentence, added after the model's text so the two can be read together."""
    parts: list[str] = []
    for side in ("left", "right"):
        pose = facts["poses"][side]
        if not pose.get("found"):
            parts.append(f"pose {pose['rank']}: la corrida no la tiene" if "rank" in pose else "una pose: la corrida no la tiene")
            continue
        status = pose.get("physical_status") or "no evaluada"
        label = {"passed": "superó los controles físicos", "failed": "no superó los controles físicos",
                 "review": "quedó en revisión (no cuenta como válida)", "not_evaluated": "no tiene controles físicos evaluados"}.get(status, status)
        parts.append(f"pose {pose['rank']}: {label}")
    text = "Controles físicos según MolDesign — " + "; ".join(parts) + "."
    # What separates the two poses and what a silent contact list means are the lock's words too: a model can read
    # Vina's bounds as a confidence interval or an empty contact list as "no interaction", and no number check sees it.
    # The distance measured from the stored coordinates answers "how far apart are they"; Vina's bounds (which are
    # against its best pose) only speak when nothing was measured.
    measured = facts["difference"].get("pose_rmsd_between_poses")
    rmsd = measured if isinstance(measured, dict) and measured.get("available") else facts["difference"].get("vina_rmsd_between_poses")
    if isinstance(rmsd, dict) and rmsd.get("meaning"):
        text += " " + rmsd["meaning"]
    contacts = facts.get("contacts")
    if isinstance(contacts, dict) and contacts.get("caution"):
        text += " " + contacts["caution"]
    if reading := contact_reading(facts):
        text += " " + reading
    return text + " La energía de Vina no es afinidad medida y no se declara ganadora."


def evidence_values(facts: dict[str, Any]) -> dict[str, str]:
    """The short rows the interface shows for these facts."""
    values: dict[str, str] = {}
    for side in ("left", "right"):
        pose = facts["poses"][side]
        if not pose.get("found"):
            continue
        name = f"pose {pose['rank']}"
        if pose.get("vina_affinity_kcal_mol") is not None:
            values[f"{name}: energía de Vina (kcal/mol)"] = str(pose["vina_affinity_kcal_mol"])
        values[f"{name}: controles físicos"] = str(pose.get("physical_status") or "no evaluada")
        detail = pose.get("checks_detail") or []
        for result, label in (("passed", "superados"), ("failed", "que fallan"), ("not_evaluated", "no evaluados")):
            names = [item["check"] for item in detail if item["result"] == result]
            if names:
                values[f"{name}: controles {label}"] = ", ".join(names[:30])
        if not detail and (pose.get("checks_passed") is not None):
            values[f"{name}: detalle de los controles"] = f"no guardado; solo el recuento ({pose['checks_passed']} superados)"
    delta = facts["difference"]["right_minus_left_vina_kcal_mol"]
    if delta is not None:
        values["derecha − izquierda (kcal/mol)"] = str(delta)
    contacts = facts.get("contacts") or {}
    rmsd = facts["difference"].get("vina_rmsd_between_poses") or {}
    measured = facts["difference"].get("pose_rmsd_between_poses") or {}
    if measured.get("available") is True:
        values["RMSD entre las poses (Å, coordenadas)"] = str(measured["rmsd_angstrom"])
    if rmsd.get("available") is True:
        values["RMSD de Vina entre las poses (Å, cotas)"] = f"{rmsd['lower_bound_angstrom']} – {rmsd['upper_bound_angstrom']}"
    if contacts.get("status") == "ok":
        if contacts.get("conclusive") is False:
            values["contactos tipificados"] = "0 en alguna pose: no concluyente"
        values["contactos compartidos"] = str(contacts["shared_count"])
        if contacts.get("residues_in_both_count") is not None:
            values["residuos presentes en las dos poses"] = str(contacts["residues_in_both_count"])
        values["solo en la izquierda"] = str(contacts["only_left_count"])
        values["solo en la derecha"] = str(contacts["only_right_count"])
    return values


def compare_poses_tool(bridge: MolDesignBridge) -> Tool:
    """Read-only: what separates two poses of a finished run, with the contacts computed here."""
    async def compare(args: dict[str, Any]) -> dict[str, Any]:
        task_id = args["task_id"].strip()
        left, right = args["left"], args["right"]
        if not _TASK_ID.fullmatch(task_id):
            return {"status": "invalid", "message": "Identificador de tarea no válido."}
        if left == right:
            return {"status": "invalid", "message": "Elige dos poses distintas para compararlas."}
        if not getattr(bridge, "token", None):
            return {"status": "unavailable", "message": "Se necesita una sesión de MolDesign."}
        status, data = await _get(bridge, f"/evaluation/pose-comparison/{task_id}", {"left": left, "right": right})
        if data is None:
            return _refusal(status, task_id)
        if not isinstance(data, dict) or data.get("task_id") != task_id:
            return {"status": "unavailable", "message": "MolDesign devolvió una comparación incompatible."}
        facts = build_comparison_facts(task_id, data)
        both = facts["poses"]["left"].get("found") and facts["poses"]["right"].get("found")
        molecule_id = data.get("molecule_id")
        if args.get("contacts") == "omitir":
            facts["contacts"] = {"status": "skipped", "message": "El usuario pidió omitir los contactos."}
        elif not both:
            facts["contacts"] = {"status": "unavailable", "message": "Falta una de las dos poses; no hay contactos que comparar."}
        elif not isinstance(molecule_id, str) or not _MOLECULE_ID.fullmatch(molecule_id):
            facts["contacts"] = {"status": "unavailable", "message": "MolDesign no identificó la molécula de la corrida."}
        else:
            facts["contacts"] = await _contacts(bridge, task_id, molecule_id, left, right)
        return facts

    pose = {"type": "integer", "minimum": 1, "maximum": 20}
    schema = {"type": "object",
              "properties": {"task_id": {"type": "string", "maxLength": 128}, "left": pose, "right": pose,
                             "contacts": {"type": "string", "enum": ["incluir", "omitir"], "maxLength": 10}},
              "required": ["task_id", "left", "right"], "additionalProperties": False}
    return Tool("compare_poses", "Solo lectura. Compara dos poses (por su rango, 1 = la primera) de una evaluación terminada "
                "(task_id de evaluate_case): la energía de Vina de cada una y su diferencia, los controles físicos de PoseBusters, "
                "lo que dijo el selector de poses, y los contactos con el receptor de cada pose (compartidos y exclusivos, calculados "
                "con ProLIF en el equipo de la persona, unos segundos por pose). No elige ganadora. No inicia, cancela, reintenta ni "
                "guarda nada. Usa contacts «omitir» si solo hace falta la energía y la validez física.",
                schema, compare)
