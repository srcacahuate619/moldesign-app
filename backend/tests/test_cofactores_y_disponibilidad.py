"""DOCK-003 con margen de sitio, disponibilidad del catálogo, DOCK-012 y panel de Bowes.

Contexto (verificación del 2026-09-26): la guarda de cofactores de la fase 1
bloqueaba cualquier cofactor sin plantilla, también a 30 Å del sitio (el FMN
de la flavodoxina fusionada a CB1 en 5TGZ). Ahora se aplica el mismo margen
que a los residuos que pierde Meeko.
"""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import pytest

from services.docking import preparer
from services.docking.preparer import (
    MARGEN_SITIO_A,
    cofactores_sin_plantilla,
    retirar_cofactores_fuera_del_sitio,
)

RAIZ = Path(__file__).resolve().parents[2]
CAJA = ((0.0, 0.0, 0.0), (10.0, 10.0, 10.0))  # de -5 a 5 en cada eje


def _hetatm(serial, nombre, resname, cadena, num, x, y=0.0, z=0.0, elemento="C"):
    return (f"HETATM{serial:5d} {nombre:<4} {resname:>3} {cadena}{num:>4}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00 20.00          {elemento:>2}")


def _pdb(*lineas):
    return "\n".join(lineas) + "\nEND\n"


def test_cofactor_en_el_sitio_bloquea_y_lejano_no():
    raw = _pdb(
        _hetatm(1, "FE", "HEM", "A", 500, 1.0, elemento="FE"),     # dentro de la caja
        _hetatm(2, "N1", "FMN", "A", 600, 40.0, elemento="N"),     # a 35 Å
    )
    en_sitio, fuera = cofactores_sin_plantilla(
        raw, cadenas={"A"}, site_ligand=None, cofactors_whitelist=[], center=CAJA[0], size=CAJA[1])
    assert [f["name"] for f in en_sitio] == ["HEM"]
    assert [(f["name"], f["action"]) for f in fuera] == [("FMN", "retirado")]


def test_el_margen_es_el_mismo_que_para_residuos_perdidos():
    # A 5 + 6 Å del centro: en el borde del margen, cuenta como sitio.
    borde = _pdb(_hetatm(1, "N1", "FMN", "A", 600, 5.0 + MARGEN_SITIO_A, elemento="N"))
    lejos = _pdb(_hetatm(1, "N1", "FMN", "A", 600, 5.0 + MARGEN_SITIO_A + 0.01, elemento="N"))
    kw = dict(cadenas={"A"}, site_ligand=None, cofactors_whitelist=[], center=CAJA[0], size=CAJA[1])
    assert cofactores_sin_plantilla(borde, **kw)[0]
    assert not cofactores_sin_plantilla(lejos, **kw)[0]


def test_fosfotreonina_lejana_vuelve_a_treonina_sin_fosfato():
    atomos = ["N", "CA", "C", "O", "CB", "OG1", "CG2", "P", "O1P", "O2P", "O3P"]
    raw = _pdb(*(_hetatm(i + 1, a, "TPO", "A", 160, 20.0 + i * 0.1,
                         elemento="P" if a == "P" else a[0]) for i, a in enumerate(atomos)))
    _, fuera = cofactores_sin_plantilla(
        raw, cadenas={"A"}, site_ligand=None, cofactors_whitelist=[], center=CAJA[0], size=CAJA[1])
    assert fuera[0]["action"] == "convertido a THR, sin fosfato"
    salida = retirar_cofactores_fuera_del_sitio(raw, fuera)
    registros = [l for l in salida.splitlines() if l.startswith(("ATOM", "HETATM"))]
    assert {l[17:20] for l in registros} == {"THR"}
    assert all(l.startswith("ATOM  ") for l in registros)
    assert {l[12:16].strip() for l in registros} == {"N", "CA", "C", "O", "CB", "OG1", "CG2"}


def test_otra_cadena_y_ligando_del_sitio_no_cuentan():
    raw = _pdb(
        _hetatm(1, "FE", "HEM", "B", 500, 1.0, elemento="FE"),     # cadena no pedida
        _hetatm(2, "C1", "ATP", "A", 700, 1.0),                    # es el ligando del sitio
    )
    en_sitio, fuera = cofactores_sin_plantilla(
        raw, cadenas={"A"}, site_ligand="ATP", cofactors_whitelist=[], center=CAJA[0], size=CAJA[1])
    assert en_sitio == [] and fuera == []


# ── Disponibilidad del catálogo ────────────────────────────────────────


def _generador():
    ruta = RAIZ / "scripts" / "generate_catalog_availability.py"
    spec = importlib.util.spec_from_file_location("generate_catalog_availability", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_el_inventario_coincide_con_la_funcion_de_prepare_target():
    """Lo mismo que `--check`: si el código o el catálogo cambian, esto cae."""
    g = _generador()
    anterior = json.loads(g.DESTINO.read_text(encoding="utf-8"))
    assert g.serializar(g.conservar_medidas(g.construir(), anterior)) == g.DESTINO.read_text(encoding="utf-8")


def test_el_inventario_no_lleva_rutas_de_la_maquina_que_midio():
    texto = (RAIZ / "backend" / "data" / "disponibilidad_catalogo.json").read_text(encoding="utf-8")
    assert ":\\" not in texto and "/home/" not in texto and "python-embed" not in texto


def test_cyp3a4_no_disponible_y_cdk2_recuperada():
    from services.targets.disponibilidad import motivo_no_disponible

    assert "HEM" in (motivo_no_disponible("4NY4") or "")
    # 6GUE: la fosfotreonina 160 está a 7,9 Å de la caja; antes bloqueaba.
    datos = json.loads((RAIZ / "backend" / "data" / "disponibilidad_catalogo.json").read_text(encoding="utf-8"))
    assert "6GUE" in datos["cofactores_fuera_del_sitio"]
    assert motivo_no_disponible("6GUE") is None


def test_el_modelo_target_se_lee_disponible_por_defecto():
    from core.models import Target

    campos = Target.model_fields
    assert campos["disponible"].default is True
    assert campos["motivo_no_disponible"].default is None


# ── DOCK-012 ───────────────────────────────────────────────────────────


def _rotar(coords, angulo):
    c, s = math.cos(angulo), math.sin(angulo)
    return [(c * x - s * y, s * x + c * y, z) for x, y, z in coords]


def _pdbqt(tmp_path, coords):
    lineas = [f"ATOM  {i + 1:5d}  C   LIG A   1    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00     0.000 C"
              for i, (x, y, z) in enumerate(coords)]
    ruta = tmp_path / f"lig_{len(list(tmp_path.iterdir()))}.pdbqt"
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


@pytest.mark.parametrize("angulo", [0.0, math.pi / 4, math.pi / 3, 1.1])
def test_el_aviso_de_caja_no_depende_de_la_orientacion(tmp_path, angulo):
    from services.docking.vina_service import _check_ligand_fits_box

    varilla = [(i * 1.5, 0.0, 0.0) for i in range(11)]            # 15 Å de largo
    caja = (18.0, 18.0, 18.0)                                       # 15 + 4 > 18: no cabe
    assert _check_ligand_fits_box(_pdbqt(tmp_path, _rotar(varilla, angulo)), caja, "TEST")
    holgada = (20.0, 20.0, 20.0)                                    # 15 + 4 < 20: cabe
    assert _check_ligand_fits_box(_pdbqt(tmp_path, _rotar(varilla, angulo)), holgada, "TEST") is None


# ── Panel de selectividad ──────────────────────────────────────────────


def test_panel_por_defecto_sin_cyp3a4_y_sugeridas_aparte():
    from services.docking.selectivity import ANTI_DIANAS_BOWES_2012, ANTI_TARGET_PANEL

    por_defecto = {t["pdb_id"] for t in ANTI_TARGET_PANEL}
    assert por_defecto == {"5VA1", "4NC3"}
    sugeridas = {t["pdb_id"] for t in ANTI_DIANAS_BOWES_2012}
    assert not por_defecto & sugeridas
    # Estructuras que el catálogo etiqueta como humanas y no lo son.
    assert not sugeridas & {"4BVN", "1GPK", "6Y5A"}


@pytest.mark.asyncio
async def test_una_sugerida_elegida_conserva_su_categoria():
    from services.docking.selectivity import seleccionar_anti_dianas

    class Repo:
        async def get_target_by_pdb_id(self, pdb_id):
            return type("Fila", (), {"name": "catálogo", "chain": "R", "affinity_threshold": -7.0,
                                     "anti_target_risk": None})()

    elegidas, desconocidas = await seleccionar_anti_dianas(["7E2Y"], repository=Repo())
    assert desconocidas == []
    assert elegidas[0]["category"].startswith("Bowes 2012")
    assert elegidas[0]["name"] == "5-HT1A (HTR1A)"
    assert "center" not in elegidas[0]      # la caja sale del catálogo


def test_prepare_target_usa_la_funcion_compartida():
    """Que la guarda y el inventario no puedan divergir: una sola función."""
    import inspect

    fuente = inspect.getsource(preparer.prepare_target)
    assert "cofactores_sin_plantilla(" in fuente
    assert "retirar_cofactores_fuera_del_sitio(" in fuente


def test_la_interfaz_no_pide_por_defecto_anti_dianas_retiradas():
    """La fase 1 sacó 6MVW (NavAb) y 1SO2 (PDE3B) del panel, pero la interfaz
    las seguía enviando por defecto y el backend las acoplaba como «anti-diana
    del usuario». El valor por defecto de la interfaz es el panel del backend."""
    import re

    from services.docking.selectivity import ANTI_TARGET_PANEL

    esperado = sorted(t["pdb_id"] for t in ANTI_TARGET_PANEL)
    front = RAIZ / "frontend" / "components"
    for rel in ("evaluation/CaseEvaluationRunner.tsx", "interfaces/pro/ProEvaluation.tsx",
                "interfaces/pro/ProOptionsModal.tsx"):
        fuente = (front / rel).read_text(encoding="utf-8")
        listas = re.findall(r"(?:pro_anti_targets|selectedAntiTargets)[^\[]*\[([^\]]*)\]", fuente)
        assert listas, rel
        for lista in listas:
            ids = sorted(re.findall(r'"([0-9A-Z]{4})"', lista))
            if ids:
                assert ids == esperado, (rel, ids)
