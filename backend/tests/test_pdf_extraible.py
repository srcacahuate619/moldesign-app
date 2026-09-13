"""Doc 71, D2 y E5: el dossier tiene que poder leerse, buscarse y copiarse.

Un PDF que se ve bien en pantalla y se extrae mal no sirve para lo que existe:
un revisor que busca un termino, un lector de pantalla, un `grep` sobre el
documento. Estas pruebas GENERAN el certificado de verdad y miran lo que sale al
extraerlo, en vez de inspeccionar el codigo que lo compone.

# D2 — los marcadores de lista salian como caracteres de control

`•` (U+2022) se extraia como **U+007F**, el caracter DEL. La causa no es el
texto sino la fuente: `font_path` apunta a `/usr/share/fonts/truetype/dejavu/…`,
una ruta de Linux que en Windows -la plataforma real del producto- nunca existe,
asi que se cae a Courier. Ni Courier ni Helvetica llevan el glifo del bullet en
su codificacion y ReportLab lo sustituye.

MEDIDO generando un PDF y extrayendo con pypdf:

    -   U+002D  sobrevive        •   U+2022  ->  U+007F
    *   U+002A  sobrevive        ⚠   U+26A0  ->  ■
    ·   U+00B7  sobrevive        ▪   U+25AA  ->  ■
    →   U+2192  sobrevive        ✓   U+2713  sobrevive

Se usa el punto medio, que es el mas parecido a una vineta de los que
sobreviven.

# E5 — paginacion

Una frase cortada entre paginas y una pagina con solo la ultima fila del
apendice. `allowWidows` viene en 1 por defecto en ReportLab y permite dejar sola
la ultima linea de un parrafo.
"""

from __future__ import annotations

import importlib.util
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None or importlib.util.find_spec("pypdf") is None,
    reason="reportlab o pypdf no disponibles en este entorno",
)


def _documento():
    """Un certificado real, con el mismo material que `test_report_contract`."""
    from core.models import EvaluationResultORM, MoleculeORM, TargetORM
    from services.blockchain import pdf_generator

    target = TargetORM(
        pdb_id="7E2Y", name="5-HT1A serotonin receptor", chain="R",
        grid_center_x=103.03, grid_center_y=114.79, grid_center_z=108.36,
        description="Receptor de serotonina 5-HT1A acoplado a proteina G.",
        requires_cns=True, is_private=False, spearman_rho=0.512,
    )
    mol = MoleculeORM(smiles="CC(=O)Oc1ccccc1C(=O)O", name="Aspirina", smiles_hash="d" * 64)
    mol.target = target
    eval_result = EvaluationResultORM(
        molecule_id=uuid.uuid4(),
        affinity_kcal=-5.78, affinity_score=62.1, total_score=71.2,
        adme_score=68.0, druglikeness_score=70.0, gnn_score=0.5,
        docking_poses=[
            {"rank": 1, "affinity": -5.8, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
            {"rank": 2, "affinity": -5.1, "rmsd_lb": 1.1, "rmsd_ub": 1.4},
        ],
        parsing_source="sdf", vina_version="1.2.5", vina_random_seed=42,
        scientific_warnings=["grid no validado"], hotspots_hit=["ASP116"],
        molecular_weight=180.16, log_p=1.4, tpsa=63.6, hbd=1, hba=4,
        rotatable_bonds=3, heavy_atom_count=13, ring_count=2,
        lipinski_pass=True, veber_pass=True, qed=0.93, sa_score=1.9,
    )
    buf = pdf_generator.generate_certificate_pdf(mol, eval_result, target.name)
    buf.seek(0)
    return buf


def _paginas() -> list[str]:
    import pypdf

    return [p.extract_text() or "" for p in pypdf.PdfReader(_documento()).pages]


# ── D2 ───────────────────────────────────────────────────────────────────────

def test_el_texto_extraido_no_tiene_caracteres_de_control():
    """U+007F en el texto extraido rompe busqueda, copiado y accesibilidad."""
    texto = "\n".join(_paginas())
    control = sorted({
        hex(ord(c)) for c in texto
        if ord(c) < 32 and c not in "\n\r\t" or ord(c) == 127
    })
    assert not control, (
        f"el dossier extrae caracteres de control {control}. Suele ser un glifo "
        "que la fuente no tiene y ReportLab sustituye: revisa la tabla de "
        "marcadores del docstring antes de anadir simbolos nuevos."
    )


def test_no_quedan_glifos_que_se_extraen_como_cuadrado():
    """`⚠` y `▪` salen como ■: un simbolo que no se puede leer ni buscar."""
    texto = "\n".join(_paginas())
    assert "■" not in texto, (
        "hay un glifo que la fuente no tiene. El PDF lo dibuja como un cuadrado "
        "y se extrae como tal."
    )


def test_la_vineta_elegida_sobrevive_a_la_extraccion():
    """No basta con que no falle: la vineta tiene que seguir ahi."""
    from services.blockchain.pdf_generator import VINETA

    assert VINETA == "·"
    texto = "\n".join(_paginas())
    assert VINETA in texto, "las vinetas desaparecieron del texto extraido"


# ── E5 ───────────────────────────────────────────────────────────────────────

def test_ninguna_pagina_queda_practicamente_vacia():
    """«La pagina 7 contiene solo la ultima fila del apendice».

    Una pagina con cuatro palabras no es un problema estetico: es una pagina que
    el lector pasa buscando contenido que no esta, y sugiere que el documento
    se corto donde no debia.
    """
    paginas = _paginas()
    assert len(paginas) >= 2, "el documento de prueba deberia ocupar varias paginas"
    escasas = [
        (i + 1, len(t.strip()))
        for i, t in enumerate(paginas)
        if len(t.strip()) < 120
    ]
    assert not escasas, (
        f"paginas con casi nada de contenido (numero, caracteres): {escasas}"
    )


def test_los_estilos_no_permiten_lineas_viudas():
    """`allowWidows = 1` es el defecto de ReportLab y deja sola la ultima linea
    de un parrafo al principio de la pagina siguiente."""
    import inspect

    from services.blockchain import pdf_generator

    fuente = inspect.getsource(pdf_generator.generate_certificate_pdf)
    assert "allowWidows = 0" in fuente
