"""DOCK-020: correspondencia de cada SDF con su bloque PDBQT."""

import pytest

from services.docking.pose_recovery import PoseNoRecuperable, verificar_pares_sdf_pdbqt


def _sdf_pose(x: float) -> str:
    return (f"pose\n  Meeko\n\n  1  0  0  0  0  0            999 V2000\n"
            f"{x:10.4f}{0.0:10.4f}{0.0:10.4f} C   0  0  0  0  0  0  0  0  0  0  0  0\n"
            "M  END\n$$$$\n")


def _pdbqt_pose(x: float) -> str:
    return ("MODEL 1\n" +
            f"ATOM      1  C1  LIG A   1    {x:8.3f}{0.0:8.3f}{0.0:8.3f}  1.00  0.00      0.000 C\n" +
            "ENDMDL\n")


def test_pares_identicos_y_ordenados_pasan():
    assert verificar_pares_sdf_pdbqt(
        _sdf_pose(0.0) + _sdf_pose(10.0),
        [_pdbqt_pose(0.0), _pdbqt_pose(10.0)],
    ) == [0.0, 0.0]


def test_poses_intercambiadas_con_igual_afinidad_se_abstienen():
    with pytest.raises(PoseNoRecuperable, match="otra geometría"):
        verificar_pares_sdf_pdbqt(
            _sdf_pose(10.0) + _sdf_pose(0.0),
            [_pdbqt_pose(0.0), _pdbqt_pose(10.0)],
        )


def test_cuenta_truncada_se_abstiene():
    with pytest.raises(PoseNoRecuperable, match="recuentos diferentes"):
        verificar_pares_sdf_pdbqt(_sdf_pose(0.0), [_pdbqt_pose(0.0), _pdbqt_pose(10.0)])
