"""El idioma de exportación no reescribe la evidencia ni los datos personales."""

from core.i18n_plantillas import traducir
from core.i18n import reset_request_locale, set_request_locale
from services.dossier.localization import traducir_dossier
from services.dossier.model import Campo, build_case_dossier
from services.dossier.package import _readme, _receta
from services.dossier.taxonomy import Estado
from tests.fixtures_dossier import caso_completo


def test_traduce_las_etiquetas_del_modelo_y_conserva_nombres_y_valores():
    dossier = build_case_dossier(**caso_completo())
    nombre = "2 elegidos de 8 del catálogo: Aspirina"
    dossier.case_name = nombre
    dossier.portada[0] = Campo("Caso", nombre)

    en = traducir_dossier(dossier, "en")

    assert en is not dossier
    assert en.case_name == nombre
    assert en.portada[0].etiqueta == "Case"
    assert en.portada[0].valor == nombre
    assert dossier.portada[0].etiqueta == "Caso"
    assert dossier.portada[0].valor == nombre


def test_solo_traduce_el_valor_cuando_es_una_clasificacion():
    dato = Campo("Estado", "NO EVALUADO", Estado.NO_EVALUADO)
    clasificacion = Campo(
        "Estado", "NO EVALUADO", Estado.NO_EVALUADO, valor_es_clasificacion=True
    )

    assert traducir_dossier(dato, "en").valor == "NO EVALUADO"
    assert traducir_dossier(clasificacion, "en").valor == "NOT EVALUATED"


def test_traduce_valores_explicativos_y_conserva_codigos_y_datos_de_persona():
    explicacion = Campo("Explicación", "La corrida no registró la semilla.")
    estado = Campo("Estado", "NO EVALUADO", Estado.NO_EVALUADO)
    caso = Campo("Caso", "La corrida no registró la semilla.")

    assert traducir_dossier(explicacion, "en").valor == "This run did not record the seed."
    assert traducir_dossier(estado, "en").valor == "NO EVALUADO"
    assert traducir_dossier(caso, "en").valor == "La corrida no registró la semilla."


def test_traduce_la_auditoria_de_preparacion_sin_cambiar_claves_ni_fuentes():
    auditoria = {
        "alcance": "Auditor de readiness para FEP en desarrollo",
        "bloques": [{
            "id": "receptor",
            "requisitos": [{
                "clave": "receptor.protonacion",
                "etiqueta": "Protonación del receptor",
                "valor": "Asignación por plantilla, sin pH experimental: el estado de histidinas, ácidos y bases del sitio no está validado.",
                "estado": "REVISAR",
                "fuente": "receptor_prep.protonation_method",
            }],
        }],
    }

    en = traducir_dossier(auditoria, "en")

    requisito = en["bloques"][0]["requisitos"][0]
    assert en["alcance"] == "FEP readiness auditor in development"
    assert requisito["etiqueta"] == "Receptor protonation"
    assert requisito["valor"] == (
        "Template-based assignment, without experimental pH: the state of site "
        "histidines, acids, and bases has not been validated."
    )
    assert requisito["clave"] == "receptor.protonacion"
    assert requisito["estado"] == "REVISAR"
    assert requisito["fuente"] == "receptor_prep.protonation_method"


def test_readme_y_receta_del_paquete_salen_en_ingles_y_conservan_el_nombre():
    dossier = build_case_dossier(**caso_completo())
    dossier.case_name = "Nombre de prueba Ácida"
    dossier.portada[0] = Campo("Caso", dossier.case_name)
    en = traducir_dossier(dossier, "en")

    locale_token = set_request_locale("en")
    try:
        readme = _readme(en, [], "moldesign_case_example")
        receta = _receta(en, "moldesign_case_example")
    finally:
        reset_request_locale(locale_token)

    assert "# Reproducible dossier · Nombre de prueba Ácida" in readme
    assert "The verifiable counterpart to `dossier.pdf`" in readme
    assert "No es una recomendación" not in readme
    assert "# How to reproduce this run" in receta
    assert "Check integrity first" in receta
    assert "el archivo" not in receta.lower()


def test_pdf_del_caso_entrega_cadenas_localizadas_al_renderizador(monkeypatch):
    from reportlab.platypus import Paragraph, Table

    from core.i18n import reset_request_locale, set_request_locale
    from services.dossier import pdf as dossier_pdf

    nombre = "Nombre de prueba Ácida"
    dossier = build_case_dossier(**caso_completo())
    dossier.case_name = nombre
    dossier.portada[0] = Campo("Caso", nombre)
    dossier.portada.append(Campo("Question", None, Estado.NO_DEFINIDO))
    dossier.avisos_integridad = ["La corrida no registró el parser."]
    renderizado: list[str] = []
    document_class = dossier_pdf.SimpleDocTemplate

    class _CapturingDocument(document_class):
        def build(self, flowables, *args, **kwargs):
            def visit(flowable):
                if isinstance(flowable, str):
                    renderizado.append(flowable)
                elif isinstance(flowable, Paragraph):
                    renderizado.append(flowable.getPlainText())
                elif isinstance(flowable, Table):
                    for row in flowable._cellvalues:
                        for cell in row:
                            visit(cell)
                else:
                    for child in getattr(flowable, "_content", ()):
                        visit(child)

            for flowable in flowables:
                visit(flowable)
            return super().build(flowables, *args, **kwargs)

    monkeypatch.setattr(dossier_pdf, "SimpleDocTemplate", _CapturingDocument)
    locale_token = set_request_locale("en")
    try:
        pdf = dossier_pdf.render_dossier_pdf(dossier).getvalue()
    finally:
        reset_request_locale(locale_token)
    texto = "\n".join(renderizado)

    assert pdf.startswith(b"%PDF")
    assert "COMPUTATIONAL EVIDENCE DOSSIER" in texto
    assert "This run did not record the parser." in texto
    assert "NOT DEFINED" in texto
    assert "NO DEFINIDO" not in texto
    assert nombre in texto
    assert "La corrida no registró el parser." not in texto


def test_dict_de_evidencia_traduce_textos_declarados_y_preserva_identificadores():
    frase = "2 elegidos de 8 del catálogo: Aspirina"
    evidencia = {
        "cohort_name": frase,
        "molecules": [{"source_name": frase, "canonical_smiles": "CCO"}],
        "limits": [frase],
        "unknown": frase,
    }

    en = traducir_dossier(evidencia, "en")

    assert en["cohort_name"] == frase
    assert en["molecules"][0]["source_name"] == frase
    assert en["molecules"][0]["canonical_smiles"] == "CCO"
    assert en["limits"] == [traducir(frase, "en")]
    assert en["unknown"] == frase
    assert evidencia["limits"] == [frase]


def test_espanol_devuelve_el_objeto_original_sin_recorrerlo():
    dossier = build_case_dossier(**caso_completo())

    assert traducir_dossier(dossier, "es") is dossier


def test_reporte_de_especies_traduce_gramatica_y_conserva_conteos_e_identificadores():
    """Las filas de especies del sitio (las de la auditoría) pasan al inglés sin tocar conteos ni identificadores."""
    registros = Campo(
        "Registros HETATM retirados del ensamblaje",
        "aguas 127, metales 0, cofactores orgánicos 0, otras especies 45",
        Estado.REGISTRADO,
    )
    metales = Campo(
        "Metales y cofactores junto al sitio",
        "Retirados a 6 Å o menos del ligando: ZN A:301 (2.1 Å); más lejos: HEM B:701 (8.5 Å)",
        Estado.ABSTENCION,
        "El receptor que se entregaría no contiene especies que estaban en el sitio. "
        "Hay que decidir sobre ellas antes de cualquier cálculo posterior.",
        valor_es_clasificacion=True,
    )
    convertidas = Campo(
        "Especies conservadas como otro residuo (Å a la caja)", "MSE A:2 (0.0 Å) → MET", Estado.REGISTRADO,
    )
    en_registros, en_metales, en_convertidas = (traducir_dossier(c, "en") for c in (registros, metales, convertidas))

    assert en_registros.etiqueta == "HETATM records removed from the assembly"
    assert en_registros.valor == "waters 127, metals 0, organic cofactors 0, other species 45"
    assert en_metales.etiqueta == "Metals and cofactors near the site"
    assert "Removed within 6 Å of the ligand" in en_metales.valor and "farther away" in en_metales.valor
    assert "ZN A:301 (2.1 Å)" in en_metales.valor and "HEM B:701 (8.5 Å)" in en_metales.valor
    assert en_convertidas.etiqueta == "Species kept as another residue (Å to the box)"
    assert en_convertidas.valor == "MSE A:2 (0.0 Å) → MET"
    assert traducir_dossier(metales, "es") is metales

