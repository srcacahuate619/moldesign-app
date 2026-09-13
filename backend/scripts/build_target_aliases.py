"""
scripts/build_target_aliases.py

Genera `backend/data/target_aliases.json` — aliases de nombres comunes para
los 387 targets curados, para que MolChat resuelva "receptor de serotonina"
→ 7E2Y (F4 target resolver).

Fuentes (en orden de calidad):
  1. curated_targets.csv  → nombres comunes limpios (79 targets, grid listo)
  2. curated_targets.json → campo `name` (corto/útil) + structural_family
  3. Headers PDB COMPND SYNONYM de data/targets/ y data/target_library/**
     (nombres biológicos reales: "PROTEIN KINASE B", "PKB", ...)
  4. Aliases curados en español/INN para targets de uso frecuente (curados
     manualmente abajo, ver TARGET_ALIASES_ES).

Salida (por pdb_id):
  {
    "pdb_id": "7E2Y",
    "name": "5-HT1A",                      # nombre corto preferido
    "family": "gpcr",
    "has_structure": true,                 # PDB local encontrado
    "aliases": ["5-HT1A Serotonin Receptor", "receptor de serotonina", ...]
  }

Reejecutable: python -m scripts.build_target_aliases
"""
from __future__ import annotations

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
CSV_PATH = ROOT / "curated_targets.csv"
JSON_PATH = ROOT / "curated_targets.json"
TARGETS_DIR = ROOT / "data" / "targets"
LIBRARY_DIR = ROOT / "data" / "target_library"
OUT_PATH = ROOT / "backend" / "data" / "target_aliases.json"


def _norm(s: str) -> str:
    """Lowercase, strip accents, collapse whitespace (for matching keys)."""
    if not s:
        return ""
    nf = unicodedata.normalize("NFKD", s)
    stripped = "".join(ch for ch in nf if not unicodedata.combining(ch))
    return " ".join(stripped.lower().split())


def _clean_alias(raw: str) -> str | None:
    """Clean a raw synonym/title token into a usable alias.

    Drops: empty, too short (<3), too long (>90), pure noise ("2 RPR208815"),
    continuation artifacts ("3 80'S LOOP."), tokens that are mostly numbers,
    and expression-construct tags (lysozyme chimera, etc.).
    Returns None when the token is unusable.
    """
    if not raw:
        return None
    s = raw.strip().strip(";.,")
    if len(s) < 3 or len(s) > 90:
        return None
    # Drop tokens that are mostly numbers / fragments like "2 RPR208815"
    alpha = sum(c.isalpha() for c in s)
    if alpha < 3:
        return None
    # Drop obvious continuation noise: starts with a bare digit + short tail
    if re.match(r"^\d{1,2}\s+[A-Z0-9'\"]+$", s):
        return None
    # Drop "1 ... 2 ..." continuation artifact lines from folded TITLE records
    if re.match(r"^\d{1,2}\s", s) and len(s) < 20:
        return None
    # Drop expression-construct / fusion tags that are NOT the biological
    # target (seen in GPCR structures using a lysozyme/BRIL chimera tag).
    if any(tag in s.upper() for tag in (
        "LYSIS PROTEIN", "LYSOZYME", "MURAMIDASE", "ENDOLYSIN",
        "CYTOCHROME B-562", "BRIL", "BACTERIOPHAGE T4", "T4 LYSOZYME",
        "FLAVODOXIN", "APOCYTOCHROME", "HEME TAG",
    )):
        return None
    return s


# Aliases curados en español / INN para targets de uso frecuente.
# Clave: pdb_id. Valor: lista de nombres alternativos (español, INN, común).
TARGET_ALIASES_ES: dict[str, list[str]] = {
    "7E2Y": ["receptor de serotonina", "receptor 5-ht1a", "5ht1a", "serotonina",
             "receptor serotoninergico 5-ht1a", "5-ht1a"],
    "6PS2": ["receptor beta-adrenergico", "receptor beta 2 adrenergico",
             "beta-2 adrenergico", "adrenoreceptor beta-2", "beta2", "b2ar"],
    "6CM4": ["receptor opioide mu", "receptor de opioides mu", "mu-opioide",
             "receptor mu-opioide", "opioide"],
    "5TGZ": ["receptor canabinoide cb1", "receptor cannabinoid cb1", "cb1",
             "canabinoide cb1", "cannabinoide"],
    "4BVN": ["receptor de adenosina a2a", "a2a", "adenosina a2a", "receptor a2a"],
    "7DFL": ["receptor de histamina h1", "histamina h1", "receptor h1", "h1"],
    "6WHA": ["receptor muscarinico m2", "muscarinico m2", "m2"],
    "6X1A": ["receptor glp-1", "glp-1", "glp1", "receptor del peptido glucagon-like",
             "glp-1r"],
    "4NC3": ["receptor 5-ht2b", "5-ht2b", "serotonina 2b", "htr2b"],
    "5NDD": ["receptor de quimiocina ccr5", "ccr5", "quimiocina ccr5"],
    "6MEO": ["receptor de quimiocina cxcr4", "cxcr4", "quimiocina cxcr4"],
    "1M17": ["receptor egfr", "egfr", "receptor del factor de crecimiento epidermico",
             "erbb1", "her1"],
    "4FK3": ["braf", "braf v600e", "kinasa braf", "v600e"],
    "3PP0": ["cdk4", "quinasa dependiente de ciclina 4", "cdk4 ciclina d1"],
    "3WZE": ["vegfr2", "kdr", "receptor de vegf", "kinasa kdr", "receptor vegfr-2"],
    "3G0E": ["jak2", "quinasa jak2", "janus quinasa 2"],
    "2HZI": ["abl1", "kinasa abl", "bcr-abl", "imatinib"],
    "4BCF": ["pi3k delta", "pi3k-delta", "fosfoinositido 3-quinasa delta", "pi3kd"],
    "3GEN": ["vegfr2", "receptor vegfr2", "kinasa flk1", "kdr"],
    "5QTS": ["mek1", "kinasa mek1", "map2k1"],
    "4AUA": ["akt1", "proteina kinasa b", "pkb", "pkb/akt"],
    "3O96": ["akt1", "proteina kinasa b", "pkb", "kinasa akt1"],
    "3ERT": ["receptor de estrogeno alfa", "er-alpha", "er alfa", "receptor estrogenico alfa"],
    "2AM9": ["receptor de androgenos", "receptor androgenico", "ar", "androgenos"],
    "1X7R": ["ppar-gamma", "receptor gamma activado por proliferador de peroxisomas",
             "pparg", "ppar gamma"],
    "3DZY": ["receptor de glucocorticoides", "receptor glucocorticoide", "gr"],
    "4OIV": ["receptor de vitamina d", "vdr", "vitamina d receptor"],
    "3KJF": ["dpp-4", "dpp4", "dipeptidil peptidasa 4", "cd26"],
    "2JDI": ["trombina", "factor ii", "trombina coagulacion"],
    "4Y79": ["factor xa", "factor xa coagulacion", "fx"],
    "4DQC": ["bace-1", "beta-secretasa", "bace1", "enzima de clivaje amiloide"],
    "5TY1": ["mmp-9", "gelatinasa b", "metaloproteinasa 9", "mmp9"],
    "5I3T": ["ace2", "enzima convertidora de angiotensina 2"],
    "5EPN": ["renina", "renina proteasa"],
    "4CVL": ["furina", "proproteina convertasa furina"],
    "6LU7": ["mpro", "proteasa principal sars-cov-2", "3cl-pro", "sars-cov-2 mpro",
             "covid-19 proteasa", "coronavirus mpro"],
    "5RFY": ["ns3/4a", "proteasa ns3", "hcv ns3", "hepatitis c proteasa"],
    "1NHY": ["proteasa hiv-1", "hiv-1 proteasa", "hiv proteasa"],
    "5J89": ["pd-l1", "cd274", "ligando de muerte programada 1"],
    "6U26": ["pcsk9", "proproteina convertasa subtilisina/kexina tipo 9"],
    "1HWK": ["hmg-coa reductasa", "hmgcr", "reductasa de hmg-coa"],
    "5NN5": ["sglt2", "transportador de sodio-glucosa 2", "sglt-2"],
    "6HL1": ["fxr", "receptor farsenoide x", "receptor biliar fxr"],
    "5HYK": ["fasn", "sintasa de acidos grasos", "fatty acid synthase"],
    "6BOS": ["acc", "acetil-coa carboxilasa", "acc1"],
    "5TBO": ["hdac2", "histona deacetilasa 2", "histona desacetilasa 2"],
    "5LSH": ["brd4", "bromodominio bet", "bromodominio brd4"],
    "6G2O": ["ezh2", "metiltransferasa ezh2", "enhancer of zeste 2"],
    "4NY4": ["cyp3a4", "citocromo p450 3a4", "p450 3a4"],
    "5TFT": ["cyp2d6", "citocromo p450 2d6", "p450 2d6"],
    "4EJJ": ["cyp2c9", "citocromo p450 2c9", "p450 2c9"],
    "3QXX": ["cyp2c19", "citocromo p450 2c19", "p450 2c19"],
    "2NNJ": ["cyp1a2", "citocromo p450 1a2", "p450 1a2"],
    "6MVW": ["nav1.5", "canal de sodio nav1.5", "scn5a", "canal de sodio cardiaco"],
    "1SO2": ["pde3a", "fosfodiesterasa 3a", "pde3"],
    "4W1V": ["pde4b", "fosfodiesterasa 4b", "pde4"],
    "6N7B": ["pde5a", "fosfodiesterasa 5a", "pde5"],
    "6Y5E": ["receptor gaba-a", "gaba-a", "gabaa", "receptor de gaba"],
    "4I5H": ["cftr", "canal de cloro cftr", "regulador de conductancia transmembrana"],
    "1HVY": ["parp1", "parp", "polimerasa de poli-adp ribosa 1"],
    "6P3D": ["kras", "kras g12c", "oncogen kras"],
    "4PXZ": ["bcl-2", "bcl2", "apoptosis bcl-2"],
    "5F4W": ["mdm2", "mdm2-p53", "interaccion mdm2 p53"],
    "2XAB": ["hsp90", "proteina de choque termico 90", "hsp90 chaperona"],
    "6NTW": ["dhfr", "dihidrofolato reductasa"],
    "3SRW": ["adn girasa b", "adn girasa", "gyrb"],
    "4ZUD": ["mao-b", "monoamino oxidasa b", "maob"],
    "3L54": ["ache", "acetilcolinesterasa", "colinesterasa", "enzima acetilcolinesterasa"],
    "5WIU": ["sod1", "superoxido dismutasa 1", "superoxido dismutasa"],
    "6B3J": ["receptor de serotonina", "serotonina", "5-ht"],
    "5VA1": ["herg", "canal de potasio herg", "kcnh2"],
    "1GPK": ["acetilcolinesterasa", "ache", "colinesterasa"],
    "1HSG": ["proteasa hiv-1", "hiv-1 proteasa"],
    "1BN1": ["anhidrasa carbonica ii", "ca2", "anhidrasa carbonica 2"],
    "1XP0": ["pde5a", "fosfodiesterasa 5", "pde5"],
    "2P4E": ["pcsk9", "proproteina convertasa"],
    "6GUE": ["cdk2", "quinasa dependiente de ciclina 2"],
    "5Z2R": ["cdk6", "quinasa dependiente de ciclina 6"],
    "4E4N": ["alk", "quinasa alkl", "linfoma anaplasico kinasa"],
}


def _read_csv_aliases() -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    if not CSV_PATH.exists():
        return out
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = (row.get("pdb_id") or "").strip().upper()
            name = (row.get("name") or "").strip()
            if pid and name:
                out.setdefault(pid, []).append(name)
    return out


def _read_json_names() -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not JSON_PATH.exists():
        return out
    with open(JSON_PATH, encoding="utf-8") as f:
        for t in json.load(f):
            pid = (t.get("pdb_id") or "").strip().upper()
            if not pid:
                continue
            name = (t.get("name") or "").strip()
            fam = (t.get("structural_family") or "").strip()
            out[pid] = {"name": name, "family": fam}
    return out


def _pdb_files_for(pid: str) -> list[Path]:
    hits: list[Path] = []
    for base in (TARGETS_DIR, LIBRARY_DIR):
        if not base.is_dir():
            continue
        for variant in (pid, pid.lower(), pid.upper()):
            hits.extend(base.glob(f"**/{variant}.pdb"))
    return hits


def _read_pdb_synonyms(pid: str) -> list[str]:
    """Extract ONLY COMPND SYNONYM records (biological aliases)."""
    out: list[str] = []
    for f in _pdb_files_for(pid):
        try:
            with open(f, encoding="utf-8", errors="ignore") as pf:
                for line in pf:
                    if line.startswith("COMPND"):
                        m = re.search(r"SYNONYM:\s*(.+)", line, re.IGNORECASE)
                        if m:
                            for tok in m.group(1).split(","):
                                tok = tok.strip().strip(";")
                                cleaned = _clean_alias(tok)
                                if cleaned:
                                    out.append(cleaned)
        except OSError:
            continue
    return out


def main() -> int:
    csv_aliases = _read_csv_aliases()
    json_info = _read_json_names()

    entries: dict[str, dict] = {}
    for pid, info in json_info.items():
        aliases: list[str] = []

        # 1. CSV clean names (highest quality)
        aliases.extend(csv_aliases.get(pid, []))

        # 2. JSON short names (skip the raw pdb_id echo and long crystal titles)
        json_name = info.get("name") or ""
        if json_name and json_name != pid and len(json_name) <= 60:
            aliases.append(json_name)

        # 3. PDB COMPND SYNONYM records (biological names)
        pdb_syns = _read_pdb_synonyms(pid)
        for s in pdb_syns:
            if s not in aliases and s.lower() not in [a.lower() for a in aliases]:
                aliases.append(s)

        # 4. Curated Spanish/INN aliases
        aliases.extend(TARGET_ALIASES_ES.get(pid, []))

        # ── Corrección de datos conocidos ──────────────────────────────
        # 3O96: el CSV lo cataloga como "ER-alpha LBD Unbound" pero el PDB
        # real es AKT1 (RAC-PK-ALPHA / PROTEIN KINASE B). Los ER-alpha reales
        # son 3ERT/5L2I/4JPS. Eliminamos el alias erróneo del CSV para no
        # resolver "receptor de estrogeno" hacia AKT1.
        if pid == "3O96":
            aliases = [
                a for a in aliases
                if "ER-alpha" not in a and "Estrogen" not in a and "estrogeno" not in a.lower()
            ]

        # Dedupe (case-insensitive), keep original case of first occurrence
        seen: set[str] = set()
        unique: list[str] = []
        for a in aliases:
            key = _norm(a)
            if key and key not in seen:
                seen.add(key)
                unique.append(a)

        entries[pid] = {
            "pdb_id": pid,
            "name": info.get("name") or (unique[0] if unique else pid),
            "family": info.get("family") or "",
            "has_structure": bool(_pdb_files_for(pid)),
            "aliases": unique,
        }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(list(entries.values()), f, ensure_ascii=False, indent=2)

    n_structure = sum(1 for e in entries.values() if e["has_structure"])
    n_with_alias = sum(1 for e in entries.values() if len(e["aliases"]) > 0)
    n_es = sum(1 for pid in entries if pid in TARGET_ALIASES_ES)
    print(f"Wrote {OUT_PATH}")
    print(f"Targets:        {len(entries)}")
    print(f"With structure: {n_structure}")
    print(f"With aliases:   {n_with_alias}")
    print(f"Curated es:     {n_es}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
