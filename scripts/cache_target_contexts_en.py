"""Cache original RCSB/UniProt prose for offline English reports (explicit --fetch)."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "backend/data/target_contexts_en.json"
BASE = "https://data.rcsb.org/rest/v1/core"


def fetch(url):
    with urlopen(url, timeout=30) as response:
        raw = response.read()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def context(row):
    pdb = row["pdb_id"].upper()
    try:
        entry, entry_digest = fetch(f"{BASE}/entry/{pdb}")
        ids = entry["rcsb_entry_container_identifiers"].get("polymer_entity_ids", [])
        for entity_id in ids:
            entity, _ = fetch(f"{BASE}/polymer_entity/{pdb}/{entity_id}")
            chains = entity["rcsb_polymer_entity_container_identifiers"].get("auth_asym_ids", [])
            if row["chain"] not in chains:
                continue
            url = f"{BASE}/uniprot/{pdb}/{entity_id}"
            try:
                records, digest = fetch(url)
            except HTTPError as error:
                if error.code != 404:
                    raise
                records = []
            functions = []
            accessions = []
            for record in records:
                function = record.get("rcsb_uniprot_protein", {}).get("function", {}).get("details")
                if function and function not in functions:
                    functions.append(function)
                    accessions.append(record["rcsb_id"])
            if functions:
                return pdb, {
                    "description": "\n\n".join(functions), "kind": "uniprot_function",
                    "source_url": url, "response_sha256": digest,
                    "uniprot_accessions": accessions, "entity_id": entity_id,
                    "chain": row["chain"], "catalog_description": row.get("description"),
                }
            break
        return pdb, {"description": entry["struct"]["title"], "kind": "structure_title",
                     "source_url": f"{BASE}/entry/{pdb}", "response_sha256": entry_digest, "chain": row["chain"],
                     "catalog_description": row.get("description")}
    except Exception as error:
        return pdb, {"error": f"{type(error).__name__}: {error}"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true", required=True)
    parser.parse_args()
    rows = json.loads((ROOT / "curated_targets.json").read_text(encoding="utf-8"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = dict(pool.map(context, rows))
    errors = {p: r for p, r in records.items() if "error" in r}
    output = {"schema": 1, "retrieved_at": datetime.now(timezone.utc).isoformat(),
              "contexts": dict(sorted(records.items()))}
    print(json.dumps({"total": len(records), "errors": errors,
                      "functions": sum(r.get("kind") == "uniprot_function" for r in records.values())}))
    if errors:
        return 1  # Keep the previous offline cache intact on a partial fetch.
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
