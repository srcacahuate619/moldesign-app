"""
La resolución que enseña el catálogo es la que declara su propia estructura (QA1-005).

Medido sobre `GET /targets/` (380 receptores) frente al `REMARK   2 RESOLUTION.` de
`data/targets/<PDB>.pdb.gz`: 13 discrepaban, en los dos sentidos (5VA1 enseñaba
2,8 Å y su archivo declara 3,70; 3OSK enseñaba 2,5 y declara 1,80; 1GPK enseñaba
2,5 y su propio título dice «at 2.1A Resolution»).

La causa: `scripts/anotar_sitio_en_catalogo.py` rellenó las resoluciones AUSENTES
desde el `REMARK 2` («si es None»), y esas 13 ya traían un valor escrito a mano
que nunca se contrastó. El catálogo muestra la resolución en cada tarjeta del
selector de receptores, así que un número equivocado ahí es un dato de procedencia
equivocado.

Este archivo es la guardia: cualquier valor de `curated_targets.json` que no
coincida con la estructura que viaja en el instalador hace fallar la prueba.
"""

from __future__ import annotations

import gzip
import json
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
CATALOGO = RAIZ / "curated_targets.json"
ESTRUCTURAS = RAIZ / "data" / "targets"

_REMARK_2 = re.compile(r"^REMARK\s+2\s+RESOLUTION\.\s+([0-9]+(?:\.[0-9]+)?)\s+ANGSTROMS", re.MULTILINE)
TOLERANCIA = 0.005


def resolucion_declarada(texto_pdb: str) -> float | None:
    """La resolución del `REMARK 2`, o `None` si no la declara (RMN: «NOT APPLICABLE»)."""
    m = _REMARK_2.search(texto_pdb)
    return float(m.group(1)) if m else None


def _estructura(pdb_id: str) -> str | None:
    ruta = ESTRUCTURAS / f"{pdb_id}.pdb.gz"
    if not ruta.is_file():
        return None
    return gzip.open(ruta, "rt", encoding="utf-8", errors="replace").read()


# ── El guardián tiene que demostrar que ve ───────────────────────────


def test_el_lector_de_remark_2_ve_lo_que_debe_y_no_inventa_nada():
    assert resolucion_declarada("HEADER x\nREMARK   2 RESOLUTION.    2.10 ANGSTROMS.\nATOM") == 2.1
    assert resolucion_declarada("REMARK   2 RESOLUTION.    3.70 ANGSTROMS.") == 3.7
    assert resolucion_declarada("REMARK   2 RESOLUTION.    1.5 ANGSTROMS.") == 1.5
    # Sin resolución numérica no hay nada que contrastar: no se inventa un número.
    assert resolucion_declarada("REMARK   2 RESOLUTION. NOT APPLICABLE.") is None
    assert resolucion_declarada("HEADER sin remark") is None


def test_la_comparacion_detecta_una_discrepancia_y_deja_pasar_una_coincidencia():
    declarada = resolucion_declarada("REMARK   2 RESOLUTION.    2.10 ANGSTROMS.")
    assert abs(2.5 - declarada) > TOLERANCIA  # el valor erróneo de 1GPK: se detecta
    assert abs(2.1 - declarada) <= TOLERANCIA  # el valor correcto: pasa


# ── La guardia sobre el catálogo real ────────────────────────────────


def test_hay_catalogo_y_estructuras_que_comparar():
    assert CATALOGO.is_file()
    assert sum(1 for _ in ESTRUCTURAS.glob("*.pdb.gz")) > 300


def test_ninguna_resolucion_del_catalogo_contradice_a_su_estructura():
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    comparadas = 0
    discrepantes: list[str] = []
    for fila in catalogo:
        pdb_id = fila.get("pdb_id")
        valor = fila.get("resolution")
        texto = _estructura(pdb_id) if pdb_id else None
        if texto is None or valor is None:
            continue
        declarada = resolucion_declarada(texto)
        if declarada is None:
            continue
        comparadas += 1
        if abs(float(valor) - declarada) > TOLERANCIA:
            discrepantes.append(f"{pdb_id}: catálogo {valor} Å, estructura {declarada} Å")

    # Si no se compara casi nada, la guardia está ciega y «0 discrepancias» no significa nada.
    assert comparadas >= 350, f"sólo se compararon {comparadas} receptores: la guardia no ve"
    assert not discrepantes, "resoluciones del catálogo que no son las de su estructura:\n  " + "\n  ".join(discrepantes)
