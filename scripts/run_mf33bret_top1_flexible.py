#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf33bret_top1_flexible.py — MF-33-B-RET: el brazo B otra vez, esta vez sin tirar las poses.

Corre en la maquina local, donde `posebusters` esta instalado.

Por que existe
--------------
`MF-33` y `MF-33-A3` miden **cobertura del oraculo**: si la pose buena existe entre las que el
brazo conserva. `MF-09` midio la otra mitad y el numero es duro -top-1 acierta **0/33** en el
estrato dificil, top-20 **2/33**-, asi que subir el techo de 1/33 a 26/33 **podria no mover
nada de lo que el usuario recibe**. Es la primera amenaza a la validez del paper (T1 del
doc. 52) y hoy no esta medida sobre el brazo que el paper defiende.

No se puede medir con lo que hay: `run_mf28_roadmap.py` escribio las poses del brazo B en un
`TemporaryDirectory` y se borraron al terminar. `MF-33-TOP1` da el precedente en el protocolo
**rigido**, cuyas poses si sobrevivieron, pero **ese no es el brazo del paper**.

Este experimento repite el brazo B **cambiando una sola cosa**: registra `(score, rmsd)` de
cada pose en vez de tirarlas.

Protocolo — identico al brazo B, salvo la retencion
----------------------------------------------------
Cohorte: los **48** de `MF-33`, que es la del paper. Por complejo, dockear **todos** los
`conf*.flex.pdbqt` con los parametros del brazo de control de `MF-28`, de donde `MF-33` reuso
su brazo B: `exhaustiveness=8`, `num_modes=9`, `seed=42`, caja de 25 A, `--cpu 1`. Metrica
`rmsd_pose_pocket` sin alineamiento.

No se re-corre sobre los 116: `MF-33-EXT` ya lo esta haciendo para la cobertura, y duplicarlo
seria gastar 103 CPU-h para responder una pregunta que se contesta con 42.6 sobre la cohorte
que el paper usa.

GATE DE CORDURA, ANTES DEL PRIMARIO
------------------------------------
**G1**: el oraculo del brazo ENSEMBLE debe **reproducir el `rmsd_min` del brazo B sellado en
`MF-33`** dentro de 0.001 A en >= 95% de los complejos. Mismo protocolo, misma semilla, mismo
binario: si no reproduce, algo cambio entre entonces y ahora y **nada de lo que sigue se lee**.

Es la unica forma de saber que este re-run es el mismo experimento y no uno parecido.

Que se mide
-----------
Sobre las poses de cada complejo, ordenadas por **score de Vina** (mas negativo = mejor):

    SINGLE     las 9 poses de `conf0.flex.pdbqt`, el brazo A de `MF-33`
    ENSEMBLE   las K x 9 poses de todos los conformeros, el brazo B

    top1       rmsd de la pose de mejor score
    top5       mejor rmsd entre las 5 de mejor score
    oraculo    mejor rmsd entre todas

Y, sobre el **top-1 de cada brazo**, `pb_valid_fisica` de `posebusters_metrica`, con los
checks que fallan. Un top-1 con RMSD bueno y fisicamente invalido no es un acierto.

Lectura preregistrada
---------------------
McNemar exacto pareado sobre «acierta <= 2 A», por separado en `top1`, `top5` y `oraculo`.

  * **LA VENTAJA LLEGA AL USUARIO** si el ensemble mejora `oraculo` **y** `top1`, ambos con
    p < 0.05. El claim del paper pasa de «mejoramos el pool» a «mejoramos la entrega».
  * **EL CUELLO SE DESPLAZA A LA SELECCION** si mejora `oraculo` (p < 0.05) y **no** `top1`.
    La diversidad conformacional resuelve el cuello de generacion y lo traslada al selector.
    **Este desenlace no debilita el paper: lo reencuadra**, y conecta con la cartera RS y con
    `MF-09`.
  * **SIN EFECTO EN LA ENTREGA** si no mejora ninguno de los dos. Habria que decirlo tal cual.

Se reporta ademas el **margen de seleccion**: complejos con pose buena disponible que el
brazo **no entrega**. Es la cantidad que el programa deberia optimizar si sale la segunda.

Coste
-----
**~42.6 CPU-h**, medidos del consumo real del brazo B en `MF-33`. Unas 4.5 h con 10 workers.
Lanzar con la maquina libre: `MF-33-EXT` ocupa los 12 nucleos hasta que cierre.

Limites declarados ANTES de correr
----------------------------------
1. **Se ordena por score de Vina, sin rescoring.** La cartera RS mide eso aparte; meterlo aqui
   confundiria generacion, seleccion y funcion de puntuacion en un solo numero.
2. `SINGLE` usa `conf0` **por indice y no por calidad**: elegir el mejor conformero seria
   informacion de oraculo inexistente en produccion. Misma convencion que el brazo A.
3. El ensemble selecciona sobre un pool K veces mayor. **No es un confundido: es el fenomeno.**
4. **No reabre `MF-33` ni `MF-33-A3`.** Sus cantidades son de oraculo y siguen como estan;
   esto anade una cantidad que no tenian.
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
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Identicos al brazo de control de MF-28, de donde MF-33 reuso su brazo B
BOX = 25.0
SEED = 42
EXH = 8
NUM_MODES = 9
UMBRAL_A = 2.0
RE_FLEX = re.compile(r"conf(\d+)\.flex\.pdbqt$")
G1_TOL = 0.001
G1_MIN = 0.95


def _vina() -> str:
    return os.environ.get("MF33BRET_VINA", "/usr/local/bin/vina")


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def _metricas(poses: List[Tuple[float, float]]) -> Dict[str, Any]:
    if not poses:
        return {"n_poses": 0, "top1": None, "top5": None, "oraculo": None}
    orden = sorted(poses, key=lambda p: p[0])
    m = {"n_poses": len(poses), "top1": round(orden[0][1], 3),
         "top5": round(min(p[1] for p in orden[:5]), 3),
         "oraculo": round(min(p[1] for p in poses), 3),
         "score_top1": round(orden[0][0], 3)}
    for k in ("top1", "top5", "oraculo"):
        m[f"acierta_{k}"] = bool(m[k] is not None and m[k] <= UMBRAL_A)
    m["margen_de_seleccion"] = bool(m["acierta_oraculo"] and not m["acierta_top1"])
    return m


def analizar(ws: Path, pid: str, estrato: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato}
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

    flexes = sorted([f for f in w.glob("conf*.flex.pdbqt") if RE_FLEX.search(f.name)],
                    key=lambda f: int(RE_FLEX.search(f.name).group(1)))
    if not flexes:
        out["error"] = "SIN_CONFORMEROS"
        return out

    por_conf: Dict[int, List[Tuple[float, float]]] = {}
    coords_top: Dict[int, Any] = {}
    t_cpu = 0.0
    for f in flexes:
        k = int(RE_FLEX.search(f.name).group(1))
        salida = tmp / f"{pid}_c{k}.out.pdbqt"
        cmd = [_vina(), "--receptor", str(rec), "--ligand", str(f)] + _caja(centro) + [
            "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
            "--seed", str(SEED), "--cpu", "1", "--out", str(salida)]
        t1 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok = False
        t_cpu += time.time() - t1
        if not ok:
            por_conf[k] = []
            continue
        lista: List[Tuple[float, float]] = []
        for score, atomos in mf.parsear_out_vina(
                salida.read_text(encoding="utf-8", errors="replace")):
            if score is None:
                continue
            c = mf.coords_pose_a_por_mol(atomos, s2m)
            if not c:
                continue
            r = mf.rmsd_pose_pocket(crystal, c)
            if r is None:
                continue
            lista.append((float(score), float(r)))
            coords_top[len(coords_top)] = (float(score), c)
        por_conf[k] = lista
        try:
            salida.unlink()
        except OSError:
            pass

    single = por_conf.get(0, [])
    ensemble = [pp for v in por_conf.values() for pp in v]
    out["K"] = len(flexes)
    out["SINGLE"] = _metricas(single)
    out["ENSEMBLE"] = _metricas(ensemble)
    out["cpu_s"] = round(t_cpu, 1)

    # ── validez fisica del top-1 de cada brazo ──
    try:
        import posebusters_metrica as pbm
        prot = ws / "data" / "pdbbind" / pid / f"{pid}_protein.pdb"
        if pbm.disponible() and prot.exists():
            mh = pbm.mol_con_hidrogenos(crystal)
            for brazo, poses in (("SINGLE", single), ("ENSEMBLE", ensemble)):
                if not poses:
                    continue
                mejor = min(p[0] for p in poses)
                cand = [c for _i, (s, c) in coords_top.items() if abs(s - mejor) < 1e-6]
                if cand:
                    r = pbm.evaluar_pose(pbm.pose_a_mol(mh, cand[0]), mh, prot)
                    out[brazo]["pb_valid_fisica"] = r.get("pb_valid_fisica")
                    out[brazo]["pb_checks_que_fallan"] = r.get("checks_que_fallan")
    except Exception as ex:
        out["pb_error"] = f"{type(ex).__name__}:{str(ex)[-80:]}"

    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    from estadistica_fnd04 import mcnemar_exacto

    ap = argparse.ArgumentParser(description="MF-33-B-RET: brazo B con retencion, top-1 y validez fisica")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-33-B-RET"
    out_dir.mkdir(parents=True, exist_ok=True)

    m33 = {r["pid"]: r for r in
           (json.loads(l) for l in
            (art / "MF-33" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip())}
    jobs = sorted((pid, r["estrato"]) for pid, r in m33.items())
    if args.limite:
        jobs = jobs[:args.limite]

    print(f"[MF-33-B-RET] {len(jobs)} complejos | brazo B con retencion de (score, rmsd) | "
          f"exh={EXH} seed={SEED} | workers={args.workers}", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, ws, pid, est, tmp): pid for pid, est in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                filas.append(fut.result())
                r = filas[-1]
                print(f"  [{i}/{len(jobs)}] {r['pid']} K={r.get('K')} "
                      f"S(top1={r.get('SINGLE',{}).get('top1')},or={r.get('SINGLE',{}).get('oraculo')}) "
                      f"E(top1={r.get('ENSEMBLE',{}).get('top1')},or={r.get('ENSEMBLE',{}).get('oraculo')}) "
                      f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [f for f in filas if "ENSEMBLE" in f and f["ENSEMBLE"]["n_poses"] > 0]

    # ── G1: reproduce el brazo B sellado ──
    comp = [(f, m33[f["pid"]]["brazos"].get("B", {}).get("rmsd_min")) for f in ok
            if m33.get(f["pid"], {}).get("brazos", {}).get("B", {}).get("rmsd_min") is not None]
    iguales = sum(1 for f, ref in comp if abs(f["ENSEMBLE"]["oraculo"] - ref) <= G1_TOL)
    g1 = (iguales / len(comp)) if comp else 0.0

    def _pareado(campo: str, sub) -> Dict[str, Any]:
        b = sum(1 for f in sub if f["ENSEMBLE"][f"acierta_{campo}"] and not f["SINGLE"][f"acierta_{campo}"])
        c = sum(1 for f in sub if f["SINGLE"][f"acierta_{campo}"] and not f["ENSEMBLE"][f"acierta_{campo}"])
        ns = sum(1 for f in sub if f["SINGLE"][f"acierta_{campo}"])
        ne = sum(1 for f in sub if f["ENSEMBLE"][f"acierta_{campo}"])
        return {"single": ns, "ensemble": ne, "de": len(sub), "b_gana_ensemble": b,
                "c_gana_single": c, "mcnemar_p": round(mcnemar_exacto(b, c), 6),
                "delta_pp": round((ne - ns) / len(sub) * 100, 2) if sub else None}

    def _bloque(sub, etq):
        r = {"etiqueta": etq, "n": len(sub)}
        for campo in ("top1", "top5", "oraculo"):
            r[campo] = _pareado(campo, sub)
        r["margen_de_seleccion_single"] = sum(1 for f in sub if f["SINGLE"]["margen_de_seleccion"])
        r["margen_de_seleccion_ensemble"] = sum(1 for f in sub if f["ENSEMBLE"]["margen_de_seleccion"])
        return r

    glob = _bloque(ok, "TODOS")
    col = _bloque([f for f in ok if f["estrato"] == "COLOCACION"], "COLOCACION")

    mej_or = glob["oraculo"]["mcnemar_p"] < 0.05 and glob["oraculo"]["b_gana_ensemble"] > glob["oraculo"]["c_gana_single"]
    mej_t1 = glob["top1"]["mcnemar_p"] < 0.05 and glob["top1"]["b_gana_ensemble"] > glob["top1"]["c_gana_single"]
    lectura = ("LA_VENTAJA_LLEGA_AL_USUARIO" if (mej_or and mej_t1)
               else "EL_CUELLO_SE_DESPLAZA_A_LA_SELECCION" if mej_or
               else "SIN_EFECTO_EN_LA_ENTREGA")

    pbs = {}
    for brazo in ("SINGLE", "ENSEMBLE"):
        ev = [f for f in ok if f[brazo].get("pb_valid_fisica") is not None]
        val = [f for f in ev if f[brazo]["pb_valid_fisica"]]
        pbs[brazo] = {"n_evaluadas": len(ev), "n_validas": len(val),
                      "tasa": round(len(val) / len(ev), 4) if ev else None}

    metrics = {
        "experiment_id": "MF-33-B-RET",
        "tipo": "re-ejecucion con retencion y regla de lectura preregistrada",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"exh": EXH, "num_modes": NUM_MODES, "seed": SEED, "box": BOX,
                   "umbral_A": UMBRAL_A, "ligandos": "todos los conf*.flex.pdbqt",
                   "cambio_unico": "se registra (score, rmsd) de cada pose en vez de tirarlas",
                   "identico_a": "brazo de control de MF-28, reusado como brazo B por MF-33"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "G1_REPRODUCE_BRAZO_B_SELLADO": {
            "criterio": f"oraculo del ENSEMBLE == rmsd_min del brazo B de MF-33 dentro de {G1_TOL} A",
            "iguales": iguales, "de": len(comp),
            "fraccion": round(g1, 4), "minimo": G1_MIN, "pasa": bool(g1 >= G1_MIN)},
        "TODOS": glob, "COLOCACION": col,
        "lectura_preregistrada": lectura,
        "validez_fisica_del_top1": pbs,
        "limites_declarados": [
            "se ordena por score de Vina sin rescoring; la cartera RS mide eso aparte",
            "SINGLE usa conf0 por indice y no por calidad, como el brazo A de MF-33",
            "el ensemble selecciona sobre un pool K veces mayor: eso es el fenomeno",
            "no reabre MF-33 ni MF-33-A3: sus cantidades son de oraculo y siguen como estan",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"\n[MF-33-B-RET] n={len(ok)} | G1={round(g1,4)} ({'PASA' if g1>=G1_MIN else 'FALLA'})")
    for etq, blq in (("TODOS", glob), ("COLOCACION", col)):
        print(f"  {etq} (n={blq['n']}):")
        for campo in ("oraculo", "top5", "top1"):
            d = blq[campo]
            print(f"    {campo:8s} single={d['single']:3d} ensemble={d['ensemble']:3d} "
                  f"delta={d['delta_pp']:+6.2f}pp b={d['b_gana_ensemble']} c={d['c_gana_single']} p={d['mcnemar_p']}")
        print(f"    margen de seleccion: single={blq['margen_de_seleccion_single']} "
              f"ensemble={blq['margen_de_seleccion_ensemble']}")
    print(f"  LECTURA: {lectura}")
    print(f"  validez fisica top-1: single={pbs['SINGLE']['tasa']} ensemble={pbs['ENSEMBLE']['tasa']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
