#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf33a3_reinicios.py — MF-33-A3: ¿la ventaja era la diversidad, o eran las poses?

Corre en la maquina local. Etapa 3 y corrigendum de `MF-33`.

NO LANZAR SIN LEER ESTO
-----------------------
Coste aproximado: el mismo que el brazo B de `MF-33`, unas **42 CPU-h**, es decir
**4-6 h con 10 workers** y la maquina al 90% de CPU sostenido. Pensado para lanzarse con
la maquina descansada.

El defecto que motiva el experimento
------------------------------------
La metrica del programa es de **oraculo**: el mejor RMSD entre las poses que el brazo
**conserva**. Y `num_modes=9` limita cuantas poses escribe Vina **por corrida**, no
cuantas busca.

    brazo A   1 corrida   ->   9 poses conservadas
    brazo A2  1 corrida   ->   9 poses conservadas  (subir exhaustiveness NO lo cambia)
    brazo B   29 corridas -> 261 poses conservadas  (mediana)

El brazo B extrae su oraculo de **29 veces mas muestras**. Aunque la calidad de busqueda
fuese identica, ganaria solo por conservar mas poses. Eso no es un mecanismo: es un
artefacto de medicion, y contamina tanto el 26-contra-12 de `MF-33` como el 26-contra-19
de `MF-33-A2`.

El brazo A3
-----------
K corridas **independientes** de Vina desde el **mismo** `conf0.flex.pdbqt`, con
K = `n_docks` del brazo B en ese complejo, `exh=8`, `num_modes=9` y **semillas distintas**
(42, 43, ... 42+K-1). El oraculo se toma sobre las K*9 poses.

Eso iguala a B en las tres variables confundidas —corridas independientes, poses
conservadas y CPU aproximada— dejando como **unica** diferencia la conformacion de
partida. Es la comparacion limpia que ni `MF-33` ni `MF-33-A2` pudieron hacer.

Lectura preregistrada (ver `MF-33-A3-PRE`)
------------------------------------------
Con `g_A3` = complejos donde A3 alcanza y B no, y `g_B` = donde B alcanza y A3 no:

  * A3 equivalente a B (diferencia dentro de +-4) -> la ventaja era el **conteo de
    poses**; la diversidad conformacional no aporta y la magnitud de MF-33 colapsa;
  * `g_B >= 6` con `g_A3 = 0` -> la **diversidad conformacional es real**; MF-33
    sobrevive con magnitud corregida;
  * cualquier otro caso, incluido `g_B >= 6` con `g_A3 >= 1` -> **MIXTA**, se reporta la
    fraccion y no se autoriza atribucion causal limpia.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

BOX = 25.0
SEED_BASE = 42
EXH = 8
NUM_MODES = 9
UMBRAL_A = 2.0
CONF0 = "conf0.flex.pdbqt"


def analizar(pid: str, estrato: str, k: int, ws: Path, vina_bin: str,
             tmp: Path) -> Dict[str, Any]:
    import molflex as mf

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "k_corridas": k}
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen, lig = w / "rec.pdbqt", w / "center.json", w / CONF0
    if not rec.exists() or not cen.exists() or not lig.exists() or \
       not (w / "index_map.json").exists():
        out["error"] = "SIN_MATERIAL"
        return out
    centro = json.loads(cen.read_text(encoding="utf-8"))
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}

    t0 = time.time()
    best = None
    n_poses = 0
    fallos = 0
    for j in range(k):
        semilla = SEED_BASE + j
        salida = tmp / f"{pid}_A3_s{semilla}.pdbqt"
        cmd = [vina_bin, "--receptor", str(rec), "--ligand", str(lig),
               "--center_x", str(centro[0]), "--center_y", str(centro[1]),
               "--center_z", str(centro[2]), "--size_x", str(BOX),
               "--size_y", str(BOX), "--size_z", str(BOX),
               "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
               "--seed", str(semilla), "--cpu", "1", "--out", str(salida)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok = False
        if not ok:
            fallos += 1
            continue
        for _sc, at in mf.parsear_out_vina(
                salida.read_text(encoding="utf-8", errors="replace")):
            c = mf.coords_pose_a_por_mol(at, s2m)
            if not c:
                continue
            n_poses += 1
            v = mf.rmsd_pose_pocket(crystal, c)
            if v is not None and (best is None or v < best):
                best = v
        salida.unlink(missing_ok=True)

    out["rmsd_min"] = round(best, 3) if best is not None else None
    out["alcanza"] = bool(best is not None and best <= UMBRAL_A)
    out["cpu_s"] = round(time.time() - t0, 1)
    out["n_poses_conservadas"] = n_poses
    out["n_corridas_fallidas"] = fallos
    return out


def _mcnemar(b: int, c: int) -> Optional[float]:
    n = b + c
    if n == 0:
        return None
    from math import comb
    k = min(b, c)
    return round(min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / (2 ** n)), 4)


def _mediana(vals, dec):
    v = [x for x in vals if x is not None]
    return round(median(v), dec) if v else None


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-33-A3: reinicios y poses igualados a B")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--vina", default=str(PROJECT_ROOT / "tools" / "vina" / "vina.exe"))
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-33-A3"
    out_dir.mkdir(parents=True, exist_ok=True)

    prev = {}
    for l in (art / "MF-33" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            prev[r["pid"]] = r
    a2 = {}
    p_a2 = art / "MF-33-A2" / "per_complex.jsonl"
    if p_a2.exists():
        for l in p_a2.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                a2[r["pid"]] = r

    jobs = []
    for pid, r in prev.items():
        b = r.get("brazos", {}).get("B", {})
        if not b.get("n_docks"):
            continue
        jobs.append((pid, r["estrato"], int(b["n_docks"])))
    jobs.sort(key=lambda x: x[0])
    if args.limite:
        jobs = jobs[:args.limite]

    print(f"[MF-33-A3] {len(jobs)} complejos | K mediano "
          f"{int(median(j[2] for j in jobs))} corridas | semillas {SEED_BASE}..{SEED_BASE}+K-1",
          flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, pid, est, k, ws, args.vina, tmp): pid
                    for pid, est, k in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                r = fut.result()
                br = prev.get(r["pid"], {}).get("brazos", {})
                for nom in ("A", "B", "C"):
                    r[nom] = {k2: br.get(nom, {}).get(k2)
                              for k2 in ("rmsd_min", "alcanza", "cpu_s", "n_docks")}
                x2 = a2.get(r["pid"], {})
                r["A2"] = {"rmsd_min": x2.get("rmsd_min"), "alcanza": x2.get("alcanza"),
                           "cpu_s": x2.get("cpu_s"), "exh": x2.get("exh_A2")}
                filas.append(r)
                print(f"  [{i}/{len(jobs)}] {r['pid']} [{r['estrato']}] K={r['k_corridas']} "
                      f"A3={r.get('rmsd_min')} ({r.get('cpu_s')}s, "
                      f"{r.get('n_poses_conservadas')} poses)  "
                      f"A2={r['A2']['rmsd_min']} B={r['B']['rmsd_min']} "
                      f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8",
                          newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if r.get("rmsd_min") is not None and r["B"]["alcanza"] is not None]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        g_a3 = sum(1 for r in g if r["alcanza"] and not r["B"]["alcanza"])
        g_b = sum(1 for r in g if r["B"]["alcanza"] and not r["alcanza"])
        d = {
            "n": len(g),
            "A_alcanza": sum(1 for r in g if r["A"]["alcanza"]),
            "A2_alcanza": sum(1 for r in g if r["A2"]["alcanza"]),
            "A3_alcanza": sum(1 for r in g if r["alcanza"]),
            "B_alcanza": sum(1 for r in g if r["B"]["alcanza"]),
            "C_alcanza": sum(1 for r in g if r["C"]["alcanza"]),
            "g_A3_alcanza_y_B_no": g_a3,
            "g_B_alcanza_y_A3_no": g_b,
            "A3vsB_mcnemar_p": _mcnemar(g_a3, g_b),
            "A3vsB_delta_complejos": sum(1 for r in g if r["B"]["alcanza"])
                                     - sum(1 for r in g if r["alcanza"]),
            "A3_rmsd_mediano": _mediana([r["rmsd_min"] for r in g], 3),
            "A3_poses_medianas": _mediana([r["n_poses_conservadas"] for r in g], 1),
            "A3_cpu_mediana_s": _mediana([r["cpu_s"] for r in g], 1),
            "B_cpu_mediana_s": _mediana([r["B"]["cpu_s"] for r in g], 1),
            "n_corridas_fallidas": sum(r["n_corridas_fallidas"] for r in g),
            "margen_equivalencia_declarado": "+-4 complejos",
            "mde_declarado": "g_B >= 6 con g_A3 = 0",
        }
        if d["A3_cpu_mediana_s"] and d["B_cpu_mediana_s"]:
            d["razon_cpu_A3_sobre_B"] = round(d["A3_cpu_mediana_s"] / d["B_cpu_mediana_s"], 3)
        resumen[est] = d

    metrics = {
        "experiment_id": "MF-33-A3",
        "tipo": "corrigendum y control de confundido (poses y reinicios igualados)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"box": BOX, "exh": EXH, "num_modes": NUM_MODES, "umbral_A": UMBRAL_A,
                   "ligando": CONF0, "semillas": f"{SEED_BASE}..{SEED_BASE}+K-1",
                   "K": "n_docks del brazo B por complejo",
                   "brazos_reusados": "A, B, C de MF-33 y A2 de MF-33-A2, sin recomputo"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "por_estrato": resumen,
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"[MF-33-A3] LISTO n={len(ok)} ({round(time.time()-t0)}s)", flush=True)
    for est, d in resumen.items():
        print(f"  {est}: C {d['C_alcanza']}  A {d['A_alcanza']}  A2 {d['A2_alcanza']}  "
              f"A3 {d['A3_alcanza']}  B {d['B_alcanza']} /{d['n']}  |  A3 vs B: "
              f"g_A3={d['g_A3_alcanza_y_B_no']} g_B={d['g_B_alcanza_y_A3_no']} "
              f"p={d['A3vsB_mcnemar_p']} | poses A3={d['A3_poses_medianas']} | "
              f"CPU A3/B={d.get('razon_cpu_A3_sobre_B')}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
