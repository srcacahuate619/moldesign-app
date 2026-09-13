#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_fnd03_varianza_semilla.py — FND-03: ¿cuánto varía Vina entre semillas?

Corre en el contenedor `moldesign-lab` del servidor.

El hueco que cierra
-------------------
`FND-03` está declarado **P0** desde el inicio del programa —«el baseline es estable
entre ejecuciones… docking reporta varianza por seed»— y **no tiene artefacto**. Todas
las comparaciones de la cartera C usan `seed 42` y ninguna tiene control de ruido.

La auditoría adversarial (`MF-32`) lo identificó como el ataque más grave al que la
línea está expuesta: si re-correr con otra semilla mueve el oráculo ±0.5 Å, entonces
los efectos medidos —`MF-08` −0.82 Å, `MF-02F` −0.79 Å, `MF-25` −0.78 Å— caen dentro
del ruido de una sola corrida y hay que reescribir sus lecturas.

Diseño, elegido para que la comparación sea directa
---------------------------------------------------
Se replica **exactamente** el brazo `exhaustiveness=8` de `MF-25`: mismo receptor,
misma caja, mismo confórmero (el de menor RMSD alineado), mismo `num_modes`. Lo único
que cambia es la **semilla**: 42, 43, 44, 45, 46.

Así la desviación medida aquí es la barra de error que le faltaba a aquel experimento,
y la pregunta «¿0.78 Å es efecto o ruido?» se responde comparando dos números obtenidos
bajo condiciones idénticas.

Métricas
--------
Por complejo: desviación típica y rango del oráculo entre semillas, y —más importante
para un producto que promete confianza— si el **veredicto binario** (≤2 Å) cambia entre
semillas. Un veredicto que baila con la semilla no se puede vender como confianza.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median, pstdev
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

BOX = 25.0
EXH = 8
NUM_MODES = 9
SEMILLAS = (42, 43, 44, 45, 46)
UMBRAL_A = 2.0


def _vina() -> str:
    return os.environ.get("FND03_VINA", "/usr/local/bin/vina")


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def analizar(ws: Path, pid: str, estrato: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf
    from rdkit import Chem
    from rdkit.Chem import AllChem

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "por_semilla": {}}
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
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    ref_heavy = Chem.RemoveAllHs(Chem.Mol(crystal))
    if ref_heavy.GetNumAtoms() != len(pesados):
        out["error"] = "DESAJUSTE_PESADOS"
        return out

    # mismo conformero que MF-25: el de menor RMSD alineado
    mejor = (9e9, None)
    for f in sorted(w.glob("conf*.rigid.pdbqt")):
        if not re.match(r"conf\d+\.rigid\.pdbqt$", f.name):
            continue
        at = []
        for l in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
                try:
                    at.append([int(l[6:11]), float(l[30:38]), float(l[38:46]),
                               float(l[46:54])])
                except ValueError:
                    continue
        c = mf.coords_pose_a_por_mol(at, s2m)
        if not c or any(i not in c for i in pesados):
            continue
        probe = Chem.Mol(ref_heavy)
        cf = probe.GetConformer(0)
        for k, i in enumerate(pesados):
            x, y, z = c[i]
            cf.SetAtomPosition(k, (float(x), float(y), float(z)))
        try:
            r = float(AllChem.GetBestRMS(probe, ref_heavy, 0, 0))
        except Exception:
            continue
        if r < mejor[0]:
            mejor = (r, f)
    if mejor[1] is None:
        out["error"] = "SIN_CONFORMEROS"
        return out
    out["rmsd_conf"] = round(mejor[0], 3)

    for sem in SEMILLAS:
        salida = tmp / f"{pid}_s{sem}.pdbqt"
        cmd = [_vina(), "--receptor", str(rec), "--ligand", str(mejor[1])] + _caja(centro) + [
            "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
            "--seed", str(sem), "--cpu", "1", "--out", str(salida)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok = False
        if not ok:
            out["por_semilla"][str(sem)] = {"error": "VINA_FALLO"}
            continue
        best = None
        for sc, at in mf.parsear_out_vina(salida.read_text(encoding="utf-8", errors="replace")):
            c = mf.coords_pose_a_por_mol(at, s2m)
            if not c:
                continue
            v = mf.rmsd_pose_pocket(crystal, c)
            if v is not None and (best is None or v < best):
                best = v
        if best is None:
            out["por_semilla"][str(sem)] = {"error": "SIN_POSES"}
            continue
        out["por_semilla"][str(sem)] = {"oraculo": round(best, 3),
                                        "acierta": bool(best <= UMBRAL_A)}

    vals = [v["oraculo"] for v in out["por_semilla"].values() if "oraculo" in v]
    ac = [v["acierta"] for v in out["por_semilla"].values() if "acierta" in v]
    if len(vals) >= 2:
        out["n_semillas_ok"] = len(vals)
        out["oraculo_mediano"] = round(median(vals), 3)
        out["sd_semillas"] = round(pstdev(vals), 3)
        out["rango_semillas"] = round(max(vals) - min(vals), 3)
        out["veredicto_inestable"] = bool(len(set(ac)) > 1)
        out["aciertos"] = sum(ac)
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="FND-03: varianza por semilla de Vina")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "FND-03"
    out_dir.mkdir(parents=True, exist_ok=True)

    cand = [ws / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json",
            ws / "scripts" / "mf13_cohorte.json"]
    ruta = next((c for c in cand if c.exists()), None)
    if ruta is None:
        print("[FND-03] ERROR: falta cohorte.json")
        return 2
    coh = json.loads(ruta.read_text(encoding="utf-8"))
    jobs = [(p, "COLOCACION") for p in coh["cohorte_colocacion"]] + \
           [(p, "CONTROL") for p in coh["control_cubiertos"]]
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[FND-03] {len(jobs)} complejos x {len(SEMILLAS)} semillas {SEMILLAS} | exh={EXH}",
          flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, ws, pid, est, tmp): pid for pid, est in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                filas.append(fut.result())
                r = filas[-1]
                print(f"  [{i}/{len(jobs)}] {r['pid']} [{r['estrato']}] "
                      f"sd={r.get('sd_semillas')} rango={r.get('rango_semillas')} "
                      f"aciertos={r.get('aciertos')}/{r.get('n_semillas_ok')} "
                      f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8",
                          newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if r.get("sd_semillas") is not None]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        resumen[est] = {
            "n": len(g),
            "sd_mediana": round(median(r["sd_semillas"] for r in g), 3),
            "sd_p90": round(sorted(r["sd_semillas"] for r in g)[int(0.9 * (len(g) - 1))], 3),
            "rango_mediano": round(median(r["rango_semillas"] for r in g), 3),
            "rango_max": round(max(r["rango_semillas"] for r in g), 3),
            "complejos_con_veredicto_inestable": sum(1 for r in g if r["veredicto_inestable"]),
        }
    metrics = {
        "experiment_id": "FND-03",
        "tipo": "control de ruido (P0 declarado desde el inicio, sin artefacto hasta hoy)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"semillas": list(SEMILLAS), "exhaustiveness": EXH,
                   "num_modes": NUM_MODES, "box": BOX,
                   "conformero": "el de menor RMSD alineado (identico a MF-25)"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": resumen,
        "comparacion_declarada": {
            "MF-08_efecto": -0.82, "MF-02F_efecto": -0.79, "MF-25_efecto": -0.784,
            "nota": ("si la sd por semilla es del orden de estos efectos, las tres lecturas "
                     "quedan sin control de ruido y deben releerse")},
        "lectura": ("sd mediana >= 0.4 A => los efectos de ~0.8 A de la cartera C estan al "
                    "borde del ruido de una sola corrida. sd << 0.4 A => los efectos son "
                    "reales y las lecturas se sostienen. veredictos inestables > 0 => la "
                    "confianza por complejo NO se puede vender sin repeticiones"),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[FND-03] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
