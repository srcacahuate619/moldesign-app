"""Benchmark MolPocket sobre PDBbind v2020 refined set (ground truth oficial).

PDBbind es el estándar de oro para benchmarking de pockets: cada complejo trae
    {pdb_id}_protein.pdb   → receptor APO real (sin ligando)
    {pdb_id}_ligand.mol2   → ligando druglike curado por expertos

Eso ELIMINA la contaminación de carbohydratos/detergentes/metales que sufría el
benchmark sobre `target_library` (PDBs crudos con NAG/MAN/BOG/HG/ZN/HOH como
"ligandos"). Acá el receptor es APO real y el ligando es curado.

Uso:
    python benchmark_pdbbind.py                       # todos los válidos
    python benchmark_pdbbind.py --limit 30           # muestra rápida
    python benchmark_pdbbind.py --out data/bench.json
    python benchmark_pdbbind.py --pdbbind-dir <ruta>/data/pdbbind
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

# Forzar UTF-8 en stdout/stderr (la consola Windows en cp1252 revienta con ≤/Å)
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from utils.pocket_detector import detect_pockets          # noqa: E402


# ── Configuración ──────────────────────────────────────────────────────────────

DEFAULT_PDBBIND = Path(__file__).resolve().parent.parent.parent / "data" / "pdbbind"
DEFAULT_OUT = _ROOT / "data" / "benchmark_pdbbind.json"
DEFAULT_TOP_N = 3          # pockets a detectar por target
DIST_UMBRAL_OK = 4.0       # ≤ 4 Å = buena predicción
DIST_UMBRAL_TOL = 6.0      # ≤ 6 Å = tolerable
DIST_UMBRAL_FLOP = 10.0    # > 10 Å = outlier / fallo

_PDBID_RE = re.compile(r"^[0-9][a-z0-9]{3}$")


# ── Parsing del ligando .mol2 ──────────────────────────────────────────────────

def centro_ligando_mol2(path: Path) -> tuple[np.ndarray, int, str]:
    """Centro geométrico del ligando desde el .mol2 de PDBbind.

    Returns:
        (centroid (3,), n_atoms, first_resname)
    """
    atoms = []
    in_atom = False
    resname = "?"
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("@<TRIPOS>ATOM"):
                in_atom = True
                continue
            if line.startswith("@<TRIPOS>"):
                in_atom = False
                continue
            if in_atom and line.strip():
                parts = line.split()
                # mol2 atom line: id name x y z type subst_id subst_name charge
                try:
                    x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
                    if len(parts) >= 7:
                        resname = parts[6][:3]
                except (ValueError, IndexError):
                    continue
                atoms.append([x, y, z])
    if not atoms:
        return np.zeros(3), 0, resname
    return np.asarray(atoms).mean(axis=0), len(atoms), resname


# ── Iteración sobre complejos válidos ──────────────────────────────────────────

def complejos_validos(pdbbind_dir: Path, limit: int | None = None):
    """Yield (pdb_id, protein_pdb, ligand_mol2) para cada complejo válido."""
    if not pdbbind_dir.is_dir():
        return
    found = 0
    for d in sorted(pdbbind_dir.iterdir()):
        if not d.is_dir():
            continue
        if not _PDBID_RE.match(d.name):
            continue
        prot = d / f"{d.name}_protein.pdb"
        lig = d / f"{d.name}_ligand.mol2"
        if prot.is_file() and lig.is_file():
            yield d.name.upper(), prot, lig
            found += 1
            if limit and found >= limit:
                return


# ── Evaluación ─────────────────────────────────────────────────────────────────

def evaluar_complejo(pdb_id: str, prot_path: Path, lig_path: Path,
                     top_n: int = DEFAULT_TOP_N) -> dict:
    """Evalúa un complejo PDBbind: detecta pockets y mide distancia al ligando."""
    t0 = time.perf_counter()
    try:
        pdb_content = prot_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return {"pdb_id": pdb_id, "skip": "no_leer_pdb", "error": str(exc),
                "elapsed": round(time.perf_counter() - t0, 3)}

    lig_center, n_lig, lig_resname = centro_ligando_mol2(lig_path)
    if n_lig == 0:
        return {"pdb_id": pdb_id, "skip": "ligando_vacio",
                "elapsed": round(time.perf_counter() - t0, 3)}

    try:
        pockets = detect_pockets(pdb_content, top_n=top_n)
    except Exception as exc:
        return {"pdb_id": pdb_id, "skip": "error_detect",
                "error": str(exc)[:120],
                "elapsed": round(time.perf_counter() - t0, 3)}

    if not pockets:
        return {"pdb_id": pdb_id, "skip": "sin_pocket",
                "n_lig_atoms": n_lig, "lig_resname": lig_resname,
                "lig_center": [round(c, 2) for c in lig_center],
                "elapsed": round(time.perf_counter() - t0, 3)}

    # Mejor pocket por score (top_n=3) + distancia al ligando curado
    distancias = []
    for p in pockets:
        d = float(np.linalg.norm(np.asarray(p.center) - lig_center))
        distancias.append(d)
    best_idx = int(np.argmin(distancias))   # el pocket más cercano al lig
    best = pockets[best_idx]
    top1 = pockets[0]

    return {
        "pdb_id": pdb_id,
        "distancia": round(distancias[best_idx], 3),
        "distancia_top1": round(distancias[0], 3),
        "score": round(best.score, 4),
        "druggability": round(best.druggability, 4),
        "n_spheres": best.n_spheres,
        "n_pockets": len(pockets),
        "n_lig_atoms": n_lig,
        "lig_resname": lig_resname,
        "lig_center": [round(c, 2) for c in lig_center],
        "pocket_center": [round(c, 2) for c in best.center],
        "elapsed": round(time.perf_counter() - t0, 3),
    }


# ── Métricas ───────────────────────────────────────────────────────────────────

def calcular_metricas(distancias: list[float]) -> dict:
    a = np.asarray(distancias, dtype=float)
    return {
        "N": int(a.size),
        "median": float(np.median(a)),
        "p25": float(np.percentile(a, 25)),
        "p75": float(np.percentile(a, 75)),
        "p90": float(np.percentile(a, 90)),
        "mean": float(np.mean(a)),
        "pct_le_4": float(np.mean(a <= DIST_UMBRAL_OK) * 100.0),
        "pct_le_6": float(np.mean(a <= DIST_UMBRAL_TOL) * 100.0),
        "pct_le_10": float(np.mean(a <= DIST_UMBRAL_FLOP) * 100.0),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
    }


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(
        description="Benchmark MolPocket sobre PDBbind (ground truth oficial).")
    ap.add_argument("--pdbbind-dir", type=Path, default=DEFAULT_PDBBIND,
                    help=f"Dir de PDBbind (default: {DEFAULT_PDBBIND})")
    ap.add_argument("--limit", type=int, default=None,
                    help="Limitar a N complejos (debug).")
    ap.add_argument("--sample", type=int, default=None,
                    help="Tomar una muestra aleatoria de N complejos "
                         "(reproducible con --seed).")
    ap.add_argument("--seed", type=int, default=42,
                    help="Semilla para --sample (default: 42).")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"JSON de reporte (default: {DEFAULT_OUT})")
    ap.add_argument("--top-n", type=int, default=DEFAULT_TOP_N,
                    help=f"Pockets por target (default: {DEFAULT_TOP_N})")
    args = ap.parse_args()

    print("BENCHMARK PDBbind — MolPocket", flush=True)
    print(f"  PDBbind dir: {args.pdbbind_dir}", flush=True)
    print(f"  top_n: {args.top_n}  limit: {args.limit or 'sin limite'}", flush=True)
    print(f"  out: {args.out}", flush=True)
    print(flush=True)

    if not args.pdbbind_dir.is_dir():
        print(f"ERROR: no existe {args.pdbbind_dir}", flush=True)
        return 2

    resultados = []
    skips = []
    t_start = time.perf_counter()

    complejos = list(complejos_validos(args.pdbbind_dir, limit=None))
    if args.sample and args.sample < len(complejos):
        import random
        rng = random.Random(args.seed)
        complejos = rng.sample(complejos, args.sample)
    elif args.limit:
        complejos = complejos[:args.limit]
    print(f"Complejos válidos detectados: {len(complejos)}"
          + (f" (muestra random seed={args.seed})" if args.sample else ""),
          flush=True)
    print(flush=True)

    print(f"{'PDB':>6}  {'d(Å)':>7}  {'d_t1':>7}  {'score':>6}  "
          f"{'dr':>5}  {'sph':>4}  {'lig':>4}  {'resn':>6}  {'t(s)':>5}",
          flush=True)
    print("-" * 80, flush=True)

    for i, (pdb_id, prot, lig) in enumerate(complejos, 1):
        res = evaluar_complejo(pdb_id, prot, lig, args.top_n)
        if "skip" in res:
            skips.append(res)
            print(f"  {pdb_id:>6}  SKIP: {res['skip']}", flush=True)
        else:
            resultados.append(res)
            d = res["distancia"]
            print(f"{i:>3} {pdb_id:>6}  {d:7.2f}  {res['distancia_top1']:7.2f}  "
                  f"{res['score']:6.3f}  {res['druggability']:5.3f}  "
                  f"{res['n_spheres']:4d}  {res['n_lig_atoms']:4d}  "
                  f"{res['lig_resname']:>6}  {res['elapsed']:5.2f}",
                  flush=True)

    elapsed = time.perf_counter() - t_start
    print("-" * 80, flush=True)
    print(f"\nFin. {len(resultados)} evaluados, {len(skips)} skips, "
          f"{elapsed:.1f}s totales", flush=True)

    if not resultados:
        print("NADA PARA EVALUAR — revisar skips/dir", flush=True)
        return 1

    dists = [r["distancia"] for r in resultados]
    dists_t1 = [r["distancia_top1"] for r in resultados]
    m = calcular_metricas(dists)
    m_t1 = calcular_metricas(dists_t1)

    print("\n" + "=" * 78, flush=True)
    print("RESUMEN — MolPocket sobre PDBbind", flush=True)
    print("=" * 78, flush=True)
    print(f"  N evaluados:        {m['N']:>5}", flush=True)
    print(f"  Mediana (best):      {m['median']:6.2f} Å   "
          f"(top1 por score: {m_t1['median']:6.2f} Å)", flush=True)
    print(f"  p25 / p75:           {m['p25']:6.2f} / {m['p75']:6.2f} Å", flush=True)
    print(f"  p90:                 {m['p90']:6.2f} Å", flush=True)
    print(f"  mean:                {m['mean']:6.2f} Å", flush=True)
    print(f"  % ≤ {DIST_UMBRAL_OK:.0f} Å:           {m['pct_le_4']:6.1f}%   "
          f"(top1: {m_t1['pct_le_4']:6.1f}%)", flush=True)
    print(f"  % ≤ {DIST_UMBRAL_TOL:.0f} Å:           {m['pct_le_6']:6.1f}%   "
          f"(top1: {m_t1['pct_le_6']:6.1f}%)", flush=True)
    print(f"  % ≤ {DIST_UMBRAL_FLOP:.0f} Å:          {m['pct_le_10']:6.1f}%   "
          f"(top1: {m_t1['pct_le_10']:6.1f}%)", flush=True)
    print(f"  min / max:           {m['min']:6.2f} / {m['max']:6.2f} Å",
          flush=True)
    print(flush=True)

    # Top peores outliers
    outliers = sorted(resultados, key=lambda r: -r["distancia"])[:10]
    print("Peores outliers (top 10):", flush=True)
    for r in outliers:
        print(f"  {r['pdb_id']:>6}  d={r['distancia']:6.2f} Å  "
              f"t1={r['distancia_top1']:6.2f}  n_lig={r['n_lig_atoms']:>3}  "
              f"resn={r['lig_resname']:>4}  tranh={r['elapsed']:4.1f}s",
              flush=True)
    print(flush=True)

    # Reporte JSON
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "fuente": "PDBbind v2020 refined",
        "pdbbind_dir": str(args.pdbbind_dir),
        "top_n": args.top_n,
        "limit": args.limit,
        "n_complejos_validos": len(complejos),
        "n_evaluados": len(resultados),
        "n_skips": len(skips),
        "elapsed_segundos": round(elapsed, 2),
        "metricas_best": m,
        "metricas_top1": m_t1,
        "umbrales": {"ok": DIST_UMBRAL_OK, "tol": DIST_UMBRAL_TOL,
                      "flop": DIST_UMBRAL_FLOP},
        "resultados": resultados,
        "skips": skips[:100],
    }
    try:
        args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        print(f"Reporte JSON: {args.out}", flush=True)
    except OSError as exc:
        print(f"no se pudo escribir {args.out}: {exc}", flush=True)
        return 1

    # Exit code basado en mediana
    return 0 if m["median"] <= 4.0 else 1


if __name__ == "__main__":
    sys.exit(main())
