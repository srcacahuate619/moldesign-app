"""Pruebas puras del exportador de docking (sin correr Vina)."""
import importlib.util
import sys
from pathlib import Path

MOD = Path(__file__).resolve().parents[1] / "scene_export" / "build_docking_package.py"


def _mod():
    spec = importlib.util.spec_from_file_location("build_docking_package", MOD)
    m = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("build_docking_package", m)
    spec.loader.exec_module(m)
    return m


def test_separar_poses_con_afinidad(tmp_path):
    m = _mod()
    p = tmp_path / "poses.pdbqt"
    p.write_text(
        "MODEL 1\nREMARK VINA RESULT: -7.4 0.000 0.000\n"
        "HETATM    1  C1  LIG A   1       1.0   2.0   3.0\nENDMDL\n"
        "MODEL 2\nREMARK VINA RESULT: -6.2 1.000 1.500\n"
        "HETATM    1  C1  LIG A   1       2.0   3.0   4.0\nENDMDL\n",
        encoding="utf-8")
    poses = m._separar_poses(p)
    assert [x["afinidad"] for x in poses] == [-7.4, -6.2]
    assert all(len(x["lineas"]) == 1 for x in poses)


def test_pose_a_pdb_sin_cola_autodock(tmp_path):
    m = _mod()
    linea = ("HETATM   10  C2  BEN H 300       1.146  30.045  34.122"
             "  0.00  0.00    +0.123 C  ")
    salida = m._pose_a_pdb([linea])
    assert salida.splitlines()[0] == linea[:66]
    assert salida.endswith("END\n")


def test_rmsd_incluye_la_separacion_espacial(tmp_path):
    m = _mod()
    ref = {"C1": (0.0, 0.0, 0.0), "C2": (1.0, 0.0, 0.0), "N3": (0.0, 1.0, 0.0),
           "O4": (0.0, 0.0, 1.0)}
    # misma forma trasladada 10 A en x: el RMSD debe reflejar la distancia
    mov = {k: (x + 10.0, y, z) for k, (x, y, z) in ref.items()}
    r = m._rmsd_kabsch(ref, mov)
    assert r is not None and abs(r - 10.0) < 1e-4


def test_rmsd_desiste_si_el_emparejado_no_es_biunivoco(tmp_path):
    m = _mod()
    ref = {"A": (0, 0, 0), "B": (1, 0, 0), "C": (0, 1, 0), "D": (0, 0, 1)}
    mov = {"A": (0, 0, 0), "B": (1, 0, 0)}   # incompleto: no se inventa
    assert m._rmsd_kabsch(ref, mov) is None


def test_limite_atomos_dentro_de_caja():
    """El predicado de la caja: un átomo fuera basta para que la pose no se
    proponga nunca (Vina rechaza la pose entera)."""
    centro, tam = [0.0, 0.0, 0.0], [10.0, 10.0, 10.0]
    lo = [c - t / 2.0 for c, t in zip(centro, tam)]
    hi = [c + t / 2.0 for c, t in zip(centro, tam)]

    def dentro(coords):
        return all(lo[j] <= xyz[j] <= hi[j] for xyz in coords for j in range(3))

    assert dentro([[0.0, 0.0, 0.0], [4.9, -4.9, 4.9]])
    assert not dentro([[0.0, 0.0, 0.0], [6.0, 0.0, 0.0]])
