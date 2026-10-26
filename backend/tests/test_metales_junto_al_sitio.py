"""Los iones metálicos del sitio del catálogo y quién los coordina (2026-10-11).

`scripts/medir_metales_del_sitio.py` mide, sobre los depósitos sin preparar, qué iones no declarados hay a 6 Å o menos
del ligando del cristal y si el propio ligando los coordina (un N, O o S suyo a 2,8 Å o menos). `AGENTS.md` cita
esas cifras; estas pruebas hacen que citarlas no sea un acto de fe.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
AGENTS = RAIZ / "AGENTS.md"


def _medidor():
    spec = importlib.util.spec_from_file_location("medir_metales_del_sitio", RAIZ / "scripts" / "medir_metales_del_sitio.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def _atomo(registro: str, n: int, nombre: str, residuo: str, cadena: str, numero: int,
           xyz: tuple[float, float, float], elemento: str) -> str:
    return (f"{registro:<6}{n:5d} {nombre:<4} {residuo:>3} {cadena}{numero:4d}    "
            f"{xyz[0]:8.3f}{xyz[1]:8.3f}{xyz[2]:8.3f}  1.00 20.00          {elemento:>2}\n")


ENTRADA = {"pdb_id": "TEST", "site_ligand": "LIG", "grid_center_x": 0.0, "grid_center_y": 0.0, "grid_center_z": 0.0,
           "cofactors_whitelist": []}


def _deposito(*, iones: list[tuple[str, tuple[float, float, float]]]) -> list[str]:
    lineas = [_atomo("HETATM", 1, "O1", "LIG", "A", 1, (0.0, 0.0, 0.0), "O"),
              _atomo("HETATM", 2, "C1", "LIG", "A", 1, (1.2, 0.0, 0.0), "C")]
    for i, (nombre, xyz) in enumerate(iones, 3):
        lineas.append(_atomo("HETATM", i, nombre, nombre, "A", 100 + i, xyz, nombre))
    return lineas


def test_un_ion_junto_a_un_oxigeno_del_ligando_lo_coordina_el_ligando():
    m = _medidor()
    filas = m.medir_entrada(_deposito(iones=[("ZN", (0.0, 2.0, 0.0))]), ENTRADA)
    assert [(f["metal"], f["lo_coordina_el_ligando"], f["atomos_del_ligando_que_lo_coordinan"]) for f in filas] == [
        ("ZN", True, ["O1"])]


def test_un_ion_del_sitio_que_el_ligando_no_toca_se_cuenta_pero_no_coordinado():
    m = _medidor()
    filas = m.medir_entrada(_deposito(iones=[("MG", (0.0, 4.5, 0.0))]), ENTRADA)
    assert len(filas) == 1 and not filas[0]["lo_coordina_el_ligando"] and filas[0]["d_ligando_A"] == 4.5


def test_lo_que_queda_fuera_del_margen_o_esta_declarado_no_cuenta():
    m = _medidor()
    assert m.medir_entrada(_deposito(iones=[("ZN", (0.0, 9.0, 0.0))]), ENTRADA) == []
    declarada = dict(ENTRADA, cofactors_whitelist=["zn"])
    assert m.medir_entrada(_deposito(iones=[("ZN", (0.0, 2.0, 0.0))]), declarada) == []
    assert m.medir_entrada(_deposito(iones=[("ZN", (0.0, 2.0, 0.0))]), dict(ENTRADA, site_ligand=None)) == []


def test_un_carbono_a_distancia_de_coordinacion_no_coordina():
    """Sólo N, O y S coordinan: a 2,6 Å del C y a 2,86 Å del O, el ion está en el sitio pero no lo coordina el ligando."""
    m = _medidor()
    filas = m.medir_entrada(_deposito(iones=[("ZN", (1.2, 2.6, 0.0))]), ENTRADA)
    assert len(filas) == 1 and filas[0]["d_ligando_A"] == 2.6 and not filas[0]["lo_coordina_el_ligando"]


def test_la_evidencia_se_reproduce_desde_los_depositos():
    """Lo mismo que `--check`: si los depósitos, el catálogo o el criterio cambian, esto cae."""
    m = _medidor()
    guardada = json.loads((RAIZ / "docs" / "auditorias" / "metales_junto_al_sitio_2026-10-11.json").read_text(encoding="utf-8"))
    assert guardada == m.medir(RAIZ)


def test_el_control_negativo_ve_una_cifra_mejorada_a_mano():
    """Un guardián tiene que demostrar que ve (AGENTS.md, restricción 2)."""
    m = _medidor()
    guardada = json.loads((RAIZ / "docs" / "auditorias" / "metales_junto_al_sitio_2026-10-11.json").read_text(encoding="utf-8"))
    falsa = copy.deepcopy(guardada)
    falsa["filas"][0]["lo_coordina_el_ligando"] = not falsa["filas"][0]["lo_coordina_el_ligando"]
    assert falsa != m.medir(RAIZ)
    sin_una = copy.deepcopy(guardada)
    sin_una["filas"].pop()
    assert sin_una != m.medir(RAIZ)


def test_agents_cita_las_cifras_medidas():
    resumen = json.loads((RAIZ / "docs" / "auditorias" / "metales_junto_al_sitio_2026-10-11.json").read_text(encoding="utf-8"))["resumen"]
    texto = " ".join(AGENTS.read_text(encoding="utf-8").split())
    por = resumen["por_elemento"]
    esperado = (f"En {resumen['entradas']} de las 381 hay un ion a 6 Å o menos del ligando del cristal "
                f"({resumen['iones']} iones: {por['ZN']['iones']} de Zn, {por['MG']['iones']} de Mg, "
                f"{por['CA']['iones']} de Ca y {por['K']['iones']} de K)")
    assert esperado in texto
    assert f"coordina {resumen['iones_coordinados_por_el_ligando']} de ellos" in texto
    assert (f"{por['ZN']['coordinados']} de Zn, {por['MG']['coordinados']} de Mg, "
            f"{por['CA']['coordinados']} de Ca y {por['K']['coordinados']} de K") in texto
