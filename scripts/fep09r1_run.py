"""FEP-09-R1: la misma ruta por API que FEP-09 (upload B → preflight → Vina → result → Preparación).

Cada caso lo ejecuta `fep09_run.run_case`, sin cambios; este archivo sólo cambia dónde se escribe, qué
producto y qué prerregistro se exigen, y la etiqueta de cada fila. No importa el producto.

    python scripts/fep09r1_run.py --capsule DIR (--shard 0|1|2 | --pilot)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

import fep09_run
from fep09_inputs import PLB_COMMIT, write_json
from fep09_run import API, append_json, run_case

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "scripts/artifacts_science/FEP-09-R1"
EXPERIMENTO = "FEP-09-R1"
#: El piloto: un caso de FEP-09 cuyo origen no se reconocía, y una línea base y una variante nuevas.
PILOTO = ("cdk2__baseline__0", "cdk8__baseline_estereo__1", "cdk8__estereo_sin_asignar__1")


def condiciones() -> dict:
    """Lo registrado antes de medir, más el commit que lo registró (un archivo no lleva su propio hash)."""
    registro = ART / "registered_conditions.json"
    datos = json.loads(registro.read_text(encoding="utf-8"))
    commit = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", str(registro.relative_to(ROOT))],
                                     cwd=ROOT, text=True).strip()
    if not commit or subprocess.check_output(["git", "status", "--porcelain", "--", str(registro.relative_to(ROOT))],
                                             cwd=ROOT, text=True).strip():
        raise SystemExit("El registro de condiciones no está commiteado: se mide sólo lo registrado antes")
    return {**datos["preregistration"], "product_commit": datos["product_under_test"]["commit"], "commit": commit}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plb", type=Path, default=Path("E:/MolDesign-science/openff-plb"))
    ap.add_argument("--capsule", type=Path, required=True)
    ap.add_argument("--shard", type=int, choices=(0, 1, 2))
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--task-timeout", type=float, default=3600)
    args = ap.parse_args()
    if not args.pilot and args.shard is None:
        ap.error("requiere --pilot o --shard")
    if subprocess.check_output(["git", "-C", str(args.plb), "rev-parse", "HEAD"], text=True).strip() != PLB_COMMIT:
        raise SystemExit("Benchmark modificado")
    reg = condiciones()
    producto = reg["product_commit"]
    if subprocess.check_output(["git", "diff", producto, "--", "backend", "frontend", "rescoring", "tools"], cwd=ROOT):
        raise SystemExit(f"Producto modificado respecto a {producto}")
    if hashlib.sha256((ART / "inventory.json").read_bytes()).hexdigest() != reg["inventory_sha256"]:
        raise SystemExit("Inventario difiere del prerregistro")
    plan = json.loads((ART / "inventory.json").read_text(encoding="utf-8"))
    systems = {s["target"]: s for s in plan["systems"]}
    if args.pilot:
        cases = [c for c in plan["cases"] if c["case_id"] in PILOTO]
    else:
        targets = [s["target"] for i, s in enumerate(plan["systems"]) if i % 3 == args.shard]
        cases = [c for c in plan["cases"] if c["target"] in targets]
    dest = ART / "_work" / ("pilot" if args.pilot else f"shard-{args.shard}")
    dest.mkdir(parents=True, exist_ok=True)
    terminal, failures = dest / "per_complex.jsonl", dest / "failures.jsonl"
    terminal.touch(exist_ok=True)
    failures.touch(exist_ok=True)
    existing = [json.loads(line) for line in terminal.read_text(encoding="utf-8").splitlines() if line]
    done = {row["case_id"] for row in existing}
    failed, attempted = sum(r["outcome"] == "infrastructure_failure" for r in existing), len(existing)
    api = API(args.capsule / "manifest.json")
    manifest = json.loads((args.capsule / "manifest.json").read_text(encoding="utf-8"))
    write_json(dest / "capsule_conditions.json", {k: manifest.get(k) for k in (
        "repositorio", "puertos", "vina_cpu", "runtime_compartido", "export",
        "desviaciones_respecto_a_la_app_instalada", "autoverificacion")})
    if attempted and failed / attempted > .30:
        raise SystemExit("PARADA previa: infraestructura >30%; no se reintenta ni sobrescribe")
    # `run_case` escribe la evidencia relativa a la raíz de SU módulo; es la misma raíz.
    assert fep09_run.ROOT == ROOT
    for case in cases:
        if case["case_id"] in done:
            continue
        row = run_case(api, args.plb.resolve(), systems[case["target"]], case, dest, args.capsule / "tmp/inputs",
                       args.task_timeout)
        # `run_case` etiqueta con el producto y el prerregistro de FEP-09; aquí se corrigen.
        row.update(experiment=EXPERIMENTO, product_commit=producto, preregistration_commit=reg["commit"])
        append_json(terminal, row)
        attempted += 1
        if row["outcome"] == "infrastructure_failure":
            append_json(failures, row)
            failed += 1
        print(json.dumps({"case": case["case_id"], "outcome": row["outcome"], "elapsed_s": row["elapsed_s"],
                          "global": row["global_state"], "error": row.get("error")}, ensure_ascii=False), flush=True)
        if failed / attempted > .30:
            write_json(dest / "stop.json", {"reason": "infraestructura supera 30%", "failed": failed, "attempted": attempted})
            return 2
    write_json(dest / "complete.json", {"attempted": attempted, "failed": failed, "pilot": args.pilot,
                                        "cases": [c["case_id"] for c in cases]})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
