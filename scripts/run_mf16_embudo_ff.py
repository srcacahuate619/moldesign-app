#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf16_embudo_ff.py — MF-16: ¿tiene embudo un potencial físico donde Vina no lo tiene?

Corre en el contenedor `moldesign-lab` del servidor.

La pregunta
-----------
`MF-15` midió que en el estrato difícil la función de Vina **no tiene embudo**:
Spearman(rmsd, score) ≈ 0.21, frente a ≈ 0.50 en los controles. `MF-14` midió que la
cuenca del mínimo nativo existe (r50 ≈ 2 Å) pero es rugosa. La conclusión provisional
es que el problema está en el **paisaje de puntuación**, no en el muestreo.

Eso deja una pregunta con consecuencias prácticas inmediatas: **¿es un problema de
Vina, o del problema?** Si un potencial físico bien parametrizado —amber14 + Sage
2.2.1 + cargas NAGL, el mismo de `MF-10`— tiene gradiente donde Vina no lo tiene, hay
una dirección concreta. Si tampoco lo tiene, el fallo es más profundo que la elección
de función de puntuación.

Diseño: comparación **pareada sobre las mismas poses**
-----------------------------------------------------
Se usan las 878 poses de `mf10_poses.json` —las mismas de `MF-10`, elegidas por score
y nunca por RMSD—, y para cada complejo se calculan **dos** correlaciones sobre el
**mismo conjunto de poses**:

  * `rho_vina`  = Spearman(rmsd, vina_score)
  * `rho_ff`    = Spearman(rmsd, energia_amber_sage)

Al ser exactamente las mismas poses, la diferencia `rho_ff - rho_vina` es pareada por
complejo y no mezcla efectos de muestreo.

Eficiencia: el sistema OpenMM se construye **una vez por complejo** y luego sólo se
mueven las coordenadas del ligando (`setPositions`). La proteína queda fija, así que
las diferencias de energía entre poses reflejan energía interna del ligando más
interacción — que es exactamente lo que un embudo necesita comparar dentro de un
complejo. Construir el sistema por pose costaría 20 s cada una; así cuesta ~0.1 s.

Advertencia declarada
---------------------
La energía en vacío con proteína fija es un puntuador **crudo**: sin solvatación y sin
entropía. No se propone como función de producción. Lo que se mide es si **ordena**
mejor que Vina, no si predice afinidad.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Sequence

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from run_mf10_relax_insitu import construir_sistema  # noqa: E402

MIN_POSES = 8
OUT_NAME = "MF-16"


def _spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    n = len(a)
    if n < MIN_POSES:
        return None

    def rangos(v):
        orden = sorted(range(n), key=lambda i: v[i])
        r = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and v[orden[j + 1]] == v[orden[i]]:
                j += 1
            prom = (i + j) / 2 + 1
            for k in range(i, j + 1):
                r[orden[k]] = prom
            i = j + 1
        return r
    ra, rb = rangos(a), rangos(b)
    ma, mb = sum(ra) / n, sum(rb) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    da = sum((x - ma) ** 2 for x in ra) ** 0.5
    db = sum((y - mb) ** 2 for y in rb) ** 0.5
    return round(num / (da * db), 4) if da and db else None


def analizar(ws: Path, pid: str, datos: Dict[str, Any]) -> Dict[str, Any]:
    from openmm import unit
    from rdkit import Chem
    import numpy as np

    out: Dict[str, Any] = {"pid": pid, "estrato": datos["estrato"]}
    t0 = time.time()
    sdf = ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
    crystal = Chem.MolFromMolFile(str(sdf))
    if crystal is None:
        crystal = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]

    poses = datos["poses"]
    try:
        coords0 = [poses[0]["coords"][str(i)] for i in pesados]
    except KeyError:
        out["error"] = "MAPEO_INCOMPLETO"
        return out
    # el sistema se construye UNA vez; despues solo se mueven coordenadas
    try:
        sim, idx_lig, _ = construir_sistema(ws, pid, crystal, coords0)
    except Exception as ex:
        out["error"] = f"{type(ex).__name__}: {str(ex)[-160:]}"
        return out

    st0 = sim.context.getState(getPositions=True)
    pos = st0.getPositions(asNumpy=True).value_in_unit(unit.angstroms)

    rmsds, vinas, energias = [], [], []
    n_err = 0
    for p in poses:
        try:
            c = [p["coords"][str(i)] for i in pesados]
        except KeyError:
            n_err += 1
            continue
        nuevo = np.array(pos, copy=True)
        for k, j in enumerate(idx_lig):
            nuevo[j] = c[k]
        try:
            sim.context.setPositions(nuevo * unit.angstroms)
            e = sim.context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(
                unit.kilocalories_per_mole)
            if not np.isfinite(e):
                n_err += 1
                continue
        except Exception:
            n_err += 1
            continue
        rmsds.append(p["rmsd"])
        vinas.append(p["score"])
        energias.append(float(e))

    out["n_poses"] = len(rmsds)
    out["n_errores"] = n_err
    if len(rmsds) < MIN_POSES:
        out["error"] = "POCAS_POSES"
        out["t_s"] = round(time.time() - t0, 1)
        return out
    rv = _spearman(rmsds, vinas)
    rf = _spearman(rmsds, energias)
    out.update({
        "rho_vina": rv, "rho_ff": rf,
        "delta_rho": round(rf - rv, 4) if (rv is not None and rf is not None) else None,
        "energia_min": round(min(energias), 1), "energia_max": round(max(energias), 1),
        "rmsd_min": round(min(rmsds), 3), "rmsd_max": round(max(rmsds), 3),
        "t_s": round(time.time() - t0, 1),
    })
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-16: embudo de un potencial fisico vs Vina")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / OUT_NAME
    out_dir.mkdir(parents=True, exist_ok=True)

    poses = json.loads((ws / "scripts" / "mf10_poses.json").read_text(encoding="utf-8"))
    pids = list(poses)[:args.limite] if args.limite else list(poses)
    print(f"[MF-16] {len(pids)} complejos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    for i, pid in enumerate(pids, 1):
        filas.append(analizar(ws, pid, poses[pid]))
        r = filas[-1]
        print(f"  [{i}/{len(pids)}] {pid} [{r['estrato']}] rho_vina={r.get('rho_vina')} "
              f"rho_ff={r.get('rho_ff')} n={r.get('n_poses')} "
              f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
        with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
            for x in filas:
                fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if r.get("delta_rho") is not None]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        resumen[est] = {
            "n": len(g),
            "rho_vina_mediano": round(median(r["rho_vina"] for r in g), 4),
            "rho_ff_mediano": round(median(r["rho_ff"] for r in g), 4),
            "delta_rho_mediano": round(median(r["delta_rho"] for r in g), 4),
            "complejos_ff_mejor": sum(1 for r in g if r["delta_rho"] > 0),
            "complejos_vina_mejor": sum(1 for r in g if r["delta_rho"] < 0),
        }
    metrics = {
        "experiment_id": OUT_NAME,
        "tipo": "medicion pareada sobre las mismas poses",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "n_complejos": len(filas), "n_ok": len(ok),
        "advertencia": ("energia en vacio con proteina fija: puntuador crudo, sin solvatacion "
                        "ni entropia. Se mide si ORDENA mejor que Vina, no si predice afinidad."),
        "resumen": resumen,
        "gates": {
            "G1_validez": {"criterio": ">=70% de complejos con ambas correlaciones",
                           "tasa": round(len(ok) / max(1, len(filas)), 4),
                           "pass": len(ok) >= 0.70 * len(filas)},
            "G2_embudo": {"criterio": "delta_rho mediano en COLOCACION > 0: el FF ordena mejor",
                          "delta_rho_mediano": resumen.get("COLOCACION", {}).get("delta_rho_mediano"),
                          "lectura": ("delta>0 y ff mejor en la mayoria => hay direccion concreta: "
                                      "un potencial fisico si orienta donde Vina no. delta<=0 => "
                                      "el fallo no es de la eleccion de funcion")},
        },
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-16] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
