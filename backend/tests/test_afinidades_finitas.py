"""SCORE-011: un dato inválido no se convierte en el mejor candidato."""
import pytest
from pydantic import ValidationError

from core.models import DockingPose, DockingResult
from scoring.normalizer import clamp_score, normalize_affinity


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), float("-inf")])
def test_resultado_rechaza_afinidad_no_finita(valor):
    with pytest.raises(ValidationError):
        DockingResult(
            best_affinity=valor,
            poses=[DockingPose(rank=1, affinity=-8.0, rmsd_lb=0.0, rmsd_ub=0.0)],
        )


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), float("-inf")])
def test_normalizador_rechaza_valor_no_finito(valor):
    with pytest.raises(ValueError):
        clamp_score(valor)
    with pytest.raises(ValueError):
        normalize_affinity(valor, heavy_atoms=30)


@pytest.mark.parametrize("valor", [float("nan"), float("inf"), float("-inf")])
def test_pose_rechaza_medidas_no_finitas(valor):
    with pytest.raises(ValidationError):
        DockingPose(rank=1, affinity=valor, rmsd_lb=0.0, rmsd_ub=0.0)
    with pytest.raises(ValidationError):
        DockingPose(rank=1, affinity=-8.0, rmsd_lb=valor, rmsd_ub=0.0)
