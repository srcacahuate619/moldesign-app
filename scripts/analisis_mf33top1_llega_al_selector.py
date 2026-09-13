#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_mf33top1_llega_al_selector.py — MF-33-TOP1: ¿la ganancia llega al usuario?

Sin computo de docking. Lee poses que ya estan en disco.

El agujero que cierra
---------------------
`MF-33` y `MF-33-A3` miden **cobertura del oraculo**: si la pose buena **existe** entre las
que el brazo conserva. Eso no es lo que un usuario recibe. `MF-09` ya midio la otra mitad
sobre el estrato dificil y el numero es duro:

    existe pose <=2 A   3/33        top-1 acierta   0/33
    acierta en top-5    1/33        en top-20       2/33

Es decir: **el techo nunca fue la restriccion activa para el usuario**. Un revisor razonable
preguntara si subir el techo de 1/33 a 26/33 mueve algo de lo que el usuario ve, y hoy no
esta medido: `MF-33` registro `rmsd_min` por brazo -oraculo- y no el top-1.

Este analisis mide lo que falta, con lo que hay.

Que se compara
--------------
Los `conf<i>.out.pdbqt` del protocolo congelado estan en disco para **los 116** de train, con
sus scores (`REMARK VINA RESULT`) y 9 modelos por corrida. Eso permite construir dos brazos
pareados **sin recomputar nada**:

    SINGLE     las 9 poses de `conf0.out.pdbqt`
    ENSEMBLE   las K x 9 poses de todos los `conf<i>.out.pdbqt`

y, sobre cada uno, las tres cantidades que separan generacion de seleccion:

    top1       rmsd_pose_pocket de la pose de MEJOR SCORE
    top5       el mejor rmsd entre las 5 de mejor score
    oraculo    el mejor rmsd entre todas

LIMITACION CENTRAL, DECLARADA ARRIBA DEL TODO
----------------------------------------------
**Estas poses son del protocolo RIGIDO.** `molflex.docking_conformero` pasa a `--ligand` el
`conf<i>.rigid.pdbqt`, y `RC-F0-V2-EXT` ya midio que el 93.9% del conjunto v2 viene de ahi.

Las poses **flexibles** del brazo B de `MF-33` **no existen**: `run_mf28_roadmap.py` las
escribio en un `TemporaryDirectory` y se borraron al terminar. Recuperarlas exige re-correr
el brazo con retencion de poses -~42.6 CPU-h-, y eso se prerregistra aparte.

Por tanto este analisis **no mide el brazo del paper**. Mide si el **mecanismo** -mas
conformeros, mejor pool- llega al selector, en el unico protocolo cuyas poses sobrevivieron.
Es evidencia sobre el cuello de botella, no sobre la magnitud del efecto flexible.

Endpoint fisico desde el principio
----------------------------------
Se anade `pb_valid_fisica` de `posebusters_metrica` sobre la pose **top-1 de cada brazo**.
Un top-1 con RMSD bueno y fisicamente invalido no es un acierto, y esa distincion no existia
en el programa hasta hoy. Va por familias implicito: el modulo devuelve que checks fallan.

Lectura preregistrada
---------------------
McNemar exacto pareado sobre «acierta <=2 A», por separado en `top1`, `top5` y `oraculo`.

  * **EL CUELLO SE DESPLAZA A LA SELECCION** si el ensemble mejora el **oraculo** con
    p < 0.05 y **no** mejora `top1` (p >= 0.05). La generacion deja de ser el limite y pasa
    a serlo el selector.
  * **LA VENTAJA LLEGA AL USUARIO** si mejora **ambos** con p < 0.05.
  * **SIN EFECTO EN ESTE PROTOCOLO** si no mejora el oraculo. Con el techo rigido que
    `MF-33` midio en 1/33 para COLOCACION, es un desenlace posible y no seria sorprendente.

Se reporta ademas el **margen de seleccion**: cuantos complejos tienen pose buena disponible
y no la entregan. Es la cantidad que el programa deberia estar optimizando si la lectura sale
la primera.

Limites declarados ANTES de correr
----------------------------------
1. Protocolo **rigido**, no flexible. Ver arriba. No extrapola a la magnitud del brazo B.
2. Se ordena por **score de Vina, sin rescoring**. La cartera RS mide eso aparte; meterlo
   aqui confundiria generacion, seleccion y funcion de puntuacion en un solo numero.
3. `SINGLE` usa `conf0` **por indice y no por calidad**: elegir el mejor conformero seria
   informacion de oraculo que en produccion no existe. Es la misma convencion del brazo A de
   `MF-33`.
4. El ensemble selecciona sobre un pool K veces mayor. **Eso no es un confundido: es el
   fenomeno.** La pregunta es precisamente si un pool mayor se traduce en mejor entrega.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

UMBRAL_A = 2.0
RE_OUT = re.compile(r"conf(\d+)\.out\.pdbqt$")


def _poses_de_archivo(texto: str, s2m: Dict[int, int], crystal, mf) -> List[Tuple[float, float]]:
    """[(score, rmsd_pose_pocket)] de un .out.pdbqt."""
    salida = []
    for score, atomos in mf.parsear_out_vina(texto):
        if score is None:
            continue
        c = mf.coords_pose_a_por_mol(atomos, s2m)
        if not c:
            continue
        r = mf.rmsd_pose_pocket(crystal, c)
        if r is not None:
            salida.append((float(score), float(r)))
    return salida


def _metricas(poses: List[Tuple[float, float]]) -> Dict[str, Any]:
    """top1, top5 y oraculo de una lista [(score, rmsd)]. Menor score = mejor."""
    if not poses:
        return {"n_poses": 0, "top1": None, "top5": None, "oraculo": None}
    orden = sorted(poses, key=lambda p: p[0])
    return {"n_poses": len(poses),
            "top1": round(orden[0][1], 3),
            "top5": round(min(p[1] for p in orden[:5]), 3),
            "oraculo": round(min(p[1] for p in poses), 3),
            "score_top1": round(orden[0][0], 3)}


def main() -> int:
    from estadistica_fnd04 import mcnemar_exacto
    import molflex as mf
    import posebusters_metrica as pbm
    from rdkit import Chem

    ap = argparse.ArgumentParser(description="MF-33-TOP1: la ganancia del ensemble, ¿llega al selector?")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--sin-posebusters", action="store_true")
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-33-TOP1"
    out_dir.mkdir(parents=True, exist_ok=True)

    estratos = {}
    for l in (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            estratos[r["pid"]] = r.get("estrato", "RESTO")
    pids = sorted(estratos)
    if args.limite:
        pids = pids[:args.limite]

    filas: List[Dict[str, Any]] = []
    for i, pid in enumerate(pids, 1):
        w = ws / "data" / "molflex_train_v2" / pid / pid
        f: Dict[str, Any] = {"pid": pid, "estrato": estratos[pid]}
        idx = w / "index_map.json"
        sdf = ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
        if not idx.exists() or not sdf.exists():
            f["error"] = "SIN_MATERIAL"
            filas.append(f); continue
        crystal = mf.leer_ligando(sdf)
        if crystal is None:
            f["error"] = "SDF_ILEGIBLE"
            filas.append(f); continue
        s2m = {int(s): int(m) for s, m in json.loads(idx.read_text(encoding="utf-8"))}

        archivos = sorted([p for p in w.glob("conf*.out.pdbqt") if RE_OUT.search(p.name)],
                          key=lambda p: int(RE_OUT.search(p.name).group(1)))
        if not archivos:
            f["error"] = "SIN_POSES"
            filas.append(f); continue

        por_conf: Dict[int, List[Tuple[float, float]]] = {}
        for p in archivos:
            k = int(RE_OUT.search(p.name).group(1))
            por_conf[k] = _poses_de_archivo(p.read_text(encoding="utf-8", errors="replace"),
                                            s2m, crystal, mf)
        f["K"] = len(archivos)
        single = por_conf.get(0, [])
        ensemble = [pp for v in por_conf.values() for pp in v]
        f["SINGLE"] = _metricas(single)
        f["ENSEMBLE"] = _metricas(ensemble)
        for brazo in ("SINGLE", "ENSEMBLE"):
            m = f[brazo]
            for k in ("top1", "top5", "oraculo"):
                m[f"acierta_{k}"] = bool(m[k] is not None and m[k] <= UMBRAL_A)
            m["margen_de_seleccion"] = bool(m.get("acierta_oraculo") and not m.get("acierta_top1"))

        # ── endpoint fisico sobre el top-1 de cada brazo ──
        if not args.sin_posebusters and pbm.disponible():
            prot = ws / "data" / "pdbbind" / pid / f"{pid}_protein.pdb"
            if prot.exists():
                mh = pbm.mol_con_hidrogenos(crystal)
                for brazo, poses in (("SINGLE", single), ("ENSEMBLE", ensemble)):
                    if not poses:
                        continue
                    mejor_score = min(p[0] for p in poses)
                    coords = None
                    for p in archivos:
                        for score, atomos in mf.parsear_out_vina(
                                p.read_text(encoding="utf-8", errors="replace")):
                            if score is None or abs(float(score) - mejor_score) > 1e-6:
                                continue
                            if brazo == "SINGLE" and RE_OUT.search(p.name).group(1) != "0":
                                continue
                            coords = mf.coords_pose_a_por_mol(atomos, s2m)
                            break
                        if coords:
                            break
                    if coords:
                        r = pbm.evaluar_pose(pbm.pose_a_mol(mh, coords), mh, prot)
                        f[brazo]["pb_valid_fisica"] = r.get("pb_valid_fisica")
                        f[brazo]["pb_checks_que_fallan"] = r.get("checks_que_fallan")
        filas.append(f)
        if i % 20 == 0:
            print(f"  [{i}/{len(pids)}] {pid}", flush=True)

    ok = [f for f in filas if "SINGLE" in f and f["SINGLE"]["n_poses"] > 0]

    def _pareado(campo: str, sub: List[Dict[str, Any]]) -> Dict[str, Any]:
        b = sum(1 for f in sub if f["ENSEMBLE"][f"acierta_{campo}"] and not f["SINGLE"][f"acierta_{campo}"])
        c = sum(1 for f in sub if f["SINGLE"][f"acierta_{campo}"] and not f["ENSEMBLE"][f"acierta_{campo}"])
        ns = sum(1 for f in sub if f["SINGLE"][f"acierta_{campo}"])
        ne = sum(1 for f in sub if f["ENSEMBLE"][f"acierta_{campo}"])
        return {"single": ns, "ensemble": ne, "de": len(sub),
                "b_gana_ensemble": b, "c_gana_single": c,
                "mcnemar_p": round(mcnemar_exacto(b, c), 6),
                "delta_pp": round((ne - ns) / len(sub) * 100, 2) if sub else None}

    def _bloque(sub, etq):
        r = {"etiqueta": etq, "n": len(sub)}
        for campo in ("top1", "top5", "oraculo"):
            r[campo] = _pareado(campo, sub)
        r["margen_de_seleccion_ensemble"] = sum(1 for f in sub if f["ENSEMBLE"]["margen_de_seleccion"])
        r["margen_de_seleccion_single"] = sum(1 for f in sub if f["SINGLE"]["margen_de_seleccion"])
        return r

    glob = _bloque(ok, "TODOS")
    col = _bloque([f for f in ok if f["estrato"] == "COLOCACION"], "COLOCACION")

    p_or, p_t1 = glob["oraculo"]["mcnemar_p"], glob["top1"]["mcnemar_p"]
    mejora_or = p_or < 0.05 and glob["oraculo"]["b_gana_ensemble"] > glob["oraculo"]["c_gana_single"]
    mejora_t1 = p_t1 < 0.05 and glob["top1"]["b_gana_ensemble"] > glob["top1"]["c_gana_single"]
    lectura = ("LA_VENTAJA_LLEGA_AL_USUARIO" if (mejora_or and mejora_t1)
               else "EL_CUELLO_SE_DESPLAZA_A_LA_SELECCION" if mejora_or
               else "SIN_EFECTO_EN_ESTE_PROTOCOLO")

    pbs = {}
    for brazo in ("SINGLE", "ENSEMBLE"):
        ev = [f for f in ok if f[brazo].get("pb_valid_fisica") is not None]
        val = [f for f in ev if f[brazo]["pb_valid_fisica"]]
        pbs[brazo] = {"n_evaluadas": len(ev), "n_validas": len(val),
                      "tasa": round(len(val) / len(ev), 4) if ev else None}

    salida = {
        "analisis_id": "MF-33-TOP1",
        "tipo": "medicion pareada con regla de lectura preregistrada, sin computo de docking",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "PROTOCOLO": "RIGIDO. Las poses flexibles del brazo B de MF-33 no existen: se escribieron "
                     "en un TemporaryDirectory. Esto NO mide el brazo del paper; mide si el "
                     "mecanismo llega al selector en el protocolo cuyas poses sobrevivieron.",
        "n_complejos": len(filas), "n_ok": len(ok),
        "TODOS": glob, "COLOCACION": col,
        "lectura_preregistrada": lectura,
        "validez_fisica_del_top1": pbs,
        "referencia_MF09": {"existe_pose_buena": "3/33", "top1_acierta": "0/33",
                            "top5": "1/33", "top20": "2/33",
                            "nota": "medido sobre el conjunto v2 en el estrato dificil"},
        "limites_declarados": [
            "protocolo rigido, no flexible: no extrapola a la magnitud del brazo B",
            "se ordena por score de Vina sin rescoring; la cartera RS mide eso aparte",
            "SINGLE usa conf0 por indice y no por calidad, como el brazo A de MF-33",
            "el ensemble selecciona sobre un pool K veces mayor: eso es el fenomeno, no un confundido",
        ],
        "per_complex": filas,
    }
    (out_dir / "metrics.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in filas:
            fh.write(json.dumps(f, ensure_ascii=False) + "\n")

    print(f"\n[MF-33-TOP1] n={len(ok)} | protocolo RIGIDO")
    for etq, blq in (("TODOS", glob), ("COLOCACION", col)):
        print(f"  {etq} (n={blq['n']}):")
        for campo in ("oraculo", "top5", "top1"):
            d = blq[campo]
            print(f"    {campo:8s} single={d['single']:3d} ensemble={d['ensemble']:3d} "
                  f"delta={d['delta_pp']:+6.2f}pp  b={d['b_gana_ensemble']} c={d['c_gana_single']} "
                  f"p={d['mcnemar_p']}")
        print(f"    margen de seleccion (tiene pose buena y no la entrega): "
              f"single={blq['margen_de_seleccion_single']} ensemble={blq['margen_de_seleccion_ensemble']}")
    print(f"  LECTURA: {lectura}")
    print(f"  validez fisica del top-1: single={pbs['SINGLE']['tasa']} ensemble={pbs['ENSEMBLE']['tasa']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
