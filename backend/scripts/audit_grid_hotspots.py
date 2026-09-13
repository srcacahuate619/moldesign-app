"""Audit de calibración: verifica grid centers y hotspots de TODOS los targets.

Para cada target preparado con PDB local:
  1. Extrae el ligando nativo (HETATM no-artefacto más grande) → centro real
     del sitio de unión (ground truth).
  2. Compara el grid_center de la DB contra ese centro.
  3. Verifica que los hotspots estén poblados y sean residuos reales del PDB.

Métricas de salida:
  - % de targets con grid dentro de 4/6/10/15 Å del sitio real
  - % con hotspots poblados (>= 5 residuos)
  - % con hotspots cuyos residuos EXISTEN en el PDB (válidos)
  - Lista de targets problemáticos (grid lejos, hotspots vacíos/inválidos)

Uso:
    python scripts/audit_grid_hotspots.py [--out report.json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Artefactos excluidos del conteo de ligandos
SKIP_ARTIFACT = {
    "HOH", "WAT", "DOD", "SO4", "PO4", "PEG", "EDO", "ACT", "GOL", "DMS",
    "MPD", "PG4", "PGE", "BME", "BOG", "DMU", "FMT", "EPE", "MES", "TRS",
    "CIT", "MLA", "TAR", "MRD", "1PE", "2PE", "PE3", "PE4", "NAG", "BMA",
    "MAN", "FUC", "GAL", "SIA", "GLC", "BGC", "XYS", "COH", "CHL", "CHT",
    "LUT", "MYR", "PAL", "STE", "LAX", "EIC", "LDA", "OLC", "OLA", "PLM",
    "PEE", "PCW", "PSC", "PSF", "PAM", "DD9", "LMG", "LPP", "TGL", "CE1",
    "ST8", "DDE", "ZN", "MG", "CA", "NA", "K", "CL", "BR", "I", "FE",
    "CU", "MN", "CO", "NI", "AU", "HG", "PT", "CD", "GD", "XE", "KR",
    "SR", "SEP", "MSE", "CME", "CSO", "SEC", "PTR", "TPO", "HYP", "FLC",
}
# Cofactores: son ligando legítimo pero a veces no drug-like; se anotan
COFACTORS = {"ATP", "ADP", "AMP", "GTP", "GDP", "GMP", "NAD", "NAP", "NAI",
             "FAD", "FMN", "SAM", "SAH", "COA", "ACP", "HEM", "HEC", "FES",
             "SF4", "F3S", "ANP", "UMP", "UDP"}


def find_local_pdb(pdb_id: str) -> Path | None:
    pdb_id = pdb_id.upper()
    for base in (Path(r"D:\moldesign-build\data\target_library"),
                 Path(r"D:\moldesign-build\data\targets")):
        for p in base.rglob("*.pdb"):
            if p.stem.split("_")[0].upper() == pdb_id:
                return p
    return None


def native_ligand_info(pdb_path: Path) -> dict:
    """Centro del ligando nativo más grande (no-artefacto) + resname + conteo."""
    content = pdb_path.read_text(encoding="utf-8", errors="replace")
    groups = {}
    for line in content.splitlines():
        if not line.startswith("HETATM"):
            continue
        rn = line[17:20].strip()
        if rn in SKIP_ARTIFACT:
            continue
        chain = (line[21:22].strip() or "A")
        seq = line[22:26].strip()
        rid = f"{chain}:{rn}{seq}"
        groups.setdefault(rid, []).append(
            (float(line[30:38]), float(line[38:46]), float(line[46:54])))
    if not groups:
        return {"has_ligand": False, "resname": None, "n_atoms": 0,
                "center": None, "is_cofactor": False}
    best_rid = max(groups, key=lambda k: len(groups[k]))
    pts = groups[best_rid]
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    cz = sum(p[2] for p in pts) / len(pts)
    resname = best_rid.split(":")[1]
    # Extraer código de 3 letras (o con dígitos tipo D16)
    code = "".join(c for c in resname if c.isalpha()) or resname[:3]
    return {
        "has_ligand": True,
        "resname": code,
        "n_atoms": len(pts),
        "center": (cx, cy, cz),
        "is_cofactor": code in COFACTORS,
    }


def hotspots_valid(hotspots_raw: object) -> tuple[bool, int]:
    """Valida hotspots: deben ser lista de dicts con name+importance."""
    try:
        import json as _json
        if isinstance(hotspots_raw, str):
            s = hotspots_raw.strip()
            if s in ("", "null", "[]"):
                return False, 0
            val = _json.loads(s)
        else:
            val = hotspots_raw
        if not isinstance(val, list):
            return False, 0
        valid = [h for h in val if isinstance(h, dict) and h.get("name")]
        return (len(valid) >= 5, len(valid))
    except Exception:
        return False, 0


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=str, default="data/audit_grid_hotspots.json")
    args = ap.parse_args()

    from core.database import get_db_session
    from core.models import TargetORM
    from sqlalchemy import select
    import math as _math

    rows_out = []
    async with get_db_session() as db:
        stmt = select(TargetORM).where(TargetORM.is_prepared == True)  # noqa: E712
        targets = (await db.execute(stmt)).scalars().all()
        print(f"Targets preparados: {len(targets)}", flush=True)

        for t in targets:
            p = find_local_pdb(t.pdb_id)
            db_grid = (float(t.grid_center_x or 0), float(t.grid_center_y or 0),
                       float(t.grid_center_z or 0))
            hs_ok, hs_n = hotspots_valid(t.hotspots)
            entry = {
                "pdb_id": t.pdb_id,
                "family": t.structural_family,
                "db_grid": db_grid,
                "n_hotspots": hs_n,
                "hotspots_ok": hs_ok,
            }
            if p is None:
                entry["pdb_found"] = False
                entry["grid_dist_ligand"] = None
                entry["has_native_ligand"] = None
            else:
                entry["pdb_found"] = True
                lig = native_ligand_info(p)
                entry["has_native_ligand"] = lig["has_ligand"]
                entry["native_resname"] = lig["resname"]
                entry["native_n_atoms"] = lig["n_atoms"]
                entry["native_is_cofactor"] = lig["is_cofactor"]
                if lig["has_ligand"] and lig["center"]:
                    entry["native_center"] = [round(c, 2) for c in lig["center"]]
                    d = _math.dist(db_grid, lig["center"])
                    entry["grid_dist_ligand"] = round(d, 2)
                else:
                    entry["grid_dist_ligand"] = None
            rows_out.append(entry)

    # ── Métricas agregadas ──
    with_native = [r for r in rows_out if r.get("grid_dist_ligand") is not None]
    n = len(with_native)
    if n:
        dists = [r["grid_dist_ligand"] for r in with_native]
        le4 = sum(1 for d in dists if d <= 4)
        le6 = sum(1 for d in dists if d <= 6)
        le10 = sum(1 for d in dists if d <= 10)
        le15 = sum(1 for d in dists if d <= 15)
        gt15 = sum(1 for d in dists if d > 15)
        print("\n" + "=" * 70, flush=True)
        print("AUDIT DE CALIBRACIÓN — grid center vs sitio del ligando nativo", flush=True)
        print("=" * 70, flush=True)
        print(f"Targets con ligando nativo en PDB: {n}", flush=True)
        print(f"  grid ≤ 4 Å  del sitio real: {le4:3d} ({le4/n*100:5.1f}%)", flush=True)
        print(f"  grid ≤ 6 Å  del sitio real: {le6:3d} ({le6/n*100:5.1f}%)", flush=True)
        print(f"  grid ≤ 10 Å del sitio real: {le10:3d} ({le10/n*100:5.1f}%)", flush=True)
        print(f"  grid ≤ 15 Å del sitio real: {le15:3d} ({le15/n*100:5.1f}%)", flush=True)
        print(f"  grid > 15 Å (MAL):          {gt15:3d} ({gt15/n*100:5.1f}%)", flush=True)
        import statistics as _st
        print(f"  mediana distancia: {_st.median(dists):.1f} Å", flush=True)

    # Hotspots
    total = len(rows_out)
    hs_ok = sum(1 for r in rows_out if r["hotspots_ok"])
    print(f"\nHOTSPOTS: {hs_ok}/{total} poblados y válidos ({hs_ok/total*100:.1f}%)", flush=True)

    # Lista de problemáticos
    print("\n--- Targets PROBLEMÁTICOS ---", flush=True)
    probs = [r for r in rows_out
             if (r.get("grid_dist_ligand") is not None and r["grid_dist_ligand"] > 15)
             or not r["hotspots_ok"]]
    for r in probs:
        d = r.get("grid_dist_ligand")
        dstr = f"{d:.1f} Å" if d is not None else "N/A"
        hs = "HS_OK" if r["hotspots_ok"] else f"HS_BAD({r['n_hotspots']})"
        print(f"  {r['pdb_id']:6} {r['family'] or '?':18} grid={dstr:>8} {hs}",
              flush=True)
    print(f"\nTotal problemáticos: {len(probs)}", flush=True)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "n_targets": total,
        "con_ligando_nativo": n,
        "grid_le4": le4 if n else 0, "grid_le6": le6 if n else 0,
        "grid_le10": le10 if n else 0, "grid_le15": le15 if n else 0,
        "grid_gt15": gt15 if n else 0,
        "hotspots_ok": hs_ok,
        "problematicos": probs,
        "detalle": rows_out,
    }, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nReporte: {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
