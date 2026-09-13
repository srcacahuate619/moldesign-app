#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
backend/scripts/validate_molpocket.py — Benchmark del motor MolPocket.

Evalúa `utils/pocket_detector.detect_pockets` contra targets de la DB local:
para cada target del catálogo se detectan pockets sobre el PDB local y se
compara el mejor pocket (por score) contra el ground truth = centroide del
ligando cocristalizado (HETATM no-SKIP más grande con 6..500 átomos, misma
regla que structural.py).

Catálogo default (derivado): targets `is_prepared=1` ∩ PDBs locales en
`~/MolDesign/data/targets/` (búsqueda recursiva: soporta subcarpetas por
familia, p. ej. `target_library/01_gpcr/`) ∩ con ligando drug-like en el PDB
local. `--catalog <json>` fija una lista exacta de pdb_ids (override reproducible).

Métricas agregadas: N evaluados, mediana, p75, mean, %≤4/6/10 Å y mediana por
`structural_family`. Exit code ≠ 0 si la mediana ≥ umbral (default 4.0 Å) o si
nada pudo evaluarse.

Uso:
    python validate_molpocket.py                                   # derivado + consola
    python validate_molpocket.py --offline --out data/molpocket_report.json
    python validate_molpocket.py --catalog data/molpocket_targets.json --max-median 6.0

Solo stdlib + numpy/scipy (el motor). Nunca toca la red: los PDBs son locales;
`--offline` es explícito por contrato (el script no descarga nada, con o sin él).
"""

from __future__ import annotations

import argparse
import json
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Permitir `import utils.*` cuando se corre como script standalone.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from utils.pocket_detector import detect_pockets
from utils.structural import MAX_LIGAND_ATOMS, MIN_LIGAND_ATOMS, SKIP_HETATM

# ── Rutas por defecto ──────────────────────────────────────────────────────────

DEFAULT_DB = Path.home() / "MolDesign" / "data" / "moldesign_local.db"
# PDBs HOLO con ligando cocristalizado (ground truth real). Árbol del repo:
# D:\moldesign-build\data\target_library\<familia>\<PDB>.pdb (307 holo) +
# D:\moldesign-build\data\targets\<PDB>.pdb (111, ~106 holo). Relativo al
# script (backend/scripts/ -> repo_root/data/...). NO usar ~/MolDesign/data/targets
# (esos son PDBs APO preparados para Vina; los únicos HETATM son MSE/SEP =
# selenometionina/fosfoserina, aminoácidos modificados, NO ligandos).
_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PDB_DIR = _REPO_ROOT / "data" / "target_library"
DEFAULT_OUT = Path(__file__).resolve().parents[1] / "data" / "molpocket_report.json"
DEFAULT_CATALOG_OUT = Path(__file__).resolve().parents[1] / "data" / "molpocket_targets.json"
DEFAULT_MAX_MEDIAN = 4.0   # Å — umbral de aceptación (design: objetivo < 4-6 Å)

# Métricas de distancia reportadas
PCT_THRESHOLDS = (4.0, 6.0, 10.0)


# ── Utilidades ─────────────────────────────────────────────────────────────────

def configurar_stdout():
    """Fuerza UTF-8 en la consola (Windows) para no romper acentos ni nombres."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def conectar_ro(db_path: Path) -> sqlite3.Connection:
    """Conexión SOLO LECTURA (uri mode=ro): el benchmark jamás escribe en la DB."""
    uri = "file:" + db_path.as_posix() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def cargar_catalog(path: Path) -> set[str]:
    """Carga un JSON de pdb_ids (lista o {"pdb_ids": [...]})."""
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        data = data.get("pdb_ids") or data.get("targets") or []
    return {str(x).upper() for x in data}


def leer_targets_preparados(conn: sqlite3.Connection) -> dict[str, str | None]:
    """pdb_id (upper) -> structural_family para filas is_prepared=1."""
    cur = conn.cursor()
    cur.execute("SELECT pdb_id, structural_family FROM targets WHERE is_prepared = 1")
    return {row[0].upper(): row[1] for row in cur.fetchall()}


def pdb_path_map(pdb_dir: Path) -> dict[str, Path]:
    """pdb_id (upper) -> Path del archivo .pdb del árbol del directorio.

    Búsqueda RECURSIVA (rglob): soporta datasets organizados en subcarpetas
    por familia (p. ej. `target_library/01_gpcr/4IAQ.pdb`). Si un pdb_id
    apareciera en más de un archivo, se toma el primero (orden estable).
    """
    if not pdb_dir.is_dir():
        return {}
    mapa: dict[str, Path] = {}
    for p in sorted(pdb_dir.rglob("*.pdb")):
        mapa.setdefault(p.stem.upper(), p)
    return mapa


def pdb_ids_locales(pdb_dir: Path) -> set[str]:
    """pdb_id (upper) de los archivos *.pdb del directorio (recursivo)."""
    return set(pdb_path_map(pdb_dir))


# ── Ground truth: ligando cocristalizado ──────────────────────────────────────

def ligandos_druglike(pdb_content: str) -> dict[str, list[tuple[float, float, float]]]:
    """Grupos HETATM no-SKIP con 6..500 átomos (reglas de structural.py)."""
    groups: dict[str, list[tuple[float, float, float]]] = {}
    for line in pdb_content.splitlines():
        if not line.startswith("HETATM"):
            continue
        res_name = line[17:20].strip().upper()
        if res_name in SKIP_HETATM:
            continue
        chain = (line[21:22].strip() or "A").upper()
        res_seq = line[22:26].strip()
        res_id = f"{chain}:{res_name}{res_seq}"
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        groups.setdefault(res_id, []).append((x, y, z))
    return {
        rid: coords for rid, coords in groups.items()
        if MIN_LIGAND_ATOMS <= len(coords) <= MAX_LIGAND_ATOMS
    }


def ground_truth_centroid(pdb_content: str):
    """Centroide del ligando cocristalizado más grande (media de coords).

    Misma regla que structural.py (líneas 208-211): el grupo HETATM no-SKIP
    más grande con 6..500 átomos. Retorna (centroid (x,y,z), res_id) o
    (None, None) si no hay ligando válido.
    """
    ligs = ligandos_druglike(pdb_content)
    if not ligs:
        return None, None
    best_id = max(ligs, key=lambda k: len(ligs[k]))
    coords = ligs[best_id]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]
    return (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs)), best_id


# ── Evaluación por target ─────────────────────────────────────────────────────

def evaluar_target(pdb_content: str, gt_centroid: tuple[float, float, float]):
    """detect_pockets(top_n=5) → mejor por score → distancia al ground truth.

    Returns:
        (distancia | None, motivo | None, info dict)
        motivo: "sin_pocket" | "error" (detect_pockets nunca lanza, pero se
        registra por defensa).
    """
    try:
        pockets = detect_pockets(pdb_content, top_n=5)
    except Exception as exc:  # defensivo: el contrato dice que no lanza
        return None, "error", {"error": str(exc)}

    if not pockets:
        return None, "sin_pocket", {}

    best = pockets[0]
    d = math.dist(best.center, gt_centroid)
    info = {
        "score": round(best.score, 4),
        "druggability": round(best.druggability, 4),
        "pocket_center": [round(c, 2) for c in best.center],
        "pocket_radius": round(best.radius, 2),
        "n_spheres": best.n_spheres,
        "n_pockets": len(pockets),
    }
    return d, None, info


# ── Métricas ──────────────────────────────────────────────────────────────────

def calcular_metricas(distancias: list[float]) -> dict:
    a = np.asarray(distancias, dtype=float)
    return {
        "N": int(a.size),
        "median": float(np.median(a)),
        "p75": float(np.percentile(a, 75)),
        "mean": float(np.mean(a)),
        "pct_le_4": float(np.mean(a <= 4.0) * 100.0),
        "pct_le_6": float(np.mean(a <= 6.0) * 100.0),
        "pct_le_10": float(np.mean(a <= 10.0) * 100.0),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
    }


def metricas_por_familia(
    distancias: dict[str, float],
    familias: dict[str, str | None],
) -> dict:
    """Mediana/p75 por structural_family (join con la DB)."""
    por_familia: dict[str, list[float]] = {}
    for pdb_id, d in distancias.items():
        fam = familias.get(pdb_id) or "sin_familia"
        por_familia.setdefault(fam, []).append(d)
    out = {}
    for fam, ds in sorted(por_familia.items()):
        arr = np.asarray(ds, dtype=float)
        out[fam] = {
            "N": int(arr.size),
            "median": float(np.median(arr)),
            "p75": float(np.percentile(arr, 75)),
        }
    return out


# ── Derivación del catálogo ───────────────────────────────────────────────────

def derivar_catalogo(preparados: dict[str, str | None], pdb_dir: Path):
    """is_prepared=1 ∩ PDBs locales ∩ ligando drug-like en el PDB local.

    Returns:
        (catalog dict[pdb_id -> familia], skips list[dict], warnings list[str]).
    """
    locales = pdb_ids_locales(pdb_dir)
    paths = pdb_path_map(pdb_dir)
    warnings: list[str] = []
    sin_pdb = sorted(set(preparados) - locales)
    if sin_pdb:
        warnings.append(
            f"{len(sin_pdb)} targets preparados sin PDB local (se omiten): "
            f"{', '.join(sin_pdb[:10])}{'…' if len(sin_pdb) > 10 else ''}"
        )

    catalog: dict[str, str | None] = {}
    skips: list[dict] = []
    for pdb_id in sorted(set(preparados) & locales):
        pdb_path = paths[pdb_id]
        try:
            pdb_content = pdb_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            skips.append({"pdb_id": pdb_id, "motivo": f"error_lectura: {exc}"})
            continue
        gt, lig_id = ground_truth_centroid(pdb_content)
        if gt is None:
            skips.append({
                "pdb_id": pdb_id,
                "motivo": "sin_ligando_druglike",
                "detalle": "el PDB local no contiene HETATM no-SKIP con 6..500 átomos",
            })
            continue
        catalog[pdb_id] = preparados[pdb_id]
    return catalog, skips, warnings


# ── Reporte ───────────────────────────────────────────────────────────────────

def imprimir_reporte(args, n_catalog, metricas, por_familia,
                     skipped, fallos, peores, exit_code):
    print("=" * 78)
    print("BENCHMARK MOLPOCKET — validate_molpocket.py")
    print("=" * 78)
    print(f"  DB:        {args.db}")
    print(f"  PDB dir:   {args.pdb_dir}")
    origen = f"derivado ({n_catalog} targets)" if args.catalog is None \
        else f"archivo {args.catalog} ({n_catalog} targets)"
    print(f"  Catálogo:  {origen}")
    print(f"  Umbral:    mediana < {args.max_median} Å (exit ≠ 0 si se supera)")
    print()

    print("── Resumen ──────────────────────────────────────────────")
    if metricas["N"] == 0:
        print("  NADA PUDO EVALUARSE (revisar skips/faltas de PDB).")
        print()
        _imprimir_skips(skipped)
        return
    print(f"  N evaluados:          {metricas['N']:>4}")
    print(f"  Mediana:              {metricas['median']:6.2f} Å"
          + ("   ← SOBRE EL UMBRAL" if metricas["median"] >= args.max_median else ""))
    print(f"  p75:                  {metricas['p75']:6.2f} Å")
    print(f"  mean:                 {metricas['mean']:6.2f} Å")
    print(f"  % ≤ 4 Å:              {metricas['pct_le_4']:6.1f}%")
    print(f"  % ≤ 6 Å:              {metricas['pct_le_6']:6.1f}%")
    print(f"  % ≤ 10 Å:             {metricas['pct_le_10']:6.1f}%")
    print(f"  min/max:              {metricas['min']:6.2f} / {metricas['max']:6.2f} Å")
    if peores:
        print("  Peores outliers (top 5):")
        for pdb_id, d in peores:
            print(f"    {pdb_id:<8} {d:6.2f} Å")
    print()

    if por_familia:
        print("── Mediana por familia estructural ──────────────────────")
        for fam, m in sorted(por_familia.items(), key=lambda kv: -kv[1]["N"]):
            print(f"    {fam:<26} N={m['N']:>3}  mediana={m['median']:6.2f} Å  "
                  f"p75={m['p75']:6.2f} Å")
        print()

    if skipped:
        _imprimir_skips(skipped)
    if fallos:
        print(f"── Fallos de detección ({len(fallos)}) ─────────────────────")
        for pdb_id, motivo in sorted(fallos.items()):
            print(f"    {pdb_id:<8} {motivo}")
        print()

    estado = "OK (mediana bajo el umbral)" if exit_code == 0 \
        else "FALLO (mediana ≥ umbral → revisar calibración)"
    print(f"── Exit code: {exit_code} — {estado} ───────────────────────")
    print()


def _imprimir_skips(skipped: list[dict]):
    if not skipped:
        return
    print(f"── Skipped ({len(skipped)}) ────────────────────────────────────")
    for s in skipped[:25]:
        detalle = f" — {s.get('detalle', '')}" if s.get("detalle") else ""
        print(f"    {s['pdb_id']:<8} {s['motivo']}{detalle}")
    if len(skipped) > 25:
        print(f"    … y {len(skipped) - 25} más")
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Benchmark del motor MolPocket contra targets de la DB local.",
    )
    parser.add_argument("--catalog", type=Path, default=None,
                        help="JSON con pdb_ids exactos (override del catálogo derivado)")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB,
                        help=f"ruta a la DB SQLite (default: {DEFAULT_DB})")
    parser.add_argument("--pdb-dir", type=Path, default=DEFAULT_PDB_DIR,
                        help=f"directorio con PDBs locales (búsqueda recursiva; "
                             f"default: {DEFAULT_PDB_DIR})")
    parser.add_argument("--offline", action="store_true",
                        help="no tocar red (no-op: el script nunca descarga; "
                             "flag por contrato)")
    parser.add_argument("--out", type=Path, default=None,
                        help=f"JSON de reporte (default: {DEFAULT_OUT})")
    parser.add_argument("--catalog-out", type=Path, default=DEFAULT_CATALOG_OUT,
                        help="dónde volcar el catálogo derivado "
                             f"(default: {DEFAULT_CATALOG_OUT})")
    parser.add_argument("--max-median", type=float, default=DEFAULT_MAX_MEDIAN,
                        help=f"umbral de mediana en Å (default: {DEFAULT_MAX_MEDIAN})")
    parser.add_argument("--limit", type=int, default=None,
                        help="máximo de targets del catálogo a evaluar (los primeros "
                             "N del orden estable; default: None = todos). Para iterar "
                             "rápido durante calibración.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    configurar_stdout()
    args = parse_args(argv)

    if not args.db.exists():
        print(f"ERROR: no existe la DB: {args.db}")
        return 2
    if not args.pdb_dir.is_dir():
        print(f"ERROR: no existe el directorio de PDBs: {args.pdb_dir}")
        return 2

    conn = conectar_ro(args.db)
    try:
        preparados = leer_targets_preparados(conn)
    finally:
        conn.close()
    familias = preparados

    # ── Catálogo ──────────────────────────────────────────────────────
    if args.catalog is not None:
        if not args.catalog.exists():
            print(f"ERROR: no existe el catálogo: {args.catalog}")
            return 2
        catalog = {pid: familias.get(pid) for pid in sorted(cargar_catalog(args.catalog))}
        skipped: list[dict] = []
        warnings: list[str] = []
    else:
        catalog, skipped, warnings = derivar_catalogo(preparados, args.pdb_dir)
        # Volcar el catálogo derivado (artifact reproducible del benchmark).
        try:
            args.catalog_out.parent.mkdir(parents=True, exist_ok=True)
            args.catalog_out.write_text(
                json.dumps({"derivado": True, "pdb_ids": sorted(catalog),
                            "generado": datetime.now().isoformat(timespec="seconds")},
                           indent=2),
                encoding="utf-8",
            )
            print(f"[catalogo] derivado: {len(catalog)} targets → {args.catalog_out}")
        except OSError as exc:
            print(f"[catalogo] no se pudo volcar {args.catalog_out}: {exc}")

    for w in warnings:
        print(f"[warn] {w}")

    # ── Benchmark ─────────────────────────────────────────────────────
    distancias: dict[str, float] = {}
    fallos: dict[str, str] = {}
    por_target: dict = {}
    targets_evaluados = []
    paths = pdb_path_map(args.pdb_dir)

    evaluados = 0
    for pdb_id in sorted(catalog):
        if args.limit is not None and evaluados >= args.limit:
            break
        evaluados += 1
        pdb_path = paths.get(pdb_id)
        if not pdb_path.exists():
            skipped.append({"pdb_id": pdb_id, "motivo": "sin_pdb_local"})
            por_target[pdb_id] = {"skip": "sin_pdb_local"}
            continue
        try:
            pdb_content = pdb_path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            skipped.append({"pdb_id": pdb_id, "motivo": f"error_lectura: {exc}"})
            por_target[pdb_id] = {"skip": "error_lectura"}
            continue

        gt, lig_id = ground_truth_centroid(pdb_content)
        if gt is None:
            skipped.append({"pdb_id": pdb_id, "motivo": "sin_ligando_druglike"})
            por_target[pdb_id] = {"skip": "sin_ligando_druglike"}
            continue

        d, motivo, info = evaluar_target(pdb_content, gt)
        if d is None:
            fallos[pdb_id] = motivo or "desconocido"
            por_target[pdb_id] = {"fallo": motivo, **info}
            continue

        distancias[pdb_id] = d
        targets_evaluados.append(pdb_id)
        por_target[pdb_id] = {
            "distancia_a_ligando": round(d, 3),
            "ground_truth": lig_id,
            **info,
        }
        print(f"  {pdb_id:<8} d={d:6.2f} Å  score={info['score']:.3f}  "
              f"n_spheres={info['n_spheres']}")

    metricas = calcular_metricas(list(distancias.values()))
    por_familia = metricas_por_familia(distancias, familias)

    # Peores outliers: top 5 por distancia
    peores = sorted(distancias.items(), key=lambda kv: kv[1], reverse=True)[:5]

    if metricas["N"] > 0 and metricas["median"] >= args.max_median:
        exit_code = 1
    elif metricas["N"] == 0:
        exit_code = 2
    else:
        exit_code = 0

    imprimir_reporte(args, len(catalog), metricas, por_familia,
                     skipped, fallos, peores, exit_code)

    # ── JSON (--out) ──────────────────────────────────────────────────
    if args.out is not None:
        report = {
            "motor": "molpocket",
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "config": {
                "db": str(args.db),
                "pdb_dir": str(args.pdb_dir),
                "catalog": str(args.catalog) if args.catalog else "derivado",
                "max_median": args.max_median,
                "offline": args.offline,
            },
            "catalogo": {
                "derivado": args.catalog is None,
                "n_targets": len(catalog),
            },
            "resumen": metricas,
            "por_familia": por_familia,
            "por_target": por_target,
            "skipped": skipped,
            "fallos": fallos,
            "peores_outliers": [{"pdb_id": k, "distancia": round(v, 3)}
                                for k, v in peores],
            "exit_code": exit_code,
        }
        try:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                encoding="utf-8")
            print(f"[reporte] JSON escrito en {args.out}")
        except OSError as exc:
            print(f"[reporte] no se pudo escribir {args.out}: {exc}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
