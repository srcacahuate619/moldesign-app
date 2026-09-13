"""
El diccionario de moléculas conocidas no puede entregar la estructura equivocada.

# Por qué esta prueba existe

`known_molecules.py` resuelve un nombre de fármaco a un SMILES y alimenta al
clasificador de intención, es decir, al camino de evaluación. Si una entrada
está mal, el usuario pide «celecoxib», el pipeline acopla otra cosa, y el
producto entrega un dossier impecable —con hashes, procedencia y controles
físicos superados— **sobre el compuesto que nadie pidió**.

Ese fallo es invisible para todo el resto del aparato de honestidad: la cadena
posterior sería correcta. Lo que estaría mal es la entrada. Por eso se comprueba
aquí y no en ningún otro sitio.

# Qué se comprueba, en orden de gravedad

1. **Toda entrada parsea.** Un SMILES roto rompe la evaluación.
2. **La fórmula coincide con la referencia.** Es lo que detectó que `celecoxib`
   había perdido el CF₃ y el tolilo, y que `codeína` no era codeína.
3. **Dos moléculas distintas no comparten estructura.** La fórmula sola no lo
   detecta: `metanfetamina` llevaba el SMILES de la `anfetamina`, y las dos
   parseaban perfectamente.
4. **Nadie deja marcas de «pendiente de verificar».** Una entrada sin verificar
   se retira; no se marca y se publica.
"""

from __future__ import annotations

import pytest

pytest.importorskip("rdkit", reason="la verificación estructural necesita RDKit")

from rdkit import Chem, RDLogger  # noqa: E402
from rdkit.Chem.rdMolDescriptors import CalcMolFormula  # noqa: E402

from services.ai.known_molecules import (  # noqa: E402
    KNOWN_MOLECULES,
    KNOWN_SMILES,
    _NON_SMILES_PREFIXES,
)

RDLogger.DisableLog("rdApp.*")

#: Fórmulas de referencia (PubChem). No cubre todo el diccionario: cubre lo que
#: se ha verificado. Añadir una entrada aquí es lo que la declara verificada.
REFERENCIA = {
    "aspirina": "C9H8O4",
    "ibuprofeno": "C13H18O2",
    "paracetamol": "C8H9NO2",
    "naproxeno": "C14H14O3",
    "diclofenaco": "C14H11Cl2NO2",
    "ketorolaco": "C15H13NO3",
    "celecoxib": "C17H14F3N3O2S",
    "metamizol": "C13H17N3O4S",
    "tramadol": "C16H25NO2",
    "morfina": "C17H19NO3",
    "codeina": "C18H21NO3",
    "oxicodona": "C18H21NO4",
    "fentanilo": "C22H28N2O",
    "metadona": "C21H27NO",
    "diazepam": "C16H13ClN2O",
    "lorazepam": "C15H10Cl2N2O2",
    "alprazolam": "C17H13ClN4",
    "clonazepam": "C15H10ClN3O3",
    "zolpidem": "C19H21N3O",
    "quetiapina": "C21H25N3O2S",
    "olanzapina": "C17H20N4S",
    "clozapina": "C18H19ClN4",
    "aripiprazol": "C23H27Cl2N3O2",
    "carbamazepina": "C15H12N2O",
    "lamotrigina": "C9H7Cl2N5",
    "levetiracetam": "C8H14N2O2",
    "levodopa": "C9H11NO4",
    "bupropion": "C13H18ClNO",
    "duloxetina": "C18H19NOS",
    "mirtazapina": "C17H19N3",
    "citalopram": "C20H21FN2O",
    "paroxetina": "C19H20FNO3",
    "fluoxetina": "C17H18F3NO",
    "sertralina": "C17H17Cl2N",
    "atorvastatina": "C33H35FN2O5",
    "simvastatina": "C25H38O5",
    "rosuvastatina": "C22H28FN3O6S",
    "losartan": "C22H23ClN6O",
    "valsartan": "C24H29N5O3",
    "enalapril": "C20H28N2O5",
    "captopril": "C9H15NO3S",
    "lisinopril": "C21H31N3O5",
    "amlodipino": "C20H25ClN2O5",
    "nifedipino": "C17H18N2O6",
    "felodipino": "C18H19Cl2NO4",
    "verapamilo": "C27H38N2O4",
    "carvedilol": "C24H26N2O4",
    "bisoprolol": "C18H31NO4",
    "propranolol": "C16H21NO2",
    "warfarina": "C19H16O4",
    "ampicilina": "C16H19N3O4S",
    "cefalexina": "C16H17N3O4S",
    "tetraciclina": "C22H24N2O8",
    "doxiciclina": "C22H24N2O8",
    "clindamicina": "C18H33ClN2O5S",
    "loratadina": "C22H23ClN2O2",
    "cetirizina": "C21H25ClN2O3",
    "difenhidramina": "C17H21NO",
    "ranitidina": "C13H22N4O3S",
    "estradiol": "C18H24O2",
    "progesterona": "C21H30O2",
    "dexametasona": "C22H29FO5",
    "prednisona": "C21H26O5",
    "dapagliflozina": "C21H25ClO6",
    "empagliflozina": "C23H27ClO7",
    "sitagliptina": "C16H15F6N5O",
    "glucosa": "C6H12O6",
    "fructosa": "C6H12O6",
    "sacarosa": "C12H22O11",
    "etanol": "C2H6O",
    "propanol": "C3H8O",
    "metanol": "CH4O",
    "acetona": "C3H6O",
    "benceno": "C6H6",
    "tolueno": "C7H8",
    "urea": "CH4N2O",
    "glicerol": "C3H8O3",
    "cafeina": "C8H10N4O2",
    "nicotina": "C10H14N2",
    "anfetamina": "C9H13N",
    "metanfetamina": "C10H15N",
    "noradrenalina": "C8H11NO3",
    "acetilcolina": "C7H16NO2",
    "retinol": "C20H30O",
    "colecalciferol": "C27H44O",
    "riboflavina": "C17H20N4O6",
    "vitamina b6": "C8H11NO3",
}

#: Nombres que apuntan a la MISMA molécula a propósito.
SINONIMOS_ESPERADOS = [
    {"aspirina", "acido acetilsalicilico"},
    {"paracetamol", "acetaminofen"},
    {"dapagliflozina", "dapagliflozin"},
    {"propranolol", "propanolol"},
    {"felodipino", "felodipina"},
    {"penicilina", "penicilina g", "penicillin g"},
    {"ciprofloxacino", "ciprofloxacina"},
    {"adrenalina", "epinefrina"},
    {"noradrenalina", "norepinefrina"},
    {"nicotina", "nicotine"},
    {"vitamina c", "acido ascorbico", "ascorbico"},
    {"vitamina d3", "colecalciferol"},
    {"vitamina a", "retinol"},
]


def _formula(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    return CalcMolFormula(mol) if mol is not None else None


# ── 1. Todo parsea ───────────────────────────────────────────────────


def test_toda_entrada_publicada_parsea_en_rdkit():
    """
    Un SMILES roto no es un hueco: revienta la evaluación que lo use.

    `KNOWN_SMILES` es lo que el resolutor entrega; los marcadores no-SMILES ya
    quedan fuera por construcción y no se comprueban aquí.
    """
    rotos = [nombre for nombre, smi in KNOWN_SMILES.items() if Chem.MolFromSmiles(smi) is None]
    assert rotos == [], f"SMILES que RDKit no parsea: {rotos}"


def test_los_marcadores_no_smiles_no_se_publican():
    """
    `MACROLIDE:`, `CORRINOID:`… declaran «no disponible localmente».

    Son honestos y se conservan, pero no pueden colarse a `KNOWN_SMILES`: allí
    dentro un marcador sería un SMILES roto. Es lo que pasaba con
    `INORGANIC/SALT:`, un prefijo que no estaba en la lista.
    """
    for nombre, valor in KNOWN_MOLECULES.items():
        if valor.startswith(_NON_SMILES_PREFIXES):
            assert nombre not in KNOWN_SMILES, nombre
    for nombre, smi in KNOWN_SMILES.items():
        # Ningún valor publicado puede parecer un marcador con dos puntos.
        assert not re_marcador(smi), f"{nombre} publica un marcador: {smi}"


def re_marcador(valor: str) -> bool:
    cabeza = valor.split(":", 1)[0]
    return ":" in valor and cabeza.isupper() and " " not in cabeza.strip("/ ")


# ── 2. La fórmula coincide con la referencia ─────────────────────────


@pytest.mark.parametrize("nombre", sorted(REFERENCIA))
def test_la_formula_coincide_con_la_referencia(nombre):
    """
    Es lo que detectó que `celecoxib` había perdido el CF₃ y el tolilo.

    Se compara la fórmula, no el SMILES: dos SMILES distintos pueden describir
    la misma molécula, y exigir uno concreto haría fallar la prueba por una
    diferencia de escritura en vez de por una diferencia química.
    """
    assert nombre in KNOWN_SMILES, f"«{nombre}» tiene referencia pero no está publicado"
    real = _formula(KNOWN_SMILES[nombre])
    esperada = REFERENCIA[nombre]
    assert real is not None, f"«{nombre}» no parsea"
    assert real.replace("+", "").replace("-", "") == esperada, (
        f"«{nombre}»: el diccionario describe {real} y la referencia dice {esperada}. "
        f"Corrige la estructura o retira la entrada; no la marques como pendiente."
    )


def test_la_cobertura_de_referencias_no_retrocede():
    """
    Un mínimo de entradas verificadas, para que nadie baje el listón callando.

    No exige el 100%: hay nombres cuya estructura no se ha confirmado y se
    resuelven contra PubChem. Exige que lo verificado no se erosione.
    """
    verificadas = [n for n in REFERENCIA if n in KNOWN_SMILES]
    assert len(verificadas) >= 80, f"sólo {len(verificadas)} entradas con referencia"


# ── 3. Dos moléculas distintas no comparten estructura ───────────────


def test_ningun_par_de_moleculas_distintas_comparte_estructura():
    """
    La fórmula sola no habría detectado esto.

    `metanfetamina` llevaba el SMILES de la `anfetamina`, y `propanolol` —errata
    de propranolol— el del 1-propanol: los cuatro parseaban perfectamente. Sólo
    comparar estructuras canónicas entre nombres lo saca a la luz.
    """
    por_estructura: dict[str, set[str]] = {}
    for nombre, smi in KNOWN_SMILES.items():
        try:
            canonico = Chem.CanonSmiles(smi)
        except Exception:                                          # noqa: BLE001
            continue
        por_estructura.setdefault(canonico, set()).add(nombre)

    compartidos = [nombres for nombres in por_estructura.values() if len(nombres) > 1]
    inesperados = [
        sorted(nombres) for nombres in compartidos
        if not any(nombres <= esperado for esperado in SINONIMOS_ESPERADOS)
    ]
    assert inesperados == [], (
        f"Nombres distintos con la MISMA estructura: {inesperados}. "
        f"Si son sinónimos, decláralos en SINONIMOS_ESPERADOS; si no, uno está mal."
    )


# ── 4. Nada queda marcado como «pendiente» ───────────────────────────


def test_no_quedan_entradas_marcadas_como_sin_verificar():
    """
    Una entrada sin verificar se RETIRA; no se marca y se publica.

    El resolutor consulta MolGraph y PubChem cuando el nombre no está aquí.
    «No lo sé localmente» es una respuesta correcta; una estructura equivocada
    bajo el nombre de un fármaco real, no.
    """
    import inspect

    from services.ai import known_molecules

    fuente = inspect.getsource(known_molecules)
    ini = fuente.index("KNOWN_MOLECULES: dict[str, str] = {")
    fin = fuente.index("\n}", ini)
    tabla = fuente[ini:fin]

    assert "TODO" not in tabla, "hay entradas marcadas como pendientes de verificar"
    assert "FIXME" not in tabla
