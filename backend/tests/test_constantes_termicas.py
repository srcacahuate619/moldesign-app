"""B-5 de 1.0.4: cada constante térmica dice a qué temperatura está, y lo dicho es cierto.

La auditoría científica encontró conviviendo `1.364`, `1.3633`, `1.36` y `RT_KCAL = 0.61626`. No son una deriva del mismo número:
son tres conversiones con significado distinto (kcal/mol por unidad logarítmica a 298.15 K para LLE y eficiencias; kcal/mol por
década para el factor de selectividad, a ≈ 298 K; R·T a 310.15 K para pasar un score a concentración en el panel). Lo que sí
podía pasar es que un comentario rotulara una constante con una temperatura que no es la suya (1.3633 se llamaba «298.15 K» y
es el valor a 297.94 K). Estas pruebas fijan cada valor a su temperatura y las copias de frontend y backend entre sí.

No cambian ningún valor: sólo hacen que un rótulo falso, o una copia que se aleja, falle aquí.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

from scoring.eficiencia import KCAL_POR_UNIDAD_LOG
from services.docking import selectividad_margen as _margen
from services.docking.selectividad_margen import KCAL_POR_DECADA

#: R en kcal/(mol·K): 8.314462618 J/(mol·K) (CODATA 2018) entre 4184 J/kcal (termoquímica).
R_KCAL = 8.314462618 / 4184.0
LN10 = math.log(10.0)

RAIZ = Path(__file__).resolve().parents[2]
SELECTIVIDAD_TS = RAIZ / "frontend" / "lib" / "selectividadMargen.ts"
PANEL_TSX = RAIZ / "frontend" / "components" / "interfaces" / "pro" / "ProSelectivityPanel.tsx"


def _rt_ln10(temperatura_k: float) -> float:
    return R_KCAL * temperatura_k * LN10


def _constante_ts(ruta: Path, nombre: str) -> float:
    texto = ruta.read_text(encoding="utf-8")
    hallado = re.search(rf"\b{re.escape(nombre)}\s*=\s*([0-9]+\.[0-9]+)\s*;", texto)
    assert hallado, f"{nombre} no está en {ruta.name}"
    return float(hallado.group(1))


def test_la_conversion_de_eficiencias_es_rt_ln10_a_298_15_k():
    """1.364 es la convención de química medicinal a 298.15 K (a esa temperatura son 1.3643)."""
    assert KCAL_POR_UNIDAD_LOG == pytest.approx(_rt_ln10(298.15), abs=0.001)


def test_el_factor_de_selectividad_es_rt_ln10_a_unos_298_k():
    """1.3633 NO es el valor a 298.15 K (1.3643): es el de 297.94 K. Se acepta, y se declara, dentro de 0.0015."""
    assert KCAL_POR_DECADA == pytest.approx(_rt_ln10(298.0), abs=0.0015)
    # El rótulo viejo («298.15 K») era falso con esta tolerancia: lo fija como medida, no como opinión.
    assert abs(KCAL_POR_DECADA - _rt_ln10(298.15)) > 0.0005


def test_las_dos_conversiones_de_decada_se_parecen_pero_no_son_la_misma():
    """Una es kcal por unidad log de afinidad (LLE); la otra, por década de selectividad. Distan 0.03 %, no más."""
    assert abs(KCAL_POR_UNIDAD_LOG - KCAL_POR_DECADA) / KCAL_POR_DECADA < 0.001


def test_el_frontend_usa_el_mismo_factor_de_decada_que_el_backend():
    assert _constante_ts(SELECTIVIDAD_TS, "KCAL_POR_DECADA") == KCAL_POR_DECADA


def test_el_panel_convierte_con_rt_a_310_15_k_no_con_rt_ln10():
    """`RT_KCAL` es R·T (0.61633 a 310.15 K), no ln(10)·R·T, y no está a 298 K."""
    rt = _constante_ts(PANEL_TSX, "RT_KCAL")
    assert rt == pytest.approx(R_KCAL * 310.15, abs=0.0002)
    assert abs(rt - R_KCAL * 298.15) > 0.02, "ya no está a temperatura fisiológica: el comentario del panel lo afirma"


def test_los_rotulos_no_vuelven_a_atribuir_298_15_k_al_factor_de_decada():
    for ruta in (SELECTIVIDAD_TS, Path(_margen.__file__)):
        texto = ruta.read_text(encoding="utf-8")
        # La línea de la constante no puede decir «298.15 K» a secas: el valor de 1.3633 es el de ≈ 298 K.
        for linea in texto.splitlines():
            if "ln(10)·R·T a 298.15 K" in linea:
                pytest.fail(f"{ruta.name}: rotula 1.3633 con 298.15 K, y a esa temperatura son 1.3643")
