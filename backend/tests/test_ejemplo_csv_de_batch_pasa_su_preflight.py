"""
El CSV de ejemplo que enseña la pantalla de Batch pasa el preflight de Batch (QA1-015).

Medido en la cápsula de QA: la ayuda de «Preparar el archivo» enseña

    smiles,name,active,control_role
    CCO,etanol,1,reference
    CC(=O)O,acido_acetico,0,none

y al comprobar exactamente ese archivo el preflight lo BLOQUEA: las dos filas son
`invalid_input` / `SMILES_NO_ADMISIBLE` («No molecule can enter this run»). Etanol y
ácido acético tienen tres y cuatro átomos pesados y `validate_smiles` —el mismo
validador que usa `/evaluation/submit`— no los admite. Quien copia el ejemplo para
probar la pantalla se encuentra con un callejón sin salida.

Esta guardia lee el ejemplo de `frontend/app/evaluation/batch/page.tsx` y exige que
sus filas sean elegibles. Es el mismo tipo de comprobación que
`limiteDelContexto.test.ts`: dos capas que tienen que decir lo mismo.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import rdkit_available

RAIZ = Path(__file__).resolve().parents[2]
PAGINA = RAIZ / "frontend" / "app" / "evaluation" / "batch" / "page.tsx"

_EJEMPLO = re.compile(r"`(smiles,name,active,control_role\n(?:[^`\n]+\n?)+)`")


def filas_del_ejemplo(codigo_de_la_pagina: str) -> list[dict[str, str]]:
    """Las filas del CSV de ejemplo, como diccionarios por columna."""
    m = _EJEMPLO.search(codigo_de_la_pagina.replace("\r\n", "\n"))
    assert m, "la pantalla de Batch ya no enseña un CSV de ejemplo con esa cabecera"
    lineas = [l for l in m.group(1).split("\n") if l.strip()]
    cabecera = lineas[0].split(",")
    return [dict(zip(cabecera, linea.split(","))) for linea in lineas[1:]]


# ── El lector del ejemplo tiene que demostrar que ve ─────────────────


def test_el_lector_extrae_las_filas_del_ejemplo():
    codigo = "x `smiles,name,active,control_role\nCCO,etanol,1,reference\nCC(=O)O,acido,0,none` y"
    filas = filas_del_ejemplo(codigo)
    assert [f["smiles"] for f in filas] == ["CCO", "CC(=O)O"]
    assert filas[0]["control_role"] == "reference"


def test_el_lector_se_queja_si_el_ejemplo_desaparece():
    with pytest.raises(AssertionError):
        filas_del_ejemplo("<pre>sin ejemplo</pre>")


@rdkit_available
def test_el_validador_rechaza_de_verdad_las_moleculas_diminutas():
    """El control negativo: lo que mostraba el ejemplo anterior se rechaza hoy y se rechazaría mañana."""
    from services.cohort.preflight import _evaluar_molecula

    for diminuta in ("CCO", "CC(=O)O"):
        _, razon, _ = _evaluar_molecula(diminuta)
        assert razon == "SMILES_NO_ADMISIBLE", diminuta


# ── La guardia real ──────────────────────────────────────────────────


@rdkit_available
def test_todas_las_filas_del_ejemplo_de_la_ayuda_son_elegibles():
    from services.cohort.preflight import _evaluar_molecula

    filas = filas_del_ejemplo(PAGINA.read_text(encoding="utf-8"))
    assert len(filas) >= 2, "un ejemplo con una sola fila no enseña el formato"
    rechazadas = []
    for fila in filas:
        _, razon, _ = _evaluar_molecula(fila["smiles"])
        if razon is not None:
            rechazadas.append(f"{fila.get('name')}: {fila['smiles']} → {razon}")
    assert not rechazadas, "el ejemplo de la ayuda de Batch no pasa su propio preflight:\n  " + "\n  ".join(rechazadas)


def test_el_ejemplo_enseña_una_referencia_con_su_etiqueta_activa():
    """El ejemplo existe para enseñar `active` y `control_role`: al menos una fila declara una referencia."""
    filas = filas_del_ejemplo(PAGINA.read_text(encoding="utf-8"))
    assert any(f.get("control_role") == "reference" and f.get("active") == "1" for f in filas)
    assert any(f.get("control_role") == "none" for f in filas)
