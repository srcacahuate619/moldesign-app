"""Contrato canónico de clasificación de selectividad."""

from __future__ import annotations

import pytest

from services.docking.selectivity_verdict import selectivity_verdict


@pytest.mark.parametrize(
    ("ratio", "expected"),
    [
        (None, "Sin datos suficientes"),
        (10.01, "ALTAMENTE SELECTIVO - Excelente perfil de seguridad"),
        (10.0, "SELECTIVO - Buen margen terapeutico"),
        (3.0, "MODERADAMENTE SELECTIVO - Monitorear off-targets"),
        (1.5, "BAJA SELECTIVIDAD - Riesgo de efectos secundarios"),
        (1.0, "NO SELECTIVO - La molecula prefiere anti-targets. ALTO RIESGO"),
    ],
)
def test_selectivity_verdict_preserves_thresholds_and_persisted_text(
    ratio: float | None, expected: str
):
    assert selectivity_verdict(ratio) == expected
