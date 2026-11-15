"""Aplica el criterio firmado de D-09 a los dos dictámenes de las 44 filas."""
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "77aeb73775fd334a24bbe5e3e7382dd2d456379e"


def main():
    panel = json.loads(subprocess.check_output(["git", "show", f"{BASE}:backend/data/anti_dianas_bowes44.json"], cwd=ROOT))
    revision_a = (HERE / "D09-ampliacion-A.md").read_text(encoding="utf-8")
    revision_b = (HERE / "D09-ampliacion-B.md").read_text(encoding="utf-8")
    a = dict(re.findall(r"^\|\s*\d+\s*·\s*([A-Z0-9]+)\s*\|[^|]+\|\s*\*\*([ABCU])\*\*", revision_a, re.M))
    b = dict(re.findall(r"^\|\s*([A-Z0-9]+)\s*/[^|]*\|\s*\*\*([ABCU])\*\*", revision_b, re.M))
    if len(a) != 35 or a.keys() != b.keys():
        raise ValueError("Las dos revisiones de ampliación deben cubrir las mismas 35 filas")
    a.update(HTR2B="A", KCNH2="A", SCN5A="C", CACNA1C="A", GABRA1="A", PTGS2="A", PDE3A="A", CHRNA4="U", KV="U")
    b.update({k: a[k] for k in set(a) - set(b)})
    rows = [
        {"fila": i, "ensayo": row["assay"], "gen": row.get("gen"), "pdb_id": row.get("pdb_id"),
         "A": a[gen], "B": b[gen], "vigente": row.get("sitio_adjudicado"),
         "propuesta": a[gen] == b[gen] == "A" if row.get("sitio_adjudicado") is not None else None}
        for i, row in enumerate(panel["dianas"], 1) for gen in (row.get("gen") or "KV",)
    ]
    assert len(rows) == 44
    total = Counter(r["A"] + "/" + r["B"] for r in rows)
    source = json.loads(subprocess.check_output(["git", "show", f"{BASE}:curated_targets.json"], cwd=ROOT))
    catalog = [
        {"pdb_id": row["pdb_id"], "site_evidence": row.get("site_evidence"),
         "hotspots_source": row.get("hotspots_source"),
         "centro_A": [row.get(f"grid_center_{axis}") for axis in "xyz"],
         "tamano_A": [row.get(f"grid_size_{axis}") for axis in "xyz"]}
        for row in source if not row.get("site_ligand")
    ]
    metadata = {"base": BASE, "resumen_dictamenes": dict(total), "filas": rows,
                "catalogo_general_sin_ligando": catalog}
    print(json.dumps(metadata, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
