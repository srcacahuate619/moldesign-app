"""Análisis discriminante de features de pockets vs ligando real (PDBbind).

Objetivo: exportar TODOS los pockets de cada complejo (no solo el mejor) con
TODAS sus features crudas, junto a la distancia al centro del ligando curado.
Eso permite descubrir qué feature (score, druggability, volume, as_density,
surf_pol_vdw14, ...) discrimina mejor el pocket correcto del incorrecto, y
diseñar un re-ranker basado en datos.

Uso:
    python analyze_pockets.py --limit 200 --seed 42 --out data/pocket_dataset.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import numpy as np

# UTF-8 para consolas Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Acceso a features crudas del motor: reutilizamos el pipeline paso a paso,
# pero necesitamos los descriptores. Importamos funciones internas.
from utils.pocket_detector import (            # noqa: E402
    DEFAULT_MIN_RADIUS,
    DEFAULT_MAX_RADIUS,
    _parse_heavy_atoms,
    _circumspheres,
    _filter_spheres,
    _cluster_spheres,
    _compute_descriptors,
    _minmax,
    _sigmoid,
    SCORE_B0,
    SCORE_B_NAS,
    SCORE_B_DENS,
    SCORE_B_VOL,
    SCORE_B_SURF_POL,
    SCORE_B_SURF_APOL,
    DRUG_B0,
    DRUG_B1,
    DRUG_B2,
    DRUG_B3,
    MIN_POCKET_N_SPHERES,
    ENABLE_MIN_AS_DENSITY,
    MAX_AS_DENSITY,
)

DEFAULT_PDBBIND = Path(__file__).resolve().parent.parent.parent / "data" / "pdbbind"
DEFAULT_OUT = _ROOT / "data" / "pocket_dataset.json"
_PDBID_RE = re.compile(r"^[0-9][a-z0-9]{3}$")
FEATURES = [
    "score", "druggability", "n_spheres", "radius", "volume",
    "convex_hull_volume", "as_density", "as_max_dst",
    "mean_loc_hyd_dens", "surf_pol_vdw14", "surf_apol_vdw14",
    "surf_pol_vdw22", "nas_norm", "hyd_norm",
]


def centro_ligando_mol2(path: Path):
    atoms = []
    in_atom = False
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
                try:
                    x, y, z = float(parts[2]), float(parts[3]), float(parts[4])
                except (ValueError, IndexError):
                    continue
                atoms.append([x, y, z])
    if not atoms:
        return None, 0
    return np.asarray(atoms).mean(axis=0), len(atoms)


def pocket_features_raw(pdb_content: str, top_n: int = 12):
    """Todos los pockets (hasta top_n) con features crudas y score/druggability.

    Retorna lista de dicts con las features de FEATURES + center, o [] en error.
    NO devuelve la distancia al ligando (eso se hace afuera).
    """
    try:
        coords, res_names, res_ids, elements = _parse_heavy_atoms(pdb_content)
        n_atoms = coords.shape[0]
        if n_atoms < 10:
            return []
        centers, radii, simplices = _circumspheres(coords)
        if centers.shape[0] == 0:
            return []
        mask = _filter_spheres(
            centers, radii, simplices, coords,
            min_radius=DEFAULT_MIN_RADIUS, max_radius=DEFAULT_MAX_RADIUS,
        )
        keep = np.flatnonzero(mask)
        if keep.size == 0:
            return []
        clusters = _cluster_spheres(centers[keep], radii[keep])
        if not clusters:
            return []
        raw = [
            _compute_descriptors(
                centers[keep], radii[keep], idxs,
                coords, res_names, res_ids, elements,
            )
            for idxs in clusters
        ]
        n_spheres_vals = np.asarray([d["n_spheres"] for d in raw], dtype=float)
        hyd_vals = np.asarray([d["mean_loc_hyd_dens"] for d in raw], dtype=float)
        nas_norm = _minmax(n_spheres_vals)
        hyd_norm = _minmax(hyd_vals)

        pockets = []
        for i, d in enumerate(raw):
            if d["n_spheres"] < MIN_POCKET_N_SPHERES:
                continue
            if ENABLE_MIN_AS_DENSITY and d["as_density"] < MAX_AS_DENSITY:
                continue
            score = (
                SCORE_B0
                + SCORE_B_NAS * nas_norm[i]
                + SCORE_B_DENS * d["as_density"]
                + SCORE_B_VOL * d["convex_hull_volume"]
                + SCORE_B_SURF_POL * d["surf_pol_vdw14"]
                + SCORE_B_SURF_APOL * d["surf_apol_vdw14"]
            )
            druggability = _sigmoid(
                DRUG_B0
                + DRUG_B1 * hyd_norm[i]
                + DRUG_B2 * d["as_max_dst"]
                + DRUG_B3 * d["surf_pol_vdw22"]
            )
            pockets.append({
                "center": [float(v) for v in d["center"]],
                "score": round(float(score), 6),
                "druggability": round(float(druggability), 6),
                "n_spheres": d["n_spheres"],
                "radius": d["radius"],
                "volume": d["volume"],
                "convex_hull_volume": d["convex_hull_volume"],
                "as_density": d["as_density"],
                "as_max_dst": d["as_max_dst"],
                "mean_loc_hyd_dens": d["mean_loc_hyd_dens"],
                "surf_pol_vdw14": d["surf_pol_vdw14"],
                "surf_apol_vdw14": d["surf_apol_vdw14"],
                "surf_pol_vdw22": d["surf_pol_vdw22"],
                "nas_norm": float(nas_norm[i]),
                "hyd_norm": float(hyd_norm[i]),
            })
        pockets.sort(key=lambda p: p["score"], reverse=True)
        return pockets[:top_n]
    except Exception:
        return []


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pdbbind-dir", type=Path, default=DEFAULT_PDBBIND)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--sample", type=int, default=None)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--top-n", type=int, default=12,
                    help="Pockets máximos a exportar por complejo (default 12).")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    print(f"ANALYZE POCKETS — PDBbind | top_n={args.top_n}", flush=True)
    print(f"  Dir: {args.pdbbind_dir}", flush=True)
    print(flush=True)

    # enumerar complejos válidos
    complejos = []
    for d in sorted(args.pdbbind_dir.iterdir()):
        if not d.is_dir() or not _PDBID_RE.match(d.name):
            continue
        prot = d / f"{d.name}_protein.pdb"
        lig = d / f"{d.name}_ligand.mol2"
        if prot.is_file() and lig.is_file():
            complejos.append((d.name.upper(), prot, lig))
    print(f"Complejos válidos: {len(complejos)}", flush=True)

    import random
    if args.sample and args.sample < len(complejos):
        rng = random.Random(args.seed)
        complejos = rng.sample(complejos, args.sample)
    elif args.limit:
        complejos = complejos[:args.limit]
    print(f"Procesando: {len(complejos)}", flush=True)

    dataset = []
    t_start = time.perf_counter()
    for i, (pdb_id, prot, lig) in enumerate(complejos, 1):
        try:
            pdb_content = prot.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lig_center, n_lig = centro_ligando_mol2(lig)
        if lig_center is None:
            continue
        pockets = pocket_features_raw(pdb_content, top_n=args.top_n)
        for p in pockets:
            d = float(np.linalg.norm(np.asarray(p["center"]) - lig_center))
            row = {"pdb_id": pdb_id, "n_lig_atoms": n_lig, "distancia": round(d, 3)}
            row.update({k: p.get(k) for k in FEATURES})
            row["center"] = [round(c, 2) for c in p["center"]]
            dataset.append(row)
        if i % 25 == 0:
            print(f"  {i}/{len(complejos)}  (t={time.perf_counter()-t_start:.0f}s)",
                  flush=True)

    elapsed = time.perf_counter() - t_start
    print(f"\nFin. {len(dataset)} filas pocket (de {len(complejos)} complejos) "
          f"en {elapsed:.0f}s", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "fuente": "PDBbind v2020 refined",
        "n_complejos": len(complejos),
        "n_pocket_rows": len(dataset),
        "features": FEATURES,
        "filas": dataset,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Dataset: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
