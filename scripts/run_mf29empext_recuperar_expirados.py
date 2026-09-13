#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf29empext_recuperar_expirados.py — MF-29-EMP-EXT: los dos que expiraron.

Corre en el contenedor `moldesign-lab` del servidor, el mismo de `MF-29-EMP`.

Que se recupera
---------------
`MF-29-EMP` leyo sobre **48** de 50. `1mmr` y `1nm6` figuran en su `per_complex.jsonl` como
`VINA_FALLO` en las tres semillas del brazo masivo, con `t_total_s: 0`, y **no fallaron**:
el tiempo de fila menos el del brazo de produccion da 43200.4 s y 43200.6 s, exactamente
3 x el `timeout=14400` que esta en duro en `run_mf29emp_optimo_global.py:146`. Son tres
plazos vencidos, documentados en el `failures.jsonl` de `MF-29-EMP`.

A `exh=512` estos dos necesitan mas de 4 h por semilla: su brazo de produccion tardo 569 y
736 s por semilla a `exh=8`, unas diez veces la media de la cohorte, y 64x de presupuesto
sobre eso se sale del plazo.

Protocolo: identico, salvo el plazo
-----------------------------------
Mismo ligando `conf0.flex.pdbqt`, mismo receptor y caja de 25 A, `num_modes=9`, `--cpu 1`,
brazo masivo `exh=512` con semillas {42, 7, 13}. **Lo unico que cambia es el timeout**, que
aqui es parametro y no constante. El brazo de produccion NO se recomputa: sus valores ya
estan medidos en `MF-29-EMP` -1mmr -6.608, 1nm6 -8.724- y se reusan tal cual.

Lectura preregistrada
---------------------
La union de los 48 ya leidos mas estos 2, con **los umbrales de `MF-29-EMP` sin tocar**:
`f` = fraccion de complejos donde `min(exh=512) < min(exh=8) - 0.10`.

  * `f >= 0.30` -> BUSQUEDA
  * `f < 0.10`  -> OBJETIVO
  * intermedio  -> MIXTO

**El caso de borde, declarado ANTES de correr.** Hoy son 3 de 48 = 0.0625. Los desenlaces
posibles sobre 50 son:

  * ninguno mejora -> 3/50 = 0.0600 -> **OBJETIVO**, se confirma;
  * uno mejora     -> 4/50 = 0.0800 -> **OBJETIVO**, se confirma;
  * los dos mejoran-> 5/50 = 0.1000 -> **MIXTO**, porque la regla de `MF-29-EMP` dice
    `< 0.10` para OBJETIVO y 0.1000 no es menor que 0.10.

Ese tercer desenlace **cambiaria la lectura de `MF-29-EMP`** y esta escrito aqui antes de
mirar, precisamente para no discutirlo despues. Su probabilidad a priori es baja -3 de 48
mejoraron y las ganancias maximas de toda la cohorte no pasan de 0.282- pero no es cero, y
no se resuelve moviendo el umbral.

Limites declarados
------------------
1. **No re-sella `MF-29-EMP`.** Aquel queda como esta, leido sobre 48 y con su limitacion
   declarada. Esto es una extension con su propio registro, como `REC-08-EXT` o `FEP-02-EXT`.
2. **No certifica optimalidad global.** `MF-29` sigue ABIERTO.
3. Los tiempos son orientativos: el servidor puede estar compartido con otro trabajo. La
   cantidad primaria es el score, que no depende de la carga -el mismo limite que declaro
   `MF-29-EMP`-.
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
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Identicos a MF-29-EMP
BOX = 25.0
NUM_MODES = 9
EXH_MASIVO = 512
SEMILLAS_MASIVO = (42, 7, 13)
DELTA_RUIDO = 0.10
LIGANDO = "conf0.flex.pdbqt"
EXPIRADOS = ("1mmr", "1nm6")


def _vina() -> str:
    return os.environ.get("MF29_VINA", "/usr/local/bin/vina")


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def correr_masivo(ws: Path, pid: str, estrato: str, timeout: int, tmp: Path) -> Dict[str, Any]:
    """El brazo masivo de MF-29-EMP para un complejo, con el plazo como parametro."""
    import molflex as mf

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato}
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

    corridas = []
    for sd in SEMILLAS_MASIVO:
        salida = tmp / f"{pid}_masivo_s{sd}.pdbqt"
        cmd = [_vina(), "--receptor", str(rec), "--ligand", str(lig)] + _caja(centro) + [
            "--exhaustiveness", str(EXH_MASIVO), "--num_modes", str(NUM_MODES),
            "--seed", str(sd), "--cpu", "1", "--out", str(salida)]
        t1 = time.time()
        expiro = False
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok, expiro = False, True
        if not ok:
            corridas.append({"seed": sd,
                             "error": "TIMEOUT" if expiro else "VINA_FALLO",
                             "t_s": round(time.time() - t1, 1)})
            print(f"    {pid} s{sd}: {'TIMEOUT' if expiro else 'VINA_FALLO'} "
                  f"tras {round(time.time()-t1)}s", flush=True)
            continue
        mejor_score, mejor_rmsd = None, None
        for sc, at in mf.parsear_out_vina(salida.read_text(encoding="utf-8", errors="replace")):
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
            corridas.append({"seed": sd, "error": "SIN_POSES", "t_s": round(time.time() - t1, 1)})
            continue
        corridas.append({"seed": sd, "score": round(mejor_score, 3),
                         "rmsd": round(mejor_rmsd, 3) if mejor_rmsd is not None else None,
                         "t_s": round(time.time() - t1, 1)})
        print(f"    {pid} s{sd}: score={round(mejor_score,3)} "
              f"rmsd={mejor_rmsd} en {round(time.time()-t1)}s", flush=True)

    val = [c["score"] for c in corridas if "score" in c]
    rms = [c["rmsd"] for c in corridas if c.get("rmsd") is not None]
    out["brazo_masivo"] = {
        "exh": EXH_MASIVO, "corridas": corridas,
        "score_min": round(min(val), 3) if val else None,
        "score_sd_semillas": (round(
            (sum((x - sum(val) / len(val)) ** 2 for x in val) / (len(val) - 1)) ** 0.5, 3)
            if len(val) > 1 else None),
        "rmsd_min": round(min(rms), 3) if rms else None,
        "t_total_s": round(sum(c.get("t_s", 0) for c in corridas), 1)}
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-29-EMP-EXT: recuperar 1mmr y 1nm6")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--timeout", type=int, default=72000,
                    help="plazo por corrida en segundos (MF-29-EMP tenia 14400 en duro)")
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-29-EMP-EXT"
    out_dir.mkdir(parents=True, exist_ok=True)

    base = {}
    for l in (art / "MF-29-EMP" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            base[r["pid"]] = r

    jobs = [(pid, base[pid]["estrato"]) for pid in EXPIRADOS if pid in base]
    print(f"[MF-29-EMP-EXT] {len(jobs)} complejos x {len(SEMILLAS_MASIVO)} semillas "
          f"a exh={EXH_MASIVO} | timeout={args.timeout}s ({args.timeout/3600:.1f} h) "
          f"| workers={args.workers}", flush=True)
    for pid, est in jobs:
        prod = base[pid]["brazos"]["produccion"]
        print(f"  {pid} [{est}] produccion ya medida: score_min={prod['score_min']} "
              f"({prod['t_total_s']}s en 5 semillas a exh=8)", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(correr_masivo, ws, pid, est, args.timeout, tmp): pid
                    for pid, est in jobs}
            for fut in as_completed(futs):
                filas.append(fut.result())
                r = filas[-1]
                prod = base[r["pid"]]["brazos"]["produccion"]
                a = prod.get("score_min")
                b = r.get("brazo_masivo", {}).get("score_min")
                if a is not None and b is not None:
                    r["score_produccion"] = a
                    r["ganancia_masivo"] = round(a - b, 3)
                    r["masivo_mejora"] = bool(b < a - DELTA_RUIDO)
                print(f"  [{len(filas)}/{len(jobs)}] {r['pid']} prod={a} "
                      f"masivo={b} gana={r.get('ganancia_masivo')} "
                      f"mejora={r.get('masivo_mejora')} ({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    # ── Union con los 48 ya leidos, con los umbrales de MF-29-EMP sin tocar ──
    prev_ok = [r for r in base.values() if "masivo_mejora" in r]
    prev_mej = sum(1 for r in prev_ok if r["masivo_mejora"])
    nuevos_ok = [r for r in filas if "masivo_mejora" in r]
    nuevos_mej = sum(1 for r in nuevos_ok if r["masivo_mejora"])
    n_union = len(prev_ok) + len(nuevos_ok)
    n_mej = prev_mej + nuevos_mej
    frac = (n_mej / n_union) if n_union else None
    lectura = None
    if frac is not None:
        lectura = ("BUSQUEDA" if frac >= 0.30 else
                   "OBJETIVO" if frac < 0.10 else "MIXTO")

    metrics = {
        "experiment_id": "MF-29-EMP-EXT",
        "tipo": "extension de cobertura de MF-29-EMP con regla de lectura preregistrada",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"exh_masivo": EXH_MASIVO, "semillas": list(SEMILLAS_MASIVO),
                   "num_modes": NUM_MODES, "box": BOX, "ligando": LIGANDO,
                   "delta_ruido_kcal": DELTA_RUIDO,
                   "timeout_s": args.timeout,
                   "cambio_unico": "el timeout deja de ser la constante 14400 en duro y pasa a parametro",
                   "brazo_produccion": "reusado de MF-29-EMP sin recomputo"},
        "recuperados": {
            "intentados": list(EXPIRADOS),
            "con_lectura": [r["pid"] for r in nuevos_ok],
            "sin_lectura": [r["pid"] for r in filas if "masivo_mejora" not in r],
            "n_mejoran": nuevos_mej,
        },
        "union": {
            "definicion": "los 48 leidos en MF-29-EMP mas los recuperados aqui, misma cantidad primaria",
            "n_previos": len(prev_ok), "n_mejoran_previos": prev_mej,
            "n_total": n_union, "n_mejoran_total": n_mej,
            "fraccion": round(frac, 4) if frac is not None else None,
            "lectura_preregistrada": lectura,
            "umbrales": ">=0.30 BUSQUEDA, <0.10 OBJETIVO, intermedio MIXTO (los de MF-29-EMP, sin tocar)",
            "lectura_de_MF-29-EMP_sobre_48": "OBJETIVO (3/48 = 0.0625)",
            "cambia_la_lectura": bool(lectura is not None and lectura != "OBJETIVO"),
        },
        "limites_declarados": [
            "no re-sella MF-29-EMP; aquel queda leido sobre 48 con su limitacion declarada",
            "no certifica optimalidad global; MF-29 sigue ABIERTO",
            "tiempos orientativos: el servidor puede estar compartido; la cantidad primaria es el score",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"[MF-29-EMP-EXT] LISTO recuperados={len(nuevos_ok)}/{len(jobs)} "
          f"union={n_mej}/{n_union} frac={frac} lectura={lectura} "
          f"cambia={metrics['union']['cambia_la_lectura']} ({round(time.time()-t0)}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
