"""MolFlex V1 — feasibility on the 74 redock-timeout complexes.

Pre-registered: docs/40_MOLFLEX_PROTOCOL.md
Success criterion: >=90% of complexes complete in <120s (vs 300s flexible timeout).

Per complex: ETKDG ensemble of 15 conformers -> rigid dock each (single ROOT
PDBQT, TORSDOF 0) -> report best score, total time, per-conformer times.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
VINA = PROJECT_ROOT / "tools" / "vina" / "vina.exe"
N_CONF = 15

sys.path.insert(0, str(PROJECT_ROOT / "rescoring" / "scripts"))
import redock_pdbbind as rp  # noqa: E402


def make_rigid_pdbqt(sdf_path: Path, out_path: Path, n_conf: int) -> list[int]:
    """ETKDG ensemble -> one rigid PDBQT per conformer (all atoms under ROOT)."""
    from rdkit import Chem, RDLogger
    from rdkit.Chem import AllChem
    from meeko import MoleculePreparation, PDBQTWriterLegacy

    RDLogger.logger().setLevel(RDLogger.ERROR)
    m = Chem.MolFromMolFile(str(sdf_path))
    if m is None:
        m = Chem.MolFromMolFile(str(sdf_path), sanitize=False, removeHs=False)
    if m is None:
        return []
    m = Chem.AddHs(m)
    try:
        ids = list(AllChem.EmbedMultipleConfs(
            m, numConfs=n_conf, randomSeed=42,
            useExpTorsionAnglePrefs=True, useBasicKnowledge=True,
            pruneRmsThresh=0.5, numThreads=0,
        ))
    except Exception:
        return []

    prep = MoleculePreparation()
    written = []
    for cid in ids:
        try:
            setups = prep.prepare(m, conformer_id=cid)
            s, ok, _ = PDBQTWriterLegacy.write_string(setups[0])
            if not ok or not s:
                continue
            atoms = [l for l in s.splitlines() if l.startswith(("ATOM", "HETATM"))]
            rigid = "\n".join(["ROOT"] + atoms + ["ENDROOT", "TORSDOF 0"]) + "\n"
            p = out_path / f"conf{cid}.pdbqt"
            p.write_text(rigid)
            written.append(cid)
        except Exception:
            continue
    return written


def rigid_dock_one(args) -> tuple[str, dict]:
    pid, rec_pdbqt, lig_pdbqt, center = args
    out = Path(lig_pdbqt).with_suffix(".out.pdbqt")
    t0 = time.time()
    r = subprocess.run(
        [str(VINA), "--receptor", rec_pdbqt, "--ligand", lig_pdbqt,
         "--center_x", str(center[0]), "--center_y", str(center[1]),
         "--center_z", str(center[2]),
         "--size_x", "25", "--size_y", "25", "--size_z", "25",
         "--exhaustiveness", "8", "--num_modes", "9", "--cpu", "2",
         "--out", str(out)],
        capture_output=True, text=True, timeout=240,
    )
    dt = time.time() - t0
    if r.returncode != 0:
        return pid, {"ok": False, "reason": f"rc={r.returncode}", "t": dt}
    scores = [float(x.split()[1]) for x in r.stdout.splitlines()
              if len(x.split()) >= 2 and x.split()[0].isdigit()]
    if not scores:
        return pid, {"ok": False, "reason": "no_scores", "t": dt}
    return pid, {"ok": True, "best": scores[0], "t": dt}


def work_one(pid: str, n_conf: int) -> dict:
    d = PDBBIND / pid
    work = Path(tempfile.mkdtemp(prefix=f"molflex_{pid}_"))
    try:
        rec = str(work / "rec.pdbqt")
        if not rp.prepare_receptor_pdbqt(str(d / f"{pid}_protein.pdb"), rec):
            return {"pdb_id": pid, "ok": False, "reason": "receptor_prep_failed"}
        center = rp.find_binding_center(str(d / f"{pid}_ligand.sdf"))
        if center is None:
            return {"pdb_id": pid, "ok": False, "reason": "binding_center_failed"}

        conf_dir = work / "confs"
        conf_dir.mkdir()
        cids = make_rigid_pdbqt(d / f"{pid}_ligand.sdf", conf_dir, n_conf)
        if not cids:
            return {"pdb_id": pid, "ok": False, "reason": "no_conformers",
                    "n_conf": 0, "n_docked_ok": 0, "best_score": None,
                    "total_time_s": 0.0, "per_conf_time_s": 0.0}

        t0 = time.time()
        jobs = [(pid, rec, str(conf_dir / f"conf{c}.pdbqt"), center) for c in cids]
        results = []
        # Topologia corregida (2026-08-13): cpu=1 por Vina + 8 docks paralelos
        # por complejo + 2 complejos = 16 hilos... no: rigid_dock_one usa cpu=2.
        # Para no oversubscribir 12 cores: 2 complejos x 3 docks x cpu2 = 12 hilos.
        with ProcessPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(rigid_dock_one, j) for j in jobs]
            for f in as_completed(futs):
                try:
                    results.append(f.result())
                except Exception as e:  # noqa: BLE001
                    results.append((pid, {"ok": False, "reason": type(e).__name__, "t": 0.0}))
        oks = [r for _, r in results if r["ok"]]
        total = time.time() - t0
        return {
            "pdb_id": pid,
            "ok": len(oks) > 0,
            "n_conf": len(cids),
            "n_docked_ok": len(oks),
            "best_score": min((r["best"] for r in oks), default=None),
            "total_time_s": round(total, 1),
            "per_conf_time_s": round(total / max(len(cids), 1), 1),
        }
    finally:
        import shutil
        shutil.rmtree(work, ignore_errors=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--out", type=str, default="artifacts_molflex_v1.json")
    args = ap.parse_args()

    failures = sorted(json.loads(
        (PDBBIND / "vina_redock_cache" / "redock_failures.json").read_text()
    ))
    subset = failures[: args.limit]
    print(f"V1: {len(subset)} complejos (de los 74 timeout) | {N_CONF} conf rigidos c/u")

    results = []
    out_path = Path(args.out)
    # escribir incrementalmente: cada resultado al archivo (resumible)
    existing = []
    if out_path.exists():
        try:
            existing = json.loads(out_path.read_text()).get("results", [])
        except Exception:
            existing = []
    done_ids = {r["pdb_id"] for r in existing}
    subset = [p for p in subset if p not in done_ids]
    if not subset:
        print("Todos los complejos ya procesados.")
        return
    results = existing

    t0 = time.time()
    with ProcessPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(work_one, pid, N_CONF): pid for pid in subset}
        for f in as_completed(futs):
            r = f.result()
            results.append(r)
            out_path.write_text(json.dumps({
                "n": len(results), "results": results,
            }, indent=2))
            status = f"{r['best_score']:.1f}" if r["ok"] else f"FAIL:{r.get('reason')}"
            print(f"  {r['pdb_id']}: {status} | {r['total_time_s']}s "
                  f"({r['n_docked_ok']}/{r['n_conf']} docks)", flush=True)
    total = time.time() - t0

    ok = [r for r in results if r["ok"]]
    frac_ok = len(ok) / max(len(results), 1)
    under_120 = [r for r in results if r["ok"] and r["total_time_s"] < 120]
    print(f"\nV1: {len(ok)}/{len(results)} completaron ({frac_ok:.0%})")
    print(f"  <120s: {len(under_120)}/{len(results)} | tiempo total batch: {total:.0f}s")
    print(f"  Criterio pre-registrado: >=90% en <120s -> "
          f"{'PASS' if len(under_120) / max(len(results), 1) >= 0.9 else 'NO PASS'}")

    Path(args.out).write_text(json.dumps({
        "n": len(results), "frac_ok": frac_ok,
        "n_under_120s": len(under_120), "batch_time_s": round(total, 1),
        "results": results,
    }, indent=2))


if __name__ == "__main__":
    main()
