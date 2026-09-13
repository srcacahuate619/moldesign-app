#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf13_score_nativo.py — MF-13: ¿la función de Vina prefiere la pose nativa?

Prerrequisito formal: `scripts/artifacts_science/MF-13-PRE/PREREGISTRO.md` escrito.
Corre en el contenedor `moldesign-lab` del servidor (Vina 1.2.7, Meeko 0.7.1).

La pregunta que queda abierta
-----------------------------
`MF-09` estableció que en **30 de 33** complejos difíciles no existe pose ≤2 Å entre
~751 candidatas, y concluyó «es muestreo, no puntuación». Pero midió el muestreo
sobre lo que el buscador **produjo**; nunca preguntó si la función de puntuación
**reconocería** la pose nativa si se la entregaran.

Son dos fallos distintos y las consecuencias son opuestas:

  (A) **fallo de búsqueda** — la función prefiere la pose nativa pero el optimizador
      no la encuentra. La palanca es el muestreo: mejor optimizador, más reinicios,
      mejor inicialización.

  (B) **fallo de puntuación** — el mínimo global de la función de Vina **no está** en
      la pose nativa. Entonces ninguna palanca de muestreo puede funcionar, porque
      buscar mejor sólo lleva más rápido al sitio equivocado. Explicaría de una sola
      vez `MF-08` (caja), `MF-02F` (reinicios), `MF-09` (cobertura) y `MF-10` (FF).

Nadie ha medido cuál de las dos es. Este experimento lo hace con material ya en
disco y una llamada a Vina por complejo.

Diseño
------
Para cada complejo de **train** (116), en su propio receptor y su propia caja —los
mismos `rec.pdbqt` y `center.json` que usó el docking—:

  1. Se prepara la **pose cristalográfica** como PDBQT con el mismo tipado de Meeko.
  2. `vina --score_only` sobre ella  → `score_cristal`.
  3. `vina --local_only` desde ella  → `score_cristal_local` y **cuánto se aleja**:
     si el optimizador local empuja el cristal lejos, el cristal ni siquiera es un
     mínimo local de la función.
  4. Se compara con el **mejor score entre todas las poses dockeadas** del conjunto
     v2 (`score_top1_dock`), y se calcula el **percentil** del score del cristal
     dentro de la distribución de scores dockeados del complejo.

Nota sobre la comparación
-------------------------
Es deliberadamente **conservadora con la hipótesis (B)**: el cristal se puntúa tal
cual, sin relajar, mientras las poses dockeadas ya salen optimizadas por Vina. Si aun
así el cristal puntúa mejor, la conclusión de «fallo de búsqueda» es sólida. Por eso
se reporta también `score_cristal_local`, que es la comparación justa.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

BOX = 25.0
SEED = 42
UMBRAL_A = 2.0


def _vina_bin() -> str:
    return os.environ.get("MF13_VINA", "/usr/local/bin/vina")


def _correr_vina(args: List[str], timeout: int) -> Optional[str]:
    try:
        p = subprocess.run([_vina_bin()] + args, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return p.stdout if p.returncode == 0 else None


def _score_de_salida(texto: str) -> Optional[float]:
    """Lee el score de `--score_only` ('Estimated Free Energy of Binding : -9.1')."""
    for l in texto.splitlines():
        if "Estimated Free Energy of Binding" in l:
            try:
                return float(l.split(":")[1].split()[0])
            except (IndexError, ValueError):
                return None
    return None


def _args_caja(centro) -> List[str]:
    return ["--center_x", str(centro[0]), "--center_y", str(centro[1]),
            "--center_z", str(centro[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def preparar_cristal(ws: Path, pid: str, destino: Path) -> Optional[dict]:
    """PDBQT de la pose cristalográfica con el tipado de Meeko de molflex."""
    import molflex as mf
    from meeko import MoleculePreparation
    from rdkit import Chem

    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        return None
    mh = Chem.AddHs(crystal, addCoords=True)
    setups = MoleculePreparation().prepare(mh, conformer_id=0)
    rigid, _flex, mapa, _err = mf.escribir_pdbqt(setups[0])
    if not rigid or not mapa:
        return None
    destino.write_text(rigid, encoding="utf-8")
    return {"mapa": mapa, "crystal": crystal}


def analizar(ws: Path, pid: str, estrato: str, dock: Dict[str, Any],
             tmp: Path) -> Dict[str, Any]:
    import molflex as mf
    out: Dict[str, Any] = {"pid": pid, "estrato": estrato}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen = w / "rec.pdbqt", w / "center.json"
    if not rec.exists() or not cen.exists():
        out["error"] = "SIN_RECEPTOR_O_CAJA"
        return out
    centro = json.loads(cen.read_text(encoding="utf-8"))
    lig = tmp / f"{pid}_cristal.pdbqt"
    try:
        prep = preparar_cristal(ws, pid, lig)
    except Exception as ex:
        out["error"] = f"MEEKO:{type(ex).__name__}:{str(ex)[-120:]}"
        return out
    if prep is None:
        out["error"] = "PREP_CRISTAL_FALLO"
        return out

    base = ["--receptor", str(rec), "--ligand", str(lig)] + _args_caja(centro) + \
           ["--seed", str(SEED), "--cpu", "1"]

    s = _correr_vina(base + ["--score_only"], timeout=120)
    out["score_cristal"] = _score_de_salida(s) if s else None

    salida = tmp / f"{pid}_local.pdbqt"
    s2 = _correr_vina(base + ["--local_only", "--out", str(salida)], timeout=300)
    if s2 and salida.exists():
        modelos = mf.parsear_out_vina(salida.read_text(encoding="utf-8", errors="replace"))
        if modelos:
            sc, at = modelos[0]
            # `--local_only` NO escribe REMARK VINA RESULT (ver molflex.parsear_out_vina):
            # el score de la pose relajada se obtiene re-puntuandola, como hace molflex.
            if sc is None:
                s3 = _correr_vina(["--receptor", str(rec), "--ligand", str(salida)]
                                  + _args_caja(centro)
                                  + ["--seed", str(SEED), "--cpu", "1", "--score_only"],
                                  timeout=120)
                sc = _score_de_salida(s3) if s3 else None
            out["score_cristal_local"] = float(sc) if sc is not None else None
            try:
                s2m = {int(k): int(v) for k, v in prep["mapa"]} \
                    if isinstance(prep["mapa"], list) else \
                    {int(k): int(v) for k, v in prep["mapa"].items()}
                coords = mf.coords_pose_a_por_mol(at, s2m)
                out["rmsd_deriva_local"] = (
                    round(mf.rmsd_pose_pocket(prep["crystal"], coords), 3)
                    if coords else None)
            except Exception:
                out["rmsd_deriva_local"] = None

    out.update({
        "score_top1_dock": dock.get("mejor_score"),
        "rmsd_top1_dock": dock.get("rmsd_top1"),
        "oraculo": dock.get("oraculo"),
        "cubierto": bool(dock.get("oraculo") is not None
                         and dock["oraculo"] <= UMBRAL_A),
        "n_poses_dock": dock.get("n"),
    })
    sc_c, sc_d = out.get("score_cristal"), out.get("score_top1_dock")
    if sc_c is not None and sc_d is not None:
        out["ventaja_cristal"] = round(sc_d - sc_c, 3)      # >0 => el cristal puntua MEJOR
        out["cristal_gana"] = bool(sc_c < sc_d)
        peores = dock.get("scores", [])
        if peores:
            out["percentil_cristal"] = round(
                100.0 * sum(1 for x in peores if x < sc_c) / len(peores), 1)
    scl = out.get("score_cristal_local")
    if scl is not None and sc_d is not None:
        out["ventaja_cristal_local"] = round(sc_d - scl, 3)
        out["cristal_local_gana"] = bool(scl < sc_d)
    out["t_s"] = round(time.time() - t0, 1)
    return out


def cargar_dock(ws: Path) -> Dict[str, Dict[str, Any]]:
    """Mejor score, rmsd del top-1 y oráculo por complejo, desde el conjunto v2."""
    por = defaultdict(list)
    for l in (ws / "data" / "pose_selector_dataset" / "v2" /
              "poses_train.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            d = json.loads(l)
            por[d["pid"]].append((d["vina_score"], d["rmsd"]))
    salida = {}
    for pid, v in por.items():
        top = min(v, key=lambda x: x[0])
        salida[pid] = {"mejor_score": round(top[0], 3), "rmsd_top1": round(top[1], 3),
                       "oraculo": round(min(x[1] for x in v), 3), "n": len(v),
                       "scores": [x[0] for x in v]}
    return salida


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-13: la funcion de Vina frente a la pose nativa")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()

    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-13"
    out_dir.mkdir(parents=True, exist_ok=True)

    # la cohorte vive en el arbol de artefactos en local; en el contenedor se sube a
    # scripts/ porque artifacts_science pertenece a root y no es escribible por sftp
    cand = [ws / "scripts" / "artifacts_science" / "MF-02F" / "cohorte.json",
            ws / "scripts" / "mf13_cohorte.json"]
    ruta_coh = next((c for c in cand if c.exists()), None)
    if ruta_coh is None:
        print("[MF-13] ERROR: no encuentro cohorte.json en %s" % [str(c) for c in cand])
        return 2
    coh = json.loads(ruta_coh.read_text(encoding="utf-8"))
    estrato = {p: "COLOCACION" for p in coh["cohorte_colocacion"]}
    estrato.update({p: "CONTROL" for p in coh["control_cubiertos"]})

    dock = cargar_dock(ws)
    pids = sorted(dock)
    if args.limite:
        pids = pids[:args.limite]
    print(f"[MF-13] {len(pids)} complejos de train | vina={_vina_bin()}", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for i, pid in enumerate(pids, 1):
            filas.append(analizar(ws, pid, estrato.get(pid, "RESTO"), dock[pid], tmp))
            r = filas[-1]
            print(f"  [{i}/{len(pids)}] {pid} [{r['estrato']}] "
                  f"cristal={r.get('score_cristal')} local={r.get('score_cristal_local')} "
                  f"dock={r.get('score_top1_dock')} gana={r.get('cristal_gana')} "
                  f"({round(time.time()-t0)}s)", flush=True)
            with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for x in filas:
                    fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if r.get("score_cristal") is not None]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL", "RESTO"):
        g = [r for r in ok if r["estrato"] == est and "cristal_gana" in r]
        if not g:
            continue
        gl = [r for r in g if "cristal_local_gana" in r]
        der = [r["rmsd_deriva_local"] for r in g if r.get("rmsd_deriva_local") is not None]
        resumen[est] = {
            "n": len(g),
            "cristal_gana": sum(r["cristal_gana"] for r in g),
            "frac_cristal_gana": round(sum(r["cristal_gana"] for r in g) / len(g), 4),
            "cristal_local_gana": sum(r["cristal_local_gana"] for r in gl) if gl else None,
            "frac_cristal_local_gana": (round(sum(r["cristal_local_gana"] for r in gl) / len(gl), 4)
                                        if gl else None),
            "ventaja_mediana": round(median([r["ventaja_cristal"] for r in g]), 3),
            "ventaja_local_mediana": (round(median([r["ventaja_cristal_local"] for r in gl]), 3)
                                      if gl else None),
            "percentil_cristal_mediano": round(median(
                [r["percentil_cristal"] for r in g if "percentil_cristal" in r]), 1),
            "deriva_local_mediana_A": round(median(der), 3) if der else None,
        }

    col = resumen.get("COLOCACION", {})
    frac = col.get("frac_cristal_local_gana")
    if frac is None:
        frac = col.get("frac_cristal_gana")
    metrics = {
        "experiment_id": "MF-13",
        "tipo": "medicion con regla de lectura preregistrada",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"box": BOX, "seed": SEED, "receptor_y_caja": "los mismos del docking v2"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "resumen": resumen,
        "gates": {
            "G1_validez": {"criterio": ">=95% de complejos con score finito del cristal",
                           "tasa": round(len(ok) / max(1, len(filas)), 4),
                           "pass": len(ok) >= 0.95 * len(filas)},
            "G2_diagnostico": {
                "criterio": ("fraccion de COLOCACION donde el cristal relajado localmente "
                             "puntua mejor que el mejor pose dockeado"),
                "fraccion": frac,
                "lectura": (">=0.70 => FALLO DE BUSQUEDA: la funcion prefiere la nativa y el "
                            "optimizador no la encuentra; la palanca es el muestreo. "
                            "<=0.30 => FALLO DE PUNTUACION: el minimo de Vina no esta en la "
                            "nativa y ninguna palanca de muestreo puede funcionar. "
                            "0.30-0.70 => mixto, se reporta la distribucion."),
            },
        },
    }
    if frac is not None:
        metrics["diagnostico"] = ("BUSQUEDA" if frac >= 0.70 else
                                  "PUNTUACION" if frac <= 0.30 else "MIXTO")
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    print("\n[MF-13] " + json.dumps(resumen, ensure_ascii=False, indent=1))
    print(f"[MF-13] diagnostico: {metrics.get('diagnostico')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
