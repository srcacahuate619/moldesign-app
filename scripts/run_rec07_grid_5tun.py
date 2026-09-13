#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rec07_grid_5tun.py — REC-07: corrección del grid APO de 5TUN.

Preregistro: scripts/artifacts_science/REC-07/PREREGISTRO.md
Protocolo:   docs/49 §7 (REC-07) + docs/35_GRID_APO_5TUN_PENDIENTE.md
Entrada:     REC-01-R1 (sellado) — 5TUN con E8, margen_min = -5.147 A

Compara tres grids sobre 5TUN contra un ancla INDEPENDIENTE de MolPocket (la
triada catalitica Cys25-His162-Asn182 de la familia papaina) y valida el
candidato con un control de docking usando E64c, el inhibidor canonico de
cisteina-proteasas, extraido del homologo local 1ITO.

Los tres brazos comparten el MISMO receptor .pdbqt y el MISMO ligando: la unica
variable es la caja. Verificado en diseno: para receptor rigido, Meeko escribe la
macromolecula completa y el .pdbqt no depende de la caja.

SOLO LECTURA sobre el catalogo y las DB (gate G7). No actualiza produccion:
un GO recomienda un grid, no lo promueve (eso exige E6).

Uso:
    python scripts/run_rec07_grid_5tun.py --workdir <dir>
    python scripts/run_rec07_grid_5tun.py --dry-run     # solo geometria
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_ID = "REC-07"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
FUENTE_R1 = PROJECT_ROOT / "scripts" / "artifacts_science" / "REC-01-R1"

PDB_5TUN = PROJECT_ROOT / "data" / "target_library" / "03_protease" / "5TUN.pdb"
PDB_1ITO = PROJECT_ROOT / "data" / "target_library" / "03_protease" / "1ITO.pdb"
VINA = PROJECT_ROOT / "tools" / "vina" / "vina.exe"

RUTAS_PROTEGIDAS = (
    PROJECT_ROOT / "curated_targets.json",
    PROJECT_ROOT / "curated_targets.csv",
)

# ── Congelado en el preregistro §4, §5 ───────────────────────────────────────
GRIDS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "G_DB":    ((11.151, 133.751, 14.09),  (22.0, 22.0, 22.0)),
    "G_MP":    ((8.44, 136.26, 21.28),     (24.9, 24.9, 24.9)),
    # Caja minima que contiene los 15 hotspots (CA) + los 3 atomos de la triada,
    # con 4.0 A de padding, leyendo Cys25:SG en altloc A (convencion del §3 del
    # preregistro, la misma que usa el receptor via --default_altloc A).
    "G_ADAPT": ((11.104, 135.221, 21.288), (19.0, 25.3, 25.9)),
}
CADENA = "A"
AGUAS = {"HOH", "WAT", "DOD"}
SEEDS = (42, 43, 44, 45, 46)
EXHAUSTIVENESS = 32
NUM_MODES = 9
CPU = 1
UMBRAL_CONTACTO_A = 5.0
LIGANDO_RESNAME = "E6C"

HOTSPOTS_5TUN = ("A:LYS17", "A:PHE28", "A:LYS181", "A:SER29", "A:VAL31",
                 "A:VAL164", "A:LEU165", "A:GLU84", "A:ASN182", "A:PRO50",
                 "A:SER183", "A:GLY32", "A:GLU35", "A:LEU48", "A:TYR89")
TRIADA = (("A:CYS25", "SG"), ("A:HIS162", "NE2"), ("A:ASN182", "ND2"))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


# ── Parseo ───────────────────────────────────────────────────────────────────

def leer_atomos(pdb: Path) -> dict[str, dict[str, tuple[float, float, float]]]:
    res: dict[str, dict[str, tuple[float, float, float]]] = {}
    for l in pdb.read_text(encoding="utf-8", errors="replace").splitlines():
        if not l.startswith("ATOM") or len(l) < 54:
            continue
        rn, ch = l[17:20].strip(), (l[21:22].strip() or "A")
        clave = f"{ch}:{rn}{l[22:26].strip()}"
        an = l[12:16].strip()
        res.setdefault(clave, {}).setdefault(
            an, (float(l[30:38]), float(l[38:46]), float(l[46:54])))
    return res


def filtrar_pdb(origen: Path, destino: Path) -> dict[str, Any]:
    """Filtra el PDB replicando backend/services/docking/preparer.py.

    1. solo ATOM/HETATM/TER/END/MODEL/ENDMDL;
    2. elimina aguas (HOH/WAT/DOD) — sin esto Meeko las conserva como parte del
       receptor rigido, llena el bolsillo y todo docking colisiona;
    3. conserva solo la cadena objetivo;
    4. descarta residue_seq <= 0;
    5. altloc: conserva la variante mayoritaria por residuo, prefiriendo la
       variante sin altloc si empata (misma regla que preparer.py).
    """
    contenido = origen.read_text(encoding="utf-8", errors="replace")

    # paso previo: elegir altloc por residuo
    por_residuo: dict[tuple, dict[str, int]] = {}
    for l in contenido.splitlines():
        if l[:6].strip() not in {"ATOM", "HETATM"} or len(l) < 27:
            continue
        rn = l[17:20].strip()
        if rn in AGUAS:
            continue
        ch = l[21:22].strip() or "A"
        try:
            sq = int(l[22:26].strip())
        except ValueError:
            continue
        cuentas = por_residuo.setdefault((ch, sq, rn), {})
        v = l[16:17]
        cuentas[v] = cuentas.get(v, 0) + 1

    elegido: dict[tuple, str] = {}
    for k, cuentas in por_residuo.items():
        if cuentas.get(" ", 0) >= max(cuentas.values()):
            elegido[k] = " "
        else:
            elegido[k] = max(cuentas, key=lambda v: (cuentas[v], v == " "))

    salida: list[str] = []
    stats = {"aguas_eliminadas": 0, "otra_cadena": 0, "altloc_descartado": 0, "conservadas": 0}
    for l in contenido.splitlines():
        rec = l[:6].strip()
        if rec not in {"ATOM", "HETATM", "TER", "END", "MODEL", "ENDMDL"}:
            continue
        if rec in {"TER", "END", "MODEL", "ENDMDL"}:
            salida.append(l)
            continue
        if len(l) < 27:
            continue
        rn = l[17:20].strip()
        ch = l[21:22].strip() or "A"
        if rn in AGUAS:
            stats["aguas_eliminadas"] += 1
            continue
        if ch != CADENA:
            stats["otra_cadena"] += 1
            continue
        try:
            sq = int(l[22:26].strip())
        except ValueError:
            continue
        if sq <= 0:
            continue
        if l[16:17] != elegido.get((ch, sq, rn), " "):
            stats["altloc_descartado"] += 1
            continue
        salida.append(l)
        stats["conservadas"] += 1

    destino.write_text("\n".join(salida) + "\nEND\n", encoding="utf-8")
    stats["altloc_cys25"] = elegido.get((CADENA, 25, "CYS"), "?")
    return stats


def dentro(pt, c, s) -> bool:
    return all(abs(pt[i] - c[i]) <= s[i] / 2 for i in range(3))


def margen(pt, c, s) -> float:
    return min(s[i] / 2 - abs(pt[i] - c[i]) for i in range(3))


def geometria_por_brazo(res: dict) -> dict[str, dict[str, Any]]:
    sg = res["A:CYS25"]["SG"]
    tri_pts = [res[r][a] for r, a in TRIADA]
    tri_cen = tuple(sum(p[i] for p in tri_pts) / 3 for i in range(3))
    hs = {h: res[h]["CA"] for h in HOTSPOTS_5TUN if h in res and "CA" in res[h]}

    salida = {}
    for nombre, (c, s) in GRIDS.items():
        m = {h: round(margen(v, c, s), 3) for h, v in hs.items()}
        salida[nombre] = {
            "centro": list(c), "tamano": list(s),
            "volumen_A3": round(s[0] * s[1] * s[2], 1),
            "d_cys25_sg": round(math.dist(c, sg), 3),
            "d_triada_centroide": round(math.dist(c, tri_cen), 3),
            "hotspots_dentro": sum(1 for v in hs.values() if dentro(v, c, s)),
            "hotspots_total": len(hs),
            "triada_dentro": sum(1 for p in tri_pts if dentro(p, c, s)),
            "margen_min_hotspots": round(min(m.values()), 3),
            "hotspots_fuera": sorted(h for h, v in m.items() if v < 0),
        }
    return salida


def parsear_poses(pdbqt: Path) -> list[dict[str, Any]]:
    """Modos con score de REMARK VINA RESULT y sus atomos pesados."""
    modos: list[dict[str, Any]] = []
    actual: dict[str, Any] | None = None
    for l in pdbqt.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.startswith("MODEL"):
            actual = {"score": None, "atomos": []}
        elif l.startswith("REMARK VINA RESULT") and actual is not None:
            try:
                actual["score"] = float(l.split()[3])
            except (IndexError, ValueError):
                actual["score"] = None
        elif l.startswith(("ATOM", "HETATM")) and actual is not None and len(l) >= 54:
            tipo = l[77:79].strip() if len(l) >= 79 else ""
            if tipo.upper().startswith("H") and tipo.upper() not in ("HD", "HS"):
                continue
            if tipo.upper() in ("H", "HD"):
                continue
            actual["atomos"].append((float(l[30:38]), float(l[38:46]), float(l[46:54])))
        elif l.startswith("ENDMDL") and actual is not None:
            modos.append(actual)
            actual = None
    return modos


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-07: grid APO de 5TUN")
    ap.add_argument("--workdir", type=str, default=None, help="directorio de trabajo para pdbqt/salidas")
    ap.add_argument("--dry-run", action="store_true", help="solo geometria, sin docking ni artefactos")
    args = ap.parse_args()

    t0 = time.time()
    hashes_pre = {p.name: sha256_file(p) for p in RUTAS_PROTEGIDAS if p.exists()}

    # ── Integridad de la entrada sellada (REC-01-R1) ──
    m_r1 = json.loads((FUENTE_R1 / "manifest.json").read_text(encoding="utf-8"))
    ah = m_r1.get("assets_hashes", {})
    clave = next((k for k in ah if k.endswith("REC-01-R1/per_complex.jsonl")), None)
    real_r1 = sha256_file(FUENTE_R1 / "per_complex.jsonl")
    entrada_ok = clave is not None and ah[clave] == real_r1
    fila_5tun = next(
        (json.loads(l) for l in (FUENTE_R1 / "per_complex.jsonl")
         .read_text(encoding="utf-8").splitlines()
         if l.strip() and json.loads(l)["pdb_id"] == "5TUN"), None)
    print(f"[REC-07] entrada REC-01-R1 integra: {entrada_ok} | 5TUN margen_min="
          f"{fila_5tun.get('margen_min_hotspots') if fila_5tun else '?'}", flush=True)

    # ── Geometría ──
    res = leer_atomos(PDB_5TUN)
    geo = geometria_por_brazo(res)
    sg = res["A:CYS25"]["SG"]

    print(f"\n{'brazo':<10}{'d(Cys25)':>10}{'d(triada)':>11}{'hotspots':>11}"
          f"{'triada':>8}{'margen':>9}{'volumen':>10}")
    for nom, g in geo.items():
        print(f"{nom:<10}{g['d_cys25_sg']:>10.2f}{g['d_triada_centroide']:>11.2f}"
              f"{g['hotspots_dentro']:>8}/{g['hotspots_total']}"
              f"{g['triada_dentro']:>6}/3{g['margen_min_hotspots']:>9.2f}"
              f"{g['volumen_A3']:>10,.0f}")

    if args.dry_run:
        print("\n[REC-07] --dry-run: geometría solamente, sin docking ni artefactos.")
        return 0

    wd = Path(args.workdir) if args.workdir else (OUT_DIR / "_work")
    wd.mkdir(parents=True, exist_ok=True)

    # ── Preparación (una sola vez: receptor y ligando comunes a los 3 brazos) ──
    rec_pdbqt = wd / "5TUN_receptor.pdbqt"
    pdb_filtrado = wd / "5TUN_filtrado.pdb"
    stats_filtro = filtrar_pdb(PDB_5TUN, pdb_filtrado)
    print(f"\n[REC-07] filtro de receptor (regla de preparer.py): "
          f"aguas eliminadas={stats_filtro['aguas_eliminadas']}, "
          f"otra cadena={stats_filtro['otra_cadena']}, "
          f"altloc descartado={stats_filtro['altloc_descartado']}, "
          f"conservadas={stats_filtro['conservadas']}, "
          f"altloc Cys25='{stats_filtro['altloc_cys25']}'", flush=True)

    if not rec_pdbqt.exists():
        print("[REC-07] preparando receptor…", flush=True)
        c0, s0 = GRIDS["G_ADAPT"]
        r = subprocess.run(
            [sys.executable, "-m", "meeko.cli.mk_prepare_receptor",
             "--read_pdb", str(pdb_filtrado), "-o", str(wd / "5TUN_receptor"), "-p",
             "--box_center", str(c0[0]), str(c0[1]), str(c0[2]),
             "--box_size", str(s0[0]), str(s0[1]), str(s0[2]),
             "--default_altloc", "A", "-a"],
            capture_output=True, text=True, timeout=900)
        if not rec_pdbqt.exists():
            print(f"[REC-07] FALLO preparando receptor:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
            return 2
        n_hoh = sum(1 for l in rec_pdbqt.read_text(encoding="utf-8", errors="replace").splitlines()
                    if "HOH" in l)
        if n_hoh:
            print(f"[REC-07] ABORTA: el receptor conserva {n_hoh} lineas HOH")
            return 2

    lig_pdbqt = wd / "E6C.pdbqt"
    if not lig_pdbqt.exists():
        print("[REC-07] preparando ligando E64c desde 1ITO…", flush=True)
        het = [l for l in PDB_1ITO.read_text(encoding="utf-8", errors="replace").splitlines()
               if l.startswith("HETATM") and l[17:20].strip() == LIGANDO_RESNAME]
        (wd / "E6C.pdb").write_text("\n".join(het) + "\nEND\n", encoding="utf-8")
        from openbabel import pybel
        mol = next(pybel.readfile("pdb", str(wd / "E6C.pdb")))
        mol.addh()
        mol.write("sdf", str(wd / "E6C.sdf"), overwrite=True)
        subprocess.run([sys.executable, "-m", "meeko.cli.mk_prepare_ligand",
                        "-i", str(wd / "E6C.sdf"), "-o", str(lig_pdbqt)],
                       capture_output=True, text=True, timeout=600)
        if not lig_pdbqt.exists():
            print("[REC-07] FALLO preparando ligando")
            return 2

    print(f"[REC-07] receptor sha {sha256_file(rec_pdbqt)[:16]} | "
          f"ligando sha {sha256_file(lig_pdbqt)[:16]}", flush=True)

    # ── Docking: 3 brazos x 5 semillas ──
    filas: list[dict[str, Any]] = []
    fallos: list[dict[str, Any]] = []
    for brazo, (c, s) in GRIDS.items():
        for seed in SEEDS:
            out = wd / f"out_{brazo}_{seed}.pdbqt"
            cmd = [str(VINA), "--receptor", str(rec_pdbqt), "--ligand", str(lig_pdbqt),
                   "--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
                   "--size_x", str(s[0]), "--size_y", str(s[1]), "--size_z", str(s[2]),
                   "--exhaustiveness", str(EXHAUSTIVENESS), "--num_modes", str(NUM_MODES),
                   "--seed", str(seed), "--cpu", str(CPU), "--out", str(out)]
            t1 = time.time()
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
                rc = r.returncode
            except subprocess.TimeoutExpired:
                rc = -9
                r = None

            fila: dict[str, Any] = {
                "brazo": brazo, "seed": seed, "rc": rc,
                "centro": list(c), "tamano": list(s),
                "wall_s": round(time.time() - t1, 2),
            }
            valido = rc == 0 and out.exists() and out.stat().st_size > 0
            if valido:
                modos = parsear_poses(out)
                scores_finitos = all(m["score"] is not None and math.isfinite(m["score"])
                                     for m in modos)
                fila["n_modos"] = len(modos)
                fila["scores_finitos"] = scores_finitos
                fila["geometria_parseable"] = all(m["atomos"] for m in modos)
                valido = (1 <= len(modos) <= NUM_MODES and scores_finitos
                          and fila["geometria_parseable"])
                if modos:
                    top = modos[0]
                    fila["score_top1"] = top["score"]
                    fila["d_min_cys25_sg_top1"] = round(
                        min(math.dist(a, sg) for a in top["atomos"]), 3)
                    fila["contacto_top1"] = fila["d_min_cys25_sg_top1"] <= UMBRAL_CONTACTO_A
                    fila["d_min_cys25_sg_mejor_de_9"] = round(
                        min(min(math.dist(a, sg) for a in m["atomos"]) for m in modos), 3)
            else:
                fila["n_modos"] = 0
                salida = ((r.stdout or "") + (r.stderr or ""))[-400:] if r else "timeout"
                fallos.append({"brazo": brazo, "seed": seed, "rc": rc, "salida": salida})
            fila["valido"] = valido
            filas.append(fila)
            print(f"  {brazo:<9} seed={seed}  rc={rc}  modos={fila.get('n_modos')}  "
                  f"top1={fila.get('score_top1')}  d(Cys25)={fila.get('d_min_cys25_sg_top1')}  "
                  f"{fila['wall_s']}s", flush=True)

    hashes_post = {p.name: sha256_file(p) for p in RUTAS_PROTEGIDAS if p.exists()}

    # ── Agregados por brazo ──
    def _mediana(xs: list[float]):
        xs = sorted(xs)
        if not xs:
            return None
        k = len(xs) // 2
        return round(xs[k] if len(xs) % 2 else (xs[k - 1] + xs[k]) / 2, 3)

    por_brazo = {}
    for brazo in GRIDS:
        f = [x for x in filas if x["brazo"] == brazo]
        ok = [x for x in f if x.get("valido")]
        d = [x["d_min_cys25_sg_top1"] for x in ok if "d_min_cys25_sg_top1" in x]
        sc = [x["score_top1"] for x in ok if x.get("score_top1") is not None]
        cont = sum(1 for x in ok if x.get("contacto_top1"))
        por_brazo[brazo] = {
            "geometria": geo[brazo],
            "n_corridas": len(f), "n_validas": len(ok),
            "contacto_top1_n": cont, "contacto_top1_de": len(SEEDS),
            "d_cys25_top1_mediana": _mediana(d),
            "d_cys25_top1_min": round(min(d), 3) if d else None,
            "score_top1_mediana": _mediana(sc),
            "score_top1_mejor": round(min(sc), 3) if sc else None,
            "wall_s_total": round(sum(x["wall_s"] for x in f), 1),
        }

    # ── Selección del grid recomendado (regla del preregistro §7) ──
    d_db = geo["G_DB"]["d_cys25_sg"]
    elegibles = [b for b, g in geo.items()
                 if g["hotspots_dentro"] == g["hotspots_total"]
                 and g["triada_dentro"] == 3
                 and g["d_cys25_sg"] <= d_db]
    # entre elegibles, menor volumen (menos coste de búsqueda)
    recomendado = min(elegibles, key=lambda b: geo[b]["volumen_A3"]) if elegibles else None

    g4 = None
    g5 = None
    if recomendado:
        r_ = por_brazo[recomendado]
        db_ = por_brazo["G_DB"]
        g4 = r_["contacto_top1_n"] >= 3
        peor_med = (r_["d_cys25_top1_mediana"] is not None
                    and db_["d_cys25_top1_mediana"] is not None
                    and r_["d_cys25_top1_mediana"] - db_["d_cys25_top1_mediana"] > 1.0)
        g5 = (r_["contacto_top1_n"] >= db_["contacto_top1_n"]) and not peor_med

    metricas = {
        "experiment_id": EXPERIMENT_ID,
        "target": "5TUN",
        "prueba_ciega": {
            "geometria": False,
            "docking": "parcial: 1 smoke previo (G_ADAPT, exh=8, seed=42, top1=-4.418) "
                       "sin medir distancia a Cys25 y sin otros brazos ni semillas",
        },
        "entrada_sellada": {
            "fuente": "REC-01-R1/per_complex.jsonl",
            "integra": entrada_ok,
            "sha256": real_r1,
            "5TUN_margen_min_hotspots": fila_5tun.get("margen_min_hotspots") if fila_5tun else None,
            "5TUN_excepciones": fila_5tun.get("excepciones") if fila_5tun else None,
        },
        "ancla_independiente": {
            "familia": "papaina / cisteina-proteasa C1",
            "triada": "Cys25-His162-Asn182",
            "cys25_sg": [round(v, 3) for v in sg],
            "nota": "independiente de MolPocket, de los hotspots del catalogo y de toda prediccion",
        },
        "config_docking": {
            "ligando": f"{LIGANDO_RESNAME} (E64c) extraido de 1ITO.pdb",
            "formula": "C15H28N2O5",
            "exhaustiveness": EXHAUSTIVENESS, "num_modes": NUM_MODES,
            "cpu": CPU, "seeds": list(SEEDS),
            "umbral_contacto_A": UMBRAL_CONTACTO_A,
            "receptor_sha256": sha256_file(rec_pdbqt),
            "ligando_sha256": sha256_file(lig_pdbqt),
            "receptor_unico_para_los_3_brazos": True,
            "filtro_receptor": {
                "regla": "replica backend/services/docking/preparer.py",
                "aguas_eliminadas_lineas": stats_filtro["aguas_eliminadas"],
                "otra_cadena_lineas": stats_filtro["otra_cadena"],
                "altloc_descartado_lineas": stats_filtro["altloc_descartado"],
                "lineas_conservadas": stats_filtro["conservadas"],
                "altloc_cys25_elegido": stats_filtro["altloc_cys25"],
                "cadena": CADENA,
            },
            "residuo_eliminado": "A:49 (SER con cadena lateral incompleta, sin OG; "
                                 "13.64 A de Cys25 SG; -a/--allow_bad_res, mismo fallback "
                                 "que preparer.py; identico en los 3 brazos)",
            "limitacion": "Vina hace docking NO covalente y E64c es inhibidor covalente: "
                          "el criterio es CONTACTO, no distancia de enlace. 5TUN es APO, "
                          "no hay pose cristalografica de referencia: no se afirma exactitud de pose.",
        },
        "por_brazo": por_brazo,
        "recomendado": recomendado,
        "gates": {
            "G1_contencion": {
                "criterio": "grid recomendado con 15/15 hotspots y 3/3 triada",
                "recomendado": recomendado,
                "pass": bool(recomendado),
            },
            "G2_ancla": {
                "criterio": f"d(centro, Cys25 SG) <= {d_db} A (G_DB)",
                "d_recomendado": geo[recomendado]["d_cys25_sg"] if recomendado else None,
                "d_G_DB": d_db,
                "pass": bool(recomendado and geo[recomendado]["d_cys25_sg"] <= d_db),
            },
            "G3_validez_docking": {
                "criterio": "rc=0, no vacio, 1<=modos<=9, scores finitos de REMARK VINA RESULT, geometria parseable",
                "n_corridas": len(filas),
                "n_validas": sum(1 for x in filas if x.get("valido")),
                "pass": all(x.get("valido") for x in filas),
            },
            "G4_contacto_catalitico": {
                "criterio": f"top-1 a <= {UMBRAL_CONTACTO_A} A de Cys25 SG en >=3 de 5 semillas",
                "contacto_n": por_brazo[recomendado]["contacto_top1_n"] if recomendado else None,
                "pass": g4,
            },
            "G5_no_regresion": {
                "criterio": "tasa de contacto no menor que G_DB y mediana no peor por mas de 1.0 A",
                "pass": g5,
            },
            "G6_determinismo": {"criterio": "misma semilla -> mismo top1 y misma distancia", "pass": None},
            "G7_solo_lectura": {
                "criterio": "catalogo y CSV conservan su SHA-256",
                "hashes_pre": hashes_pre, "hashes_post": hashes_post,
                "pass": hashes_pre == hashes_post,
            },
        },
        "alcance": {
            "no_actualiza_catalogo": True,
            "nota": "un GO RECOMIENDA un grid; promover a produccion exige E6 "
                    "(no-regresion, manifest, rollback), fuera de alcance",
        },
        "entorno": {
            "python": platform.python_version(),
            "so": f"{platform.system()} {platform.release()}",
            "vina": str(VINA.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "vina_sha256": sha256_file(VINA) if VINA.exists() else None,
            "duracion_s": round(time.time() - t0, 2),
            "generado_utc": datetime.now(timezone.utc).isoformat(),
        },
    }

    print("\n" + "=" * 68)
    print("REC-07 — GRID APO DE 5TUN")
    print("=" * 68)
    print(f"{'brazo':<10}{'validas':>9}{'contacto':>10}{'d(Cys25) med':>14}{'score med':>11}")
    for b, v in por_brazo.items():
        print(f"{b:<10}{v['n_validas']:>6}/{v['n_corridas']}"
              f"{v['contacto_top1_n']:>7}/{v['contacto_top1_de']}"
              f"{(v['d_cys25_top1_mediana'] if v['d_cys25_top1_mediana'] is not None else float('nan')):>14.2f}"
              f"{(v['score_top1_mediana'] if v['score_top1_mediana'] is not None else float('nan')):>11.2f}")
    print(f"\nGrid recomendado: {recomendado}")
    print("\nGates:")
    for g, d in metricas["gates"].items():
        print(f"  {g:<26} {{}}".format() if False else
              f"  {g:<26} {'PASS' if d['pass'] else ('FAIL' if d['pass'] is False else 'PENDIENTE')}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for x in filas:
            f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for x in fallos:
            f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT_DIR / "metrics.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    print(f"\n[REC-07] artefactos en {OUT_DIR.relative_to(PROJECT_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
