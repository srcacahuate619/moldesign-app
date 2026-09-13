import pytest

from services.blockchain.certificate_context import generate_physiological_context


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        (None, "Descripción fisiológica no disponible para este receptor personalizado."),
        ("HEADER    G protein-coupled receptor", "Receptor Acoplado a Proteínas G"),
        ("HEADER    TYROSINE KINASE", "Proteína Quinasa"),
        ("HEADER    VIRAL PROTEASE", "Hidrolasa / Proteasa"),
        ("HEADER    POTASSIUM CHANNEL", "Canal Iónico"),
        ("HEADER    UNKNOWN PROTEIN", "Estructura proteica personalizada"),
    ],
)
def test_generate_physiological_context_keeps_existing_classification(headers, expected):
    assert expected in generate_physiological_context("7E2Y", headers)


def test_generate_physiological_context_preserves_keyword_priority():
    result = generate_physiological_context("7E2Y", "GPCR KINASE PROTEASE CHANNEL")

    assert "Receptor Acoplado a Proteínas G" in result
