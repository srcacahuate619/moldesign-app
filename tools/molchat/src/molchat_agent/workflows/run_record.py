"""What MolDesign said about one run, kept for the notebook instead of being dropped after the number was read.

The iteration decides on two values (Vina's energy and the physical controls), but the job MolDesign returns carries
much more: the protocol it actually executed, the scientific warnings of the run, the species that was docked and
the receptor it was docked into. Until now all of it was read and thrown away, so the notebook could not say «you
wrote this SMILES and this other species was docked», nor which warnings each molecule had.

Nothing here is computed or interpreted: fields are copied from MolDesign's answer, bounded in size, and a field the
run did not persist stays ``None`` («not recorded»), never a default that looks measured.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from ..lang import tr

MAX_FIELD_CHARS = 20_000
MAX_WARNINGS = 40
MAX_TEXT = 500


def _bounded(value: Any) -> Any:
    """``value`` as is when it is JSON and small; otherwise a note with its size and hash, never a silent cut."""
    if value is None:
        return None
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return {"omitted": "no se pudo serializar"}
    if len(text) <= MAX_FIELD_CHARS:
        return json.loads(text)
    return {"omitted": f"demasiado grande para el cuaderno ({len(text)} caracteres)",
            "sha256": sha256(text.encode("utf-8")).hexdigest()}


def _text(value: Any) -> str | None:
    return value[:MAX_TEXT] if isinstance(value, str) and value.strip() else None


def _warnings(raw: Any) -> list[dict[str, str | None]] | None:
    """MolDesign's ``scientific_warnings``: ``{codigo, severidad, mensaje}``; older runs saved bare strings."""
    if not isinstance(raw, list):
        return None
    out: list[dict[str, str | None]] = []
    for item in raw[:MAX_WARNINGS]:
        if isinstance(item, dict):
            message = _text(item.get("mensaje") or item.get("message"))
            if message:
                out.append({"code": _text(item.get("codigo") or item.get("code")),
                            "severity": _text(item.get("severidad") or item.get("severity")), "message": message})
        elif _text(item):
            out.append({"code": None, "severity": tr("heredada", "legacy"), "message": _text(item)})
    if len(raw) > MAX_WARNINGS:
        more = len(raw) - MAX_WARNINGS
        out.append({"code": None, "severity": None, "message": tr(f"y {more} avisos más en MolDesign.",
                                                                   f"and {more} more warnings in MolDesign.")})
    return out


def _species(state: Any) -> dict[str, Any] | None:
    """The docked species in a few fields: what was written, what was docked in 3D and what changed on the way."""
    if not isinstance(state, dict):
        return None
    stereo = state.get("estereoquimica") if isinstance(state.get("estereoquimica"), dict) else {}
    proton = state.get("protonacion") if isinstance(state.get("protonacion"), dict) else {}
    tauto = state.get("tautomeria") if isinstance(state.get("tautomeria"), dict) else {}
    lost = stereo.get("perdida_en_la_especie_acoplada")
    return {
        "input_smiles": _text(state.get("smiles_entrada")),
        "docked_smiles_3d": _text(stereo.get("smiles_3d_efectivo")),
        "protonation": {"applied": proton.get("aplicada"), "ph": proton.get("ph"),
                        "alternatives": proton.get("alternativas"), "reason": _text(proton.get("motivo"))},
        "tautomer": {"applied": tauto.get("aplicada"), "alternatives": tauto.get("alternativas"),
                     "reason": _text(tauto.get("motivo"))},
        "stereo": {"unassigned_centers": stereo.get("centros_sin_asignar"),
                   "unassigned_double_bonds": stereo.get("dobles_sin_asignar"),
                   "declared_by_user": stereo.get("declarada_por_el_usuario"),
                   "lost_in_docked_species": lost if isinstance(lost, dict) else None},
    }


def _protocol(protocol: Any) -> dict[str, Any] | None:
    if not isinstance(protocol, dict):
        return None
    provenance = protocol.get("execution_provenance") if isinstance(protocol.get("execution_provenance"), dict) else {}
    return {"engine": protocol.get("engine"), "exhaustiveness": protocol.get("exhaustiveness"),
            "num_poses": protocol.get("num_poses"), "seed": protocol.get("seed"),
            "conformers": protocol.get("conformers_generated"), "requested": protocol.get("solicitado"),
            "box_center": provenance.get("box_center"), "box_size": provenance.get("box_size")}


def molecule_source(smiles: str, lookups: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Which PubChem lookup of this conversation the SMILES came from, by literal comparison and nothing else.

    ``lookups`` are ``{"query", "matches"}`` as the PubChem tool returned them. A SMILES equal to a compound's
    ``SMILES`` is an exact match; equal only to its ``ConnectivitySMILES`` means the plan used the structure without
    stereochemistry, which is said. Two compounds with that SMILES are ambiguous, and no match is ``None``: the
    notebook then says the source is not recorded, it does not guess one.
    """
    found: dict[int, dict[str, Any]] = {}
    for lookup in lookups:
        for match in lookup.get("matches") or []:
            if not isinstance(match, dict) or type(match.get("cid")) is not int:
                continue
            props = match.get("properties") if isinstance(match.get("properties"), dict) else {}
            if props.get("SMILES") == smiles:
                kind = "exact"
            elif props.get("ConnectivitySMILES") == smiles:
                kind = "connectivity_only"
            else:
                continue
            if match["cid"] not in found or kind == "exact":
                found[match["cid"]] = {"database": "PubChem", "cid": match["cid"], "name": _text(match.get("name")),
                                       "url": _text(match.get("source")), "query": _text(lookup.get("query")),
                                       "match": kind, "pubchem_smiles": _text(props.get("SMILES"))}
    if not found:
        return None
    if len(found) > 1:
        return {"database": "PubChem", "match": "ambiguous", "cids": sorted(found)}
    return next(iter(found.values()))


def record_from_result(result: Any) -> dict[str, Any] | None:
    """The record of one finished run, from the ``result`` of MolDesign's ``GET /evaluation/status``."""
    if not isinstance(result, dict):
        return None
    calibration = result.get("target_calibracion")
    return {
        "source": "MolDesign GET /evaluation/status",
        "vina_version": _text(result.get("vina_version")),
        "receptor_sha256": _text(result.get("receptor_sha256")),
        "protocol": _protocol(result.get("docking_protocol")),
        "warnings": _warnings(result.get("scientific_warnings")),
        "species": _species(result.get("ligand_state")),
        "receptor_calibration": _bounded(calibration) if isinstance(calibration, dict) else None,
        "raw": {"docking_protocol": _bounded(result.get("docking_protocol")),
                "ligand_state": _bounded(result.get("ligand_state"))},
    }
