#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf33a2_paridad_cpu.py — MF-33-A2: ¿la brecha era el ensemble o era la CPU?

Corre en la maquina local. Etapa 2 de `MF-33`, declarada condicional en su prerregistro y
activada porque el brazo B supero al A con 14 discordantes a favor y 0 en contra.

El confundido que hay que romper
--------------------------------
`MF-33` midio que el ensemble flexible (brazo B) convierte 26 de 33 y un solo conformero
flexible (brazo A) convierte 12. Pero B consume **27 veces** la CPU de A —3,822 s contra
140 s de mediana—, de modo que la brecha admite dos explicaciones que aquel diseno no
separa: el **ensemble**, o el **presupuesto**.

Este experimento le da al brazo A la CPU de B y vuelve a medir.

Como se iguala el presupuesto
-----------------------------
Vina escala aproximadamente lineal en `exhaustiveness`, asi que por complejo:

    exh_A2 = round(8 * cpu_B / cpu_A)

acotado a [8, 1024]. Cuando el tope actua se registra, porque en esos complejos la
paridad de CPU no se alcanza y el brazo A2 queda en desventaja declarada.

Todo lo demas congelado: el MISMO `conf0.flex.pdbqt` del brazo A —primero por indice, sin
mirar su RMSD—, semilla 42, `num_modes=9`, caja 25 A, mismo receptor, misma metrica. Los
brazos A y B se reusan de `MF-33` sin recomputo.

Regla de lectura, escrita antes (ver `MF-33-A2-PRE`)
---------------------------------------------------
  * A2 equivalente a B  -> la brecha era CPU; el ensemble NO aporta y MolFlex vuelve a ser
    redundante pese al resultado de MF-33;
  * B sigue superando a A2 con >=6 discordantes y 0 en contra -> la brecha era el
    ensemble; la reapertura de la cartera C queda confirmada;
  * recuperacion parcial -> se reporta la fraccion y NO se autoriza atribucion causal.
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
SEED = 42
EXH_BASE = 8
EXH_TOPE = 1024
NUM_MODES = 9
UMBRAL_A = 2.0
CONF0 = "conf0.flex.pdbqt"


def analizar(pid: str, estrato: str, exh: int, tope: bool, ws: Path,
             vina_bin: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "exh_A2": exh,
                           "tope_activo": tope}
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

    salida = tmp / f"{pid}_A2.pdbqt"
    cmd = [vina_bin, "--receptor", str(rec), "--ligand", str(lig),
           "--center_x", str(centro[0]), "--center_y", str(centro[1]),
           "--center_z", str(centro[2]), "--size_x", str(BOX),
           "--size_y", str(BOX), "--size_z", str(BOX),
           "--exhaustiveness", str(exh), "--num_modes", str(NUM_MODES),
           "--seed", str(SEED), "--cpu", "1", "--out", str(salida)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=28800)
        ok = p.returncode == 0 and salida.exists()
    except subprocess.TimeoutExpired:
        ok = False
    t = time.time() - t0
    if not ok:
        out["error"] = "VINA_FALLO"
        out["cpu_s"] = round(t, 1)
        return out

    best = None
    for _sc, at in mf.parsear_out_vina(
            salida.read_text(encoding="utf-8", errors="replace")):
        c = mf.coords_pose_a_por_mol(at, s2m)
        if not c:
            continue
        v = mf.rmsd_pose_pocket(crystal, c)
        if v is not None and (best is None or v < best):
            best = v
    salida.unlink(missing_ok=True)
    out["rmsd_min"] = round(best, 3) if best is not None else None
    out["alcanza"] = bool(best is not None and best <= UMBRAL_A)
    out["cpu_s"] = round(t, 1)
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
    ap = argparse.ArgumentParser(description="MF-33-A2: paridad de CPU sobre un conformero")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--vina", default=str(PROJECT_ROOT / "tools" / "vina" / "vina.exe"))
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-33-A2"
    out_dir.mkdir(parents=True, exist_ok=True)

    # brazos A y B: se REUSAN de MF-33 sin recomputo
    prev = {}
    for l in (ws / "scripts" / "artifacts_science" / "MF-33" /
              "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            prev[r["pid"]] = r

    jobs = []
    for pid, r in prev.items():
        br = r.get("brazos", {})
        a, b = br.get("A", {}), br.get("B", {})
        if a.get("cpu_s") is None or b.get("cpu_s") is None or a["cpu_s"] <= 0:
            continue
        exh = int(round(EXH_BASE * b["cpu_s"] / a["cpu_s"]))
        tope = exh > EXH_TOPE
        exh = max(EXH_BASE, min(EXH_TOPE, exh))
        jobs.append((pid, r["estrato"], exh, tope))
    jobs.sort(key=lambda x: x[0])
    if args.limite:
        jobs = jobs[:args.limite]

    n_tope = sum(1 for j in jobs if j[3])
    print(f"[MF-33-A2] {len(jobs)} complejos | exh mediano "
          f"{int(median(j[2] for j in jobs))} | tope de {EXH_TOPE} actua en {n_tope}",
          flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, pid, est, exh, tope, ws, args.vina, tmp): pid
                    for pid, est, exh, tope in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                r = fut.result()
                p = prev.get(r["pid"], {}).get("brazos", {})
                r["A"] = {k: p.get("A", {}).get(k) for k in ("rmsd_min", "alcanza", "cpu_s")}
                r["B"] = {k: p.get("B", {}).get(k) for k in ("rmsd_min", "alcanza", "cpu_s")}
                filas.append(r)
                print(f"  [{i}/{len(jobs)}] {r['pid']} [{r['estrato']}] "
                      f"exh={r['exh_A2']} A2={r.get('rmsd_min')} ({r.get('cpu_s')}s)  "
                      f"A={r['A']['rmsd_min']} B={r['B']['rmsd_min']} "
                      f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8",
                          newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if r.get("rmsd_min") is not None
          and r["B"]["alcanza"] is not None and r["A"]["alcanza"] is not None]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        b2 = sum(1 for r in g if r["alcanza"] and not r["B"]["alcanza"])
        c2 = sum(1 for r in g if r["B"]["alcanza"] and not r["alcanza"])
        bA = sum(1 for r in g if r["alcanza"] and not r["A"]["alcanza"])
        cA = sum(1 for r in g if r["A"]["alcanza"] and not r["alcanza"])
        resumen[est] = {
            "n": len(g),
            "A_alcanza": sum(1 for r in g if r["A"]["alcanza"]),
            "A2_alcanza": sum(1 for r in g if r["alcanza"]),
            "B_alcanza": sum(1 for r in g if r["B"]["alcanza"]),
            "A2vsB_gana_A2": b2, "A2vsB_gana_B": c2,
            "A2vsB_mcnemar_p": _mcnemar(b2, c2),
            "A2vsB_delta_complejos": sum(1 for r in g if r["B"]["alcanza"])
                                     - sum(1 for r in g if r["alcanza"]),
            "A2vsA_gana_A2": bA, "A2vsA_gana_A": cA,
            "A2vsA_mcnemar_p": _mcnemar(bA, cA),
            "A2_rmsd_mediano": _mediana([r["rmsd_min"] for r in g], 3),
            "A2_cpu_mediana_s": _mediana([r["cpu_s"] for r in g], 1),
            "B_cpu_mediana_s": _mediana([r["B"]["cpu_s"] for r in g], 1),
            "razon_cpu_A2_sobre_B": None,
            "n_tope_activo": sum(1 for r in g if r["tope_activo"]),
            "margen_equivalencia_declarado": "+-4 complejos",
            "mde_declarado": "6 discordantes a favor de B con 0 en contra",
        }
        a2c = resumen[est]["A2_cpu_mediana_s"]
        bc = resumen[est]["B_cpu_mediana_s"]
        if a2c and bc:
            resumen[est]["razon_cpu_A2_sobre_B"] = round(a2c / bc, 3)

    metrics = {
        "experiment_id": "MF-33-A2",
        "tipo": "control de confundido (paridad de CPU)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"box": BOX, "seed": SEED, "exh_base": EXH_BASE, "exh_tope": EXH_TOPE,
                   "num_modes": NUM_MODES, "umbral_A": UMBRAL_A, "ligando": CONF0,
                   "escalado": "exh_A2 = round(8 * cpu_B / cpu_A) por complejo",
                   "brazos_A_y_B": "reusados de MF-33 sin recomputo"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "por_estrato": resumen,
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"[MF-33-A2] LISTO n={len(ok)} ({round(time.time()-t0)}s)", flush=True)
    for est, d in resumen.items():
        print(f"  {est}: A {d['A_alcanza']}/{d['n']}  A2 {d['A2_alcanza']}/{d['n']}  "
              f"B {d['B_alcanza']}/{d['n']}  |  A2 vs B: gana_A2={d['A2vsB_gana_A2']} "
              f"gana_B={d['A2vsB_gana_B']} p={d['A2vsB_mcnemar_p']} "
              f"delta={d['A2vsB_delta_complejos']} | CPU A2/B={d['razon_cpu_A2_sobre_B']}",
              flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
