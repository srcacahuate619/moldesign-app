"""
AMP-11: el dossier distingue el receptor DECLARADO de la unidad ACOPLADA.

«Receptor declarado» dice lo que el caso pidió (en 3F75, la cadena A). La corrida
mide sobre los bytes del PDBQT cuáles cadenas contiene (A+P). Quien recibe el PDF
sin conocer la sesión necesita las dos: la declarada no demuestra que se acoplara
sólo contra ella.
"""

from __future__ import annotations

import io
import re

import pytest

from services.dossier.model import build_case_dossier
from services.dossier.pdf import render_dossier_pdf
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo

ETIQUETA = "Receptor acoplado (unidad preparada)"


def _caso(prepared_chains=None, *, con_procedencia=True, cadena_declarada="A"):
    caso = caso_completo()
    caso["projection"].inputs.receptor.pdb_id = "3F75"
    caso["projection"].inputs.receptor.chain = cadena_declarada
    protocolo = dict(caso["eval_result"].docking_protocol)
    if con_procedencia:
        protocolo["execution_provenance"] = {
            "receptor_sha256": "a" * 64,
            "receptor_prep": (
                {"prepared_chains": prepared_chains} if prepared_chains is not None else {"chain": "A"}
            ),
        }
    caso["eval_result"].docking_protocol = protocolo
    return caso


def _campo(dossier):
    return next(c for c in dossier.entradas if c.etiqueta == ETIQUETA)


def test_declarada_a_y_acoplada_a_mas_p_se_dicen_las_dos():
    campo = _campo(build_case_dossier(**_caso(["A", "P"])))
    assert campo.estado == Estado.REGISTRADO
    assert "3F75 · cadenas A+P" in campo.valor
    assert "el caso declaró la cadena A" in campo.valor
    assert "PDBQT" in campo.valor


def test_declarada_y_acoplada_coinciden_no_se_inventa_discrepancia():
    campo = _campo(build_case_dossier(**_caso(["A"])))
    assert campo.estado == Estado.REGISTRADO
    assert "cadenas A" in campo.valor
    assert "declaró" not in campo.valor


def test_la_cadena_declarada_sigue_apareciendo_como_declarada():
    dossier = build_case_dossier(**_caso(["A", "P"]))
    declarada = next(c for c in dossier.entradas if c.etiqueta == "Receptor declarado")
    assert "cadena A" in declarada.valor
    assert "P" not in declarada.valor.split("cadena A")[1]


@pytest.mark.parametrize("variante", [
    {"con_procedencia": False},
    {"prepared_chains": None},
    {"prepared_chains": []},
])
def test_sin_medida_se_declara_la_ausencia_no_se_reconstruye_de_la_peticion(variante):
    campo = _campo(build_case_dossier(**_caso(**variante)))
    assert campo.estado == Estado.NO_DISPONIBLE
    assert campo.valor is None
    assert "no prueba contra cuáles se acopló" in campo.razon


def test_la_unidad_acoplada_llega_al_pdf():
    pypdf = pytest.importorskip("pypdf", reason="el PDF se lee con pypdf")
    datos = render_dossier_pdf(build_case_dossier(**_caso(["A", "P"]))).getvalue()
    texto = "\n".join(p.extract_text() or "" for p in pypdf.PdfReader(io.BytesIO(datos)).pages)
    texto = re.sub(r"\s+", " ", texto)
    assert "Receptor acoplado (unidad preparada)" in texto
    assert "cadenas A+P" in texto


def test_la_corrida_mide_las_cadenas_sobre_los_bytes_que_hashea():
    """El hash y las cadenas salen del MISMO `receptor_content` (fuente leída)."""
    from pathlib import Path

    fuente = (Path(__file__).resolve().parents[1] / "services" / "docking" / "vina_service.py").read_text(
        encoding="utf-8"
    )
    assert "prepared_receptor_chains(receptor_content.decode" in fuente
    assert '"prepared_chains"' in fuente
    assert fuente.index("receptor_sha256 = hashlib.sha256(receptor_content)") < fuente.index('"prepared_chains"')
