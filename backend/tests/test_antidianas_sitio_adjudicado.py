"""Una alerta de anti-diana dice si su sitio está adjudicado (D-09 de la investigación de 1.0.4).

Medido por la sesión de implementación y por el investigador: `selectivity.py` emitía «ALERTA» sólo con el umbral de
afinidad, y `sitio_adjudicado` sólo viajaba en la lista de `/pro/anti-targets`. Con el sitio sin adjudicar (38 de las
44 filas del panel de Bowes), la caja puede no corresponder al mecanismo del riesgo que nombra la alerta. Este cambio
sólo lo declara: la alerta sale igual, con el mismo umbral, y el margen no cambia. Exigir la adjudicación para emitirla
es una decisión aparte.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services.docking import selectivity, vina_service
from services.docking.selectivity import (
    AVISO_SITIO_NO_ADJUDICADO,
    panel_bowes_2012,
    sitio_adjudicado_de,
    texto_de_alerta,
)


def test_el_panel_tiene_las_cuentas_que_cita_la_investigacion():
    cuenta = Counter(str(f.get("sitio_adjudicado", "ausente")) for f in panel_bowes_2012())
    assert cuenta == {"False": 38, "True": 2, "ausente": 4}


@pytest.mark.parametrize("pdb, esperado", [
    ("5VA1", True), ("7SRQ", True),            # hERG y 5-HT2B, el panel por defecto
    ("6LQA", False), ("7UL2", False), ("7ul2", False),
    ("XXXX", None), ("", None), (None, None),  # una anti-diana propia o nada: no consta
])
def test_sitio_adjudicado_de(pdb, esperado):
    assert sitio_adjudicado_de(pdb) is esperado


def test_el_texto_de_la_alerta_solo_cambia_con_un_false_explicito():
    antes = "ALERTA OPRK1: afinidad -7.2 kcal/mol < umbral -7.0. Riesgo: disforia"

    assert texto_de_alerta("OPRK1", -7.2, -7.0, "disforia", True) == antes
    assert texto_de_alerta("OPRK1", -7.2, -7.0, "disforia", None) == antes
    assert texto_de_alerta("OPRK1", -7.2, -7.0, "disforia", False) == f"{antes} — {AVISO_SITIO_NO_ADJUDICADO}"


def _panel(pdb_id: str, afinidad: float):
    async def dock(**_):
        return SimpleNamespace(best_affinity=afinidad, poses=[object()])

    async def elegir(*_):
        return ([{"pdb_id": pdb_id, "name": f"anti {pdb_id}", "chain": "A", "risk": "riesgo de prueba",
                  "affinity_threshold": -7.0}], [])

    async def correr():
        with patch.object(selectivity, "seleccionar_anti_dianas", elegir), \
                patch.object(vina_service, "run_vina_docking", dock):
            return await selectivity.run_selectivity_panel(
                "CCO", "sintetico", "1ABC", -8.0, anti_targets=[pdb_id],
                docking_protocol={"engine": "vina", "exhaustiveness": 8, "num_poses": 9, "seed": 42})

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(correr())


@pytest.mark.parametrize("pdb, aviso", [("7UL2", True), ("5VA1", False), ("XXXX", False)])
def test_el_panel_declara_el_sitio_y_la_alerta_y_el_margen_no_cambian(pdb, aviso):
    resultado = _panel(pdb, -7.2)
    alertas = [f for f in resultado.safety_flags if f.startswith("ALERTA")]

    assert len(alertas) == 1 and (AVISO_SITIO_NO_ADJUDICADO in alertas[0]) is aviso
    assert resultado.delta_delta_g_kcal == pytest.approx(0.8)
    assert resultado.off_targets[0]["sitio_adjudicado"] is sitio_adjudicado_de(pdb)


def test_sin_rebasar_el_umbral_no_hay_alerta_aunque_el_sitio_no_este_adjudicado():
    resultado = _panel("7UL2", -6.5)
    assert not any(f.startswith("ALERTA") for f in resultado.safety_flags)
    assert not any(AVISO_SITIO_NO_ADJUDICADO in f for f in resultado.safety_flags)


# ── hERG, revisión final de 1.0.4: la alerta se escribe con los decimales que dejan ver por qué se cumple ──────────


@pytest.mark.parametrize("afinidad, esperado", [
    (-7.004, "afinidad -7.004 kcal/mol < umbral -7.000"),     # el caso medido: antes «-7.0 < umbral -7.0»
    (-7.04, "afinidad -7.04 kcal/mol < umbral -7.00"),
    (-7.0499, "afinidad -7.05 kcal/mol < umbral -7.00"),
    (-7.00004, "afinidad -7.00004 kcal/mol < umbral -7.00000"),
    (-7.2, "afinidad -7.2 kcal/mol < umbral -7.0"),           # el caso normal no cambia
    (-9.87, "afinidad -9.9 kcal/mol < umbral -7.0"),
])
def test_la_alerta_no_escribe_igual_el_valor_y_el_umbral(afinidad, esperado):
    texto = texto_de_alerta("hERG", afinidad, -7.0, "arritmia", None)
    assert esperado in texto
    assert afinidad < -7.0                                    # la desigualdad estricta no se toca


def test_en_el_corte_exacto_no_hay_alerta_y_los_decimales_no_se_inventan():
    from services.docking.selectivity import decimales_para_distinguir

    assert not (-7.0 < -7.0)
    assert decimales_para_distinguir(-7.0, -7.0) == 6          # iguales: tope, no un bucle infinito
    assert decimales_para_distinguir(-7.2, -7.0) == 1
    assert decimales_para_distinguir(-7.5, -7.0, minimo=1) == 1
