"""
services/ai/intent_classifier.py

Clasificador determinista de intent del usuario.
NO USA LLM. Árbol de reglas regex + keyword.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# ── Known molecules (name → SMILES) ──────────────────────────────────
# Single source of truth: services/ai/known_molecules.py. Import ONLY the
# subset with real SMILES values (drops PEPTIDE:/MACROLIDE:/etc. markers).
# This replaces the old local hardcoded ~25-name dict that caused
# "propiedades de nicotina" to fall through to the LLM.
from services.ai.known_molecules import KNOWN_SMILES as KNOWN
from services.ai.known_molecules import SMILES_ONLY_NAMES as _KNOWN_SMILES_NAMES  # noqa: F401


@dataclass
class Intent:
    name: str
    smiles: str | None = None
    target: str | None = None
    tool: str | None = None
    # Segundo SMILES — usado por compare_molecules ("compará A con B").
    # El clasificador resuelve AMBOS nombres cuando detecta comparación.
    smiles_b: str | None = None
    # Comparación N-moléculas ("compará A, B y C") — lista de SMILES en orden
    # de aparición. Para N >= 3 el clasificador llena esto en vez de
    # smiles/smiles_b; el chat_service ejecuta compute_properties por cada una
    # y construye la tabla comparativa.
    smiles_list: list[str] | None = None
    # Sugerir moléculas (F7): modo y target para la tool suggest_smiles.
    #   suggest_mode: "interesting" | "for_target" | "variant"
    #   suggest_target: texto crudo con el receptor/variante a resolver
    suggest_mode: str | None = None
    suggest_target: str | None = None
    # Origen del SMILES — control de privacidad para web enrichment:
    #   "explicit":         el SMILES estaba explícito en el texto del user (safe web)
    #   "name":             se resolvió desde un nombre conocido en el texto (safe web, by name)
    #   "anaphora_name":    anáfora con nombre ("y del paracetamol?") — safe web, by name
    #   "anaphora_context":  anáfora sin nombre, SMILES desde molecule_context — ASK permiso
    #   None:                no SMILES (conceptual, invalid, recall_molecular, etc.)
    smiles_source: str | None = None


# ── Regex ────────────────────────────────────────────────────────────

_PDB_RE = re.compile(
    r'(?:contra|target|receptor|prote[íi]na|enzima)\s+'
    r'(?:la\s+(?:prote[íi]na|enzima|receptor)\s+)?'
    r'(\d[0-9A-Za-z\-]{2,})',
    re.I,
)

# SMILES — tokens consecutivos con caracteres del alfabeto SMILES + 6+ chars
_SMILES_RE = re.compile(r'\b([A-Z][A-Za-z0-9\r\(\)\[\]@=#+\\/.\-\%]{1,})')

_ANA_RE = re.compile(
    r'(?:'
    r'esa\s+(?:primera|segunda|otra)\s+mol[ée]cula'    # "esa primera molécula"
    r'|y\s+del?\s+\w+\?'                                # "y del paracetamol?" / "y de la X?"
    r'|y\s+de\s+la\s+\w+\?'                             # "y de la morfina?"
    r')',
    re.I,
)

# Comparación: "compará la aspirina con el ibuprofeno", "compara A vs B",
# "diferencia entre aspirina e ibuprofeno", "cuál es mejor, A o B",
# "qué molécula tiene mayor peso molecular, A o B", "cuál pesa más, A o B".
_COMPARE_RE = re.compile(
    r'(?:'
    r'compar[áa]|compara|comp[áa]r[áa]?me|comparaci[óo]n|vs\.?|versus|'
    r'diferencia[s]?\s+entre|'
    r'cu[aá]l\s+es\s+(?:mejor|m[áa]s|mayor|menor)|'      # "cuál es más/mayor..."
    r'(?:mayor|menor|m[áa]s)\s+(?:peso|masa|afinidad)|'  # "mayor peso molecular"
    r'pes[ao]\s+m[áa]s|pesa\s+m[áa]s|m[áa]s\s+pesad[oa]|m[áa]s\s+livian[oa]'  # "pesa más / más pesado"
    r')',
    re.I,
)

# Conectores entre los dos términos de una comparación.
_COMPARE_SEP_RE = re.compile(
    r'\s+(?:con|y|vs\.?|versus|o|contra|entre)\s+',
    re.I,
)


def _find_compare_names(text: str) -> tuple[str, str] | None:
    """Extraer DOS nombres de molécula conocidos de un texto de comparación,
    respetando el ORDEN DE APARICIÓN en el texto.
    Ej: "compará la aspirina con el ibuprofeno" → ("aspirina", "ibuprofeno").
    Devuelve None si no encuentra al menos 2 nombres distintos.
    """
    names = _find_all_names(text)
    if names is None:
        return None
    if len(names) >= 2:
        return names[0], names[1]
    # Fallback: un solo nombre + un SMILES explícito en el texto
    s = _extract_smiles(text)
    if len(names) == 1 and s:
        return names[0], s
    return None


def _find_all_names(text: str) -> list[str] | None:
    """Extraer TODOS los nombres de molécula conocidos de un texto, en orden
    de aparición.

    Ej: "compará la aspirina con el ibuprofeno y el paracetamol" →
    ["aspirina", "ibuprofeno", "paracetamol"]. Devuelve None si no hay al
    menos 2 nombres distintos.
    """
    from services.ai.known_molecules import normalize_name as _norm_name
    lo = _norm_name(text)
    # Orden de aparición: buscar cada nombre con find() y ordenar por posición.
    found = []
    for name in KNOWN:
        pos = lo.find(name)
        if pos >= 0 and name not in [f[0] for f in found]:
            found.append((pos, name))
    if len(found) >= 2:
        found.sort(key=lambda x: x[0])
        return [f[1] for f in found]
    return None


def _resolve_name_list(names: list[str]) -> list[str]:
    """Mapear lista de nombres a sus SMILES (conocidos o el nombre crudo)."""
    return [KNOWN.get(n, n) for n in names]


# ═══════════════════════════════════════════════════════════════
# Classifier
# ═══════════════════════════════════════════════════════════════

def classify(msg: str) -> Intent:
    """Único punto de entrada: clasificar el intent del mensaje."""
    lo = msg.lower()

    # ── N1: SMILES explícito en el mensaje ──
    s = _extract_smiles(msg)
    if s:
        if _has(lo, {"afinidad", "docking"}):
            pdb = _extract_pdb(msg)
            return Intent("docking", smiles=s, target=pdb, tool="run_docking", smiles_source="explicit")
        if _has(lo, {"similares", "análogos", "análogo"}):
            return Intent("analog", smiles=s, target=None, tool="molgraph_similar", smiles_source="explicit")
        return Intent("chemical", smiles=s, target=None, tool="compute_properties", smiles_source="explicit")

    # ── Anáfora (ANTES que nombre conocido — "y del paracetamol?" es recall) ──
    if _ANA_RE.search(lo):
        return Intent("recall_anaphoric", tool=None, smiles_source=None)

    # ── DISEÑO MOLECULAR ESPECÍFICO (F11): "Dame el SMILES de un análogo de
    # penicilina CON un anillo oxazolidinona fusionado y UN PUENTE tioéter
    # entre C3 y C7" → es un pedido de DISEÑO con requisitos estructurales
    # complejos, NO una "variante" exploratoria. El sistema no puede generarlo
    # con precisión → el guard F5 (chat_service._verify_smiles_claims) responde
    # honesto. Si esto cayera a suggest_smiles variant, BRICS diría "no pude"
    # y el usuario ve un mensaje feo (bug del testing). ──
    if _has(lo, {"smiles", "molécula", "molecula", "estructura", "análogo", "analogo",
                 "derivado", "compuesto"}) and _has(lo, {
        "con un", "con una", "fusionad", "fusionado", "puente", "tioeter",
        "tioéter", "anillo", "anillos", "entre c", "entre el c", "c3", "c7",
        "c2", "c5", "sustituyente", "grupo", "funcional", "residuo",
        "glicina", "cisteina", "cisteína", "oxazolidinona", "betalactamico",
        "beta-lactamico", "beta-lactámico", "peptido ciclico", "péptido cíclico",
    }):
        return Intent("design", tool=None, smiles_source=None)

    # ── FUENTE VERIFICADA (F12): "cita la fuente de los valores ADME",
    # "de dónde sale ese LogP", "dame el DOI/URL de la fuente" → tool web
    # query_verified_source (PubChem/ChEMBL reales con URL). Va ANTES de
    # evaluation/chemical para que "cita la fuente del ADME" no caiga a
    # query_evaluation_details y "de dónde sale ese LogP" no caiga a
    # compute_properties (el usuario pide la FUENTE, no recalcular). ──
    if (_has(lo, {
        "fuente", "fuentes", "doi", "url", "cita", "citar", "de donde",
        "de dónde", "sale ese", "sale el", "origen", "referencia",
        "referencias", "articulo", "artículo", "bibliografia", "bibliografía",
        "source", "verified", "verificada", "verificado",
    }) and _find_name(lo)) or (
        _has(lo, {"fuente", "doi", "url", "cita", "de donde", "de dónde"})
        and _has(lo, {"adme", "logp", "log p", "mw", "peso", "tpsa", "biodisponibilidad"})
    ):
        return Intent("source", tool="query_verified_source", smiles_source=None)

    # ── SUGERIR MOLÉCULAS (F7): "dame un smiles interesante" / "dame un
    # smiles para X receptor" / "dame una variante de X" → tool suggest_smiles
    # (cruza con MolGraph, selección aleatoria — nunca repite). ──
    # Va ANTES del bloque de nombre conocido para que "dame una variante de
    # la aspirina" no caiga a compute_properties.
    if _has(lo, {"dame", "da me", "quiero un", "necesito un", "suger", "sugerime",
                 "sugerime una", "sugerime un", "muestrame", "muéstrame",
                 "busca un", "encuentra un", "propon", "recomiend", "recomend",
                 "recomiendame", "recomienda", "recomendame un", "sugiere",
                 "sugerime algo", "pasa un", "pasame", "pásame", "quiero ver",
                 "algun", "algún", "algo de"}):
        # "variante de X" / "variaciones de X" / "análogo de X" — PRIMERO,
        # para que "dame una variante de la aspirina" no caiga a interesting.
        if _has(lo, {"variante", "variacion", "variación", "análogo", "analogo",
                     "derivado", "version", "versión"}):
            base_name = _find_name(lo)
            base_smiles = KNOWN.get(base_name, "") if base_name else ""
            return Intent(
                "suggest", smiles=base_smiles or None,
                target=None, tool="suggest_smiles",
                smiles_source="name" if base_name else None,
                suggest_mode="variant",
                suggest_target=base_name or "",
            )
        # "para X receptor" / "contra X" → for_target
        if _has(lo, {"para", "contra", "target", "receptor", "proteina", "proteína",
                     "enzima"}):
            pdb = _extract_pdb(msg)
            return Intent(
                "suggest", smiles=None,
                target=pdb or None, tool="suggest_smiles",
                smiles_source=None,
                suggest_mode="for_target",
                suggest_target=msg,  # el chat_service resuelve nombre→PDB
            )
        # "interesante" / adjetivos de curiosidad / recomendación general →
        # interesting (recomendación del grafo, aleatoria). "recomiendame un
        # smiles" / "sugiere algo" / "dame un smiles" SIN más contexto caen aquí.
        return Intent(
            "suggest", smiles=None,
            target=None, tool="suggest_smiles",
            smiles_source=None,
            suggest_mode="interesting",
        )

    # ── RANKING DE SESIÓN: "cuál tiene menor/mayor X" (sin nombres → las de
    # la conversación actual). Va ANTES del compare: "cuál tiene mayor peso
    # molecular?" matchea _COMPARE_RE pero sin 2 nombres → rank determinista.
    if _has(lo, {"menor", "mayor", "más lipofílica", "mas lipofilica",
                 "más lipofilica", "menos lipofílica",
                 "cuál es la más", "cual es la mas", "cuál es el más",
                 "cual es el mas", "más pesada", "mas pesada", "más liviana",
                 "mas liviana", "ranking", "ordenar"}):
        if _has(lo, {"peso", "masa", "molecular", "lipofil", "logp", "tpsa",
                     "afinidad", "score", "pesada", "liviana", "ranking",
                     "ordenar", "grande", "chica", "pequeñ"}):
            # Si hay 2+ nombres conocidos → es comparación explícita (compare).
            # Si no → ranking determinista de la conversación actual.
            names = _find_compare_names(msg)
            if names is None:
                return Intent("rank_session", tool="rank_session_molecules")
            # 2 nombres: cae al compare de abajo

    # ── COMPARACIÓN: "compará A con B" / "compará A, B y C" ──
    if _COMPARE_RE.search(lo):
        all_names = _find_all_names(msg)
        if all_names and len(all_names) >= 3:
            # Comparación N-moléculas ("compárame amlodipino, nifedipino y
            # felodipino") → el chat_service ejecuta compute_properties por
            # cada una y arma la tabla comparativa.
            smiles_list = _resolve_name_list(all_names)
            return Intent(
                "compare", smiles=smiles_list[0], smiles_b=smiles_list[1],
                smiles_list=smiles_list,
                tool="compare_molecules",
                smiles_source="name",
            )
        names = _find_compare_names(msg)
        if names:
            s_a, s_b = names
            # Si el segundo es un SMILES, queda como está; si es nombre, resolver.
            sa = KNOWN.get(s_a, s_a)
            sb = KNOWN.get(s_b, s_b) if s_b in KNOWN else s_b
            return Intent(
                "compare", smiles=sa, smiles_b=sb,
                tool="compare_molecules",
                smiles_source="name" if s_a in KNOWN else "explicit",
            )
        # Comparación sin 2 nombres → dejar que el modelo la maneje (conceptual)
        return Intent("conceptual", tool=None)

    # ── Nombre de molécula ──
    name = _find_name(lo)
    if name:
        s = KNOWN.get(name, "")
        if not s:
            # try english fallback
            en = _name_in_english(name)
            s = KNOWN.get(en, "")
        if s:
            if _has(lo, {"afinidad", "docking"}):
                pdb = _extract_pdb(msg)
                return Intent("docking", smiles=s, target=pdb, tool="run_docking", smiles_source="name")
            if _has(lo, {"similares", "análogos"}):
                return Intent("analog", smiles=s, target=None, tool="molgraph_similar", smiles_source="name")
            return Intent("chemical", smiles=s, target=None, tool="compute_properties", smiles_source="name")
        # name found but no SMILES
        if _has(lo, {"calcula", "propiedades"}):
            return Intent("chemical", smiles=None, target=None, tool="compute_properties", smiles_source=None)
        if _has(lo, {"afinidad", "docking"}):
            pdb = _extract_pdb(msg)
            if pdb:
                return Intent("docking", smiles=None, target=pdb, tool=None, smiles_source=None)
            return Intent("docking_missing", target=pdb, tool=None, smiles_source=None)
        return Intent("chemical", smiles=None, target=None, tool="compute_properties", smiles_source=None)

    # ── MOLGRAPH: buscar moléculas evaluadas contra un target o por score ──
    # "que moleculas hay contra 5-HT1A?", "top 5 moleculas por score",
    # "busca moleculas activas contra CDK2"
    if _has(lo, {"moleculas", "moléculas", "busca", "top", "mejores", "activas"}):
        if _has(lo, {"contra", "target", "receptor", "enzima", "proteina", "proteína",
                     "score", "afinidad", "activas", "evaluadas", "top"}):
            return Intent("molgraph", target=None, tool="query_molgraph")

    # ── HISTORIAL: "qué evalué contra X", "mejores scores del historial" ──
    if _has(lo, {"historial", "evalué", "evaluaciones", "evaluadas", "registradas",
                 "mis moléculas", "mis moleculas", "ya evalué", "probé", "probe",
                 "que moleculas tengo"}):
        return Intent("query_history", tool="query_history")

    # ── EVALUACIÓN DETALLADA (F10): preguntas sobre los datos REALES de una
    # evaluación persistida: poses, RMSD, distancias, ADME score, residuos
    # críticos/hotspots, comando/versión Vina, timestamp. El LLM NO tiene estos
    # datos — la tool query_evaluation_details los lee de la DB. ──
    if _has(lo, {
        "pose", "poses", "rmsd", "distancia", "distancias", "angstrom", "Å",
        "coordenadas", "xyz", "adme", "score adme", "residuos", "hotspot",
        "hotspots", "residuos criticos", "vina", "comando", "timestamp",
        "timestamps", "versiones", "sospechos", "ultima evaluacion",
        "última evaluación", "la ultima", "la última", "desglosa", "desglose", "subcomponentes",
        "formula de agregacion", "fórmula de agregación", "mejor pose",
        "pose 1", "pose 2", "pose principal", "inconsistencias de unidades",
    }):
        # Evitar conflicto: "dame el comando exacto" de otra cosa, o "historial"
        # ya capturado arriba. Si menciona una molécula nueva para evaluar,
        # no es esto (eso va a docking). Aquí buscamos EVALUACIÓN YA HECHA.
        return Intent("evaluation", tool="query_evaluation_details")

    # ── Anáfora ──
    if _ANA_RE.search(lo):
        return Intent("recall_anaphoric", tool=None)

    # ── Conceptual ──
    if _has(lo, {"qué es", "que es", "explica", "define", "diferencia", "para qué", "para que sirve"}):
        return Intent("conceptual", tool=None)

    # ── INVALID SMILES ──
    cand = _find_possible_smiles(msg)
    if cand and not _valid_smiles(cand):
        return Intent("invalid_smiles", tool=None)

    # ── Recall ──
    if _has(lo, {"recordas", "recordás", "recuerdas", "recordar"}):
        return Intent("recall_molecular", tool=None)

    return Intent("unknown", tool=None)


# ═══════════════════════════════ helpers ═══════════════════════════

def _has(lo: str, kw: set[str]) -> bool:
    return any(k.lower() in lo for k in kw)


def _find_name(text: str) -> str | None:
    """Find known molecule name in text (accent-insensitive)."""
    from services.ai.known_molecules import normalize_name as _norm_name
    lo = _norm_name(text)
    for name in sorted(KNOWN, key=len, reverse=True):
        if name in lo:
            return name
    return None


def _name_in_english(es_name: str) -> str:
    """Spanish name -> English INN via the unified ES_TO_EN table."""
    from services.ai.known_molecules import get_english_name
    return get_english_name(es_name) or es_name


def _extract_pdb(text: str) -> str:
    m = _PDB_RE.search(text)
    return m.group(1).strip() if m else ""


def _extract_smiles(text: str) -> str | None:
    """Detect SMILES in text, validate with RDKit, return canonical."""
    # Silenciar logs de RDKit
    try:
        from rdkit import RDLogger
        RDLogger.DisableLog("rdApp.*")
    except ImportError:
        pass

    for m in _SMILES_RE.finditer(text):
        cand = m.group(1)
        if len(cand) >= 3:
            ok, canon, _ = _validate_smiles(cand)
            if ok:
                return canon
    return None


def _find_possible_smiles(text: str) -> str | None:
    """Find any token that looks like a SMILES string (for invalid detection)."""
    for m in _SMILES_RE.finditer(text):
        cand = m.group(1)
        if len(cand) >= 3:
            return cand
    return None


def _validate_smiles(smiles: str) -> tuple[bool, str, str]:
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(smiles)
        if mol:
            canon = Chem.MolToSmiles(mol, canonical=True)
            return True, canon, ""
        return False, "", "RDKit:"
    except ImportError:
        return True, smiles, ""
    except Exception as e:
        return False, "", str(e)


def _valid_smiles(s: str) -> bool:
    ok, _, _ = _validate_smiles(s)
    return ok
