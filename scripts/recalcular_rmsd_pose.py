# -*- coding: utf-8 -*-
"""recalcular_rmsd_pose.py — Auditoría 2026-08-14: recomputación de RMSD de
pose EN EL MARCO DEL POCKET (sin alineamiento) desde disco.

Contexto: los RMSD previos usaban molflex.rmsd_pesados -> AllChem.GetBestRMS,
que ALINEA los dos mols y oculta desplazamientos de la pose en el pocket.
Este script NO re-dockea nada: lee las poses ya guardadas y recalcula con
mf.rmsd_pose_pocket (matching 1:1 por índice vía serial_a_mol, sin alinear).

Cubre tres secciones:
  A) Referencia flexible de v3 V2/R1 (6 pids):
     - 186l, 1add, 1ado: pose en vina_redock_work (fuente "disco") ->
       recomputar pocket-frame via flexible_desde_disco (ya arreglada).
     - 10gs, 184l, 187l: fuente "redock" PERO el redock escribió el PDBQT
       RÍGIDO (bug de unpacking, corregido). Su flex_out.pdbqt queda en
       .work_molflex_v3/{pid}/ -> recomputar para DOCUMENTAR el daño.
  B) Poses MolFlex de v3 E2 (5 pids: 1a4w, 1aaq, 1ajx, 10gs, 184l):
     - rmsd_top_score_pose: conf con mejor score en conf*.out.pdbqt.
     - relaxed (rmsd_to_crystal): conf{cid}.relax.rigid.pdbqt.
  C) Referencia flexible de ruta_a (30 pids, vina_redock_work) via
     flexible_desde_disco arreglada.

Comparación viejo (alineado, artefacto) vs nuevo (pocket-frame, disco).
Salida: scripts/artifacts_recalc_rmsd.json.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
import molflex as mf  # noqa: E402
from molflex_exp_v3 import flexible_desde_disco  # noqa: E402  (ya arreglada)

ART_V3 = PROJECT_ROOT / "scripts" / "artifacts_molflex_v3.json"
ART_RUTA_A = PROJECT_ROOT / "scripts" / "artifacts_ruta_a.json"
WORK_V3 = PROJECT_ROOT / "scripts" / ".work_molflex_v3"
OUT = PROJECT_ROOT / "scripts" / "artifacts_recalc_rmsd.json"

PIDS_REDOCK_BUG = ["10gs", "184l", "187l"]


def crystal_para(pid: str):
    return mf.leer_ligando(str(mf.PDBBIND / pid / f"{pid}_ligand.sdf"))


def mapa_indices_v3(pid: str) -> dict:
    p = WORK_V3 / pid / "index_map.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        return {int(s): int(m) for s, m in raw}
    except Exception:
        return {}


def rmsd_desde_pdbqt(pid: str, pdbqt_path: Path, crystal, mapa: dict) -> float | None:
    """Pocket-frame RMSD de la pose 1 de un PDBQT (rigido o relaxed)."""
    if crystal is None or not pdbqt_path.exists() or not mapa:
        return None
    try:
        modelos = mf.parsear_out_vina(pdbqt_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not modelos or not modelos[0][1]:
        return None
    por_mol = mf.coords_pose_a_por_mol(modelos[0][1], mapa)
    r = mf.rmsd_pose_pocket(crystal, por_mol)
    return round(r, 3) if r is not None else None


def mejor_conf_score(pid: str) -> tuple[int | None, float | None]:
    """El conformero con mejor score en .work_molflex_v3/{pid}/conf*.out.pdbqt."""
    d = WORK_V3 / pid
    mejor = (None, None)
    for p in sorted(d.glob("conf*.out.pdbqt")):
        try:
            modelos = mf.parsear_out_vina(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not modelos or modelos[0][0] is None:
            continue
        score = float(modelos[0][0])
        if mejor[1] is None or score < mejor[1]:
            cid = int(p.stem.replace("conf", "").split(".")[0])
            mejor = (cid, score)
    return mejor


def seccion_a(art: dict) -> list:
    """Referencia flexible v3 V2/R1: disco vs redock-bug."""
    refs = art.get("v2", {}).get("referencia_flexible", {})
    filas = []
    for pid, old in sorted(refs.items()):
        crystal = crystal_para(pid)
        if pid in PIDS_REDOCK_BUG:
            flex_out = WORK_V3 / pid / "flex_out.pdbqt"
            nuevo = rmsd_desde_pdbqt(pid, flex_out, crystal, mapa_indices_v3(pid))
            filas.append({
                "seccion": "A", "pid": pid, "fuente": "redock_rigido_bug",
                "rmsd_viejo_alineado": old.get("rmsd_best_pose"),
                "rmsd_nuevo_pocket": nuevo,
                "nota": "referencia escrita con PDBQT rigido (bug unpacking); "
                        "recomputada desde flex_out.pdbqt para documentar el dano",
            })
        else:
            d = flexible_desde_disco(pid)
            nuevo = d.get("rmsd_best_pose") if d else None
            filas.append({
                "seccion": "A", "pid": pid, "fuente": "disco",
                "rmsd_viejo_alineado": old.get("rmsd_best_pose"),
                "rmsd_nuevo_pocket": nuevo,
                "nota": None,
            })
    return filas


def seccion_b(art: dict) -> list:
    """Poses MolFlex v3 E2: top-score + relaxed."""
    agregados = art.get("e2", {}).get("agregados", {})
    filas = []
    for pid, a in sorted(agregados.items()):
        crystal = crystal_para(pid)
        mapa = mapa_indices_v3(pid)
        cid_top, score_top = mejor_conf_score(pid)
        nuevo_top = None
        if cid_top is not None:
            nuevo_top = rmsd_desde_pdbqt(
                pid, WORK_V3 / pid / f"conf{cid_top}.out.pdbqt", crystal, mapa)
        filas.append({
            "seccion": "B", "pid": pid, "metrica": "rmsd_top_score_pose",
            "cid": cid_top,
            "rmsd_viejo_alineado": a.get("rmsd_top_score_pose"),
            "rmsd_nuevo_pocket": nuevo_top,
            "nota": f"mejor conf {cid_top} (score {score_top})",
        })
        for r in a.get("relaxed", []):
            if not r.get("ok"):
                continue
            cid = r.get("cid")
            nuevo = rmsd_desde_pdbqt(
                pid, WORK_V3 / pid / f"conf{cid}.relax.rigid.pdbqt", crystal, mapa)
            filas.append({
                "seccion": "B", "pid": pid, "metrica": "relaxed",
                "cid": cid,
                "rmsd_viejo_alineado": r.get("rmsd_to_crystal"),
                "rmsd_nuevo_pocket": nuevo,
                "nota": None,
            })
    return filas


def seccion_c() -> list:
    """Referencia flexible ruta_a: 30 pids desde vina_redock_work."""
    if not ART_RUTA_A.exists():
        return []
    art = json.loads(ART_RUTA_A.read_text(encoding="utf-8"))
    refs = art.get("referencia_exh8", {})
    filas = []
    for pid in sorted(refs):
        old = refs[pid].get("rmsd_best_pose")
        d = flexible_desde_disco(pid)
        nuevo = d.get("rmsd_best_pose") if d else None
        filas.append({
            "seccion": "C", "pid": pid, "fuente": "disco",
            "rmsd_viejo_alineado": old,
            "rmsd_nuevo_pocket": nuevo,
            "nota": None,
        })
    return filas


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    art_v3 = json.loads(ART_V3.read_text(encoding="utf-8"))
    filas = seccion_a(art_v3) + seccion_b(art_v3) + seccion_c()
    out = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "motivo": ("Auditoria 2026-08-14: rmsd_pesados usaba GetBestRMS (alinea). "
                   "Recomputacion pocket-frame (sin alinear) desde poses en disco. "
                   "Tambien documenta las 3 referencias redock del bug de unpacking."),
        "filas": filas,
    }
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"filas totales: {len(filas)}")
    print("seccion | pid   | metrica            | viejo(alineado) | nuevo(pocket) | nota")
    print("-" * 100)
    for f in filas:
        met = f.get("metrica") or f.get("fuente")
        print(f"{f['seccion']:7} | {f['pid']:6} | {str(met):18} | "
              f"{str(f['rmsd_viejo_alineado']):16} | {str(f['rmsd_nuevo_pocket']):13} | "
              f"{f.get('nota') or ''}")
    # Resumen de deltas (solo pares con ambos valores)
    pares = [(f["rmsd_viejo_alineado"], f["rmsd_nuevo_pocket"]) for f in filas
             if f["rmsd_viejo_alineado"] is not None and f["rmsd_nuevo_pocket"] is not None]
    if pares:
        deltas = [round(b - a, 3) for a, b in pares]
        print(f"\npares comparables: {len(pares)}  delta (nuevo-viejo) mediana: "
              f"{sorted(deltas)[len(deltas)//2]:.3f} A  max: {max(deltas):.3f} A")
        empeora = sum(1 for d in deltas if d > 0.5)
        print(f"casos donde el RMSD pocket >0.5 A por encima del alineado: {empeora}/{len(pares)}")
    print(f"\nArtifacto: {OUT}")


if __name__ == "__main__":
    main()
