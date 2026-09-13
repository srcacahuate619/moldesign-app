#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rec03_grid_repair.py — REC-03: ¿un grid predicho repara el docking que el catálogo pierde?

Prerrequisito formal: `scripts/artifacts_science/REC-03-PRE/PREREGISTRO.md` sellado.
Entrada sellada: `REC-01-R1` (cohorte y severidades) y `REC-03-PRE/geometria_preflight.json`
(centros de MolPocket, ya declarados antes de ejecutar).

Diseño congelado
----------------
- Cohorte: 25 accionables (11 S1_CRITICO + 14 S2_GRAVE) + 12 control S0_SIN_EXCEPCION
  muestreados con `random.Random(42).sample` sobre la lista ordenada de S0 elegibles.
- Cajas por target (única variable = el CENTRO; el TAMAÑO es siempre el del catálogo):
    G_CAT  centro del catálogo (statu quo)
    G_MP1  centro del pocket top-1 de MolPocket
    G_MP2  centro del pocket 2
    G_MP3  centro del pocket 3
  MolPocket es ligando-libre (`detect_pockets` solo lee líneas ATOM). Los hotspots
  del catálogo NO se usan para definir cajas: `discover_pocket_from_pdb` los deriva
  de los residuos vecinos al ligando nativo y su uso sería circular.
- Brazo derivado `G_MP_SCORE`: entre G_MP1..3, el de MEJOR SCORE de Vina por semilla.
  El criterio de selección es el score, nunca la posición del ligando.
- Semillas 42/43/44, exhaustiveness 32, num_modes 9, cpu 1, timeout 1800 s.
- Receptor: todas las cadenas proteicas (líneas ATOM), sin aguas y sin HETATM —
  el ligando nativo debe salir del receptor o bloquearía su propio sitio. Cofactores
  y metales también salen: es una limitación declarada, idéntica en los cuatro brazos.
- Métrica primaria: RMSD simétrico IN SITU (`rdMolAlign.CalcRMS`, sin realinear) de la
  pose top-1 contra el ligando cristalográfico del mismo PDB. Éxito = <= 2.0 A.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

EXPERIMENT_ID = "REC-03"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
PRE_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "REC-03-PRE"
R1_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / "REC-01-R1"
VINA = PROJECT_ROOT / "tools" / "vina" / "vina.exe"
WORK = OUT_DIR / "_work"

AGUAS = {"HOH", "WAT", "DOD"}
SEEDS = (42, 43, 44)
EXHAUSTIVENESS = 32
NUM_MODES = 9
CPU = 1
TIMEOUT_S = 1800
RMSD_EXITO_A = 2.0
N_CONTROL = 12
SEED_MUESTREO = 42
WORKERS = 10
RUTAS_PROTEGIDAS = [
    PROJECT_ROOT / "curated_targets.json",
    PROJECT_ROOT / "curated_targets.csv",
]


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


# ── Preparación ────────────────────────────────────────────────────────────

def filtrar_receptor(origen: Path, destino: Path) -> Dict[str, int]:
    """Receptor = líneas ATOM de todas las cadenas, sin aguas, sin HETATM.

    Regla de altloc idéntica a `preparer.py` (variante mayoritaria por residuo,
    prefiriendo la variante sin altloc en caso de empate).
    """
    contenido = origen.read_text(encoding="utf-8", errors="replace")

    por_residuo: Dict[tuple, Dict[str, int]] = {}
    for l in contenido.splitlines():
        if l[:6].strip() != "ATOM" or len(l) < 27:
            continue
        rn = l[17:20].strip()
        if rn in AGUAS:
            continue
        ch = l[21:22].strip() or "A"
        try:
            sq = int(l[22:26].strip())
        except ValueError:
            continue
        cuentas = por_residuo.setdefault((ch, sq, rn), {})
        v = l[16:17]
        cuentas[v] = cuentas.get(v, 0) + 1

    elegido: Dict[tuple, str] = {}
    for k, cuentas in por_residuo.items():
        if cuentas.get(" ", 0) >= max(cuentas.values()):
            elegido[k] = " "
        else:
            elegido[k] = max(cuentas, key=lambda v: (cuentas[v], v == " "))

    salida: List[str] = []
    stats = {"hetatm_eliminados": 0, "aguas_eliminadas": 0,
             "altloc_descartado": 0, "conservadas": 0}
    for l in contenido.splitlines():
        rec = l[:6].strip()
        if rec in {"TER", "END"}:
            salida.append(l)
            continue
        if rec == "HETATM":
            rn = l[17:20].strip() if len(l) >= 20 else ""
            stats["aguas_eliminadas" if rn in AGUAS else "hetatm_eliminados"] += 1
            continue
        if rec != "ATOM" or len(l) < 27:
            continue
        rn = l[17:20].strip()
        ch = l[21:22].strip() or "A"
        try:
            sq = int(l[22:26].strip())
        except ValueError:
            continue
        if l[16:17] != elegido.get((ch, sq, rn), " "):
            stats["altloc_descartado"] += 1
            continue
        salida.append(l[:16] + " " + l[17:])
        stats["conservadas"] += 1

    destino.write_text("\n".join(salida) + "\nEND\n", encoding="utf-8", newline="\n")
    return stats


def extraer_ligando(pdb_path: Path, lig_id: str, destino_pdb: Path) -> int:
    """Escribe el ligando nativo (HETATM del res_id de REC-01-R1) como PDB."""
    het = []
    for l in pdb_path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not l.startswith("HETATM") or len(l) < 54:
            continue
        res_name = l[17:20].strip().upper()
        chain = (l[21:22].strip() or "A").upper()
        res_seq = l[22:26].strip()
        if f"{chain}:{res_name}{res_seq}" != lig_id.upper():
            continue
        het.append(l[:16] + " " + l[17:])
    if het:
        destino_pdb.write_text("\n".join(het) + "\nEND\n", encoding="utf-8", newline="\n")
    return len(het)


def _reparar_ligando(sdf_openbabel: Path, destino_sdf: Path) -> Optional[Tuple[Path, str]]:
    """Repara la REPRESENTACIÓN de valencia del SDF de Open Babel sin tocar su
    conectividad ni las coordenadas cristalográficas.

    Dos arreglos, ambos estándar y deterministas:
      1. `rdMolStandardize.Normalizer` — reescribe nitro y similares a su forma
         con cargas separadas (`N(=O)=O` -> `[N+](=O)[O-]`), que es la causa más
         común del rechazo de RDKit dentro de Meeko.
      2. Nitrógeno tetravalente neutro -> carga formal +1 (amonio cuaternario).

    NO se intenta reasignar órdenes de enlace desde geometría: `rdDetermineBonds`
    produce estructuras absurdas sobre estos ligandos (carbaniones [C-3], anillos
    aromáticos como alenos acumulados) y docking sobre eso sería peor que excluir
    el target. Un carbono con 5 enlaces es un error de conectividad real y el
    target se excluye.
    """
    from rdkit import Chem, RDLogger
    from rdkit.Chem.MolStandardize import rdMolStandardize

    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromMolFile(str(sdf_openbabel), sanitize=False, removeHs=False)
    if mol is None:
        return None
    arreglos: List[str] = []
    mol.UpdatePropertyCache(strict=False)
    try:
        mol = rdMolStandardize.Normalizer().normalize(mol)
        mol.UpdatePropertyCache(strict=False)
        arreglos.append("normalizer")
    except Exception:
        pass
    n_quat = 0
    for a in mol.GetAtoms():
        if a.GetSymbol() == "N" and a.GetFormalCharge() == 0 and a.GetExplicitValence() == 4:
            a.SetFormalCharge(1)
            n_quat += 1
    if n_quat:
        arreglos.append(f"N_cuaternario_x{n_quat}")
    mol.UpdatePropertyCache(strict=False)
    try:
        Chem.SanitizeMol(mol)
    except Exception:
        return None
    # Guardia de sanidad: ningún carbono cargado, ninguna carga formal |q| >= 2
    for a in mol.GetAtoms():
        if a.GetSymbol() == "C" and a.GetFormalCharge() != 0:
            return None
        if abs(a.GetFormalCharge()) >= 2:
            return None
    Chem.MolToMolFile(mol, str(destino_sdf))
    return destino_sdf, "+".join(arreglos) or "sanitizado"


def preparar_target(item: Dict[str, Any]) -> Dict[str, Any]:
    """Receptor .pdbqt + ligando .pdbqt/.sdf de un target. Devuelve estado."""
    pdb_id = item["pdb_id"]
    wd = WORK / pdb_id
    wd.mkdir(parents=True, exist_ok=True)
    pdb_path = PROJECT_ROOT / item["pdb_ruta"]
    res: Dict[str, Any] = {"pdb_id": pdb_id}

    filtrado = wd / f"{pdb_id}_rec.pdb"
    stats = filtrar_receptor(pdb_path, filtrado)
    res["filtro"] = stats
    if stats["conservadas"] < 100:
        res["error"] = "RECEPTOR_VACIO"
        return res

    rec_pdbqt = wd / f"{pdb_id}_rec.pdbqt"
    if not rec_pdbqt.exists():
        c, s = item["grid_centro"], item["grid_tam"]
        # Desviación de preparación declarada: cuando Meeko no puede desempatar el
        # tautómero de una histidina (HIE/HID/HIP dan el mismo número de H), se fija
        # HIE (tautómero neutro Nε-H, el default habitual en campos de fuerza) y se
        # reintenta. La regla es determinista y se aplica igual en los 4 brazos.
        plantillas: List[str] = []
        for _ in range(3):  # cap de coste: 3 rondas de desempate de histidina, luego se excluye
            cmd = [sys.executable, "-m", "meeko.cli.mk_prepare_receptor",
                   "--read_pdb", str(filtrado), "-o", str(wd / f"{pdb_id}_rec"), "-p",
                   "--box_center", str(c[0]), str(c[1]), str(c[2]),
                   "--box_size", str(s[0]), str(s[1]), str(s[2]),
                   "--default_altloc", "A", "-a"]
            if plantillas:
                cmd += ["--set_template", ",".join(plantillas)]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=1200)
            if rec_pdbqt.exists():
                break
            salida = (r.stderr or "") + (r.stdout or "")
            claves = [c for c in re.findall(
                r"residue_key='([^']+)', \d+ have passed: \['HI", salida)
                if not any(p.startswith(c + "=") for p in plantillas)]
            if not claves:
                break
            plantillas.extend(f"{c}=HIE" for c in dict.fromkeys(claves))
        if plantillas:
            res["set_template"] = plantillas
        if not rec_pdbqt.exists():
            res["error"] = "MEEKO_RECEPTOR_FALLO"
            res["detalle"] = ((r.stderr or r.stdout) or "")[-400:]
            return res
    if any("HOH" in l for l in rec_pdbqt.read_text(encoding="utf-8", errors="replace").splitlines()):
        res["error"] = "RECEPTOR_CON_AGUAS"
        return res

    lig_pdb = wd / f"{pdb_id}_lig.pdb"
    n_at = extraer_ligando(pdb_path, item["ligando_nativo"]["id"], lig_pdb)
    if n_at == 0:
        res["error"] = "LIGANDO_NO_EXTRAIDO"
        return res

    lig_sdf = wd / f"{pdb_id}_lig.sdf"
    lig_pdbqt = wd / f"{pdb_id}_lig.pdbqt"
    if not lig_pdbqt.exists():
        try:
            from openbabel import pybel
            mol = next(pybel.readfile("pdb", str(lig_pdb)))
            mol.addh()
            mol.write("sdf", str(lig_sdf), overwrite=True)
        except Exception as e:
            res["error"] = "OPENBABEL_FALLO"
            res["detalle"] = str(e)[-300:]
            return res
        r = subprocess.run([sys.executable, "-m", "meeko.cli.mk_prepare_ligand",
                            "-i", str(lig_sdf), "-o", str(lig_pdbqt)],
                           capture_output=True, text=True, timeout=600)
        if not lig_pdbqt.exists():
            # Desviación declarada: la percepción de enlaces de Open Babel desde
            # coordenadas produce a veces valencias imposibles (p. ej. carbono con
            # 5 enlaces) que RDKit rechaza dentro de Meeko. Se reintenta con
            # `rdDetermineBonds` de RDKit probando cargas netas en ORDEN FIJO
            # (0, -1, -2, -3, -4, +1, +2) y quedándose con la primera que sanitiza.
            # La geometría cristalográfica no se toca: solo el orden de enlace.
            detalle_ob = ((r.stderr or r.stdout) or "")[-400:]
            sdf_rd = _reparar_ligando(lig_sdf, wd / f"{pdb_id}_lig_rdkit.sdf")
            if sdf_rd is None:
                res["error"] = "MEEKO_LIGANDO_FALLO"
                res["detalle"] = detalle_ob
                return res
            lig_sdf = sdf_rd[0]
            res["desviacion_ligando"] = {
                "motivo": "representacion de valencia de openbabel rechazada por RDKit",
                "arreglo": sdf_rd[1],
                "detalle_openbabel": detalle_ob,
            }
            r = subprocess.run([sys.executable, "-m", "meeko.cli.mk_prepare_ligand",
                                "-i", str(lig_sdf), "-o", str(lig_pdbqt)],
                               capture_output=True, text=True, timeout=600)
            if not lig_pdbqt.exists():
                res["error"] = "MEEKO_LIGANDO_FALLO_TRAS_RDKIT"
                res["detalle"] = ((r.stderr or r.stdout) or "")[-400:]
                return res
    res["ligando_sdf"] = lig_sdf.name

    res["receptor_sha256"] = sha256_file(rec_pdbqt)
    res["ligando_sha256"] = sha256_file(lig_pdbqt)
    res["n_atomos_ligando_pdb"] = n_at
    res["ok"] = True
    return res


# ── Docking ────────────────────────────────────────────────────────────────

def _rmsd_top1(out_pdbqt: Path, ref_sdf: Path) -> Tuple[Optional[float], Optional[int], Optional[float]]:
    """(RMSD in situ de la pose top-1, n_poses, RMSD del mejor modo de las 9)."""
    from meeko import PDBQTMolecule, RDKitMolCreate
    from rdkit import Chem
    from rdkit.Chem import rdMolAlign

    pm = PDBQTMolecule.from_file(str(out_pdbqt), skip_typing=True)
    mols = RDKitMolCreate.from_pdbqt_mol(pm)
    if not mols or mols[0] is None:
        return None, None, None
    docked = Chem.RemoveHs(mols[0])
    ref = Chem.RemoveHs(Chem.SDMolSupplier(str(ref_sdf), removeHs=False)[0])
    if docked.GetNumAtoms() != ref.GetNumAtoms():
        return None, docked.GetNumConformers(), None

    rmsds = []
    for i in range(docked.GetNumConformers()):
        probe = Chem.Mol(docked)
        probe.RemoveAllConformers()
        probe.AddConformer(docked.GetConformer(i), assignId=True)
        try:
            rmsds.append(float(rdMolAlign.CalcRMS(probe, ref)))
        except Exception:
            rmsds.append(float("nan"))
    if not rmsds:
        return None, 0, None
    return round(rmsds[0], 3), len(rmsds), round(min(rmsds), 3)


def _una_corrida(job: Dict[str, Any]) -> Dict[str, Any]:
    pdb_id, brazo, seed = job["pdb_id"], job["brazo"], job["seed"]
    c, s = job["centro"], job["tam"]
    wd = WORK / pdb_id
    out = wd / f"out_{brazo}_{seed}{job.get('sufijo', '')}.pdbqt"
    cmd = [str(VINA), "--receptor", str(wd / f"{pdb_id}_rec.pdbqt"),
           "--ligand", str(wd / f"{pdb_id}_lig.pdbqt"),
           "--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
           "--size_x", str(s[0]), "--size_y", str(s[1]), "--size_z", str(s[2]),
           "--exhaustiveness", str(EXHAUSTIVENESS), "--num_modes", str(NUM_MODES),
           "--seed", str(seed), "--cpu", str(CPU), "--out", str(out)]
    t0 = time.time()
    fila: Dict[str, Any] = {"pdb_id": pdb_id, "brazo": brazo, "seed": seed,
                            "centro": list(c), "tamano": list(s),
                            "severidad": job["severidad"], "estrato_exp": job["estrato_exp"]}
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
        rc = r.returncode
    except subprocess.TimeoutExpired:
        rc = -9
    fila["rc"] = rc
    fila["wall_s"] = round(time.time() - t0, 2)

    if rc != 0 or not out.exists() or out.stat().st_size == 0:
        fila["valido"] = False
        return fila

    scores = []
    for l in out.read_text(encoding="utf-8", errors="replace").splitlines():
        if l.startswith("REMARK VINA RESULT"):
            try:
                scores.append(float(l.split()[3]))
            except (IndexError, ValueError):
                pass
    fila["n_modos"] = len(scores)
    fila["scores_finitos"] = bool(scores) and all(math.isfinite(x) for x in scores)
    fila["score_top1"] = round(scores[0], 3) if scores else None
    ref_sdf = wd / f"{pdb_id}_lig_rdkit.sdf"
    if not ref_sdf.exists():
        ref_sdf = wd / f"{pdb_id}_lig.sdf"
    try:
        rmsd, n_poses, rmsd_mejor = _rmsd_top1(out, ref_sdf)
        fila["rmsd_top1"] = rmsd
        fila["rmsd_mejor_de_9"] = rmsd_mejor
        fila["n_poses_reconstruidas"] = n_poses
    except Exception as e:
        fila["rmsd_top1"] = None
        fila["error_rmsd"] = str(e)[-200:]
    fila["valido"] = bool(
        scores and fila["scores_finitos"] and 1 <= len(scores) <= NUM_MODES
        and fila.get("rmsd_top1") is not None)
    fila["exito"] = bool(fila.get("rmsd_top1") is not None
                         and fila["rmsd_top1"] <= RMSD_EXITO_A)
    return fila


# ── Cohorte ────────────────────────────────────────────────────────────────

def construir_cohorte() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    geo = json.loads((PRE_DIR / "geometria_preflight.json").read_text(encoding="utf-8"))
    geo_ok = {g["pdb_id"]: g for g in geo if "error" not in g}
    r1 = {r["pdb_id"]: r for r in (
        json.loads(l) for l in (R1_DIR / "per_complex.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip())}

    accionables = sorted(p for p, g in geo_ok.items()
                         if g["severidad"] in {"S1_CRITICO", "S2_GRAVE"})
    pool_s0 = sorted(p for p, g in geo_ok.items() if g["severidad"] == "S0_SIN_EXCEPCION")
    control = sorted(random.Random(SEED_MUESTREO).sample(pool_s0, min(N_CONTROL, len(pool_s0))))

    cohorte = []
    for pdb_id in accionables + control:
        g, r = geo_ok[pdb_id], r1[pdb_id]
        cohorte.append({
            "pdb_id": pdb_id,
            "pdb_ruta": r["pdb_ruta"],
            "familia": r["familia"],
            "severidad": r["severidad"],
            "estrato_exp": "ACCIONABLE" if pdb_id in accionables else "CONTROL",
            "grid_centro": r["grid_centro"],
            "grid_tam": r["grid_tam"],
            "ligando_nativo": r["ligando_nativo"],
            "pockets": g["pockets"],
        })
    meta = {"n_accionables": len(accionables), "n_control": len(control),
            "pool_s0": len(pool_s0), "seed_muestreo": SEED_MUESTREO,
            "control": control}
    return cohorte, meta


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-03: reparación de grid por predicción de pocket")
    ap.add_argument("--solo-preparacion", action="store_true", help="prepara receptores/ligandos y sale")
    ap.add_argument("--limite", type=int, default=None, help="limita la cohorte (smoke test)")
    ap.add_argument("--workers", type=int, default=WORKERS)
    args = ap.parse_args()

    t0 = time.time()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)
    hashes_pre = {p.name: sha256_file(p) for p in RUTAS_PROTEGIDAS if p.exists()}

    cohorte, meta = construir_cohorte()
    if args.limite:
        cohorte = cohorte[:args.limite]
    print(f"[REC-03] cohorte: {len(cohorte)} targets "
          f"({meta['n_accionables']} accionables + {meta['n_control']} control de "
          f"{meta['pool_s0']} S0 elegibles, seed {meta['seed_muestreo']})", flush=True)

    # ── Preparación en paralelo ──
    preparados: Dict[str, Dict[str, Any]] = {}
    fallos: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=min(args.workers, 8)) as ex:
        for res in ex.map(preparar_target, cohorte):
            if res.get("ok"):
                preparados[res["pdb_id"]] = res
            else:
                fallos.append({"fase": "preparacion", **res})
                print(f"  [prep] {res['pdb_id']} FALLO {res.get('error')}", flush=True)
    print(f"[REC-03] preparados {len(preparados)}/{len(cohorte)}", flush=True)
    if args.solo_preparacion:
        print(json.dumps(fallos, ensure_ascii=False, indent=1)[:2000])
        return 0

    # ── Jobs de docking: 4 cajas x 3 semillas por target ──
    jobs: List[Dict[str, Any]] = []
    for t in cohorte:
        if t["pdb_id"] not in preparados:
            continue
        cajas = [("G_CAT", t["grid_centro"])]
        for p in t["pockets"]:
            cajas.append((f"G_MP{p['rank']}", p["centro"]))
        for brazo, centro in cajas:
            for seed in SEEDS:
                jobs.append({"pdb_id": t["pdb_id"], "brazo": brazo, "seed": seed,
                             "centro": centro, "tam": t["grid_tam"],
                             "severidad": t["severidad"], "estrato_exp": t["estrato_exp"]})
    print(f"[REC-03] {len(jobs)} corridas de Vina con {args.workers} procesos "
          f"(exh={EXHAUSTIVENESS}, semillas {SEEDS})", flush=True)

    filas: List[Dict[str, Any]] = []
    hechas = 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for fila in ex.map(_una_corrida, jobs, chunksize=1):
            filas.append(fila)
            hechas += 1
            if not fila.get("valido"):
                fallos.append({"fase": "docking", **{k: fila[k] for k in
                                                     ("pdb_id", "brazo", "seed", "rc")}})
            if hechas % 10 == 0 or hechas == len(jobs):
                buenos = sum(1 for f in filas if f.get("exito"))
                print(f"  [{hechas}/{len(jobs)}] exitos acumulados={buenos} "
                      f"({round(time.time() - t0)}s)", flush=True)

    # ── G5: determinismo sobre los 4 primeros targets alfabéticos (G_CAT, seed 42) ──
    det_ids = sorted(preparados)[:4]
    det_jobs = [dict(j, sufijo="_det") for j in jobs
                if j["pdb_id"] in det_ids and j["brazo"] == "G_CAT" and j["seed"] == 42]
    print(f"[REC-03] determinismo: repitiendo {len(det_jobs)} corridas", flush=True)
    determinismo = []
    with ProcessPoolExecutor(max_workers=min(args.workers, len(det_jobs) or 1)) as ex:
        for rep in ex.map(_una_corrida, det_jobs, chunksize=1):
            orig = next((f for f in filas if f["pdb_id"] == rep["pdb_id"]
                         and f["brazo"] == "G_CAT" and f["seed"] == 42), None)
            determinismo.append({
                "pdb_id": rep["pdb_id"],
                "score_original": orig.get("score_top1") if orig else None,
                "score_repeticion": rep.get("score_top1"),
                "rmsd_original": orig.get("rmsd_top1") if orig else None,
                "rmsd_repeticion": rep.get("rmsd_top1"),
                "identico": bool(orig and orig.get("score_top1") == rep.get("score_top1")
                                 and orig.get("rmsd_top1") == rep.get("rmsd_top1")),
            })

    escribir_resultados(filas, fallos, cohorte, preparados, meta, hashes_pre, t0, determinismo)
    return 0


def escribir_resultados(filas, fallos, cohorte, preparados, meta, hashes_pre, t0,
                        determinismo=None):
    from statistics import median

    por_target: Dict[str, Dict[str, Any]] = {}
    for f in filas:
        por_target.setdefault(f["pdb_id"], {}).setdefault(f["brazo"], []).append(f)

    # Brazo derivado: entre G_MP1..3 se elige por MEJOR SCORE (nunca por RMSD)
    resumen_target = []
    for pdb_id, brazos in por_target.items():
        info = next(t for t in cohorte if t["pdb_id"] == pdb_id)
        fila = {"pdb_id": pdb_id, "severidad": info["severidad"],
                "estrato_exp": info["estrato_exp"], "familia": info["familia"]}
        for brazo, corridas in brazos.items():
            val = [c for c in corridas if c.get("valido")]
            fila[brazo] = {
                "n_validas": len(val),
                "exitos": sum(1 for c in val if c.get("exito")),
                "rmsd_mediana": round(median([c["rmsd_top1"] for c in val]), 3) if val else None,
                "rmsd_min": round(min([c["rmsd_top1"] for c in val]), 3) if val else None,
                "score_mediana": round(median([c["score_top1"] for c in val]), 3) if val else None,
            }
        sel = []
        for seed in SEEDS:
            cands = [c for b, cs in brazos.items() if b.startswith("G_MP")
                     for c in cs if c["seed"] == seed and c.get("valido")]
            if cands:
                mejor = min(cands, key=lambda c: c["score_top1"])
                sel.append({"seed": seed, "brazo": mejor["brazo"],
                            "score": mejor["score_top1"], "rmsd": mejor["rmsd_top1"],
                            "exito": mejor["exito"]})
        fila["G_MP_SCORE"] = {
            "n_validas": len(sel),
            "exitos": sum(1 for s in sel if s["exito"]),
            "rmsd_mediana": round(median([s["rmsd"] for s in sel]), 3) if sel else None,
            "selecciones": sel,
        }
        resumen_target.append(fila)

    def _tasa(estrato: str, brazo: str) -> Dict[str, Any]:
        sub = [r for r in resumen_target if r["estrato_exp"] == estrato and brazo in r]
        con_exito = [r for r in sub if r[brazo]["exitos"] >= 2]  # mayoría de 3 semillas
        rm = [r[brazo]["rmsd_mediana"] for r in sub if r[brazo]["rmsd_mediana"] is not None]
        return {"n": len(sub), "targets_reparados": len(con_exito),
                "tasa": round(len(con_exito) / len(sub), 4) if sub else None,
                "rmsd_mediana_global": round(median(rm), 3) if rm else None}

    brazos_todos = ["G_CAT", "G_MP1", "G_MP2", "G_MP3", "G_MP_SCORE"]
    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "cohorte": meta,
        "config": {"exhaustiveness": EXHAUSTIVENESS, "num_modes": NUM_MODES, "cpu": CPU,
                   "seeds": list(SEEDS), "rmsd_exito_A": RMSD_EXITO_A,
                   "timeout_s": TIMEOUT_S,
                   "criterio_rmsd": "rdMolAlign.CalcRMS in situ (sin realinear), simetrico",
                   "caja": "tamano del catalogo en los 4 brazos; unica variable = el centro",
                   "receptor": "solo ATOM, todas las cadenas, sin aguas ni HETATM",
                   "seleccion_G_MP_SCORE": "mejor score de Vina entre G_MP1..3; nunca por RMSD"},
        "n_corridas": len(filas),
        "n_validas": sum(1 for f in filas if f.get("valido")),
        "por_brazo_y_estrato": {
            brazo: {estr: _tasa(estr, brazo) for estr in ("ACCIONABLE", "CONTROL")}
            for brazo in brazos_todos
        },
        "hashes_pre": hashes_pre,
        "hashes_post": {p.name: sha256_file(p) for p in RUTAS_PROTEGIDAS if p.exists()},
        "entrada_sellada": {
            "REC-01-R1_per_complex_sha256": sha256_file(R1_DIR / "per_complex.jsonl"),
            "REC-03-PRE_geometria_sha256": sha256_file(PRE_DIR / "geometria_preflight.json"),
        },
        "entorno": {
            "so": platform.system(), "python": platform.python_version(),
            "vina_sha256": sha256_file(VINA) if VINA.exists() else None,
        },
    }
    acc_mp = metrics["por_brazo_y_estrato"]["G_MP_SCORE"]["ACCIONABLE"]
    ctl_mp = metrics["por_brazo_y_estrato"]["G_MP_SCORE"]["CONTROL"]
    ctl_cat = metrics["por_brazo_y_estrato"]["G_CAT"]["CONTROL"]
    minimo_control = math.ceil(0.7 * ctl_cat["targets_reparados"])
    tasa_validez = metrics["n_validas"] / len(filas) if filas else 0.0
    metrics["determinismo"] = determinismo or []
    metrics["gates"] = {
        "G1_validez": {
            "criterio": ">=98% de corridas validas (rc=0, 1..9 modos, scores finitos, RMSD reconstruible)",
            "tasa_validez": round(tasa_validez, 4),
            "n_invalidas": len(filas) - metrics["n_validas"],
            "pass": tasa_validez >= 0.98,
        },
        "G2_solo_lectura": {
            "criterio": "curated_targets.json/.csv conservan su SHA-256",
            "pass": metrics["hashes_pre"] == metrics["hashes_post"],
        },
        "G3_reparacion": {
            "criterio": "G_MP_SCORE repara >=5 de los 25 accionables (RMSD top-1 <= 2.0 A en >=2 de 3 semillas)",
            "reparados": acc_mp["targets_reparados"], "de": acc_mp["n"],
            "techo_geometrico_declarado": 10,
            "pass": acc_mp["targets_reparados"] >= 5,
        },
        "G4_no_regresion": {
            "criterio": "en el control, G_MP_SCORE conserva >=70% de los targets que repara G_CAT",
            "g_cat": ctl_cat["targets_reparados"], "g_mp_score": ctl_mp["targets_reparados"],
            "minimo_exigido": minimo_control,
            "pass": ctl_mp["targets_reparados"] >= minimo_control,
        },
        "G5_determinismo": {
            "criterio": "misma semilla -> mismo score top-1 y mismo RMSD al repetir (4 targets, G_CAT, seed 42)",
            "n": len(determinismo or []),
            "identicos": sum(1 for d in (determinismo or []) if d["identico"]),
            "pass": bool(determinismo) and all(d["identico"] for d in determinismo),
        },
    }
    metrics["decision"] = (
        "GO" if all(g["pass"] for g in metrics["gates"].values()) else "NO_GO")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in resumen_target:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "corridas.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in filas:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in fallos:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("\n[REC-03] resultado por brazo (targets con >=2 de 3 semillas a <=2.0 A):")
    for brazo in brazos_todos:
        a = metrics["por_brazo_y_estrato"][brazo]["ACCIONABLE"]
        c = metrics["por_brazo_y_estrato"][brazo]["CONTROL"]
        print(f"  {brazo:<12} accionables {a['targets_reparados']}/{a['n']} "
              f"(mediana RMSD {a['rmsd_mediana_global']} A) | "
              f"control {c['targets_reparados']}/{c['n']} "
              f"(mediana {c['rmsd_mediana_global']} A)")


if __name__ == "__main__":
    sys.exit(main())
