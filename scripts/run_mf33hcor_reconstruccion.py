#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MF-33-H-COR: corrigendum de la capa de reconstruccion usada para PoseBusters.

EL DEFECTO. `posebusters_metrica.mol_con_hidrogenos` anade TODOS los hidrogenos sobre la
geometria CRISTALOGRAFICA. Despues `pose_a_mol` reemplaza unicamente las coordenadas
presentes en el PDBQT, que de Vina trae solo los hidrogenos POLARES. Los no polares se
quedan en posiciones del cristal, incompatibles con la pose dockeada en cuanto los atomos
pesados se mueven. PoseBusters optimiza solo los hidrogenos que el mismo anade; los
explicitos que recibe los considera existentes y los deja fijos. El resultado es una
MOLECULA HIBRIDA -esqueleto dockeado, hidrogenos cristalograficos- cuya energia interna se
dispara sin que haya tension real en el ligando.

Piloto diagnostico ya inspeccionado, 12 complejos: `10gs` pasa de 15442814 a 260.5 kcal/mol
relajando SOLO hidrogenos, con los pesados completamente fijos, y NUEVE de los doce pasan de
invalido a valido por la misma via. El unico con cero hidrogenos huerfanos, `1bcd`, ya era
valido. **Ese piloto demuestra el defecto y diseña la correccion; NO estima la tasa nueva.**

QUEDA SUSPENDIDO hasta que este corrigendum cierre: 217/8215 = 2.64%; el 97.3% de fallos por
internal_energy; el 8/48 contra 10/48 de MF-33-PB; el 8.62% contra 15.52% de MF-33-TOP1; y
las conclusiones "la validez fisica es deficiente", "el ensemble no la arregla" y "una
minimizacion post-docking atacaria el problema".

NO QUEDA INVALIDADO: RMSD y cobertura; top-1, top-5 y la cascada de conversion; las
coordenadas de atomos pesados; y los controles exclusivamente geometricos de pesados, que se
reportan por separado. Pero el indicador compuesto PB-valid SI se recalcula, porque exige que
internal_energy pase.

DOS AMBITOS, porque corregir solo uno dejaria el otro suspendido en vez de reemplazado:
  A) `MF-33-PB`   : 48 complejos, las 8215 poses del brazo flexible;
  B) `MF-33-TOP1` : 116 complejos del protocolo rigido, top-1 de los dos brazos.

Los artefactos originales NO se tocan: quedan sellados e inmutables. Esto produce un
artefacto nuevo con las dos reconstrucciones lado a lado.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

RE_OUT = re.compile(r"conf(\d+)\.out\.pdbqt$")
TOL_PESADOS_A = 1e-6          # invariante: los pesados NO se mueven
MAX_ITER_H = 500


def _receptor_pdb(rec_pdbqt: Path, destino: Path) -> Path:
    if destino.exists():
        return destino
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text("\n".join(
        l[:66].rstrip() for l in rec_pdbqt.read_text(encoding="utf-8", errors="replace").splitlines()
        if l.startswith(("ATOM", "HETATM"))) + "\nEND\n", encoding="utf-8")
    return destino


def _coords_pesados(mol) -> List[tuple]:
    c = mol.GetConformer()
    return [(round(c.GetAtomPosition(a.GetIdx()).x, 6),
             round(c.GetAtomPosition(a.GetIdx()).y, 6),
             round(c.GetAtomPosition(a.GetIdx()).z, 6))
            for a in mol.GetAtoms() if a.GetAtomicNum() > 1]


def reconstruir(crystal_mh, coords_pose: Dict[int, tuple], corregida: bool):
    """Historica o corregida. Devuelve (mol, invariantes) o (None, motivo).

    HISTORICA: copia el cristal-con-todos-los-H y sustituye solo las coordenadas que el
    PDBQT trae. Los hidrogenos no polares se quedan donde estaban en el cristal.

    CORREGIDA: parte del GRAFO DE ATOMOS PESADOS con las coordenadas dockeadas, regenera
    TODOS los hidrogenos desde esa geometria, y los optimiza manteniendo los pesados
    completamente fijos. Ningun hidrogeno hereda coordenadas cristalograficas.
    """
    from rdkit import Chem
    from rdkit.Chem import AllChem
    import posebusters_metrica as pbm

    hist = pbm.pose_a_mol(crystal_mh, coords_pose)
    if hist is None:
        return None, "POSE_A_MOL_FALLO"
    if not corregida:
        return hist, {}

    pesados_antes = _coords_pesados(hist)
    try:
        desnudo = Chem.RemoveAllHs(Chem.Mol(hist))
        rehidratado = Chem.AddHs(desnudo, addCoords=True)
    except Exception as exc:                                   # noqa: BLE001
        return None, f"REHIDRATACION_FALLO:{type(exc).__name__}"

    props = AllChem.MMFFGetMoleculeProperties(rehidratado)
    if props is None:
        return None, "MMFF_NO_PARAMETRIZA"
    ff = AllChem.MMFFGetMoleculeForceField(rehidratado, props)
    if ff is None:
        return None, "FF_NO_CONSTRUIBLE"
    for a in rehidratado.GetAtoms():
        if a.GetAtomicNum() > 1:
            ff.AddFixedPoint(a.GetIdx())
    ff.Minimize(maxIts=MAX_ITER_H)

    pesados_despues = _coords_pesados(rehidratado)
    desp = 0.0
    if len(pesados_antes) == len(pesados_despues):
        desp = max((sum((a[i] - b[i]) ** 2 for i in range(3))) ** 0.5
                   for a, b in zip(pesados_antes, pesados_despues)) if pesados_antes else 0.0
    inv = {
        "desplazamiento_pesado_max_A": round(desp, 9),
        "pesados_invariantes": len(pesados_antes) == len(pesados_despues) and desp <= TOL_PESADOS_A,
        "smiles_identico": (Chem.MolToSmiles(Chem.RemoveAllHs(Chem.Mol(hist)))
                            == Chem.MolToSmiles(Chem.RemoveAllHs(Chem.Mol(rehidratado)))),
        "carga_formal_identica": Chem.GetFormalCharge(hist) == Chem.GetFormalCharge(rehidratado),
        "n_enlaces_identico": (Chem.RemoveAllHs(Chem.Mol(hist)).GetNumBonds()
                               == Chem.RemoveAllHs(Chem.Mol(rehidratado)).GetNumBonds()),
        "n_h_historica": sum(1 for a in hist.GetAtoms() if a.GetAtomicNum() == 1),
        "n_h_corregida": sum(1 for a in rehidratado.GetAtoms() if a.GetAtomicNum() == 1),
        "n_h_heredados_del_cristal": 0,   # por construccion: se eliminaron todos y se regeneraron
    }
    return rehidratado, inv


def _evaluar(mol, crystal_mh, rec: Path) -> Dict[str, Any]:
    import posebusters_metrica as pbm
    r = pbm.evaluar_pose(mol, crystal_mh, rec, config="redock")
    return {"pb_valida": r.get("pb_valid_fisica"),
            "checks_que_fallan": r.get("checks_que_fallan") or [],
            "motivo": r.get("motivo")}


def _energia(mol) -> float | None:
    from rdkit.Chem import AllChem
    try:
        p = AllChem.MMFFGetMoleculeProperties(mol)
        if p is None:
            return None
        ff = AllChem.MMFFGetMoleculeForceField(mol, p)
        return None if ff is None else round(float(ff.CalcEnergy()), 3)
    except Exception:                                          # noqa: BLE001
        return None


def _poses_flexible(origen_r1: Path, origen_r2: Path, pid: str):
    reg = json.loads((origen_r2 / "per_pose" / f"{pid}.json").read_text(encoding="utf-8"))
    return sorted(reg, key=lambda r: (r["score"], r["conformer"], r["model_idx"]))


def analizar(ws_text: str, ambito: str, pid: str, estrato: str, out_text: str,
             o1_text: str, o2_text: str) -> Dict[str, Any]:
    import molflex as mf
    import posebusters_metrica as pbm
    from rdkit import RDLogger
    RDLogger.DisableLog("rdApp.*")

    ws, out_dir = Path(ws_text), Path(out_text)
    o1, o2 = Path(o1_text), Path(o2_text)
    t0 = time.time()
    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "ambito": ambito, "poses": []}
    w = ws / "data" / "molflex_train_v2" / pid / pid
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(a): int(b) for a, b in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}
    crystal_mh = pbm.mol_con_hidrogenos(crystal)
    rec = _receptor_pdb(w / "rec.pdbqt", out_dir / "_rec" / f"{pid}.pdb")

    trabajos: List[Dict[str, Any]] = []
    if ambito == "A":
        for r in _poses_flexible(o1, o2, pid):
            ruta = o2 / r["raw_pdbqt"]
            if not ruta.exists():
                ruta = o1 / r["raw_pdbqt"]
            trabajos.append({"identity": r["identity"], "ruta": ruta,
                             "model_idx": r["model_idx"], "conformer": r["conformer"],
                             "score": r["score"], "rmsd": r.get("rmsd_pose_pocket")})
    else:
        # Protocolo rigido: top-1 de SINGLE (conf0) y de ENSEMBLE (todos), como MF-33-TOP1.
        archivos = sorted((p for p in w.glob("conf*.out.pdbqt") if RE_OUT.search(p.name)),
                          key=lambda p: int(RE_OUT.search(p.name).group(1)))
        cand: List[Dict[str, Any]] = []
        for p in archivos:
            conf = int(RE_OUT.search(p.name).group(1))
            parsed = mf.parsear_out_vina(p.read_text(encoding="utf-8", errors="replace"))
            for i, (sc, _at) in enumerate(parsed):
                if sc is not None:
                    cand.append({"identity": f"{pid}|conf{conf}|model{i}", "ruta": p,
                                 "model_idx": i, "conformer": conf, "score": float(sc),
                                 "rmsd": None})
        if not cand:
            out["error"] = "SIN_POSES"
            return out
        best_ens = min(cand, key=lambda x: (x["score"], x["conformer"], x["model_idx"]))
        s0 = [x for x in cand if x["conformer"] == 0]
        best_sin = min(s0, key=lambda x: (x["score"], x["model_idx"])) if s0 else None
        trabajos = [dict(best_ens, brazo="ENSEMBLE")]
        if best_sin:
            trabajos.append(dict(best_sin, brazo="SINGLE"))

    cache: Dict[str, Any] = {}
    for t in trabajos:
        key = str(t["ruta"])
        if key not in cache:
            cache[key] = (mf.parsear_out_vina(
                t["ruta"].read_text(encoding="utf-8", errors="replace"))
                if t["ruta"].exists() else None)
        parsed = cache[key]
        if not parsed or t["model_idx"] >= len(parsed):
            out["poses"].append({"identity": t["identity"], "motivo": "RAW_AUSENTE"})
            continue
        coords = mf.coords_pose_a_por_mol(parsed[t["model_idx"]][1], s2m)
        if not coords:
            out["poses"].append({"identity": t["identity"], "motivo": "MAPEO_FALLIDO"})
            continue

        fila: Dict[str, Any] = {k: t[k] for k in ("identity", "conformer", "model_idx", "score")}
        if t.get("brazo"):
            fila["brazo"] = t["brazo"]
        if t.get("rmsd") is not None:
            fila["rmsd_pose_pocket"] = t["rmsd"]
        fila["n_h_sin_coordenada_en_pdbqt"] = crystal_mh.GetNumAtoms() - len(coords)

        hist, _ = reconstruir(crystal_mh, coords, corregida=False)
        if hist is None:
            out["poses"].append({"identity": t["identity"], "motivo": "RECON_HIST_FALLO"})
            continue
        fila["HISTORICA"] = dict(_evaluar(hist, crystal_mh, rec), energia=_energia(hist))

        corr, inv = reconstruir(crystal_mh, coords, corregida=True)
        if corr is None:
            fila["CORREGIDA"] = {"pb_valida": None, "motivo": inv}
        else:
            fila["CORREGIDA"] = dict(_evaluar(corr, crystal_mh, rec), energia=_energia(corr))
            fila["invariantes"] = inv
        out["poses"].append(fila)

    out["duration_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-33-H-COR: corrigendum de reconstruccion")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ambito", choices=("A", "B", "AB"), default="AB")
    ap.add_argument("--limite", type=int, default=None,
                    help="solo prueba tecnica; nunca produce decision")
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    o1, o2 = art / "MF-33-B-RET-R1", art / "MF-33-B-RET-R2"
    out_dir = art / "MF-33-H-COR"
    (out_dir / "checkpoints").mkdir(parents=True, exist_ok=True)

    estrato = {json.loads(l)["pid"]: json.loads(l).get("estrato", "RESTO")
               for l in (art / "MF-33" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
               if l.strip()}
    jobs: List[tuple] = []
    if args.ambito in ("A", "AB"):
        jobs += [("A", p.stem, estrato.get(p.stem, "RESTO"))
                 for p in sorted((o2 / "per_pose").glob("*.json"))]
    if args.ambito in ("B", "AB"):
        m13 = {json.loads(l)["pid"] for l in
               (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
               if l.strip()}
        jobs += [("B", p, estrato.get(p, "RESTO")) for p in sorted(m13)]
    if args.limite:
        jobs = jobs[:args.limite]

    hechos = {p.stem for p in (out_dir / "checkpoints").glob("*.json")
              if not p.name.endswith(".poses.json")}
    pend = [j for j in jobs if f"{j[0]}_{j[1]}" not in hechos]
    print(f"[MF-33-H-COR] total={len(jobs)} reanuda={len(hechos)} pendientes={len(pend)} "
          f"workers={args.workers}", flush=True)

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(analizar, str(ws), a, p, e, str(out_dir), str(o1), str(o2)): (a, p)
                for a, p, e in pend}
        for n, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            poses = r.pop("poses")
            base = f"{r['ambito']}_{r['pid']}"
            (out_dir / "checkpoints" / f"{base}.json").write_text(
                json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
            (out_dir / "checkpoints" / f"{base}.poses.json").write_text(
                json.dumps(poses, ensure_ascii=False), encoding="utf-8", newline="\n")
            nh = sum(1 for x in poses if x.get("HISTORICA", {}).get("pb_valida"))
            nc = sum(1 for x in poses if x.get("CORREGIDA", {}).get("pb_valida"))
            print(f"  [{n}/{len(pend)}] {base} poses={len(poses)} validas hist={nh} corr={nc} "
                  f"({r.get('duration_s')}s)", flush=True)

    filas = [json.loads(p.read_text(encoding="utf-8"))
             for p in (out_dir / "checkpoints").glob("*.json")
             if not p.name.endswith(".poses.json")]
    filas.sort(key=lambda x: (x["ambito"], x["pid"]))

    from collections import Counter
    resumen: Dict[str, Any] = {}
    for amb in ("A", "B"):
        tot = val_h = val_c = 0
        ch_h, ch_c = Counter(), Counter()
        inv_malas = 0
        for p in (out_dir / "checkpoints").glob(f"{amb}_*.poses.json"):
            for x in json.loads(p.read_text(encoding="utf-8")):
                h, c = x.get("HISTORICA"), x.get("CORREGIDA")
                if not h or h.get("pb_valida") is None or not c or c.get("pb_valida") is None:
                    continue
                tot += 1
                val_h += bool(h["pb_valida"]); val_c += bool(c["pb_valida"])
                ch_h.update(h.get("checks_que_fallan") or [])
                ch_c.update(c.get("checks_que_fallan") or [])
                inv = x.get("invariantes") or {}
                if not all(inv.get(k, True) for k in
                           ("pesados_invariantes", "smiles_identico",
                            "carga_formal_identica", "n_enlaces_identico")):
                    inv_malas += 1
        resumen[amb] = {
            "poses_evaluadas": tot,
            "validas_reconstruccion_HISTORICA": val_h,
            "validas_reconstruccion_CORREGIDA": val_c,
            "tasa_historica": round(val_h / tot, 4) if tot else None,
            "tasa_corregida": round(val_c / tot, 4) if tot else None,
            "checks_que_fallan_historica": ch_h.most_common(8),
            "checks_que_fallan_corregida": ch_c.most_common(8),
            "poses_con_invariante_violada": inv_malas,
        }

    metrics = {
        "experiment_id": "MF-33-H-COR",
        "tipo": "corrigendum de implementacion; reconstruccion historica contra corregida",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "no_es_ciego": ("Los 12 casos del piloto diagnostico ya fueron inspeccionados. El "
                        "piloto demuestra el defecto y disena la correccion; NO estima la "
                        "tasa nueva, que es lo que este artefacto mide."),
        "ambitos": {"A": "MF-33-PB: 48 complejos, 8215 poses del brazo flexible",
                    "B": "MF-33-TOP1: 116 complejos del protocolo rigido, top-1 de los dos brazos"},
        "config": {"posebusters_config": "redock", "max_iter_h": MAX_ITER_H,
                   "tolerancia_pesados_A": TOL_PESADOS_A},
        "resumen": resumen,
        "artefactos_originales": "sellados e inmutables; este corrigendum NO los modifica",
        "limites_declarados": [
            "no invalida RMSD, cobertura, top-1/top-5 ni la cascada de conversion: esas cantidades no dependen de los hidrogenos",
            "los controles exclusivamente geometricos de atomos pesados tampoco se ven afectados y se reportan por separado",
            "el indicador compuesto PB-valid SI se recalcula, porque exige que internal_energy pase",
            "corrige la CAPA DE RECONSTRUCCION, no el protocolo de docking, que no se toca",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    (out_dir / "per_complex.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas),
        encoding="utf-8", newline="\n")
    (out_dir / "failures.jsonl").write_text(
        "".join(json.dumps({"pid": f["pid"], "ambito": f["ambito"], "error": f["error"]},
                           ensure_ascii=False) + "\n" for f in filas if "error" in f),
        encoding="utf-8", newline="\n")
    for amb, r in resumen.items():
        print(f"[MF-33-H-COR] ambito {amb}: {r['poses_evaluadas']} poses | "
              f"historica {r['tasa_historica']} -> corregida {r['tasa_corregida']} | "
              f"invariantes violadas: {r['poses_con_invariante_violada']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
