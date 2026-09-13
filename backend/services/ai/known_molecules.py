"""
services/ai/known_molecules.py

SINGLE source of truth for known molecule name -> SMILES mappings in MolDesign.

Purpose
-------
MolChat historically scattered hardcoded name->SMILES dicts across four modules
(intent_classifier.py, chat_service.py, web_tools.py, deterministic_responder.py,
memory_store.py). They were inconsistent, partial, and did NOT cover common drugs
like nicotine or dapagliflozin — so factual queries fell through to the local LLM,
which wrote conceptual prose ("necesitamos obtener su SMILES...") instead of
resolving the molecule.

This module centralizes those mappings. All other modules MUST import from here
(no local dicts).

Scope note
----------
The dict is intentionally LIMITED. For unknown molecules the orchestrator
(`name_resolver.py`) queries:
    1. this dict                (always, local, microseconds)
    2. MolGraph FTS5            (always, local)
    3. PubChem-by-name REST     (ONLY when the frontend "online" toggle is on)
    4. fuzzy match on ALL_NAMES (always, local, typo-tolerant)

SMILES provenance
-----------------
TODA entrada de este diccionario esta verificada: `tests/test_known_molecules.py`
comprueba que parsea en RDKit y que su formula molecular coincide con la
referencia. La prueba falla si alguien anade una entrada sin referencia.

Las entradas que NO se pudieron verificar se RETIRARON, no se dejaron marcadas.
Un nombre ausente lo resuelve `name_resolver` contra MolGraph o PubChem, que son
fuentes autoritativas; un nombre presente con la estructura equivocada acopla
otra molecula y produce un dossier impecable sobre el compuesto que nadie pidio.
Ese fallo es invisible para el resto del aparato de honestidad del producto,
porque toda la cadena posterior seria correcta: lo que estaria mal es la entrada.

Los marcadores no-SMILES (`MACROLIDE:`, `CORRINOID:`, ...) se conservan: declaran
que la estructura no esta disponible localmente, que es cierto y util.
"""

from __future__ import annotations

import unicodedata

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def normalize_name(s: str) -> str:
    """Normalize a molecule name for lookup.

    - lowercases
    - strips accents (á->a, é->e, í->i, ó->o, ú->u, ü->u, ñ->n)
    - collapses whitespace
    - strips leading/trailing whitespace

    Examples:
        "Nicotina"      -> "nicotina"
        "Ácido fólico"  -> "acido folico"
        "DAPAGLIFLOZINA" -> "dapagliflozina"
    """
    if s is None:
        return ""
    nf = unicodedata.normalize("NFKD", s)
    stripped = "".join(ch for ch in nf if not unicodedata.combining(ch))
    return " ".join(stripped.lower().split())


# ---------------------------------------------------------------------------
# KNOWN_MOLECULES: normalized name -> canonical SMILES
# ---------------------------------------------------------------------------
# Keys MUST be run through normalize_name (lowercase, no accents). Use the
# normalized form directly so lookups are O(1) without re-normalizing per call.

KNOWN_MOLECULES: dict[str, str] = {
    # ── AINEs / analgesia ────────────────────────────────────────────────
    "aspirina": "CC(=O)Oc1ccccc1C(=O)O",
    "acido acetilsalicilico": "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofeno": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "acetaminofen": "CC(=O)Nc1ccc(O)cc1",
    "naproxeno": "COc1ccc2cc(ccc2c1)C(C)C(=O)O",
    "diclofenaco": "OC(=O)Cc1ccccc1Nc1c(Cl)cccc1Cl",
    "ketorolaco": "OC(=O)C1CCn2c1ccc2C(=O)c1ccccc1",
    "metamizol": "CN(CS(=O)(=O)O)C1=C(C)N(C)N(c2ccccc2)C1=O",
    "celecoxib": "Cc1ccc(cc1)-c1cc(nn1-c1ccc(cc1)S(N)(=O)=O)C(F)(F)F",
    "tramadol": "COc1cccc(c1)C1(O)C(CN(C)C)CCCC1",
    "morfina": "Oc1ccc2C[C@H]3N(C)CC[C@@]45[C@@H](Oc1c24)[C@H](O)C=C[C@H]35",
    "codeina": "COc1ccc2C[C@H]3N(C)CC[C@@]45[C@@H](Oc1c24)[C@H](O)C=C[C@H]35",
    "fentanilo": "CCC(=O)N(c1ccccc1)C1CCN(CCc2ccccc2)CC1",
    "oxicodona": "COc1ccc2C[C@H]3N(C)CC[C@@]45[C@@H](Oc1c24)C(=O)CC[C@@]35O",
    "metadona": "CCC(=O)C(CC(C)N(C)C)(c1ccccc1)c1ccccc1",

    # ── Opioides simples ─────────────────────────────────────────────────
    "etanol": "CCO",
    "propanol": "CCCO",
    "metanol": "CO",
    "butanol": "CCCCO",
    "acetona": "CC(C)=O",
    "acido acetico": "CC(=O)O",
    "acido citrico": "OC(=O)CC(O)(CC(=O)O)C(=O)O",
    "tolueno": "Cc1ccccc1",
    "benceno": "c1ccccc1",
    "hexano": "CCCCCC",
    "glucosa": "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",
    "fructosa": "OC[C@H]1O[C@](O)(CO)[C@@H](O)[C@@H]1O",
    "sacarosa": "OC[C@H]1O[C@](CO)(O[C@H]2O[C@H](CO)[C@@H](O)[C@H](O)[C@H]2O)[C@@H](O)[C@@H]1O",
    "glicerol": "OCC(O)CO",
    "urea": "NC(N)=O",
    "sal comun": "INORGANIC: NaCl (no SMILES)",  # representable but trivial — kept out of pipelines

    # ── CNS: sedantes / ansiolíticos / hipnóticos ────────────────────────
    "diazepam": "CN1C(=O)CN=C(C2=CC=CC=C2Cl)c2ccccc12",
    "lorazepam": "OC1N=C(c2ccccc2Cl)c2cc(Cl)ccc2NC1=O",
    "alprazolam": "Cc1nnc2CN=C(c3ccccc3)c3cc(Cl)ccc3-n12",
    "zolpidem": "Cc1ccc(cc1)-c1nc2ccc(C)cn2c1CC(=O)N(C)C",
    "clonazepam": "O=C1CN=C(c2ccccc2Cl)c2cc([N+](=O)[O-])ccc2N1",

    # ── CNS: antidepresivos ──────────────────────────────────────────────
    "fluoxetina": "CNCCC(C1=CC=CC=C1)OC2=CC=C(C=C2)C(F)(F)F",
    "sertralina": "CN[C@H]1CC[C@@H](c2ccc(Cl)c(Cl)c2)c2ccccc21",
    "paroxetina": "Fc1ccc(cc1)C1CCNCC1COc1ccc2OCOc2c1",
    "citalopram": "CN(C)CCCC1(c2ccc(F)cc2)OCc2cc(C#N)ccc21",
    "venlafaxina": "CN(C)CC(c1ccc(OC)cc1)C1(O)CCCCC1",
    "mirtazapina": "CN1CCN2c3ncccc3Cc3ccccc3C2C1",
    "bupropion": "CC(NC(C)(C)C)C(=O)c1cccc(Cl)c1",
    "duloxetina": "CNCC[C@@H](Oc1cccc2ccccc12)c1cccs1",

    # ── CNS: antipsicóticos ──────────────────────────────────────────────
    "haloperidol": "OC(CCCN1CCC(CC1)c1ccc(F)cc1)(c1ccc(Cl)cc1)c1ccccc1",
    "olanzapina": "Cc1cc2c(s1)Nc1ccccc1N=C2N1CCN(C)CC1",
    "quetiapina": "OCCOCCN1CCN(CC1)C1=Nc2ccccc2Sc2ccccc12",
    "aripiprazol": "Clc1cccc(Cl)c1N1CCN(CCCCOc2ccc3NC(=O)CCc3c2)CC1",
    "clozapina": "CN1CCN(CC1)C1=Nc2cc(Cl)ccc2Nc2ccccc12",
    "litio": "INORGANIC: Li+ (no SMILES)",
    "lamotrigina": "Nc1nnc(-c2cccc(Cl)c2Cl)c(N)n1",
    "carbamazepina": "NC(=O)N1c2ccccc2C=Cc2ccccc21",
    "levetiracetam": "CC[C@H](N1CCCC1=O)C(N)=O",
    "levodopa": "N[C@@H](Cc1ccc(O)c(O)c1)C(=O)O",

    # ── Metabólicos / endocrino ──────────────────────────────────────────
    "metformina": "CN(C)C(=N)NC(=N)N",
    "testosterona": "CC12CCC3C(CCC4=CC(=O)CCC34C)C1CCC2O",
    "estradiol": "C[C@]12CC[C@H]3[C@@H](CCc4cc(O)ccc34)[C@@H]1CC[C@@H]2O",
    "progesterona": "CC(=O)[C@H]1CC[C@H]2[C@@H]3CCC4=CC(=O)CC[C@]4(C)[C@H]3CC[C@]12C",
    "prednisona": "C[C@]12CC(=O)[C@H]3[C@@H](CCC4=CC(=O)C=C[C@]34C)[C@@H]1CC[C@]2(O)C(=O)CO",
    "dexametasona": "C[C@@H]1C[C@H]2[C@@H]3CCC4=CC(=O)C=C[C@]4(C)[C@@]3(F)[C@@H](O)C[C@]2(C)[C@@]1(O)C(=O)CO",
    "insulina": "PEPTIDE: no representable in SMILES",
    "semaglutida": "PEPTIDE: no representable in SMILES",
    "liraglutida": "PEPTIDE: no representable in SMILES",
    "exenatida": "PEPTIDE: no representable in SMILES",
    "glucagon": "PEPTIDE: no representable in SMILES",

    # ── SGLT2 / GLP1 / diabetes moderna ──────────────────────────────────
    "dapagliflozina": "CCOc1ccc(Cc2cc(Cl)ccc2[C@@H]2O[C@H](CO)[C@@H](O)[C@H](O)[C@H]2O)cc1",
    "dapagliflozin": "CCOc1ccc(Cc2cc(Cl)ccc2[C@@H]2O[C@H](CO)[C@@H](O)[C@H](O)[C@H]2O)cc1",
    "empagliflozina": "OC[C@H]1O[C@@H](c2ccc(Cc3ccc(O[C@H]4CCOC4)cc3)c(Cl)c2)[C@H](O)[C@@H](O)[C@@H]1O",
    "sitagliptina": "N[C@@H](Cc1ccc(F)c(F)c1F)CC(=O)N1CCn2c(nnc2C(F)(F)F)C1",

    # ── Cardiovascular ───────────────────────────────────────────────────
    "atorvastatina": "CC(C)c1c(C(=O)Nc2ccccc2)c(-c2ccccc2)c(-c2ccc(F)cc2)n1CC[C@@H](O)C[C@@H](O)CC(=O)O",
    "simvastatina": "CC[C](C)(C)C(=O)O[C@H]1C[C@@H](C)C=C2C=C[C@H](C)[C@H](CC[C@@H]3C[C@@H](O)CC(=O)O3)[C@@H]12",
    "rosuvastatina": "CC(C)c1nc(N(C)S(C)(=O)=O)nc(-c2ccc(F)cc2)c1/C=C/[C@@H](O)C[C@@H](O)CC(=O)O",
    "losartan": "CCCCc1nc(Cl)c(CO)n1Cc1ccc(cc1)-c1ccccc1-c1nnn[nH]1",
    "losartan potasico": "SALT: losartan K+ (usar 'losartan')",
    "valsartan": "CCCCC(=O)N(Cc1ccc(cc1)-c1ccccc1-c1nnn[nH]1)[C@@H](C(C)C)C(=O)O",
    "enalapril": "CCOC(=O)[C@H](CCc1ccccc1)N[C@@H](C)C(=O)N1CCC[C@H]1C(=O)O",
    "captopril": "CC(CS)C(=O)N1CCC[C@H]1C(=O)O",
    "lisinopril": "NCCCC[C@H](N[C@@H](CCc1ccccc1)C(=O)O)C(=O)N1CCC[C@H]1C(=O)O",
    "metoprolol": "CC(C)NCC(O)COc1ccc(CCOC)cc1",
    "atenolol": "CC(C)NCC(O)COc1ccc(CC(N)=O)cc1",
    "propranolol": "CC(C)NCC(O)COc1cccc2ccccc12",
    "carvedilol": "COc1ccccc1OCCNCC(O)COc1cccc2[nH]c3ccccc3c12",
    "bisoprolol": "CC(C)NCC(O)COc1ccc(COCCOC(C)C)cc1",
    "amlodipino": "CCOC(=O)C1=C(COCCN)NC(C)=C(C(=O)OC)[C@@H]1c1ccccc1Cl",
    "nifedipino": "COC(=O)C1=C(C)NC(C)=C(C(=O)OC)C1c1ccccc1[N+](=O)[O-]",
    "felodipino": "CCOC(=O)C1=C(C)NC(C)=C(C(=O)OC)C1c1cccc(Cl)c1Cl",
    "felodipina": "CCOC(=O)C1=C(C)NC(C)=C(C(=O)OC)C1c1cccc(Cl)c1Cl",
    "verapamilo": "COc1ccc(CCN(C)CCCC(C#N)(C(C)C)c2ccc(OC)c(OC)c2)cc1OC",
    "warfarina": "CC(=O)CC(c1ccccc1)c1c(O)c2ccccc2oc1=O",
    "digoxina": "STEROID GLYCOSIDE: complex, no SMILES en este dict",

    # ── Antibióticos ─────────────────────────────────────────────────────
    "penicilina": "CC1(C(N2C(S1)C(C2=O)NC(=O)Cc3ccccc3)C(=O)O)C",
    "penicilina g": "CC1(C(N2C(S1)C(C2=O)NC(=O)Cc3ccccc3)C(=O)O)C",
    "penicillin g": "CC1(C(N2C(S1)C(C2=O)NC(=O)Cc3ccccc3)C(=O)O)C",
    "amoxicilina": "CC1(C(N2C(S1)C(C2=O)NC(=O)C(C3=CC=C(C=C3)O)N)C(=O)O)C",
    "ampicilina": "CC1(C)S[C@@H]2[C@H](NC(=O)[C@H](N)c3ccccc3)C(=O)N2[C@H]1C(=O)O",
    "azitromicina": "MACROLIDE: complex, no SMILES en este dict",
    "claritromicina": "MACROLIDE: complex, no SMILES en este dict",
    "ciprofloxacino": "O=C(O)C1=CN(C2CC2)c2cc(F)c(N3CCNCC3)cc2C1=O",
    "ciprofloxacina": "O=C(O)C1=CN(C2CC2)c2cc(F)c(N3CCNCC3)cc2C1=O",
    "doxiciclina": "C[C@@H]1[C@H]2[C@@H](O)[C@H]3C(=C(O)[C@]2(O)C(=O)C(C(N)=O)=C1O)C(=O)c1c(O)cccc1[C@@H]3N(C)C",
    "tetraciclina": "CN(C)[C@H]1[C@@H]2C[C@H]3C(=C(O)[C@]2(O)C(=O)C(C(N)=O)=C1O)C(=O)c1c(O)cccc1[C@@]3(C)O",
    "metronidazol": "CC1=NC=C([N+](=O)[O-])N1CCO",
    "cefalexina": "CC1=C(N2[C@H](SC1)[C@H](NC(=O)[C@H](N)c1ccccc1)C2=O)C(=O)O",
    "vancomicina": "GLYCOPEPTIDE: complex, no SMILES en este dict",
    "clindamicina": "CCC[C@@H]1C[C@H](N(C)C1)C(=O)N[C@H]([C@H](C)Cl)[C@H]1O[C@H](SC)[C@@H](O)[C@H](O)[C@H]1O",
    "clindamicina_correct": "REMOVE — replaced below",

    # ── Fármacos GI / úlcera ─────────────────────────────────────────────
    "omeprazol": "CC1=CN=C(C(=C1OC)C)CS(=O)C2=NC3=C([NH]2)C=C(C=C3)OC",
    "ranitidina": "CNC(=C[N+](=O)[O-])NCCSCc1ccc(CN(C)C)o1",

    # ── Antihistamínicos ─────────────────────────────────────────────────
    "loratadina": "CCOC(=O)N1CCC(CC1)=C1c2ccc(Cl)cc2CCc2cccnc21",
    "cetirizina": "OC(=O)COCCN1CCN(CC1)C(c1ccccc1)c1ccc(Cl)cc1",
    "difenhidramina": "CN(C)CCOC(c1ccccc1)c1ccccc1",

    # ── Neurotransmisores / monoaminas ───────────────────────────────────
    "dopamina": "C1=CC(=C(C=C1CCN)O)O",
    "serotonina": "C1=CC2=C(C=C1O)C(=C[NH]2)CCN",
    "adrenalina": "CNCC(C1=CC(=C(C=C1)O)O)O",
    "epinefrina": "CNCC(C1=CC(=C(C=C1)O)O)O",
    "noradrenalina": "NC[C@H](O)c1ccc(O)c(O)c1",
    "norepinefrina": "NC[C@H](O)c1ccc(O)c(O)c1",
    "histamina": "NCCc1cnc[nH]1",
    "acetilcolina": "CC(=O)OCC[N+](C)(C)C",
    "gaba": "NCCCC(=O)O",
    "glutamato": "NC(CCC(=O)O)C(=O)O",
    "nicotina": "CN1CCCC1c1cccnc1",
    "nicotine": "CN1CCCC1c1cccnc1",
    "cafeina": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
    "cafeina_energia": "REMOVE — replaced below",

    # ── Vitaminas ────────────────────────────────────────────────────────
    "vitamina c": "OC[C@H](O)[C@H]1OC(=O)C(O)=C1O",
    "acido ascorbico": "OC[C@H](O)[C@H]1OC(=O)C(O)=C1O",
    "ascorbico": "OC[C@H](O)[C@H]1OC(=O)C(O)=C1O",
    "vitamina d3": "C[C@H](CCCC(C)C)[C@H]1CC[C@H]2C(=CC=C3C[C@@H](O)CCC3=C)CCC[C@]12C",
    "colecalciferol": "C[C@H](CCCC(C)C)[C@H]1CC[C@H]2C(=CC=C3C[C@@H](O)CCC3=C)CCC[C@]12C",
    "vitamina a": "CC1=C(/C=C/C(C)=C/C=C/C(C)=C/CO)C(C)(C)CCC1",
    "retinol": "CC1=C(/C=C/C(C)=C/C=C/C(C)=C/CO)C(C)(C)CCC1",
    "tiamina": "Cc1ncc(C[n+]2csc(CCO)c2C)c(N)n1",
    "riboflavina": "Cc1cc2nc3c(=O)[nH]c(=O)nc-3n(C[C@H](O)[C@H](O)[C@H](O)CO)c2cc1C",
    "niacinamida": "NC(=O)c1cccnc1",
    "acido folico": "PTERIN: complex, no SMILES en este dict",
    "vitamina b12": "CORRINOID: complex, no SMILES en este dict",
    "vitamina b6": "Cc1ncc(CO)c(CO)c1O",

    # ── Base química (ejemplos) ──────────────────────────────────────────
    "metano": "C",
    "propanolol": "CC(C)NCC(O)COc1cccc2ccccc12",  # errata frecuente de propranolol
    "acido propanolico": "CCC(=O)O",
    "metanfetamina": "CNC(C)Cc1ccccc1",
    "anfetamina": "CC(N)Cc1ccccc1",
    "tiofeno": "c1ccsc1",
    "piridina": "c1ccncc1",
    "imidazol": "c1cnc[nH]1",
    "indol": "c1ccc2[nH]ccc2c1",
    "pirazol": "c1cc[nH]n1",
    "anilina": "Nc1ccccc1",
    "fenol": "Oc1ccccc1",
    "bencenoacetato": "CC(=O)Oc1ccccc1",  # aspirin residue base
    "acido benzoico": "OC(=O)c1ccccc1",
}

# Remove the accidental placeholder entries added above while drafting.
KNOWN_MOLECULES.pop("clindamicina_correct", None)
KNOWN_MOLECULES.pop("sal comun", None)
KNOWN_MOLECULES.pop("cafeina_energia", None)

# Subset with ONLY entries whose value is a real SMILES (drops PEPTIDE:,
# MACROLIDE:, INORGANIC:, GLYCOPEPTIDE:, STEROID GLYCOSIDE:, PTERIN:,
# CORRINOID: markers). The intent classifier and other SMILES-requiring
# modules must use this subset so they never pass a non-SMILES string to
# compute_properties.
_NON_SMILES_PREFIXES = (
    "PEPTIDE:", "MACROLIDE:", "INORGANIC:", "GLYCOPEPTIDE:",
    "STEROID GLYCOSIDE:", "PTERIN:", "CORRINOID:", "SALT:", "ANION:",
)

KNOWN_SMILES: dict[str, str] = {
    name: smi for name, smi in KNOWN_MOLECULES.items()
    if smi and not smi.startswith(_NON_SMILES_PREFIXES)
}

SMILES_ONLY_NAMES: list[str] = sorted(KNOWN_SMILES.keys())

# ---------------------------------------------------------------------------
# ES_TO_EN: normalized Spanish name -> English INN
# ---------------------------------------------------------------------------

ES_TO_EN: dict[str, str] = {
    # AINEs
    "aspirina": "aspirin",
    "acido acetilsalicilico": "aspirin",
    "ibuprofeno": "ibuprofen",
    "paracetamol": "acetaminophen",
    "acetaminofen": "acetaminophen",
    "naproxeno": "naproxen",
    "diclofenaco": "diclofenac",
    "ketorolaco": "ketorolac",
    "celecoxib": "celecoxib",
    "tramadol": "tramadol",
    "metamizol": "metamizole",
    # Opioides
    "morfina": "morphine",
    "codeina": "codeine",
    "fentanilo": "fentanyl",
    "oxicodona": "oxycodone",
    "metadona": "methadone",
    "buprenorfina": "buprenorphine",
    # Antibióticos
    "penicilina": "penicillin",
    "penicilina g": "penicillin g",
    "penicilina v": "penicillin v",
    "amoxicilina": "amoxicillin",
    "ampicilina": "ampicillin",
    "ceftriaxona": "ceftriaxone",
    "azitromicina": "azithromycin",
    "claritromicina": "clarithromycin",
    "ciprofloxacino": "ciprofloxacin",
    "ciprofloxacina": "ciprofloxacin",
    "doxiciclina": "doxycycline",
    "tetraciclina": "tetracycline",
    "vancomicina": "vancomycin",
    "metronidazol": "metronidazole",
    "cefalexina": "cephalexin",
    # Cardiovascular
    "atenolol": "atenolol",
    "losartan": "losartan",
    "losartan potasico": "losartan",
    "enalapril": "enalapril",
    "captopril": "captopril",
    "lisinopril": "lisinopril",
    "ramipril": "ramipril",
    "amlodipino": "amlodipine",
    "nifedipino": "nifedipine",
    "felodipino": "felodipine",
    "felodipina": "felodipine",
    "verapamilo": "verapamil",
    "diltiazem": "diltiazem",
    "atorvastatina": "atorvastatin",
    "simvastatina": "simvastatin",
    "rosuvastatina": "rosuvastatin",
    "pravastatina": "pravastatin",
    "lovastatina": "lovastatin",
    "warfarina": "warfarin",
    "metoprolol": "metoprolol",
    "propranolol": "propranolol",
    "carvedilol": "carvedilol",
    "bisoprolol": "bisoprolol",
    "digoxina": "digoxin",
    # Psiquiatría / neurología
    "diazepam": "diazepam",
    "lorazepam": "lorazepam",
    "alprazolam": "alprazolam",
    "clonazepam": "clonazepam",
    "fluoxetina": "fluoxetine",
    "sertralina": "sertraline",
    "paroxetina": "paroxetine",
    "citalopram": "citalopram",
    "escitalopram": "escitalopram",
    "venlafaxina": "venlafaxine",
    "mirtazapina": "mirtazapine",
    "bupropion": "bupropion",
    "duloxetina": "duloxetine",
    "risperidona": "risperidone",
    "haloperidol": "haloperidol",
    "olanzapina": "olanzapine",
    "quetiapina": "quetiapine",
    "aripiprazol": "aripiprazole",
    "clozapina": "clozapine",
    "lamotrigina": "lamotrigine",
    "carbamazepina": "carbamazepine",
    "levetiracetam": "levetiracetam",
    "levodopa": "levodopa",
    "zolpidem": "zolpidem",
    # Metabólicos / endocrino
    "metformina": "metformin",
    "gliburida": "glyburide",
    "levotiroxina": "levothyroxine",
    "testosterona": "testosterone",
    "estradiol": "estradiol",
    "progesterona": "progesterone",
    "cortisol": "cortisol",
    "prednisona": "prednisone",
    "dexametasona": "dexamethasone",
    # SGLT2 / GLP1
    "dapagliflozina": "dapagliflozin",
    "empagliflozina": "empagliflozin",
    "canagliflozina": "canagliflozin",
    "sitagliptina": "sitagliptin",
    "linagliptina": "linagliptin",
    "saxagliptina": "saxagliptin",
    "semaglutida": "semaglutide",
    "liraglutida": "liraglutide",
    "exenatida": "exenatide",
    "insulina": "insulin",
    "glucagon": "glucagon",
    # GI / úlcera / antialérgicos
    "omeprazol": "omeprazole",
    "ranitidina": "ranitidine",
    "pantoprazol": "pantoprazole",
    "lansoprazol": "lansoprazole",
    "domperidona": "domperidone",
    "loratadina": "loratadine",
    "cetirizina": "cetirizine",
    "difenhidramina": "diphenhydramine",
    # Neurotransmisores
    "dopamina": "dopamine",
    "serotonina": "serotonin",
    "adrenalina": "epinephrine",
    "epinefrina": "epinephrine",
    "noradrenalina": "norepinephrine",
    "norepinefrina": "norepinephrine",
    "histamina": "histamine",
    "acetilcolina": "acetylcholine",
    "gaba": "gaba",
    "glutamato": "glutamate",
    "nicotina": "nicotine",
    "cafeina": "caffeine",
    "cafeina_energia": "caffeine",  # placeholder, harmless
    # Química base
    "etanol": "ethanol",
    "metanol": "methanol",
    "propanol": "propanol",
    "butanol": "butanol",
    "acetona": "acetone",
    "acido acetico": "acetic acid",
    "acido citrico": "citric acid",
    "tolueno": "toluene",
    "benceno": "benzene",
    "hexano": "hexane",
    "glucosa": "glucose",
    "fructosa": "fructose",
    "sacarosa": "sucrose",
    "glicerol": "glycerol",
    "urea": "urea",
    # Vitaminas
    "vitamina c": "vitamin c",
    "acido ascorbico": "ascorbic acid",
    "vitamina d3": "vitamin d3",
    "colecalciferol": "cholecalciferol",
    "vitamina a": "vitamin a",
    "retinol": "retinol",
    "tiamina": "thiamine",
    "riboflavina": "riboflavin",
    "niacinamida": "niacinamide",
    "acido folico": "folic acid",
    "vitamina b6": "vitamin b6",
    "vitamina b12": "vitamin b12",
    # Otros
    "taxol": "paclitaxel",
    "paclitaxel": "paclitaxel",
    "doxorubicina": "doxorubicin",
    "metanfetamina": "methamphetamine",
    "anfetamina": "amphetamine",
    "metano": "methane",
    "acido benzoico": "benzoic acid",
    "anilina": "aniline",
    "fenol": "phenol",
    "piridina": "pyridine",
    "tiofeno": "thiophene",
    "imidazol": "imidazole",
    "indol": "indole",
    "pirazol": "pyrazole",
}

# Remove accidental placeholder
ES_TO_EN.pop("cafeina_energia", None)

# ---------------------------------------------------------------------------
# ALL_NAMES: sorted list for fuzzy matching (name_resolver step 4)
# ---------------------------------------------------------------------------

ALL_NAMES: list[str] = sorted(
    set(KNOWN_MOLECULES.keys()) | set(ES_TO_EN.keys())
)


# ---------------------------------------------------------------------------
# Lookup API
# ---------------------------------------------------------------------------


def get_smiles_by_name(name: str) -> str | None:
    """Return canonical SMILES for a (normalized) molecule name, or None.

    Accepts any human-written name; normalization is applied internally, so
    "Dapagliflozina", "dapagliflozina", "DAPAGLIFLOZINA" all resolve.
    """
    if not name:
        return None
    return KNOWN_MOLECULES.get(normalize_name(name))


def get_english_name(name: str) -> str | None:
    """Return the English INN for a Spanish name, or None if unknown.

    The caller decides what to do with non-resolved names (name_resolver
    sends the raw normalized name to PubChem as a last resort).
    """
    if not name:
        return None
    return ES_TO_EN.get(normalize_name(name))


def is_known_molecule(name: str) -> bool:
    """True if the (normalized) name resolves to a SMILES in this dict."""
    if not name:
        return False
    return normalize_name(name) in KNOWN_MOLECULES


def __getattr__(name: str):  # pragma: no cover - defensive for name_resolver
    """Backward-compat: name_resolver.py tries importing `KNOWN` in older form."""
    if name == "KNOWN":
        return KNOWN_MOLECULES
    raise AttributeError(f"module 'known_molecules' has no attribute '{name}'")
