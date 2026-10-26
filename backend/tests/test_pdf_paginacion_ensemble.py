"""
El PDF heredado pagina el contenido largo de la corrida (CAS-06 / AMP-04).

La auditoría lo midió en vivo: abrir en el historial un resultado de
ensemble y pedir «Dossier PDF» devolvía HTTP 500. El backend registraba
`reportlab.platypus.doctemplate.LayoutError: Table ... 1 rows x 2 cols
(tallest row 5336) ... too large on page 3` — la sección «Supuestos e
incertidumbres abiertas» del PDF heredado metía TODOS los supuestos en una
celda y TODAS las incertidumbres en la otra, y ReportLab fragmenta tablas
ENTRE filas, nunca DENTRO de una fila: una tabla de una sola fila de 5336
puntos contra un marco de ~745 no cabe en ninguna página.

En ensemble las incertidumbres se disparan porque los avisos del receptor se
repiten por conformación (CAS-07: 64 avisos en ensemble-M01), y entran crudos
porque `build_evidence_summary` hace `uncertainties.extend(scientific_warnings)`.

LA REGLA DE ESTE ARCHIVO, del criterio de cierre de la auditoría: la
paginación divide el contenido largo; JAMÁS lo recorta para caber. Cada aviso
que entró a la corrida tiene que salir en el documento.
"""

from __future__ import annotations

import importlib.util
import re
import uuid

import pytest

reportlab_disponible = importlib.util.find_spec("reportlab") is not None
pypdf_disponible = importlib.util.find_spec("pypdf") is not None

pytestmark = pytest.mark.skipif(
    not reportlab_disponible, reason="reportlab no disponible en este entorno"
)


#: Más avisos que los 64 de ensemble-M01 que la auditoría midió: si esto
#: pagina, cualquier contenido real de ensemble pagina.
AVISOS_DE_PRUEBA = 90


def _avisos_de_ensemble(n: int = AVISOS_DE_PRUEBA) -> list[str]:
    """Avisos con la forma de los que el ensemble repite: los del receptor,
    una vez por conformación acoplada."""
    avisos: list[str] = []
    for i in range(n):
        conformacion = i // 2 + 1
        if i % 2 == 0:
            avisos.append(
                "RECEPTOR_PROTONACION_DECLARADA: Plantillas de histidina de Meeko: "
                f"HIS57=HIE. Aviso repetido por la conformación {conformacion} del ensemble."
            )
        else:
            avisos.append(
                f"SITIO_DESOLVATADO: se retiraron 10 aguas estructurales a ≤6 Å del sitio "
                f"(conformación {conformacion} del ensemble)."
            )
    return avisos


def _corrida_de_ensemble(avisos: list[str]):
    from core.models import EvaluationResultORM, MoleculeORM, TargetORM

    target = TargetORM(
        pdb_id="3F75", name="Cyclooxygenase-2", chain="A",
        grid_center_x=43.21, grid_center_y=2.19, grid_center_z=46.19,
        is_private=False,
    )
    mol = MoleculeORM(
        smiles="O=C(O)c1ccccc1", name="Ácido benzoico", smiles_hash="a" * 64
    )
    mol.target = target
    eval_result = EvaluationResultORM(
        molecule_id=uuid.uuid4(),
        affinity_kcal=-5.548, affinity_score=55.4, total_score=58.0,
        docking_poses=[{"rank": 1, "affinity": -5.548, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
        parsing_source="sdf", vina_version="1.2.7", vina_random_seed=42,
        scientific_warnings=avisos,
        molecular_weight=122.12, log_p=1.9, tpsa=37.3, hbd=1, hba=2,
        rotatable_bonds=1, heavy_atom_count=9, ring_count=1,
        lipinski_pass=True, veber_pass=True, qed=0.81, sa_score=1.3,
    )
    return mol, eval_result, target


def _pdf_de_ensemble(avisos: list[str]):
    from services.blockchain.pdf_generator import generate_certificate_pdf

    mol, eval_result, target = _corrida_de_ensemble(avisos)
    return generate_certificate_pdf(mol, eval_result, target.name)


def _texto_normalizado(buf) -> str:
    """El texto del PDF con el espacio colapsado: el ajuste de línea de una
    celda de 245 pt parte los avisos, y comparar sin normalizar daría falsos
    negativos por un simple salto de línea."""
    import pypdf

    texto = "\n".join(
        page.extract_text() or "" for page in pypdf.PdfReader(buf).pages
    )
    return re.sub(r"\s+", " ", texto)


# ── La reproducción de la auditoría ───────────────────────────────────


def test_el_pdf_de_ensemble_se_genera_en_vez_de_reventar():
    """Antes de la corrección: LayoutError, HTTP 500 y ningún documento.

    Una tabla de UNA fila con todos los avisos en la celda no puede
    fragmentarse entre páginas; con 64 avisos la fila medía 5336 pt y el
    marco 745. Con más contenido que el caso real de la auditoría, la
    composición tiene que terminar y devolver un PDF.
    """
    buf = _pdf_de_ensemble(_avisos_de_ensemble())

    contenido = buf.getvalue()
    assert contenido[:4] == b"%PDF"
    assert len(contenido) > 1000


def test_el_pdf_pequeno_sigue_siendo_un_pdf():
    """La corrida única con pocos avisos — el caso que ya funcionaba — no
    cambia: sigue generando."""
    buf = _pdf_de_ensemble(["grid no validado"])
    assert buf.getvalue()[:4] == b"%PDF"


# ── La paginación no recorta: todo el contenido sale ─────────────────


@pytest.mark.skipif(
    not pypdf_disponible, reason="pypdf no viaja en el bundle; extracción no disponible"
)
def test_cada_aviso_de_la_corrida_sale_en_el_documento():
    """Criterio de cierre de CAS-06: «La corrección no debe ocultar
    incertidumbres para conseguir un PDF». Los 90 avisos entran, los 90
    tienen que salir — la paginación divide, no selecciona."""
    avisos = _avisos_de_ensemble()
    buf = _pdf_de_ensemble(avisos)
    texto = _texto_normalizado(buf)

    for aviso in avisos:
        assert re.sub(r"\s+", " ", aviso) in texto, (
            f"un aviso de la corrida desapareció del PDF: {aviso[:60]}…"
        )


@pytest.mark.skipif(
    not pypdf_disponible, reason="pypdf no viaja en el bundle; extracción no disponible"
)
def test_el_contenido_largo_reparte_entre_paginas():
    """Paginación de verdad: el documento crece en páginas, no en una celda
    imposible."""
    import pypdf

    buf = _pdf_de_ensemble(_avisos_de_ensemble())
    assert len(pypdf.PdfReader(buf).pages) > 1

    texto = _texto_normalizado(buf)
    assert "Supuestos e incertidumbres abiertas" in texto
