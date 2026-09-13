#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MF-33-MIN: ¿la tension interna de las poses es artefacto del protocolo o fisica real?

`MF-33-PB` midio que solo 217 de 8215 poses del brazo flexible pasan la bateria completa
-el 2.64%- y que el fallo esta concentrado de forma extrema: `internal_energy` falla 7997
veces frente a 598 del siguiente control. Practicamente TODA pose invalida lo es por la
misma causa.

LA PREGUNTA QUE ESTE EXPERIMENTO EXISTE PARA RESPONDER, y no es retorica. `internal_energy`
compara la energia de la pose contra un ensemble de conformeros LIBRES. Pero un ligando
UNIDO paga una penalizacion conformacional real: se tuerce para encajar. Asi que ese 97.3%
admite dos explicaciones incompatibles:

  (a) ARTEFACTO. El protocolo dockea conformeros rigidos que nunca se relajan, cada pose
      hereda la tension de la conformacion de partida, y esa tension se puede liberar SIN
      mover la pose. Si es esto, un paso de minimizacion arregla el 97.3%.
  (b) FISICA. La tension es intrinseca a estar colocado ahi, y liberarla exige mover la
      pose. Si es esto, minimizar compra validez fisica a cambio de precision geometrica, y
      NO se debe adoptar.

Las dos se distinguen con DOS BRAZOS de relajacion sobre las MISMAS poses:

  - `RESTRINGIDA` : minimizacion con restricciones armonicas sobre los atomos pesados. Deja
    relajar enlaces, angulos y torsiones pero penaliza el desplazamiento. Responde: ¿se
    puede liberar la tension EN EL SITIO?
  - `LIBRE`       : minimizacion sin restricciones. Responde: ¿cuanto tiene que moverse la
    molecula para dejar de estar tensa?

Sin dockear ni una sola pose nueva: se relajan las 8215 ya retenidas y se vuelve a medir.

LIMITE DECLARADO Y NO DISIMULADO: la minimizacion es del ligando SOLO, con MMFF, sin el
campo del receptor. "En el sitio" es por tanto una aproximacion sostenida por las
restricciones posicionales, no por la proteina. Un ligando relajado en el campo real del
receptor podria comportarse distinto, y este experimento NO lo mide. Se elige asi porque
mide la pregunta (a) contra (b) con lo que hay, y porque meter el campo del receptor
convierte esto en otro experimento, mas caro y con mas piezas que pueden fallar.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

UMBRAL_A = 2.0
TOP_K = 5
FUERZA_RESTRICCION = 10.0      # kcal/mol/A^2 sobre cada atomo pesado
MAX_ITER = 500


def _receptor_pdb(rec_pdbqt: Path, destino: Path) -> Path:
    if destino.exists():
        return destino
    lineas = [l[:66].rstrip() for l in
              rec_pdbqt.read_text(encoding="utf-8", errors="replace").splitlines()
              if l.startswith(("ATOM", "HETATM"))]
    destino.write_text("\n".join(lineas) + "\nEND\n", encoding="utf-8")
    return destino


def _minimizar(mol, restringido: bool):
    """Minimiza con MMFF. Devuelve (mol_minimizado, energia_inicial, energia_final)."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    m = Chem.Mol(mol)
    props = AllChem.MMFFGetMoleculeProperties(m)
    if props is None:
        return None, None, None
    ff = AllChem.MMFFGetMoleculeForceField(m, props)
    if ff is None:
        return None, None, None
    e0 = float(ff.CalcEnergy())
    if restringido:
        # `MMFFAddPositionConstraint` es la API documentada para restricciones
        # posicionales. La primera version las montaba a mano con AddExtraPoint +
        # AddDistanceConstraint y reventaba el campo de fuerzas -"Pre-condition Violation:
        # size mismatch" en ForceField.cpp- porque anadir puntos extra despues de
        # construirlo exige reinicializarlo. Se cambia por la via soportada en vez de
        # parchear la artesanal.
        for a in m.GetAtoms():
            if a.GetAtomicNum() > 1:
                ff.MMFFAddPositionConstraint(a.GetIdx(), 0.0, FUERZA_RESTRICCION)
    ff.Minimize(maxIts=MAX_ITER)
    return m, e0, float(ff.CalcEnergy())


def _rmsd_entre(mol_a, mol_b) -> float | None:
    """RMSD directo entre dos conformaciones de la MISMA molecula, sin alineamiento.

    Sin alineamiento a proposito: aqui interesa cuanto se MOVIO la pose en el marco del
    receptor, no cuanto cambio su forma. Alinear borraria exactamente la senal buscada.
    """
    ca, cb = mol_a.GetConformer(), mol_b.GetConformer()
    n = 0
    s = 0.0
    for a in mol_a.GetAtoms():
        if a.GetAtomicNum() <= 1:
            continue
        i = a.GetIdx()
        pa, pb = ca.GetAtomPosition(i), cb.GetAtomPosition(i)
        s += (pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2 + (pa.z - pb.z) ** 2
        n += 1
    return (s / n) ** 0.5 if n else None


def analizar(ws_text: str, origen_r1: str, origen_r2: str, pid: str, estrato: str,
             out_text: str) -> Dict[str, Any]:
    import molflex as mf
    import posebusters_metrica as pbm
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")

    ws, out_dir = Path(ws_text), Path(out_text)
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

    # La geometria cruda de 47 complejos vive en R1 y la de 1afl en R2, que es el unico que
    # R2 recomputo. Se resuelve en ese orden y se registra cual se uso.
    o1, o2 = Path(origen_r1), Path(origen_r2)
    registros = json.loads((o2 / "per_pose" / f"{pid}.json").read_text(encoding="utf-8"))
    orden = sorted(registros, key=lambda r: (r["score"], r["conformer"], r["model_idx"]))

    cache: Dict[str, Any] = {}
    for r in orden:
        rel = r["raw_pdbqt"]
        if rel not in cache:
            ruta = o2 / rel
            if not ruta.exists():
                ruta = o1 / rel
            if not ruta.exists():
                cache[rel] = None
            else:
                cache[rel] = (mf.parsear_out_vina(
                    ruta.read_text(encoding="utf-8", errors="replace")),
                    "R2" if (o2 / rel).exists() else "R1")
        if cache[rel] is None:
            out["poses"].append({"identity": r["identity"], "motivo": "RAW_AUSENTE"})
            continue
        parsed, fuente = cache[rel]
        if r["model_idx"] >= len(parsed):
            out["poses"].append({"identity": r["identity"], "motivo": "MODELO_AUSENTE"})
            continue
        coords = mf.coords_pose_a_por_mol(parsed[r["model_idx"]][1], s2m)
        if not coords:
            out["poses"].append({"identity": r["identity"], "motivo": "MAPEO_FALLIDO"})
            continue
        pose0 = pbm.pose_a_mol(crystal_mh, coords)

        fila: Dict[str, Any] = {
            "identity": r["identity"], "conformer": r["conformer"],
            "model_idx": r["model_idx"], "score": r["score"],
            "rmsd_original": r["rmsd_pose_pocket"], "fuente_raw": fuente,
        }
        base = pbm.evaluar_pose(pose0, crystal_mh, rec, config="redock")
        fila["ORIGINAL"] = {"pb_valida": base.get("pb_valid_fisica"),
                            "checks_que_fallan": base.get("checks_que_fallan") or []}

        for brazo, restringido in (("RESTRINGIDA", True), ("LIBRE", False)):
            m, e0, e1 = _minimizar(pose0, restringido)
            if m is None:
                fila[brazo] = {"pb_valida": None, "motivo": "MMFF_NO_PARAMETRIZA"}
                continue
            res = pbm.evaluar_pose(m, crystal_mh, rec, config="redock")
            cm = mf.coords_pose_a_por_mol
            coords_min = {i: (m.GetConformer().GetAtomPosition(i).x,
                              m.GetConformer().GetAtomPosition(i).y,
                              m.GetConformer().GetAtomPosition(i).z)
                          for i in coords}
            fila[brazo] = {
                "pb_valida": res.get("pb_valid_fisica"),
                "checks_que_fallan": res.get("checks_que_fallan") or [],
                "energia_antes": None if e0 is None else round(e0, 3),
                "energia_despues": None if e1 is None else round(e1, 3),
                "desplazamiento_A": (None if _rmsd_entre(pose0, m) is None
                                     else round(_rmsd_entre(pose0, m), 3)),
                "rmsd_al_cristal": (None if mf.rmsd_pose_pocket(crystal, coords_min) is None
                                    else round(mf.rmsd_pose_pocket(crystal, coords_min), 3)),
            }
        out["poses"].append(fila)

    por_id = {p["identity"]: p for p in out["poses"] if "ORIGINAL" in p}
    top1 = por_id.get(orden[0]["identity"]) if orden else None
    out["TOP1"] = top1
    out["duration_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    from estadistica_fnd04 import mcnemar_exacto, efecto_minimo_detectable

    ap = argparse.ArgumentParser(description="MF-33-MIN: relajacion de poses retenidas")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limite", type=int, default=None,
                    help="solo prueba tecnica; nunca produce decision")
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    o1, o2 = art / "MF-33-B-RET-R1", art / "MF-33-B-RET-R2"
    out_dir = art / "MF-33-MIN"
    (out_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

    estrato = {json.loads(l)["pid"]: json.loads(l).get("estrato", "RESTO")
               for l in (art / "MF-33" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
               if l.strip()}
    jobs = sorted((p.stem, estrato.get(p.stem, "RESTO"))
                  for p in (o2 / "per_pose").glob("*.json"))
    if args.limite:
        jobs = jobs[:args.limite]
    hechos = {p.stem for p in (out_dir / "checkpoints").glob("*.json")
              if not p.name.endswith(".poses.json")}
    pend = [(p, e) for p, e in jobs if p not in hechos]
    print(f"[MF-33-MIN] total={len(jobs)} reanuda={len(hechos)} pendientes={len(pend)} "
          f"workers={args.workers}", flush=True)

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(analizar, str(ws), str(o1), str(o2), p, e, str(out_dir)): p
                for p, e in pend}
        for n, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            poses = r.pop("poses")
            (out_dir / "checkpoints" / f"{r['pid']}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
            (out_dir / "checkpoints" / f"{r['pid']}.poses.json").write_text(
                json.dumps(poses, ensure_ascii=False), encoding="utf-8", newline="\n")
            t = r.get("TOP1") or {}
            print(f"  [{n}/{len(pend)}] {r['pid']} orig={t.get('ORIGINAL',{}).get('pb_valida')} "
                  f"restr={t.get('RESTRINGIDA',{}).get('pb_valida')} "
                  f"libre={t.get('LIBRE',{}).get('pb_valida')} "
                  f"poses={len(poses)} ({r.get('duration_s')}s)", flush=True)

    filas = [json.loads(p.read_text(encoding="utf-8"))
             for p in (out_dir / "checkpoints").glob("*.json")
             if not p.name.endswith(".poses.json")]
    filas.sort(key=lambda x: x["pid"])
    ok = [f for f in filas if f.get("TOP1") and f["TOP1"].get("ORIGINAL")]

    def pareado(brazo: str, campo) -> Dict[str, Any]:
        b = sum(1 for f in ok if campo(f["TOP1"].get(brazo)) and not campo(f["TOP1"]["ORIGINAL"]))
        c = sum(1 for f in ok if campo(f["TOP1"]["ORIGINAL"]) and not campo(f["TOP1"].get(brazo)))
        n = len(ok)
        disc = round((b + c) / n, 4) if n else None
        return {"antes": sum(1 for f in ok if campo(f["TOP1"]["ORIGINAL"])),
                "despues": sum(1 for f in ok if campo(f["TOP1"].get(brazo))),
                "de": n, "b_mejora": b, "c_empeora": c,
                "mcnemar_p": round(mcnemar_exacto(b, c), 6) if n else None,
                "discordancia": disc,
                "mde_pp": round(efecto_minimo_detectable(n, disc) * 100, 2) if n and disc else None}

    def val(d):
        return bool(d and d.get("pb_valida"))

    def cubre(d):
        if not d:
            return False
        r = d.get("rmsd_al_cristal", d.get("rmsd_original"))
        return r is not None and r <= UMBRAL_A

    bloques = {}
    for brazo in ("RESTRINGIDA", "LIBRE"):
        fisica = pareado(brazo, val)
        geom = pareado(brazo, cubre)
        mejora_f = fisica["mcnemar_p"] is not None and fisica["mcnemar_p"] < .05 and fisica["b_mejora"] > fisica["c_empeora"]
        degrada_g = geom["mcnemar_p"] is not None and geom["mcnemar_p"] < .05 and geom["c_empeora"] > geom["b_mejora"]
        if args.limite:
            lect = "NO_LEER_GATES_TECNICOS"
        elif mejora_f and not degrada_g:
            lect = "ERA_ARTEFACTO_SE_PUEDE_ADOPTAR"
        elif mejora_f and degrada_g:
            lect = "COMPRA_FISICA_A_COSTA_DE_GEOMETRIA_NO_ADOPTAR"
        elif not mejora_f:
            lect = "LA_MINIMIZACION_NO_ARREGLA_LA_FISICA"
        else:
            lect = "SIN_DIFERENCIA_DETECTABLE"
        desp = [p[brazo]["desplazamiento_A"] for f in filas
                for p in [f.get("TOP1")] if p and p.get(brazo)
                and p[brazo].get("desplazamiento_A") is not None]
        bloques[brazo] = {"validez_fisica": fisica, "cobertura_geometrica": geom,
                          "desplazamiento_mediano_A": (sorted(desp)[len(desp)//2] if desp else None),
                          "lectura_preregistrada": lect}

    metrics = {
        "experiment_id": "MF-33-MIN",
        "tipo": "relajacion pareada sobre poses retenidas; co-primarias fisica y geometria",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {"campo": "MMFF, ligando solo, SIN campo del receptor",
                   "restriccion_kcal_mol_A2": FUERZA_RESTRICCION, "max_iter": MAX_ITER,
                   "umbral_A": UMBRAL_A, "posebusters_config": "redock"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "por_brazo": bloques,
        "limites_declarados": [
            "la minimizacion es del ligando SOLO, sin el campo del receptor: 'en el sitio' lo sostienen las restricciones posicionales, no la proteina",
            "no se dockea ninguna pose nueva; se relajan las ya retenidas",
            "la cohorte tiene cristal, que es lo que permite arbitrar si moverse fue bueno o malo; en produccion no lo hay y la regla de producto se deriva de aqui, no al reves",
            "NO comparable con la configuracion dock de produccion ni con MF-33-TOP1",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    (out_dir / "per_complex.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas),
        encoding="utf-8", newline="\n")
    (out_dir / "failures.jsonl").write_text(
        "".join(json.dumps({"pid": f["pid"], "error": f["error"]}, ensure_ascii=False) + "\n"
                for f in filas if "error" in f), encoding="utf-8", newline="\n")
    for brazo, b in bloques.items():
        print(f"[MF-33-MIN] {brazo}: fisica {b['validez_fisica']['antes']}->"
              f"{b['validez_fisica']['despues']} p={b['validez_fisica']['mcnemar_p']} | "
              f"geometria {b['cobertura_geometrica']['antes']}->"
              f"{b['cobertura_geometrica']['despues']} p={b['cobertura_geometrica']['mcnemar_p']} | "
              f"desp={b['desplazamiento_mediano_A']} A | {b['lectura_preregistrada']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
