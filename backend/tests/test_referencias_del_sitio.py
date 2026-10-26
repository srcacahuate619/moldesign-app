"""El sitio de cada receptor lo define su inhibidor, no el cofactor del complejo (2026-10-11).

Trece entradas declaraban como `site_ligand` el cofactor: el hemo en diez COX-1/COX-2 y en CYP2D6 (5TFT), el NADP
en la DHFR de S. aureus (3SRW) y el FMN en la DHODH de P. falciparum (5TBO). La caja estaba centrada en el cofactor
—en las COX, en el sitio peroxidasa, a unos 20 Å del canal donde se une el AINE— y la preparación retiraba el
cofactor como si fuera el ligando. `scripts/corregir_referencias_cofactor.py` las recentra en la instancia del
inhibidor y deja la evidencia en `docs/auditorias/referencias_del_sitio_2026-10-11.json`. 3N8Y (diclofenaco en la
COX-1 tratada con aspirina) se dejó fuera por su serina acetilada y entró el mismo día, medida: la OAS no está en
la cadena del catálogo.

Estas pruebas comprueban la anotación contra la estructura depositada, no contra la propia anotación.
"""
from __future__ import annotations

import gzip
import json
import math
from pathlib import Path

import pytest

from services.docking import preparer
from services.dossier.preparacion import _COFACTORES_NO_DESPLAZABLES
from services.targets.sitio_de_union import CORTE_CONTACTO, anotar_sitio

RAIZ = Path(__file__).resolve().parents[2]
EVIDENCIA = RAIZ / "docs" / "auditorias" / "referencias_del_sitio_2026-10-11.json"

#: pdb -> (inhibidor, cadena, número, cofactor que se conserva).
CORREGIDAS = {
    "1CX2": ("S58", "A", "701", "HEM"), "1Q4G": ("BFL", "A", "701", "HEM"),
    "2OYE": ("IM8", "P", "700", "HEM"), "2OYU": ("IMS", "P", "700", "HEM"),
    "3KK6": ("CEL", "A", "701", "HEM"), "3N8W": ("FLP", "A", "802", "HEM"),
    "3N8X": ("NIM", "A", "701", "HEM"), "3N8Z": ("FLP", "A", "701", "HEM"),
    "3SRW": ("Q27", "X", "168", "NAP"), "5TBO": ("78Z", "A", "1001", "FMN"),
    "5TFT": ("P6U", "A", "604", "HEM"), "5U6X": ("P6A", "A", "702", "HEM"),
    "5WBE": ("63X", "A", "803", "HEM"),
    # Entró después (`--solo 3N8Y`): la serina acetilada sólo está en la cadena B.
    "3N8Y": ("DIF", "A", "701", "HEM"),
}
#: Entradas que conservan a propósito un cofactor como referencia. Vacío desde que 3N8Y se midió.
PENDIENTES: dict[str, str] = {}


@pytest.fixture(scope="module")
def catalogo():
    return {e["pdb_id"]: e for e in json.loads((RAIZ / "curated_targets.json").read_text(encoding="utf-8"))}


def _fuente(pdb_id: str) -> str:
    with gzip.open(RAIZ / "data" / "targets" / f"{pdb_id}.pdb.gz", "rt", encoding="utf-8") as fh:
        return fh.read()


def _instancia(fuente: str, ref: str, cadena: str, numero: str) -> list[tuple[float, float, float]]:
    return [tuple(float(l[i:i + 8]) for i in (30, 38, 46)) for l in fuente.splitlines()
            if l.startswith("HETATM") and l[17:20].strip() == ref and l[21:22].strip() == cadena
            and l[22:26].strip() == numero and l[76:78].strip().upper() not in {"H", "D"}]


def _caja(entrada: dict):
    return (tuple(entrada[f"grid_center_{e}"] for e in "xyz"), tuple(entrada[f"grid_size_{e}"] for e in "xyz"))


@pytest.mark.parametrize("pdb_id", sorted(CORREGIDAS))
def test_la_caja_esta_sobre_el_inhibidor_y_lo_contiene(catalogo, pdb_id):
    ref, cadena, numero, _ = CORREGIDAS[pdb_id]
    entrada = catalogo[pdb_id]
    assert entrada["site_ligand"] == ref
    ligando = _instancia(_fuente(pdb_id), ref, cadena, numero)
    assert len(ligando) >= 6
    centro, lado = _caja(entrada)
    for eje in range(3):
        assert abs(sum(p[eje] for p in ligando) / len(ligando) - centro[eje]) <= 0.0005
        assert min(lado[eje] / 2 - abs(p[eje] - centro[eje]) for p in ligando) >= 4.0


@pytest.mark.parametrize("pdb_id", sorted(CORREGIDAS))
def test_los_hotspots_y_el_sitio_salen_del_inhibidor(catalogo, pdb_id):
    ref, cadena, numero, _ = CORREGIDAS[pdb_id]
    entrada = catalogo[pdb_id]
    fuente = _fuente(pdb_id)
    ligando = _instancia(fuente, ref, cadena, numero)
    assert entrada["hotspots_source"] == "box_ligand_contacts"
    assert 3 <= len(entrada["hotspots"]) <= 15
    for hotspot in entrada["hotspots"]:
        c, etiqueta = hotspot["name"].split(":")
        puntos = [tuple(float(l[i:i + 8]) for i in (30, 38, 46)) for l in fuente.splitlines()
                  if l.startswith("ATOM") and l[21:22].strip() == c and l[17:20].strip() + l[22:26].strip() == etiqueta]
        assert puntos and min(math.dist(p, q) for p in puntos for q in ligando) <= CORTE_CONTACTO, hotspot
    sitio = anotar_sitio(fuente, *_caja(entrada))
    for campo in ("site_ligand", "site_chains", "site_chain_atoms", "site_evidence"):
        assert sitio[campo] == entrada[campo], campo


@pytest.mark.parametrize("pdb_id", sorted(CORREGIDAS))
def test_la_preparacion_retira_el_inhibidor_y_conserva_el_cofactor(catalogo, pdb_id):
    ref, _, _, cofactor = CORREGIDAS[pdb_id]
    entrada = catalogo[pdb_id]
    filtrado = preparer.filter_pdb_content(
        _fuente(pdb_id), entrada["chain"], keep_hetatm=True,
        cofactors_whitelist=entrada.get("cofactors_whitelist"), site_ligand=entrada["site_ligand"])
    nombres = {l[17:20].strip() for l in filtrado.splitlines() if l.startswith("HETATM")}
    assert cofactor in nombres
    assert ref not in nombres


def test_ningun_receptor_declara_como_ligando_un_cofactor_que_no_se_desplaza(catalogo):
    """Guardián: el hemo, el FAD, el FMN, el NADP o un clúster Fe–S no son lo que el inhibidor desplaza."""
    culpables = {pdb: e["site_ligand"] for pdb, e in catalogo.items()
                 if (e.get("site_ligand") or "").upper() in _COFACTORES_NO_DESPLAZABLES}
    assert culpables == PENDIENTES


def test_el_guardian_ve_un_cofactor_declarado_como_ligando(catalogo):
    """Un guardián tiene que demostrar que ve (AGENTS.md, restricción 2)."""
    falso = dict(catalogo, ZZZZ={"site_ligand": "FMN"})
    culpables = {pdb: e["site_ligand"] for pdb, e in falso.items()
                 if (e.get("site_ligand") or "").upper() in _COFACTORES_NO_DESPLAZABLES}
    assert culpables != PENDIENTES and "ZZZZ" in culpables


def test_la_evidencia_describe_el_catalogo_que_hay(catalogo):
    evidencia = json.loads(EVIDENCIA.read_text(encoding="utf-8"))
    assert {d["pdb_id"] for d in evidencia["decisiones"]} == set(CORREGIDAS)
    for d in evidencia["decisiones"]:
        entrada = catalogo[d["pdb_id"]]
        assert d["problemas"] == []
        assert d["despues"]["centro"] == list(_caja(entrada)[0])
        assert d["despues"]["hotspots"] == [h["name"] for h in entrada["hotspots"]]
        assert d["antes"]["site_ligand"] == CORREGIDAS[d["pdb_id"]][3]


def test_recentrar_5tbo_no_oculta_su_hueco(catalogo):
    """El sitio de DSM421 sigue con el bucle VAL343→GLU356 sin resolver: recentrar no repara la estructura."""
    entrada = catalogo["5TBO"]
    fuente = _fuente("5TBO")
    filtrado = preparer.filter_pdb_content(fuente, "A", keep_hetatm=True, site_ligand=entrada["site_ligand"])
    huecos = preparer.huecos_del_esqueleto(filtrado, fuente, *_caja(entrada))
    assert any(h["after"] == "VAL 343" and h["before"] == "GLU 356" and h["site_critical"] for h in huecos)


def test_3n8y_la_serina_acetilada_no_esta_en_la_cadena_del_catalogo(catalogo):
    """La premisa de recentrar 3N8Y sin preparación covalente, contra el depósito y no contra la anotación."""
    fuente = _fuente("3N8Y")
    oas = {(l[21:22], l[22:26].strip()) for l in fuente.splitlines()
           if l.startswith("HETATM") and l[17:20].strip() == "OAS"}
    assert oas == {("B", "530")}
    cadena = catalogo["3N8Y"]["chain"]
    assert cadena == "A" and catalogo["3N8Y"]["site_chains"] == ["A"]
    serina = {l[12:16].strip(): tuple(float(l[i:i + 8]) for i in (30, 38, 46)) for l in fuente.splitlines()
              if l.startswith("ATOM") and l[21:22] == cadena and l[22:26].strip() == "530"}
    assert serina and all(l[17:20] == "SER" for l in fuente.splitlines()
                          if l.startswith(("ATOM", "HETATM")) and l[21:22] == cadena and l[22:26].strip() == "530")
    diclofenaco = _instancia(fuente, "DIF", "A", "701")
    # El carboxilato del diclofenaco toca el OG de la Ser530: el modo de unión invertido, contra Tyr385 y Ser530.
    assert min(math.dist(serina["OG"], p) for p in diclofenaco) <= 3.2
    assert min(math.dist(o, p) for o in _instancia(fuente, "OAS", "B", "530") for p in diclofenaco) > 30
