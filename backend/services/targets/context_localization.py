"""Original English catalogue annotations, available without network access."""
from functools import lru_cache
import json
from pathlib import Path

from core.i18n import current_locale


@lru_cache(maxsize=1)
def _contexts():
    path = Path(__file__).resolve().parents[2] / "data/target_contexts_en.json"
    return json.loads(path.read_text(encoding="utf-8"))["contexts"]


def physiological_description(target):
    description = target.description
    if current_locale() != "en" or getattr(target, "is_private", False):
        return description
    record = _contexts().get((target.pdb_id or "").upper(), {})
    # Only replace the exact catalogue annotation for the same chain. Free text
    # entered by a researcher must survive even when it is written in Spanish.
    if record.get("catalog_description") != description or record.get("chain") != target.chain:
        return description
    original = record.get("description")
    if record.get("kind") == "structure_title" and original:
        return "Physiological annotation unavailable. Deposited structure title: " + original
    return original or description
