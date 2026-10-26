"""SCI-A-059 y SCI-A-007: el estado global conserva el veredicto físico.

El frontend ya lo hacía —`lib/evaluationEvidence.ts` mete `failed` y `review` en
su reserva, y la prueba SOL-05 lo fija— pero el backend no tenía el espejo. Una
corrida con poses, procedencia y dominio en orden salía «EVIDENCIA DISPONIBLE»
en verde aunque su pose principal fallara los controles de química o geometría,
en el MISMO documento cuya matriz imprime ese fallo.

El segundo defecto es de redacción, y es el que hace falsa la explicación: el
agregador `_estado_de_etapa` devuelve `review` por DOS causas distintas —batería
incompleta, o principal que pasa con una alternativa que falla— y el texto
nombraba sólo la primera.
"""

from __future__ import annotations

import pytest

from core.i18n import reset_request_locale, set_request_locale
from services.blockchain.evidence_summary import build_evidence_summary

from tests.test_evidence_summary import _result, _target


def _evidencia(stage_status: str, *, producidas: int = 2, evaluadas: int = 2) -> dict:
    return {
        "stage_status": stage_status,
        "poses_produced": producidas,
        "poses_evaluated": evaluadas,
        "validation_engine": "posebusters:1.0:dock",
        "reason_code": None,
        "entries": [],
    }


def _resumen(stage_status: str, **extra):
    return build_evidence_summary(
        _result(structural_evidence=_evidencia(stage_status, **extra)), _target()
    )


class TestElEstadoGlobalNoIgnoraElVeredictoFisico:
    @pytest.mark.parametrize("stage_status", ["failed", "review"])
    def test_un_veredicto_con_reserva_no_deja_el_resumen_en_verde(self, stage_status):
        resumen = _resumen(stage_status)

        assert resumen["status"] == "review", (
            "una corrida con controles físicos en "
            f"{stage_status} no puede presentarse como evidencia disponible"
        )
        assert resumen["label"] != "EVIDENCIA DISPONIBLE"

    def test_un_fallo_aparece_en_las_incertidumbres(self):
        resumen = _resumen("failed")

        assert any(
            "falla los controles de química o geometría" in u
            for u in resumen["uncertainties"]
        ), "un control fallido tiene que viajar en las incertidumbres del resumen"

    def test_el_fallo_llega_a_su_dimension_sin_aplanarse_en_revision(self):
        dimension = next(
            d for d in _resumen("failed")["dimensions"] if d["id"] == "physical"
        )

        # `review` es ámbar en el PDF; `failed` es rojo. Aplanarlos pintaba un
        # fallo medido con el color de «queda por mirar».
        assert dimension["status"] == "failed"

    def test_passed_sigue_autorizando_el_verde(self):
        resumen = _resumen("passed")

        assert resumen["status"] == "ready"
        assert next(
            d for d in resumen["dimensions"] if d["id"] == "physical"
        )["status"] == "available"

    def test_no_evaluado_sigue_siendo_ausencia_y_no_reserva(self):
        # Que nadie midiera no es una reserva sobre la pose: es un hueco. Esta
        # rama no cambia, y se fija para que el arreglo no la contamine.
        resumen = _resumen("not_evaluated", evaluadas=0)

        assert resumen["physical_validity"]["status"] == "not_evaluated"


class TestLaExplicacionDeReviewNombraSusDosCausas:
    """SCI-A-007: `review` también significa «una alternativa falla»."""

    def test_el_detalle_castellano_no_afirma_solo_bateria_incompleta(self):
        detalle = _resumen("review")["physical_validity"]["detail"]

        assert "alguna alternativa falla" in detalle
        assert "NO una pose aprobada" in detalle

    def test_la_incertidumbre_de_review_tampoco_lo_afirma(self):
        incertidumbres = _resumen("review")["uncertainties"]

        assert any("una pose alternativa falla" in u for u in incertidumbres)

    @pytest.mark.parametrize(
        "frase, esperado",
        [
            (
                "La batería no corrió entera sobre todas las poses, o la pose principal "
                "pasa y alguna alternativa falla. «Revisión necesaria» describe una "
                "comprobación que hay que mirar, NO una pose aprobada.",
                "an alternative fails",
            ),
            (
                "Los controles físicos no corrieron enteros sobre todas las poses, o una "
                "pose alternativa falla; «revisión necesaria» no equivale a pose aprobada.",
                "an alternative pose fails",
            ),
            (
                "Al menos la pose principal falla los controles de química o geometría: la "
                "afinidad de esta corrida no sostiene una priorización del ligando.",
                "does not support prioritizing the ligand",
            ),
        ],
    )
    def test_cada_frase_nueva_tiene_su_pareja_inglesa(self, frase, esperado):
        # `traducir` es todo-o-nada por frase: una frase sin pareja deja en
        # castellano el párrafo ENTERO que la contiene (la lección de
        # SCI-A-008). Cambiar una redacción sin mover su entrada del catálogo
        # rompe el documento inglés en silencio.
        from core.i18n import translate_text

        token = set_request_locale("en")
        try:
            traducida = translate_text(frase)
        finally:
            reset_request_locale(token)

        assert esperado in traducida
        assert traducida != frase

    def test_el_detalle_entero_sale_en_ingles(self):
        """El párrafo se arma por frases y cada una necesita su par.

        El detalle concatena la explicación con «Motor: …» y «Cobertura …», y
        `i18n_plantillas.py` las traduce una a una. Cambiar la redacción sin
        mover su par deja el párrafo ENTERO en castellano dentro del informe
        inglés, en silencio: es la lección de SCI-A-008, y pasó al escribir
        este mismo arreglo.
        """
        token = set_request_locale("en")
        try:
            detalle = _resumen("review")["physical_validity"]["detail"]
        finally:
            reset_request_locale(token)

        assert "an alternative fails" in detalle
        assert "NOT an approved pose" in detalle
        assert "Coverage: 2/2 poses." in detalle
        assert "batería" not in detalle and "alternativa" not in detalle


# ── SCI-A-023: el resumen no niega un ensemble que el protocolo registra ──────

@pytest.mark.parametrize("protocolo, esperado", [
    ({"conformers_requested": 3, "conformers_generated": 3}, "ensemble de 3 conformaciones"),
    ({"conformers_requested": 1, "conformers_generated": 1}, "Confórmero único"),
    (None, "no informa si hubo ensemble"),
])
def test_la_frase_de_muestreo_sale_del_protocolo(protocolo, esperado):
    from types import SimpleNamespace
    from core.i18n_plantillas import traducir
    from services.blockchain.evidence_summary import frase_de_muestreo

    frase = frase_de_muestreo(SimpleNamespace(docking_protocol=protocolo))
    assert esperado in frase and "ni ensemble" not in frase
    assert traducir(frase, "en") != frase
    detalle = f"Diferencia pose 1-2 0.40 kcal/mol. {frase}"
    assert traducir(detalle, "en").startswith("Pose 1–2 difference: 0.40 kcal/mol. ")
    assert "réplicas" not in traducir(detalle, "en")
