#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf33ext_cobertura_flexible.py — MF-33-EXT: la cobertura del oráculo, con generador flexible.

Mismo metodo que el brazo B de `MF-33`, distinto alcance: **los 116 de train** en vez de los
48 de la cohorte. Igual que `REC-08-EXT` extendio a `REC-08`.

El denominador que nadie ha vuelto a medir
------------------------------------------
`RC-F0-V2-EXT` midio que el **93.9%** de las poses del conjunto v2 vienen del **protocolo
rigido** -`molflex` docka `conf{cid}.rigid.pdbqt`-. Sobre ese conjunto, la cobertura del
oraculo en train con la metrica del programa es **92 de 116 = 0.7931**, y es el denominador
de media docena de conclusiones.

`MF-33` midio que dockeando **flexibles** los MISMOS conformeros la cobertura del estrato
dificil pasa de 1/33 a 26/33. Si ese salto se sostiene sobre los 116, el denominador de todo
el programa esta mal puesto.

LA LINEA BASE CORRECTA, Y POR QUE NO ES EL 93.1%
------------------------------------------------
`MF-02D` reporto dos numeros y conviene no confundirlos:

  * `cobertura_despues` = 108/116 = **0.9310**, y
  * su gate **G5**, declarado sobre la **metrica de pocket, que es la primaria**, dio
    **0.7931** y **FALLO** el liston de 0.90. Por eso `MF-02D` esta sellado **NO_GO**.

La linea base de este experimento es **0.7931**, la primaria. El 0.9310 es de otra metrica y
no se usa aqui.

Protocolo — identico al brazo B, sin nada nuevo
-----------------------------------------------
Por complejo, dockear **todos** los `conf*.flex.pdbqt` del ensemble ETKDG con los mismos
parametros del brazo de control de `MF-28`, que es de donde `MF-33` reuso su brazo B:
`exhaustiveness=8`, `num_modes=9`, `seed=42`, caja de 25 A, `--cpu 1`. Metrica
`rmsd_pose_pocket`, RMSD de pesados en el marco del pocket **sin alineamiento**, seccion 5.1
del doc 49.

El oraculo de un complejo es el mejor RMSD entre todas las poses que el brazo conserva.

Lectura preregistrada — con un liston HEREDADO, no elegido
-----------------------------------------------------------
Cantidad primaria: **cobertura = fraccion de los 116 con oraculo <= 2.0 A**.

El umbral no se elige aqui: es el **0.90 del gate G5 de `MF-02D`**, declarado antes que este
experimento y ya usado para sellar aquel NO_GO. Se reusa tal cual.

  * `cobertura >= 0.90` -> **EL GENERADOR FLEXIBLE ALCANZA EL LISTON** que el rigido no
    alcanzo. La regeneracion completa de la cohorte queda **JUSTIFICADA**, y con ella el
    coste de re-sellar lo que dependa del denominador.
  * `cobertura < 0.90` -> **NO ALCANZA EL LISTON.** Se reporta la diferencia contra 0.7931
    como magnitud descriptiva, y la regeneracion NO queda justificada por esta via.

Secundario: **curva de cobertura contra presupuesto**
-----------------------------------------------------
Se registra el oraculo acumulado tras 1, 2, ... K corridas, en **orden de indice de
conformero** -no ordenado por calidad, que seria informacion de oraculo inexistente en
produccion-. Eso permite leer la cobertura **a presupuesto igualado** y no solo al final.

Esta parte existe por `MF-33-A3`, que a la hora de escribir esto esta midiendo si la ventaja
del brazo B era **diversidad conformacional** o simplemente **conteo de poses**. La curva
hace que este experimento se lea con cualquiera de las dos respuestas:

  * si A3 dice que la ventaja era diversidad, el titular es la cobertura final;
  * si dice que era conteo de poses, el titular es la cobertura al presupuesto de poses del
    protocolo rigido, que la curva da sin recomputar nada.

**Por eso este experimento no depende de A3 para EJECUTARSE, solo para titularse.**

Coste medido, no estimado
-------------------------
El brazo B de `MF-33` consumio **42.6 CPU-h** en 48 complejos -mediana 2548 s por complejo,
maximo 11391 s, 970 docks en total-. Extrapolado a 116: **~103 CPU-h**. Con 10 workers son
~10.3 h; con los 4 nucleos del servidor, ~25.7 h.

Limites declarados ANTES de correr
----------------------------------
1. **El oraculo es una cota superior de lo alcanzable, no una prediccion.** Mide si la pose
   buena esta en el conjunto, no si el selector la encuentra. `MF-02D` ya declaro fuera de
   alcance toda evaluacion de selector y aqui se mantiene.
2. **No decide la regeneracion por si solo.** La justifica o no; ejecutarla es un programa
   con su propio coste de re-sellado, y afecta a los 17 consumidores que `RC-F0-V2-EXT`
   inventario.
3. Los conformeros son los del ensemble ETKDG ya en disco: **no se regeneran**. Si el techo
   fuese conformacional, este experimento no lo mueve -`MF-02A-EXT` midio 83.9% a K30-.
4. `MF-33-CRUCES` midio que 4 de los 7 que el ensemble no convierte son cristales que
   puntuan absurdo, y `REC-09` que al menos dos lo son por aguas bloqueantes. Parte del
   techo de cobertura puede ser **preparacion** y no generador; este experimento no los
   separa y no debe leerse como si lo hiciera.
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

# Identicos al brazo de control de MF-28, de donde MF-33 reuso su brazo B
BOX = 25.0
SEED = 42
EXH = 8
NUM_MODES = 9
UMBRAL_A = 2.0
RE_FLEX = re.compile(r"conf\d+\.flex\.pdbqt$")   # excluye *.relax.* y *.flexpose.*

LISTON_MF02D_G5 = 0.90        # heredado, no elegido aqui
BASE_RIGIDA = 0.7931          # cobertura del conjunto v2, metrica de pocket


def _vina() -> str:
    return os.environ.get("MF33EXT_VINA", "/usr/local/bin/vina")


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


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

    flexes = sorted([f for f in w.glob("conf*.flex.pdbqt") if RE_FLEX.match(f.name)],
                    key=lambda f: int(re.search(r"conf(\d+)", f.name).group(1)))
    if not flexes:
        out["error"] = "SIN_CONFORMEROS"
        return out

    corridas: List[Dict[str, Any]] = []
    curva: List[Optional[float]] = []      # oraculo acumulado tras 1, 2, ... K corridas
    mejor = None
    t_cpu = 0.0
    for f in flexes:
        salida = tmp / f"{pid}_{f.stem}.out.pdbqt"
        cmd = [_vina(), "--receptor", str(rec), "--ligand", str(f)] + _caja(centro) + [
            "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
            "--seed", str(SEED), "--cpu", "1", "--out", str(salida)]
        t1 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok = False
        dt = time.time() - t1
        t_cpu += dt
        if not ok:
            corridas.append({"conf": f.stem, "error": "VINA_FALLO", "t_s": round(dt, 1)})
            curva.append(mejor)
            continue
        rmsd_corrida = None
        for _sc, at in mf.parsear_out_vina(salida.read_text(encoding="utf-8", errors="replace")):
            c = mf.coords_pose_a_por_mol(at, s2m)
            if c:
                v = mf.rmsd_pose_pocket(crystal, c)
                if v is not None and (rmsd_corrida is None or v < rmsd_corrida):
                    rmsd_corrida = v
        try:
            salida.unlink()
        except OSError:
            pass
        if rmsd_corrida is not None and (mejor is None or rmsd_corrida < mejor):
            mejor = rmsd_corrida
        corridas.append({"conf": f.stem,
                         "rmsd_min": round(rmsd_corrida, 3) if rmsd_corrida is not None else None,
                         "t_s": round(dt, 1)})
        curva.append(round(mejor, 3) if mejor is not None else None)

    out["n_docks"] = len(flexes)
    out["corridas"] = corridas
    out["oraculo"] = round(mejor, 3) if mejor is not None else None
    out["cubierto"] = bool(mejor is not None and mejor <= UMBRAL_A)
    out["curva_oraculo"] = curva
    out["primer_dock_que_cubre"] = next(
        (i + 1 for i, v in enumerate(curva) if v is not None and v <= UMBRAL_A), None)
    out["cpu_s"] = round(t_cpu, 1)
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-33-EXT: cobertura del oraculo con generador flexible")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-33-EXT"
    out_dir.mkdir(parents=True, exist_ok=True)

    m13 = {}
    for l in (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            m13[r["pid"]] = r.get("estrato", "RESTO")
    jobs = sorted(m13.items())
    if args.limite:
        jobs = jobs[:args.limite]

    print(f"[MF-33-EXT] {len(jobs)} complejos | brazo B de MF-33 (todos los conf*.flex) | "
          f"exh={EXH} num_modes={NUM_MODES} seed={SEED} | workers={args.workers}", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, ws, pid, est, tmp): pid for pid, est in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                filas.append(fut.result())
                r = filas[-1]
                print(f"  [{i}/{len(jobs)}] {r['pid']} K={r.get('n_docks')} "
                      f"oraculo={r.get('oraculo')} cubierto={r.get('cubierto')} "
                      f"cpu={r.get('cpu_s')}s {r.get('error','')} "
                      f"({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if r.get("oraculo") is not None]
    n_cub = sum(1 for r in ok if r["cubierto"])
    cob = (n_cub / len(ok)) if ok else None
    lectura = None
    if cob is not None:
        lectura = ("EL_GENERADOR_FLEXIBLE_ALCANZA_EL_LISTON" if cob >= LISTON_MF02D_G5
                   else "NO_ALCANZA_EL_LISTON")

    # curva agregada: cobertura si solo se hubieran hecho k corridas
    kmax = max((r["n_docks"] for r in ok), default=0)
    curva_cob = []
    for k in range(1, kmax + 1):
        c = 0
        for r in ok:
            v = r["curva_oraculo"][k - 1] if len(r["curva_oraculo"]) >= k else r["curva_oraculo"][-1]
            if v is not None and v <= UMBRAL_A:
                c += 1
        curva_cob.append({"k": k, "cubiertos": c, "cobertura": round(c / len(ok), 4)})

    por_estrato = {}
    for est in sorted({r["estrato"] for r in ok}):
        g = [r for r in ok if r["estrato"] == est]
        por_estrato[est] = {"n": len(g), "cubiertos": sum(1 for r in g if r["cubierto"]),
                            "cobertura": round(sum(1 for r in g if r["cubierto"]) / len(g), 4),
                            "oraculo_mediano": round(median([r["oraculo"] for r in g]), 3)}

    metrics = {
        "experiment_id": "MF-33-EXT",
        "tipo": "extension de alcance de MF-33 brazo B con regla de lectura preregistrada",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"exh": EXH, "num_modes": NUM_MODES, "seed": SEED, "box": BOX,
                   "umbral_A": UMBRAL_A, "metrica": "rmsd_pose_pocket sin alineamiento",
                   "ligandos": "todos los conf*.flex.pdbqt del ensemble ETKDG ya en disco",
                   "identico_a": "brazo de control de MF-28, reusado como brazo B por MF-33"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "cantidad_primaria": {
            "definicion": "fraccion de complejos con oraculo <= 2.0 A (metrica de pocket)",
            "cubiertos": n_cub, "de": len(ok),
            "cobertura": round(cob, 4) if cob is not None else None,
            "liston_heredado_de_MF02D_G5": LISTON_MF02D_G5,
            "base_rigida_conjunto_v2": BASE_RIGIDA,
            "diferencia_vs_base": round(cob - BASE_RIGIDA, 4) if cob is not None else None,
            "lectura_preregistrada": lectura},
        "por_estrato": por_estrato,
        "curva_cobertura_vs_presupuesto": curva_cob,
        "limites_declarados": [
            "el oraculo es cota superior de lo alcanzable, no prediccion: no evalua selector",
            "no decide la regeneracion por si solo; ejecutarla es un programa con su re-sellado",
            "los conformeros no se regeneran: si el techo fuese conformacional esto no lo mueve",
            "parte del techo puede ser PREPARACION y no generador (MF-33-CRUCES, REC-09); no los separa",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"[MF-33-EXT] LISTO n={len(ok)} cobertura={cob} (base rigida {BASE_RIGIDA}, "
          f"liston {LISTON_MF02D_G5}) lectura={lectura} ({round(time.time()-t0)}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
