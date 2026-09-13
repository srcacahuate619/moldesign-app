#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf33_ensemble.py — MF-33: ¿aporta algo el ensemble cuando el docking es flexible?

Corre en la maquina local (binario de `tools/vina`).

La pregunta
-----------
El brazo de control de `MF-28` midio algo que nadie habia preguntado: dockeando
**flexibles** los mismos conformeros que el protocolo congelado dockea **rigidos**, la
cobertura del estrato dificil pasa de 3/33 a 26/33. Mismos conformeros, mismo receptor,
misma caja — `molflex.py` escribe las dos codificaciones desde el mismo objeto:

    rigid_str, flex_str, mapa, _err = escribir_pdbqt(setups[0])
    conf{cid}.rigid.pdbqt   <- un solo ROOT, TORSDOF 0
    conf{cid}.flex.pdbqt    <- arbol de torsiones

Eso deja abierta la pregunta que decide si MolFlex tiene arreglo o sobra:

  * si **un solo** conformero flexible alcanza lo mismo que los K del ensemble,
    MolFlex no esta roto, es **REDUNDANTE**;
  * si los K aportan sobre uno, el ensemble si sirve y hay diana medible.

Los tres brazos
---------------
  A  `conf0.flex.pdbqt`          — un conformero, flexible
  B  todos los `conf*.flex.pdbqt` — REUSADO de MF-28, sin recomputo
  C  todos los `conf*.rigid.pdbqt` — el protocolo congelado de MolFlex

Todos a exh=8, semilla 42, num_modes=9, caja 25 A, mismo receptor. CPU medida.

Por que conf0 y no el mejor
---------------------------
Se toma el **primer** conformero por indice, sin mirar su RMSD al cristal. Elegir el
mejor seria informacion de oraculo que en produccion no existe, y convertiria el brazo A
en una cota superior irreal. Queda declarado en el prerregistro.

Regla de lectura, escrita antes
-------------------------------
El resultado interesante de este experimento es la AUSENCIA de diferencia, y esa no se
demuestra con un test de superioridad: "no significativo" con n=33 se explica por falta
de potencia por defecto. Por eso se declara un margen de equivalencia de +-4 complejos.
Ver el gate de `MF-33-PRE`.
"""

from __future__ import annotations

import argparse
import json
import re
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
EXH = 8
NUM_MODES = 9
UMBRAL_A = 2.0

RE_RIGID = re.compile(r"conf\d+\.rigid\.pdbqt$")   # excluye *.relax.rigid.* (leccion MF-21)
CONF0 = "conf0.flex.pdbqt"


def _dock(vina_bin: str, rec: Path, lig: Path, centro, salida: Path) -> float:
    """Ejecuta un dock y devuelve el tiempo consumido; -1 si fallo."""
    cmd = [vina_bin, "--receptor", str(rec), "--ligand", str(lig),
           "--center_x", str(centro[0]), "--center_y", str(centro[1]),
           "--center_z", str(centro[2]), "--size_x", str(BOX),
           "--size_y", str(BOX), "--size_z", str(BOX),
           "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
           "--seed", str(SEED), "--cpu", "1", "--out", str(salida)]
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
        ok = p.returncode == 0 and salida.exists()
    except subprocess.TimeoutExpired:
        ok = False
    return (time.time() - t0) if ok else -1.0


def analizar(pid: str, estrato: str, ws: Path, vina_bin: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "brazos": {}}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen = w / "rec.pdbqt", w / "center.json"
    if not rec.exists() or not cen.exists() or not (w / "index_map.json").exists():
        out["error"] = "SIN_MATERIAL"
        return out
    centro = json.loads(cen.read_text(encoding="utf-8"))
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}

    def mejor_rmsd(salida: Path) -> Optional[float]:
        best = None
        for _sc, at in mf.parsear_out_vina(
                salida.read_text(encoding="utf-8", errors="replace")):
            c = mf.coords_pose_a_por_mol(at, s2m)
            if not c:
                continue
            v = mf.rmsd_pose_pocket(crystal, c)
            if v is not None and (best is None or v < best):
                best = v
        return best

    # ── brazo A: un solo conformero, flexible ────────────────────────────────
    ligA = w / CONF0
    if not ligA.exists():
        out["error"] = "SIN_CONF0"
        return out
    sal = tmp / f"{pid}_A.pdbqt"
    tA = _dock(vina_bin, rec, ligA, centro, sal)
    if tA < 0:
        out["brazos"]["A"] = {"error": "VINA_FALLO"}
    else:
        r = mejor_rmsd(sal)
        out["brazos"]["A"] = {"rmsd_min": round(r, 3) if r is not None else None,
                              "alcanza": bool(r is not None and r <= UMBRAL_A),
                              "cpu_s": round(tA, 1), "n_docks": 1,
                              "ligando": CONF0}
        sal.unlink(missing_ok=True)

    # ── brazo C: todos los conformeros, RIGIDO (protocolo congelado) ─────────
    rigidos = sorted([f for f in w.glob("conf*.rigid.pdbqt") if RE_RIGID.match(f.name)])
    if not rigidos:
        out["brazos"]["C"] = {"error": "SIN_CONFORMEROS"}
    else:
        tC = 0.0
        best = None
        for f in rigidos:
            sal = tmp / f"{pid}_C_{f.stem}.pdbqt"
            t = _dock(vina_bin, rec, f, centro, sal)
            if t < 0:
                continue
            tC += t
            r = mejor_rmsd(sal)
            if r is not None and (best is None or r < best):
                best = r
            sal.unlink(missing_ok=True)
        out["brazos"]["C"] = {"rmsd_min": round(best, 3) if best is not None else None,
                              "alcanza": bool(best is not None and best <= UMBRAL_A),
                              "cpu_s": round(tC, 1), "n_docks": len(rigidos)}

    out["t_s"] = round(time.time() - t0, 1)
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
    ap = argparse.ArgumentParser(description="MF-33: aporta el ensemble bajo docking flexible?")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--vina", default=str(PROJECT_ROOT / "tools" / "vina" / "vina.exe"))
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-33"
    out_dir.mkdir(parents=True, exist_ok=True)

    coh = json.loads((ws / "scripts" / "artifacts_science" / "MF-02F" /
                      "cohorte.json").read_text(encoding="utf-8"))
    jobs = [(p, "COLOCACION") for p in coh["cohorte_colocacion"]] + \
           [(p, "CONTROL") for p in coh["control_cubiertos"]]
    if args.limite:
        jobs = jobs[:args.limite]

    # brazo B: se REUSA de MF-28 sin recomputo
    b28 = {}
    p28 = ws / "scripts" / "artifacts_science" / "MF-28" / "per_complex.jsonl"
    if p28.exists():
        for l in p28.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                if "vina" in r:
                    b28[r["pid"]] = r["vina"]
    print(f"[MF-33] {len(jobs)} complejos | brazo B reusado de MF-28: {len(b28)} "
          f"complejos, sin recomputo", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, pid, est, ws, args.vina, tmp): pid
                    for pid, est in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                r = fut.result()
                if r["pid"] in b28:
                    v = b28[r["pid"]]
                    r["brazos"]["B"] = {"rmsd_min": v["rmsd_min"], "alcanza": v["alcanza"],
                                        "cpu_s": v["cpu_s"], "n_docks": v["n_docks"],
                                        "origen": "MF-28 (reusado, sin recomputo)"}
                filas.append(r)
                a = r["brazos"].get("A", {})
                c = r["brazos"].get("C", {})
                b = r["brazos"].get("B", {})
                print(f"  [{i}/{len(jobs)}] {r['pid']} [{r['estrato']}] "
                      f"A={a.get('rmsd_min')} ({a.get('cpu_s')}s)  "
                      f"C={c.get('rmsd_min')} ({c.get('cpu_s')}s)  "
                      f"B={b.get('rmsd_min')}  {r.get('error','')} "
                      f"({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8",
                          newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas
          if all(k in r["brazos"] and "rmsd_min" in r["brazos"][k] for k in ("A", "B", "C"))]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        bAB = sum(1 for r in g if r["brazos"]["A"]["alcanza"] and not r["brazos"]["B"]["alcanza"])
        cAB = sum(1 for r in g if r["brazos"]["B"]["alcanza"] and not r["brazos"]["A"]["alcanza"])
        d = {"n": len(g)}
        for k in ("A", "B", "C"):
            d[f"{k}_alcanza"] = sum(1 for r in g if r["brazos"][k]["alcanza"])
            d[f"{k}_rmsd_mediano"] = _mediana([r["brazos"][k]["rmsd_min"] for r in g], 3)
            d[f"{k}_cpu_mediana_s"] = _mediana([r["brazos"][k]["cpu_s"] for r in g], 1)
        d["AvsB_b_gana_A"] = bAB
        d["AvsB_c_gana_B"] = cAB
        d["AvsB_mcnemar_p"] = _mcnemar(bAB, cAB)
        d["AvsB_delta_complejos"] = d["B_alcanza"] - d["A_alcanza"]
        d["margen_equivalencia_declarado"] = "+-4 complejos (+-12 pp)"
        d["mde_superioridad_declarado"] = "b>=6 con c=0"
        resumen[est] = d

    metrics = {
        "experiment_id": "MF-33",
        "tipo": "comparacion pareada de tres brazos (aporta el ensemble?)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"box": BOX, "seed": SEED, "exh": EXH, "num_modes": NUM_MODES,
                   "umbral_A": UMBRAL_A, "conformero_brazo_A": CONF0,
                   "eleccion_conf0": "primero por indice, SIN mirar RMSD (declarado)",
                   "brazo_B": "reusado de MF-28 sin recomputo"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "por_estrato": resumen,
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"[MF-33] LISTO n={len(ok)} ({round(time.time()-t0)}s)", flush=True)
    for est, d in resumen.items():
        print(f"  {est}: A {d['A_alcanza']}/{d['n']}  B {d['B_alcanza']}/{d['n']}  "
              f"C {d['C_alcanza']}/{d['n']}  |  A vs B: b={d['AvsB_b_gana_A']} "
              f"c={d['AvsB_c_gana_B']} p={d['AvsB_mcnemar_p']} "
              f"delta={d['AvsB_delta_complejos']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
