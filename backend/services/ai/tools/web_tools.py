"""
services/ai/tools/web_tools.py

Herramientas verificadas que requieren internet (RCSB PDB, PubChem, ChEMBL).
Solo disponibles si hay conectividad. Resultados se cachean localmente.

Estrategia de failover: cada tool prueba 2-4 endpoints alternativos en
secuencia. Si el primary falla (offline / timeout / API cambio de contrato),
pasa automáticamente al siguiente. Ninguna API rota bloquea MolChat.

Herramientas expuestas (todas offline=False):
  pubchem_lookup    — propiedades físico-químicas (MW, LogP, TPSA, HBD, HBA)
  chembl_activity   — bioactividad, dianas farmacológicas (IC50, Ki, Kd)
  search_pdb        — estructuras 3D de proteínas (RCSB PDB)
  search_similar    — análogos químicos (local MolGraph + ChEMBL backup)
  pubchem_description — descripción completa de un compuesto (uso clínico, mecanismo)
"""

from __future__ import annotations

import json
import sqlite3
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Callable, Awaitable

from services.ai.tool_registry import ToolDef, get_tool_registry
from utils.logger import get_logger

log = get_logger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# Caches locales (offline-first)
# ═══════════════════════════════════════════════════════════════════════

_PUBCHEM_CACHE = Path.home() / "MolDesign" / "data" / "pubchem_cache.db"
_CHEMBL_CACHE  = Path.home() / "MolDesign" / "data" / "chembl_cache.db"

# PubChem y otras APIs públicas rechazan User-Agents cortos/custom con HTTP 400.
# Un UA tipo navegador es lo que esperan (verificado: "MolDesign/1.5" → 400,
# "Mozilla/5.0 ..." → 200 con CID). Bug real: pubchem_lookup nunca funcionó.
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 MolDesign/1.5"
)

_OFFLINE_MARKERS = (
    "[PubChem offline]", "[ChEMBL offline]", "[RCSB offline]",
    "[PubChem error]",   "[ChEMBL error]",   "[RCSB error]",
)


def _pubchem_conn() -> sqlite3.Connection:
    _PUBCHEM_CACHE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_PUBCHEM_CACHE))
    c.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(smiles TEXT PRIMARY KEY, data_json TEXT, fetched_at REAL)"
    )
    c.commit()
    return c


def _chembl_conn() -> sqlite3.Connection:
    _CHEMBL_CACHE.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_CHEMBL_CACHE))
    c.execute(
        "CREATE TABLE IF NOT EXISTS cache "
        "(key TEXT PRIMARY KEY, data TEXT, fetched REAL)"
    )
    c.commit()
    return c


# ═══════════════════════════════════════════════════════════════════════
# Helpers: HTTP + traducción español → inglés
# ═══════════════════════════════════════════════════════════════════════

_NAME_ES_TO_EN: dict[str, str] = {
    # AINEs
    "aspirina": "aspirin", "ibuprofeno": "ibuprofen",
    "paracetamol": "acetaminophen", "naproxeno": "naproxen",
    "diclofenaco": "diclofenac", "ketorolaco": "ketorolac",
    # Opioides
    "morfina": "morphine", "tramadol": "tramadol", "fentanilo": "fentanyl",
    # Antibióticos
    "penicilina": "penicillin", "amoxicilina": "amoxicillin",
    "ampicilina": "ampicillin", "ceftriaxona": "ceftriaxone",
    "azitromicina": "azithromycin", "ciprofloxacino": "ciprofloxacin",
    "tetraciclina": "tetracycline", "vancomicina": "vancomycin",
    # Cardiovascular
    "atenolol": "atenolol", "losartán": "losartan", "enalapril": "enalapril",
    "amlodipino": "amlodipine", "atorvastatina": "atorvastatin",
    "simvastatina": "simvastatin", "warfarina": "warfarin",
    # Psiquiatría / neurología
    "diazepam": "diazepam", "lorazepam": "lorazepam", "alprazolam": "alprazolam",
    "fluoxetina": "fluoxetine", "sertralina": "sertraline",
    "escitalopram": "escitalopram", "risperidona": "risperidone",
    "haloperidol": "haloperidol", "levodopa": "levodopa",
    # Metabólicos
    "metformina": "metformin", "gliburida": "glyburide",
    "levotiroxina": "levothyroxine",
    # Antineoplásicos
    "taxol": "paclitaxel", "paclitaxel": "paclitaxel",
    "doxorubicina": "doxorubicin",
    # Otros
    "dexametasona": "dexamethasone", "prednisona": "prednisone",
    "omeprazol": "omeprazole", "ranitidina": "ranitidine",
    "cafeína": "caffeine", "cafeina": "caffeine",
    "dopamina": "dopamine", "serotonina": "serotonin",
    "adrenalina": "epinephrine",
}


def _name_to_english(user_name: str) -> str:
    """Traduce nombre de fármaco español → inglés estándar (PubChem/ChEMBL)."""
    return _NAME_ES_TO_EN.get(user_name.lower().strip(), user_name)


def _puede_salir(url: str, user_id: str | None) -> bool:
    """La puerta única de salida (`services/ai/red.py`).

    Antes de esto la única defensa era `allow_web`, un interruptor global:
    autorizar «buscar en internet» autorizaba PubChem, ChEMBL, RCSB y UniProt a
    la vez, sin decir cuáles ni qué sale hacia ellos. Ahora el permiso es por
    cuenta y por destino, y la denegación es silenciosa hacia arriba —la
    herramienta devuelve `None`, como con cualquier fallo de red— pero queda en
    el log con su motivo.
    """
    from services.ai import red

    try:
        red.exigir_permiso(url, user_id)
        return True
    except red.SalidaNoAutorizada as exc:
        log.info("salida_denegada", url=url[:120], motivo=str(exc)[:200])
        return False


def _http_get_json(
    url: str, timeout: float = 8.0, user_id: str | None = None
) -> dict | None:
    """HTTP GET → JSON dict. None si falla (timeout, offline, HTTP != 200).

    `None` también cuando esta cuenta no autorizó ese destino: para el llamador
    es el mismo desenlace —no hay dato— y no hace falta que cada herramienta
    aprenda a distinguirlo.
    """
    if not _puede_salir(url, user_id):
        return None
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _http_post_json(
    url: str, payload: dict, timeout: float = 10.0, user_id: str | None = None
) -> dict | None:
    """HTTP POST JSON → JSON dict. None si falla o si el destino no está autorizado."""
    if not _puede_salir(url, user_id):
        return None
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json", "User-Agent": _UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════
# Failover runner — corazón del circuito
# ═══════════════════════════════════════════════════════════════════════

async def _fetch_with_fallback(
    calls: list[Callable[[], Awaitable[str]]],
    label: str = "web",
) -> str:
    """Ejecuta calls en secuencia. La primera que devuelve un resultado útil
    (sin marcador de error/offline) gana. Si todas fallan, mensaje genérico."""
    last_error = ""
    for fn in calls:
        try:
            result = await fn()
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        if not result or any(result.startswith(m) for m in _OFFLINE_MARKERS):
            last_error = result or "vacio"
            continue
        return result
    return f"[{label}] No disponible. {last_error}"


# ═══════════════════════════════════════════════════════════════════════
# Tool: pubchem_lookup
#   Primary:  PubChem REST by SMILES
#   Fallback: PubChem REST by English name
# ═══════════════════════════════════════════════════════════════════════

async def pubchem_lookup(smiles: str) -> str:
    """Propiedades físico-químicas verificadas (MW, LogP, TPSA, HBD, HBA)."""
    if not smiles or len(smiles) < 2:
        return "[PubChem] SMILES inválido."

    # Cache check
    conn = _pubchem_conn()
    row = conn.execute(
        "SELECT data_json FROM cache WHERE smiles=?", (smiles,)
    ).fetchone()
    conn.close()
    if row:
        return row[0]

    async def _via_smiles() -> str:
        enc = urllib.parse.quote(smiles, safe="")
        url = (
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{enc}"
            f"/property/MolecularWeight,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,CanonicalSMILES/JSON"
        )
        data = _http_get_json(url)
        if not data:
            return "[PubChem offline]"
        props = (data.get("PropertyTable") or {}).get("Properties", [{}])
        if not props or not props[0]:
            return "[PubChem] Sin datos para este SMILES."
        p = props[0]
        return (
            f"[PubChem] SMILES canonico: {p.get('CanonicalSMILES','?')}. "
            f"MW: {p.get('MolecularWeight','?')} g/mol. "
            f"LogP: {p.get('XLogP','?')}. "
            f"TPSA: {p.get('TPSA','?')} Å². "
            f"HBD: {p.get('HBondDonorCount','?')}. HBA: {p.get('HBondAcceptorCount','?')}."
        )

    async def _via_name_fallback() -> str:
        # Intenta inferir nombre común desde KNOWN_DRUGS → english → PubChem name
        name = _smiles_to_common_name(smiles)
        if not name:
            return "[PubChem] sin nombre conocido para este SMILES."
        ename = _name_to_english(name)
        enc = urllib.parse.quote(ename)
        url = (
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{enc}"
            f"/property/MolecularWeight,XLogP,TPSA/JSON"
        )
        data = _http_get_json(url)
        if not data:
            return "[PubChem name] endpoint offline"
        props = (data.get("PropertyTable") or {}).get("Properties", [{}])
        if not props or not props[0]:
            return "[PubChem name] Sin datos"
        p = props[0]
        return (
            f"[PubChem — {ename}] "
            f"MW: {p.get('MolecularWeight','?')} g/mol. "
            f"LogP: {p.get('XLogP','?')}. TPSA: {p.get('TPSA','?')} Å²."
        )

    result = await _fetch_with_fallback([_via_smiles, _via_name_fallback], "PubChem")
    if result and not result.startswith("["):
        return result
    # Guardar en cache antes de retornar
    conn2 = _pubchem_conn()
    conn2.execute(
        "INSERT OR REPLACE INTO cache VALUES(?,?,?)",
        (smiles, result, time.time()),
    )
    conn2.commit()
    conn2.close()
    return result


# ═══════════════════════════════════════════════════════════════════════
# Tool: chembl_activity
#   Primary:  ChEMBL REST (molecule → activity, con traducción es→en)
#   Fallback: PubChem CID → BioAssay summary
# ═══════════════════════════════════════════════════════════════════════

async def chembl_activity(molecule_name: str) -> str:
    """Bioactividad y dianas de un fármaco (IC50, Ki, Kd, EC50, fases clínicas)."""
    if not molecule_name or len(molecule_name) < 2:
        return "[ChEMBL] Nombre de molécula inválido."

    # Cache
    conn = _chembl_conn()
    row = conn.execute(
        "SELECT data FROM cache WHERE key=?", (f"act_{molecule_name}",)
    ).fetchone()
    conn.close()
    if row:
        return row[0]

    async def _via_chembl_rest() -> str:
        ename = _name_to_english(molecule_name)
        # Paso 1: encontrar molecule_chembl_id
        url1 = (
            "https://www.ebi.ac.uk/chembl/api/data/molecule"
            f"?format=json&molecule_synonyms__molecule_synonym__iexact={urllib.parse.quote(ename)}"
            "&limit=2"
        )
        md = _http_get_json(url1)
        if not md:
            return "[ChEMBL offline]"
        mols = md.get("molecules", [])
        if not mols:
            return f"[ChEMBL] '{ename}' no encontrado en ChEMBL."
        mol_id = mols[0].get("molecule_chembl_id", "")
        # Paso 2: actividades
        url2 = (
            "https://www.ebi.ac.uk/chembl/api/data/activity"
            f"?format=json&molecule_chembl_id={mol_id}&limit=8"
        )
        ad = _http_get_json(url2)
        activities = (ad or {}).get("activities", [])
        if not activities:
            return f"[ChEMBL] {ename} ({mol_id}): sin datos de bioactividad."
        lines = [f"[ChEMBL — {ename}] {mol_id}"]
        seen_targets: set[str] = set()
        for a in activities:
            tgt = a.get("target_pref_name", "") or a.get("target_chembl_id", "?")
            if tgt in seen_targets:
                continue
            seen_targets.add(tgt)
            stype = a.get("standard_type", "?")
            sval  = a.get("standard_value", "?")
            sunit = a.get("standard_units", "")
            srel  = a.get("standard_relation", "")
            lines.append(f"  {tgt}: {stype}={srel}{sval} {sunit}")
            if len(lines) > 6:
                break
        return "\n".join(lines)

    async def _via_pubchem_assay() -> str:
        # PubChem CID → BioAssay (solo si tenemos el CID)
        ename = _name_to_english(molecule_name)
        cid_url = (
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{urllib.parse.quote(ename)}"
            "/cids/JSON"
        )
        cdata = _http_get_json(cid_url)
        cids = (cdata or {}).get("IdentifierList", {}).get("CID", []) if cdata else []
        if not cids:
            return "[PubChem assay] CID no encontrado"
        cid = cids[0]
        aurl = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/assaysummary/JSON"
        adata = _http_get_json(aurl, timeout=12)
        if not adata:
            return "[PubChem assay] sin datos"
        table = adata.get("Table", {})
        rows = table.get("Row", [])
        if not rows:
            return f"[PubChem assay] CID {cid}: sin bioassays"
        lines = [f"[PubChem BioAssay — {ename}] CID {cid} ({len(rows)} assays) — primeros 2:"]
        for row in rows[:2]:
            cells = row.get("Cell", [])
            if len(cells) >= 5:
                lines.append(f"  {cells[9][:80]}: resultado={cells[4]}")
            else:
                lines.append(f"  {str(cells)[:120]}")
        return "\n".join(lines)

    result = await _fetch_with_fallback(
        [_via_chembl_rest, _via_pubchem_assay], "ChEMBL",
    )
    # Cache
    conn2 = _chembl_conn()
    conn2.execute(
        "INSERT OR REPLACE INTO cache VALUES(?,?,?)",
        (f"act_{molecule_name}", result, time.time()),
    )
    conn2.commit()
    conn2.close()
    return result


# ═══════════════════════════════════════════════════════════════════════
# Tool: search_pdb
#   Paso 1: RCSB v2 search → identifiers
#   Paso 2: RCSB GraphQL → títulos (batch)
#   Fallback: ChEMBL target search
# ═══════════════════════════════════════════════════════════════════════

async def _rcsb_graphql_titles(pdb_ids: list[str]) -> dict[str, str]:
    """GraphQL batch: obtener título de cada PDB ID."""
    titles: dict[str, str] = {}
    for pid in pdb_ids[:5]:
        gd = _http_post_json(
            "https://data.rcsb.org/graphql",
            {"query": f'{{ entry(entry_id: "{pid}") {{ struct {{ title }} }} }}'},
        )
        if not gd:
            titles[pid] = "(sin conexión)"
            continue
        entry = gd.get("data", {}).get("entry", {})
        title = entry.get("struct", {}).get("title", "(sin título)") if entry else "?"
        titles[pid] = title
    return titles


async def search_pdb(query: str, limit: int = 5) -> str:
    """Buscar estructuras 3D de proteínas en RCSB PDB (257K entradas)."""
    if not query or len(query) < 2:
        return "[RCSB] Query demasiado corta."

    async def _via_rcsb() -> str:
        payload = {
            "query": {
                "type": "terminal", "service": "full_text",
                "parameters": {"value": query},
            },
            "return_type": "entry",
            "request_options": {
                "return_all_hits": False,
                "paginate": {"start": 0, "rows": limit},
            },
        }
        data = _http_post_json(
            "https://search.rcsb.org/rcsbsearch/v2/query", payload,
        )
        if not data:
            return "[RCSB offline]"
        entries = data.get("result_set", [])
        if not entries:
            return f"[RCSB] No se encontraron estructuras para '{query}'."
        ids = [e.get("identifier", "?") for e in entries[:limit]]
        titles = await _rcsb_graphql_titles(ids)
        lines = [f"[RCSB PDB] Resultados para '{query}':"]
        for eid in ids:
            t = titles.get(eid, "?")[:100]
            lines.append(f"  {eid}: {t}")
        return "\n".join(lines)

    async def _via_chembl_target() -> str:
        # Fallback: buscar target en ChEMBL
        ename = _name_to_english(query)
        url = (
            "https://www.ebi.ac.uk/chembl/api/data/target"
            f"?format=json&pref_name__iexact={urllib.parse.quote(ename)}&limit=3"
        )
        td = _http_get_json(url)
        if not td or not td.get("targets"):
            return f"[ChEMBL target] '{ename}' no encontrado."
        lines = [f"[ChEMBL target] '{ename}':"]
        for t in td["targets"][:3]:
            tid = t.get("target_chembl_id", "?")
            tname = t.get("pref_name", "?")
            org = t.get("target_components", [{}])[0].get("accession", "")
            lines.append(f"  {tid}: {tname} ({org})")
        return "\n".join(lines)

    return await _fetch_with_fallback([_via_rcsb, _via_chembl_target], "RCSB PDB")


# ═══════════════════════════════════════════════════════════════════════
# Tool: search_similar
#   Primary:  MolGraph local (offline, fingerprint Tanimoto)
#   Fallback: ChEMBL similarity endpoint
#   (PubChem similarity requiere polling async — deprecado por ahora)
# ═══════════════════════════════════════════════════════════════════════

async def search_similar(smiles: str, limit: int = 5) -> str:
    """Buscar análogos químicos de un SMILES (local MolGraph + ChEMBL backup)."""
    if not smiles or len(smiles) < 3:
        return "[similar] SMILES inválido."

    async def _via_molgraph() -> str:
        try:
            from services.ai.tools.molgraph_tool import molgraph_similar
            return await molgraph_similar(smiles, threshold="0.5", limit=str(limit))
        except ImportError:
            return "[MolGraph] no disponible (¿módulo no cargado?)"
        except Exception as exc:
            return f"[MolGraph error] {exc}"

    async def _via_chembl() -> str:
        url = (
            "https://www.ebi.ac.uk/chembl/api/data/similarity"
            f"/{urllib.parse.quote(smiles)}/85?format=json&limit={limit}"
        )
        data = _http_get_json(url, timeout=12)
        if not data:
            return "[ChEMBL similarity] offline"
        mols = data.get("molecules", [])
        if not mols:
            return "[ChEMBL similarity] sin análogos"
        lines = [f"[ChEMBL similarity] {len(mols)} análogos para {smiles[:40]}:"]
        for m in mols[:limit]:
            cid = m.get("molecule_chembl_id", "?")
            pn  = m.get("pref_name", "") or "(sin nombre)"
            lines.append(f"  {cid}: {pn[:60]}")
        return "\n".join(lines)

    return await _fetch_with_fallback(
        [_via_molgraph, _via_chembl], "similaridad",
    )


# ═══════════════════════════════════════════════════════════════════════
# Tool: pubchem_description (NUEVA)
#   Primary:  PubChem REST compound description (CID)
#   Fallback: ChEMBL molecule schema
# ═══════════════════════════════════════════════════════════════════════

async def pubchem_description(name_or_cid: str) -> str:
    """Descripción completa de un compuesto: uso clínico, mecanismo de acción,
    indicaciones, sinónimos. Usa PubChem como primario, ChEMBL como fallback."""
    inp = name_or_cid.strip()
    if not inp or len(inp) < 2:
        return "[PubChem desc] Entrada inválida."

    async def _via_pubchem() -> str:
        # Si es numérico → CID directo; si es texto → name → CID
        cid: str | None = None
        if inp.isdigit():
            cid = inp
        else:
            ename = _name_to_english(inp)
            curl = (
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name"
                f"/{urllib.parse.quote(ename)}/cids/JSON"
            )
            cdata = _http_get_json(curl)
            cids = (cdata or {}).get("IdentifierList", {}).get("CID", []) if cdata else []
            if cids:
                cid = str(cids[0])
        if not cid:
            return f"[PubChem desc] '{inp}' no encontrado."
        # Obtener description
        durl = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/description/JSON"
        ddata = _http_get_json(durl, timeout=10)
        if not ddata:
            return "[PubChem desc] offline"
        info_list = ddata.get("InformationList", {}).get("Information", [])
        if not info_list:
            return f"[PubChem desc] CID {cid}: sin descripción."
        info = info_list[0]
        title = info.get("Title", "?")
        desc  = info.get("Description", "") or ""
        # Si no hay Description, al menos devolvemos el Title
        if not desc:
            desc = f"(compuesto registrado en PubChem como '{title}')"
        snippet = desc[:600].replace("\n", " ")
        return (
            f"[PubChem — {title}] CID {cid}. "
            f"{'Descripción: ' + snippet if snippet else ''}"
        )

    async def _via_chembl() -> str:
        ename = _name_to_english(inp)
        url = (
            "https://www.ebi.ac.uk/chembl/api/data/molecule"
            f"?format=json&pref_name__iexact={urllib.parse.quote(ename)}&limit=2"
        )
        md = _http_get_json(url)
        mols = (md or {}).get("molecules", [])
        if not mols:
            return f"[ChEMBL desc] '{ename}' no encontrado."
        m = mols[0]
        cid   = m.get("molecule_chembl_id", "?")
        mtype = m.get("molecule_type", "?")
        mwt   = m.get("full_mwt", "?")
        alogp = m.get("alogp", "?")
        desc  = m.get("description", "") or "(sin descripción)"
        return (
            f"[ChEMBL — {ename}] {cid}. Tipo: {mtype}. "
            f"MW: {mwt}, ALogP: {alogp}. {desc[:400]}"
        )

    return await _fetch_with_fallback(
        [_via_pubchem, _via_chembl], "PubChem description",
    )


# ═══════════════════════════════════════════════════════════════════════
# Helper: SMILES → common name (inverso del dict KNOWN_DRUGS)
# ═══════════════════════════════════════════════════════════════════════

# Reverso del diccionario español → inglés: para inferir nombre desde SMILES
# cuando el fallback necesita usar pubchem_lookup_by_name.
_SMILES_TO_NAME: dict[str, str] = {
    "CC(=O)Oc1ccccc1C(=O)O": "aspirin",
    "CC(C)Cc1ccc(C(C)C(=O)O)cc1": "ibuprofen",
    "CC(=O)Nc1ccc(O)cc1": "acetaminophen",
    "Cn1c(=O)c2c(ncn2C)n(C)c1=O": "caffeine",
    "CN1C(=O)CN=C(C2=C1C=CC(=C2)Cl)C3=CC=CC=C3": "diazepam",
    "CC1=CN=C(C(=C1OC)C)CS(=O)C2=NC3=C([NH]2)C=C(C=C3)OC": "omeprazole",
    "CN(C)C(=N)NC(=N)N": "metformin",
    "CNCCC(C1=CC=CC=C1)OC2=CC=C(C=C2)C(F)(F)F": "fluoxetine",
    "CNC1(CCC2=C(C1)C=C(C=C2)Cl)C3=CC=CC=C3": "sertraline",
    "CC1(C(N2C(S1)C(C2=O)NC(=O)CC3=CC=CC=C3)C(=O)O)C": "penicillin",
    "CC1(C(N2C(S1)C(C2=O)NC(=O)C(C3=CC=C(C=C3)O)N)C(=O)O)C": "amoxicillin",
}


def _smiles_to_common_name(smiles: str) -> str:
    """Devuelve el nombre común en inglés si el SMILES está en nuestro dict."""
    # Normalizar: quitar espacios y probar
    s = smiles.strip()
    if s in _SMILES_TO_NAME:
        return _SMILES_TO_NAME[s]
    # Intentar canonical match via RDKit
    try:
        from rdkit import Chem
        mol = Chem.MolFromSmiles(s)
        if mol:
            canon = Chem.MolToSmiles(mol, canonical=True)
            if canon in _SMILES_TO_NAME:
                return _SMILES_TO_NAME[canon]
    except Exception:
        pass
    return ""


# ═══════════════════════════════════════════════════════════════════════
# pubchem_autolookup — usado por chat_service.py (compatibilidad)
# ═══════════════════════════════════════════════════════════════════════

KNOWN_DRUGS: dict[str, str] = {
    "aspirina": "CC(=O)Oc1ccccc1C(=O)O",
    "ibuprofeno": "CC(C)Cc1ccc(C(C)C(=O)O)cc1",
    "paracetamol": "CC(=O)Nc1ccc(O)cc1",
    "morfina": "CN1CCC23C4=C1CC5=C2C(=C(C=C5)O)OC3C(C=C4)O",
    "cafeina": "CN1C=NC2=C1C(=O)N(C(=O)N2C)C",
    "diazepam": "CN1C(=O)CN=C(C2=C1C=CC(=C2)Cl)C3=CC=CC=C3",
    "omeprazol": "CC1=CN=C(C(=C1OC)C)CS(=O)C2=NC3=C([NH]2)C=C(C=C3)OC",
    "metformina": "CN(C)C(=N)NC(=N)N",
    "fluoxetina": "CNCCC(C1=CC=CC=C1)OC2=CC=C(C=C2)C(F)(F)F",
    "sertralina": "CNC1(CCC2=C(C1)C=C(C=C2)Cl)C3=CC=CC=C3",
    "penicilina": "CC1(C(N2C(S1)C(C2=O)NC(=O)CC3=CC=CC=C3)C(=O)O)C",
    "amoxicilina": "CC1(C(N2C(S1)C(C2=O)NC(=O)C(C3=CC=C(C=C3)O)N)C(=O)O)C",
    "dopamina": "C1=CC(=C(C=C1CCN)O)O",
    "serotonina": "C1=CC2=C(C=C1O)C(=C[NH]2)CCN",
    "adrenalina": "CNCC(C1=CC(=C(C=C1)O)O)O",
}


def pubchem_autolookup(
    user_message: str,
    molecule_context: dict | None,
    user_id: str | None = None,
) -> str:
    """Auto-consulta PubChem si el mensaje menciona un fármaco conocido.
    Usa cache local. Mantenido por compatibilidad con chat_service.py."""
    msg_lower = user_message.lower()
    for name, smiles in KNOWN_DRUGS.items():
        if name not in msg_lower:
            continue
        if molecule_context and molecule_context.get("smiles") == smiles:
            continue
        conn = _pubchem_conn()
        row = conn.execute(
            "SELECT data_json FROM cache WHERE smiles=?", (smiles,)
        ).fetchone()
        conn.close()
        if row:
            return f"\n[PubChem - {name.capitalize()} (cache)] {row[0]}"
        try:
            enc = urllib.parse.quote(smiles, safe="")
            url = (
                f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/{enc}"
                "/property/MolecularWeight,XLogP,TPSA/JSON"
            )
            # Ésta era la salida que el gate runtime encontró fuera de todo
            # control: consultaba PubChem en cada turno que nombrara un fármaco
            # conocido, sin mirar `allow_web` ni consentimiento. Ahora pasa por
            # la misma puerta que el resto.
            data = _http_get_json(url, timeout=5, user_id=user_id)
            if not data:
                continue
            p = data.get("PropertyTable", {}).get("Properties", [{}])[0]
            if p:
                result = (
                    f"[PubChem - {name.capitalize()}] SMILES: {smiles}. "
                    f"MW: {p.get('MolecularWeight','?')} g/mol. "
                    f"LogP: {p.get('XLogP','?')}."
                )
                conn2 = _pubchem_conn()
                conn2.execute(
                    "INSERT OR REPLACE INTO cache VALUES(?,?,?)",
                    (smiles, result, time.time()),
                )
                conn2.commit()
                conn2.close()
                return result
        except Exception:
            pass
    return ""


# ═══════════════════════════════════════════════════════════════════════
# Registration — 5 tools web con descripciones enriquecidas
# ═══════════════════════════════════════════════════════════════════════

def register_web_tools() -> None:
    registry = get_tool_registry()

    registry.register(ToolDef(
        name="pubchem_lookup",
        clase="recuperacion_externa",
        procedencia="PubChem (NCBI)",
        description=(
            "Propiedades FISICO-QUIMICAS VERIFICADAS de un compuesto en PubChem "
            "(NCBI NIH, 120M compuestos): MolecularWeight, XLogP, TPSA, HBD, HBA. "
            "USA ESTA TOOL en vez de inventar MW/LogP/TPSA de memoria. "
            "Cache offline. REQUIERE INTERNET la primera vez. Entrada: SMILES."
        ),
        parameters={"smiles": {"type": "string", "required": True}},
        offline=False,
        fn=pubchem_lookup,
    ))
    registry.register(ToolDef(
        name="chembl_activity",
        clase="recuperacion_externa",
        procedencia="ChEMBL (EBI)",
        description=(
            "BIOACTIVIDAD y DIANAS verificadas de un farmaco. Fuente: ChEMBL (EBI, "
            "2.4M compuestos, 15K targets, 19M bioactividades: IC50, Ki, Kd, EC50), "
            "con fases clinicas I-III y mechanism of action. Con failover a PubChem "
            "BioAssay si ChEMBL no responde. Cache offline. REQUIERE INTERNET. "
            "Entrada: nombre del compuesto (español o inglés)."
        ),
        parameters={"molecule_name": {"type": "string", "required": True}},
        offline=False,
        fn=chembl_activity,
    ))
    registry.register(ToolDef(
        name="search_pdb",
        clase="recuperacion_externa",
        procedencia="RCSB PDB",
        description=(
            "Estructuras 3D de PROTEINAS en RCSB Protein Data Bank (257K entradas "
            "experimentales, estándar global): PDB ID, título, organismo fuente. "
            "Util para identificar targets de docking. Con fallback a ChEMBL "
            "target search si RCSB no responde. REQUIERE INTERNET. "
            "Entrada: texto libre (nombre del receptor, enzima o PDB ID)."
        ),
        parameters={
            "query": {"type": "string", "required": True},
            "limit": {"type": "integer", "required": False},
        },
        offline=False,
        fn=search_pdb,
    ))
    registry.register(ToolDef(
        name="search_similar",
        clase="recuperacion_externa",
        procedencia="grafo local con respaldo de similitud de ChEMBL",
        description=(
            "ANALOGOS QUIMICOS: busca moleculas similares por fingerprint Tanimoto. "
            "Primario: MolGraph local (offline, rapido). Fallback: ChEMBL similarity "
            "(online). NO usa PubChem similarity (requiere polling >30s). "
            "Util para explorar espacio quimico alrededor de un SMILES. "
            "Entrada: SMILES canonico."
        ),
        parameters={
            "smiles": {"type": "string", "required": True},
            "limit": {"type": "integer", "required": False},
        },
        offline=False,
        fn=search_similar,
    ))
    registry.register(ToolDef(
        name="pubchem_description",
        clase="recuperacion_externa",
        procedencia="PubChem (NCBI), respaldo ChEMBL",
        description=(
            "DESCRIPCION COMPLETA de un compuesto: uso clinico, mecanismo de accion, "
            "indicaciones, sinónimos. Fuente primaria: PubChem (NCBI). Fallback: "
            "ChEMBL molecule schema. UTIL para contextualizar un farmaco SIN INVENTAR "
            "indicaciones ni mecanismos. Entrada: nombre del compuesto o CID numerico."
        ),
        parameters={"name_or_cid": {"type": "string", "required": True}},
        offline=False,
        fn=pubchem_description,
    ))


# ═══════════════════════════════════════════════════════════════════════
# Tool: query_verified_source
#   Devuelve valores VERIFICADOS con su fuente (PubChem URL) para que el
#   LLM NO invente "LogP: 0.83" con URLs falsas (bug F8 del testing).
# ═══════════════════════════════════════════════════════════════════════

async def query_verified_source(molecule_name: str) -> str:
    """Propiedades y/o bioactividad VERIFICADAS de una molécula, con la URL
    de la fuente (PubChem / ChEMBL).

    Uso: cuando el usuario pide "cita la fuente de los valores", "de dónde
    sale ese LogP", "dame el DOI/URL". Devuelve los valores REALES de la API
    con su URL — el modelo NO debe inventar ni citar de memoria.
    """
    if not molecule_name or len(molecule_name) < 2:
        return "Necesito el nombre de una molécula para buscar su fuente verificada."

    # Nombre en inglés para las APIs
    ename = _name_to_english(molecule_name)
    enc = urllib.parse.quote(ename)

    lines = [f"[Fuente verificada de '{molecule_name}' ({ename})]"]
    found_any = False

    # ── 1. PubChem: propiedades fisicoquímicas reales + URL ──
    pubchem_url = f"https://pubchem.ncbi.nlm.nih.gov/compound/{enc}"
    # Campos válidos del endpoint PUG property: MolecularWeight, XLogP, TPSA,
    # HBondDonorCount, HBondAcceptorCount, CanonicalSMILES. (HBD/HBA no existen
    # como nombres de campo — causaban HTTP 400 y la petición completa fallaba.)
    url = (
        f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{enc}"
        f"/property/MolecularWeight,XLogP,TPSA,HBondDonorCount,HBondAcceptorCount,CanonicalSMILES/JSON"
    )
    data = _http_get_json(url, timeout=8.0)
    if data:
        props = (data.get("PropertyTable") or {}).get("Properties") or []
        if props and isinstance(props[0], dict):
            p = props[0]
            parts = []
            if p.get("MolecularWeight") is not None:
                parts.append(f"MW={p['MolecularWeight']} g/mol")
            if p.get("XLogP") is not None:
                parts.append(f"LogP={p['XLogP']}")
            if p.get("TPSA") is not None:
                parts.append(f"TPSA={p['TPSA']} Å²")
            if p.get("HBondDonorCount") is not None:
                parts.append(f"HBD={p['HBondDonorCount']}")
            if p.get("HBondAcceptorCount") is not None:
                parts.append(f"HBA={p['HBondAcceptorCount']}")
            if parts:
                lines.append(f"  PubChem: {', '.join(parts)}")
                lines.append(f"    URL: {pubchem_url}")
                found_any = True
            else:
                lines.append("  PubChem: sin propiedades numéricas disponibles")
    else:
        lines.append("  PubChem: offline o no encontrado")

    # ── 2. ChEMBL: bioactividad real (si existe) + URL ──
    act = await chembl_activity(molecule_name)
    if act and not act.startswith("[ChEMBL]") and "no encontrado" not in act:
        chembl_url = (
            "https://www.ebi.ac.uk/chembl/"
            f"#report_card/molecule/{urllib.parse.quote(ename)}"
        )
        lines.append(f"  ChEMBL: {act[:300]}")
        lines.append(f"    URL: {chembl_url}")
        found_any = True
    elif act and "no encontrado" in act:
        lines.append(
            "  ChEMBL: no hay actividad medida publicada para este compuesto "
            "(no inventar — el dato no existe públicamente)"
        )

    if not found_any:
        return (
            f"No pude verificar '{molecule_name}' en PubChem/ChEMBL "
            "(offline o no encontrado). No citaré valores sin fuente verificada."
        )

    return "\n".join(lines)


def register_web_tools_extended():
    """Registro adicional para query_verified_source (evita tocar el registro
    principal por compatibilidad)."""
    registry = get_tool_registry()
    registry.register(ToolDef(
        name="query_verified_source",
        clase="recuperacion_externa",
        procedencia="PubChem y ChEMBL, con la URL de cada valor",
        description=(
            "Devuelve valores VERIFICADOS con su FUENTE (URL PubChem/ChEMBL) para "
            "una molécula por NOMBRE. USALA cuando el usuario pida 'cita la fuente', "
            "'de dónde sale ese valor', 'dame el DOI/URL', 'biodisponibilidad con "
            "fuente'. Devuelve MW/LogP/TPSA/HBD/HBA reales de PubChem + actividad "
            "ChEMBL si existe. NUNCA inventar valores ni URLs — si no hay dato, "
            "dice honestamente que no existe públicamente. REQUIERE INTERNET."
        ),
        parameters={"molecule_name": {"type": "string", "required": True}},
        offline=False,
        fn=query_verified_source,
    ))
