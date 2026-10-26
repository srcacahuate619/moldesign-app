"""La evidencia de un lote dice la verdad y sale entera en inglés (B02 y B04 de la QA de 1.0.2).

# Qué se midió (2026-10-10, QA de release de Sol con un lote real de dos ligandos)

* B04: las dos filas del lote eran controles con etiqueta `active`. Los controles se apartan de la
  población, así que la métrica se abstiene con razón, pero el motivo decía «La cohorte no declara
  etiquetas `active`», que era falso.
* B02: en la interfaz inglesa, los cinco límites del resumen y los motivos de abstención salían en
  castellano: `limits` no era un campo traducible de la API y nada de eso tenía traducción.
"""
from __future__ import annotations

import pytest

from core.i18n import localize_payload, reset_request_locale, set_request_locale
from core.i18n_plantillas import traducir
from services.cohort import evidence as ev
from services.cohort import execution as ex
from tests.test_cohort_evidence import cohorte_etiquetada, molecula


def test_si_solo_los_controles_llevan_etiqueta_el_motivo_lo_dice():
    filas = [molecula(0, smiles="C0", activa=True, control="positive"),
             molecula(1, smiles="C1", activa=False, control="negative")]
    metricas = ev.build_labeled_metrics(filas, run_status=ex.RUN_COMPLETED)
    assert metricas["status"] == "not_evaluated" and metricas["reason_code"] == ev.SIN_ETIQUETAS
    assert metricas["reason"].startswith("Las únicas moléculas con etiqueta `active` son controles")
    assert "no declara" not in metricas["reason"]


def test_sin_ninguna_etiqueta_el_motivo_no_cambia():
    filas = [molecula(i, smiles=f"M{i}") for i in range(3)] + [molecula(3, smiles="C", control="positive")]
    metricas = ev.build_labeled_metrics(filas, run_status=ex.RUN_COMPLETED)
    assert metricas["reason"].startswith("La cohorte no declara etiquetas `active`")


def _motivos_de_abstencion() -> list[str]:
    casos = [
        ([molecula(i, smiles=f"M{i}") for i in range(3)], ex.RUN_COMPLETED),
        ([molecula(0, smiles="C0", activa=True, control="positive")], ex.RUN_COMPLETED),
        (cohorte_etiquetada(8, 8), ex.RUN_RUNNING),
        ([molecula(0, smiles="X", activa=True), molecula(1, smiles="X", activa=False)], ex.RUN_COMPLETED),
        ([molecula(0, smiles="A", activa=True, afinidad=None)], ex.RUN_COMPLETED),
        (cohorte_etiquetada(0, 15), ex.RUN_COMPLETED),
        (cohorte_etiquetada(15, 0), ex.RUN_COMPLETED),
        (cohorte_etiquetada(2, 2), ex.RUN_COMPLETED),
    ]
    return [ev.build_labeled_metrics(filas, run_status=estado)["reason"] for filas, estado in casos]


@pytest.mark.parametrize("motivo", _motivos_de_abstencion())
def test_cada_motivo_de_abstencion_tiene_traduccion(motivo):
    assert traducir(motivo, "en") != motivo, motivo


@pytest.mark.parametrize(
    "veredictos",
    [
        None,
        {"passed": 0, "failed": 0, "review": 0, "not_evaluated": 4},
        {"passed": 3, "failed": 0, "review": 0, "not_evaluated": 1},
        {"passed": 1, "failed": 1, "review": 1, "not_evaluated": 1},
    ],
)
def test_los_limites_del_lote_salen_en_ingles_por_la_api(veredictos):
    # SCI-A-004: el límite de validez física depende de los veredictos, así que
    # las tres ramas tienen que estar traducidas, no sólo la que salía antes.
    respuesta = {
        "limits": ev.limites_de_la_evidencia(veredictos),
        "labeled_metrics": {"reason": _motivos_de_abstencion()[1]},
    }
    token = set_request_locale("en")
    try:
        localizada = localize_payload(respuesta)
    finally:
        reset_request_locale(token)
    for original, traducido in zip(respuesta["limits"], localizada["limits"]):
        assert traducido != original, original
    assert localizada["labeled_metrics"]["reason"].startswith("The only molecules with an `active` label are controls")
