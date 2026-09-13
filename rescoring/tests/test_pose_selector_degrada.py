"""
tests/test_pose_selector_degrada.py

Degradacion elegante del pose selector (Fase 4): un artefacto ausente o
entradas invalidas deben devolver (None, motivo) — NUNCA una excepcion que
rompa el flujo del sidecar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SIDECAR = Path(__file__).resolve().parent.parent  # rescoring/
sys.path.insert(0, str(_SIDECAR))

from pose_selector.selector import PoseSelector  # noqa: E402

_BLOQUE_VALIDO = "\n".join([
    "MODEL 1",
    "REMARK VINA RESULT:    -7.1      0.000      0.000",
    "ATOM      1  C1  UNL     1      1.000   2.000   3.000  1.00  0.00    C",
    "ATOM      2  C2  UNL     1      1.500   2.200   3.100  1.00  0.00    C",
    "ENDMDL",
]) + "\n"


class TestPoseSelectorDegrada:
    """El selector degrada con motivo, sin propagar excepciones."""

    def test_modelo_inexistente_devuelve_none_con_motivo(self, tmp_path):
        """Artefactos ausentes: la construccion NO lanza y
        seleccionar_pose devuelve (None, motivo)."""
        sel = PoseSelector(
            str(tmp_path / "no_existe.xgb"),
            str(tmp_path / "no_existe.json"),
        )
        assert sel.load_error is not None
        resultado, motivo = sel.seleccionar_pose(
            [_BLOQUE_VALIDO, _BLOQUE_VALIDO],
            [-7.0, -6.5],
            str(tmp_path / "target.pdb"),
        )
        assert resultado is None
        assert motivo

    def test_pdb_inexistente_devuelve_none_con_motivo(self):
        """Selector cargado pero PDB de la proteina ilegible: degrada con
        motivo (no lanza)."""
        sel = PoseSelector(
            str(_SIDECAR / "artifacts" / "pose_selector_v06.xgb"),
            str(_SIDECAR / "artifacts" / "pose_selector_v06_meta.json"),
        )
        assert sel.load_error is None
        resultado, motivo = sel.seleccionar_pose(
            [_BLOQUE_VALIDO, _BLOQUE_VALIDO],
            [-7.0, -6.5],
            str(Path("no_existe_target.pdb")),
        )
        assert resultado is None
        assert motivo

    def test_bloques_vacios_devuelve_none_con_motivo(self):
        """Bloques sin atomos: degrada con motivo (no lanza)."""
        sel = PoseSelector(
            str(_SIDECAR / "artifacts" / "pose_selector_v06.xgb"),
            str(_SIDECAR / "artifacts" / "pose_selector_v06_meta.json"),
        )
        resultado, motivo = sel.seleccionar_pose(
            ["", "MODEL 1\nENDMDL\n"],
            [-7.0, -6.5],
            str(Path("no_existe_target.pdb")),
        )
        assert resultado is None
        assert motivo

    def test_longitudes_inconsistentes_devuelve_none_con_motivo(self):
        """n poses != n scores: degrada con motivo (no lanza)."""
        sel = PoseSelector(
            str(_SIDECAR / "artifacts" / "pose_selector_v06.xgb"),
            str(_SIDECAR / "artifacts" / "pose_selector_v06_meta.json"),
        )
        resultado, motivo = sel.seleccionar_pose(
            [_BLOQUE_VALIDO, _BLOQUE_VALIDO],
            [-7.0],
            str(Path("no_existe_target.pdb")),
        )
        assert resultado is None
        assert motivo

    def test_sin_poses_devuelve_none_con_motivo(self):
        """Lista vacia: degrada con motivo (no lanza)."""
        sel = PoseSelector(
            str(_SIDECAR / "artifacts" / "pose_selector_v06.xgb"),
            str(_SIDECAR / "artifacts" / "pose_selector_v06_meta.json"),
        )
        resultado, motivo = sel.seleccionar_pose(
            [], [], str(Path("no_existe_target.pdb"))
        )
        assert resultado is None
        assert motivo
