"""Comparar la pose de UNA molécula entre dos evaluaciones (corridas) distintas.

`pose_comparison.compare_two_poses` compara dos poses de una misma corrida. Esto responde otra pregunta, la de
quien reevalúa: ¿cambió la pose al cambiar la semilla, la exhaustividad o el receptor preparado?

Reglas, en el orden en que protegen:

1. **Sólo la misma molécula.** Entre moléculas distintas no hay una correspondencia atómica total, y un RMSD
   «entre análogos» sería inventado. El endpoint lo exige; aquí, si el grafo pesado no coincide, se abstiene.
2. **Sólo en el mismo marco.** Las coordenadas de una pose viven en el marco del receptor preparado. Con otro
   `receptor_sha256` (o sin declarar) el RMSD no significa nada y se abstiene; la energía sigue enseñándose, aparte.
3. **Lo que difiere entre las dos corridas se nombra** (semilla, exhaustividad, poses, motor, receptor, especie
   acoplada): sin eso, una distancia de 3 Å no se puede leer.
4. **No elige ganadora.**
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from typing import Any

from services.evaluation.pose_comparison import compare_two_poses

#: Ligandos con mucha simetría tienen muchas correspondencias; más allá se declara y no se sigue.
MAX_MAPPINGS = 10000
METHOD = ("RMSD de átomos pesados en el marco del receptor, sin superponer, entre la pose de una corrida y la de "
          "otra; correspondencia atómica del grafo y, entre las equivalentes por simetría, la de menor distancia "
          "(RDKit CalcRMS)")

#: (campo, dónde se lee). Lo que se enseña cuando difiere.
_PROTOCOL_FIELDS = ("engine", "exhaustiveness", "num_poses", "conformers_generated")


def _unavailable(code: str, **extra: Any) -> dict[str, Any]:
    return {"available": False, "reason_code": code, "rmsd_angstrom": None, "heavy_atoms": None, **extra}


def rmsd_between_sdfs(sdf_a: str, rank_a: int, sdf_b: str, rank_b: int) -> dict[str, Any]:
    """RMSD de la pose `rank_a` del SDF A contra la `rank_b` del SDF B (rangos 1..n). No lanza: abstiene con motivo."""
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign

    def pose(content: str, rank: int):
        supplier = Chem.SDMolSupplier()
        supplier.SetData(content, removeHs=True)
        poses = list(supplier)
        if rank < 1 or rank > len(poses):
            return None, "POSE_NOT_IN_SDF"
        chosen = poses[rank - 1]
        if chosen is None or chosen.GetNumConformers() == 0:
            return None, "POSE_UNREADABLE"
        return chosen, None

    a, reason = pose(sdf_a, rank_a)
    if a is None:
        return _unavailable(reason, side="a")
    b, reason = pose(sdf_b, rank_b)
    if b is None:
        return _unavailable(reason, side="b")
    if a.GetNumAtoms() != b.GetNumAtoms() or a.GetNumAtoms() == 0:
        return _unavailable("NOT_THE_SAME_MOLECULE")
    try:
        value = rdMolAlign.CalcRMS(b, a, maxMatches=MAX_MAPPINGS)
    except (RuntimeError, ValueError):
        return _unavailable("NOT_THE_SAME_MOLECULE")
    if not math.isfinite(value):
        return _unavailable("RMSD_NOT_FINITE")
    return {"available": True, "reason_code": None, "rmsd_angstrom": round(value, 3),
            "heavy_atoms": a.GetNumAtoms(), "method": METHOD}


def _get(source: Any, key: str) -> Any:
    return source.get(key) if isinstance(source, Mapping) else None


def protocol_differences(result_a: Mapping[str, Any] | None, result_b: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Qué difiere entre las dos corridas, con ambos valores. Lo no declarado en una de ellas también cuenta."""
    protocol_a, protocol_b = _get(result_a, "docking_protocol"), _get(result_b, "docking_protocol")
    rows: list[tuple[str, Any, Any]] = [
        ("receptor_sha256", _get(result_a, "receptor_sha256"), _get(result_b, "receptor_sha256")),
        ("seed", _get(result_a, "vina_random_seed"), _get(result_b, "vina_random_seed")),
    ]
    rows += [(field, _get(protocol_a, field), _get(protocol_b, field)) for field in _PROTOCOL_FIELDS]
    state_a, state_b = _get(result_a, "ligand_state"), _get(result_b, "ligand_state")
    protonation_a = _get(state_a, "protonacion") if isinstance(state_a, Mapping) else None
    protonation_b = _get(state_b, "protonacion") if isinstance(state_b, Mapping) else None
    rows.append(("protonation_ph", _get(protonation_a, "ph"), _get(protonation_b, "ph")))
    return [{"field": field, "a": a, "b": b} for field, a, b in rows if a != b]


def frame_status(result_a: Mapping[str, Any] | None, result_b: Mapping[str, Any] | None) -> str:
    """`same` sólo si las dos corridas declaran el mismo receptor preparado; si no, el RMSD no tiene marco común."""
    sha_a, sha_b = _get(result_a, "receptor_sha256"), _get(result_b, "receptor_sha256")
    if not sha_a or not sha_b:
        return "undeclared"
    return "same" if sha_a == sha_b else "different"


def compare_runs(result_a: Mapping[str, Any] | None, result_b: Mapping[str, Any] | None, rank_a: int, rank_b: int,
                 rmsd: dict[str, Any]) -> dict[str, Any]:
    """Une la energía y los controles de cada pose, la distancia (ya medida o abstenida) y lo que difiere."""
    pose_a = compare_two_poses(result_a, rank_a, rank_a)["left"]
    pose_b = compare_two_poses(result_b, rank_b, rank_b)["left"]
    frame = frame_status(result_a, result_b)
    both = pose_a["found"] and pose_b["found"]
    delta = None
    if both and pose_a["vina_affinity_kcal_mol"] is not None and pose_b["vina_affinity_kcal_mol"] is not None:
        delta = round(pose_b["vina_affinity_kcal_mol"] - pose_a["vina_affinity_kcal_mol"], 3)
    if frame != "same":
        rmsd = _unavailable("DIFFERENT_RECEPTOR" if frame == "different" else "RECEPTOR_NOT_DECLARED")
    return {
        "a": pose_a, "b": pose_b,
        "frame": frame,
        "difference": {"b_minus_a_vina_kcal_mol": delta, "pose_rmsd_between_runs": rmsd},
        "protocol_differences": protocol_differences(result_a, result_b),
    }


# ── Análogos: ligandos distintos en el mismo marco del receptor ─────────────────────────────────────────────────

#: Convenciones de presentación (no umbrales validados): por debajo de esto el «núcleo común» es demasiado pequeño
#: para que su distancia diga algo sobre cómo se coloca la molécula.
MIN_CORE_HEAVY_ATOMS = 6
MIN_CORE_FRACTION = 0.5
#: Correspondencias núcleo-núcleo que se prueban (simetría); más allá se declara y se mide con las probadas.
MAX_CORE_MAPPINGS = 10000
MCS_TIMEOUT_S = 2


def _read_poses(content: str) -> list:
    """Las poses de un SDF, con sus hidrógenos. Una pose ilegible queda como `None` en su sitio, no desaparece."""
    from rdkit import Chem

    supplier = Chem.SDMolSupplier()
    supplier.SetData(content, removeHs=False)
    return list(supplier)


def _load_pose(content: str, rank: int):
    """La pose `rank` (1..n): `((átomos pesados, molécula completa), None)` o `(None, motivo)`.

    Cada átomo de la molécula pesada lleva `_sdf_index`, su posición (desde 0) en el registro del SDF con hidrógenos:
    es el índice con el que el visor 3D numera los átomos de ese modelo, y lo que permite decirle cuáles son del núcleo.
    """
    from rdkit import Chem

    poses = _read_poses(content)
    if rank < 1 or rank > len(poses):
        return None, "POSE_NOT_IN_SDF"
    return _prepare_pose(poses[rank - 1], Chem)


def _prepare_pose(full, Chem):
    if full is None or full.GetNumConformers() == 0:
        return None, "POSE_UNREADABLE"
    for atom in full.GetAtoms():
        atom.SetIntProp("_sdf_index", atom.GetIdx())
    # Lo mismo que hace `SDMolSupplier(removeHs=True)`: así la distancia no cambia respecto a la medida de siempre.
    return (Chem.RemoveHs(full), full), None


def _core_pattern(a, b):
    """El núcleo común máximo de dos moléculas (anillos completos): `((patrón, info), None)` o `(None, ausencia)`.

    Sólo depende del grafo, no de las coordenadas: sirve para todas las poses de la misma pareja de moléculas.
    """
    from rdkit import Chem
    from rdkit.Chem import rdFMCS

    try:
        mcs = rdFMCS.FindMCS([a, b], timeout=MCS_TIMEOUT_S, ringMatchesRingOnly=True, completeRingsOnly=True)
    except Exception:  # noqa: BLE001 - sin núcleo no hay medida, pero la comparación sigue valiendo
        return None, _unavailable("CORE_SEARCH_FAILED")
    smaller = min(a.GetNumAtoms(), b.GetNumAtoms())
    info = {"core_heavy_atoms": mcs.numAtoms, "heavy_atoms_a": a.GetNumAtoms(), "heavy_atoms_b": b.GetNumAtoms(),
            "core_fraction_of_smaller": round(mcs.numAtoms / smaller, 3) if smaller else None,
            "core_search_complete": not mcs.canceled}
    if mcs.numAtoms < MIN_CORE_HEAVY_ATOMS or smaller == 0 or mcs.numAtoms / smaller < MIN_CORE_FRACTION:
        return None, _unavailable("CORE_TOO_SMALL", **info)
    return (Chem.MolFromSmarts(mcs.smartsString), info), None


def _best_core_mapping(a, b, pattern):
    """La correspondencia núcleo-núcleo de menor distancia, sin superponer: `(rmsd, probadas, (ma, mb))` o `None`."""
    import numpy as np

    matches_a = a.GetSubstructMatches(pattern, uniquify=False, maxMatches=MAX_CORE_MAPPINGS)
    matches_b = b.GetSubstructMatches(pattern, uniquify=False, maxMatches=MAX_CORE_MAPPINGS)
    if not matches_a or not matches_b:
        return None
    pos_a, pos_b = a.GetConformer().GetPositions(), b.GetConformer().GetPositions()
    best = math.inf
    best_pair = None
    tested = 0
    for ma in matches_a:
        coords_a = pos_a[list(ma)]
        for mb in matches_b:
            tested += 1
            if tested > MAX_CORE_MAPPINGS:
                break
            diff = coords_a - pos_b[list(mb)]
            value = float(np.sqrt((diff ** 2).sum(axis=1).mean()))
            if value < best:
                best, best_pair = value, (ma, mb)
        if tested > MAX_CORE_MAPPINGS:
            break
    return best, tested, best_pair


def _core_atoms_in_sdf(heavy, full, match) -> list[int]:
    """Los átomos de una pose que son del núcleo, con el índice del registro SDF: los pesados de la correspondencia y
    los hidrógenos que cuelgan de ellos (un H de un sustituyente no es del núcleo)."""
    originals = [heavy.GetAtomWithIdx(i).GetIntProp("_sdf_index") for i in match]
    core = set(originals)
    for index in originals:
        core.update(n.GetIdx() for n in full.GetAtomWithIdx(index).GetNeighbors() if n.GetAtomicNum() == 1)
    return sorted(core)


def rmsd_core_between_sdfs(sdf_a: str, rank_a: int, sdf_b: str, rank_b: int) -> dict[str, Any]:
    """RMSD del NÚCLEO COMÚN de dos ligandos distintos, en el marco del receptor (sin superponer).

    El núcleo es la subestructura común máxima (RDKit `rdFMCS`, anillos completos). Se mide sobre sus átomos pesados,
    con la correspondencia de menor distancia entre las equivalentes por simetría. No es el RMSD de la molécula
    entera: los sustituyentes que no están en el núcleo no entran. Se abstiene si el núcleo es pequeño.

    Con distancia disponible devuelve también `core_atoms`: qué átomos de cada pose (índice del registro SDF, desde 0,
    con sus hidrógenos) son de ese núcleo, para que el visor 3D distinga el núcleo de lo que cambia.
    """
    a, reason = _load_pose(sdf_a, rank_a)
    if a is None:
        return _unavailable(reason, side="a")
    b, reason = _load_pose(sdf_b, rank_b)
    if b is None:
        return _unavailable(reason, side="b")
    (heavy_a, full_a), (heavy_b, full_b) = a, b
    found, absence = _core_pattern(heavy_a, heavy_b)
    if found is None:
        return absence
    pattern, info = found
    mapping = _best_core_mapping(heavy_a, heavy_b, pattern)
    if mapping is None:
        return _unavailable("CORE_NOT_MAPPABLE", **info)
    best, tested, best_pair = mapping
    if not math.isfinite(best):
        return _unavailable("RMSD_NOT_FINITE", **info)
    core_a = _core_atoms_in_sdf(heavy_a, full_a, best_pair[0])
    core_b = _core_atoms_in_sdf(heavy_b, full_b, best_pair[1])
    return {"available": True, "reason_code": None, "rmsd_angstrom": round(best, 3), "heavy_atoms": info["core_heavy_atoms"],
            "mappings_tested": tested, "mappings_truncated": tested > MAX_CORE_MAPPINGS, **info,
            "core_atoms": {"a": core_a, "b": core_b, "index_basis": "sdf_atom_index_zero_based"},
            "method": ("RMSD de los átomos pesados del núcleo común máximo (RDKit FMCS, anillos completos), en el marco "
                       "del receptor, sin superponer; entre las correspondencias equivalentes, la de menor distancia")}


#: Cuántas poses de la otra evaluación se miden como máximo.
MAX_MATCH_POSES = 100


def pose_matches(sdf_a: str, rank_a: int, sdf_b: str, *, kind: str) -> dict[str, Any]:
    """¿Cuál de las poses de B se parece más a la pose `rank_a` de A? RMSD contra CADA una, en el marco del receptor.

    `kind="molecule"`: la misma molécula, RMSD de todos sus átomos pesados (como `rmsd_between_sdfs`).
    `kind="core"`: ligandos distintos, RMSD del núcleo común; el núcleo se busca una vez (sólo depende del grafo) y se
    mide en cada pose. Se abstiene con motivo si el núcleo es pequeño. No elige ganadora: nombra la más cercana.
    """
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign

    def unavailable(code: str, **extra: Any) -> dict[str, Any]:
        return {"available": False, "reason_code": code, "kind": kind, "matches": [], "closest_rank": None,
                "closest_rmsd_angstrom": None, **extra}

    a, reason = _load_pose(sdf_a, rank_a)
    if a is None:
        return unavailable(reason, side="a")
    poses_b = _read_poses(sdf_b)[:MAX_MATCH_POSES]
    if not poses_b:
        return unavailable("POSE_NOT_IN_SDF", side="b")
    heavy_a = a[0]
    prepared = [_prepare_pose(full, Chem) for full in poses_b]
    reference = next((pair for pair, _ in prepared if pair is not None), None)
    if reference is None:
        return unavailable("POSE_UNREADABLE", side="b")

    pattern = None
    info: dict[str, Any] = {}
    if kind == "core":
        found, absence = _core_pattern(heavy_a, reference[0])
        if found is None:
            return unavailable(absence["reason_code"], **{k: v for k, v in absence.items()
                                                          if k not in ("available", "reason_code", "rmsd_angstrom", "heavy_atoms")})
        pattern, info = found

    matches = []
    for rank, (pair, why) in enumerate(prepared, start=1):
        if pair is None:
            matches.append({"rank": rank, "available": False, "reason_code": why, "rmsd_angstrom": None})
            continue
        heavy_b = pair[0]
        try:
            if kind == "core":
                mapping = _best_core_mapping(heavy_a, heavy_b, pattern)
                value = mapping[0] if mapping else math.inf
            elif heavy_a.GetNumAtoms() != heavy_b.GetNumAtoms() or heavy_a.GetNumAtoms() == 0:
                matches.append({"rank": rank, "available": False, "reason_code": "NOT_THE_SAME_MOLECULE", "rmsd_angstrom": None})
                continue
            else:
                value = rdMolAlign.CalcRMS(heavy_b, heavy_a, maxMatches=MAX_MAPPINGS)
        except (RuntimeError, ValueError):
            value = math.inf
        if not math.isfinite(value):
            matches.append({"rank": rank, "available": False, "reason_code": "RMSD_NOT_FINITE", "rmsd_angstrom": None})
        else:
            matches.append({"rank": rank, "available": True, "reason_code": None, "rmsd_angstrom": round(value, 3)})
    measured = [m for m in matches if m["available"]]
    closest = min(measured, key=lambda m: (m["rmsd_angstrom"], m["rank"])) if measured else None
    return {"available": bool(measured), "reason_code": None if measured else "NO_POSE_MEASURABLE", "kind": kind,
            "matches": matches, "closest_rank": closest["rank"] if closest else None,
            "closest_rmsd_angstrom": closest["rmsd_angstrom"] if closest else None, **info}


def compare_analogs(result_a: Mapping[str, Any] | None, result_b: Mapping[str, Any] | None, rank_a: int, rank_b: int,
                    core: dict[str, Any]) -> dict[str, Any]:
    """Dos ligandos del mismo caso: energía y controles de cada pose, distancia del núcleo y lo que difiere.

    El marco común lo da el receptor preparado; sin él, el RMSD del núcleo se abstiene. La diferencia de afinidad entre
    moléculas distintas sólo es comparable si el protocolo es el mismo: `affinity_delta_comparable` lo dice.
    """
    pose_a = compare_two_poses(result_a, rank_a, rank_a)["left"]
    pose_b = compare_two_poses(result_b, rank_b, rank_b)["left"]
    frame = frame_status(result_a, result_b)
    both = pose_a["found"] and pose_b["found"]
    delta = None
    if both and pose_a["vina_affinity_kcal_mol"] is not None and pose_b["vina_affinity_kcal_mol"] is not None:
        delta = round(pose_b["vina_affinity_kcal_mol"] - pose_a["vina_affinity_kcal_mol"], 3)
    if frame != "same":
        core = _unavailable("DIFFERENT_RECEPTOR" if frame == "different" else "RECEPTOR_NOT_DECLARED")
    differences = protocol_differences(result_a, result_b)
    return {
        "a": pose_a, "b": pose_b, "frame": frame,
        "difference": {"b_minus_a_vina_kcal_mol": delta, "core_rmsd": core,
                       "affinity_delta_comparable": not differences},
        "protocol_differences": differences,
    }
