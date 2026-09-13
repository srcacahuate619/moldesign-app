#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf19_rigido_cristal.py — MF-19: ¿falla la COLOCACIÓN o falla la búsqueda TORSIONAL?

**Hipótesis nueva.** Vina busca sobre 6 grados de libertad rígidos (posición y
orientación) **más** un grado por torsión rotable. Toda la línea ha atacado el problema
sin separar esas dos partes:

  * `MF-02F` dio más **reinicios** conformacionales → 3 de 33;
  * `MF-08` redujo el **volumen** de búsqueda → 3 de 33;
  * `MF-09` mostró que en 30 de 33 no existe ninguna pose ≤2 Å entre ~751;
  * `MF-15` mostró que **no hay embudo** que guíe (ρ=0.21).

La hipótesis: el fallo no está en colocar el ligando, sino en la **dimensionalidad
torsional**. Si se le entrega a Vina el **confórmero bioactivo exacto** y se le prohíbe
girar torsiones —docking **rígido** del cristal—, sólo le quedan 6 grados de libertad.

  * Si **encuentra** la pose nativa: la colocación en 6D es un problema resuelto y todo
    el fallo es búsqueda conformacional. La palanca sería seleccionar confórmeros, no
    afinar la caja ni el score.
  * Si **no la encuentra** ni con el confórmero correcto y sin torsiones: el fallo es
    de **colocación pura**, y eso indicta al buscador o al paisaje, no al confórmero.
    Sería el resultado más fuerte de la línea.

`MF-02A-EXT` hace la pregunta legítima: el confórmero bioactivo está disponible en el
83.9% de PDBBind a K30, así que entregarlo no es hacer trampa sobre algo inalcanzable.

Diseño
------
Por complejo, en **su propio receptor y su propia caja** (los mismos del docking v2):

  1. se prepara el ligando **cristalográfico** con Meeko;
  2. se produce un PDBQT **rígido** (sin torsiones activas);
  3. se dockea con Vina `exhaustiveness=8`, `num_modes=9`, semilla 42 — el mismo
     presupuesto del protocolo congelado;
  4. se mide el **mínimo RMSD** entre los modos emitidos y el cristal.

Prohibición: el confórmero de entrada es el cristalográfico, así que este experimento
**no puede leerse como una política de producción** — en producción no se conoce. Mide
un techo: qué pasaría si el generador de confórmeros fuera perfecto.
"""

from __future__ import annotations

import argparse
import json
import os
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


def _vina() -> str:
    return os.environ.get("MF19_VINA", "/usr/local/bin/vina")


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def _rigidizar(pdbqt: str) -> str:
    """Elimina BRANCH/ENDBRANCH/TORSDOF: todos los atomos quedan en la raiz rigida."""
    out = []
    for l in pdbqt.splitlines():
        if l.startswith(("BRANCH", "ENDBRANCH", "TORSDOF")):
            continue
        out.append(l)
    # una sola raiz: ROOT ... ENDROOT envolviendo todos los atomos
    atomos = [l for l in out if l.startswith(("ATOM", "HETATM"))]
    otros = [l for l in out if l.startswith("REMARK")]
    return "\n".join(otros + ["ROOT"] + atomos + ["ENDROOT", "TORSDOF 0"]) + "\n"


def analizar(ws: Path, pid: str, estrato: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf
    from meeko import MoleculePreparation
    from rdkit import Chem

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen = w / "rec.pdbqt", w / "center.json"
    if not rec.exists() or not cen.exists():
        out["error"] = "SIN_RECEPTOR_O_CAJA"
        return out
    centro = json.loads(cen.read_text(encoding="utf-8"))
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    try:
        mh = Chem.AddHs(crystal, addCoords=True)
        setups = MoleculePreparation().prepare(mh, conformer_id=0)
        rigid, flex, mapa, _e = mf.escribir_pdbqt(setups[0])
    except Exception as ex:
        out["error"] = f"MEEKO:{type(ex).__name__}"
        return out
    if not rigid or not flex or not mapa:
        out["error"] = "PREP_FALLO"
        return out

    s2m = {int(k): int(v) for k, v in (mapa if isinstance(mapa, list) else mapa.items())}
    pesados = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]
    # las torsiones activas viven en el PDBQT FLEXIBLE; el rigido ya trae TORSDOF 0
    n_tors = sum(1 for l in flex.splitlines() if l.startswith("BRANCH"))
    out["n_torsiones_originales"] = n_tors

    resultados = {}
    for etiq, texto in (("flexible", flex), ("rigido", rigid)):
        lig = tmp / f"{pid}_{etiq}.pdbqt"
        salida = tmp / f"{pid}_{etiq}_out.pdbqt"
        lig.write_text(texto, encoding="utf-8")
        cmd = [_vina(), "--receptor", str(rec), "--ligand", str(lig)] + _caja(centro) + [
            "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
            "--seed", str(SEED), "--cpu", "1", "--out", str(salida)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok = False
        if not ok:
            resultados[etiq] = {"error": "VINA_FALLO"}
            continue
        modelos = mf.parsear_out_vina(salida.read_text(encoding="utf-8", errors="replace"))
        rr, ss = [], []
        for sc, at in modelos:
            c = mf.coords_pose_a_por_mol(at, s2m)
            if not c:
                continue
            v = mf.rmsd_pose_pocket(crystal, c)
            if v is not None:
                rr.append(round(v, 3))
                ss.append(float(sc) if sc is not None else None)
        resultados[etiq] = {
            "n_modos": len(rr), "rmsds": rr, "scores": ss,
            "mejor_rmsd": round(min(rr), 3) if rr else None,
            "rmsd_top1": rr[0] if rr else None,
            "acierta": bool(rr and min(rr) <= UMBRAL_A),
            "top1_acierta": bool(rr and rr[0] <= UMBRAL_A),
        }
    out["resultados"] = resultados
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-19: docking rigido del conformero cristalografico")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-19"
    out_dir.mkdir(parents=True, exist_ok=True)

    cand = [ws / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json",
            ws / "scripts" / "mf13_cohorte.json"]
    ruta = next((c for c in cand if c.exists()), None)
    if ruta is None:
        print("[MF-19] ERROR: falta cohorte.json")
        return 2
    coh = json.loads(ruta.read_text(encoding="utf-8"))
    jobs = [(p, "COLOCACION") for p in coh["cohorte_colocacion"]] + \
           [(p, "CONTROL") for p in coh["control_cubiertos"]]
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[MF-19] {len(jobs)} complejos | exh={EXH} modos={NUM_MODES}", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Vina corre con --cpu 1, asi que un complejo a la vez usa 1 de los 4 nucleos.
        # Se paralelizan complejos DENTRO del mismo proceso: lanzar varios contenedores
        # sobre el mismo directorio de salida se pisaria los artefactos (leccion de
        # RS-03-PARAM-B). Los ficheros temporales llevan el pid, asi que no colisionan.
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futuros = {ex.submit(analizar, ws, pid, est, tmp): pid for pid, est in jobs}
            for i, fut in enumerate(as_completed(futuros), 1):
                filas.append(fut.result())
                r = filas[-1]
                rr = r.get("resultados", {})
                print(f"  [{i}/{len(jobs)}] {r['pid']} [{r['estrato']}] "
                      f"flex={rr.get('flexible',{}).get('mejor_rmsd')} "
                      f"rigido={rr.get('rigido',{}).get('mejor_rmsd')} "
                      f"tors={r.get('n_torsiones_originales')} {r.get('error','')} "
                      f"({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8",
                          newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "resultados" in r and
          r["resultados"].get("rigido", {}).get("mejor_rmsd") is not None]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        d: Dict[str, Any] = {"n": len(g),
                             "torsiones_mediana": int(median(r["n_torsiones_originales"] for r in g))}
        for etiq in ("flexible", "rigido"):
            h = [r for r in g if r["resultados"].get(etiq, {}).get("mejor_rmsd") is not None]
            if not h:
                continue
            d[etiq] = {
                "n": len(h),
                "acierta": sum(1 for r in h if r["resultados"][etiq]["acierta"]),
                "top1_acierta": sum(1 for r in h if r["resultados"][etiq]["top1_acierta"]),
                "mejor_rmsd_mediano": round(median(r["resultados"][etiq]["mejor_rmsd"] for r in h), 3),
            }
        resumen[est] = d
    metrics = {
        "experiment_id": "MF-19",
        "tipo": "medicion con hipotesis nueva",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"exhaustiveness": EXH, "num_modes": NUM_MODES, "seed": SEED, "box": BOX},
        "brazos": {"flexible": "conformero cristalografico con sus torsiones activas",
                   "rigido": "mismo conformero con TODAS las torsiones congeladas (6 GDL)"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": resumen,
        "prohibicion": ("el conformero de entrada es el cristalografico: NO es una politica de "
                        "produccion, mide un techo -que pasaria si el generador de conformeros "
                        "fuera perfecto"),
        "lectura": ("rigido acierta en la mayoria => la colocacion en 6 GDL esta resuelta y el "
                    "fallo es busqueda conformacional. rigido falla => el fallo es de COLOCACION "
                    "pura, y eso indicta al buscador o al paisaje, no al conformero"),
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-19] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
