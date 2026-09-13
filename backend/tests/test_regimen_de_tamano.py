"""El tamaño de molécula lo definen criterios publicados, no este proyecto.

Auditoría del 2026-09-04, caso de uso «molécula pequeña». El producto tenía sus
propios umbrales, en `core/config.py` y presentados como ajustes configurables:

    mol_max_heavy_atoms      = 80     <- ERROR, detenía la corrida
    mol_max_molecular_weight = 800.0  <- aviso
    mol_min_molecular_weight = 100.0  <- aviso

Ninguno corresponde a un criterio de la literatura. El 800 no es frontera de
nada; el 80 —el único que bloqueaba— no aparece en ninguna regla de
drug-likeness. Eran números inventados decidiendo el alcance científico de la
aplicación, y presentados como si fueran parámetros que se afinan.

Ahora las fronteras son las de la química medicinal (`chem/regimenes.py`):

    Molécula pequeña   Rule of Five        MW ≤ 500        Lipinski et al. 1997
    Más allá de Ro5    bRo5                500 < MW ≤ 1000  Doak et al. 2014
    Fuera de alcance   —                   MW > 1000, o > 70 átomos (Ghose 1999)

Y el segundo defecto del mismo caso: la eficiencia de ligando se juzgaba con
umbrales fijos (0.25 / 0.45) sobre `|afinidad| / átomos_pesados`, de modo que el
veredicto lo decidía el tamaño antes de acoplar. Medido: benceno con Vina −4.5
recibía a la vez «Eficiencia de Ligando Excepcional» y «Afinidad débil … sirve
para descartar». Dos frases que se contradicen.
"""

from __future__ import annotations

import pytest
from rdkit import Chem
from rdkit.Chem import Descriptors

from chem.regimenes import (
    HA_MAXIMO,
    MW_BRO5,
    MW_FRAGMENTO,
    MW_RO5,
    Regimen,
    clasificar,
)

# (nombre, SMILES, régimen esperado). Fármacos reales, elegidos para caer a
# ambos lados de cada frontera publicada.
FARMACOS = [
    ("benceno", "c1ccccc1", Regimen.RO5),
    ("cafeína", "CN1C=NC2=C1C(=O)N(C)C(=O)N2C", Regimen.RO5),
    ("aspirina", "CC(=O)Oc1ccccc1C(=O)O", Regimen.RO5),
    ("acetazolamida", "CC(=O)Nc1nnc(S(N)(=O)=O)s1", Regimen.RO5),
    (
        "lisinopril",
        "CCCC[C@H](N[C@@H](C)C(=O)N1CCC[C@H]1C(O)=O)C(O)=O",
        Regimen.RO5,
    ),
    (
        "imatinib",
        "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1",
        Regimen.RO5,
    ),
    (
        "atorvastatina",
        "CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CC[C@@H](O)C[C@@H](O)CC(O)=O",
        Regimen.BRO5,
    ),
    (
        "ritonavir",
        "CC(C)c1nc(CN(C)C(=O)N[C@@H](CC(C)C)C(=O)N[C@@H](Cc2ccccc2)C[C@H](O)"
        "[C@H](Cc2ccccc2)NC(=O)OCc2cncs2)cs1",
        Regimen.BRO5,
    ),
    (
        "ciclosporina A",
        "CC[C@H]1NC(=O)[C@H]([C@H](O)[C@H](C)C/C=C/C)N(C)C(=O)[C@H](C(C)C)N(C)"
        "C(=O)[C@H](CC(C)C)N(C)C(=O)[C@H](CC(C)C)N(C)C(=O)[C@@H](C)NC(=O)[C@H]"
        "(C)NC(=O)[C@H](CC(C)C)N(C)C(=O)[C@@H](NC(=O)[C@H](CC(C)C)N(C)C(=O)CN"
        "(C)C1=O)C(C)C",
        Regimen.FUERA_DE_ALCANCE,
    ),
]


def _mw_ha(smiles: str) -> tuple[float, int]:
    mol = Chem.MolFromSmiles(smiles)
    assert mol is not None, f"SMILES de prueba inválido: {smiles}"
    return Descriptors.MolWt(mol), mol.GetNumHeavyAtoms()


# ── Las fronteras son las publicadas ─────────────────────────────────────

def test_las_fronteras_son_las_de_la_literatura():
    """Cambiar uno de estos números es cambiar de qué habla el producto."""
    assert MW_RO5 == 500.0, "Rule of Five (Lipinski et al. 1997)"
    assert MW_BRO5 == 1000.0, "Beyond Rule of Five (Doak et al. 2014)"
    assert MW_FRAGMENTO == 300.0, "Rule of Three (Congreve et al. 2003)"
    assert HA_MAXIMO == 70, "rango de átomos de Ghose et al. 1999 (20-70)"


def test_el_tope_de_atomos_coincide_con_ghose_ya_implementado():
    """No se introduce un número nuevo: es el que ya usaba GhoseRule."""
    from chem.properties import GhoseRule

    assert HA_MAXIMO == GhoseRule.ATOM_RANGE[1], (
        "el tope de átomos dejó de coincidir con el filtro de Ghose que el "
        "producto ya aplicaba: habría dos fronteras distintas para lo mismo"
    )


@pytest.mark.parametrize("nombre,smiles,esperado", FARMACOS, ids=[f[0] for f in FARMACOS])
def test_farmacos_reales_caen_en_el_regimen_que_les_toca(
    nombre: str, smiles: str, esperado: Regimen
):
    mw, ha = _mw_ha(smiles)
    obtenido = clasificar(mw, ha).regimen
    assert obtenido is esperado, (
        f"{nombre} ({mw:.0f} Da, {ha} átomos) salió «{obtenido.value}» y debía "
        f"ser «{esperado.value}»"
    )


def test_imatinib_es_ro5_aunque_los_atomos_digan_lo_contrario():
    """El caso que destapó el error de diseño de la primera versión.

    Imatinib pesa 493.6 Da —cumple la regla de los cinco— pero tiene 37 átomos
    pesados, uno más que los 36 que da la conversión desde 500 Da. La primera
    versión tomaba el régimen más restrictivo de los dos y lo mandaba a bRo5:
    una aproximación propia contradiciendo el criterio citado.
    """
    mw, ha = _mw_ha(
        "Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1"
    )
    assert mw <= MW_RO5 and ha > 36, "cambió el SMILES de prueba"

    resultado = clasificar(mw, ha)
    assert resultado.regimen is Regimen.RO5
    assert resultado.discrepancia, (
        "la discrepancia entre masa y átomos tiene que declararse, no "
        "resolverse en silencio"
    )


def test_ro3_es_una_marca_y_no_un_regimen():
    """La aspirina cumple Ro3 y sigue siendo una molécula pequeña."""
    mw, ha = _mw_ha("CC(=O)Oc1ccccc1C(=O)O")
    resultado = clasificar(mw, ha)
    assert resultado.regimen is Regimen.RO5, "un fármaco no es un fragmento"
    assert resultado.cumple_ro3 is True


def test_el_espacio_bro5_no_se_rechaza():
    """Doak et al. 2014 documentan fármacos orales reales ahí."""
    mw, ha = _mw_ha(
        "CC(C)c1nc(CN(C)C(=O)N[C@@H](CC(C)C)C(=O)N[C@@H](Cc2ccccc2)C[C@H](O)"
        "[C@H](Cc2ccccc2)NC(=O)OCc2cncs2)cs1"
    )
    resultado = clasificar(mw, ha)
    assert resultado.regimen is Regimen.BRO5
    assert resultado.bloquea is False, (
        "rechazar bRo5 sería afirmar que ese espacio no tiene fármacos orales, "
        "y los tiene (macrociclos, péptidos cíclicos, inhibidores de PPI)"
    )


def test_cada_regimen_cita_su_criterio():
    """Un umbral sin referencia es un número inventado con otro nombre."""
    for _, smiles, _ in FARMACOS:
        mw, ha = _mw_ha(smiles)
        resultado = clasificar(mw, ha)
        assert resultado.criterio.strip(), f"régimen sin criterio: {resultado.regimen}"
        assert any(
            autor in resultado.criterio
            for autor in ("Lipinski", "Doak", "Ghose", "Congreve")
        ), f"el criterio de «{resultado.etiqueta}» no cita a nadie"


# ── El validador usa el régimen, no umbrales propios ─────────────────────

def test_config_ya_no_decide_el_tamano_de_molecula():
    from core.config import Settings

    for ajuste in (
        "mol_max_heavy_atoms",
        "mol_max_molecular_weight",
        "mol_min_molecular_weight",
    ):
        assert ajuste not in Settings.model_fields, (
            f"«{ajuste}» volvió a `Settings`. El alcance científico de la "
            "aplicación no es un parámetro configurable: vive en "
            "chem/regimenes.py con su cita."
        )


def test_el_validador_bloquea_por_el_criterio_publicado():
    from chem.validator import validate_smiles

    _, smiles, _ = FARMACOS[-1]  # ciclosporina
    resultado = validate_smiles(smiles)
    assert resultado.is_valid is False
    assert resultado.regimen == "fuera_de_alcance"
    texto = " ".join(resultado.errors)
    assert "Ghose" in texto or "bRo5" in texto, (
        "el rechazo por tamaño no dice qué criterio lo motiva"
    )


def test_el_validador_deja_pasar_bro5_avisando():
    from chem.validator import validate_smiles

    resultado = validate_smiles(
        "CC(C)c1nc(CN(C)C(=O)N[C@@H](CC(C)C)C(=O)N[C@@H](Cc2ccccc2)C[C@H](O)"
        "[C@H](Cc2ccccc2)NC(=O)OCc2cncs2)cs1"
    )
    assert resultado.is_valid is True
    assert resultado.regimen == "bro5"
    assert any("Doak" in w for w in resultado.warnings), (
        "bRo5 pasa pero tiene que decir qué reglas dejan de aplicar y por qué"
    )


def test_el_regimen_viaja_en_el_resultado_de_validacion():
    """Para que la interfaz no tenga que recalcular fronteras por su cuenta."""
    from chem.validator import validate_smiles

    resultado = validate_smiles("CC(=O)Oc1ccccc1C(=O)O")
    assert resultado.regimen == "ro5"
    assert resultado.regimen_etiqueta
    assert "Lipinski" in (resultado.regimen_criterio or "")


# ── La eficiencia de ligando deja de estar decidida por el tamaño ────────

def test_el_veredicto_de_eficiencia_no_se_emite_donde_no_discrimina():
    """El defecto: a 6 átomos pesados el umbral de 0.45 lo cruza todo."""
    from utils.scientific import audit_scientific_quality

    avisos = audit_scientific_quality(
        affinity_kcal=-4.5, heavy_atom_count=6, log_p=1.9,
        docking_poses=[], hotspots=[], hotspots_hit=[],
        regimen="ro5", cumple_ro3=True,
    )
    texto = " ".join(avisos)
    assert "Excepcional" not in texto, (
        "vuelve la felicitación automática a los fragmentos: a 6 átomos, "
        "superar LE 0.45 sólo exige una afinidad mejor que -2.7 kcal/mol"
    )
    assert "no distingue" in texto, (
        "hay que decir POR QUÉ el umbral no sirve a este tamaño, no callarlo"
    )


def test_no_se_contradicen_los_dos_avisos_en_un_fragmento():
    """Benceno recibía «excepcional» y «sirve para descartar» a la vez."""
    from utils.scientific import audit_scientific_quality

    avisos = audit_scientific_quality(
        affinity_kcal=-4.5, heavy_atom_count=6, log_p=1.9,
        docking_poses=[], hotspots=[], hotspots_hit=[],
        regimen="ro5", cumple_ro3=True,
    )
    texto = " ".join(avisos)
    assert "sirve para descartar" not in texto, (
        "por debajo de 300 Da una afinidad de -4.5 es lo esperado en cribado "
        "por fragmentos, no un motivo para descartar"
    )
    assert "Rule of Three" in texto


def test_en_bro5_se_informa_la_eficiencia_sin_veredicto():
    from utils.scientific import audit_scientific_quality

    avisos = audit_scientific_quality(
        affinity_kcal=-8.0, heavy_atom_count=51, log_p=4.2,
        docking_poses=[], hotspots=[], hotspots_hit=[],
        regimen="bro5", cumple_ro3=False,
    )
    texto = " ".join(avisos)
    assert "sin veredicto" in texto
    assert "demasiado grande" not in texto, (
        "los umbrales de LE no están calibrados en bRo5: aplicarlos ahí dice "
        "«demasiado grande» a casi cualquier macrociclo"
    )


def test_dentro_de_ro5_los_umbrales_convencionales_siguen_aplicando():
    """La corrección no puede haber apagado el criterio donde sí vale."""
    from utils.scientific import audit_scientific_quality

    avisos = audit_scientific_quality(
        affinity_kcal=-5.0, heavy_atom_count=30, log_p=2.0,
        docking_poses=[], hotspots=[], hotspots_hit=[],
        regimen="ro5", cumple_ro3=False,
    )
    texto = " ".join(avisos)
    assert "Baja eficiencia de ligando" in texto, (
        "LE = 0.17 en espacio Ro5 sigue siendo baja y hay que decirlo"
    )


def test_los_dos_ejecutores_pasan_el_regimen_a_la_auditoria():
    """Si uno no lo pasa, sus umbrales vuelven a aplicarse fuera de rango."""
    from pathlib import Path

    backend = Path(__file__).resolve().parents[1]
    for ruta in (
        backend / "services" / "docking" / "queue_handler.py",
        backend / "services" / "pipeline" / "runner.py",
    ):
        fuente = ruta.read_text(encoding="utf-8")
        assert "regimen=_reg.regimen.value" in fuente, (
            f"{ruta.name} llama a la auditoría sin el régimen"
        )
