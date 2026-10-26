"""Reproduce una entrada fuera del experimento sellado, con una cápsula nueva."""
import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from fep09_inputs import PLB_COMMIT, write_json
from fep09_run import API, ART, ROOT, run_case

ap = argparse.ArgumentParser()
ap.add_argument("--case", required=True)
ap.add_argument("--capsule", type=Path, required=True)
ap.add_argument("--plb", type=Path, default=Path("E:/MolDesign-science/openff-plb"))
args = ap.parse_args()
if subprocess.check_output(["git", "-C", str(args.plb), "rev-parse", "HEAD"], text=True).strip() != PLB_COMMIT:
    raise SystemExit("Clon PLB diferente del sellado")
if subprocess.check_output(["git", "diff", "f183e0af", "--", "backend", "frontend", "rescoring", "tools"], cwd=ROOT):
    raise SystemExit("Producto distinto de f183e0af")
plan = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
case = next(c for c in plan["cases"] if c["case_id"] == args.case)
system = next(s for s in plan["systems"] if s["target"] == case["target"])
stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
dest = ROOT / "tmp/fep09-reproductions" / (stamp+"_"+case["case_id"])
dest.mkdir(parents=True, exist_ok=False)
row = run_case(API(args.capsule / "manifest.json"), args.plb.resolve(), system, case, dest, args.capsule / "tmp/reproduce", 3600)
row["phase"] = "independent_reproduction"
write_json(dest / "result.json", row)
print(json.dumps({"output": str(dest), "outcome": row["outcome"], "global_state": row["global_state"], "task_id": row["task_id"]}))
raise SystemExit(0 if row["outcome"] == "audited" else 1)
