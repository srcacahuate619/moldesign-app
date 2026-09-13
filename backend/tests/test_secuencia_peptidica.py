"""
El motor peptídico de ESMFold nunca extrajo una secuencia.

# Tres defectos superpuestos, más uno de fondo

`ESMFoldFastPredictor._smiles_to_aa_sequence` es un `@staticmethod` que hacía:

    aa_patterns = {aa: Chem.MolFromSmarts(s) for aa, s in _AA_SMARTS.items()}

`_AA_SMARTS` estaba definido como atributo de clase, y un nombre suelto dentro
de un método estático no resuelve contra el cuerpo de la clase. La línea
levantaba `NameError` **en toda llamada, para todo péptido**. El motor no
plegó nunca: cada corrida peptídica caía al respaldo de Vina.

Arreglar sólo el `NameError` habría sido peor, porque varios de los veinte
patrones estaban mal —`"N": "[NX3][CX3](=[OX1])"` casa con cualquier amida,
incluido el propio esqueleto— y el resultado no habría sido un error sino una
secuencia inventada, plegada y acoplada.

Tercero: los residuos se recorrían en el orden de `GetSubstructMatches`, que
sigue los índices atómicos. Con un SMILES escrito de N a C coincide por
casualidad; con otro, la secuencia sale permutada, que es otro péptido.

Y el de fondo: **nada miraba el estereocentro del Cα**. Un D-péptido y su
enantiómero L dan la misma secuencia de letras, así que ESMFold —que sólo
conoce L— habría plegado el L y el resultado se habría presentado como la
molécula del usuario. Un D-péptido se diseña justamente para no ser el L.
"""

import sys
from pathlib import Path

import pytest

SIDECAR = Path(__file__).resolve().parents[1] / "sidecars" / "esmfold"
if str(SIDECAR) not in sys.path:
    sys.path.insert(0, str(SIDECAR))

from secuencia import (  # noqa: E402
    AMINOACIDOS_L,
    SecuenciaNoDeterminable,
    _POR_HUELLA,
    extraer_secuencia,
)

ENCEFALINA = (
    "N[C@@H](Cc1ccc(O)cc1)C(=O)NCC(=O)NCC(=O)N[C@@H](Cc1ccccc1)C(=O)"
    "N[C@@H](CC(C)C)C(=O)O"
)


# ── La tabla de referencia ─────────────────────────────────────────────────

def test_los_veinte_estandar_son_distinguibles():
    """La huella tiene que separar los veinte, no diecinueve.

    Costó dos intentos: sin el Cα, leucina e isoleucina dan el mismo isobutano;
    con el Cα como carbono normal, el mismo isopentano. Sólo marcando el punto
    de anclaje con un átomo ficticio quedan separadas.
    """
    assert len(_POR_HUELLA) == len(AMINOACIDOS_L) == 20


def test_leucina_e_isoleucina_no_colisionan():
    assert _POR_HUELLA["*CC(C)C"] == "L"
    assert _POR_HUELLA["*C(C)CC"] == "I"


# ── Lectura de secuencia ───────────────────────────────────────────────────

def test_lee_un_pentapeptido_real():
    lectura = extraer_secuencia(ENCEFALINA)
    assert lectura.secuencia == "YGGFL"


def test_el_orden_importa_y_se_respeta():
    """Una permutación es otro péptido."""
    leu_ile = "CC(C)C[C@H](N)C(=O)N[C@@H]([C@@H](C)CC)C(=O)O"
    ile_leu = "CC[C@H](C)[C@H](N)C(=O)N[C@@H](CC(C)C)C(=O)O"
    assert extraer_secuencia(leu_ile).secuencia == "LI"
    assert extraer_secuencia(ile_leu).secuencia == "IL"


def test_la_prolina_no_confunde_su_anillo_con_una_ramificacion():
    """La cadena lateral de la prolina se cierra sobre el N del esqueleto."""
    assert extraer_secuencia("OC(=O)CNC(=O)[C@@H]1CCCN1").secuencia == "PG"


def test_los_aromaticos_se_reconocen():
    trp_his = "N[C@@H](Cc1c[nH]c2ccccc12)C(=O)N[C@@H](Cc1c[nH]cn1)C(=O)O"
    assert extraer_secuencia(trp_his).secuencia == "WH"


# ── La quiralidad ──────────────────────────────────────────────────────────

def test_l_y_d_dan_la_misma_secuencia_y_distinta_serie():
    """Ese es exactamente el motivo por el que hacía falta mirar el Cα."""
    ele = extraer_secuencia("C[C@H](N)C(=O)N[C@@H](C)C(=O)O")
    de = extraer_secuencia("C[C@@H](N)C(=O)N[C@H](C)C(=O)O")

    assert ele.secuencia == de.secuencia == "AA"
    assert [r.serie for r in ele.residuos] == ["L", "L"]
    assert [r.serie for r in de.residuos] == ["D", "D"]
    assert de.tiene_d and not ele.tiene_d


def test_una_cadena_mixta_se_detecta():
    mixto = extraer_secuencia("C[C@H](N)C(=O)N[C@H](C)C(=O)O")
    assert [r.serie for r in mixto.residuos] == ["L", "D"]
    assert mixto.tiene_d


def test_la_glicina_no_tiene_serie():
    lectura = extraer_secuencia("NCC(=O)NCC(=O)O")
    assert lectura.secuencia == "GG"
    assert all(r.serie is None for r in lectura.residuos)
    assert lectura.series_sin_declarar == 0, "la glicina no cuenta como no declarada"


def test_la_cisteina_invierte_el_codigo_cip_pero_no_la_serie():
    """L-Cys es (R) por la prioridad del azufre; sigue siendo L."""
    l_cys_gly = "N[C@@H](CS)C(=O)NCC(=O)O"
    lectura = extraer_secuencia(l_cys_gly)
    assert lectura.secuencia == "CG"
    assert lectura.residuos[0].serie == "L"


def test_un_smiles_sin_estereoquimica_no_se_inventa_serie():
    lectura = extraer_secuencia("CC(N)C(=O)NC(C)C(=O)O")
    assert lectura.secuencia == "AA"
    assert all(r.serie is None for r in lectura.residuos)
    assert lectura.series_sin_declarar == 2


# ── Abstención ─────────────────────────────────────────────────────────────

def test_lo_que_no_es_un_peptido_se_rechaza():
    with pytest.raises(SecuenciaNoDeterminable):
        extraer_secuencia("CCO")


def test_un_smiles_invalido_se_rechaza():
    with pytest.raises(SecuenciaNoDeterminable):
        extraer_secuencia("esto((no es")


def test_un_residuo_no_estandar_se_marca_pero_no_se_adivina():
    """Ornitina: no es de los veinte. Sale como X, no como lisina."""
    orn_gly = "NCCC[C@H](N)C(=O)NCC(=O)O"
    lectura = extraer_secuencia(orn_gly)
    assert "X" in lectura.secuencia
    assert lectura.tiene_no_estandar


# ── El predictor, que es quien lo usaba mal ────────────────────────────────

def _predictor():
    import predictor

    return predictor.ESMFoldFastPredictor


def test_la_tabla_muerta_ya_no_existe():
    """Una tabla equivocada que no llama nadie es una trampa."""
    assert not hasattr(_predictor(), "_AA_SMARTS")


def test_el_extractor_del_predictor_ya_no_levanta_nameerror():
    assert _predictor()._smiles_to_aa_sequence(ENCEFALINA) == "YGGFL"


def test_un_d_peptido_se_rechaza_en_vez_de_plegar_el_enantiomero():
    """ESMFold sólo conoce L. Plegar el L sería devolver otra molécula."""
    with pytest.raises(ValueError) as excinfo:
        _predictor()._smiles_to_aa_sequence("C[C@@H](N)C(=O)N[C@H](C)C(=O)O")
    mensaje = str(excinfo.value)
    assert "aminoácidos D" in mensaje
    # Y dice DÓNDE están, para poder corregirlos.
    assert "1A" in mensaje and "2A" in mensaje


def test_un_residuo_no_estandar_se_rechaza_con_su_posicion():
    with pytest.raises(ValueError) as excinfo:
        _predictor()._smiles_to_aa_sequence("NCCC[C@H](N)C(=O)NCC(=O)O")
    assert "veinte estándar" in str(excinfo.value)


# ── El otro sidecar, que tenía el mismo fallo desplazado ───────────────────
#
# `esmfold-pro` (RFdiffusion, puerto 8300) llevaba su propia copia de la tabla
# `_AA_SMARTS`, con los mismos patrones equivocados. Y su propio `NameError`,
# una función más adentro: `_match_aa_by_smarts` y `_identify_single_aa` usaban
# `Chem` como nombre de módulo, pero el único `import rdkit.Chem as Chem` del
# archivo estaba dentro de `_smiles_to_aa_sequence`. Medido antes del arreglo:
#
#     >>> RFdiffusionPredictor._smiles_to_aa_sequence("C[C@H](N)C(=O)NCC(=O)O")
#     NameError: name 'Chem' is not defined
#
# Es decir, el motor de RFdiffusion tampoco leyó una secuencia jamás.

RAIZ = Path(__file__).resolve().parents[2]
SIDECAR_PRO = RAIZ / "esmfold-pro"


def test_las_dos_copias_de_secuencia_son_la_misma():
    """Los sidecars son procesos independientes; la lectura no puede divergir.

    Cada uno tiene su `requirements.txt` y su `logger.py`, así que `secuencia.py`
    se copia en vez de importarse. Lo que no puede pasar es que se separen: un
    péptido leído distinto por cada motor es dos moléculas distintas.
    """
    original = (SIDECAR / "secuencia.py").read_bytes()
    copia = (SIDECAR_PRO / "secuencia.py").read_bytes()
    assert copia == original, (
        "esmfold-pro/secuencia.py se ha separado de backend/sidecars/esmfold/"
        "secuencia.py. Copia la buena sobre la otra."
    )


def _predictor_pro():
    """Carga `esmfold-pro/predictor.py` con su `logger` propio en su sitio."""
    import importlib.util
    import types

    if "logger" not in sys.modules or not hasattr(sys.modules["logger"], "get_logger"):
        falso = types.ModuleType("logger")
        falso.get_logger = lambda _n: types.SimpleNamespace(
            info=lambda *a, **k: None, warning=lambda *a, **k: None,
            error=lambda *a, **k: None, debug=lambda *a, **k: None,
            exception=lambda *a, **k: None,
        )
        sys.modules.setdefault("logger", falso)

    if str(SIDECAR_PRO) not in sys.path:
        sys.path.insert(0, str(SIDECAR_PRO))
    if "predictor_pro" in sys.modules:
        return sys.modules["predictor_pro"].RFdiffusionPredictor

    ruta = SIDECAR_PRO / "predictor.py"
    spec = importlib.util.spec_from_file_location("predictor_pro", ruta)
    modulo = importlib.util.module_from_spec(spec)
    # Registrar ANTES de ejecutar: los `@dataclass` del módulo resuelven sus
    # anotaciones vía `sys.modules[cls.__module__]`, y sin esta línea encuentran
    # `None`.
    sys.modules["predictor_pro"] = modulo
    spec.loader.exec_module(modulo)
    return modulo.RFdiffusionPredictor


def test_el_predictor_pro_ya_no_lleva_su_tabla_a_mano():
    assert not hasattr(_predictor_pro(), "_AA_SMARTS")
    # Y los tres lectores que la usaban se fueron con ella.
    for muerto in ("_expand_residue", "_match_aa_by_smarts", "_identify_single_aa"):
        assert not hasattr(_predictor_pro(), muerto), muerto


def test_el_predictor_pro_extrae_la_secuencia():
    assert _predictor_pro()._smiles_to_aa_sequence(ENCEFALINA) == "YGGFL"


def test_el_predictor_pro_rechaza_un_d_peptido():
    """RFdiffusion difunde backbones L; el D es otra molécula."""
    with pytest.raises(ValueError) as excinfo:
        _predictor_pro()._smiles_to_aa_sequence("C[C@@H](N)C(=O)N[C@H](C)C(=O)O")
    assert "aminoácidos D" in str(excinfo.value)


def test_los_dos_sidecars_leen_igual_el_mismo_peptido():
    """La prueba de que la copia sirve para algo."""
    from secuencia import extraer_secuencia as extraer_esmfold

    for smiles in (ENCEFALINA, "C[C@H](N)C(=O)NCC(=O)N[C@@H](CO)C(=O)O"):
        assert (
            _predictor_pro()._smiles_to_aa_sequence(smiles)
            == extraer_esmfold(smiles).secuencia
        )
