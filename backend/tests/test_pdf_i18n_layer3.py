from __future__ import annotations

import importlib.util
import re
import uuid

import pytest

from core.i18n import reset_request_locale, set_request_locale


def _capturar_pdf(monkeypatch: pytest.MonkeyPatch, idioma: str, configure=None) -> tuple[bytes, str, dict[str, str | None]]:
    from reportlab.platypus import KeepTogether as ReportLabKeepTogether
    from reportlab.platypus import Paragraph as ReportLabParagraph
    from reportlab.platypus import Table as ReportLabTable

    from core.models import EvaluationResultORM, MoleculeORM, TargetORM
    from services.blockchain import pdf_generator

    textos: list[str] = []
    metadatos: dict[str, str | None] = {}
    original_build = pdf_generator.SimpleDocTemplate.build

    def recoger(elemento) -> None:
        if isinstance(elemento, ReportLabParagraph):
            textos.append(elemento.getPlainText())
        elif isinstance(elemento, ReportLabTable):
            for fila in elemento._cellvalues:
                if isinstance(fila, (list, tuple)):
                    for celda in fila:
                        recoger(celda)
                else:
                    recoger(fila)
        elif isinstance(elemento, ReportLabKeepTogether):
            for hijo in elemento._content:
                recoger(hijo)
        elif isinstance(elemento, str):
            textos.append(elemento)

    def observar_build(documento, historia, *args, **kwargs):
        for elemento in historia:
            recoger(elemento)
        metadatos["title"] = getattr(documento, "title", None)
        metadatos["subject"] = getattr(documento, "subject", None)
        return original_build(documento, historia, *args, **kwargs)

    monkeypatch.setattr(pdf_generator.SimpleDocTemplate, "build", observar_build)

    target = TargetORM(
        pdb_id="5IKR",
        name="Cyclooxygenase-2",
        chain="A",
        is_private=False,
        description="Curated description; keep this input unchanged.",
    )
    molecule = MoleculeORM(
        smiles="O=C(O)c1ccccc1C(=O)O",
        name="Ácido Mefenámico (entrada)",
        smiles_hash="f" * 64,
    )
    molecule.target = target
    result = EvaluationResultORM(
        molecule_id=uuid.uuid4(),
        affinity_kcal=-5.78,
        docking_poses=[
            {"rank": 1, "affinity": -5.8, "rmsd_lb": 0.0, "rmsd_ub": 0.0},
            {"rank": 2, "affinity": -5.1, "rmsd_lb": 1.1, "rmsd_ub": 1.4},
        ],
        parsing_source="sdf",
        vina_version="1.2.7",
        vina_random_seed=42,
        scientific_warnings=[
            "Preparación en condición desolvatada: la estructura depositada no tenía aguas "
            "cristalográficas dentro de la caja de acoplamiento, así que el sitio no perdió ninguna al prepararlo."
        ],
        molecular_weight=180.16,
        log_p=1.4,
        tpsa=63.6,
        hbd=1,
        hba=4,
        rotatable_bonds=3,
        heavy_atom_count=13,
        ring_count=2,
        lipinski_pass=True,
        veber_pass=True,
        qed=0.93,
        sa_score=1.9,
    )
    result.task_id = "run-report-0001"
    if configure:
        configure(target, result)

    token = set_request_locale(idioma)
    try:
        pdf = pdf_generator.generate_certificate_pdf(molecule, result, target.name)
    finally:
        reset_request_locale(token)
    return pdf.getvalue(), re.sub(r"\s+", " ", " ".join(textos)), metadatos


@pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None,
    reason="reportlab no disponible",
)
def test_pdf_de_capa_3_se_localiza_y_preserva_identidades(monkeypatch: pytest.MonkeyPatch) -> None:
    pdf, texto, metadatos = _capturar_pdf(monkeypatch, "en")

    assert pdf.startswith(b"%PDF")
    assert "EVALUATION REPORT" in texto
    assert "Report purpose" in texto
    assert "Co-crystallized ligand: Mefenamic acid" in texto
    assert "Desolvated preparation:" in texto
    assert "Run: run-report-0001." in texto
    assert "case dossier" in texto
    assert "Evidence, reproducibility, assumptions, checks, and uncertainties" in texto
    assert "Open assumptions and uncertainties" in texto
    assert "Recorded assumptions" in texto
    assert "Open uncertainties" in texto
    assert "Input system:" in texto
    assert "Pose search:" in texto
    assert "Derived models:" in texto
    assert "Physical validity:" in texto
    assert "Computational nature:" in texto
    assert "ADMET limitations:" in texto
    assert "Selectivity:" in texto
    assert "Reproducibility:" in texto
    assert "Minimum traces 3/3" in texto
    assert "2 serialized poses; best raw affinity -5.80 kcal/mol 1.2.7." in texto
    assert "Contact map not evaluated: missing SDF pose, receptor PDB structure." in texto
    assert "Aqueous solubility (LogS)" in texto
    assert "Modeled property (ADMET-AI)" in texto
    assert "NOT REPORTED model not reported." in texto
    assert "Ácido Mefenámico (entrada)" in texto
    assert "Curated description; keep this input unchanged." in texto
    assert "INFORME DE EVALUACIÓN" not in texto
    assert "Propósito del informe" not in texto
    assert "Naturaleza computacional:" not in texto
    assert "Limitaciones ADMET:" not in texto
    assert "Selectividad:" not in texto
    assert "Reproducibilidad:" not in texto
    assert "Supuestos registrados" not in texto
    assert "Incertidumbres abiertas" not in texto
    assert "Solubilidad Acuosa" not in texto
    assert "modelo no informado" not in texto
    assert not re.search(r"[áéíóúñ¿¡]", texto.replace("Ácido Mefenámico (entrada)", ""))
    assert metadatos["title"].startswith("Evaluation report · 5IKR")
    assert metadatos["subject"] == "Evaluation report for one run (not the case dossier)"


@pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None,
    reason="reportlab no disponible",
)
def test_pdf_conserva_el_español_al_renderizar_en_es(monkeypatch: pytest.MonkeyPatch) -> None:
    _pdf, texto, metadatos = _capturar_pdf(monkeypatch, "es-MX")

    assert "INFORME DE EVALUACIÓN" in texto
    assert "Propósito del informe" in texto
    assert "Corrida: run-report-0001." in texto
    assert "Sistema de entrada:" in texto
    assert "Naturaleza computacional:" in texto
    assert "Supuestos registrados" in texto
    assert "Ácido Mefenámico (entrada)" in texto
    assert "EVALUATION REPORT" not in texto
    assert metadatos["title"].startswith("Informe de evaluación · 5IKR")
