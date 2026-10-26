"""SCI-A-008: la validez física de la metodología, sin depender de pypdf.

Las pruebas que LEEN el PDF viven en `test_informe_vs_dossier_identidad.py`, que
necesita `pypdf` y por tanto se salta entera con el intérprete que se distribuye.
Lo que se entrega tiene que poder verificarse con lo que se entrega
(restricción 1 de `AGENTS.md`), así que la frase condicional y su traducción se
comprueban aquí, donde python-embed sí las ejecuta.
"""

from __future__ import annotations

import pytest

LIMITE_EXTERNO = "debe documentarse antes de cálculos posteriores"
FRASE_FALSA = "no evaluada en esta versión de producción"


@pytest.fixture
def frase():
    from services.blockchain.pdf_generator import _frase_de_validez_fisica_en_metodologia

    return _frase_de_validez_fisica_en_metodologia


class TestLaFraseEsCondicional:
    """La frase describe ESTA corrida, no la versión del producto."""

    @pytest.mark.parametrize(
        "resumen",
        [
            {},
            {"physical_validity": None},
            {"physical_validity": {"status": None}},
            {"physical_validity": {"status": "not_evaluated", "label": "NO EVALUADA"}},
        ],
    )
    def test_sin_veredicto_lo_declara_sin_hablar_de_las_poses(self, frase, resumen):
        texto = frase(resumen)
        assert "no llegaron a emitir veredicto" in texto
        assert "esa ausencia no habla de las poses" in texto
        assert FRASE_FALSA not in texto

    @pytest.mark.parametrize(
        ("estado", "etiqueta"),
        [
            ("passed", "CONTROLES SUPERADOS"),
            ("review", "REVISIÓN NECESARIA"),
            ("failed", "CONTROLES FALLIDOS"),
        ],
    )
    def test_con_veredicto_nombra_el_estado_y_no_lo_niega(self, frase, estado, etiqueta):
        texto = frase({"physical_validity": {"status": estado, "label": etiqueta}})
        assert etiqueta in texto
        assert "emitieron veredicto" in texto
        assert FRASE_FALSA not in texto
        assert "no llegaron a emitir veredicto" not in texto

    def test_superar_los_controles_nunca_se_presenta_como_validez_experimental(self, frase):
        texto = frase({"physical_validity": {"status": "passed", "label": "CONTROLES SUPERADOS"}})
        assert "no demuestra validez experimental" in texto
        assert "descarta artefactos de preparación" in texto

    def test_el_limite_del_analisis_externo_sobrevive_en_las_dos_ramas(self, frase):
        assert LIMITE_EXTERNO in frase({})
        assert LIMITE_EXTERNO in frase(
            {"physical_validity": {"status": "review", "label": "REVISIÓN NECESARIA"}}
        )


class TestLaFraseLlegaEnIngles:
    """`traducir` es todo-o-nada por frase: una sin pareja deja el párrafo en castellano."""

    @pytest.mark.parametrize(
        "resumen",
        [
            {},
            {"physical_validity": {"status": "review", "label": "REVIEW REQUIRED"}},
        ],
    )
    def test_las_dos_ramas_tienen_pareja_inglesa(self, frase, resumen):
        from core.i18n_plantillas import traducir

        castellano = frase(resumen)
        ingles = traducir(castellano, "en")
        assert ingles != castellano, "la frase se quedaría en castellano en el informe inglés"
        assert "Physical validity:" in ingles
        assert "External geometric analysis should be documented" in ingles
        for resto in ("Validez física", "El análisis geométrico", "veredicto"):
            assert resto not in ingles

    def test_el_parrafo_completo_de_la_metodologia_sigue_teniendo_plantilla(self, frase):
        """El párrafo se traduce como una unidad; `{frase1}` no puede romperla."""
        from core.i18n_plantillas import traducir

        parrafo = (
            "<b>Sistema de entrada:</b> receptor 3F75, estado de preparación revisar, "
            "cofactores: la corrida no registró la lista de cofactores. El informe no atribuye protonación, "
            "eliminación de aguas, minimización ni estados de carga cuando esas operaciones "
            "no fueron serializadas por la corrida.<br/><b>Exploración de poses:</b> el "
            "resultado registra 1 poses, motor 1.2.7, semilla 42 y parser sdf. Las afinidades "
            "son señales de la función de scoring y ranking; no son medidas experimentales de "
            "energía libre.<br/><b>Modelos derivados:</b> motor no informado, modelo no "
            "informado, dominio no informado. Cada salida se reporta por separado; el informe "
            "no convierte el índice compuesto heredado en una conclusión científica.<br/>"
        ) + frase({"physical_validity": {"status": "review", "label": "REVIEW REQUIRED"}})

        ingles = traducir(parrafo, "en")
        assert "<b>Input system:</b>" in ingles
        assert "<b>Pose search:</b>" in ingles
        assert "<b>Physical validity:</b>" in ingles
        assert "Validez física" not in ingles
