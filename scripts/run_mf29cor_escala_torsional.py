#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf29cor_escala_torsional.py — MF-29-EMP-COR: el testigo comparaba dos escalas.

Corre en el contenedor `moldesign-lab` del servidor, el mismo de `MF-13` y `MF-29-EMP`.

El defecto
----------
El testigo de `MF-29-EMP` compara `score_cristal_local` de `MF-13` contra el mejor score
del brazo masivo. Los dos numeros **no estan en la misma escala**:

  * `MF-13` puntuo el cristal como PDBQT **rigido**. Su `preparar_cristal` escribe el
    `rigid_str` de `molflex.escribir_pdbqt`, que es ROOT / atomos / ENDROOT / TORSDOF 0.
  * `MF-29-EMP` dockeo `conf0.flex.pdbqt`, **flexible**, con hasta 6 torsiones activas.

Vina normaliza la afinidad por el numero de torsiones: la energia se divide por
(1 + w_rot * N_rot). Un ligando con TORSDOF 0 no paga esa penalizacion y otro con 6 si, de
modo que el rigido puntua sistematicamente mejor **para la misma pose**. El deficit de 0.49
kcal/mol medianos que `MF-29-EMP` leyo como fallo de busqueda puede ser entero o en parte
ese artefacto de escala.

La aritmetica que motiva el experimento -y que NO lo sustituye, por eso este script existe-:
con w_rot=0.05846 y el TORSDOF real de cada complejo, la penalizacion sola predice un
deficit mediano de 1.367, y el observado es 0.491. Es decir, el artefacto por si solo
predice MAS deficit del que hay. Pero eso es un modelo de la formula de Vina, no una
medicion, y una decision de gate no se cambia con un modelo cuando medirlo cuesta minutos.

Que se mide
-----------
Repetir `MF-13` **cambiando una sola cosa**: preparar el cristal como PDBQT **flexible**
-el flex_str de la misma llamada a `molflex.escribir_pdbqt`, mismo tipado de Meeko, mismo
receptor, misma caja de 25 A, misma semilla 42- y volver a puntuarlo con `--score_only` y
`--local_only`. Asi el cristal paga la misma penalizacion torsional que el ligando dockeado
y la comparacion queda en una sola escala.

    deficit_corregido = score_min(masivo) - score_cristal_local_FLEX

Lectura preregistrada
---------------------
`f` = fraccion de los 48 donde el cristal flexible sigue ganando por mas del ruido de 0.10:

  * `f <= 0.30` -> **ARTEFACTO DE ESCALA**. El testigo no sostiene fallo de busqueda; la
    cantidad primaria de `MF-29-EMP` queda como unico instrumento valido y su lectura
    OBJETIVO se sostiene sola.
  * `f >= 0.70` -> **EL TESTIGO SOBREVIVE**. El cristal gana tambien a igual escala: la
    busqueda no llega al fondo y `MF-29-EMP` se queda INCONCLUSIVE.
  * intermedio -> **MIXTO**, se reporta la fraccion y `MF-29-EMP` se queda INCONCLUSIVE.

Gates de validez, ANTES del primario
------------------------------------
  * **G1**: el TORSDOF del cristal flexible coincide con el de `conf0.flex.pdbqt` en >=95%
    de los complejos. Si no coincide, no son la misma molecula preparada igual y la
    comparacion no es a igual escala: el experimento no se lee.
  * **G2**: la deriva de `--local_only` respecto del cristal se mantiene por debajo de
    2.0 A medianos. Con torsiones libres el relajado puede alejarse mas que el rigido de
    `MF-13` -que derivo 0.32 A-; si se va, deja de ser el cristal y el numero no mide lo
    que dice medir.

Limites declarados ANTES de correr
----------------------------------
1. Esto **no reabre la cantidad primaria** de `MF-29-EMP`: la fraccion masivo-vs-produccion
   es la que es y no la toca ningun resultado de aqui. Lo unico que este experimento puede
   cambiar es si el testigo era o no un instrumento valido.
2. **No certifica optimalidad global.** `MF-29` sigue ABIERTO pase lo que pase aqui.
3. El brazo masivo de `1mmr` y `1nm6` expiro, asi que la cohorte es de 48 y no de 50, la
   misma de la lectura de `MF-29-EMP`.
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
DELTA_RUIDO = 0.10      # el mismo de MF-29-EMP
G1_MIN = 0.95
G2_MAX_DERIVA = 2.0


def _vina_bin() -> str:
    return os.environ.get("MF29COR_VINA", "/usr/local/bin/vina")


def _correr_vina(args: List[str], timeout: int) -> Optional[str]:
    try:
        p = subprocess.run([_vina_bin()] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return p.stdout if p.returncode == 0 else None


def _score_de_salida(texto: str) -> Optional[float]:
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


def _torsdof(texto: str) -> Optional[int]:
    for l in texto.splitlines():
        if l.startswith("TORSDOF"):
            try:
                return int(l.split()[1])
            except (IndexError, ValueError):
                return None
    return None


def preparar_cristal_flex(ws: Path, pid: str, destino: Path) -> Optional[dict]:
    """Identico a MF-13.preparar_cristal salvo que escribe el FLEXIBLE, no el rigido."""
    import molflex as mf
    from meeko import MoleculePreparation
    from rdkit import Chem

    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        return None
    mh = Chem.AddHs(crystal, addCoords=True)
    setups = MoleculePreparation().prepare(mh, conformer_id=0)
    _rigid, flex, mapa, _err = mf.escribir_pdbqt(setups[0])
    if not flex or not mapa:
        return None
    destino.write_text(flex, encoding="utf-8")
    return {"mapa": mapa, "crystal": crystal, "torsdof": _torsdof(flex)}


def analizar(ws: Path, pid: str, estrato: str, ref: Dict[str, Any], tmp: Path) -> Dict[str, Any]:
    import molflex as mf

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato,
                           "score_masivo": ref["score_masivo"],
                           "score_cristal_local_rigido": ref["score_cristal_local_rigido"],
                           "torsdof_conf0": ref["torsdof_conf0"]}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen = w / "rec.pdbqt", w / "center.json"
    if not rec.exists() or not cen.exists():
        out["error"] = "SIN_RECEPTOR_O_CAJA"
        return out
    centro = json.loads(cen.read_text(encoding="utf-8"))
    lig = tmp / f"{pid}_cristal_flex.pdbqt"
    try:
        prep = preparar_cristal_flex(ws, pid, lig)
    except Exception as ex:
        out["error"] = f"MEEKO:{type(ex).__name__}:{str(ex)[-120:]}"
        return out
    if prep is None:
        out["error"] = "PREP_CRISTAL_FALLO"
        return out

    out["torsdof_cristal_flex"] = prep["torsdof"]
    out["torsdof_coincide"] = bool(prep["torsdof"] is not None
                                   and prep["torsdof"] == ref["torsdof_conf0"])

    base = ["--receptor", str(rec), "--ligand", str(lig)] + _args_caja(centro) + \
           ["--seed", str(SEED), "--cpu", "1"]

    s = _correr_vina(base + ["--score_only"], timeout=120)
    out["score_cristal_flex"] = _score_de_salida(s) if s else None

    salida = tmp / f"{pid}_local_flex.pdbqt"
    s2 = _correr_vina(base + ["--local_only", "--out", str(salida)], timeout=300)
    if s2 and salida.exists():
        modelos = mf.parsear_out_vina(salida.read_text(encoding="utf-8", errors="replace"))
        if modelos:
            sc, at = modelos[0]
            if sc is None:   # --local_only no escribe REMARK VINA RESULT: se re-puntua
                s3 = _correr_vina(["--receptor", str(rec), "--ligand", str(salida)]
                                  + _args_caja(centro)
                                  + ["--seed", str(SEED), "--cpu", "1", "--score_only"],
                                  timeout=120)
                sc = _score_de_salida(s3) if s3 else None
            out["score_cristal_local_flex"] = float(sc) if sc is not None else None
            try:
                m = prep["mapa"]
                s2m = {int(k): int(v) for k, v in (m if isinstance(m, list) else m.items())}
                coords = mf.coords_pose_a_por_mol(at, s2m)
                out["rmsd_deriva_local"] = (round(mf.rmsd_pose_pocket(prep["crystal"], coords), 3)
                                            if coords else None)
            except Exception:
                out["rmsd_deriva_local"] = None

    a, b = out.get("score_cristal_local_flex"), ref["score_masivo"]
    if a is not None and b is not None:
        out["deficit_corregido"] = round(b - a, 3)          # >0 => el cristal flex gana
        out["cristal_flex_gana"] = bool(a < b - DELTA_RUIDO)
        r = ref["score_cristal_local_rigido"]
        if r is not None:
            out["salto_de_escala"] = round(a - r, 3)        # >0 => el flex puntua peor, como se espera
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-29-EMP-COR: el testigo a igual escala torsional")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "MF-29-EMP-COR"
    out_dir.mkdir(parents=True, exist_ok=True)

    testigo = json.loads((art / "MF-29-EMP" / "testigo_mf13.json").read_text(encoding="utf-8"))
    emp = {}
    for l in (art / "MF-29-EMP" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            emp[r["pid"]] = r

    jobs = []
    for f in testigo["per_complex"]:
        r = emp[f["pid"]]
        jobs.append((f["pid"], f["estrato"], {
            "score_masivo": f["score_masivo"],
            "score_cristal_local_rigido": f["score_cristal_local"],
            "torsdof_conf0": r.get("torsdof"),
        }))
    jobs.sort(key=lambda x: x[0])
    if args.limite:
        jobs = jobs[:args.limite]

    print(f"[MF-29-EMP-COR] {len(jobs)} complejos | cristal FLEXIBLE, misma caja/semilla que MF-13",
          flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, ws, pid, est, ref, tmp): pid for pid, est, ref in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                filas.append(fut.result())
                r = filas[-1]
                print(f"  [{i}/{len(jobs)}] {r['pid']} flex={r.get('score_cristal_local_flex')} "
                      f"rigido={r.get('score_cristal_local_rigido')} "
                      f"masivo={r.get('score_masivo')} def_corr={r.get('deficit_corregido')} "
                      f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "cristal_flex_gana" in r]
    coincide = [r for r in filas if r.get("torsdof_coincide")]
    g1 = (len(coincide) / len(filas)) if filas else 0.0
    derivas = [r["rmsd_deriva_local"] for r in ok if r.get("rmsd_deriva_local") is not None]
    g2 = median(derivas) if derivas else None

    n_gana = sum(1 for r in ok if r["cristal_flex_gana"])
    frac = (n_gana / len(ok)) if ok else None
    lectura = None
    if frac is not None:
        lectura = ("ARTEFACTO_DE_ESCALA" if frac <= 0.30 else
                   "EL_TESTIGO_SOBREVIVE" if frac >= 0.70 else "MIXTO")
    gates_ok = (g1 >= G1_MIN) and (g2 is not None and g2 <= G2_MAX_DERIVA)

    saltos = [r["salto_de_escala"] for r in ok if r.get("salto_de_escala") is not None]
    defs = [r["deficit_corregido"] for r in ok]
    metrics = {
        "experiment_id": "MF-29-EMP-COR",
        "tipo": "corrigendum del testigo de MF-29-EMP con regla de lectura preregistrada",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"box": BOX, "seed": SEED, "delta_ruido_kcal": DELTA_RUIDO,
                   "cambio_unico": "el cristal se prepara FLEXIBLE (flex_str) y no RIGIDO (rigid_str, TORSDOF 0) como en MF-13",
                   "receptor_y_caja": "los mismos de MF-13 y del docking v2"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "gates_validez": {
            "G1_torsdof_coincide_con_conf0": {"fraccion": round(g1, 4), "minimo": G1_MIN,
                                              "pasa": bool(g1 >= G1_MIN)},
            "G2_deriva_local_mediana_A": {"valor": g2, "maximo": G2_MAX_DERIVA,
                                          "pasa": bool(g2 is not None and g2 <= G2_MAX_DERIVA)},
            "ambos_pasan": bool(gates_ok),
        },
        "cantidad_primaria": {
            "definicion": "fraccion de complejos donde score_cristal_local_FLEX < score_min(masivo) - 0.10",
            "n_gana": n_gana, "de": len(ok),
            "fraccion": round(frac, 4) if frac is not None else None,
            "lectura_preregistrada": lectura,
        },
        "contexto": {
            "deficit_corregido_mediano": round(median(defs), 3) if defs else None,
            "deficit_original_mediano_contra_rigido": testigo["cantidad"]["deficit_mediano_global"],
            "salto_de_escala_mediano": round(median(saltos), 3) if saltos else None,
            "salto_de_escala_definicion": "score_cristal_local_FLEX - score_cristal_local_RIGIDO; >0 mide cuanto del deficit original era penalizacion torsional",
        },
        "limites_declarados": [
            "no reabre la cantidad primaria de MF-29-EMP, que es masivo vs produccion",
            "no certifica optimalidad global; MF-29 sigue ABIERTO",
            "cohorte de 48 y no 50: el brazo masivo de 1mmr y 1nm6 expiro",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"[MF-29-EMP-COR] LISTO n={len(ok)} G1={round(g1,4)} G2={g2} "
          f"frac={frac} lectura={lectura} gates_ok={gates_ok} ({round(time.time()-t0)}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
