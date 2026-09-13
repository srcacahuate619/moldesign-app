#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rec11_aguas_denovo.py — REC-11: las aguas, sobre docking de novo.

Corre en el contenedor `moldesign-lab` del servidor.

Por que existe
--------------
`docs/51_POLITICA_DE_AGUAS.md` declaro la politica actual -se conservan todas- y nombro
**un solo experimento** como lo unico que la cambiaria. Este es ese experimento.

`REC-09` midio el efecto de las aguas sobre el **scoring del cristal en su sitio**: 26 de
116 complejos tienen alguna agua que choca con el ligando cristalografico, y en `1fkh` dos
de ellas valen 12.919 kcal/mol. Pero la politica no gobierna el scoring del cristal:
gobierna el **docking de novo**, donde la pose no se conoce de antemano, el buscador explora
todo el sitio y choca con aguas que el cristal ni toca. Ese caso no estaba medido.

La diferencia importa en las dos direcciones. Conservar aguas puede **bloquear** la cuenca
nativa -lo que `REC-09` vio-, pero tambien puede **guiar**: un agua estructural que media un
puente de hidrogeno es parte del sitio, y quitarla deja un bolsillo que no existe. Ninguna
de las dos cosas se sabe hoy.

Diseno — intervencion pareada, una sola variable
------------------------------------------------
Cohorte: los **116 de train**. Ligando `conf0.flex.pdbqt`, **fijo y el mismo en los dos
brazos**. Misma caja de 25 A, mismo `exhaustiveness=8`, mismo `num_modes=9`, mismas cinco
semillas {42, 1, 2, 3, 4} -las del brazo de produccion de `MF-29-EMP`-.

    brazo CON   `rec.pdbqt` tal cual                    <- la politica actual
    brazo SIN   el mismo receptor sin ningun residuo    <- la politica alternativa
                de agua (HOH / WAT / DOD)

**Lo unico que cambia es el receptor.** El ligando es identico, asi que la penalizacion
torsional es la misma en los dos brazos y se cancela en cualquier comparacion -la leccion de
`MF-29-EMP-COR` aplicada por diseno-.

Se quitan TODAS las aguas, no solo las que chocarian: en produccion no existe una pose de
referencia con la que decidir cuales estorban. Esa es exactamente la asimetria que hace que
este experimento no sea `REC-09` otra vez.

Que se mide
-----------
Por brazo y complejo, sobre las poses de las cinco semillas:

  * **oraculo** = mejor `rmsd_pose_pocket` entre todas las poses que el brazo conserva.
    Es la cantidad primaria del programa y la que usan `MF-02D`, `MF-33` y `MF-33-EXT`.
  * **top-1** = `rmsd_pose_pocket` de la pose de mejor score. Es lo que produccion entrega
    de verdad, y va como secundario porque es mas ruidoso.

`cubierto` = oraculo <= 2.0 A, metrica de pocket sin alineamiento (seccion 5.1 del doc 49).

Lectura preregistrada
---------------------
Tabla pareada sobre los 116: `b` = complejos donde **SIN** cubre y **CON** no; `c` = donde
**CON** cubre y **SIN** no. McNemar exacto bilateral, de `estadistica_fnd04`.

  * `p < 0.05` con `b > c` -> **QUITARLAS MEJORA**. La politica de `docs/51` cambia, y el
    coste de regenerar queda justificado.
  * `p < 0.05` con `c > b` -> **CONSERVARLAS MEJORA**. La politica queda confirmada
    **positivamente**, que hoy no lo esta: hoy solo esta declarada.
  * `p >= 0.05` -> **SIN DIFERENCIA DETECTABLE**. La politica se mantiene por inercia y se
    declara el limite de potencia, sin leerlo como equivalencia.

Efecto minimo detectable, declarado ANTES (seccion 20.9)
---------------------------------------------------------
  * Si `c = 0`, McNemar exacto exige **`b >= 6`** para `p < 0.05` (2 * 0.5^6 = 0.031).
  * Con una discordancia realista del 20%, el MDE pareado con n=116 es de **11.3 puntos
    porcentuales**, unos **13 complejos netos**. Con discordancia del 10% baja a 8.0 puntos.

Diferencias menores que eso **no son resolubles con esta cohorte** y se reportaran como no
concluyentes, nunca como tendencia. Es la leccion de `RS-14`, que descubrio su limite de
resolucion despues de ejecutar.

Limites declarados ANTES de correr
----------------------------------
1. **Un solo conformero.** `MF-33` midio que `conf0.flex` solo convierte 12 de 33 en el
   estrato dificil contra 26 del ensemble. Esto **no** mide la cobertura alcanzable: mide el
   efecto de las aguas a conformero igualado, que es una pregunta pareada y no absoluta.
2. **Quitar todas no es la unica alternativa.** Filtrar por B-factor, por ocupancia o por
   enterramiento son politicas intermedias que este experimento no evalua. Si sale
   `QUITARLAS MEJORA`, lo que autoriza es abrir esa comparacion, no adoptar el brazo SIN.
3. **No toca ningun artefacto sellado.** Los 111 que consumen receptores con aguas siguen
   como estan; cambiar la politica seria un programa de regeneracion con su re-sellado.
4. `REC-09` quedo `INCONCLUSIVE`. Este experimento no lo relee ni depende de su lectura:
   comparte el tema y no el gate.
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
EXH = 8
NUM_MODES = 9
SEMILLAS = (42, 1, 2, 3, 4)          # las del brazo de produccion de MF-29-EMP
UMBRAL_A = 2.0
LIGANDO = "conf0.flex.pdbqt"
RESNAMES_AGUA = {"HOH", "WAT", "DOD"}


def _vina() -> str:
    return os.environ.get("REC11_VINA", "/usr/local/bin/vina")


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def _sin_aguas(texto: str) -> tuple[str, int]:
    """Devuelve el PDBQT sin ningun residuo de agua, y cuantos atomos quito."""
    fuera, quitados = [], 0
    for l in texto.splitlines():
        if l.startswith(("ATOM", "HETATM")) and l[17:20].strip().upper() in RESNAMES_AGUA:
            quitados += 1
            continue
        fuera.append(l)
    return "\n".join(fuera) + "\n", quitados


def _brazo(vina: str, rec: Path, lig: Path, centro, crystal, s2m, tmp: Path,
           pid: str, etq: str) -> Dict[str, Any]:
    import molflex as mf

    corridas, oraculo = [], None
    mejor_score, rmsd_top1 = None, None
    t0 = time.time()
    for sd in SEMILLAS:
        salida = tmp / f"{pid}_{etq}_s{sd}.pdbqt"
        cmd = [vina, "--receptor", str(rec), "--ligand", str(lig)] + _caja(centro) + [
            "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
            "--seed", str(sd), "--cpu", "1", "--out", str(salida)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok = False
        if not ok:
            corridas.append({"seed": sd, "error": "VINA_FALLO"})
            continue
        mejor_rmsd_corrida = None
        for sc, at in mf.parsear_out_vina(salida.read_text(encoding="utf-8", errors="replace")):
            c = mf.coords_pose_a_por_mol(at, s2m)
            if not c:
                continue
            v = mf.rmsd_pose_pocket(crystal, c)
            if v is None:
                continue
            if oraculo is None or v < oraculo:
                oraculo = v
            if mejor_rmsd_corrida is None or v < mejor_rmsd_corrida:
                mejor_rmsd_corrida = v
            if sc is not None and (mejor_score is None or sc < mejor_score):
                mejor_score, rmsd_top1 = sc, v
        try:
            salida.unlink()
        except OSError:
            pass
        corridas.append({"seed": sd, "rmsd_min": round(mejor_rmsd_corrida, 3)
                         if mejor_rmsd_corrida is not None else None})
    return {"corridas": corridas,
            "oraculo": round(oraculo, 3) if oraculo is not None else None,
            "cubierto": bool(oraculo is not None and oraculo <= UMBRAL_A),
            "score_top1": mejor_score,
            "rmsd_top1": round(rmsd_top1, 3) if rmsd_top1 is not None else None,
            "cpu_s": round(time.time() - t0, 1)}


def analizar(ws: Path, pid: str, estrato: str, tmp: Path) -> Dict[str, Any]:
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

    rec_sin = tmp / f"{pid}_rec_sin_aguas.pdbqt"
    texto, quitados = _sin_aguas(rec.read_text(encoding="utf-8", errors="replace"))
    rec_sin.write_text(texto, encoding="utf-8")
    out["atomos_agua_quitados"] = quitados

    v = _vina()
    out["CON"] = _brazo(v, rec, lig, centro, crystal, s2m, tmp, pid, "con")
    out["SIN"] = _brazo(v, rec_sin, lig, centro, crystal, s2m, tmp, pid, "sin")
    try:
        rec_sin.unlink()
    except OSError:
        pass

    a, b = out["CON"], out["SIN"]
    if a["oraculo"] is not None and b["oraculo"] is not None:
        out["delta_oraculo"] = round(a["oraculo"] - b["oraculo"], 3)   # >0 => SIN mejor
        out["discordante"] = a["cubierto"] != b["cubierto"]
        out["gana_SIN"] = bool(b["cubierto"] and not a["cubierto"])
        out["gana_CON"] = bool(a["cubierto"] and not b["cubierto"])
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    from estadistica_fnd04 import mcnemar_exacto, efecto_minimo_detectable

    ap = argparse.ArgumentParser(description="REC-11: aguas sobre docking de novo, pareado")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "REC-11"
    out_dir.mkdir(parents=True, exist_ok=True)

    m13 = {}
    for l in (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            m13[r["pid"]] = r.get("estrato", "RESTO")
    jobs = sorted(m13.items())
    if args.limite:
        jobs = jobs[:args.limite]

    print(f"[REC-11] {len(jobs)} complejos x 2 brazos x {len(SEMILLAS)} semillas | "
          f"exh={EXH} num_modes={NUM_MODES} | ligando {LIGANDO} fijo | workers={args.workers}",
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
                if i % 5 == 0 or r.get("discordante") or r.get("error"):
                    print(f"  [{i}/{len(jobs)}] {r['pid']} "
                          f"CON={r.get('CON',{}).get('oraculo')} "
                          f"SIN={r.get('SIN',{}).get('oraculo')} "
                          f"aguas_quitadas={r.get('atomos_agua_quitados')} "
                          f"discordante={r.get('discordante')} {r.get('error','')} "
                          f"({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "discordante" in r]
    b = sum(1 for r in ok if r["gana_SIN"])
    c = sum(1 for r in ok if r["gana_CON"])
    p = mcnemar_exacto(b, c)
    cub_con = sum(1 for r in ok if r["CON"]["cubierto"])
    cub_sin = sum(1 for r in ok if r["SIN"]["cubierto"])
    disc = ((b + c) / len(ok)) if ok else 0.0
    mde = efecto_minimo_detectable(len(ok), max(disc, 0.01)) if ok else None

    lectura = None
    if ok:
        if p < 0.05 and b > c:
            lectura = "QUITARLAS_MEJORA"
        elif p < 0.05 and c > b:
            lectura = "CONSERVARLAS_MEJORA"
        else:
            lectura = "SIN_DIFERENCIA_DETECTABLE"

    # secundario: top-1
    t1_con = sum(1 for r in ok if r["CON"].get("rmsd_top1") is not None
                 and r["CON"]["rmsd_top1"] <= UMBRAL_A)
    t1_sin = sum(1 for r in ok if r["SIN"].get("rmsd_top1") is not None
                 and r["SIN"]["rmsd_top1"] <= UMBRAL_A)
    b1 = sum(1 for r in ok if (r["SIN"].get("rmsd_top1") or 99) <= UMBRAL_A
             and (r["CON"].get("rmsd_top1") or 99) > UMBRAL_A)
    c1 = sum(1 for r in ok if (r["CON"].get("rmsd_top1") or 99) <= UMBRAL_A
             and (r["SIN"].get("rmsd_top1") or 99) > UMBRAL_A)

    metrics = {
        "experiment_id": "REC-11",
        "tipo": "intervencion pareada con regla de lectura y MDE preregistrados",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"exh": EXH, "num_modes": NUM_MODES, "semillas": list(SEMILLAS),
                   "box": BOX, "umbral_A": UMBRAL_A, "ligando": LIGANDO,
                   "variable_unica": "el receptor: con todas las aguas contra sin ninguna",
                   "resnames_agua": sorted(RESNAMES_AGUA),
                   "metrica": "rmsd_pose_pocket sin alineamiento"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "cantidad_primaria": {
            "definicion": "cobertura del oraculo pareada; b = SIN cubre y CON no, c = CON cubre y SIN no",
            "cobertura_CON": {"n": cub_con, "de": len(ok),
                              "frac": round(cub_con / len(ok), 4) if ok else None},
            "cobertura_SIN": {"n": cub_sin, "de": len(ok),
                              "frac": round(cub_sin / len(ok), 4) if ok else None},
            "b_gana_SIN": b, "c_gana_CON": c,
            "mcnemar_p_exacto": round(p, 6),
            "discordancia": round(disc, 4),
            "mde_observado_pp": round(mde * 100, 2) if mde else None,
            "lectura_preregistrada": lectura},
        "secundario_top1": {
            "cubiertos_CON": t1_con, "cubiertos_SIN": t1_sin,
            "b_gana_SIN": b1, "c_gana_CON": c1,
            "mcnemar_p_exacto": round(mcnemar_exacto(b1, c1), 6),
            "nota": "mas ruidoso que el oraculo; descriptivo, sin gate"},
        "contexto": {
            "atomos_agua_quitados_mediana": median([r["atomos_agua_quitados"] for r in ok])
            if ok else None,
            "delta_oraculo_mediano": round(median([r["delta_oraculo"] for r in ok]), 3)
            if ok else None},
        "limites_declarados": [
            "un solo conformero: mide el efecto de las aguas a conformero igualado, no la cobertura alcanzable",
            "quitar todas no es la unica alternativa; filtrar por B-factor u ocupancia no se evalua aqui",
            "no toca ningun artefacto sellado; cambiar la politica seria un programa de regeneracion",
            "no relee REC-09 ni depende de su lectura: comparte tema y no gate",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"[REC-11] LISTO n={len(ok)} CON={cub_con} SIN={cub_sin} b={b} c={c} "
          f"p={round(p,6)} MDE={round(mde*100,2) if mde else None}pp lectura={lectura} "
          f"({round(time.time()-t0)}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
