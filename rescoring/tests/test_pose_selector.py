"""
tests/test_pose_selector.py

Tests de integracion del pose selector v0.6 (Fase 4): paridad de la ruta de
produccion (bloques PDBQT + PDB de proteina) contra la funcion canonica
puntuar_complejo() de scripts/ruta_c_fase3_calibracion.py sobre el split de
test congelado del dataset de pose selector.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pytest

_SIDECAR = Path(__file__).resolve().parent.parent  # rescoring/
_REPO = _SIDECAR.parent
sys.path.insert(0, str(_SIDECAR))
sys.path.insert(0, str(_REPO))
sys.path.insert(0, str(_REPO / "scripts"))

import molflex as mf  # noqa: E402
import ruta_c_fase1_5_v05 as v05  # noqa: E402
import ruta_c_fase1_6_v06 as v06  # noqa: E402
import ruta_c_fase3_calibracion as f3  # noqa: E402
from pose_selector.selector import PoseSelector  # noqa: E402

DATASET = _REPO / "data" / "pose_selector_dataset"
ARTIFACTOS = _SIDECAR / "artifacts"

#: Este modulo es una prueba de integracion contra un corpus congelado que NO
#: se versiona: el split del dataset y los dos arboles de poses suman decenas
#: de GB. En un clon limpio no existen, y hasta ahora la suite no se omitia:
#: reventaba con FileNotFoundError al abrir la primera pose, tumbando el paso
#: `Run rescoring contracts` de CI despues de que 224 pruebas ya habian pasado.
#: Se declara la dependencia y se omite el modulo entero cuando falta.
#:
#: La omision no es gratis: donde el corpus SI esta, exportar
#: RESCORING_EXIGE_CORPUS=1 convierte la ausencia en fallo, para que el
#: contrato no se pierda en silencio si el corpus desaparece de esa maquina.
_CORPUS = (
    DATASET,
    _REPO / "scripts" / ".work_molflex_v3",
    _REPO / "data" / "pdbbind" / "vina_redock_work",
)
_AUSENTES = [str(ruta.relative_to(_REPO)) for ruta in _CORPUS if not ruta.exists()]
if _AUSENTES:
    _MOTIVO = (
        "corpus local del pose selector ausente: " + ", ".join(_AUSENTES)
        + " (no versionado; ver la nota de este modulo)"
    )
    if os.environ.get("RESCORING_EXIGE_CORPUS") == "1":
        raise RuntimeError(_MOTIVO)
    pytest.skip(_MOTIVO, allow_module_level=True)


def _archivo_pose(r: dict) -> Path:
    """Ruta del archivo de poses por fuente (logica de
    scripts/ruta_c_fase3_5_decidibilidad.py::archivo_pose)."""
    if r["source"] == "flexible_redock":
        return _REPO / "data" / "pdbbind" / "vina_redock_work" / r["pid"] / (
            r["pid"] + "_out.pdbqt"
        )
    if r["source"] == "molflex":
        return _REPO / "scripts" / ".work_molflex_v3" / r["pid"] / (
            r["file_stem"] + ".pdbqt"
        )
    return _REPO / "tmp" / "ruta_a" / r["pid"] / r["file_stem"] / "out.pdbqt"


def _bloques_de(archivo: Path) -> list[str]:
    """Extrae los bloques MODEL del PDBQT de salida de Vina (uno por modelo)."""
    texto = archivo.read_text(encoding="utf-8")
    bloques: list[list[str]] = []
    actual: list[str] | None = None
    for l in texto.splitlines():
        if l.startswith("MODEL"):
            actual = []
        elif l.startswith("ENDMDL"):
            if actual is not None:
                bloques.append(actual)
            actual = None
        elif actual is not None:
            actual.append(l)
    return ["\n".join(b) for b in bloques]


@pytest.fixture(scope="module")
def selector():
    """PoseSelector cargado con los artefactos de produccion del sidecar."""
    return PoseSelector(
        str(ARTIFACTOS / "pose_selector_v06.xgb"),
        str(ARTIFACTOS / "pose_selector_v06_meta.json"),
    )


@pytest.fixture(scope="module")
def cache_v05():
    return v06.cargar_cache_v05()


def _comparar(pid: str, selector: PoseSelector, cache_v05: dict) -> tuple:
    """Ejecuta la ruta de produccion y la canonica para un pid del test.

    Devuelve (rank_produccion, rank_canonico, scores_prod, scores_canon,
    resultado, motivo).
    """
    regs = [r for r in v06.cargar_split("test") if r["pid"] == pid]
    recs = f3.registros_raw_224(regs, cache_v05)
    s_canon = f3.puntuar_complejo(recs)

    bloques, vinas = [], []
    for r in regs:
        modelos = _bloques_de(_archivo_pose(r))
        bloques.append(modelos[r["model_idx"]])
        vinas.append(r["vina_score"])
    target = v05.ruta_pdb_proteina(pid)
    assert target is not None and target.exists()
    resultado, motivo = selector.seleccionar_pose(bloques, vinas, str(target))
    if resultado is None:
        return None, None, None, s_canon, resultado, motivo
    return (resultado["selected_pose_rank"], int(np.argmax(s_canon)),
            np.array(resultado["pose_scores"]), s_canon, resultado, motivo)


class TestParidadConPuntuarComplejo:
    """Paridad de la ruta de produccion contra la referencia congelada."""

    def test_paridad_exacta_1ceb_un_run(self, selector, cache_v05):
        """Complejo de UN solo run (9 poses, flexible_redock): los 224
        features raw reproducen exactamente el contrato v0.5 (mismo set de
        atomos del receptor, misma semantica de varianza/rango y cluster),
        por lo que los scores deben coincidir EXACTAMENTE con
        puntuar_complejo() (tolerancia 1e-8)."""
        pid = "1ceb"
        rank_p, rank_c, s_p, s_c, resultado, motivo = _comparar(
            pid, selector, cache_v05
        )
        assert resultado is not None, f"selector degradado: {motivo}"
        assert len(resultado["pose_scores"]) == 9
        assert rank_p == rank_c
        max_dif = float(np.max(np.abs(s_p - s_c)))
        assert max_dif < 1e-8, f"scores distintos del canonico: {max_dif:.3e}"
        assert resultado["pose_selector_model"]

    def test_primer_pid_del_test_congelado_1a1e(self, selector, cache_v05):
        """Primer pid del test congelado (1a1e, 180 poses de 20 runs de
        molflex): la seleccion debe coincidir con puntuar_complejo().

        NOTA HONESTA: los scores NO son exactos en este caso porque
        pose_score_variance/range en el dataset congelado se computaron POR
        ARCHIVO (run) y la produccion los computa sobre el conjunto de
        poses del request (semantica v0.5 de "mismo set" = mismo run). El
        rank top-1 sigue siendo identico.
        """
        pid = "1a1e"
        rank_p, rank_c, s_p, s_c, resultado, motivo = _comparar(
            pid, selector, cache_v05
        )
        assert resultado is not None, f"selector degradado: {motivo}"
        assert len(resultado["pose_scores"]) == 180
        assert rank_p == rank_c, f"rank produccion {rank_p} vs canonico {rank_c}"
        # Los scores siguen el MISMO orden casi perfecto (Spearman ~0.99)
        # aunque los valores exactos difieran por la semantica de
        # varianza/rango (por archivo en el dataset vs por request en
        # produccion). Umbral 0.95: solo detecta un desorden real.
        from scipy.stats import spearmanr
        sp = spearmanr(s_p, s_c).correlation
        assert sp is not None and sp > 0.95, f"orden de scores distinto: {sp}"
        assert resultado["pose_selector_model"]

    def test_scores_y_margen_consistentes(self, selector, cache_v05):
        """El rank reportado es el argmax de pose_scores y el margen es
        top1 - top2."""
        pid = "1ceb"
        _, _, _, _, resultado, _ = _comparar(pid, selector, cache_v05)
        scores = np.array(resultado["pose_scores"])
        assert resultado["selected_pose_rank"] == int(np.argmax(scores))
        ordenados = np.sort(scores)[::-1]
        margen = float(ordenados[0] - ordenados[1])
        assert abs(resultado["pose_confidence"] - margen) < 1e-9
        assert resultado["pose_abstained"] == (
            margen < 0.097663
        )
