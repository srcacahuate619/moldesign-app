"""
scripts/calibrate_redock.py

Calibración acotada del pipeline de re-docking de PDBbind.

Ejecuta el pipeline de `rescoring/scripts/redock_pdbbind.py` (preparación
de receptor y ligando, centro del sitio, Vina) sobre los primeros N
complejos SIN cache, uno por uno, midiendo tiempos y tasas de éxito.

IMPORTANTE: NO escribe en `data/pdbbind/vina_redock_cache/`. Los
resultados van a un directorio temporal (`--output-dir`) que se elimina
al terminar, salvo que se pase `--keep`.

Con los tiempos medidos se extrapola el ETA del redock completo:
300 complejos a 6 workers.

Acotación:
  - Presupuesto global duro: 15 minutos (configurable con --budget-min).
    Al agotarse, se reportan los resultados parciales honestamente.
  - Timeouts por subproceso: preparación de receptor 60s (interno en
    redock_pdbbind), Vina 180s por complejo. La preparación de ligando
    es en proceso (RDKit+Meeko), sin subproceso que limitar.

Uso:
  python scripts/calibrate_redock.py [--data-dir ...] [--vina-path ...]
      [--max-complexes 10] [--budget-min 15] [--keep]
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "rescoring" / "scripts"))

import redock_pdbbind as rp  # noqa: E402

# Tamaño de caja y parámetros de Vina idénticos a redock_pdbbind.py.
BOX_SIZE = "25"
EXHAUSTIVENESS = "8"
NUM_MODES = "9"
VINA_TIMEOUT = 180  # segundos por complejo (calibración acotada)
BUDGET_MIN = 15  # presupuesto global duro en minutos


def discover_complexes(data_dir: Path, limit: int) -> list[tuple[str, Path, Path]]:
    """Descubre complejos sin cache, misma lógica que redock_pdbbind.main()."""
    cache_dir = data_dir / "vina_redock_cache"
    complexes = []
    for d in sorted(data_dir.iterdir()):
        if not d.is_dir():
            continue
        pdb = d / f"{d.name}_protein.pdb"
        sdf = d / f"{d.name}_ligand.sdf"
        if pdb.exists() and sdf.exists():
            cache_file = cache_dir / f"{d.name}.json"
            if not cache_file.exists():
                complexes.append((d.name, pdb, sdf))
                if len(complexes) >= limit:
                    break
    return complexes


def parse_scores(stdout: str) -> list[float]:
    """Parsea scores de la salida de Vina, igual que run_vina_redocking."""
    scores = []
    for line in stdout.split("\n"):
        parts = line.strip().split()
        if len(parts) >= 4 and parts[0].isdigit():
            try:
                scores.append(float(parts[1]))
            except ValueError:
                continue
    return scores


def run_one(
    pdb_id: str, pdb: Path, sdf: Path, vina_path: str, work_dir: Path
) -> dict:
    """Ejecuta el pipeline completo para un complejo, midiendo cada etapa."""
    work_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    timings: dict[str, float] = {}

    t = time.monotonic()
    rec_ok = rp.prepare_receptor_pdbqt(str(pdb), str(work_dir / f"{pdb_id}_rec.pdbqt"))
    timings["rec_prep"] = time.monotonic() - t

    t = time.monotonic()
    lig_ok = rp.prepare_ligand_pdbqt(str(sdf), str(work_dir / f"{pdb_id}_lig.pdbqt"))
    timings["lig_prep"] = time.monotonic() - t

    center = rp.find_binding_center(str(sdf))

    vina_ok = False
    vina_stdout = ""
    if rec_ok and lig_ok and center is not None:
        out_pdbqt = work_dir / f"{pdb_id}_out.pdbqt"
        cmd = [
            vina_path,
            "--receptor", str(work_dir / f"{pdb_id}_rec.pdbqt"),
            "--ligand", str(work_dir / f"{pdb_id}_lig.pdbqt"),
            "--center_x", str(center[0]),
            "--center_y", str(center[1]),
            "--center_z", str(center[2]),
            "--size_x", BOX_SIZE,
            "--size_y", BOX_SIZE,
            "--size_z", BOX_SIZE,
            "--exhaustiveness", EXHAUSTIVENESS,
            "--num_modes", NUM_MODES,
            "--out", str(out_pdbqt),
        ]
        t = time.monotonic()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=VINA_TIMEOUT)
            vina_ok = result.returncode == 0
            vina_stdout = result.stdout or ""
        except subprocess.TimeoutExpired:
            vina_ok = False
        timings["vina"] = time.monotonic() - t

    scores = parse_scores(vina_stdout) if vina_ok else []
    features = None
    if scores:
        features = {
            "vina_best_score": scores[0],
            "pose_score_variance": float(np.var(scores)) if len(scores) > 1 else 0.0,
            "pose_score_range": scores[-1] - scores[0] if len(scores) > 1 else 0.0,
            "poses_passing_ratio": sum(1 for s in scores if s < -5.0) / len(scores),
        }

    return {
        "pdb_id": pdb_id,
        "rec_ok": rec_ok,
        "lig_ok": lig_ok,
        "center_ok": center is not None,
        "vina_ok": vina_ok and bool(scores),
        "scores": scores,
        "features": features,
        "seconds": time.monotonic() - t0,
        "timings": timings,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Calibración acotada del pipeline de re-docking"
    )
    parser.add_argument("--data-dir", default="data/pdbbind", help="PDBbind data directory")
    parser.add_argument("--vina-path", default="tools/vina/vina.exe", help="Path to Vina executable")
    parser.add_argument("--max-complexes", type=int, default=10)
    parser.add_argument("--budget-min", type=float, default=BUDGET_MIN)
    parser.add_argument("--output-dir", default="scripts/.calibration_out")
    parser.add_argument("--keep", action="store_true", help="No borrar el directorio de salida")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = REPO_ROOT / data_dir
    vina_path = args.vina_path
    if not Path(vina_path).is_absolute():
        vina_path = str(REPO_ROOT / vina_path)
    out_dir = Path(args.output_dir)
    if not out_dir.is_absolute():
        out_dir = REPO_ROOT / out_dir

    complexes = discover_complexes(data_dir, args.max_complexes)
    print(f"Complejos a calibrar: {len(complexes)}")
    print(f"Vina: {vina_path}")
    print(f"Presupuesto: {args.budget_min:.0f} min | timeout Vina: {VINA_TIMEOUT}s")
    print(f"Salida temporal: {out_dir} (se elimina al final salvo --keep)")
    print()

    out_dir.mkdir(parents=True, exist_ok=True)
    budget_end = time.monotonic() + args.budget_min * 60

    rows = []
    print(f"{'complex':<10} {'rec_prep':>8} {'lig_prep':>8} {'vina':>5} {'seconds':>8}")
    print("-" * 44)
    for pdb_id, pdb, sdf in complexes:
        if time.monotonic() >= budget_end:
            print(f"\n[PRESUPUESTO AGOTADO] {args.budget_min:.0f} min alcanzados; "
                  f"reportando {len(rows)} resultados parciales.")
            break
        row = run_one(pdb_id, pdb, sdf, vina_path, out_dir / pdb_id)
        rows.append(row)
        (out_dir / f"{pdb_id}.json").write_text(
            json.dumps(row, indent=2, default=float)
        )
        print(
            f"{pdb_id:<10} "
            f"{'OK' if row['rec_ok'] else 'FAIL':>8} "
            f"{'OK' if row['lig_ok'] else 'FAIL':>8} "
            f"{'OK' if row['vina_ok'] else 'FAIL':>5} "
            f"{row['seconds']:>8.1f}"
        )

    print()
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    attempted = len(rows)
    if attempted == 0:
        print("No se calibró ningún complejo (revisar descubrimiento/presupuesto).")
    else:
        success = [r for r in rows if r["vina_ok"]]
        n_success = len(success)
        rate = n_success / attempted
        secs = [r["seconds"] for r in rows]
        mean_s = statistics.mean(secs)
        median_s = statistics.median(secs)
        eta_h = mean_s * 300 / 6 / 3600
        print(f"Complejos intentados: {attempted}")
        print(f"Éxito (Vina OK + scores): {n_success} ({rate:.1%})")
        print(f"Fallos de prep: "
              f"receptor={sum(1 for r in rows if not r['rec_ok'])}, "
              f"ligando={sum(1 for r in rows if not r['lig_ok'])}, "
              f"centro={sum(1 for r in rows if not r['center_ok'])}")
        print(f"Tiempo medio por complejo: {mean_s:.1f}s | mediana: {median_s:.1f}s")
        print(f"ETA extrapolado (300 complejos @ 6 workers): {eta_h:.1f} horas "
              f"= {mean_s * 300 / 6 / 3600:.2f} h")
        prep_ok = sum(1 for r in rows if r["rec_ok"] and r["lig_ok"] and r["center_ok"])
        vina_fail = prep_ok - sum(1 for r in rows if r["rec_ok"] and r["lig_ok"] and r["center_ok"] and r["vina_ok"])
        print(f"Preps completas: {prep_ok}/{attempted} | Vina falló tras prep OK: {vina_fail}")

    if not args.keep:
        shutil.rmtree(out_dir, ignore_errors=True)
        print(f"\nDirectorio temporal eliminado: {out_dir}")
    else:
        print(f"\nResultados conservados en: {out_dir}")


if __name__ == "__main__":
    main()
