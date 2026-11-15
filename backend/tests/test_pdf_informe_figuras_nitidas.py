"""Grupo 3 de los arreglos de PDF (2026-11-11): figuras nítidas, sin deformar, con su título y con rótulos legibles.

La cápsula de QA midió en 14 de 14 informes: el perfil de energía y el SHAP a 141 dpi y con un 2 % de deformación (F3), el
diagrama de contactos con rótulos de ~4 pt y sin «Å» (F2) y figuras que abrían una página sin el título que las explica (F4).
Estas pruebas GENERAN el informe con una pose, un receptor y valores SHAP reales y miden el PDF.
"""
from __future__ import annotations

import importlib.util
import re

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None or importlib.util.find_spec("pypdf") is None,
    reason="reportlab o pypdf no disponibles en este entorno",
)

from tests.test_pdf_informe_figuras_y_cuadros import IMATINIB, _informe  # noqa: E402

SHAP = {"log_p": 0.31, "tpsa": -0.12, "molecular_weight": 0.08, "hbd": -0.05, "qed": 0.04, "sa_score": -0.02}
DPI_MINIMO = 200
DEFORMACION_MAXIMA = 0.005  # 0,5 %: el 2 % medido era visible en un círculo o una cuadrícula


def _pose_y_receptor() -> tuple[str, str]:
    """El imatinib en 3D y un receptor con un N de residuo a 2,9 Å de cada uno de tres heteroátomos suyos."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.AddHs(Chem.MolFromSmiles(IMATINIB))
    AllChem.EmbedMolecule(mol, randomSeed=11)
    AllChem.MMFFOptimizeMolecule(mol)
    conf = mol.GetConformer()
    n = mol.GetNumAtoms()
    centro = [sum(conf.GetAtomPosition(i)[k] for i in range(n)) / n for k in range(3)]
    elegidos = [a.GetIdx() for a in mol.GetAtoms() if a.GetSymbol() in ("N", "O")][:3]
    lineas = []
    for orden, idx in enumerate(elegidos, start=1):
        p = conf.GetAtomPosition(idx)
        v = [p[k] - centro[k] for k in range(3)]
        norma = sum(c * c for c in v) ** 0.5
        x, y, z = (p[k] + 2.9 * v[k] / norma for k in range(3))
        lineas.append(f"ATOM  {orden:5d}  N   ASP A{100 + orden:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           N")
    return Chem.MolToMolBlock(mol) + "$$$$\n", "\n".join(lineas) + "\n"


@pytest.fixture(scope="module")
def datos_con_figuras() -> bytes:
    pose, receptor = _pose_y_receptor()
    return _informe(pose_sdf=pose, receptor_pdb=receptor, shap=SHAP)


def _figuras(datos: bytes):
    from tests.pdf_geometria import paginas

    return [(n, f) for n, pagina in enumerate(paginas(datos), start=1) for f in pagina.figuras()]


def test_el_informe_con_pose_lleva_las_cuatro_figuras(datos_con_figuras):
    """Sin esto las demás pruebas podrían pasar sobre un informe sin figuras."""
    assert len(_figuras(datos_con_figuras)) >= 4


def test_ninguna_figura_baja_de_200_dpi(datos_con_figuras):
    malas = [(n, round(f.dpi)) for n, f in _figuras(datos_con_figuras) if f.dpi < DPI_MINIMO]
    assert not malas, f"figuras por debajo de {DPI_MINIMO} dpi (página, dpi): {malas}"


def test_ninguna_figura_sale_deformada(datos_con_figuras):
    malas = [(n, f"{f.deformacion:.1%}") for n, f in _figuras(datos_con_figuras) if f.deformacion > DEFORMACION_MAXIMA]
    assert not malas, f"figuras con la proporción cambiada (página, deformación): {malas}"


def test_el_diagrama_de_contactos_se_dibuja_a_un_tamano_en_que_se_lee(datos_con_figuras):
    """La figura de contactos es la única que se coloca bajo una tabla de contactos: debe medir al menos 250 pt de ancho."""
    from tests.pdf_geometria import paginas

    for n, pagina in enumerate(paginas(datos_con_figuras), start=1):
        textos = " ".join(t.texto for t in pagina.textos)
        if "Mapeo de Contactos" in textos or "Active Site Contact" in textos:
            anchas = [f for f in pagina.figuras() if 250 <= f.caja.ancho <= 400]
            assert anchas, f"p. {n}: el diagrama de contactos mide menos de 250 pt de ancho"
            return
    pytest.fail("el informe no tiene sección de contactos")


def test_la_leyenda_del_diagrama_dice_la_unidad(datos_con_figuras):
    import io

    import pypdf

    texto = re.sub(r"\s+", " ", "\n".join((p.extract_text() or "") for p in pypdf.PdfReader(io.BytesIO(datos_con_figuras)).pages))
    assert "distancia al átomo marcado, en Å" in texto


def test_los_rotulos_del_diagrama_no_llevan_el_glifo_que_rdkit_no_tiene():
    from services.blockchain.certificate_figures import _rotulo_dibujable

    assert _rotulo_dibujable("SER42 (2.90 Å)") == "SER42 (2.90)"
    assert _rotulo_dibujable("MET769, THR766 (2.90 Å)") == "MET769, THR766 (2.90)"
    assert _rotulo_dibujable("sin unidad") == "sin unidad"


@pytest.mark.parametrize("relleno", [0, 3, 6, 9, 12, 15])
def test_cada_figura_esta_en_la_pagina_de_su_titulo(relleno):
    """Con más o menos texto antes, ninguna figura abre una página sin el título que la explica (F4)."""
    from services.avisos import Severidad, aviso
    from tests.pdf_geometria import paginas

    pose, receptor = _pose_y_receptor()
    avisos = [aviso(f"RELLENO_{i}", Severidad.INFO, "Aviso de relleno que ocupa una línea del documento, número %d." % i)
              for i in range(relleno)]
    datos = _informe(pose_sdf=pose, receptor_pdb=receptor, shap=SHAP, avisos=avisos)

    import io

    import pypdf

    lector = pypdf.PdfReader(io.BytesIO(datos))
    geometria = paginas(datos)
    titulos = ("Perfiles de Energía por Pose", "Explicabilidad Científica", "SHAP del regresor", "Mapeo de Contactos")
    for titulo in titulos:
        paginas_con_titulo = [i for i, p in enumerate(lector.pages) if titulo in (p.extract_text() or "")]
        assert paginas_con_titulo, f"no se encontró «{titulo}»"
        i = paginas_con_titulo[0]
        assert geometria[i].figuras(), f"«{titulo}» (p. {i + 1}) no tiene su figura en la misma página"
