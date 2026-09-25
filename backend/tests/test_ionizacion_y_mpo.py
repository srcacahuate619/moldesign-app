"""
LogD por Henderson-Hasselbalch, y el sexto término del MPO de Pfizer.

# Lo que había

    # 6. logD (approximated as logP - 0.5 for neutral compounds)
    logd_est = logp - 0.5

Un desplazamiento constante, con el propio comentario admitiendo que sólo vale
para compuestos neutros y aplicándose a todos. En fármacos del SNC eso es al
revés del caso típico: la mayoría llevan una amina básica que a pH 7.4 está
protonada en más del 95 % y pierde entre 1.5 y 2.5 unidades de lipofilia.

Y el sexto término del MPO de Pfizer es el **pKa del centro más básico**; aquí
estaba el número de aceptores de enlace de hidrógeno ocupando su sitio.

Medido contra LogD7.4 experimental de literatura:

                  exp     −0.5 constante     Henderson-Hasselbalch
    aspirina     −2.0         +0.81                 −1.89
    fluoxetina   +1.9         +3.94                 +2.03
    levodopa     −2.4         −0.45                 −3.21

El error pasa de 2-2.8 unidades logarítmicas a menos de 0.9.
"""

import pytest

from chem.ionizacion import (
    PH_FISIOLOGICO,
    analizar_ionizacion,
    desirabilidad_pka,
)

# (nombre, SMILES, LogD7.4 experimental de referencia)
FARMACOS = [
    ("aspirina", "CC(=O)Oc1ccccc1C(=O)O", -2.0),
    ("fluoxetina", "CNCCC(Oc1ccc(cc1)C(F)(F)F)c1ccccc1", 1.9),
    ("difenhidramina", "CN(C)CCOC(c1ccccc1)c1ccccc1", 1.3),
    ("cafeina", "Cn1cnc2c1c(=O)n(C)c(=O)n2C", -0.1),
    ("ibuprofeno", "CC(C)Cc1ccc(cc1)C(C)C(O)=O", 0.6),
]


def _logp(smiles: str) -> float:
    from rdkit import Chem
    from rdkit.Chem import Crippen

    return Crippen.MolLogP(Chem.MolFromSmiles(smiles))


@pytest.mark.parametrize(("nombre", "smiles", "experimental"), FARMACOS)
def test_el_logd_estimado_se_acerca_al_experimental(nombre, smiles, experimental):
    estado = analizar_ionizacion(smiles, _logp(smiles))
    assert estado.logd is not None
    assert abs(estado.logd - experimental) < 1.0, (
        f"{nombre}: LogD estimado {estado.logd} frente a {experimental} experimental"
    )


@pytest.mark.parametrize(("nombre", "smiles", "experimental"), FARMACOS)
def test_es_mejor_que_el_desplazamiento_constante(nombre, smiles, experimental):
    """La comparación directa con la fórmula que se retiró."""
    logp = _logp(smiles)
    nuevo = abs(analizar_ionizacion(smiles, logp).logd - experimental)
    viejo = abs((logp - 0.5) - experimental)
    assert nuevo <= viejo + 1e-9, f"{nombre}: el método nuevo no mejora al constante"


def test_una_base_pierde_lipofilia_y_un_neutro_no():
    base = analizar_ionizacion("CN(C)CCOC(c1ccccc1)c1ccccc1", 3.35)
    neutro = analizar_ionizacion("Cn1cnc2c1c(=O)n(C)c(=O)n2C", -1.03)
    assert base.logd < 3.35 - 2.0, "una amina de pKa ~9.8 pierde más de 2 unidades"
    assert neutro.logd == pytest.approx(-1.03), "sin centro ionizable, LogD = LogP"


def test_la_carga_neta_es_la_de_la_especie_dominante():
    assert analizar_ionizacion("CC(=O)Oc1ccccc1C(=O)O", 1.31).carga_neta == -1
    assert analizar_ionizacion("CN(C)CCOC(c1ccccc1)c1ccccc1", 3.35).carga_neta == 1
    assert analizar_ionizacion("Cn1cnc2c1c(=O)n(C)c(=O)n2C", -1.03).carga_neta == 0


def test_el_zwitterion_usa_un_solo_denominador():
    """Sumar dos logaritmos multiplicaba los denominadores.

    Con levodopa la forma multiplicativa daba LogD −5.6 frente al −2.4
    experimental; con las microespecies en un único denominador queda cerca de
    −3.2, que es lo que esta aproximación puede sostener.
    """
    import math

    levodopa = "N[C@@H](Cc1ccc(O)c(O)c1)C(O)=O"
    logp = _logp(levodopa)
    estado = analizar_ionizacion(levodopa, logp)

    a = 10 ** (9.8 - PH_FISIOLOGICO)
    b = 10 ** (PH_FISIOLOGICO - 4.2)
    multiplicativa = logp - (math.log10(1 + a) + math.log10(1 + b))

    assert estado.logd > multiplicativa + 1.0
    assert abs(estado.logd - (-2.4)) < 1.2


def test_se_declaran_los_centros_reconocidos():
    """El pKa es representativo de la clase, no calculado: hay que poder verlo."""
    estado = analizar_ionizacion("CN(C)CCOC(c1ccccc1)c1ccccc1", 3.35)
    nombres = {c[0] for c in estado.centros}
    assert "amina_alifatica" in nombres
    assert estado.pka_mas_basico == 9.8


def test_losartan_tetrazol_1h_y_2h_conservan_el_centro_acido():
    from rdkit import Chem
    from rdkit.Chem.MolStandardize import rdMolStandardize
    from chem.ionizacion import cargas_esperadas_a_ph

    entrada = "CCCCc1nc(Cl)c(CO)n1Cc1ccc(-c2ccccc2-c2nnn[nH]2)cc1"
    parametros = rdMolStandardize.CleanupParameters()
    parametros.tautomerRemoveSp3Stereo = False
    canonico = Chem.MolToSmiles(
        rdMolStandardize.TautomerEnumerator(parametros).Canonicalize(
            Chem.MolFromSmiles(entrada)
        )
    )
    assert entrada != canonico
    for smiles in (entrada, canonico):
        assert cargas_esperadas_a_ph(smiles) == (0, 1)
        estado = analizar_ionizacion(smiles, 3.0)
        assert [centro[0] for centro in estado.centros] == ["tetrazol"]
        assert estado.centros_completos
        assert estado.carga_neta == -1


def test_una_amida_no_se_confunde_con_una_amina_basica():
    """El nitrógeno amídico no se protona a pH 7.4."""
    estado = analizar_ionizacion("CC(=O)Nc1ccc(O)cc1", 1.0)  # paracetamol
    assert estado.carga_neta == 0
    assert estado.pka_mas_basico is None


def test_un_smiles_ilegible_no_inventa_ionizacion():
    estado = analizar_ionizacion("esto((no es", 2.0)
    assert estado.logd == 2.0
    assert estado.centros == []


# ── El término de pKa del MPO ──────────────────────────────────────────────

@pytest.mark.parametrize(
    ("pka", "esperado"),
    [(None, 1.0), (7.0, 1.0), (8.0, 1.0), (9.0, 0.5), (10.0, 0.0), (12.0, 0.0)],
)
def test_la_desirabilidad_de_pka_penaliza_las_bases_fuertes(pka, esperado):
    """Wager et al.: un pKa alto significa cargado en sangre, y cargado no difunde."""
    assert desirabilidad_pka(pka) == pytest.approx(esperado)


def test_el_mpo_usa_pka_y_logd_cuando_recibe_el_smiles():
    from chem.blood_viability import _calculate_cns_mpo

    # Base fuerte: el término de pKa la penaliza y el LogD real baja.
    con_smiles = _calculate_cns_mpo(
        mw=255.4, logp=3.35, tpsa=12.5, hbd=0, hba=2,
        smiles="CN(C)CCOC(c1ccccc1)c1ccccc1",
    )
    sin_smiles = _calculate_cns_mpo(mw=255.4, logp=3.35, tpsa=12.5, hbd=0, hba=2)
    assert con_smiles < sin_smiles, (
        "una amina de pKa 9.8 debe puntuar peor cuando se tiene en cuenta que "
        "en sangre está protonada"
    )


@pytest.mark.parametrize(
    ("nombre", "smiles", "esperadas", "carga"),
    [
        ("metformina", "CN(C)C(=N)N=C(N)N", (1, 0), 1),
        ("cimetidina", "CN=C(NC#N)NCCSCc1[nH]cnc1C", (0, 0), 0),
        ("celecoxib", "Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1", (0, 0), 0),
        ("glucosa_6_fosfato", "O=P(O)(O)O[C@H]1O[C@H](CO)[C@@H](O)[C@H](O)[C@H]1O", (0, 2), -2),
    ],
)
def test_lig003_reconoce_carga_fisiologica(nombre, smiles, esperadas, carga):
    from chem.ionizacion import cargas_esperadas_a_ph
    assert cargas_esperadas_a_ph(smiles) == esperadas, nombre
    assert analizar_ionizacion(smiles, 1.0).carga_neta == carga, nombre


def test_lig003_microestado_real_cimetidina_celecoxib_fosfato():
    from dimorphite_dl import protonate_smiles
    from chem.ionizacion import elegir_microestado
    from rdkit import Chem

    casos = [
        ("cimetidina", "CN=C(NC#N)NCCSCc1[nH]cnc1C", 0),
        ("celecoxib", "Cc1ccc(-c2cc(C(F)(F)F)nn2-c2ccc(S(N)(=O)=O)cc2)cc1", 0),
        ("glucosa_6_fosfato", "O=P(O)(O)O[C@H]1O[C@H](CO)[C@@H](O)[C@H](O)[C@H]1O", -2),
    ]
    for nombre, smiles, carga in casos:
        alternativas = protonate_smiles(smiles, ph_min=7.4, ph_max=7.4)
        elegido, criterio = elegir_microestado(smiles, alternativas)
        assert Chem.GetFormalCharge(Chem.MolFromSmiles(elegido)) == carga, nombre
        assert criterio["quimica_resuelta"] is (nombre != "cimetidina")


def test_lig003_imida_sin_pka_deja_revision_explicita():
    from dimorphite_dl import protonate_smiles
    from chem.ionizacion import elegir_microestado
    from rdkit import Chem

    talidomida = "O=C1CCC(N2C(=O)c3ccccc3C2=O)C(=O)N1"
    elegido, criterio = elegir_microestado(
        talidomida, protonate_smiles(talidomida, ph_min=7.4, ph_max=7.4)
    )
    assert Chem.GetFormalCharge(Chem.MolFromSmiles(elegido)) == 0
    assert criterio["criterio"] == "grupo_reconocido_sin_pka"
    assert criterio["quimica_resuelta"] is False


def test_lig003_incertidumbre_aparece_como_revision_en_dossier_y_aviso():
    from types import SimpleNamespace
    from dimorphite_dl import protonate_smiles
    from chem.ionizacion import elegir_microestado
    from services.docking.ligand_state_warnings import avisos_estado_ligando
    from services.dossier.model import Estado, _campos_de_protocolo_y_abstencion

    smiles = "CN(C)C(=N)N=C(N)N"
    _, seleccion = elegir_microestado(
        smiles, protonate_smiles(smiles, ph_min=7.4, ph_max=7.4)
    )
    assert seleccion["revision_biguanida"] is True
    assert seleccion["quimica_resuelta"] is False
    estado = {"protonacion": {"aplicada": True, "ph": 7.4, "alternativas": 3, "seleccion": seleccion}}
    assert any(a["codigo"] == "BIGUANIDA_ESTADO_EN_REVISION" for a in avisos_estado_ligando(estado))
    campos = _campos_de_protocolo_y_abstencion(
        SimpleNamespace(ligand_state=estado), {"top_pose_affinity": -6.0}
    )
    especie = next(c for c in campos if c.etiqueta == "Especie acoplada")
    assert especie.estado == Estado.REVISAR
    assert "hipótesis" in especie.razon


def test_fosfato_no_cuenta_dos_veces_la_carga_escrita_en_la_entrada():
    for smiles in ("COP(=O)(O)O", "COP(=O)([O-])O", "COP(=O)([O-])[O-]"):
        estado = analizar_ionizacion(smiles, 1.0)
        assert estado.carga_neta == -2


def test_cns_mpo_se_abstiene_si_pka_clase_esta_en_revision(monkeypatch):
    from chem import blood_viability
    from chem.properties import calculate_properties

    monkeypatch.setattr(blood_viability, "predict_admet_ai", lambda _s: {
        "Solubility": -3.0, "HIA": None, "BBB_prob": None,
    })
    monkeypatch.setattr(blood_viability, "predict_tabpfn_custom_toxicity", lambda _p: [])
    metformina = "CN(C)C(=N)N=C(N)N"
    aspirina = "CC(=O)Oc1ccccc1C(=O)O"
    props_met = calculate_properties(metformina, run_admet_ai=False)
    props_asp = calculate_properties(aspirina, run_admet_ai=False)
    assert blood_viability.calculate_blood_viability(metformina, props_met).blood_cns_mpo is None
    assert blood_viability.calculate_blood_viability(aspirina, props_asp).blood_cns_mpo is not None
