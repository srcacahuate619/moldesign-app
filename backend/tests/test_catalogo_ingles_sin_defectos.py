"""El catálogo exacto sólo conserva entradas vivas y traducciones verificadas."""

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from auditar_catalogo_i18n import (  # noqa: E402
    BRITANICAS,
    ESPANOL,
    analizar_catalogo,
    cargar_catalogo,
    es_fragmento_obvio,
    fuentes_backend,
    problemas_entrada,
)
from core.i18n_plantillas import PLANTILLAS_ES_EN  # noqa: E402


def test_catalogo_sin_fragmentos_muertos_ni_defectos_conocidos():
    informe = analizar_catalogo(cargar_catalogo(), *fuentes_backend())

    assert informe["resumen"]["entradas"] > 0
    assert informe["resumen"]["con_problemas"] == 0
    assert informe["resumen"]["por_problema"] == {}


def test_plantillas_declaradas_pasan_los_mismos_controles_de_traduccion():
    assert len(PLANTILLAS_ES_EN) > 0
    for español, inglés in PLANTILLAS_ES_EN:
        assert problemas_entrada(español, inglés) == []


def test_guardia_detecta_fragmentos_y_no_confunde_comillas_balanceadas():
    assert es_fragmento_obvio("' no es un destino declarado.")
    assert es_fragmento_obvio(") y la pose (#")
    assert not es_fragmento_obvio("Token inválido: falta claim 'sub'")
    assert not es_fragmento_obvio("La pose conserva la geometría del sitio.")


def test_guardia_detecta_pares_sospechosos_y_terminologia_del_glosario():
    defectos = problemas_entrada(
        "Sin leer la fuente no se puede afirmar nada sobre lo que entra en la corrida.",
        "Without reading the source, nothing can be said about what enters the race.",
    )
    assert "sospechosa:corrida como race" in defectos
    assert "glosario:corrida como run" in defectos

    defectos = problemas_entrada("El destino cambió.", "The destiny changed.")
    assert "sospechosa:destino como destiny" in defectos


def test_guardia_permite_el_nombre_gpcr_y_sigue_detectando_docking_mal_traducido():
    assert problemas_entrada("Receptor Acoplado a Proteínas G", "G protein-coupled receptor") == []
    defects = problemas_entrada(
        "El ligando se acopla al receptor acoplado a proteínas G.",
        "The ligand is coupled to the G protein-coupled receptor.")
    assert "sospechosa:acoplar como couple/connect (en docking es dock)" in defects


#: Cada pareja (español, inglés) es una traducción REAL que sobrevivió a la auditoría de la Fase 1 y llegaba a la pantalla en inglés
#: (revisión del 2026-10-04): el control tiene que verlas, y no acusar lo que está bien dicho.
DEFECTOS_DE_LA_REVISION = [
    ("La cadena del receptor ya no coincide con la configuración.", "The receptor string no longer matches the settings.",
     "sospechosa:cadena como string (es chain)"),
    ("Es la cadena que se acoplará.", "It is the chain that will be coupled.", "sospechosa:acoplar como couple/connect (en docking es dock)"),
    ("Sin una molécula interpretable no hay nada que acoplar.", "Without an interpretable molecule there is nothing to couple.",
     "sospechosa:acoplar como couple/connect (en docking es dock)"),
    ("Mapa de contactos (Residuo-Ligando)", "Contact map (Residue-Living)", "sospechosa:ligando como living (es ligand)"),
    ("Pertenece al sitio de unión.", "It belongs to the junction site.", "sospechosa:sitio de unión como junction site (es binding site)"),
    ("La confianza describe la estructura, no la unión.", "Confidence describes the structure, not the union.",
     "sospechosa:unión como union (es binding)"),
    ("No se elige otra en su lugar.", "No one else is chosen instead.", "sospechosa:otra/otro como no one else (nadie más)"),
    ("preparer.filter_pdb_content sobre el PDB", "prepare.filter_pdb_content on the PDB",
     "identificador_alterado:preparer.filter_pdb_content"),
    ("Ver docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md.", "See docs/76_DECISION_TRANSFERENCY_ESMFOLD_A_LIGANDO_V1.md.",
     "identificador_alterado:docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md"),
]
BIEN_DICHAS = [
    ("La cadena del receptor ya no coincide.", "The receptor chain no longer matches."),
    ("Se acopla contra la cadena A.", "It is docked against chain A."),
    ("La corrida no registró la cadena de herramientas.", "This run did not record the toolchain."),  # cadena = toolchain, no «chain»
    ("<b>Estructura SMILES:</b>", "<b>SMILES string:</b>"),
    ("RMSD l.b.", "RMSD lower bound"),  # «l.b.» es una abreviatura que SÍ se traduce, no un identificador de código
    ("Ver docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md.", "See docs/76_DECISION_TRANSFERENCIA_ESMFOLD_A_LIGANDO_V1.md."),
]


def test_guardia_ve_los_defectos_que_sobrevivieron_a_la_fase_1():
    for español, inglés, esperado in DEFECTOS_DE_LA_REVISION:
        assert esperado in problemas_entrada(español, inglés), (español, inglés)


def test_guardia_no_acusa_lo_que_esta_bien_dicho():
    for español, inglés in BIEN_DICHAS:
        assert problemas_entrada(español, inglés) == [], (español, inglés)


def test_guardia_detecta_marcas_y_grafias_no_americanas():
    assert BRITANICAS.search("The Catalogue was labelled in the centre.")
    assert not BRITANICAS.search("The Catalog was labeled in the center.")
    assert ESPANOL.search("The receptor is ready, ¿correcto?")
    assert not ESPANOL.search("The receptor is ready.")


def test_guardia_exige_los_mismos_marcadores():
    assert "marcadores_distintos" not in problemas_entrada(
        "Se generaron {cantidad} poses.", "Generated {cantidad} poses."
    )
    assert "marcadores_distintos" in problemas_entrada(
        "Se generaron {cantidad} poses.", "Generated poses."
    )
