#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf25_presupuesto_busqueda.py — MF-25: ¿el coste de colocación es falta de presupuesto?

Corre en el contenedor `moldesign-lab` del servidor.

La pregunta
-----------
`MF-22` midió que el **coste de colocación** —lo que la búsqueda añade sobre el error
conformacional de partida— es **0.741 Å** en el estrato control y **3.847 Å** en el
dominado por colocación. Cinco veces más, con el mismo motor, la misma caja y
confórmeros de calidad comparable.

Hay dos explicaciones y son incompatibles:

  * **(A) presupuesto**: la búsqueda no tiene suficiente muestreo para el espacio que
    debe cubrir. Se arregla subiendo `exhaustiveness`.
  * **(B) paisaje**: la búsqueda converge a un óptimo equivocado. Más presupuesto la
    lleva más rápido al sitio equivocado y no baja el coste. Es lo que predice `MF-15`
    (sin embudo, ρ=0.21) y `MF-13-DIAG` (competidores a ~2 Å con el mismo enterramiento).

El sesgo de circularidad, y cómo se evita
-----------------------------------------
El estrato COLOCACION se **definió** como los complejos que fallan la colocación, así
que comparar su coste de colocación contra el control es parcialmente tautológico: la
diferencia de nivel está garantizada por construcción.

Por eso este experimento **no compara niveles, compara la respuesta al presupuesto** —
la derivada. Que el coste sea mayor en COLOCACION está dado; que **baje o no al subir
el presupuesto** no lo está, y es lo que decide entre (A) y (B).

Diseño
------
Por complejo, sobre su **mejor confórmero ETKDG** (el de menor RMSD alineado al
cristal), dockeado rígido en su propio receptor y caja:

  * `exhaustiveness` ∈ {8, 32, 128} — el protocolo congelado es 8, así que el barrido
    llega a **16×** el presupuesto de producción;
  * `num_modes=9`, semilla 42, todo lo demás idéntico.

Métrica: **coste de colocación** = mejor RMSD en marco de pocket − RMSD alineado del
confórmero de partida. Es la cantidad que `MF-22` definió.

Elección del confórmero, declarada
----------------------------------
Se elige **por RMSD**, no por score. Es deliberado y es lo contrario de lo que exigen
los experimentos de rendimiento: aquí se quiere **aislar la colocación**, entregándole
a la búsqueda el mejor material conformacional disponible. Por eso este experimento
**no mide rendimiento** y no puede leerse como tal.

Prohibición heredada de `MF-13-PRE`
-----------------------------------
`MF-13-PRE` prohíbe leer un diagnóstico de búsqueda como permiso para reabrir
`MF-03/04/05/07/12`, que ajustan parámetros del mismo buscador. `exhaustiveness` **es**
un parámetro del mismo buscador, así que se declara explícitamente: esto es un
**diagnóstico**, y un resultado positivo **no autoriza** subir `exhaustiveness` en
producción. Eso exigiría su propio experimento con coste de CPU medido, porque
`exhaustiveness=128` cuesta ~16× por corrida.
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
from statistics import median
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

BOX = 25.0
SEED = 42
NUM_MODES = 9
EXHAUSTIVIDADES = (8, 32, 128)
UMBRAL_A = 2.0


def _vina() -> str:
    return os.environ.get("MF25_VINA", "/usr/local/bin/vina")


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def analizar(ws: Path, pid: str, estrato: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf
    from rdkit import Chem
    from rdkit.Chem import AllChem

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "barrido": []}
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

    # mejor conformero ETKDG de ENTRADA (regex estricta: excluye *.relax.rigid.*,
    # que son poses ya dockeadas -leccion del corrigendum de MF-21)
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
    out["conformero"] = mejor[1].name

    for exh in EXHAUSTIVIDADES:
        salida = tmp / f"{pid}_e{exh}.pdbqt"
        cmd = [_vina(), "--receptor", str(rec), "--ligand", str(mejor[1])] + _caja(centro) + [
            "--exhaustiveness", str(exh), "--num_modes", str(NUM_MODES),
            "--seed", str(SEED), "--cpu", "1", "--out", str(salida)]
        t1 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=5400)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok = False
        if not ok:
            out["barrido"].append({"exh": exh, "error": "VINA_FALLO"})
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
            out["barrido"].append({"exh": exh, "error": "SIN_POSES"})
            continue
        out["barrido"].append({
            "exh": exh, "rmsd_pose": round(best, 3),
            "colocacion": round(best - mejor[0], 3),
            "acierta": bool(best <= UMBRAL_A),
            "t_s": round(time.time() - t1, 1)})
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-25: respuesta del coste de colocacion al presupuesto")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-25"
    out_dir.mkdir(parents=True, exist_ok=True)

    cand = [ws / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json",
            ws / "scripts" / "mf13_cohorte.json"]
    ruta = next((c for c in cand if c.exists()), None)
    if ruta is None:
        print("[MF-25] ERROR: falta cohorte.json")
        return 2
    coh = json.loads(ruta.read_text(encoding="utf-8"))
    jobs = [(p, "COLOCACION") for p in coh["cohorte_colocacion"]] + \
           [(p, "CONTROL") for p in coh["control_cubiertos"]]
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[MF-25] {len(jobs)} complejos x {len(EXHAUSTIVIDADES)} presupuestos "
          f"{EXHAUSTIVIDADES}", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, ws, pid, est, tmp): pid for pid, est in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                filas.append(fut.result())
                r = filas[-1]
                b = {x["exh"]: x.get("colocacion") for x in r.get("barrido", [])}
                print(f"  [{i}/{len(jobs)}] {r['pid']} [{r['estrato']}] "
                      f"conf={r.get('rmsd_conf')} coloc={b} {r.get('error','')} "
                      f"({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8",
                          newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if r.get("barrido") and
          all("colocacion" in x for x in r["barrido"])]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        d: Dict[str, Any] = {"n": len(g),
                             "rmsd_conf_mediano": round(median(r["rmsd_conf"] for r in g), 3)}
        for exh in EXHAUSTIVIDADES:
            v = [x["colocacion"] for r in g for x in r["barrido"] if x["exh"] == exh]
            a = [x["acierta"] for r in g for x in r["barrido"] if x["exh"] == exh]
            tt = [x["t_s"] for r in g for x in r["barrido"] if x["exh"] == exh]
            d[f"exh_{exh}"] = {"coloc_mediano": round(median(v), 3) if v else None,
                               "aciertan": sum(a), "de": len(a),
                               "t_mediano_s": round(median(tt), 1) if tt else None}
        base = d[f"exh_{EXHAUSTIVIDADES[0]}"]["coloc_mediano"]
        alto = d[f"exh_{EXHAUSTIVIDADES[-1]}"]["coloc_mediano"]
        d["mejora_por_presupuesto"] = (round(base - alto, 3)
                                       if (base is not None and alto is not None) else None)
        resumen[est] = d
    metrics = {
        "experiment_id": "MF-25",
        "tipo": "intervencion (barrido de presupuesto de busqueda)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"exhaustividades": list(EXHAUSTIVIDADES), "num_modes": NUM_MODES,
                   "seed": SEED, "box": BOX,
                   "conformero": "el de menor RMSD alineado (elegido POR RMSD, declarado)"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": resumen,
        "circularidad": ("el estrato COLOCACION se definio por fallo de colocacion, asi que "
                         "el NIVEL del coste es tautologico; este experimento compara la "
                         "RESPUESTA al presupuesto, que no lo es"),
        "lectura": ("el coste baja materialmente (>0.5 A) al subir 16x el presupuesto => "
                    "PRESUPUESTO: la busqueda no muestrea bastante. No baja => PAISAJE: "
                    "converge a un optimo equivocado y mas presupuesto no ayuda, "
                    "consistente con MF-15 (sin embudo) y MF-13-DIAG (competidores a ~2 A)"),
        "prohibicion": ("un resultado positivo NO autoriza subir exhaustiveness en produccion: "
                        "exh=128 cuesta ~16x por corrida y eso exige su propio experimento "
                        "con CPU medida"),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-25] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
