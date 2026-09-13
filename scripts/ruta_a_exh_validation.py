# -*- coding: utf-8 -*-
"""ruta_a_exh_validation.py — Ruta A: valida si el docking flexible de Vina con
exhaustiveness bajo (exh=1, 2, 4) preserva el mismo ranking que la referencia
exh=8 sobre una cohorte estratificada de complejos PDBbind.

EXPERIMENTO PRE-REGISTRADO (método científico: hipótesis antes de ejecutar,
validación + refutación, criterios de éxito definidos).

Hipótesis H-A: Vina flexible con exh in {1, 2, 4} produce el mismo ranking de
complejos que exh=8 (el de referencia), medido por:
  (a) Spearman de vina_best_score (exhN vs exh8).
  (b) Spearman / mediana de delta-RMSD de la mejor pose al cristal (exhN vs exh8).

Criterio de éxito (pre-registrado):
  exh=2 debe alcanzar Spearman rho >= 0.9 en el ranking de vina_best_score vs
  la referencia exh=8, Y RMSD-comparable (mediana |delta RMSD| <= 1.0 Å, o
  Spearman del RMSD rho >= 0.7). Si exh=2 pasa, los 74 complejos que hacen
  timeout a exh=8 pueden re-dockearse a exh=2 -> set de entrenamiento homogéneo
  sin MolFlex en producción.

Salvaguarda de refutación: si exh=1/2 produce poses basura (vina_best_score >
-2.0 kcal/mol, o RMSD > 10 Å para la mejor pose), ese nivel exh se marca FAIL
independientemente de la correlación de ranking — la búsqueda colapsó, no solo
se abarató.

Diseño (muestreo estratificado):
  De los 218 complejos con _out.pdbqt en vina_redock_work/ (runs exh=8 con pose
  guardada), se toman N complejos (default 30):
    - la mitad "fáciles" (< 15 enlaces rotables)
    - la mitad "difíciles" (>= 15 enlaces rotables)
  Si no hay suficientes difíciles, se completa con fáciles (se reporta el split
  real). Enlaces rotables con RDKit: Descriptors.NumRotatableBonds(AddHs(mol)).
  Semilla fija (random.Random(42)) para reproducibilidad. Pool de candidatos
  ordenado alfabéticamente antes de muestrear.

Referencia exh=8 (NO se re-corre):
  - vina_best_score: de data/pdbbind/vina_redock_cache/{pid}.json (dict plano).
  - rmsd_best_pose: flexible_desde_disco(pid) reutilizado de molflex_exp_v3.

Datos nuevos exh in {1, 2, 4}: se dockea cada complejo 3 veces (exh=1, 2, 4),
replicando redock_flexible_referencia de molflex_exp_v3 EXACTAMENTE, solo
cambiando exh. Se captura vina_best_score (parseado de stdout) y rmsd_best_pose
(parseado del _out.pdbqt NUEVO con el mismo pipeline de RMSD).

Salida: scripts/artifacts_ruta_a.json (escrito tras CADA dock: una caída pierde
a lo sumo un dock). Reanudable: salta (pid, exh) ya presentes en el artifacto.

Uso (CLI):
  python scripts/ruta_a_exh_validation.py            # correr los 90 docks
  python scripts/ruta_a_exh_validation.py --dry-run  # solo imprimir la cohorte
  python scripts/ruta_a_exh_validation.py --n 20     # override del tamaño
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# El motor molflex expone VINA, PDBBIND, leer_ligando, escribir_pdbqt,
# _args_box, parsear_scores_tabla, parsear_out_vina, coords_pose_a_por_mol,
# rmsd_pesados, y rp (redock_pdbbind) para preparar el receptor/centro de caja.
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402

# Reutilizar flexible_desde_disco para la referencia exh=8 desde disco:
from molflex_exp_v3 import flexible_desde_disco  # noqa: E402

# Constantes del protocolo (idénticas a molflex_exp_v3.redock_flexible_referencia,
# solo exh cambia — nunca 8 aquí, ese es el de referencia en disco).
EXH_NIVELES = [1, 2, 4]
EXH_REFERENCIA = 8
NUM_MODES = 9
CPU = 1
FLEX_TIMEOUT = 300   # mismo timeout que Fase B
MAX_WORKERS = 4      # maquina con nucleos limitados, --cpu 1 por Vina (patron v3)
SEED = 42              # semilla de SELECCION DE COHORTE (no del dock)
SEMILLA_VINA = 42      # seed de DOCKING Vina preregistrada 2026-08-15 (FND-06,
                       # cierre de garantia futura): TODAS las corridas futuras
                       # de ruta_a la pasan explicitamente via --seed; emitida
                       # como seed_docking en provenance.json
UMBRAL_ROT = 15      # < 15 facil, >= 15 dificil
DEFAULT_N = 30
GARBAGE_SCORE = -2.0        # kcal/mol: score peor que esto = busqueda colapsada
GARBAGE_RMSD = 10.0         # Angstrom: RMSD peor que esto = pose sin sentido
CRIT_SPEARMAN_SCORE = 0.9    # rho >= 0.9 en ranking de vina_best_score
CRIT_MEDIAN_DELTA_RMSD = 1.0 # mediana |delta RMSD| <= 1.0 Å
CRIT_SPEARMAN_RMSD = 0.7     # o rho del RMSD >= 0.7

WORK = PROJECT_ROOT / "tmp" / "ruta_a"
ARTIFACTO = PROJECT_ROOT / "scripts" / "artifacts_ruta_a.json"


# ─────────────────────── cohort estratificado ───────────────────────────

def _enlaces_rotables(pid: str) -> int | None:
    """Número de enlaces rotables: Descriptors.NumRotatableBonds(AddHs(mol))
    donde mol se lee de data/pdbbind/{pid}/{pid}_ligand.sdf.
    Devuelve None si el SDF no se puede leer."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors

    sdf = mf.PDBBIND / pid / f"{pid}_ligand.sdf"
    if not sdf.exists():
        return None
    m = mf.leer_ligando(str(sdf))
    if m is None:
        return None
    try:
        mh = Chem.AddHs(m)
        return int(Descriptors.NumRotatableBonds(mh))
    except Exception:
        return None


def candidatos_con_out() -> list:
    """PIDs con _out.pdbqt en vina_redock_work/ (runs exh=8 con pose guardada).
    Pool ordenado alfabéticamente (la semilla muestrea sobre este orden)."""
    work = mf.PDBBIND / "vina_redock_work"
    out = []
    if not work.exists():
        return out
    for d in sorted(work.iterdir(), key=lambda p: p.name):
        if not d.is_dir():
            continue
        pid = d.name
        if (d / f"{pid}_out.pdbqt").exists():
            out.append(pid)
    return out


def seleccionar_cohorte(n: int, seed: int) -> tuple[dict, dict]:
    """Muestreo estratificado con semilla fija.

    Devuelve (cohort, rot):
      cohort -> {"facil": [pid...], "dificil": [pid...]}
      rot     -> {pid: int}

    Estratos: facil (< UMBRAL_ROT rotables), dificil (>= UMBRAL_ROT rotables).
    La mitad de la muestra a cada estrato. Si no hay suficientes dificiles, se
    completa con faciles (el split real se reporta en el output).
    """
    pool = candidatos_con_out()
    # Filtrar a los que se les pueda contar rotables (SDF legible).
    pool_con_rot = []
    rot = {}
    for pid in pool:
        r = _enlaces_rotables(pid)
        if r is None:
            continue
        rot[pid] = r
        pool_con_rot.append(pid)

    faciles = sorted([p for p in pool_con_rot if rot[p] < UMBRAL_ROT])
    dificiles = sorted([p for p in pool_con_rot if rot[p] >= UMBRAL_ROT])

    rng = random.Random(seed)
    # n_objetivo por estrato (redondeo hacia arriba del facil, el resto al dificil).
    n_facil = math.ceil(n / 2)
    n_dificil = n - n_facil

    facilitos = rng.sample(faciles, min(n_facil, len(faciles)))
    dificilitos = rng.sample(dificiles, min(n_dificil, len(dificiles)))

    # Si faltan dificiles, rellenar con faciles restantes.
    faltan = n - (len(facilitos) + len(dificilitos))
    if faltan > 0:
        restantes_faciles = [p for p in faciles if p not in facilitos]
        extra = rng.sample(restantes_faciles, min(faltan, len(restantes_faciles)))
        facilitos = facilitos + extra

    cohort = {
        "facil": facilitos,
        "dificil": dificilitos,
    }
    return cohort, rot


# ─────────────────────── RMSD desde un _out.pdbqt cualquiera ────────────

def rmsd_pose_exh(pid: str, out_pdbqt_path, crystal, mapa: dict) -> float | None:
    """RMSD al cristal de la mejor pose de un _out.pdbqt (referencia exh=8 en
    disco, o un run NUEVO exh=1/2/4 en tmp/). Mismo pipeline que
    flexible_desde_disco: parsear_out_vina -> modelos[0][1] ->
    coords_pose_a_por_mol -> rmsd_pose_pocket (marco del pocket, SIN alinear:
    mide la colocación real, no solo la geometría interna). Devuelve None si
    no es recuperable.

    crystal: mol RDKit del SDF (sin AddHs, como lo devuelve leer_ligando).
    mapa: serial_a_mol del PDBQT flexible meeko del MISMO SDF (el orden
    atómico es idéntico para el mismo SDF + misma version de meeko).
    """
    p = Path(out_pdbqt_path)
    if not p.exists():
        return None
    try:
        modelos = mf.parsear_out_vina(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not modelos or modelos[0][1] is None:
        return None
    por_mol = mf.coords_pose_a_por_mol(modelos[0][1], mapa)
    rmsd = mf.rmsd_pose_pocket(crystal, por_mol)
    return round(rmsd, 3) if rmsd is not None else None


def referencia_exh8_para(pid: str) -> dict:
    """Lee la referencia exh=8 desde disco (NO la re-corre):
      - vina_best_score: de vina_redock_cache/{pid}.json
      - rmsd_best_pose: de flexible_desde_disco(pid)
    Devuelve {} si no hay cache, y rmsd=None si la pose no es recuperable.
    """
    cache = mf.PDBBIND / "vina_redock_cache" / f"{pid}.json"
    ref: dict = {}
    if cache.exists():
        try:
            ref = json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            ref = {}
    rmsd = None
    fuente_rmsd = None
    d = flexible_desde_disco(pid)
    if d and d.get("ok"):
        rmsd = d.get("rmsd_best_pose")
        fuente_rmsd = d.get("fuente")
    return {
        "vina_best_score": ref.get("vina_best_score"),
        "rmsd_best_pose": rmsd,
        "fuente": fuente_rmsd,
    }


# ─────────────────────── worker: un dock flexible con exh=N ──────────────

def dock_one_exh(args_tuple) -> dict:
    """Un dock flexible con exh=N. Replica redock_flexible_referencia de
    molflex_exp_v3.py EXACTAMENTE, solo cambiando exh. Devuelve el dict de
    resultado (sin la referencia exh=8 — esa se une despues en main)."""
    pid, exh, rot_bonds, estrato = args_tuple
    base = {
        "pdb_id": pid, "exh": exh, "rotatables": rot_bonds, "estrato": estrato,
        "ok": False, "reason": None, "wall_s": 0.0,
        "vina_best_score": None,
        "pose_score_variance": None,
        "pose_score_range": None,
        "poses_passing_ratio": None,
        "rmsd_best_pose": None,
    }

    from meeko import MoleculePreparation
    from rdkit import Chem

    w = WORK / pid / f"exh{exh}"
    w.mkdir(parents=True, exist_ok=True)
    sdf = mf.PDBBIND / pid / f"{pid}_ligand.sdf"
    prot = mf.PDBBIND / pid / f"{pid}_protein.pdb"

    # 1. SDF cristalografico (leo una sola vez; el cristal se reusa para RMSD).
    crystal = mf.leer_ligando(str(sdf))
    if crystal is None:
        base["reason"] = "sdf_unreadable"
        return base

    # 2. Receptor PDBQT.
    rec = str(w / "rec.pdbqt")
    if not mf.rp.prepare_receptor_pdbqt(str(prot), rec):
        base["reason"] = "receptor_prep_failed"
        return base

    # 3. Centro de caja (centroide del ligando cristalográfico).
    center = mf.rp.find_binding_center(str(sdf))
    if center is None:
        base["reason"] = "binding_center_failed"
        return base

    # 4. Preparacion meeko del ligando: PDBQT FLEXIBLE + mapa serial->mol.
    # OJO (bug corregido 2026-08-14): escribir_pdbqt devuelve
    # (rigid_str, flex_str, serial_a_mol, err). Desempaquetar mal ponia el
    # PDBQT RIGIDO como ligando -> Vina dockeaba rigido (INTRA 0.000).
    try:
        mh = Chem.AddHs(crystal)
        prep = MoleculePreparation()
        setups = prep.prepare(mh)
        _rigid, flex_str, mapa, _err = mf.escribir_pdbqt(setups[0])
        if not flex_str or not mapa:
            base["reason"] = "meeko_failed"
            return base
    except Exception as e:  # noqa: BLE001
        base["reason"] = f"meeko: {type(e).__name__}"
        return base
    lig = str(w / "lig.pdbqt")
    Path(lig).write_text(flex_str, encoding="utf-8")

    # 5. Comando Vina (idéntico al de referencia, solo exh cambia) + semilla
    #    de docking preregistrada (FND-06, 2026-08-15).
    out = str(w / "out.pdbqt")
    cmd = [mf.VINA, "--receptor", rec, "--ligand", lig] + mf._args_box(center) + [
        "--exhaustiveness", str(exh), "--num_modes", str(NUM_MODES),
        "--seed", str(SEMILLA_VINA),
        "--cpu", str(CPU), "--out", out]

    # 6. Ejecutar Vina con timeout de 300s (igual que Fase B).
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=FLEX_TIMEOUT)
    except subprocess.TimeoutExpired:
        base["reason"] = "vina_timeout_300s"
        base["wall_s"] = round(time.monotonic() - t0, 1)
        return base
    dt = round(time.monotonic() - t0, 1)
    base["wall_s"] = dt
    if r.returncode != 0:
        base["reason"] = f"rc={r.returncode}"
        return base

    # 7. Scores (columna de afinidad de la tabla de Vina).
    scores = mf.parsear_scores_tabla(r.stdout)
    if not scores:
        base["reason"] = "no_scores"
        return base

    # 8. RMSD de la mejor pose (del _out.pdbqt NUEVO que este run escribió).
    rmsd = rmsd_pose_exh(pid, out, crystal, mapa)

    # 9. Features del caché (misma semantica que vina_redock_cache JSON).
    import numpy as np
    base.update({
        "ok": True,
        "vina_best_score": round(scores[0], 4),
        "pose_score_variance": float(np.var(scores)) if len(scores) > 1 else 0.0,
        "pose_score_range": round(scores[-1] - scores[0], 4) if len(scores) > 1 else 0.0,
        "poses_passing_ratio": round(sum(1 for s in scores if s < -5.0) / len(scores), 6),
        "rmsd_best_pose": rmsd,
    })

    # FND-06: provenance canonico por corrida (key = pid|ruta_a|exh{N}).
    # Emision post-dock, nunca tumba el dock.
    try:
        _escribir_provenance(w, pid, exh, center)
    except Exception:
        pass
    return base


def _escribir_provenance(w, pid, exh, center) -> None:
    """Escribe provenance.json canonico (FND-06) en el workdir pid/exh{N}.

    Registro del contrato v1.1 con clave pid|ruta_a|exh{N}. El ligando es la
    conformacion cristalografica (conformer_id="crystal"): no hay generacion
    estocastica de conformeros, por eso seed_conformer="crystal";
    seed_docking es la semilla preregistrada de Vina (--seed 42).
    """
    registro = {
        "key": f"{pid}|ruta_a|exh{exh}",
        "pid": pid,
        "source": "ruta_a",
        "file_stem": f"exh{exh}",
        "seed_conformer": "crystal",
        "seed_docking": SEMILLA_VINA,
        "conformer_id": "crystal",
        "exhaustiveness": exh,
        "num_modes": NUM_MODES,
        "box": {"center": [round(float(c), 3) for c in center],
                "size": [25.0, 25.0, 25.0],
                "method": "center_from_crystal_ligand"},
        "preparation": {
            "ligand": {"method": "meeko_molecule_preparation_conformacion_cristal",
                       "tool": "meeko", "version": mf.VERSION_MEEKO},
            "receptor": {"protonation": "pdb_original",
                         "tool": "openbabel_pdb2pdbqt_rigido"},
        },
        "engine": {"name": "vina", "version": mf.version_vina()},
        "experiment_id": "ruta_a_exh_validation",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    Path(w / "provenance.json").write_text(
        json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")


# ─────────────────────── spearman (empates) ────────────────────────────

def spearman(xs: list, ys: list):
    """Spearman con empates (rangos promediados). scipy si esta disponible;
    si no, implementacion manual equivalente. Devuelve None si < 2 pares."""
    import numpy as np

    if len(xs) != len(ys) or len(xs) < 2:
        return None
    x = np.asarray(xs, dtype=float)
    y = np.asarray(ys, dtype=float)
    if x.size < 2 or y.size < 2:
        return None
    try:
        from scipy.stats import spearmanr
        return float(spearmanr(x, y)[0])
    except Exception:
        pass
    # Fallback manual: Pearson sobre rangos con promedios para empates.
    def rangos(v):
        order = np.argsort(v, kind="mergesort")
        ranks = np.empty_like(v, dtype=float)
        ranks[order] = np.arange(1, v.size + 1)
        _, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        r = np.zeros_like(v, dtype=float)
        s = 0
        for k, c in enumerate(cnt):
            r[inv == k] = s + (c + 1) / 2.0
            s += c
        return r
    rx, ry = rangos(x), rangos(y)
    return float(np.corrcoef(rx, ry)[0, 1])


# ─────────────────────── analisis ───────────────────────────────────────

def analizar(results: list, ref_exh8: dict) -> dict:
    """Computa por nivel exh: Spearman(score), Spearman(rmsd), mediana
    |delta rmsd|, flag de basura y veredicto. Devuelve recomendacion textual."""
    analisis: dict = {}
    veredictos: dict = {}

    for exh in EXH_NIVELES:
        # Emparejar por pid: (ref, nuevo) solo cuando ambos validos.
        pares_score = []
        pares_rmsd = []
        garbage = False
        sub = [r for r in results if r.get("exh") == exh and r.get("ok")]

        for r in sub:
            pid = r["pdb_id"]
            ref = ref_exh8.get(pid, {})
            ref_s = ref.get("vina_best_score")
            ref_r = ref.get("rmsd_best_pose")
            nuevo_s = r.get("vina_best_score")
            nuevo_r = r.get("rmsd_best_pose")
            if ref_s is not None and nuevo_s is not None:
                pares_score.append((ref_s, nuevo_s))
            if ref_r is not None and nuevo_r is not None:
                pares_rmsd.append((ref_r, nuevo_r))
            # Salvaguarda de refutacion: garbage individual.
            if nuevo_s is not None and nuevo_s > GARBAGE_SCORE:
                garbage = True
            if nuevo_r is not None and nuevo_r > GARBAGE_RMSD:
                garbage = True

        # Spearman score.
        sp_s = spearman([a for a, _ in pares_score], [b for _, b in pares_score])
        sp_r = spearman([a for a, _ in pares_rmsd], [b for _, b in pares_rmsd])

        # Mediana de |delta RMSD|.
        if pares_rmsd:
            deltas = [abs(b - a) for a, b in pares_rmsd]
            med_delta = round(statistics.median(deltas), 3)
        else:
            med_delta = None

        # Veredicto pre-registrado.
        sp_s_ok = sp_s is not None and sp_s >= CRIT_SPEARMAN_SCORE
        med_ok = med_delta is not None and med_delta <= CRIT_MEDIAN_DELTA_RMSD
        sp_r_ok = sp_r is not None and sp_r >= CRIT_SPEARMAN_RMSD
        rmsd_ok = med_ok or sp_r_ok
        veredicto = "PASS" if (sp_s_ok and rmsd_ok and not garbage) else "FAIL"

        analisis[f"exh{exh}"] = {
            "n": len(sub),
            "spearman_score": round(sp_s, 3) if sp_s is not None else None,
            "spearman_rmsd": round(sp_r, 3) if sp_r is not None else None,
            "median_delta_rmsd": med_delta,
            "garbage": garbage,
            "veredicto": veredicto,
        }
        veredictos[exh] = veredicto

    # Recomendacion: el MENOR exh que PASO (preferir exh=1, luego 2, luego 4).
    recomendado = None
    for exh in EXH_NIVELES:
        if veredictos.get(exh) == "PASS":
            recomendado = exh
            break
    if recomendado is not None:
        # rho real del score para el texto.
        rho = analisis[f"exh{recomendado}"]["spearman_score"]
        analisis["recomendacion"] = (
            f"exh={recomendado} recomendado para redock de los 74 timeout "
            f"— preserva ranking (rho={rho} >= {CRIT_SPEARMAN_SCORE})"
        )
    else:
        analisis["recomendacion"] = (
            "Ruta A no recomendada — mantener MolFlex o explorar ruta C"
        )
    return analisis


# ─────────────────────── artifact helpers ───────────────────────────────

def cargar_artifacto() -> dict:
    if ARTIFACTO.exists():
        try:
            return json.loads(ARTIFACTO.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def guardar_artifacto(art: dict) -> None:
    ARTIFACTO.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACTO.write_text(
        json.dumps(art, ensure_ascii=False, indent=2), encoding="utf-8")


def config_bloque(n: int, cohort: dict) -> dict:
    return {
        "n_objetivo": n,
        "estrato_facil": {"umbral_rot": UMBRAL_ROT, "n": len(cohort["facil"]),
                          "criterio": f"< {UMBRAL_ROT} rotaables"},
        "estrato_dificil": {"umbral_rot": UMBRAL_ROT,
                            "n": len(cohort["dificil"]),
                            "criterio": f">= {UMBRAL_ROT} rotaables"},
        "exh_niveles": EXH_NIVELES,
        "exh_referencia": EXH_REFERENCIA,
        "timeout_s": FLEX_TIMEOUT,
        "max_workers": MAX_WORKERS,
        "seed": SEED,
        "criterio_exito": (
            f"exh=2: Spearman(vina_best_score) rho >= {CRIT_SPEARMAN_SCORE} "
            f"AND (median delta RMSD <= {CRIT_MEDIAN_DELTA_RMSD} Å "
            f"OR Spearman(RMSD) rho >= {CRIT_SPEARMAN_RMSD})"),
        "criterio_refutacion": (
            f"exh level produces garbage: vina_best_score > {GARBAGE_SCORE} "
            f"OR rmsd_best_pose > {GARBAGE_RMSD} Å -> FAIL regardless of rho"),
    }


# ─────────────────────── main ───────────────────────────────────────────

def _ts() -> str:
    return time.strftime("%H:%M:%S")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="Ruta A: validacion exh 1/2/4 vs 8")
    ap.add_argument("--dry-run", action="store_true",
                    help="Solo imprimir la cohorte (no dockear)")
    ap.add_argument("--n", type=int, default=DEFAULT_N,
                    help=f"Tamaño de la cohorte (default {DEFAULT_N})")
    args = ap.parse_args()

    # Construir (o cargar) la cohorte estratificada.
    art_existente = cargar_artifacto()
    if art_existente and "cohorte" in art_existente:
        # Reutilizar la cohorte del artifacto para no romper la resumabilidad.
        cohort = art_existente["cohorte"]
        rot = art_existente.get("rotatables", {})
        _log(f"[{_ts()}] cohorte reutilizada del artifacto existente "
             f"({len(cohort['facil'])} faciles, "
             f"{len(cohort['dificil'])} dificiles)")
    else:
        cohort, rot = seleccionar_cohorte(args.n, SEED)
        _log(f"[{_ts()}] cohorte seleccionada: "
             f"{len(cohort['facil'])} faciles + "
             f"{len(cohort['dificil'])} dificiles = "
             f"{len(cohort['facil']) + len(cohort['dificil'])} total")

    # --dry-run: solo imprimir y salir (sin dockear).
    if args.dry_run:
        _log("\n=== RUTA A — Dry run (cohorte) ===")
        _log(f"n_objetivo={args.n}  seed={SEED}  umbral_rot={UMBRAL_ROT}\n")
        _log(f"--- Faciles (< {UMBRAL_ROT} rot): {len(cohort['facil'])} ---")
        for p in sorted(cohort["facil"]):
            _log(f"  {p}  rot={rot.get(p, '?')}")
        _log(f"\n--- Dificiles (>= {UMBRAL_ROT} rot): "
             f"{len(cohort['dificil'])} ---")
        for p in sorted(cohort["dificil"]):
            _log(f"  {p}  rot={rot.get(p, '?')}")
        total = len(cohort["facil"]) + len(cohort["dificil"])
        _log(f"\nTotal cohorte: {total} complejos, "
             f"{total * len(EXH_NIVELES)} docks previstos")
        return

    # Dockear exh in {1,2,4} por pid (reanudable).
    pids = sorted(set(cohort["facil"]) | set(cohort["dificil"]))
    estrato_de = {}
    for p in cohort["facil"]:
        estrato_de[p] = "facil"
    for p in cohort["dificil"]:
        estrato_de[p] = "dificil"

    # Load resultados existentes para resum.
    results = list(art_existente.get("results", []))
    hechos = {(r["pdb_id"], r["exh"]) for r in results if r.get("exh")}

    # Cola de tareas pendientes.
    tareas = []
    for p in pids:
        for exh in EXH_NIVELES:
            if (p, exh) in hechos:
                continue
            tareas.append((p, exh, rot.get(p), estrato_de.get(p, "facil")))

    total = len(pids) * len(EXH_NIVELES)
    hecho_count = len(results)
    _log(f"[{_ts()}] {hecho_count}/{total} docks ya completados, "
         f"{len(tareas)} pendientes, pool={MAX_WORKERS} workers")

    if tareas:
        art = dict(art_existente)
        art["config"] = config_bloque(args.n, cohort)
        art["cohorte"] = cohort
        art["rotatables"] = rot
        art["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        # Guardar el esqueleto con los resultados previos (resum).
        art["results"] = results
        guardar_artifacto(art)

        t_start = time.monotonic()
        with ProcessPoolExecutor(max_workers=MAX_WORKERS) as ex:
            futs = {ex.submit(dock_one_exh, t): t for t in tareas}
            for fut in as_completed(futs):
                pid, exh = (
                    futs[fut][0], futs[fut][1]
                )
                try:
                    res = fut.result()
                except Exception as e:  # noqa: BLE001
                    res = {
                        "pdb_id": pid, "exh": exh,
                        "rotatables": futs[fut][2],
                        "estrato": futs[fut][3],
                        "ok": False, "reason": f"EXC:{type(e).__name__}",
                        "wall_s": 0.0,
                        "vina_best_score": None,
                        "pose_score_variance": None,
                        "pose_score_range": None,
                        "poses_passing_ratio": None,
                        "rmsd_best_pose": None,
                    }
                results.append(res)
                # Guardado incremental: tras cada dock (una caida pierde 1 dock).
                art["results"] = results
                guardar_artifacto(art)

                hecho_count += 1
                if res.get("ok"):
                    _log(
                        f"[{_ts()}] pid={pid} exh={exh} ... ok "
                        f"score={res['vina_best_score']} "
                        f"rmsd={res['rmsd_best_pose']} "
                        f"wall={res['wall_s']}s  "
                        f"done={hecho_count}/{total}"
                    )
                else:
                    _log(
                        f"[{_ts()}] pid={pid} exh={exh} ... FAIL "
                        f"reason={res.get('reason')}  "
                        f"done={hecho_count}/{total}"
                    )

        dt = round(time.monotonic() - t_start, 1)
        _log(f"[{_ts()}] docking completo: {hecho_count}/{total} docks en "
             f"{dt}s")

    # --- Tras completar: referencia exh=8 + analisis ---
    ref_exh8: dict = {}
    for p in pids:
        ref_exh8[p] = referencia_exh8_para(p)

    analisis = analizar(results, ref_exh8)

    # Artifacto final.
    art = dict(art_existente)
    art["generated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    art["config"] = config_bloque(args.n, cohort)
    art["cohorte"] = cohort
    art["rotatables"] = rot
    art["results"] = results
    art["referencia_exh8"] = ref_exh8
    art["analisis"] = analisis
    guardar_artifacto(art)

    # --- Tabla resumen a stderr ---
    _log("\n=== RUTA A — Resultados ===")
    _log("exh | n  | spearman_score | spearman_rmsd | "
         "median_delta_rmsd | garbage | veredicto")
    for exh in EXH_NIVELES:
        a = analisis.get(f"exh{exh}", {})
        n = a.get("n") if a is not None else None
        ss = a.get("spearman_score") if a is not None else None
        sr = a.get("spearman_rmsd") if a is not None else None
        md = a.get("median_delta_rmsd") if a is not None else None
        gb = a.get("garbage") if a is not None else None
        vd = a.get("veredicto") if a is not None else None
        _log(
            f"{exh}   | {n} | "
            f"{str(ss).ljust(14)} | {str(sr).ljust(13)} | "
            f"{str(md).ljust(17)} | "
            f"{'si' if gb else 'no':6} | {vd}"
        )
    _log(analisis.get("recomendacion", ""))
    _log(f"\nArtifacto: {ARTIFACTO}")


if __name__ == "__main__":
    main()
