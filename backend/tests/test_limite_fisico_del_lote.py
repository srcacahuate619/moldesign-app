"""SCI-A-004: el PDF del lote no niega lo que su propio recuento registra.

El límite de validez física era una frase fija: «las poses de esta cohorte no
han superado todavía una validación geométrica/física automática». El PDF la
imprimía siempre, también debajo de su propia tabla, donde la línea
«· controles superados» contaba 1. El documento se contradecía a sí mismo y
firmaba la contradicción con su SHA-256.
"""

from __future__ import annotations

import pytest

from services.cohort.evidence import (
    LIMITES_DE_LA_EVIDENCIA,
    limite_de_validez_fisica,
    limites_de_la_evidencia,
)

NEGACION = "no han superado"


class TestElLimiteDescribeLaCorrida:
    def test_sin_ningun_veredicto_dice_que_nadie_fue_evaluado(self):
        texto = limite_de_validez_fisica({"passed": 0, "failed": 0, "review": 0, "not_evaluated": 5})

        assert "Ninguna pose de esta cohorte recibió" in texto
        # Ausencia de evaluación no es fallo: describe al validador, no a la pose.
        assert NEGACION not in texto

    @pytest.mark.parametrize("veredictos", [None, {}])
    def test_sin_embudo_se_comporta_como_sin_veredictos(self, veredictos):
        assert "Ninguna pose" in limite_de_validez_fisica(veredictos)

    def test_si_todas_las_evaluadas_pasan_no_lo_niega(self):
        texto = limite_de_validez_fisica({"passed": 3, "failed": 0, "review": 0, "not_evaluated": 1})

        assert NEGACION not in texto, "el recuento dice que 3 superaron los controles"
        assert "superaron los controles" in texto
        # Pero superar la batería sigue sin ser actividad.
        assert "no demuestra actividad ni afinidad experimental" in texto

    @pytest.mark.parametrize(
        "veredictos",
        [
            {"passed": 1, "failed": 1, "review": 0, "not_evaluated": 0},
            {"passed": 1, "failed": 0, "review": 1, "not_evaluated": 0},
            {"passed": 0, "failed": 2, "review": 0, "not_evaluated": 0},
        ],
    )
    def test_con_fallos_o_revisiones_remite_al_desglose(self, veredictos):
        texto = limite_de_validez_fisica(veredictos)

        assert "no superó los controles" in texto
        assert "desglose por veredicto" in texto


class TestLosLimitesConservanLoDemas:
    def test_el_limite_fisico_va_segundo_y_los_fijos_siguen_estando(self):
        limites = limites_de_la_evidencia({"passed": 2, "failed": 0, "review": 0})

        assert len(limites) == len(LIMITES_DE_LA_EVIDENCIA) + 1
        assert limites[0] == LIMITES_DE_LA_EVIDENCIA[0]
        assert limites[1] == limite_de_validez_fisica({"passed": 2, "failed": 0, "review": 0})
        assert limites[2:] == list(LIMITES_DE_LA_EVIDENCIA[1:])

    def test_la_constante_ya_no_trae_la_frase_condicional(self):
        # Si alguien la devuelve a la constante, vuelve a imprimirse siempre.
        assert not any(NEGACION in limite for limite in LIMITES_DE_LA_EVIDENCIA)
