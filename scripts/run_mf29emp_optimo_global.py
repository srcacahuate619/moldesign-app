#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf29emp_optimo_global.py — MF-29-EMP: ¿alcanza Vina su propio óptimo global?

Corre en el contenedor `moldesign-lab` del servidor.

La pregunta
-----------
`MF-15-EXT` midió que no hay embudo (rho 0.186) y `MF-25` que 16x de presupuesto no
convierte nada. Las dos son compatibles con dos historias incompatibles entre sí:

  * **BUSQUEDA**: el mínimo global de la función está en la pose nativa y la búsqueda
    no llega. Entonces hay que cambiar el buscador.
  * **OBJETIVO**: la búsqueda sí llega al mínimo global, y el mínimo global no es la
    pose nativa. Entonces ningún buscador arregla nada y hay que cambiar la función.

Separarlas exige conocer el **mínimo global de la función**, que es justo lo que nadie
ha medido. `MF-13` sólo pudo puntuar el cristal: eso da un **testigo** de que existe un
valor bajo, no el óptimo.

Método sustituido, y por qué
----------------------------
La seccion 20.11(b) del doc. 49 propone la **jerarquía de Lasserre** para obtener el
mínimo global **certificado**. Se declara NO IMPLEMENTABLE en este hardware:

  * los términos de Vina (gauss1, gauss2, repulsion, hydrophobic, hbond) **no son
    polinómicos** —son gaussianas y tramos lineales—, así que exigirían un sustituto
    polinómico cuyo error habría que acotar; el certificado sería del sustituto, no de
    Vina;
  * con SE(3) x T^6 las variables son 3 (traslación) + 4 (cuaternión) + 12 (cos,sen de
    6 torsiones) = **19**. La matriz de momentos de orden 2 es C(21,2)=210, la de orden
    3 es C(22,3)=1540 y la de orden 4 es C(23,4)=8855. El orden 2 casi con seguridad no
    es ajustado para este problema, y a partir del orden 3 el numero de momentos
    -C(25,6)=177,100- deja el SDP fuera del alcance de 12 nucleos.

Se sustituye por una **cota superior empírica** del mínimo global: presupuesto masivo.
Es más débil —no certifica— y el nombre lo dice: `MF-29-EMP`, no `MF-29`. `MF-29` queda
ABIERTO.

Diseño
------
Cohorte: los complejos con **TORSDOF <= 6 en el propio PDBQT**, que es la dimensión que
Vina realmente busca (y no el conteo de RDKit: difieren en 2 complejos, `1mmr` y
`1nm6`, que entran por este criterio y no por el otro). El corte en 6 no es cosmético:
es el régimen donde un presupuesto masivo puede plausiblemente **saturar**, de modo que
la cota empírica signifique algo.

Por complejo, ligando **flexible** `conf0.flex.pdbqt` —fijo y el mismo en los dos
brazos, de modo que la única diferencia sea el presupuesto—, su propio receptor y caja:

  * brazo PRODUCCION: `exhaustiveness=8`, semillas {42, 1, 2, 3, 4};
  * brazo MASIVO:     `exhaustiveness=512`, semillas {42, 7, 13}  (**64x**).

Se registra el **mejor score** de cada corrida (no el RMSD: la pregunta es sobre la
función, no sobre el cristal) y, como contexto, el mejor `rmsd_pose_pocket`.

Tercer testigo, reusado sin recomputo
-------------------------------------
`MF-13` ya puntuó el cristal relajado localmente en los 116 complejos. Ese valor es una
**cota superior independiente** del mínimo global: si el cristal puntúa mejor que lo que
encuentra el brazo masivo, la búsqueda falló y no hace falta ningún certificado para
afirmarlo.

Límites declarados ANTES de correr
----------------------------------
1. **Esto no es el certificado de `MF-29`.** Que el brazo masivo no mejore NO prueba que
   Vina alcance el óptimo global: prueba que 64x de presupuesto no encontró nada mejor.
2. El estrato COLOCACION aporta **n=7** en esta cohorte. Por la regla derivada del
   entregable 8, con n pequeño se reporta la **comparación pareada**, nunca la mediana
   por estrato.
3. El resultado **no extrapola** a 16 torsiones: la cohorte se eligió justamente por ser
   el régimen de baja dimensión.
4. Los tiempos se miden con 4 workers en una caja de 4 núcleos. Son orientativos; la
   cantidad primaria es el score, que no depende de la carga.
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
NUM_MODES = 9
BRAZOS = {"produccion": (8, (42, 1, 2, 3, 4)), "masivo": (512, (42, 7, 13))}
DELTA_RUIDO = 0.10   # kcal/mol, declarado ANTES como ruido numerico
UMBRAL_A = 2.0
LIGANDO = "conf0.flex.pdbqt"


def _vina() -> str:
    return os.environ.get("MF29_VINA", "/usr/local/bin/vina")


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def analizar(ws: Path, pid: str, estrato: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "brazos": {}}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen, lig = w / "rec.pdbqt", w / "center.json", w / LIGANDO
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

    torsdof = None
    for l in lig.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.startswith("TORSDOF"):
            torsdof = int(l.split()[1])
    out["torsdof"] = torsdof

    for nombre, (exh, semillas) in BRAZOS.items():
        corridas = []
        for sd in semillas:
            salida = tmp / f"{pid}_{nombre}_s{sd}.pdbqt"
            cmd = [_vina(), "--receptor", str(rec), "--ligand", str(lig)] + _caja(centro) + [
                "--exhaustiveness", str(exh), "--num_modes", str(NUM_MODES),
                "--seed", str(sd), "--cpu", "1", "--out", str(salida)]
            t1 = time.time()
            try:
                p = subprocess.run(cmd, capture_output=True, text=True, timeout=14400)
                ok = p.returncode == 0 and salida.exists()
            except subprocess.TimeoutExpired:
                ok = False
            if not ok:
                corridas.append({"seed": sd, "error": "VINA_FALLO"})
                continue
            mejor_score, mejor_rmsd = None, None
            for sc, at in mf.parsear_out_vina(
                    salida.read_text(encoding="utf-8", errors="replace")):
                if sc is not None and (mejor_score is None or sc < mejor_score):
                    mejor_score = sc
                c = mf.coords_pose_a_por_mol(at, s2m)
                if c:
                    v = mf.rmsd_pose_pocket(crystal, c)
                    if v is not None and (mejor_rmsd is None or v < mejor_rmsd):
                        mejor_rmsd = v
            try:
                salida.unlink()
            except OSError:
                pass
            if mejor_score is None:
                corridas.append({"seed": sd, "error": "SIN_POSES"})
                continue
            corridas.append({
                "seed": sd, "score": round(mejor_score, 3),
                "rmsd": round(mejor_rmsd, 3) if mejor_rmsd is not None else None,
                "t_s": round(time.time() - t1, 1)})
        val = [c["score"] for c in corridas if "score" in c]
        rms = [c["rmsd"] for c in corridas if c.get("rmsd") is not None]
        out["brazos"][nombre] = {
            "exh": exh, "corridas": corridas,
            "score_min": round(min(val), 3) if val else None,
            "score_sd_semillas": (round(
                (sum((x - sum(val) / len(val)) ** 2 for x in val) / (len(val) - 1)) ** 0.5, 3)
                if len(val) > 1 else None),
            "rmsd_min": round(min(rms), 3) if rms else None,
            "t_total_s": round(sum(c.get("t_s", 0) for c in corridas), 1)}

    a = out["brazos"].get("produccion", {}).get("score_min")
    b = out["brazos"].get("masivo", {}).get("score_min")
    if a is not None and b is not None:
        out["ganancia_masivo"] = round(a - b, 3)          # >0 => el masivo encontro mejor
        out["masivo_mejora"] = bool(b < a - DELTA_RUIDO)
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-29-EMP: cota empirica del optimo global")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-29-EMP"
    out_dir.mkdir(parents=True, exist_ok=True)

    ruta = ws / "scripts" / "artifacts_science" / "MF-29-EMP" / "cohorte.json"
    if not ruta.exists():
        print("[MF-29-EMP] ERROR: falta cohorte.json")
        return 2
    coh = json.loads(ruta.read_text(encoding="utf-8"))
    jobs = [(r["pid"], r["estrato"]) for r in coh["cohorte"]]
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[MF-29-EMP] {len(jobs)} complejos x "
          f"{sum(len(s) for _, s in BRAZOS.values())} corridas "
          f"(exh {[e for e, _ in BRAZOS.values()]})", flush=True)

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
                      f"prod={r.get('brazos',{}).get('produccion',{}).get('score_min')} "
                      f"masivo={r.get('brazos',{}).get('masivo',{}).get('score_min')} "
                      f"gana={r.get('ganancia_masivo')} {r.get('error','')} "
                      f"({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8",
                          newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "masivo_mejora" in r]
    n_mej = sum(1 for r in ok if r["masivo_mejora"])
    frac = (n_mej / len(ok)) if ok else None
    lectura = None
    if frac is not None:
        lectura = ("BUSQUEDA" if frac >= 0.30 else
                   "OBJETIVO" if frac < 0.10 else "MIXTO")

    resumen: Dict[str, Any] = {}
    for est in sorted({r["estrato"] for r in ok}):
        g = [r for r in ok if r["estrato"] == est]
        gan = [r["ganancia_masivo"] for r in g]
        resumen[est] = {
            "n": len(g),
            "n_masivo_mejora": sum(1 for r in g if r["masivo_mejora"]),
            "ganancia_mediana": round(median(gan), 3) if gan else None,
            "ganancia_max": round(max(gan), 3) if gan else None,
        }

    metrics = {
        "experiment_id": "MF-29-EMP",
        "tipo": "medicion con regla de lectura preregistrada (cota superior empirica)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"brazos": {k: {"exh": e, "seeds": list(s)} for k, (e, s) in BRAZOS.items()},
                   "num_modes": NUM_MODES, "box": BOX, "ligando": LIGANDO,
                   "delta_ruido_kcal": DELTA_RUIDO,
                   "criterio_cohorte": "TORSDOF<=6 en el PDBQT (dimension que Vina busca)"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "cantidad_primaria": {
            "definicion": "fraccion de complejos donde min(score exh=512) < min(score exh=8) - 0.10",
            "n_mejora": n_mej, "de": len(ok), "fraccion": round(frac, 4) if frac is not None else None,
            "lectura_preregistrada": lectura},
        "por_estrato": resumen,
        "limites_declarados": [
            "NO es el certificado de MF-29; que el masivo no mejore no prueba optimalidad global",
            "el estrato COLOCACION aporta n pequeno: se reporta comparacion pareada, no mediana",
            "no extrapola fuera del regimen de <=6 torsiones",
        ],
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"[MF-29-EMP] LISTO n={len(ok)} frac={frac} lectura={lectura} "
          f"({round(time.time()-t0)}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
