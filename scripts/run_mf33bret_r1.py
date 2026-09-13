#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MF-33-B-RET-R1: repeticion completa, reanudable y auditable del brazo B.

No modifica MF-33-B-RET. Conserva cada salida PDBQT, stdout/stderr, un registro
por pose y checkpoints por complejo; asi una interrupcion nunca obliga a borrar
ni reinterpretar el output parcial previo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
BOX, SEED, EXH, NUM_MODES, UMBRAL_A = 25.0, 42, 8, 9, 2.0
G1_TOL, G1_MIN = 0.001, 0.95
RE_FLEX = re.compile(r"conf(\d+)\.flex\.pdbqt$")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for b in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = json.dumps(value, ensure_ascii=False, indent=2) if not isinstance(value, str) else value
    tmp.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _vina() -> str:
    override = os.environ.get("MF33BRET_VINA")
    if override:
        return override
    local = ROOT / "tools" / "vina" / "vina.exe"
    return str(local if local.exists() else "/usr/local/bin/vina")


def _box(c: list[float]) -> list[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def _metricas(poses: list[dict[str, Any]]) -> dict[str, Any]:
    if not poses:
        return {"n_poses": 0, "top1": None, "top5": None, "oraculo": None}
    order = sorted(poses, key=lambda x: (x["score"], x["conformer"], x["model_idx"]))
    result = {"n_poses": len(order), "top1": round(order[0]["rmsd_pose_pocket"], 3),
              "top5": round(min(x["rmsd_pose_pocket"] for x in order[:5]), 3),
              "oraculo": round(min(x["rmsd_pose_pocket"] for x in order), 3),
              "score_top1": round(order[0]["score"], 3),
              "top1_identity": order[0]["identity"]}
    for key in ("top1", "top5", "oraculo"):
        result[f"acierta_{key}"] = result[key] <= UMBRAL_A
    result["margen_de_seleccion"] = result["acierta_oraculo"] and not result["acierta_top1"]
    return result


def _posebusters(pid: str, raw: Path, model: int, ws: Path, crystal: Any, s2m: dict[int, int]) -> dict[str, Any]:
    try:
        import posebusters_metrica as pb
        if not pb.disponible():
            return {"pb_valid_fisica": None, "motivo": "posebusters_no_instalado"}
        rows = pb.evaluar_pdbqt(pid, raw.read_text(encoding="utf-8", errors="replace"), ws,
                                crystal=crystal, s2m=s2m, solo_top1=False)
        return next((x for x in rows if x.get("modelo") == model),
                    {"pb_valid_fisica": None, "motivo": "MODELO_NO_ENCONTRADO"})
    except Exception as ex:
        return {"pb_valid_fisica": None, "motivo": f"{type(ex).__name__}:{str(ex)[-120:]}"}


def analizar(ws_text: str, pid: str, estrato: str, out_text: str) -> dict[str, Any]:
    """Un complejo atomico: todos sus PDBQT se publican antes del checkpoint."""
    import molflex as mf
    ws, out_dir = Path(ws_text), Path(out_text)
    started = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, center_path, map_path = w / "rec.pdbqt", w / "center.json", w / "index_map.json"
    out: dict[str, Any] = {"pid": pid, "estrato": estrato, "failures": [], "poses": []}
    if not all(p.exists() for p in (rec, center_path, map_path)):
        out["error"] = "SIN_MATERIAL"; return out
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"; return out
    center = json.loads(center_path.read_text(encoding="utf-8"))
    s2m = {int(a): int(b) for a, b in json.loads(map_path.read_text(encoding="utf-8"))}
    flexes = sorted((p for p in w.glob("conf*.flex.pdbqt") if RE_FLEX.search(p.name)),
                    key=lambda p: int(RE_FLEX.search(p.name).group(1)))
    if not flexes:
        out["error"] = "SIN_CONFORMEROS"; return out
    out["K"] = len(flexes)
    for flex in flexes:
        conf = int(RE_FLEX.search(flex.name).group(1))
        raw = out_dir / "raw_pdbqt" / pid / f"conf{conf}.out.pdbqt"
        stdout = out_dir / "logs" / pid / f"conf{conf}.stdout.txt"
        stderr = out_dir / "logs" / pid / f"conf{conf}.stderr.txt"
        raw.parent.mkdir(parents=True, exist_ok=True); stdout.parent.mkdir(parents=True, exist_ok=True)
        temp = raw.with_suffix(".pdbqt.part")
        cmd = [_vina(), "--receptor", str(rec), "--ligand", str(flex)] + _box(center) + [
            "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES), "--seed", str(SEED),
            "--cpu", "1", "--out", str(temp)]
        began = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
            stdout.write_text(p.stdout, encoding="utf-8", newline="\n")
            stderr.write_text(p.stderr, encoding="utf-8", newline="\n")
            ok = p.returncode == 0 and temp.exists()
        except subprocess.TimeoutExpired as ex:
            stdout.write_text(ex.stdout or "", encoding="utf-8", newline="\n")
            stderr.write_text((ex.stderr or "") + "\nTIMEOUT", encoding="utf-8", newline="\n")
            ok, p = False, None
        if not ok:
            out["failures"].append({"pid": pid, "conformer": conf, "stage": "vina",
                                    "returncode": None if p is None else p.returncode,
                                    "duration_s": round(time.time() - began, 3)})
            try: temp.unlink()
            except OSError: pass
            continue
        os.replace(temp, raw)
        raw_hash = _sha(raw)
        parsed = mf.parsear_out_vina(raw.read_text(encoding="utf-8", errors="replace"))
        if not parsed:
            out["failures"].append({"pid": pid, "conformer": conf, "stage": "parse", "raw_sha256": raw_hash})
        for model_idx, (score, atoms) in enumerate(parsed):
            coords = mf.coords_pose_a_por_mol(atoms, s2m)
            rmsd = mf.rmsd_pose_pocket(crystal, coords) if coords else None
            if score is None or rmsd is None:
                out["failures"].append({"pid": pid, "conformer": conf, "model_idx": model_idx,
                                        "stage": "map_or_rmsd", "raw_sha256": raw_hash})
                continue
            out["poses"].append({"identity": f"{pid}|conf{conf}|model{model_idx}", "pid": pid,
                                 "conformer": conf, "model_idx": model_idx, "score": float(score),
                                 "rmsd_pose_pocket": float(rmsd), "raw_pdbqt": raw.relative_to(out_dir).as_posix(),
                                 "raw_sha256": raw_hash, "stdout": stdout.relative_to(out_dir).as_posix(),
                                 "stderr": stderr.relative_to(out_dir).as_posix()})
    single = [x for x in out["poses"] if x["conformer"] == 0]
    out["SINGLE"], out["ENSEMBLE"] = _metricas(single), _metricas(out["poses"])
    for arm, pool in (("SINGLE", single), ("ENSEMBLE", out["poses"])):
        if pool:
            top = sorted(pool, key=lambda x: (x["score"], x["conformer"], x["model_idx"]))[0]
            pb = _posebusters(pid, out_dir / top["raw_pdbqt"], top["model_idx"], ws, crystal, s2m)
            out[arm]["pb_valid_fisica"] = pb.get("pb_valid_fisica")
            out[arm]["pb_checks_que_fallan"] = pb.get("checks_que_fallan")
            out[arm]["pb_motivo"] = pb.get("motivo")
    out["duration_s"] = round(time.time() - started, 3)
    return out


def _block(rows: list[dict[str, Any]], label: str) -> dict[str, Any]:
    from estadistica_fnd04 import mcnemar_exacto
    b: dict[str, Any] = {"etiqueta": label, "n": len(rows)}
    for field in ("top1", "top5", "oraculo"):
        win_e = sum(x["ENSEMBLE"][f"acierta_{field}"] and not x["SINGLE"][f"acierta_{field}"] for x in rows)
        win_s = sum(x["SINGLE"][f"acierta_{field}"] and not x["ENSEMBLE"][f"acierta_{field}"] for x in rows)
        s = sum(x["SINGLE"][f"acierta_{field}"] for x in rows); e = sum(x["ENSEMBLE"][f"acierta_{field}"] for x in rows)
        b[field] = {"single": s, "ensemble": e, "de": len(rows), "b_gana_ensemble": win_e,
                    "c_gana_single": win_s, "mcnemar_p": round(mcnemar_exacto(win_e, win_s), 6),
                    "delta_pp": round((e-s)*100/len(rows), 2) if rows else None}
    b["margen_de_seleccion_single"] = sum(x["SINGLE"]["margen_de_seleccion"] for x in rows)
    b["margen_de_seleccion_ensemble"] = sum(x["ENSEMBLE"]["margen_de_seleccion"] for x in rows)
    return b


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default=str(ROOT)); ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--limite", type=int, default=None, help="solo prueba tecnica; nunca produce decision")
    args = ap.parse_args(); ws = Path(args.workspace); out_dir = ws / "scripts" / "artifacts_science" / "MF-33-B-RET-R1"
    out_dir.mkdir(parents=True, exist_ok=True)
    parent = {x["pid"]: x for x in (json.loads(s) for s in (ws / "scripts" / "artifacts_science" / "MF-33" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines() if s.strip())}
    jobs = sorted((pid, r["estrato"]) for pid, r in parent.items())
    if args.limite: jobs = jobs[:args.limite]
    completed: dict[str, dict[str, Any]] = {}
    for p in (out_dir / "checkpoints").glob("*.json"):
        try:
            r = json.loads(p.read_text(encoding="utf-8")); completed[r["pid"]] = r
        except (json.JSONDecodeError, KeyError): pass
    pending = [(p, e) for p, e in jobs if p not in completed]
    print(f"[MF-33-B-RET-R1] total={len(jobs)} reanuda={len(completed)} pendientes={len(pending)} workers={args.workers}", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(analizar, str(ws), pid, est, str(out_dir)): pid for pid, est in pending}
        for n, future in enumerate(as_completed(futures), 1):
            r = future.result(); pid = r["pid"]
            _write(out_dir / "checkpoints" / f"{pid}.json", r)
            _write(out_dir / "per_pose" / f"{pid}.json", r.pop("poses"))
            completed[pid] = r
            print(f"  [{n}/{len(pending)}] {pid} poses={r.get('ENSEMBLE',{}).get('n_poses')} failures={len(r.get('failures',[]))}", flush=True)
    rows = [completed[p] for p, _ in jobs if p in completed]
    failures = [f for r in rows for f in r.get("failures", [])]
    ok = [r for r in rows if not r.get("error") and not r.get("failures") and r.get("ENSEMBLE", {}).get("n_poses", 0) > 0]
    for r in rows:
        r.pop("failures", None)
    _write(out_dir / "per_complex.jsonl", "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows))
    _write(out_dir / "failures.jsonl", "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in failures))
    comp = [(r, parent[r["pid"]]["brazos"].get("B", {}).get("rmsd_min")) for r in ok]
    equal = sum(abs(r["ENSEMBLE"]["oraculo"] - ref) <= G1_TOL for r, ref in comp if ref is not None)
    g1n = sum(ref is not None for _, ref in comp); g1 = equal/g1n if g1n else 0.0
    all_block, coloc = _block(ok, "TODOS"), _block([r for r in ok if r["estrato"] == "COLOCACION"], "COLOCACION")
    improve_o = all_block["oraculo"]["mcnemar_p"] < .05 and all_block["oraculo"]["b_gana_ensemble"] > all_block["oraculo"]["c_gana_single"]
    improve_t = all_block["top1"]["mcnemar_p"] < .05 and all_block["top1"]["b_gana_ensemble"] > all_block["top1"]["c_gana_single"]
    technical = len(rows) == len(jobs) and not failures and len(ok) == len(jobs) and g1 >= G1_MIN
    reading = ("LA_VENTAJA_LLEGA_AL_USUARIO" if improve_o and improve_t else "EL_CUELLO_SE_DESPLAZA_A_LA_SELECCION" if improve_o else "SIN_EFECTO_EN_LA_ENTREGA") if technical and not args.limite else "NO_LEER_GATES_TECNICOS"
    metrics = {"experiment_id": "MF-33-B-RET-R1", "timestamp": datetime.now(timezone.utc).isoformat(),
               "config": {"exhaustiveness": EXH, "num_modes": NUM_MODES, "seed": SEED, "box_A": BOX, "cpu": 1, "threshold_A": UMBRAL_A},
               "technical_gate": {"expected_complexes": len(jobs), "completed": len(rows), "failures": len(failures), "pasa": technical},
               "G1_REPRODUCE_BRAZO_B_SELLADO": {"iguales": equal, "de": g1n, "fraccion": round(g1,4), "minimo": G1_MIN, "pasa": g1 >= G1_MIN},
               "TODOS": all_block, "COLOCACION": coloc, "lectura_preregistrada": reading,
               "retention": {"raw_pdbqt": "raw_pdbqt/", "logs": "logs/", "per_pose": "per_pose/", "checkpoint": "checkpoints/"}}
    _write(out_dir / "metrics.json", metrics)
    print(f"[MF-33-B-RET-R1] tecnico={technical} G1={g1:.4f} lectura={reading}", flush=True)
    return 0 if technical else 2


if __name__ == "__main__":
    raise SystemExit(main())
