#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MF-33-PB: validez fisica de las poses del brazo flexible.

Cierra el claim `C10` del docs/52, que estaba marcado **bloqueado porque las poses se
borraron**. Ya no lo estan: `MF-33-B-RET-R1` retuvo 8215 poses en 969 PDBQT crudos sobre 48
complejos. Aquel R1 fallo su gate tecnico por un dock, pero su retencion forense es
exactamente el material que este claim necesitaba.

CONFIGURACION `redock`, NO `dock`, Y LA RAZON IMPORTA. Aqui SI existe el ligando
cristalografico, asi que se usa la bateria completa con verdad de terreno. Es ademas la
misma configuracion con la que `MF-33-TOP1` midio 8.62% / 15.52% sobre el protocolo
RIGIDO. Mezclar `dock` y `redock` produciria numeros que parecen comparables y no lo son,
que es el error de escala que costo una retractacion en `MF-29-EMP-COR`.

QUE SE COMPARA. Por complejo, dos brazos que salen del MISMO artefacto:
  - SINGLE   : las poses del conformero 0;
  - ENSEMBLE : todas las poses, de todos los conformeros.
Es un pareado perfecto: mismo complejo, mismo receptor, mismo cristal, misma corrida.

ORDEN DE EVALUACION DELIBERADO. Dentro de cada complejo se evaluan primero los top-1 y
top-5 de cada brazo, que son las cantidades con gate, y despues el resto. Si la corrida se
interrumpe -paso hoy mismo con R1- los complejos completados siguen respondiendo la
pregunta primaria.

CORRECCION DEL 2026-08-23, ANTES DE PRODUCIR NINGUNA LECTURA. La primera version llamaba a
PoseBusters por su cuenta y tenia DOS defectos que la prueba tecnica -`--limite`, que por
contrato nunca produce decision- destapo. El primero: la llamada fallaba entera, 261 de 261
poses con RuntimeError, porque la API quiere argumentos posicionales, la proteina como Path
y el cristal CON hidrogenos. El segundo y mas grave: contaba el check `rmsd_` del config
`redock` como si fuera un control fisico, lo que habria convertido "validez fisica" en
"valida Y ADEMAS acertada" -exactamente lo que el gate prohibe leer-. El modulo sellado
`posebusters_metrica.py` ya resolvia las dos cosas y las documentaba en sus lineas 101-108;
esta version LO REUSA en lugar de reimplementarlo, que es la regla del docs/49 seccion 17
que la primera version se salto. **No se leyo ningun resultado con la version defectuosa.**
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

ORIGEN_ID = "MF-33-B-RET-R1"
UMBRAL_A = 2.0
TOP_K_SECUNDARIO = 5


def _receptor_pdb(rec_pdbqt: Path, destino: Path) -> Path:
    """PoseBusters no lee PDBQT. Truncar a 66 columnas da un PDB equivalente."""
    if destino.exists():
        return destino
    lineas = [l[:66].rstrip() for l in
              rec_pdbqt.read_text(encoding="utf-8", errors="replace").splitlines()
              if l.startswith(("ATOM", "HETATM"))]
    destino.write_text("\n".join(lineas) + "\nEND\n", encoding="utf-8")
    return destino


def _mol_de_pose(pose_atoms, crystal_mh, s2m):
    """La pose como molecula, delegando en el modulo sellado de PoseBusters.

    `posebusters_metrica.pose_a_mol` copia el cristal CON hidrogenos y le pone las
    coordenadas de la pose por indice de atomo. Reusarlo -en vez de re-perceptualizar desde
    el PDBQT- conserva ordenes de enlace y aromaticidad, sin los cuales los controles
    intramoleculares no valen nada.
    """
    import molflex as mf
    import posebusters_metrica as pbm

    coords = mf.coords_pose_a_por_mol(pose_atoms, s2m)
    if not coords:
        return None
    return pbm.pose_a_mol(crystal_mh, coords)


def analizar(ws_text: str, origen_text: str, pid: str, estrato: str,
             out_text: str) -> Dict[str, Any]:
    import molflex as mf
    import posebusters_metrica as pbm
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")

    ws, origen, out_dir = Path(ws_text), Path(origen_text), Path(out_text)
    t0 = time.time()
    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "poses": []}

    w = ws / "data" / "molflex_train_v2" / pid / pid
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(a): int(b) for a, b in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
    crystal_mh = pbm.mol_con_hidrogenos(crystal)

    tmp = out_dir / "_rec"
    tmp.mkdir(parents=True, exist_ok=True)
    rec = _receptor_pdb(w / "rec.pdbqt", tmp / f"{pid}.pdb")

    registros = json.loads((origen / "per_pose" / f"{pid}.json").read_text(encoding="utf-8"))
    if not registros:
        out["error"] = "SIN_POSES"
        return out

    def clave(r):
        return (r["score"], r["conformer"], r["model_idx"])

    single = sorted([r for r in registros if r["conformer"] == 0], key=clave)
    ensemble = sorted(registros, key=clave)
    # Las cantidades con gate primero (ver docstring).
    prioritarias = {r["identity"] for r in single[:TOP_K_SECUNDARIO]}
    prioritarias |= {r["identity"] for r in ensemble[:TOP_K_SECUNDARIO]}
    orden = ([r for r in ensemble if r["identity"] in prioritarias]
             + [r for r in ensemble if r["identity"] not in prioritarias])

    cache_raw: Dict[str, list] = {}
    for r in orden:
        ruta = origen / r["raw_pdbqt"]
        if r["raw_pdbqt"] not in cache_raw:
            cache_raw[r["raw_pdbqt"]] = mf.parsear_out_vina(
                ruta.read_text(encoding="utf-8", errors="replace"))
        parsed = cache_raw[r["raw_pdbqt"]]
        if r["model_idx"] >= len(parsed):
            out["poses"].append({"identity": r["identity"], "pb_valida": None,
                                 "motivo": "MODELO_AUSENTE"})
            continue
        mol = _mol_de_pose(parsed[r["model_idx"]][1], crystal_mh, s2m)
        if mol is None:
            out["poses"].append({"identity": r["identity"], "pb_valida": None,
                                 "motivo": "MAPEO_FALLIDO"})
            continue
        # El modulo sellado ya SEPARA el check `rmsd_` de los controles fisicos: mezclarlos
        # convertiria validez fisica en acierto de docking, que el gate prohibe.
        res = pbm.evaluar_pose(mol, crystal_mh, rec, config="redock")
        if res.get("pb_valid_fisica") is None:
            out["poses"].append({"identity": r["identity"], "pb_valida": None,
                                 "motivo": res.get("motivo", "sin_motivo")})
            continue
        out["poses"].append({
            "identity": r["identity"], "conformer": r["conformer"],
            "model_idx": r["model_idx"], "score": r["score"],
            "rmsd_pose_pocket": r["rmsd_pose_pocket"],
            "pb_valida": bool(res["pb_valid_fisica"]),
            "pb_rmsd_ok": res.get("pb_rmsd_ok"),
            "checks_que_fallan": res.get("checks_que_fallan") or [],
            "n_checks_fisicos": res.get("n_checks_fisicos"),
        })

    por_id = {p["identity"]: p for p in out["poses"]}

    def bloque(pool: List[Dict[str, Any]]) -> Dict[str, Any]:
        top1 = por_id.get(pool[0]["identity"]) if pool else None
        topk = [por_id.get(r["identity"]) for r in pool[:TOP_K_SECUNDARIO]]
        topk = [x for x in topk if x is not None]
        return {
            "n_poses": len(pool),
            "top1_valida": None if top1 is None else top1.get("pb_valida"),
            "top1_rmsd": None if top1 is None else top1.get("rmsd_pose_pocket"),
            "top5_alguna_valida": (None if not topk
                                   else any(x.get("pb_valida") for x in topk)),
            "n_validas": sum(1 for x in out["poses"]
                             if x.get("pb_valida") and x["identity"] in
                             {r["identity"] for r in pool}),
        }

    out["SINGLE"], out["ENSEMBLE"] = bloque(single), bloque(ensemble)
    out["duration_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    from estadistica_fnd04 import mcnemar_exacto, efecto_minimo_detectable

    ap = argparse.ArgumentParser(description="MF-33-PB: validez fisica del brazo flexible")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limite", type=int, default=None,
                    help="solo prueba tecnica; nunca produce decision")
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    origen = art / ORIGEN_ID
    out_dir = art / "MF-33-PB"
    (out_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

    estrato = {}
    for l in (art / "MF-33" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            estrato[r["pid"]] = r.get("estrato", "RESTO")
    jobs = sorted((p.stem, estrato.get(p.stem, "RESTO"))
                  for p in (origen / "per_pose").glob("*.json"))
    if args.limite:
        jobs = jobs[:args.limite]

    # `*.poses.json` NO cuenta como complejo hecho: su `.stem` es `<pid>.poses`.
    hechos = {p.stem for p in (out_dir / "checkpoints").glob("*.json")
              if not p.name.endswith(".poses.json")}
    pend = [(p, e) for p, e in jobs if p not in hechos]
    print(f"[MF-33-PB] total={len(jobs)} reanuda={len(hechos)} pendientes={len(pend)} "
          f"workers={args.workers}", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(analizar, str(ws), str(origen), p, e, str(out_dir)): p
                for p, e in pend}
        for n, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            poses = r.pop("poses")
            (out_dir / "checkpoints" / f"{r['pid']}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
            (out_dir / "checkpoints" / f"{r['pid']}.poses.json").write_text(
                json.dumps(poses, ensure_ascii=False), encoding="utf-8", newline="\n")
            print(f"  [{n}/{len(pend)}] {r['pid']} single_top1={r.get('SINGLE',{}).get('top1_valida')} "
                  f"ens_top1={r.get('ENSEMBLE',{}).get('top1_valida')} "
                  f"poses={len(poses)} ({r.get('duration_s')}s)", flush=True)

    for p in (out_dir / "checkpoints").glob("*.json"):
        if p.name.endswith(".poses.json"):
            continue
        filas.append(json.loads(p.read_text(encoding="utf-8")))
    filas.sort(key=lambda x: x["pid"])
    ok = [f for f in filas if "SINGLE" in f and f["SINGLE"]["top1_valida"] is not None
          and f["ENSEMBLE"]["top1_valida"] is not None]

    b = sum(1 for f in ok if f["ENSEMBLE"]["top1_valida"] and not f["SINGLE"]["top1_valida"])
    c = sum(1 for f in ok if f["SINGLE"]["top1_valida"] and not f["ENSEMBLE"]["top1_valida"])
    n = len(ok)
    disc = round((b + c) / n, 4) if n else None
    p_val = round(mcnemar_exacto(b, c), 6) if n else None
    if args.limite:
        lectura = "NO_LEER_GATES_TECNICOS"
    elif p_val is not None and p_val < 0.05 and b > c:
        lectura = "EL_ENSEMBLE_ENTREGA_MAS_VALIDO"
    elif p_val is not None and p_val < 0.05 and c > b:
        lectura = "EL_ENSEMBLE_ENTREGA_MENOS_VALIDO"
    else:
        lectura = "SIN_DIFERENCIA_DETECTABLE"

    from collections import Counter
    checks = Counter()
    total_poses = validas = 0
    for p in (out_dir / "checkpoints").glob("*.poses.json"):
        for x in json.loads(p.read_text(encoding="utf-8")):
            if x.get("pb_valida") is None:
                continue
            total_poses += 1
            validas += bool(x["pb_valida"])
            checks.update(x.get("checks_que_fallan") or [])

    metrics = {
        "experiment_id": "MF-33-PB",
        "tipo": "validez fisica pareada sobre poses retenidas; gate y MDE preregistrados",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {"posebusters_config": "redock", "umbral_A": UMBRAL_A,
                   "origen_de_las_poses": ORIGEN_ID,
                   "nota_config": ("redock usa la verdad de terreno y es la misma "
                                   "configuracion de MF-33-TOP1; NO es comparable con la "
                                   "configuracion dock que usa produccion")},
        "n_complejos": len(filas), "n_ok": n,
        "cantidad_primaria": {
            "definicion": "top-1 que pasa PoseBusters, pareado por complejo",
            "single_validos": sum(1 for f in ok if f["SINGLE"]["top1_valida"]),
            "ensemble_validos": sum(1 for f in ok if f["ENSEMBLE"]["top1_valida"]),
            "de": n, "b_gana_ensemble": b, "c_gana_single": c,
            "mcnemar_p_exacto": p_val, "discordancia": disc,
            "mde_observado_pp": (round(efecto_minimo_detectable(n, disc) * 100, 2)
                                 if n and disc else None),
            "lectura_preregistrada": lectura},
        "secundario_descriptivo": {
            "top5_alguna_valida_single": sum(1 for f in ok if f["SINGLE"]["top5_alguna_valida"]),
            "top5_alguna_valida_ensemble": sum(1 for f in ok if f["ENSEMBLE"]["top5_alguna_valida"]),
            "poses_evaluadas": total_poses, "poses_validas": validas,
            "tasa_del_conjunto": round(validas / total_poses, 4) if total_poses else None,
            "checks_que_mas_fallan": checks.most_common(10)},
        "limites_declarados": [
            "las poses vienen de MF-33-B-RET-R1, cuyo G0 fallo por un dock; la validez fisica es propiedad de la pose y no de la completitud de la corrida, pero se declara",
            "47 de los 48 complejos tienen poses byte-identicas a las que tendra MF-33-B-RET-R2; 1afl cambiara y habra que recalcularlo",
            "la tasa NO es comparable con el 8.62/15.52% de MF-33-TOP1: aquello fue sobre el protocolo RIGIDO y sobre 116, esto sobre el flexible y sobre 48",
            "no mide docking ni cobertura: una pose puede ser fisicamente valida y estar en el sitio equivocado",
        ],
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    (out_dir / "per_complex.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas),
        encoding="utf-8", newline="\n")
    (out_dir / "failures.jsonl").write_text(
        "".join(json.dumps({"pid": f["pid"], "error": f["error"]}, ensure_ascii=False) + "\n"
                for f in filas if "error" in f), encoding="utf-8", newline="\n")
    print(f"[MF-33-PB] LISTO n={n} single={metrics['cantidad_primaria']['single_validos']} "
          f"ensemble={metrics['cantidad_primaria']['ensemble_validos']} b={b} c={c} "
          f"p={p_val} lectura={lectura}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
