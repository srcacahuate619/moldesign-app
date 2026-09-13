"""
rescoring/pose_filter.py

Filtro geométrico de poses de docking.

Verifica que las poses generadas por Vina sean geométricamente razonables
antes de extraer features 3D. Una pose fuera del grid box o con clashes
severos produciría features basura → predicción basura.

3 checks:
  1. Distancia del centroide del ligando al centro del grid box
  2. Porcentaje de átomos pesados dentro del grid box
  3. Número de clashes estéricos (distancias < 1.5 Å a átomos de la proteína)

Nota: Este módulo procesa bloques PDBQT directamente.
No requiere RDKit — usa parsing simple de coordenadas.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from logger import get_logger

log = get_logger(__name__)


@dataclass
class PoseFilterConfig:
    """Configuración del filtro de poses."""

    max_centroid_distance: float = 12.0  # Å
    min_atoms_in_box_ratio: float = 0.7  # 70%
    max_clashes: int = 5
    clash_distance: float = 1.5  # Å
    # Grid box — must be set from the target configuration before use.
    # These are neutral zero defaults; the caller is responsible for providing
    # the correct values via override in ModelManager.predict().
    grid_center: tuple[float, float, float] = (0.0, 0.0, 0.0)
    grid_size: tuple[float, float, float] = (25.0, 25.0, 25.0)


class PoseFilter:
    """Filtro geométrico de poses de docking."""

    def __init__(self, settings=None):
        self.config = PoseFilterConfig()
        if settings:
            self.config.max_centroid_distance = settings.pose_filter_max_distance
            self.config.min_atoms_in_box_ratio = settings.pose_filter_min_atoms_in_box
            self.config.max_clashes = settings.pose_filter_max_clashes

    def filter_poses(self, poses: list, target_pdb_path: str | None = None) -> dict[str, Any]:
        """
        Filtrar lista de poses.

        Returns:
            dict con keys:
              - valid_poses: list de poses que pasaron los 3 checks
              - poses_passing: int
              - total: int
              - details: list[dict] con resultado por pose
        """
        results = []
        valid_poses = []

        prot_coords = []
        if target_pdb_path:
            try:
                with open(target_pdb_path, "r") as f:
                    for line in f:
                        if line.startswith(("ATOM", "HETATM")):
                            atom_name = line[12:16].strip()
                            if atom_name.startswith("H") or atom_name.startswith("D"):
                                continue
                            try:
                                x = float(line[30:38])
                                y = float(line[38:46])
                                z = float(line[46:54])
                                prot_coords.append((x, y, z))
                            except:
                                continue
            except Exception as e:
                log.warning("pose_filter_protein_load_failed", error=str(e), path=target_pdb_path)

        for i, pose in enumerate(poses):
            coords = self._extract_coordinates(pose.pdbqt_block)

            if len(coords) == 0:
                results.append({
                    "pose_index": i,
                    "passed": False,
                    "reason": "No se pudieron extraer coordenadas del PDBQT",
                    "vina_score": pose.vina_score,
                })
                continue

            coords_array = np.array(coords)

            # Check 1: Distancia del centroide al grid center
            centroid = coords_array.mean(axis=0)
            grid_center = np.array(self.config.grid_center)
            centroid_dist = float(np.linalg.norm(centroid - grid_center))

            check1_pass = centroid_dist <= self.config.max_centroid_distance

            # Check 2: % de átomos dentro del grid box
            half_size = np.array(self.config.grid_size) / 2.0
            box_min = grid_center - half_size
            box_max = grid_center + half_size
            in_box = np.all((coords_array >= box_min) & (coords_array <= box_max), axis=1)
            atoms_in_box_ratio = float(in_box.sum() / len(coords_array))

            check2_pass = atoms_in_box_ratio >= self.config.min_atoms_in_box_ratio

            # Check 3: clashes reales
            check3_pass = True
            n_clashes = 0
            if len(prot_coords) > 0 and len(coords_array) > 0:
                prot_coords_arr = np.array(prot_coords)
                for lig_atom in coords_array:
                    dists = np.linalg.norm(prot_coords_arr - lig_atom, axis=1)
                    clashes = np.sum(dists < self.config.clash_distance)
                    n_clashes += int(clashes)
                check3_pass = n_clashes <= self.config.max_clashes

            all_pass = check1_pass and check2_pass and check3_pass

            results.append({
                "pose_index": i,
                "passed": all_pass,
                "centroid_distance": round(centroid_dist, 2),
                "atoms_in_box_ratio": round(atoms_in_box_ratio, 3),
                "n_clashes": n_clashes,
                "vina_score": pose.vina_score,
                "checks": {
                    "centroid": check1_pass,
                    "atoms_in_box": check2_pass,
                    "clashes": check3_pass,
                },
            })

            if all_pass:
                valid_poses.append(pose)

        n_passing = len(valid_poses)
        total = len(poses)

        if n_passing < total:
            log.info(
                "pose_filter_result",
                passing=n_passing,
                total=total,
                rejected=total - n_passing,
            )

        return {
            "valid_poses": valid_poses,
            "poses_passing": n_passing,
            "total": total,
            "details": results,
        }

    def _extract_coordinates(self, pdbqt_block: str) -> list[tuple[float, float, float]]:
        """
        Extraer coordenadas de átomos pesados de un bloque PDBQT.

        Formato PDBQT (columnas fijas):
          ATOM      1  C1  LIG A   1      -22.228  -0.583 -29.375  1.00  0.00    0.000 C
          cols:     0-5  6-10  12-15  ...  30-37    38-45  46-53  ...

        Solo extraer átomos pesados (no H).
        """
        coords = []
        for line in pdbqt_block.split("\n"):
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                continue
            # En PDBQT, el tipo de átomo está al final (columna 77+)
            atom_type = line[77:79].strip() if len(line) > 77 else ""
            # Skip hydrogens
            if atom_type == "H" or atom_type == "HD":
                continue
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
                coords.append((x, y, z))
            except (ValueError, IndexError):
                continue

        return coords
