"""
services/ai/name_resolver.py

Centralized name -> canonical SMILES resolution for MolChat.

Purpose
-------
This orchestrator centralizes molecule-name resolution so MolChat stops
falling through to the LLM "proso" (conceptual) pipeline for molecules that
are actually resolvable deterministically. When the user asks for the
"properties of nicotine" or "properties of dapagliflozin" (in Spanish or
English, with or without accents), this module resolves the name to a
canonical SMILES so the factual pipeline (compute_properties via
tool_registry) can answer with verified data, bypassing the LLM entirely.

Privacy contract (STRICT)
-------------------------
PubChem is a remote, third-party service (NCBI/NIH). It is queried ONLY when
BOTH of the following hold:
    1. `allow_web=True` was explicitly passed by the caller (the frontend
       "online/offline" toggle already exists; offline is the default).
    2. The two prior LOCAL resolution steps (in-memory dict lookup and
       MolGraph FTS5) both failed to resolve the name.

Offline users never leak molecule names to the network unless they explicitly
opt in. The dict (step 1) and MolGraph FTS5 (step 2) are pure local lookups
and run unconditionally.

Resolution chain (early return on first success)
-----------------------------------------------
    1. Normalize & dict lookup      (known_molecules.get_smiles_by_name)
    2. Exact match in MolGraph FTS5  (molgraph_fts MATCH, JOIN mol_nodes for smiles)
    3. PubChem-by-name REST          (only if allow_web=True) -> asyncio.to_thread
    4. Fuzzy match against known_molecules.ALL_NAMES (difflib, cutoff=0.8)
    5. No resolution -> structured failure with user-facing hint

Caching policy
---------------
    - Step 1 (dict):       no cache   (microseconds)
    - Step 2 (molgraph):   no cache   (sub-millisecond SQLite query)
    - Step 3 (PubChem):    reuses services.ai.tools.web_tools._pubchem_conn
                           schema: cache(smiles TEXT PRIMARY KEY, data_json TEXT, fetched_at REAL)
                           TTL ~30 days (86400 * 30 seconds)
    - Step 4 (fuzzy):      no cache   (cheap in-memory)

Integration
-----------
A successful ResolutionResult (smiles is not None) lets chat_service /
deterministic_responder route the turn through compute_properties
(tool_registry), producing verified physicochemical data instead of asking
the local Qwen LLM to write a conceptual answer.

TODO: when MolGraph supports a `mol_nodes.name_normalized` column, replace
the FTS5 manual translation trick (es -> en via known_molecules.ES_TO_EN)
with a direct normalized-name equality lookup. For now we query FTS5 with
both the normalized name and its English INN translation to cover bilingual
input.
"""

from __future__ import annotations

import asyncio
import re
import sqlite3
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

# ---------------------------------------------------------------------------
# Optional sibling-worker imports (these files may not exist yet when this
# module is first dropped into the tree; their authors are building them in
# parallel). We import defensively so this module loads even before the
# siblings land, degrading gracefully to "no dict / no translation available".
# ---------------------------------------------------------------------------

# known_molecules.py — sibling worker. Provides:
#   KNOWN_MOLECULES: dict[str, str]   lowercased/no-accent name -> canonical SMILES
#   ES_TO_EN: dict[str, str]          lowercased/no-accent Spanish name -> English INN
#   ALL_NAMES: list[str]              all known names (for fuzzy matching)
#   normalize_name(s) -> str          lowercase + strip accents + whitespace
#   get_smiles_by_name(name) -> str | None
#   get_english_name(name) -> str | None
#   is_known_molecule(name) -> bool
try:
    from services.ai.known_molecules import (
        ALL_NAMES,
        get_english_name,
        get_smiles_by_name,
        normalize_name,
    )
    _HAS_KNOWN_MOLECULES = True
except Exception:  # ImportError or, if the module exists but is mid-edit, AttributeError
    _HAS_KNOWN_MOLECULES = False
    ALL_NAMES = []  # type: ignore[assignment]

    def normalize_name(s: str) -> str:  # minimal local fallback
        import unicodedata
        if s is None:
            return ""
        nf = unicodedata.normalize("NFKD", s)
        stripped = "".join(ch for ch in nf if not unicodedata.combining(ch))
        return stripped.lower().strip()

    def get_smiles_by_name(name: str):  # type: ignore[no-redef]
        return None

    def get_english_name(name: str):  # type: ignore[no-redef]
        return None

# web_tools.py — existing. We reuse:
#   _pubchem_conn()   -> sqlite3.Connection   (cache schema: smiles PK, data_json, fetched_at)
#   _http_get_json(url, timeout) -> dict | None
# These are "private" helpers but are the canonical PubChem access path in
# this codebase; reusing them keeps a single HTTP/cache path and avoids a
# second pubchem_cache.db being created elsewhere.
try:
    from services.ai.tools.web_tools import _http_get_json, _pubchem_conn
    _HAS_WEB_TOOLS = True
except Exception:
    _HAS_WEB_TOOLS = False
    _pubchem_conn = None  # type: ignore[assignment]
    _http_get_json = None  # type: ignore[assignment]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_MOLGRAPH_DB = Path.home() / "MolDesign" / "data" / "molgraph.db"

_PUBCHEM_TTL_SECONDS = 86400 * 30  # ~30 days

# PubChem name -> CanonicalSMILES + light props endpoint. We request the same
# light fields web_tools.pubchem_lookup requests, plus CanonicalSMILES so we
# can persist a verified canonical form in the cache.
_PUBCHEM_NAME_URL = (
    "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{name}"
    "/property/MolecularWeight,XLogP,CanonicalSMILES/JSON"
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResolutionResult:
    """Outcome of resolving a user-typed molecule name.

    Fields
    ------
    smiles : str | None
        Canonical SMILES if resolved, None if not.
    source : str
        One of: "dict" | "molgraph_fts" | "pubchem" | "fuzzy" | "failed".
    english_name : str | None
        The English name actually sent to PubChem (if step 3 ran). Useful for
        debugging/audit of the es->en translation path. None if PubChem was
        never consulted (offline or earlier step already resolved).
    matched_dict_name : str | None
        For source="dict": the dict key that matched. For source="fuzzy": the
        fuzzy-corrected name that was then resolved via the dict. None when
        resolution did not go through the dict.
    error_hint : str | None
        User-facing suggestion when smiles is None. None when smiles resolved.
    """

    smiles: str | None
    source: str
    english_name: str | None
    matched_dict_name: str | None
    error_hint: str | None


# ---------------------------------------------------------------------------
# Helpers (local, pure)
# ---------------------------------------------------------------------------

def _normalize_for_fts(name: str) -> str:
    """Build a safe FTS5 MATCH expression for an exact-ish name query.

    FTS5 treats several characters as operators (double-quote, asterisk, etc.).
    We strip those and quote the term so a phrase like "D-GLUCOSE" is treated
    as a single literal token rather than an expression. Returns the empty
    string if nothing usable remains.
    """
    if not name:
        return ""
    cleaned = "".join(
        ch for ch in name
        if ch.isalnum() or ch.isspace() or ch in "-_"
    ).strip()
    if not cleaned:
        return ""
    # Wrap in double quotes; escape any internal double-quote by doubling per FTS5.
    inner = cleaned.replace('"', '""')
    return f'"{inner}"'


def _query_molgraph_fts(
    normalized_name: str,
    english_name: str | None,
    db_path: Path,
) -> tuple[str, str] | None:
    """Exact-ish FTS5 lookup in MolGraph.

    The real MolGraph schema is:
        molgraph_fts(node_id UNINDEXED, name, type, properties_text)
    and the SMILES lives in mol_nodes.smiles (NOT in the FTS table). So we
    query molgraph_fts with a phrase MATCH on `name` only, then JOIN mol_nodes
    by node_id to recover the SMILES.

    We try two MATCH terms in order and return the first that yields a row
    with a non-empty smiles:
        1. the normalized user name (covers English INN + many Spanish names
           that MolGraph already stores verbatim)
        2. the English INN translation (covers Spanish-only input that MolGraph
           only indexed under the English name)

    Returns (node_id, smiles) on success, None if nothing matched / DB missing.
    """
    if db_path is None or not Path(db_path).exists():
        return None

    candidates = [normalized_name]
    if english_name and english_name != normalized_name:
        candidates.append(english_name)

    try:
        conn = sqlite3.connect(str(db_path), timeout=2.0)
    except sqlite3.Error:
        return None

    try:
        for raw in candidates:
            expr = _normalize_for_fts(raw)
            if not expr:
                continue
            try:
                row = conn.execute(
                    "SELECT f.node_id, n.smiles "
                    "FROM molgraph_fts f "
                    "JOIN mol_nodes n ON n.id = f.node_id "
                    "WHERE molgraph_fts MATCH ? "
                    "  AND n.smiles IS NOT NULL AND n.smiles != '' "
                    "ORDER BY rank LIMIT 1",
                    (expr,),
                ).fetchone()
            except sqlite3.OperationalError:
                # FTS5 syntax error on this term — try next candidate.
                continue
            if row and row[1]:
                return row[0], row[1]
    finally:
        conn.close()
    return None


def _pubchem_name_to_smiles(name: str, timeout_seconds: float) -> str | None:
    """Synchronous PubChem name->SMILES lookup. Runs inside a worker thread.

    Returns the CanonicalSMILES on success, None on any failure (HTTP error,
    timeout, no result, missing CanonicalSMILES field). NEVER raises — the
    caller relies on None to continue the fallback chain.
    """
    if not _HAS_WEB_TOOLS:
        return None
    if not name:
        return None
    enc = urllib.parse.quote(name, safe="")
    url = _PUBCHEM_NAME_URL.format(name=enc)
    # _http_get_json already swallows all exceptions and returns None on failure.
    data = _http_get_json(url, timeout=timeout_seconds)  # type: ignore[misc]
    if not data:
        return None
    try:
        props = (data.get("PropertyTable") or {}).get("Properties") or []
    except AttributeError:
        return None
    if not props or not isinstance(props, list):
        return None
    smiles = props[0].get("CanonicalSMILES") if isinstance(props[0], dict) else None
    if not smiles or not isinstance(smiles, str):
        return None
    return smiles


def _cache_pubchem_result(smiles: str, data_json_blob: str, fetched_at: float) -> None:
    """Persist a successful PubChem resolve into the shared pubchem_cache.db.

    We INSERT OR REPLACE keyed by the freshly resolved canonical SMILES (the
    cache's natural key), storing a compact JSON blob with the name we used
    and the light props we got back. Subsequent resolves of the same molecule
    under any name can short-circuit later by hitting this cache in step 3
    before re-querying PubChem.

    Failure to write the cache is non-fatal; we swallow sqlite errors so the
    resolution still returns the SMILES upstream.
    """
    if not _HAS_WEB_TOOLS or _pubchem_conn is None or not smiles:
        return
    try:
        conn = _pubchem_conn()  # type: ignore[misc]
        try:
            conn.execute(
                "INSERT OR REPLACE INTO cache(smiles, data_json, fetched_at) "
                "VALUES(?,?,?)",
                (smiles, data_json_blob, fetched_at),
            )
            conn.commit()
        finally:
            conn.close()
    except sqlite3.Error:
        pass


def _pubchem_cached_smiles_for(name: str) -> str | None:
    """Check the shared pubchem_cache.db for a previously resolved SMILES.

    The cache is keyed by SMILES, not by name — so a name-based cache hit is
    only possible if we previously stored a name hint inside data_json. We do
    a cheap LIKE scan over data_json to find a cached entry whose stored name
    matches (case-insensitive). This is intentionally best-effort: a miss here
    simply falls through to the live PubChem query.
    """
    if not _HAS_WEB_TOOLS or _pubchem_conn is None or not name:
        return None
    try:
        conn = _pubchem_conn()  # type: ignore[misc]
        try:
            row = conn.execute(
                "SELECT smiles, fetched_at FROM cache "
                "WHERE data_json LIKE ? LIMIT 1",
                (f'%"name": "%{name}%"%',),
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        return None
    if not row or not row[0]:
        return None
    fetched_at = row[1] or 0.0
    if (time.time() - fetched_at) > _PUBCHEM_TTL_SECONDS:
        return None
    return row[0]


def _fuzzy_resolve(normalized_name: str) -> str | None:
    """Fuzzy-match `normalized_name` against known_molecules.ALL_NAMES.

    Public so the exact match dict is the single source of truth: a fuzzy hit
    returns the corrected name, which the caller then looks up via the dict
    (single canonicalization path, no second SMILES table to drift).

    cutoff=0.8 is intentional. Measured tradeoff:
        "dapaglifocina"  vs "dapagliflozina" -> ratio ~0.93  (MATCH, desired)
        "aspirina"       vs "asparagina"     -> ratio ~0.79  (NO match, desired)

    Above 0.8 we keep the strong typo correction for real drug names while
    rejecting same-length near-collisions like aspirina/asparagina that would
    silently substitute one drug for another. Lower the cutoff and you start
    mis-resolving; raise it and you lose the typo-tolerance that is the whole
    point of this step.
    """
    if not _HAS_KNOWN_MOLECULES or not ALL_NAMES or not normalized_name:
        return None
    # `difflib.get_close_matches` is case-sensitive; ALL_NAMES is stored
    # lowercased/no-accent by the sibling worker contract, and our input is
    # already normalized the same way, so this is consistent.
    import difflib
    matches = difflib.get_close_matches(
        normalized_name, ALL_NAMES, n=1, cutoff=0.8,
    )
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# Candidate extraction: resolve_molecule_name accepts a full user message
# ("propiedades de nicotina", "dame las propiedades de dapaglifocina"), not
# just a bare name. We generate candidate names and run the resolution chain
# against each one, in priority order.
# ---------------------------------------------------------------------------

# Words that describe the intent, never a molecule name. Filtered from token
# candidates so we do not waste PubChem calls (or worse, fuzzy-resolve "peso"
# into an unrelated drug) on function words.
_INTENT_STOPWORDS = frozenset({
    "propiedades", "calcula", "calcular", "dame", "quiero", "necesito",
    "obten", "obtener", "muestrame", "muéstrame", "muestra", "ver", "para",
    "sus", "cuales", "cual", "cuanto", "cuánto", "peso", "molecular", "masa",
    "afinidad", "logp", "tpsa", "lipinski", "veber", "admet", "score",
    "molecula", "molécula", "compuesto", "quimico", "químico", "medicamento",
})

# "propiedades de X", "calcula las propiedades de X", "dame la de X" ...
_PROPOSITION_DE_RE = re.compile(
    r"(?:^|\s)(?:de|del|para)\s+(?:la\s+|el\s+|las\s+|los\s+|sus\s+)?(.+?)\s*$",
    re.IGNORECASE,
)


def _extract_name_candidates(normalized: str) -> list[str]:
    """Generate candidate molecule names from a normalized user message.

    Returns candidates in priority order, de-duplicated, excluding the full
    input itself (the caller already tried it). Heuristics, in order:

        1. The phrase that follows an intent verb + "de": "propiedades de
           nicotina" -> "nicotina", "dame las propiedades de dapaglifocina"
           -> "dapaglifocina".
        2. The phrase that follows a bare trailing "de X" ("de la aspirina").
        3. Individual tokens (len >= 4, not intent stopwords).
        4. Consecutive token bi-grams ("acido ascorbico", "penicilina g").

    This is deliberately conservative: each candidate still has to survive the
    real resolution chain (dict -> FTS -> optional PubChem -> fuzzy), which is
    the strong filter against false positives. A stopword like "propiedades"
    never reaches PubChem or fuzzy.
    """
    out: list[str] = []
    # 1. Intent verb + preposition + phrase.
    #    First strip leading intent verbs so the regex sees "de nicotina".
    stripped = normalized
    for w in ("dame las propiedades de", "dame la propiedad de",
              "dame las de", "dame la de", "calcular las propiedades de",
              "calcular la propiedad de", "calcula las propiedades de",
              "calcula la propiedad de", "propiedades de", "propiedad de",
              "quiero las propiedades de", "necesito las propiedades de",
              "obten las propiedades de", "muestrame las propiedades de",
              "muéstrame las propiedades de", "muestrame las de"):
        if stripped.startswith(w):
            stripped = stripped[len(w):].strip()
            break
    m = _PROPOSITION_DE_RE.search(stripped)
    if m:
        phrase = m.group(1).strip()
        if phrase and phrase != normalized:
            out.append(phrase)

    # 2. Bare trailing "de X" fallback ("de la aspirina").
    m2 = re.search(r"\bde\s+(?:la\s+|el\s+|las\s+|los\s+)?([a-z0-9]+(?:\s+[a-z0-9]+)?)$", normalized)
    if m2:
        phrase2 = m2.group(1).strip()
        if phrase2 and phrase2 != normalized:
            out.append(phrase2)

    # 3. Tokens (>= 4 chars, not stopwords).
    tokens = [
        t for t in normalized.split()
        if len(t) >= 4 and t not in _INTENT_STOPWORDS
    ]
    out.extend(tokens)

    # 4. Bi-grams for compound names.
    for i in range(len(tokens) - 1):
        out.append(f"{tokens[i]} {tokens[i+1]}")

    # Dedupe, keep priority order, drop anything equal to the full input.
    seen: set[str] = set()
    result: list[str] = []
    for c in out:
        c = c.strip()
        if c and c != normalized and c not in seen:
            seen.add(c)
            result.append(c)
    return result


def _build_failure_hint(raw_name: str) -> str:
    """User-facing Spanish hint shown when no resolution succeeded.

    Kept in Spanish because MolChat's primary audience is Spanish-speaking.
    The hint is a string literal returned through ResolutionResult.error_hint,
    not a UI artifact we author — so matching the project's chat language is
    the right call here, not English.
    """
    safe = (raw_name or "").strip() or "?"
    return (
        f"no se reconoce '{safe}' — prueba con el nombre INN "
        f"(internacional) o ingresa el SMILES directamente"
    )


def _ok(smiles: str, source: str, *, english_name: str | None = None,
        matched_dict_name: str | None = None) -> ResolutionResult:
    return ResolutionResult(
        smiles=smiles,
        source=source,
        english_name=english_name,
        matched_dict_name=matched_dict_name,
        error_hint=None,
    )


def _fail(raw_name: str, source: str = "failed",
          english_name: str | None = None) -> ResolutionResult:
    return ResolutionResult(
        smiles=None,
        source=source,
        english_name=english_name,
        matched_dict_name=None,
        error_hint=_build_failure_hint(raw_name),
    )


# ---------------------------------------------------------------------------
# Public orchestrator
# ---------------------------------------------------------------------------

async def resolve_molecule_name(
    name_text: str,
    *,
    allow_web: bool = False,
    molgraph_db_path: Path | None = None,
    timeout_seconds: float = 4.0,
) -> ResolutionResult:
    """Resolve a user-typed molecule name into a canonical SMILES.

    Parameters
    ----------
    name_text:
        Raw user input. May be a BARE molecule name ("nicotina") or a full
        user message ("propiedades de nicotina", "dame las propiedades de
        dapaglifocina"). Spanish or English, with accents, extra whitespace,
        mixed case. Empty/None -> immediate failed result.
    allow_web:
        Whether the caller authorized network access (frontend online toggle).
        Does NOT default to True: the caller must explicitly pass True. When
        False, step 3 (PubChem) is skipped entirely and no name ever leaves
        the machine.
    molgraph_db_path:
        Override path to the MolGraph SQLite DB. Defaults to
        ``~/MolDesign/data/molgraph.db``. Useful for tests / alternate installs.
    timeout_seconds:
        Upper bound for the PubChem HTTP call. Passed to _http_get_json.

    Returns
    -------
    ResolutionResult — always. Never raises: every network / DB / parsing
    failure is captured and surfaces as ``smiles=None`` with an ``error_hint``
    plus ``source="failed"``.

    Candidate priority
    ------------------
    1. The full normalized input (a user who typed just "nicotina" hits here).
    2. Extracted candidates in priority order (phrase-after-"de", tokens,
       bi-grams) — see _extract_name_candidates.
    """
    # Guard inputs.
    if not name_text or not isinstance(name_text, str):
        return _fail(name_text or "")

    raw_input = name_text
    normalized = normalize_name(name_text)
    if not normalized:
        return _fail(raw_input)

    db_path = Path(molgraph_db_path) if molgraph_db_path else _DEFAULT_MOLGRAPH_DB

    # ---- Candidate 0: full normalized input -----------------------------
    full_result = await _resolve_candidate(
        normalized,
        db_path=db_path,
        allow_web=allow_web,
        timeout_seconds=timeout_seconds,
    )
    if full_result and full_result.smiles:
        return full_result

    # ---- Candidate N: extracted names (full chain per candidate) --------
    for candidate in _extract_name_candidates(normalized):
        cand_result = await _resolve_candidate(
            candidate,
            db_path=db_path,
            allow_web=allow_web,
            timeout_seconds=timeout_seconds,
        )
        if cand_result and cand_result.smiles:
            return cand_result

    # ---- No resolution ------------------------------------------------
    return _fail(raw_input, english_name=get_english_name(normalized))


async def _resolve_candidate(
    normalized: str,
    *,
    db_path: Path,
    allow_web: bool,
    timeout_seconds: float,
) -> ResolutionResult | None:
    """Run the full resolution chain (dict -> FTS -> optional PubChem -> fuzzy)
    against ONE normalized candidate name.

    Returns a ResolutionResult with a non-None smiles on success, or None when
    this particular candidate did not resolve (the caller tries the next one).
    Never raises.
    """
    if not normalized:
        return None

    english_translation = get_english_name(normalized)

    # ---- Step 1: in-memory dict lookup ----------------------------------
    dict_smiles = get_smiles_by_name(normalized)
    if dict_smiles:
        return _ok(dict_smiles, "dict", matched_dict_name=normalized)

    # ---- Step 2: MolGraph FTS5 exact-ish -------------------------------
    mg = _query_molgraph_fts(normalized, english_translation, db_path)
    if mg and mg[1]:
        return _ok(mg[1], "molgraph_fts", english_name=english_translation)

    # ---- Step 3: PubChem-by-name (ONLY if user is online) --------------
    # Privacy gate: do not even import-check the cache or build a URL if the
    # caller did not explicitly allow web. The cached-first check below also
    # counts as "no network", so we keep it under the allow_web branch: a
    # cached entry was originally fetched with consent, so reusing it offline
    # is fine, but we only enter this branch when allow_web is True to keep
    # the privacy surface minimal and the contract obvious.
    if allow_web:
        # 3a. cached short-circuit (best-effort, ~µs, TTL ~30d)
        cached = _pubchem_cached_smiles_for(normalized)
        if not cached and english_translation:
            cached = _pubchem_cached_smiles_for(english_translation)
        if cached:
            return _ok(cached, "pubchem", english_name=english_translation)

        # 3b. live PubChem query offloaded to a worker thread so an HTTP
        #     timeout cannot block the event loop.
        query_name = english_translation or normalized
        try:
            smiles = await asyncio.to_thread(
                _pubchem_name_to_smiles, query_name, timeout_seconds,
            )
        except Exception:
            smiles = None

        if smiles:
            # Persist into the shared cache so the next resolve is instant.
            data_json_blob = (
                '{"name": "%s", '
                '"canonical_smiles": "%s", '
                '"resolved_by": "name_resolver"}'
                % (query_name.replace('"', ''), smiles.replace('"', ''))
            )
            _cache_pubchem_result(smiles, data_json_blob, time.time())
            return _ok(smiles, "pubchem", english_name=query_name)

    # ---- Step 4: fuzzy match against ALL_NAMES -------------------------
    fuzzy_name = _fuzzy_resolve(normalized)
    if fuzzy_name:
        fuzzy_smiles = get_smiles_by_name(fuzzy_name)
        if fuzzy_smiles:
            return _ok(fuzzy_smiles, "fuzzy", matched_dict_name=fuzzy_name)

    # ---- Candidate failed: caller tries the next one ---------------------
    return None


__all__ = ["ResolutionResult", "resolve_molecule_name"]
