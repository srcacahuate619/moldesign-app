"""DEC-104-D06-8HFI. Ejecuta y analiza cuatro brazos mediante la API local."""
import argparse
import csv
import gzip
import hashlib
import json
import math
import os
import random
import sys
import time
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))
import calibracion_receptor as cal

ID = "DEC-104-D06-8HFI"
ART = ROOT / "scripts" / "artifacts_science" / ID
SOURCE = ART / "entrada"
ARMS = {"e8": (8, 42), "e8s43": (8, 43), "e16": (16, 42), "e32": (32, 42)}
BOX = ([100.281, 100.843, 101.442], [30.0, 30.0, 30.0])


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_inputs():
    manifest = json.loads((ART / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["sealed"] and manifest["status"] != "finished"
    for file, value in manifest["dataset_hashes"].items():
        assert digest((ROOT / file).read_bytes()) == value, file
    assert digest(Path(__file__).read_bytes()) == digest((SOURCE / "medir_d06.py").read_bytes())
    records = json.loads((SOURCE / "base.json").read_text(encoding="utf-8"))
    for file, value in records.items():
        assert digest((ROOT / file).read_bytes().replace(b"\r\n", b"\n") if not file.endswith(".exe")
                      else (ROOT / file).read_bytes()) == value, file


def cases():
    with (SOURCE / "panel.csv").open(encoding="utf-8", newline="") as f:
        panel = list(csv.DictReader(f))
    assert len(panel) == 57
    out = []
    protocol = json.loads((SOURCE / "cal-8hfi-protocolo.json").read_text(encoding="utf-8"))
    crystal_state = protocol["verificacion"]["ligando_cristal"]["smiles_acoplado_esperado"]
    for arm, (exhaust, seed) in ARMS.items():
        for row in panel:
            out.append((arm, row["padre"], row["smiles"], row["smiles_acoplado_esperado"], float(row["pki"]), exhaust, seed))
        if arm != "e8s43":
            out += [(arm, f"DSM-{s}", cal.SMILES_CRISTAL, crystal_state, None, exhaust, s) for s in cal.SEMILLAS_REDOCKING]
    random.Random(20261114).shuffle(out)
    return out


def evaluate(api, smiles, exhaust, seed, name):
    g = api.gate
    config = json.loads(json.dumps(cal.CONFIG_CASO))
    config["stage_params"]["docking"] = {"exhaustiveness": exhaust, "num_poses": 9, "seed": seed}
    common = {"smiles": smiles, "target_pdb_id": "8HFI", "chain": "A"}
    pre = g._json(api.base, "POST", "/evaluation/preflight", token=api.token, timeout=180, body={
        **common, "docking_engine": "vina", "exhaustiveness": exhaust, "num_poses": 9,
        "conformers": 1, "pipeline_config": config,
    })
    if pre.get("technical_blockers"):
        raise RuntimeError(f"Preflight: {pre['technical_blockers']}")
    effective = pre["effective_config"]
    if (effective["grid_center"], effective["grid_size"]) != BOX:
        raise RuntimeError(f"Caja efectiva distinta: {effective['grid_center']} / {effective['grid_size']}")
    response = g._json(api.base, "POST", "/evaluation/submit", token=api.token, expected={202}, body={
        **common, "molecule_name": name, "grid_center": effective["grid_center"], "grid_size": effective["grid_size"],
        "pipeline_config": config, "preflight_fingerprint": pre["input_fingerprint"],
    })
    task_id = response["task_id"]
    deadline = time.monotonic() + 1200
    while time.monotonic() < deadline:
        state = g._json(api.base, "GET", f"/evaluation/status/{task_id}", token=api.token)
        status = state.get("status")
        if status == "SUCCESS":
            break
        if status in {"FAILURE", "REVOKED"}:
            raise RuntimeError(f"Corrida {status}: {str(state)[:800]}")
        time.sleep(1)
    else:
        raise TimeoutError(task_id)
    result = state["result"]
    _, poses, _ = g._request(api.base, "GET", f"/evaluation/files/poses/{result['molecule_id']}", token=api.token)
    return {"task_id": task_id, "resultado": result, "poses_sdf": poses.decode("utf-8")}


def extract(raw, expected_state, exhaust, seed, ref):
    from rdkit.Chem import rdMolAlign

    result = raw["resultado"]
    dp = result["docking_protocol"]
    prov = dp["execution_provenance"]
    if (dp["exhaustiveness"], dp["num_poses"], dp["seed"], prov["cpu"], result["vina_version"]) != (
            exhaust, 9, seed, 4, "1.2.7"):
        raise ValueError(f"Configuración divergente: {dp}")
    ligand = result["ligand_state"]["smiles_acoplado"]
    if ligand != expected_state:
        raise ValueError(f"Microestado divergente: {ligand!r} / {expected_state!r}")
    mol, energy, matches = cal._top1(raw)
    if not matches or not math.isfinite(energy):
        raise ValueError("Energía o mapeo SDF–PDBQT inválido")
    top = next((p for p in result["structural_evidence"]["poses"] if p.get("rank") == 1), {})
    return {
        "energia_kcal": energy, "receptor_sha256": prov["receptor_sha256"], "hilos": prov["cpu"],
        "receta": prov.get("receta_receptor"), "microestado": ligand, "posebusters": top.get("status"),
        "rmsd": rdMolAlign.CalcRMS(cal._neutro_sin_h(mol), ref) if ref is not None else None,
    }


def run(args):
    check_inputs()
    os.environ["VINA_CPU"] = "4"
    args.datos.mkdir(parents=True, exist_ok=True)
    output = args.datos / "corridas"
    output.mkdir(exist_ok=True)
    work = []
    for index, job in enumerate(cases()):
        if index % args.shards == args.shard - 1:
            stem = f"{job[0]}-{job[1]}"
            path = output / f"{stem}.json"
            if not path.exists():
                work.append((job, stem, path))
    if not work:
        return
    ref = cal._neutro_sin_h(cal._cristal()[0])
    with cal.Backend(args.datos / f"api-{args.shard}") as api:
        for (arm, entity, smiles, state, pki, exhaust, seed), stem, path in work:
            attempts = []
            row = {
                "brazo": arm, "padre": entity, "pki": pki, "exhaustividad": exhaust,
                "semilla": seed, "intentos": attempts,
            }
            for _ in range(2):
                start = time.monotonic()
                try:
                    raw = evaluate(api, smiles, exhaust, seed, stem)
                    raw_path = output / f"{stem}.json.gz"
                    compressed = gzip.compress(json.dumps(raw).encode(), mtime=0)
                    raw_path.write_bytes(compressed)
                    observed = extract(raw, state, exhaust, seed, ref if pki is None else None)
                    row.update(observed, estado="SUCCESS", raw_sha256=digest(compressed))
                except Exception as exc:
                    attempts.append({"segundos": time.monotonic() - start, "error": f"{type(exc).__name__}: {exc}"})
                    continue
                attempts.append({"segundos": time.monotonic() - start})
                break
            else:
                row["estado"] = "FALLO"
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
            tmp.replace(path)
            print(stem, row["estado"], round(sum(x["segundos"] for x in attempts), 1), flush=True)


def rho(x, y):
    a, b = rankdata(x, axis=-1), rankdata(y, axis=-1)
    a -= a.mean(axis=-1, keepdims=True)
    b -= b.mean(axis=-1, keepdims=True)
    return (a * b).sum(axis=-1) / np.sqrt((a * a).sum(axis=-1) * (b * b).sum(axis=-1))


def analyze(args):
    out = {}
    for arm, key, *_ in cases():
        path = args.datos / "corridas" / f"{arm}-{key}.json"
        if path.exists():
            out[arm, key] = json.loads(path.read_text(encoding="utf-8"))
    failed = [f"{arm}/{key}" for arm, key, *_ in cases() if out.get((arm, key), {}).get("estado") != "SUCCESS"]
    receptor = sorted({r["receptor_sha256"] for r in out.values() if r["estado"] == "SUCCESS"})
    detail = {}
    sample = {}
    common = sorted({k for a, k in out if a == "e8" and out[a, k]["pki"] is not None
                     and all(out.get((b, k), {}).get("estado") == "SUCCESS" for b in ARMS)})
    if len(common) > 2:
        boot = np.random.default_rng(20261025).integers(len(common), size=(10000, len(common)))
        y = np.array([out["e8", k]["pki"] for k in common])
        for arm in ARMS:
            x = np.array([-out[arm, k]["energia_kcal"] for k in common])
            sample[arm] = rho(x[boot], y[boot])
            detail[arm] = {"rho": float(rho(x, y)), "ic95": np.quantile(sample[arm], [.025, .975]).tolist()}
    for arm in ARMS:
        r = [v for (a, _), v in out.items() if a == arm]
        poses = [v for v in r if v["pki"] is None and v["estado"] == "SUCCESS"]
        detail.setdefault(arm, {}).update(
            n_terminados=len(r), tiempos_s=sum(t["segundos"] for v in r for t in v["intentos"]),
            median_s=float(np.median([sum(t["segundos"] for t in v["intentos"]) for v in r])) if r else None,
            redock_ok=sum(v["rmsd"] <= 2 and v["posebusters"] == "passed" for v in poses),
            redock_bajo2_no_valido=sum(v["rmsd"] <= 2 and v["posebusters"] != "passed" for v in poses),
        )
    report = {
        "decision": "INCONCLUSIVE", "n_pareados": len(common), "fallos_o_ausentes": failed,
        "receptor_sha256": receptor, "brazos": detail,
    }
    if sample:
        interval = np.quantile(sample["e32"] - sample["e8"], [.025, .975]).tolist()
        report.update(delta_rho=detail["e32"]["rho"] - detail["e8"]["rho"], ic95_delta=interval,
                      ruido_semilla=detail["e8s43"]["rho"] - detail["e8"]["rho"])
        pose_ok = all(detail[a]["redock_ok"] >= 3 and detail[a]["redock_bajo2_no_valido"] == 0 for a in ("e8", "e32"))
        if not failed and len(receptor) == 1 and pose_ok:
            if interval[0] > .10:
                report["decision"] = "GO"
            elif (-.10 < interval[0] and interval[1] < .10) or interval[1] < 0:
                report["decision"] = "NO_GO"
    print(json.dumps(report, indent=2))
    if args.archivar:
        if json.loads((ART / "procedencia.json").read_text(encoding="utf-8"))["salidas"]:
            raise SystemExit("Experimento ya cerrado")
        (ART / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        (ART / "per_complex.jsonl").write_text("".join(json.dumps(row) + "\n" for _, row in sorted(out.items())), encoding="utf-8")
        (ART / "failures.jsonl").write_text("".join(json.dumps({"esperado": case}) + "\n" for case in failed), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modo", choices=("ejecutar", "analizar"))
    parser.add_argument("datos", type=Path)
    parser.add_argument("--shards", type=int, default=3)
    parser.add_argument("--shard", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--archivar", action="store_true")
    ns = parser.parse_args()
    (run if ns.modo == "ejecutar" else analyze)(ns)
