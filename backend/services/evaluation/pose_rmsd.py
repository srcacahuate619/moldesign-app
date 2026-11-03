"""RMSD directo entre dos poses de una corrida, de las coordenadas del SDF guardado.

Las cotas `rmsd l.b.` y `rmsd u.b.` de Vina son contra la mejor pose de SU búsqueda, así que no dicen cuánto se
separan dos poses cualesquiera. Aquí se mide: RMSD de átomos pesados en el marco del receptor (sin superponer, porque
las poses ya están en él), con la correspondencia atómica del grafo de la molécula y, de las que el grafo permite,
la de menor distancia (átomos simétricamente equivalentes). Contraste con la corrida real de 8T69: el valor con el
mismo orden de átomos coincide con la cota superior de Vina de cada pose (4,259 Å y 2,438 Å) y queda dentro de sus
cotas.
"""
from __future__ import annotations

import math
from typing import Any

#: Un ligando muy simétrico tiene muchas correspondencias; más allá de esto se declara y no se sigue buscando.
MAX_MAPPINGS = 10000
METHOD = ("RMSD de átomos pesados en el marco del receptor, sin superponer; correspondencia atómica del grafo de la "
          "molécula y, entre las equivalentes por simetría, la de menor distancia (RDKit CalcRMS)")


def _unavailable(code: str, **extra: Any) -> dict[str, Any]:
    return {"available": False, "reason_code": code, "rmsd_angstrom": None, "rmsd_atom_order_angstrom": None,
            "heavy_atoms": None, **extra}


def rmsd_between_poses(sdf_content: str, left: int, right: int) -> dict[str, Any]:
    """Distancia entre las poses `left` y `right` (rangos 1..n del SDF); `available: false` con su motivo si no se puede."""
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign

    if left == right:
        return _unavailable("SAME_POSE")
    supplier = Chem.SDMolSupplier()
    supplier.SetData(sdf_content, removeHs=True)
    poses = list(supplier)
    for rank in (left, right):
        if rank > len(poses):
            return _unavailable("POSE_NOT_IN_SDF", poses_in_file=len(poses))
        if poses[rank - 1] is None or poses[rank - 1].GetNumConformers() == 0:
            return _unavailable("POSE_UNREADABLE")
    a, b = poses[left - 1], poses[right - 1]
    if a.GetNumAtoms() != b.GetNumAtoms() or a.GetNumAtoms() == 0:
        return _unavailable("POSES_NOT_THE_SAME_MOLECULE")
    try:
        symmetric = rdMolAlign.CalcRMS(b, a, maxMatches=MAX_MAPPINGS)
    except (RuntimeError, ValueError):
        return _unavailable("POSES_NOT_THE_SAME_MOLECULE")
    squared = 0.0
    for i in range(a.GetNumAtoms()):
        pa, pb = a.GetConformer().GetAtomPosition(i), b.GetConformer().GetAtomPosition(i)
        squared += (pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2 + (pa.z - pb.z) ** 2
    atom_order = math.sqrt(squared / a.GetNumAtoms())
    if not (math.isfinite(symmetric) and math.isfinite(atom_order)):
        return _unavailable("RMSD_NOT_FINITE")
    return {"available": True, "reason_code": None, "rmsd_angstrom": round(symmetric, 3),
            "rmsd_atom_order_angstrom": round(atom_order, 3), "heavy_atoms": a.GetNumAtoms(), "method": METHOD}
