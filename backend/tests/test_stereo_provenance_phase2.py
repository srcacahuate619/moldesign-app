"""La especie 3D realmente acoplada y sus ambigüedades quedan auditables."""

from types import SimpleNamespace

from rdkit import Chem

from chem.conformer import _construir_conformero, sdf_string_to_mol
from chem.validator import validate_smiles
from services.docking.ligand_state_warnings import avisos_estado_ligando
from services.dossier.model import Estado, _campo_de_estado_quimico


IBUPROFENO_PLANO = "CC(C)Cc1ccc(C(C)C(=O)O)cc1"
TAMOXIFENO_SIN_EZ = "CCC(=C(c1ccccc1)c1ccc(OCCN(C)C)cc1)c1ccccc1"


def test_un_doble_estereogenico_sin_ez_tiene_aviso_de_entrada():
    validacion = validate_smiles(TAMOXIFENO_SIN_EZ)
    assert validacion.is_valid
    assert any("E/Z" in warning for warning in validacion.warnings)


def test_el_enantiomero_embebido_coincide_con_el_sdf_y_se_declara():
    corrida = _construir_conformero(IBUPROFENO_PLANO)
    estado = corrida["estado_del_ligando"]
    estereo = estado["estereoquimica"]
    assert estereo["centros_sin_asignar"] == 1
    assert estereo["dobles_sin_asignar"] == 0
    assert "@" in estereo["smiles_3d_efectivo"]
    assert estado["conformero"]["semilla"] == 42
    assert estado["conformero"]["campo_fuerza_final"] in {"MMFF94", "UFF", "sin_optimizacion"}

    mol = sdf_string_to_mol(corrida["sdf_content"])
    assert mol is not None
    Chem.AssignStereochemistryFrom3D(mol)
    assert Chem.MolToSmiles(Chem.RemoveHs(mol), isomericSmiles=True) == estereo["smiles_3d_efectivo"]

    avisos = avisos_estado_ligando(estado)
    assert any(a["codigo"] == "ESTEREOQUIMICA_NO_DECLARADA" for a in avisos)
    campo = _campo_de_estado_quimico(SimpleNamespace(ligand_state=estado))
    assert campo.estado == Estado.REVISAR
    assert campo.valor == estereo["smiles_3d_efectivo"]


def test_el_doble_sin_ez_declara_el_isomero_3d_y_que_no_se_evaluaron_otros():
    estado = _construir_conformero(TAMOXIFENO_SIN_EZ)["estado_del_ligando"]
    estereo = estado["estereoquimica"]
    assert estereo["dobles_sin_asignar"] == 1
    assert estereo["dobles_sin_clasificar_3d"] == 0
    assert "/" in estereo["smiles_3d_efectivo"] or "\\" in estereo["smiles_3d_efectivo"]
    assert any(a["codigo"] == "ESTEREOQUIMICA_NO_DECLARADA" for a in avisos_estado_ligando(estado))
