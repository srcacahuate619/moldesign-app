"""Tres requisitos que el cálculo siguiente necesita y la auditoría no miraba (punto 3, 2026-10-10).

1. **Unión covalente.** Vina acopla el complejo no covalente. Si el ligando lleva una
   ojiva conocida, o el depósito une el ligando del cristal a la proteína, un FEP del
   inhibidor unido necesita el aducto o un protocolo covalente: pide revisión.
2. **Membrana.** El receptor que se entrega no lleva bicapa. La familia del catálogo y
   la palabra clave «MEMBRANE» fallan (la quinasa BTK, el ectodominio del receptor de
   TSH, el Cif de CFTR); la hidropatía de Kyte-Doolittle del fragmento cristalizado no:
   en el catálogo las solubles dan 0–2 segmentos y las de membrana 5–20.
3. **Cobertura del campo de fuerzas.** Lo que OpenFF/GAFF2 o un campo de proteína
   estándar no cubren (boro, metales, cofactores, fosforresiduos) hay que
   parametrizarlo aparte y declararlo.
"""

from __future__ import annotations

import pytest

from chem.ojivas_covalentes import OJIVAS, _patrones, ojivas
from core.i18n_plantillas import _PARECE_CASTELLANO
from services.dossier.contexto_estructural import (
    ContextoEstructural,
    _enlaces_covalentes,
    no_medido,
    segmentos_transmembrana,
)
from services.dossier.localization import traducir_dossier
from services.dossier.model import build_case_dossier
from services.dossier.preparacion import build_preparacion
from tests.test_diff_de_especies_de_la_corrida import _diff
from tests.test_preparacion_auditoria import _con_procedencia, _requisito

IBRUTINIB = "C=CC(=O)N1CCC[C@@H](C1)n1nc(-c2ccc(Oc3ccccc3)cc2)c2c(N)ncnc21"
BORTEZOMIB = "CC(C)C[C@H](NC(=O)[C@H](Cc1ccccc1)NC(=O)c1cnccn1)B(O)O"
ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"


def _auditar(smiles: str = ASPIRINA, contexto: ContextoEstructural | None = None) -> dict:
    caso = _con_procedencia(_diff(), smiles_acoplado=smiles)
    return build_preparacion(build_case_dossier(**caso), caso["eval_result"], caso["projection"], contexto)


def _medido(**campos) -> ContextoEstructural:
    return ContextoEstructural(medido=True, referencia="Pose top-1", **campos)


def _sin_espanol(auditoria: dict, clave: str) -> None:
    requisito = _requisito(traducir_dossier(auditoria, "en"), clave)
    for campo in ("etiqueta", "valor", "razon", "accion_recomendada"):
        texto = requisito.get(campo)
        if isinstance(texto, str):
            assert not _PARECE_CASTELLANO.search(texto), (campo, texto)


# ── 1 · Ojivas ───────────────────────────────────────────────────────


def test_todos_los_smarts_compilan():
    assert len(_patrones()) == len(OJIVAS)


@pytest.mark.parametrize("smiles, esperada", [
    (IBRUTINIB, "acrilamida (aceptor de Michael)"),
    ("CN(C)C/C=C/C(=O)Nc1cc2c(Nc3ccc(F)c(Cl)c3)ncnc2cc1O[C@H]1CCOC1", "acrilamida (aceptor de Michael)"),
    ("CC1(C)[C@@H]2[C@H]1N(C(=O)[C@@H](NC(=O)C(F)(F)F)C(C)(C)C)C[C@@H]2C(=O)N[C@@H](C[C@@H]1CCNC1=O)C#N",
     "α-aminonitrilo (ojiva reversible)"),
    (BORTEZOMIB, "ácido o éster borónico"),
    ("N#CC(=Cc1ccccc1)C(=O)NC", "acrilamida (aceptor de Michael)"),           # cianoacrilamida (ojiva reversible)
    ("C=C1CCNC1=O", "acrilamida (aceptor de Michael)"),                       # α-metileno-lactama
    ("CC1(C)S[C@@H]2[C@H](NC(=O)[C@H](N)c3ccc(O)cc3)C(=O)N2[C@H]1C(=O)O", "β-lactama"),
    ("C[C@@H]1O[C@@H]1P(=O)(O)O", "epóxido"),
])
def test_ojivas_de_farmacos_covalentes(smiles, esperada):
    assert esperada in ojivas(smiles)


@pytest.mark.parametrize("smiles", [
    ASPIRINA,
    "N#CC[C@H](C1CCCC1)n1cc(-c2ncnc3[nH]ccc23)cn1",                          # ruxolitinib
    "CCS(=O)(=O)N1CC(CC#N)(n2cc(-c3ncnc4[nH]ccc34)cn2)C1",                   # baricitinib
    "C[C@@H]1CCN(C(=O)CC#N)C[C@@H]1N(C)c1ncnc2[nH]ccc12",                    # tofacitinib
    "O=C(CC[C@@H](O)c1ccc(F)cc1)[C@H]1[C@@H](c2ccc(O)cc2)N(c2ccc(F)cc2)C1=O",  # ezetimiba
    "N#Cc1ccc(C(c2ccc(C#N)cc2)n2cncn2)cc1",                                  # letrozol
    "O=c1[nH]cc(F)c(=O)[nH]1",                                               # 5-fluorouracilo
    # Arilidenolactamas: C=C acíclico junto a una amida, pero el carbonilo y el Cα son de un mismo anillo
    # (inhibidores reversibles, no ojivas). ABS-TR-01-VALIDEZ: 3G0E salía con «Ojiva: acrilamida».
    "CCN(CC)CCNC(=O)c1c(C)[nH]c(/C=C2\\C(=O)Nc3ccc(F)cc32)c1C",              # sunitinib
    "Cc1cc(C)c(/C=C2\\C(=O)Nc3ccccc32)[nH]1",                                # semaxanib (SU5416)
    "C/C(=C\\c1ccccc1)/C=C1/SC(=S)N(CC(=O)O)C1=O",                           # epalrestat
])
def test_sin_falsos_positivos_en_farmacos_no_covalentes(smiles):
    assert ojivas(smiles) == []


def test_una_ojiva_pide_revision_y_no_bloquea():
    auditoria = _auditar(IBRUTINIB)
    covalente = _requisito(auditoria, "ligando.covalente")
    assert covalente["estado"] == "REVISAR"
    assert covalente["valor"] == "Ojiva: acrilamida (aceptor de Michael)."
    assert "aducto" in covalente["accion_recomendada"]
    assert "ligando.covalente" not in auditoria["bloqueantes"]
    _sin_espanol(auditoria, "ligando.covalente")


def test_el_enlace_del_deposito_tambien_se_declara():
    contexto = _medido(enlaces_covalentes=["1E8 A:601 C27–CYS A:481 SG (1.8 Å)"])
    covalente = _requisito(_auditar(ASPIRINA, contexto), "ligando.covalente")
    assert covalente["estado"] == "REVISAR"
    assert covalente["valor"] == "Ligando del cristal unido a la proteína: 1E8 A:601 C27–CYS A:481 SG (1.8 Å)."
    _sin_espanol(_auditar(IBRUTINIB, contexto), "ligando.covalente")


def test_sin_ojiva_queda_registrado_con_sus_limites():
    covalente = _requisito(_auditar(ASPIRINA, _medido(enlaces_covalentes=[])), "ligando.covalente")
    assert covalente["estado"] == "REGISTRADO"
    assert covalente["razon"].endswith("El depósito no une el ligando del cristal a la proteína.")
    sin_deposito = _requisito(_auditar(ASPIRINA), "ligando.covalente")
    assert sin_deposito["razon"].endswith("No se consultaron los enlaces del depósito.")
    _sin_espanol(_auditar(ASPIRINA, _medido(enlaces_covalentes=[])), "ligando.covalente")


def _link(lig: str, prot: str, distancia: str) -> str:
    """Un registro LINK con las columnas del formato PDB."""
    linea = list(" " * 80)
    linea[0:6] = "LINK  "
    for inicio, texto in ((12, lig), (42, prot)):
        nombre, residuo, cadena, numero = texto.split()
        linea[inicio:inicio + 4] = f"{nombre:<4}"
        linea[inicio + 5:inicio + 8] = f"{residuo:>3}"
        linea[inicio + 9] = cadena
        linea[inicio + 10:inicio + 14] = f"{numero:>4}"
    linea[73:78] = f"{distancia:>5}"
    return "".join(linea).rstrip()


def test_los_link_de_coordinacion_y_los_largos_no_son_covalentes():
    origen = "\n".join([
        _link("C27 1E8 A 601", "SG CYS A 481", "1.80"),
        _link("ZN ZN A 501", "ND1 HIS A 170", "2.07"),     # coordinación de un metal
        _link("O1 1E8 A 601", "OG SER A 200", "2.90"),     # puente de hidrógeno
        _link("O1 1E8 A 601", "O HOH A 900", "1.90"),      # agua, no proteína
    ])
    assert _enlaces_covalentes(origen, "1E8") == ["1E8 A:601 C27–CYS A:481 SG (1.8 Å)"]
    assert _enlaces_covalentes(origen, "XYZ") == []


def test_los_enlaces_peptidicos_de_un_inhibidor_no_lo_unen_a_la_proteina():
    """6LU7: el inhibidor N3 es una cadena propia (C); sólo su enlace a la Cys145 de A cuenta."""
    origen = "\n".join([
        _link("C20 PJE C 5", "SG CYS A 145", "1.77"),
        _link("N PJE C 5", "C LEU C 4", "1.38"),
    ])
    assert _enlaces_covalentes(origen, "PJE", {"A"}) == ["PJE C:5 C20–CYS A:145 SG (1.8 Å)"]


# ── 2 · Membrana ─────────────────────────────────────────────────────


def test_la_hidropatia_cuenta_las_helices_transmembrana():
    helice, lazo = ["LEU", "ILE", "VAL", "LEU", "PHE"] * 4, ["ASP", "LYS", "GLU", "ARG", "SER", "GLY"] * 3
    gpcr = (lazo + helice) * 7 + lazo
    assert segmentos_transmembrana(gpcr) == 7
    soluble = ["ALA", "LYS", "LEU", "GLU", "SER", "ASP", "VAL", "ARG"] * 40
    assert segmentos_transmembrana(soluble) == 0
    assert segmentos_transmembrana(["LEU"] * 10) == 0


def test_un_gpcr_pide_revision_y_dice_por_que():
    contexto = _medido(segmentos_tm={"A": 7}, clasificacion="MEMBRANE PROTEIN", lipidos=["CLR", "OLC"])
    auditoria = _auditar(ASPIRINA, contexto)
    membrana = _requisito(auditoria, "entorno.membrana")
    assert membrana["estado"] == "REVISAR"
    assert membrana["valor"] == ("7 segmentos transmembrana probables en la cadena A. El depósito la clasifica "
                                 "como «MEMBRANE PROTEIN». Lípidos o detergentes en el cristal: CLR, OLC.")
    assert "bicapa" in membrana["razon"]
    _sin_espanol(auditoria, "entorno.membrana")


def test_dos_segmentos_son_de_una_proteina_soluble():
    """CYP, polimerasas, topoisomerasas: una o dos hélices hidrofóbicas enterradas."""
    auditoria = _auditar(ASPIRINA, _medido(segmentos_tm={"A": 2}, clasificacion="OXIDOREDUCTASE", lipidos=["BOG"]))
    membrana = _requisito(auditoria, "entorno.membrana")
    assert membrana["estado"] == "REGISTRADO"
    assert membrana["valor"] == "Sin indicios de proteína de membrana multipaso"
    assert "barriles β" in membrana["razon"]
    _sin_espanol(auditoria, "entorno.membrana")


def test_sin_estructura_de_origen_no_se_mide():
    membrana = _requisito(_auditar(ASPIRINA, no_medido("sin origen")), "entorno.membrana")
    assert membrana["estado"] == "NO_EVALUADO"


# ── 3 · Campo de fuerzas ─────────────────────────────────────────────


def test_el_boro_queda_fuera_de_openff_y_gaff2():
    auditoria = _auditar(BORTEZOMIB)
    campo = _requisito(auditoria, "ligando.campo_de_fuerzas")
    assert campo["estado"] == "REVISAR"
    assert campo["razon"] == "Elementos sin parámetros en OpenFF 2 (Sage) ni en GAFF2: B."
    _sin_espanol(auditoria, "ligando.campo_de_fuerzas")


def test_un_ligando_organico_comun_queda_registrado():
    auditoria = _auditar("Clc1ccc(Br)cc1C(=O)NCCOP(=O)(O)O")
    campo = _requisito(auditoria, "ligando.campo_de_fuerzas")
    assert campo["estado"] == "REGISTRADO"
    assert campo["valor"] == "H, C, N, O, P, Cl, Br"
    _sin_espanol(auditoria, "ligando.campo_de_fuerzas")


def test_metales_cofactores_y_fosforresiduos_del_receptor():
    auditoria = _auditar(ASPIRINA, _medido(no_estandar={"HEM": 1, "SEP": 2, "ZN": 1}))
    campo = _requisito(auditoria, "receptor.campo_de_fuerzas")
    assert campo["estado"] == "REVISAR"
    assert campo["valor"] == (
        "No estándar: HEM ×1 (cofactor: necesita parámetros propios), SEP ×2 (fosforresiduo: necesita "
        "parámetros adicionales), ZN ×1 (metal: necesita parámetros de ion o un modelo enlazado).")
    _sin_espanol(auditoria, "receptor.campo_de_fuerzas")


def test_solo_aminoacidos_estandar_y_receptor_ilegible():
    assert _requisito(_auditar(ASPIRINA, _medido(no_estandar={})), "receptor.campo_de_fuerzas")["estado"] \
        == "REGISTRADO"
    # Medido por su lado: el PDBQT se lee aunque el crudo no se pueda comprobar.
    ilegible = no_medido("sin origen")
    assert _requisito(_auditar(ASPIRINA, ilegible), "receptor.campo_de_fuerzas")["estado"] == "NO_EVALUADO"


def test_un_radical_con_boro_sale_entero_en_ingles():
    auditoria = _auditar("[CH2]B(O)O")
    campo = _requisito(auditoria, "ligando.campo_de_fuerzas")
    assert campo["estado"] == "REVISAR"
    assert "radical" in campo["razon"]
    _sin_espanol(auditoria, "ligando.campo_de_fuerzas")
