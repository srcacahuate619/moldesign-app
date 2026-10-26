"""
AMP-07 / AMP-08: dos documentos, dos identidades, y un PDF que se ve igual en
cualquier visor.

La auditoría descargó los dos PDF sobre el mismo resultado: ambos se titulaban
«DOSSIER DE EVIDENCIA COMPUTACIONAL» y tenían contenido, vínculo con el caso y
metadatos distintos (el heredado salía con Title y Author «(anonymous)»). Y en
la primera página del heredado, el nombre largo del receptor pisaba «Página 1
de 7»; el dossier usaba Helvetica/Symbol sin incrustar y Poppler dejó huecos en
α, β, Δ y ≤.

Lo que se fija:

1. el informe heredado se llama INFORME DE EVALUACIÓN, dice que no es el dossier
   del caso, identifica la corrida y trae sus metadatos;
2. el pie no pisa el número de página, sin perder afinidad ni estado;
3. el dossier incrusta una TrueType y los símbolos científicos sobreviven;
4. la nota de validez física del informe no repite la frase falsa de que no hay
   validador en producción.
"""

from __future__ import annotations

import importlib.util
import io
import re
import uuid

import pytest

pytestmark = pytest.mark.skipif(
    importlib.util.find_spec("reportlab") is None, reason="reportlab no disponible"
)
pypdf = pytest.importorskip("pypdf", reason="los PDF se leen con pypdf")


def _informe(
    *,
    task_id: str | None = "task-informe-0001",
    pdb_id: str = "3F75",
    target_name: str = "Cyclooxygenase-2",
    structural_evidence: dict | None = None,
):
    from core.models import EvaluationResultORM, MoleculeORM, TargetORM
    from services.blockchain.pdf_generator import generate_certificate_pdf

    target = TargetORM(pdb_id=pdb_id, name=target_name, chain="A", is_private=False)
    mol = MoleculeORM(smiles="O=C(O)c1ccccc1", name="Ácido benzoico", smiles_hash="a" * 64)
    mol.target = target
    resultado = EvaluationResultORM(
        molecule_id=uuid.uuid4(),
        affinity_kcal=-5.548, affinity_score=55.4, total_score=58.0,
        docking_poses=[{"rank": 1, "affinity": -5.548, "rmsd_lb": 0.0, "rmsd_ub": 0.0}],
        parsing_source="sdf", vina_version="1.2.7", vina_random_seed=42,
        molecular_weight=122.12, log_p=1.9, tpsa=37.3, hbd=1, hba=2,
        rotatable_bonds=1, heavy_atom_count=9, ring_count=1,
        lipinski_pass=True, veber_pass=True, qed=0.81, sa_score=1.3,
        task_id=task_id,
        structural_evidence=structural_evidence,
    )
    return generate_certificate_pdf(mol, resultado, target.name)


#: Una corrida cuyo validador SÍ emitió veredicto, para que el documento tenga
#: algo que contradecir: es la condición que SCI-A-008 necesita.
EVIDENCIA_CON_VEREDICTO = {
    "stage_status": "review",
    "poses_produced": 3,
    "poses_evaluated": 2,
    "validation_engine": "PoseBusters 0.6.5",
}


def _dossier_pdf(pregunta: str | None = None):
    from services.dossier.model import build_case_dossier
    from services.dossier.pdf import render_dossier_pdf
    from tests.fixtures_dossier import caso_completo

    caso = caso_completo()
    if pregunta is not None:
        caso["projection"].context.question = pregunta
    return render_dossier_pdf(build_case_dossier(**caso))


def _leer(buf) -> "pypdf.PdfReader":
    return pypdf.PdfReader(io.BytesIO(buf.getvalue()))


def _texto(lector, pagina: int | None = None) -> str:
    paginas = lector.pages if pagina is None else [lector.pages[pagina]]
    return re.sub(r"\s+", " ", "\n".join(p.extract_text() or "" for p in paginas))


# ── 1. Identidad de los dos documentos ────────────────────────────────


class TestIdentidad:
    def test_los_dos_documentos_ya_no_se_titulan_igual(self):
        informe = _texto(_leer(_informe()), 0)
        dossier = _texto(_leer(_dossier_pdf()), 0)
        assert "INFORME DE EVALUACIÓN" in informe
        assert "DOSSIER DE EVIDENCIA COMPUTACIONAL" not in informe
        assert "DOSSIER DE EVIDENCIA COMPUTACIONAL" in dossier
        assert "INFORME DE EVALUACIÓN" not in dossier

    def test_el_informe_dice_que_no_es_el_dossier_del_caso(self):
        texto = _texto(_leer(_informe()), 0)
        assert "dossier del caso" in texto
        assert "es otro documento" in texto

    def test_el_informe_identifica_la_corrida_para_poder_cruzarlo_con_el_dossier(self):
        assert "task-informe-0001" in _texto(_leer(_informe()), 0)

    def test_sin_task_id_se_declara_la_ausencia(self):
        assert "Corrida no identificada" in _texto(_leer(_informe(task_id=None)), 0)

    def test_el_informe_ya_no_se_llama_dossier_en_su_cuerpo(self):
        texto = _texto(_leer(_informe()))
        assert "Propósito del informe" in texto
        assert "Propósito del dossier" not in texto

    def test_metadatos_propios_y_distintos_no_anonymous(self):
        meta_informe = _leer(_informe()).metadata
        meta_dossier = _leer(_dossier_pdf()).metadata
        for meta in (meta_informe, meta_dossier):
            assert meta.author == "MolDesign"
            assert "anonymous" not in str(meta.title).lower()
        assert meta_informe.title.startswith("Informe de evaluación")
        assert meta_dossier.title.startswith("Dossier")
        assert meta_informe.title != meta_dossier.title


# ── 2. El pie no pisa la numeración ───────────────────────────────────


class TestPie:
    def test_el_pie_largo_se_acorta_en_la_cabeza_y_conserva_el_resto(self):
        from reportlab.pdfbase import pdfmetrics
        from services.blockchain.pdf_generator import _ajustar_a_ancho

        cabeza = "3F75 (Cyclooxygenase-2 in complex with a very long structure title that never ends)"
        resto = " | -5.55 kcal/mol | Estado: REVISIÓN NECESARIA | MolDesign"
        ancho = 330.0
        ajustado = _ajustar_a_ancho(cabeza, resto, "Helvetica", 7, ancho)
        assert pdfmetrics.stringWidth(ajustado, "Helvetica", 7) <= ancho
        assert ajustado.endswith(resto)
        assert "…" in ajustado
        assert ajustado.startswith("3F75")

    def test_un_pie_que_cabe_no_se_toca(self):
        from services.blockchain.pdf_generator import _ajustar_a_ancho

        assert _ajustar_a_ancho("3F75 (COX-2)", " | MolDesign", "Helvetica", 7, 400.0) == "3F75 (COX-2) | MolDesign"

    def test_el_pie_real_con_receptor_largo_no_pisa_la_numeracion(self):
        """Mide la caja dibujada, no sólo la función: izquierda y derecha no se cruzan."""
        from reportlab.pdfbase import pdfmetrics
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import cm
        from services.blockchain import pdf_generator as G

        dibujado: list[tuple[str, float]] = []

        class Lienzo(G.NumberedCanvas):
            def drawString(self, x, y, texto, *a, **k):  # noqa: N802
                if abs(y - 0.8 * cm) < 0.01:
                    dibujado.append(("izq", x + pdfmetrics.stringWidth(texto, "Helvetica", 7)))
                return super().drawString(x, y, texto, *a, **k)

            def drawRightString(self, x, y, texto, *a, **k):  # noqa: N802
                if abs(y - 0.8 * cm) < 0.01:
                    dibujado.append(("der", x - pdfmetrics.stringWidth(texto, "Helvetica", 7)))
                return super().drawRightString(x, y, texto, *a, **k)

        original = G.NumberedCanvas
        G.NumberedCanvas = Lienzo
        try:
            _informe(pdb_id="3F75", target_name="Cyclooxygenase-2 " + "estructura-con-nombre-larguisimo " * 4)
        finally:
            G.NumberedCanvas = original
        izquierdos = [fin for lado, fin in dibujado if lado == "izq"]
        derechos = [ini for lado, ini in dibujado if lado == "der"]
        assert izquierdos and derechos
        assert max(izquierdos) < min(derechos), "el pie izquierdo invade «Página N de M»"
        assert max(derechos) <= A4[0]


# ── 3. Fuente incrustada en el dossier ────────────────────────────────


class TestFuenteIncrustada:
    PREGUNTA = "Efecto de α y β sobre ΔG ≤ -7 kcal/mol con ≥ 1 Å → ±"

    def test_el_dossier_incrusta_una_truetype_y_los_simbolos_sobreviven(self):
        from services.dossier.pdf import fuente_de_texto_incrustada

        if not fuente_de_texto_incrustada():
            pytest.skip("este equipo no tiene Arial/DejaVu/Liberation: el dossier cae a Helvetica")
        lector = _leer(_dossier_pdf(self.PREGUNTA))
        fuentes = {}
        for pagina in lector.pages:
            for _, ref in (pagina["/Resources"].get("/Font") or {}).items():
                fuente = ref.get_object()
                descriptor = fuente.get("/FontDescriptor")
                incrustada = bool(descriptor) and "/FontFile2" in descriptor.get_object()
                fuentes[str(fuente["/BaseFont"])] = (str(fuente["/Subtype"]), incrustada)
        truetype = {n: v for n, v in fuentes.items() if v[0] == "/TrueType"}
        assert truetype and all(incrustada for _, incrustada in truetype.values())
        texto = _texto(lector)
        for simbolo in "αβΔ≤≥→±Å":
            assert simbolo in texto, f"se perdió {simbolo!r}"

    def test_sin_fuente_del_sistema_se_declara_y_el_documento_sigue_generandose(self, monkeypatch):
        from services.dossier import pdf as P

        monkeypatch.setattr(P, "_FUENTES_DE_TEXTO", None)
        monkeypatch.setattr(P, "_CANDIDATAS_DE_FUENTE", ())
        assert P.fuente_de_texto_incrustada() is False
        assert _dossier_pdf(self.PREGUNTA).getvalue()[:4] == b"%PDF"
        monkeypatch.setattr(P, "_FUENTES_DE_TEXTO", None)  # no contaminar a los demás


# ── 4. La nota de validez física ya no miente ─────────────────────────


class TestNotaDeValidezFisica:
    def test_no_repite_que_no_hay_validador_en_produccion(self):
        texto = _texto(_leer(_informe()))
        assert "no ejecuta un validador geometrico" not in texto

    def test_sin_evaluacion_dice_que_no_se_evaluo_y_que_eso_no_habla_de_las_poses(self):
        texto = _texto(_leer(_informe()))
        assert "no se evaluaron" in texto
        assert "Eso no dice nada sobre las poses" in texto

    def test_con_veredicto_remite_a_el_y_recuerda_su_limite(self):
        from services.blockchain.pdf_generator import _nota_de_validez_fisica

        nota = _nota_de_validez_fisica({"physical_validity": {"status": "review", "label": "Requiere revisión"}})
        assert "Requiere revisión" in nota
        assert "no es una pose aprobada" in nota
        assert "no se evaluaron" not in nota


# ── 5. La metodología no contradice a la matriz del mismo PDF ──────────
#
# SCI-A-008 de la auditoría de ciencia: la nota condicional de arriba y
# `evidence_summary` ya se habían corregido, pero la sección «Metodología
# observada y procedencia» conservaba impresa a mano la frase «Validez física:
# no evaluada en esta versión de producción». El mismo documento registraba el
# veredicto en su matriz y lo negaba tres páginas después, firmado con su
# SHA-256. La frase es ahora condicional, y estas pruebas cubren las dos ramas
# para que el arreglo no se pueda revertir en silencio ni invertir su error.


class TestMetodologiaYValidezFisica:
    FRASE_FALSA = "no evaluada en esta versión de producción"

    def test_con_veredicto_la_metodologia_no_lo_niega(self):
        texto = _texto(_leer(_informe(structural_evidence=EVIDENCIA_CON_VEREDICTO)))
        assert self.FRASE_FALSA not in texto
        assert "emitieron veredicto" in texto

    def test_sin_veredicto_la_metodologia_no_se_inventa_uno(self):
        texto = _texto(_leer(_informe()))
        assert self.FRASE_FALSA not in texto
        assert "no llegaron a emitir veredicto" in texto
        assert "emitieron veredicto (" not in texto

    # La frase en sí, sus dos ramas y su traducción se comprueban en
    # `test_metodologia_validez_fisica.py`, que no necesita pypdf y por tanto
    # también corre con el intérprete que se distribuye.

    @pytest.mark.parametrize("evidencia", [None, EVIDENCIA_CON_VEREDICTO])
    def test_el_parrafo_entero_llega_en_ingles_al_lector_ingles(self, evidencia):
        """La plantilla cubre el párrafo COMPLETO, con la frase condicional dentro.

        `traducir` es todo-o-nada por frase: una frase sin pareja deja el
        párrafo entero en castellano. Al condicionar la validez física había que
        mover su frase a `{frase1}` y catalogar las dos ramas, o el arreglo de
        SCI-A-008 habría creado el defecto de SCI-A-026 en el PDF inglés.
        """
        from core.i18n import reset_request_locale, set_request_locale

        token = set_request_locale("en")
        try:
            texto = _texto(_leer(_informe(structural_evidence=evidencia)))
        finally:
            reset_request_locale(token)

        assert "<b>Physical validity:</b>" not in texto  # el marcado no se imprime
        assert "Physical validity:" in texto
        assert "External geometric analysis should be documented" in texto
        assert "Validez física" not in texto
        assert "El análisis geométrico externo" not in texto
