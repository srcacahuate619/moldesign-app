"""Deterministic intent classifier. No LLM: regex + keyword rule tree.

Reimplemented from MolDesign's ``intent_classifier.py`` without importing
it. Same rule ORDER (the order is the behavior): preparation before bare
SMILES, anaphora before known names, rank before compare. Differences are
deliberate: a minimal molecule table (the 8 quality-suite molecules, facts
verified against the internal table), a structural SMILES plausibility
check instead of RDKit (real validation stays server-side), and an explicit
``druglikeness`` intent so Lipinski/Veber questions route deterministically
instead of through a model tool-loop.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re

# Molecule names verified against known_molecules.KNOWN_SMILES (reference
# commit). Short factual identifiers; the table grows with the tool-pack.
KNOWN_SMILES = {
    "aspirina": "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofeno": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "cafeina": "Cn1c(=O)c2c(ncn2C)n(C)c1=O",
    "morfina": "Oc1ccc2C[C@H]3N(C)CC[C@@]45[C@@H](Oc1c24)[C@H](O)C=C[C@H]35",
    "etanol": "CCO",
    "dopamina": "C1=CC(=C(C=C1CCN)O)O",
    "glucosa": "OC[C@H]1O[C@@H](O)[C@H](O)[C@@H](O)[C@@H]1O",
}
ENGLISH_ALIASES = {
    "aspirin": "aspirina", "ibuprofen": "ibuprofeno",
    "acetaminophen": "paracetamol", "caffeine": "cafeina",
    "morphine": "morfina", "ethanol": "etanol", "dopamine": "dopamina",
    "glucose": "glucosa",
}


@dataclass
class Intent:
    name: str
    smiles: str | None = None
    target: str | None = None
    tool: str | None = None
    smiles_b: str | None = None
    smiles_list: list[str] | None = None
    suggest_mode: str | None = None
    suggest_target: str | None = None
    smiles_source: str | None = None


def normalize(text: str) -> str:
    table = str.maketrans("áéíóúüñ", "aeiouun")
    return text.lower().translate(table)


_PDB_RE = re.compile(
    r"(?:contra|target|receptor|prote[íi]na|enzima)\s+"
    r"(?:la\s+(?:prote[íi]na|enzima|receptor)\s+)?"
    r"(\d[0-9A-Za-z\-]{2,})",
    re.I,
)
_SMILES_RE = re.compile(r"\b([A-Z][A-Za-z0-9\r\(\)\[\]@=#+\\/.\-\%]{1,})")
_ANA_RE = re.compile(
    r"(?:"
    r"esa\s+(?:primera|segunda|otra)\s+mol[ée]cula"
    r"|y\s+del?\s+\w+\?"
    r"|y\s+de\s+la\s+\w+\?"
    r"|y\s+(?:la|el)\s+\w+\?"  # fix vs internal: "y la cafeina?" is recall
    r")",
    re.I,
)
_COMPARE_RE = re.compile(
    r"(?:"
    r"compar[áa]|compara|comp[áa]r[áa]?me|comparaci[óo]n|vs\.?|versus|"
    r"diferencia[s]?\s+entre|"
    r"cu[aá]l\s+es\s+(?:mejor|m[áa]s|mayor|menor)|"
    r"(?:mayor|menor|m[áa]s)\s+(?:peso|masa|afinidad)|"
    r"pes[ao]\s+m[áa]s|pesa\s+m[áa]s|m[áa]s\s+pesad[oa]|m[áa]s\s+livian[oa]"
    r")",
    re.I,
)
_PDB_SUELTO = re.compile(r"\b([0-9][A-Za-z0-9]{3})\b")

_DOCKING = {"afinidad", "docking", "acopl", "acópl"}
_PREPARACION = {
    "preparación", "preparacion", "preparar", "prepara", "preflight", "bloquead",
    "bloquea", "listo", "lista para", "advertencia", "pierde metales", "metales",
    "aguas", "huecos", "preparation", "prepared", "ready for", "blocked", "warning",
}
_DRUGLIKENESS = {
    "lipinski", "veber", "drug-likeness", "druglikeness", "drug likeness",
    "pains", "regla de", "cumple", "aprobado", "fallido",
}
_ANALOG = {"similares", "análogos", "análogo", "analogo", "analogs"}

# Structural SMILES plausibility (NOT chemical validity: that stays
# server-side with RDKit). Rejects garbage the internal classifier rejects
# ("KILLMEnow": L starts no element; "zzzz": z is not aromatic).
_ELEMENT_STARTS = set("BCNOFPSKVYIWU")
_TWO_LETTER = {"Cl", "Br", "Si", "Na", "Ca", "Fe", "Mg", "Al", "Li", "Zn",
               "Cu", "Mn", "Co", "Ni", "Mo", "Ag", "Au", "Pt", "Pd", "Hg",
               "Pb", "Sn", "As", "Se", "Te"}
_AROMATIC = set("bcnops")
_BONDS = set("=#+-/\\.:@%")


def smiles_plausible(token: str) -> bool:
    """Structural plausibility of a SMILES candidate. Documented heuristic."""
    if not 3 <= len(token) <= 2000 or not token[0].isupper():
        return False
    depth_paren = depth_brack = 0
    digits: dict[str, int] = {}
    atoms = 0
    i = 0
    while i < len(token):
        ch = token[i]
        if ch == "(":
            depth_paren += 1
        elif ch == ")":
            depth_paren -= 1
        elif ch == "[":
            depth_brack += 1
        elif ch == "]":
            depth_brack -= 1
        elif ch == "%" and i + 2 < len(token) and token[i + 1:i + 3].isdigit():
            digits[token[i + 1:i + 3]] = digits.get(token[i + 1:i + 3], 0) + 1
            i += 2
        elif ch.isdigit():
            digits[ch] = digits.get(ch, 0) + 1
        elif ch.isupper():
            pair = token[i:i + 2]
            if len(pair) == 2 and pair[1].islower() and pair in _TWO_LETTER:
                i += 1
            elif ch not in _ELEMENT_STARTS:
                return False
            atoms += 1
        elif ch.islower():
            if ch not in _AROMATIC:
                return False
            atoms += 1
        elif ch not in _BONDS:
            return False
        if depth_paren < 0 or depth_brack < 0:
            return False
        i += 1
    if depth_paren != 0 or depth_brack != 0 or atoms == 0:
        return False
    return all(count % 2 == 0 for count in digits.values())


def _has(lo: str, keywords: set[str]) -> bool:
    return any(k.lower() in lo for k in keywords)


def find_name(text: str) -> str | None:
    lo = normalize(text)
    for name in sorted(KNOWN_SMILES, key=len, reverse=True):
        if name in lo:
            return name
    for alias, name in ENGLISH_ALIASES.items():
        if alias in lo:
            return name
    return None


def find_all_names(text: str) -> list[str] | None:
    lo = normalize(text)
    found: list[tuple[int, str]] = []
    for name in KNOWN_SMILES:
        pos = lo.find(name)
        if pos >= 0 and name not in [f[1] for f in found]:
            found.append((pos, name))
    if len(found) >= 2:
        found.sort(key=lambda item: item[0])
        return [name for _, name in found]
    return None


def _extract_smiles(text: str) -> str | None:
    for match in _SMILES_RE.finditer(text):
        candidate = match.group(1)
        if len(candidate) >= 3 and smiles_plausible(candidate):
            return candidate
    return None


def _find_possible_smiles(text: str) -> str | None:
    for match in _SMILES_RE.finditer(text):
        if len(match.group(1)) >= 3:
            return match.group(1)
    return None


def _extract_pdb(text: str) -> str:
    match = _PDB_RE.search(text)
    return match.group(1).strip() if match else ""


def _pdb_suelto(text: str) -> str:
    for match in _PDB_SUELTO.finditer(text):
        if any(c.isalpha() for c in match.group(1)):
            return match.group(1).upper()
    return ""


def _find_compare_names(text: str) -> tuple[str, str] | None:
    names = find_all_names(text)
    if names and len(names) >= 2:
        return names[0], names[1]
    candidate = _extract_smiles(text)
    if names and len(names) == 1 and candidate:
        return names[0], candidate
    return None


def classify(msg: str) -> Intent:
    """Single entry point: classify the message intent."""
    lo = msg.lower()

    # Case management is not exposed as a chat operation. Never send a request
    # to mutate a case to the conceptual model as if it had acted on the host.
    if re.search(r"\b(?:caso|case)s?\b", lo) and re.search(
        r"\b(?:crea(?:r|me)?|crear|abre|abrir|elimina(?:r)?|borra(?:r)?|create|delete|open)\b", lo
    ):
        return Intent("case_action", tool=None)

    # Preparation check first: needs a PDB in the sentence.
    pdb_prep = _pdb_suelto(msg)
    if pdb_prep and _has(lo, _PREPARACION):
        smiles_prep = _extract_smiles(msg)
        return Intent("preparation", smiles=smiles_prep, target=pdb_prep,
                      tool="check_preparation",
                      smiles_source="explicit" if smiles_prep else None)

    # Explicit SMILES in the message.
    explicit = _extract_smiles(msg)
    if explicit:
        if _has(lo, _DOCKING):
            pdb = _extract_pdb(msg) or _pdb_suelto(msg)
            return Intent("docking", smiles=explicit, target=pdb,
                          tool="run_docking", smiles_source="explicit")
        if _has(lo, _ANALOG):
            return Intent("analog", smiles=explicit, target=None,
                          tool="molgraph_similar", smiles_source="explicit")
        return Intent("chemical", smiles=explicit, target=None,
                      tool="compute_properties", smiles_source="explicit")

    # Anaphora (before known names: "y del paracetamol?" is recall).
    if _ANA_RE.search(lo):
        return Intent("recall_anaphoric", tool=None, smiles_source=None)

    # Complex molecular design requests: honest refusal, never a guess.
    if _has(lo, {"smiles", "molécula", "molecula", "estructura", "análogo",
                 "analogo", "derivado", "compuesto"}) and _has(lo, {
            "con un", "con una", "fusionad", "fusionado", "puente", "tioeter",
            "tioéter", "anillo", "anillos", "sustituyente", "grupo",
            "oxazolidinona", "peptido ciclico", "péptido cíclico"}):
        return Intent("design", tool=None, smiles_source=None)

    # Verified source: the user asks for the SOURCE, not a recompute.
    if ((_has(lo, {"fuente", "fuentes", "doi", "url", "cita", "citar",
                   "de donde", "de dónde", "origen", "referencia"})
         and find_name(lo)) or (
            _has(lo, {"fuente", "doi", "url", "cita", "de donde", "de dónde"})
            and _has(lo, {"adme", "logp", "log p", "mw", "peso", "tpsa"}))):
        return Intent("source", tool="query_verified_source", smiles_source=None)

    # Suggest molecules (before known names: "variante de X" is suggest).
    # Guard (fix vs internal): "dame las propiedades de X" asks for PROPERTIES
    # of a named molecule, not for a new molecule (internal misroutes B03).
    if _has(lo, {"dame", "quiero un", "necesito un", "suger", "muestrame",
                 "muéstrame", "busca un", "encuentra un", "propon", "recomiend",
                 "recomend", "sugiere", "pasame", "pásame", "quiero ver",
                 "algun", "algún", "algo de"}) and not (
            find_name(lo) and _has(lo, {"propiedades", "propiedad", "calcula",
                                         "peso", "mw", "logp", "tpsa"})):
        if _has(lo, {"variante", "variacion", "variación", "análogo",
                     "analogo", "derivado", "version", "versión"}):
            base_name = find_name(lo)
            base_smiles = KNOWN_SMILES.get(base_name, "") if base_name else ""
            return Intent("suggest", smiles=base_smiles or None, target=None,
                          tool="suggest_smiles",
                          smiles_source="name" if base_name else None,
                          suggest_mode="variant", suggest_target=base_name or "")
        if _has(lo, {"para", "contra", "target", "receptor", "proteina",
                     "proteína", "enzima"}):
            pdb = _extract_pdb(msg)
            return Intent("suggest", smiles=None, target=pdb or None,
                          tool="suggest_smiles", smiles_source=None,
                          suggest_mode="for_target", suggest_target=msg)
        return Intent("suggest", smiles=None, target=None,
                      tool="suggest_smiles", smiles_source=None,
                      suggest_mode="interesting")

    # Session ranking before compare: superlative without 2 names is rank.
    if _has(lo, {"menor", "mayor", "más lipofílica", "mas lipofilica",
                 "más lipofilica", "menos lipofílica", "cuál es la más",
                 "cual es la mas", "cuál es el más", "cual es el mas",
                 "más pesada", "mas pesada", "más liviana", "mas liviana",
                 "ranking", "ordenar"}):
        if _has(lo, {"peso", "masa", "molecular", "lipofil", "logp", "tpsa",
                     "afinidad", "score", "pesada", "liviana", "ranking",
                     "ordenar", "grande", "chica", "pequeñ"}):
            if _find_compare_names(msg) is None:
                return Intent("rank_session", tool="rank_session_molecules")

    # Comparison: 2 names (or N>=3 list).
    if _COMPARE_RE.search(lo):
        all_names = find_all_names(msg)
        if all_names and len(all_names) >= 3:
            smiles_list = [KNOWN_SMILES[n] for n in all_names]
            return Intent("compare", smiles=smiles_list[0],
                          smiles_b=smiles_list[1], smiles_list=smiles_list,
                          tool="compare_molecules", smiles_source="name")
        names = _find_compare_names(msg)
        if names:
            name_a, name_b = names
            smiles_a = KNOWN_SMILES.get(name_a, name_a)
            smiles_b = KNOWN_SMILES.get(name_b, name_b) if name_b in KNOWN_SMILES else name_b
            return Intent("compare", smiles=smiles_a, smiles_b=smiles_b,
                          tool="compare_molecules",
                          smiles_source="name" if name_a in KNOWN_SMILES else "explicit")
        return Intent("conceptual", tool=None)

    # Known molecule name.
    name = find_name(lo)
    if name:
        resolved = KNOWN_SMILES.get(name, "")
        if resolved:
            if _has(lo, _DOCKING):
                pdb = _extract_pdb(msg) or _pdb_suelto(msg)
                return Intent("docking", smiles=resolved, target=pdb,
                              tool="run_docking", smiles_source="name")
            if _has(lo, _ANALOG):
                return Intent("analog", smiles=resolved, target=None,
                              tool="molgraph_similar", smiles_source="name")
            if _has(lo, _DRUGLIKENESS):
                return Intent("druglikeness", smiles=resolved, target=None,
                              tool="check_druglikeness", smiles_source="name")
            return Intent("chemical", smiles=resolved, target=None,
                          tool="compute_properties", smiles_source="name")
        return Intent("chemical", smiles=None, target=None,
                      tool="compute_properties", smiles_source=None)

    # MolGraph: evaluated molecules against a target or by score.
    if _has(lo, {"moleculas", "moléculas", "busca", "top", "mejores", "activas"}):
        if _has(lo, {"contra", "target", "receptor", "enzima", "proteina",
                     "proteína", "score", "afinidad", "activas", "evaluadas",
                     "top"}):
            return Intent("molgraph", target=None, tool="query_molgraph")

    # Persisted history questions.
    if _has(lo, {"historial", "evalué", "evaluaciones", "evaluadas",
                 "registradas", "mis moléculas", "mis moleculas", "ya evalué",
                 "probé", "probe", "que moleculas tengo"}):
        return Intent("query_history", tool="query_history")

    # Persisted evaluation details (poses, RMSD, ADME score...).
    if _has(lo, {"pose", "poses", "rmsd", "distancia", "distancias",
                 "coordenadas", "adme", "residuos", "hotspot", "hotspots",
                 "vina", "comando", "timestamp", "desglosa", "desglose",
                 "mejor pose", "pose 1", "pose principal",
                 "ultima evaluacion", "última evaluación"}):
        return Intent("evaluation", tool="query_evaluation_details")

    # Anaphora (second pass, after the history block).
    if _ANA_RE.search(lo):
        return Intent("recall_anaphoric", tool=None)

    # Conceptual (fix vs internal: "qué son" also asks for a definition;
    # internal routes "que son los SMILES?" to invalid_smiles).
    if _has(lo, {"qué es", "que es", "qué son", "que son", "explica", "define",
                 "diferencia", "para qué", "para que sirve"}):
        return Intent("conceptual", tool=None)

    # Invalid SMILES-like token.
    candidate = _find_possible_smiles(msg)
    if candidate and not smiles_plausible(candidate):
        return Intent("invalid_smiles", tool=None)

    # Molecular recall.
    if _has(lo, {"recordas", "recordás", "recuerdas", "recordar"}):
        return Intent("recall_molecular", tool=None)

    return Intent("unknown", tool=None)
