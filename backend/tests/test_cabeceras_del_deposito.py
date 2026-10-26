"""Preparación lee lo que el depósito declara de sí mismo (FEP-06-PRE, 2026-10-24).

Los paquetes traían el origen con sus cabeceras, pero Preparación no las leía:

* 3G0E (P08): REMARK 610 dice que al ligando del cristal B49 A:9000 le faltan átomos (22 de los 29 pesados del sunitinib),
  y REMARK 999 / SEQADV que los residuos 694-753 se borraron y se sustituyeron por TS. Sólo uno de seis revisores lo vio, y
  el producto tampoco.
* 1M17 (P01, P10): REMARK 475/480 declaran 37 átomos de ocupación cero en siete residuos; el PDBQT les pone 1,00.
"""
from __future__ import annotations

import gzip
import math
from collections import defaultdict
from pathlib import Path

from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.contexto_estructural import _atomos, _cabeceras_del_deposito, _filas_de_remark
from services.dossier.localization import traducir_dossier
from tests.test_preparacion_desde_el_ligando import _auditar, _caso, _contexto
from tests.test_preparacion_auditoria import _requisito

RAIZ = Path(__file__).resolve().parents[2]


def _deposito(pdb_id: str) -> str:
    return gzip.decompress((RAIZ / "data" / "targets" / f"{pdb_id}.pdb.gz").read_bytes()).decode(errors="replace")


def _medir(pdb_id: str, ligando: str, cadena: str = "A"):
    origen = _deposito(pdb_id)
    por_residuo = defaultdict(list)
    for a in _atomos(origen):
        por_residuo[a.clave_con_nombre].append(a)
    copias = [v for k, v in por_residuo.items() if k[3] == ligando and v[0].registro == "HETATM"]
    cristal = copias[0]

    def al_ligando(atomos):
        if not atomos:
            return None
        return round(min(math.dist(a.xyz, b.xyz) for a in atomos for b in cristal), 2)

    return _cabeceras_del_deposito(origen, {cadena}, ligando, cristal, por_residuo, al_ligando)


def test_el_ligando_incompleto_de_3g0e_y_su_constructo():
    cab = _medir("3G0E", "B49")
    assert cab["cristal_incompleto"] == "B49 A:9000"
    modificados = {r: c for r, c, _ in cab["secuencia_modificada"]}
    assert modificados == {"A:694 THR": "SEE REMARK 999", "A:753 SER": "SEE REMARK 999"}
    assert cab["remark_999"] == "RESIDUES 694-753 DELETED, REPLACED WITH TS"


def test_la_ocupacion_cero_de_1m17():
    cab = _medir("1M17", "AQ4")
    filas = {r: a for r, a, _ in cab["ocupacion_cero"]}
    assert filas["A:725 GLU"] == ""
    assert filas["A:730 LYS"] == "CG CD CE NZ"
    assert len(filas) == 7
    assert cab.get("cristal_incompleto") is None
    # Las colas de clonación no cuentan como constructo modificado.
    assert cab["secuencia_modificada"] == []


def test_una_mutacion_de_ingenieria_se_lee():
    cab = _medir("6SXC", "OHT")
    assert ("A:208 LEU", "ENGINEERED MUTATION") in [(r, c) for r, c, _ in cab["secuencia_modificada"]]


def test_las_cabeceras_de_los_remark_no_son_filas():
    texto = ("REMARK 610 MISSING HETEROATOM\nREMARK 610   M RES C SSEQI\nREMARK 610     B49 A 9000\n"
             "REMARK 610     1 12P B  306A\n")
    assert _filas_de_remark(texto, "610") == [("B49", "A", "9000", "", []), ("12P", "B", "306", "A", [])]


def test_preparacion_declara_y_solo_pide_revision_cerca_del_ligando():
    contexto = _contexto(plantillas=[])
    contexto.cristal_incompleto = "B49 A:9000"
    contexto.secuencia_modificada = [("A:694 THR", "SEE REMARK 999", 21.4), ("A:753 SER", "SEE REMARK 999", None)]
    contexto.remark_999 = "RESIDUES 694-753 DELETED, REPLACED WITH TS"
    contexto.ocupacion_cero = [("A:725 GLU", "", 14.0), ("A:730 LYS", "CG CD CE NZ", 6.2)]
    auditoria = _auditar(_caso(), contexto)

    constructo = _requisito(auditoria, "receptor.constructo")
    assert constructo["estado"] == "REGISTRADO"
    assert "A:694 THR SEE REMARK 999 (21.4 Å), A:753 SER SEE REMARK 999 (— Å)" in constructo["valor"]
    assert "Según el REMARK 999: RESIDUES 694-753 DELETED, REPLACED WITH TS" in constructo["valor"]
    ocupacion = _requisito(auditoria, "receptor.ocupacion_cero")
    assert ocupacion["estado"] == "REVISAR"
    assert "A:725 GLU (14 Å), A:730 LYS: CG CD CE NZ (6.2 Å)" in ocupacion["valor"]
    referencia = _requisito(auditoria, "entorno.referencia")
    assert referencia["estado"] == "REVISAR"
    assert "B49 A:9000 le faltan átomos (REMARK 610)" in referencia["razon"]

    ingles = traducir_dossier(auditoria, "en")
    for clave in ("receptor.constructo", "receptor.ocupacion_cero", "entorno.referencia"):
        r = _requisito(ingles, clave)
        for texto in (r["valor"], r["razon"], r["etiqueta"]):
            assert not texto or not _PARECE_CASTELLANO.search(texto), (clave, texto)


def test_sin_nada_que_declarar_queda_registrado():
    contexto = _contexto(plantillas=[])
    contexto.secuencia_modificada = []
    contexto.ocupacion_cero = []
    auditoria = _auditar(_caso(), contexto)
    assert _requisito(auditoria, "receptor.constructo")["estado"] == "REGISTRADO"
    assert _requisito(auditoria, "receptor.ocupacion_cero")["valor"] == "Ninguna en las cadenas del receptor"
    assert _requisito(auditoria, "entorno.referencia")["estado"] == "REGISTRADO"
