#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_mf28_roadmap.py — MF-28: ¿alcanza un roadmap la cuenca que Vina no alcanza?

Corre en la máquina local (12 núcleos, binario Vina de `tools/vina`).

La pregunta
-----------
`MF-09` midió que en **30 de 33** complejos difíciles no existe pose <=2 A entre ~751
candidatas, y `MF-15-EXT` que no hay embudo que guíe hasta ella (rho 0.186). Las dos
juntas dicen que la búsqueda **no visita** la región correcta.

La planificación de movimientos lleva desde los noventa resolviendo exactamente esto en
espacios **sin gradiente útil**: no se sigue una pendiente, se construye conectividad
del espacio libre por muestreo y después se busca sobre el grafo (PRM, Kavraki et al.
1996; aplicado a este problema por Singh, Latombe & Brutlag 1999).

Si un muestreo ciego del espacio **libre** alcanza la cuenca nativa con el mismo CPU que
Vina gasta sin alcanzarla, el problema es la **estrategia de exploración**. Si tampoco
la alcanza, no lo es, y `MF-28` lo dice con la misma claridad.

Desviación declarada respecto de la sección 20.11(a)
---------------------------------------------------
El espacio es SE(3) x T^n. Aquí **T^n se discretiza por el ensemble ETKDG**: cada
confórmero es un nodo modal (el préstamo de la sección 20.2), y el roadmap se construye
sobre SE(3) x {confórmeros}. No es una simplificación gratuita: `MF-02A-EXT` midió que
la conformación correcta está disponible en el 83.9% a K30, de modo que la
discretización **no es el cuello**. Lo que se pone a prueba es la colocación.

Paridad de presupuesto
----------------------
Vina no expone su número de evaluaciones de energía, así que igualar «evaluaciones» no
es medible y se declararía sin poder comprobarlo. Se iguala por **CPU medida**: el brazo
Vina dockea el ensemble completo (protocolo congelado, exh=8, semilla 42) y se cronometra;
el roadmap recibe **exactamente ese wall-clock** en el mismo complejo y la misma máquina.
El conteo de chequeos de colisión se reporta como secundario.

La métrica es la del programa
-----------------------------
`rmsd_pose_pocket`: RMSD de pesados **en el marco del pocket, sin alineamiento**
(sección 5.1 del doc. 49). Aquí se implementa vectorizado con numpy para poder evaluar
cientos de miles de nodos, y se **verifica contra `molflex.rmsd_pose_pocket`** en una
muestra de cada complejo; el acuerdo se registra en `metrics.json`. Si divergiera, el
experimento no es comparable con el resto del programa y debe pararse.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

BOX = 25.0
SEED = 42
EXH = 8
NUM_MODES = 9
D_CLASH = 2.6          # A, declarado ANTES: choque entre pesados ligando-receptor
UMBRAL_A = 2.0
K_VECINOS = 8          # aristas por nodo en el grafo
N_INTERP = 5           # puntos intermedios del planificador local
MAX_NODOS_GRAFO = 5000  # tope de nodos que entran al grafo (conectividad es secundaria)
LOTE = 256             # configuraciones por lote vectorizado

RE_RIGID = re.compile(r"conf\d+\.rigid\.pdbqt$")   # excluye *.relax.rigid.* (lección MF-21)
RE_FLEX = re.compile(r"conf\d+\.flex\.pdbqt$")


# --------------------------------------------------------------------------- io

def _atomos_pdbqt(texto: str) -> List[Tuple[int, float, float, float, str]]:
    """(serial, x, y, z, elemento) de un PDBQT. El elemento sale de la columna 77-78."""
    out = []
    for l in texto.splitlines():
        if l.startswith(("ATOM", "HETATM")) and len(l) >= 54:
            try:
                el = l[76:78].strip() if len(l) >= 78 else ""
                out.append((int(l[6:11]), float(l[30:38]), float(l[38:46]),
                            float(l[46:54]), el))
            except ValueError:
                continue
    return out


def _receptor_pesados(p: Path) -> np.ndarray:
    at = _atomos_pdbqt(p.read_text(encoding="utf-8", errors="replace"))
    xyz = [(x, y, z) for _, x, y, z, el in at if el.upper() not in ("H", "HD")]
    return np.asarray(xyz, dtype=np.float64)


# ------------------------------------------------------------------ geometria

def _quats(rng: np.random.Generator, n: int) -> np.ndarray:
    """n cuaterniones uniformes en SO(3) (Shoemake)."""
    u1, u2, u3 = rng.random(n), rng.random(n), rng.random(n)
    s1, s2 = np.sqrt(1.0 - u1), np.sqrt(u1)
    return np.stack([s1 * np.sin(2 * np.pi * u2), s1 * np.cos(2 * np.pi * u2),
                     s2 * np.sin(2 * np.pi * u3), s2 * np.cos(2 * np.pi * u3)], axis=1)


def _matrices(q: np.ndarray) -> np.ndarray:
    """(n,4) cuaterniones -> (n,3,3) matrices de rotacion."""
    x, y, z, w = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    return np.stack([
        np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
        np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
        np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1),
    ], axis=1)


def _slerp(q0: np.ndarray, q1: np.ndarray, t: float) -> np.ndarray:
    d = float(np.dot(q0, q1))
    if d < 0.0:
        q1, d = -q1, -d
    if d > 0.9995:
        q = q0 + t * (q1 - q0)
        return q / np.linalg.norm(q)
    th0 = math.acos(max(-1.0, min(1.0, d)))
    th = th0 * t
    q2 = q1 - q0 * d
    q2 = q2 / np.linalg.norm(q2)
    return q0 * math.cos(th) + q2 * math.sin(th)


# --------------------------------------------------------------------- nucleo

def _libres(cand: np.ndarray, arbol, centro: np.ndarray, medio: float) -> np.ndarray:
    """cand: (B, A, 3). Devuelve mascara booleana (B,) de configuraciones LIBRES:
    ningun atomo pesado a menos de D_CLASH del receptor y todas dentro de la caja."""
    B, A, _ = cand.shape
    dentro = np.all(np.abs(cand - centro) <= medio, axis=(1, 2))
    plano = cand.reshape(-1, 3)
    d, _ = arbol.query(plano, k=1, workers=1)
    sin_choque = (d.reshape(B, A) >= D_CLASH).all(axis=1)
    return dentro & sin_choque


def analizar(pid: str, estrato: str, ws: Path, vina_bin: str, tmp: Path) -> Dict[str, Any]:
    import molflex as mf
    from scipy.spatial import cKDTree

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen = w / "rec.pdbqt", w / "center.json"
    if not rec.exists() or not cen.exists() or not (w / "index_map.json").exists():
        out["error"] = "SIN_MATERIAL"
        return out
    centro = np.asarray(json.loads(cen.read_text(encoding="utf-8")), dtype=np.float64)
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}

    rigidos = sorted([f for f in w.glob("conf*.rigid.pdbqt") if RE_RIGID.match(f.name)])
    flexes = sorted([f for f in w.glob("conf*.flex.pdbqt") if RE_FLEX.match(f.name)])
    if not rigidos or not flexes:
        out["error"] = "SIN_CONFORMEROS"
        return out
    out["n_conformeros"] = len(rigidos)

    # cristal en el marco del pocket, por indice de mol
    conf_c = crystal.GetConformer(0)
    pesados_mol = [i for i, a in enumerate(crystal.GetAtoms()) if a.GetAtomicNum() > 1]

    # ------------------------------------------------------ brazo VINA (control)
    t_vina = 0.0
    mejor_vina = None
    for f in flexes:
        salida = tmp / f"{pid}_{f.stem}.out.pdbqt"
        cmd = [vina_bin, "--receptor", str(rec), "--ligand", str(f),
               "--center_x", str(centro[0]), "--center_y", str(centro[1]),
               "--center_z", str(centro[2]), "--size_x", str(BOX),
               "--size_y", str(BOX), "--size_z", str(BOX),
               "--exhaustiveness", str(EXH), "--num_modes", str(NUM_MODES),
               "--seed", str(SEED), "--cpu", "1", "--out", str(salida)]
        t1 = time.time()
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            ok = p.returncode == 0 and salida.exists()
        except subprocess.TimeoutExpired:
            ok = False
        t_vina += time.time() - t1
        if not ok:
            continue
        for sc, at in mf.parsear_out_vina(
                salida.read_text(encoding="utf-8", errors="replace")):
            c = mf.coords_pose_a_por_mol(at, s2m)
            if not c:
                continue
            v = mf.rmsd_pose_pocket(crystal, c)
            if v is not None and (mejor_vina is None or v < mejor_vina):
                mejor_vina = v
        try:
            salida.unlink()
        except OSError:
            pass
    if mejor_vina is None:
        out["error"] = "VINA_SIN_POSES"
        return out
    out["vina"] = {"rmsd_min": round(mejor_vina, 3), "cpu_s": round(t_vina, 1),
                   "alcanza": bool(mejor_vina <= UMBRAL_A), "n_docks": len(flexes)}

    # -------------------------------------------------- brazo ROADMAP (mismo CPU)
    arbol = cKDTree(_receptor_pesados(rec))
    medio = BOX / 2.0
    rng = np.random.default_rng(SEED)

    # confórmeros como cuerpos rígidos: coords centradas + mapeo serial->mol
    cuerpos = []
    for f in rigidos:
        at = _atomos_pdbqt(f.read_text(encoding="utf-8", errors="replace"))
        ser = [s for s, *_ in at]
        xyz = np.asarray([[x, y, z] for _, x, y, z, _ in at], dtype=np.float64)
        idx = [k for k, s in enumerate(ser) if s in s2m]
        if not idx:
            continue
        mols = [s2m[ser[k]] for k in idx]
        # solo los pesados del cristal que están mapeados
        keep = [(k, m) for k, m in zip(idx, mols) if m in pesados_mol]
        if not keep:
            continue
        ks = [k for k, _ in keep]
        ms = [m for _, m in keep]
        ref = np.asarray([[conf_c.GetAtomPosition(m).x, conf_c.GetAtomPosition(m).y,
                           conf_c.GetAtomPosition(m).z] for m in ms], dtype=np.float64)
        sub = xyz[ks]
        cuerpos.append({"xyz_c": sub - sub.mean(axis=0), "ref": ref,
                        "ser": [ser[k] for k in ks], "mols": ms, "archivo": f.name})
    if not cuerpos:
        out["error"] = "SIN_MAPEO"
        return out

    presupuesto = t_vina
    t_ini = time.time()
    n_muestras = n_libres = n_checks = 0
    mejor_rm = None
    mejor_nodo = None
    nodos: List[Dict[str, Any]] = []

    while time.time() - t_ini < presupuesto:
        cu = cuerpos[rng.integers(len(cuerpos))]
        base = cu["xyz_c"]                       # (A,3)
        A = base.shape[0]
        q = _quats(rng, LOTE)
        R = _matrices(q)                          # (B,3,3)
        centros = centro + (rng.random((LOTE, 3)) - 0.5) * BOX
        cand = np.einsum("bij,aj->bai", R, base) + centros[:, None, :]
        m = _libres(cand, arbol, centro, medio)
        n_muestras += LOTE
        n_checks += LOTE * A
        if not m.any():
            continue
        libres = cand[m]
        d = libres - cu["ref"][None, :, :]
        rm = np.sqrt((d ** 2).sum(axis=2).mean(axis=1))   # rmsd_pose_pocket vectorizado
        n_libres += int(m.sum())
        j = int(np.argmin(rm))
        if mejor_rm is None or rm[j] < mejor_rm:
            mejor_rm = float(rm[j])
            mejor_nodo = {"archivo": cu["archivo"], "coords": libres[j],
                          "ser": cu["ser"], "mols": cu["mols"]}
        if len(nodos) < MAX_NODOS_GRAFO:
            qs = q[m]
            cs = centros[m]
            for k in range(min(len(rm), MAX_NODOS_GRAFO - len(nodos))):
                nodos.append({"cuerpo": cu["archivo"], "q": qs[k], "c": cs[k],
                              "rmsd": float(rm[k])})
    t_road = time.time() - t_ini

    # verificacion del RMSD vectorizado contra la implementacion del programa
    verif = None
    if mejor_nodo is not None:
        c = {m: tuple(float(v) for v in xyz)
             for m, xyz in zip(mejor_nodo["mols"], mejor_nodo["coords"])}
        ref_impl = mf.rmsd_pose_pocket(crystal, c)
        if ref_impl is not None:
            verif = {"vectorizado": round(mejor_rm, 4), "molflex": round(ref_impl, 4),
                     "delta": round(abs(ref_impl - mejor_rm), 6)}

    # conectividad (secundaria, descriptiva): componentes sobre los nodos guardados
    comp_mayor = None
    mejor_en_mayor = None
    if len(nodos) >= 2:
        import networkx as nx
        pos = np.asarray([n["c"] for n in nodos])
        arb_n = cKDTree(pos)
        G = nx.Graph()
        G.add_nodes_from(range(len(nodos)))
        for i in range(len(nodos)):
            _, vec = arb_n.query(pos[i], k=min(K_VECINOS + 1, len(nodos)))
            for j in np.atleast_1d(vec):
                j = int(j)
                if j == i or nodos[i]["cuerpo"] != nodos[j]["cuerpo"]:
                    continue
                cu = next(x for x in cuerpos if x["archivo"] == nodos[i]["cuerpo"])
                ok = True
                for t in np.linspace(0.0, 1.0, N_INTERP + 2)[1:-1]:
                    qi = _slerp(nodos[i]["q"], nodos[j]["q"], float(t))
                    Ri = _matrices(qi[None, :])[0]
                    ci = nodos[i]["c"] * (1 - t) + nodos[j]["c"] * t
                    pt = (cu["xyz_c"] @ Ri.T + ci)[None, :, :]
                    n_checks += pt.shape[1]
                    if not _libres(pt, arbol, centro, medio)[0]:
                        ok = False
                        break
                if ok:
                    G.add_edge(i, j)
        comps = sorted(nx.connected_components(G), key=len, reverse=True)
        if comps:
            comp_mayor = len(comps[0])
            ib = int(np.argmin([n["rmsd"] for n in nodos]))
            mejor_en_mayor = bool(ib in comps[0])

    out["roadmap"] = {
        "rmsd_min": round(mejor_rm, 3) if mejor_rm is not None else None,
        "alcanza": bool(mejor_rm is not None and mejor_rm <= UMBRAL_A),
        "cpu_s": round(t_road, 1), "n_muestras": n_muestras, "n_libres": n_libres,
        "frac_libres": round(n_libres / n_muestras, 5) if n_muestras else None,
        "n_checks_colision": n_checks, "n_nodos_grafo": len(nodos),
        "componente_mayor": comp_mayor, "mejor_en_componente_mayor": mejor_en_mayor,
        "verificacion_rmsd": verif}
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="MF-28: roadmap del espacio libre vs Vina")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--vina", default=str(PROJECT_ROOT / "tools" / "vina" / "vina.exe"))
    args = ap.parse_args()
    ws = Path(args.workspace)
    out_dir = ws / "scripts" / "artifacts_science" / "MF-28"
    out_dir.mkdir(parents=True, exist_ok=True)

    coh = json.loads((ws / "scripts" / "artifacts_science" / "MF-02F" /
                      "cohorte.json").read_text(encoding="utf-8"))
    jobs = [(p, "COLOCACION") for p in coh["cohorte_colocacion"]] + \
           [(p, "CONTROL") for p in coh["control_cubiertos"]]
    if args.limite:
        jobs = jobs[:args.limite]
    print(f"[MF-28] {len(jobs)} complejos, {args.workers} workers, "
          f"d_clash={D_CLASH} A, presupuesto = CPU de Vina por complejo", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, pid, est, ws, args.vina, tmp): pid
                    for pid, est in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                filas.append(fut.result())
                r = filas[-1]
                v = r.get("vina", {})
                rd = r.get("roadmap", {})
                print(f"  [{i}/{len(jobs)}] {r['pid']} [{r['estrato']}] "
                      f"vina={v.get('rmsd_min')} ({v.get('cpu_s')}s) "
                      f"road={rd.get('rmsd_min')} libres={rd.get('frac_libres')} "
                      f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8",
                          newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "vina" in r and "roadmap" in r]
    resumen: Dict[str, Any] = {}
    for est in ("COLOCACION", "CONTROL"):
        g = [r for r in ok if r["estrato"] == est]
        if not g:
            continue
        b = sum(1 for r in g if r["roadmap"]["alcanza"] and not r["vina"]["alcanza"])
        c = sum(1 for r in g if r["vina"]["alcanza"] and not r["roadmap"]["alcanza"])
        resumen[est] = {
            "n": len(g),
            "vina_alcanza": sum(1 for r in g if r["vina"]["alcanza"]),
            "roadmap_alcanza": sum(1 for r in g if r["roadmap"]["alcanza"]),
            "mcnemar_b_roadmap_gana": b, "mcnemar_c_vina_gana": c,
            "mcnemar_p_exacto": _mcnemar(b, c),
            "mde_declarado": "b>=6 con c=0 para p<0.05",
            "rmsd_mediano_vina": _mediana([r["vina"]["rmsd_min"] for r in g], 3),
            # None = el roadmap no hallo NINGUNA configuracion libre en todo su
            # presupuesto. No es un fallo: es que el ligando no cabe sin choque en
            # ninguna colocacion muestreada. Se excluye de la mediana y se cuenta.
            "rmsd_mediano_roadmap": _mediana([r["roadmap"]["rmsd_min"] for r in g], 3),
            "n_roadmap_sin_configuracion_libre":
                sum(1 for r in g if r["roadmap"]["rmsd_min"] is None),
            "frac_libres_mediana": _mediana([r["roadmap"]["frac_libres"] for r in g], 5),
            "cpu_mediana_s": _mediana([r["vina"]["cpu_s"] for r in g], 1),
        }
    verifs = [r["roadmap"]["verificacion_rmsd"] for r in ok
              if r["roadmap"].get("verificacion_rmsd")]
    metrics = {
        "experiment_id": "MF-28",
        "tipo": "intervencion pareada (estrategia de exploracion)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"box": BOX, "seed": SEED, "exh_control": EXH, "num_modes": NUM_MODES,
                   "d_clash_A": D_CLASH, "umbral_A": UMBRAL_A,
                   "k_vecinos": K_VECINOS, "n_interp": N_INTERP,
                   "max_nodos_grafo": MAX_NODOS_GRAFO,
                   "paridad": "CPU medida de Vina por complejo",
                   "discretizacion_torsional": "ensemble ETKDG (desviacion declarada)"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "por_estrato": resumen,
        "verificacion_metrica": {
            "n": len(verifs),
            "delta_max": round(max((v["delta"] for v in verifs), default=0.0), 6),
            "criterio": "acuerdo con molflex.rmsd_pose_pocket a 4 decimales"},
    }
    (out_dir / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"[MF-28] LISTO n={len(ok)} ({round(time.time()-t0)}s)", flush=True)
    for est, d in resumen.items():
        print(f"  {est}: vina {d['vina_alcanza']}/{d['n']}  "
              f"roadmap {d['roadmap_alcanza']}/{d['n']}  "
              f"b={d['mcnemar_b_roadmap_gana']} c={d['mcnemar_c_vina_gana']} "
              f"p={d['mcnemar_p_exacto']}", flush=True)
    return 0


def _mediana(vals: List[Optional[float]], dec: int) -> Optional[float]:
    """Mediana ignorando None. Devuelve None si no queda ningun valor."""
    v = [x for x in vals if x is not None]
    return round(median(v), dec) if v else None


def _mcnemar(b: int, c: int) -> Optional[float]:
    """McNemar exacto bilateral (binomial con p=0.5 sobre los discordantes)."""
    n = b + c
    if n == 0:
        return None
    from math import comb
    k = min(b, c)
    cola = sum(comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return round(min(1.0, 2 * cola), 4)


if __name__ == "__main__":
    raise SystemExit(main())
