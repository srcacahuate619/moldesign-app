#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REC-05: los metales del receptor sobre el docking de novo, pareado.

Mismo diseno que REC-11 y por construccion, no por copia: este runner IMPORTA
scripts/run_rec11_aguas_denovo.py -sellado como asset de REC-11- y reutiliza su funcion
_brazo y sus constantes BOX, EXH, NUM_MODES, SEMILLAS, UMBRAL_A y LIGANDO. Lo unico propio
es que la especie que se retira del receptor son los METALES en vez de las aguas, y que la
cohorte son los complejos que tienen alguno. El docs/49 seccion 17 exige exactamente esto:
un artefacto sellado se extiende por composicion, nunca se edita ni se copia.

El conjunto METALES se toma tambien del modulo sellado de REC-12, sin redefinirlo.

RE-ALCANCE DECLARADO ANTES DE CORRER. El REC-05 del docs/49 pedia ablacion por clase en
tres clases y un gate de "reglas por familia con evidencia". Dos clases quedan fuera y el
gate por familia no es alcanzable, y ambas cosas se declaran aqui y no despues:
  - AGUAS: fuera. El prerregistro de REC-11 condicionaba abrir politicas intermedias a que
    saliera QUITARLAS MEJORA; salio SIN_DIFERENCIA_DETECTABLE, asi que no esta autorizado.
  - COFACTORES: fuera por falta de n. REC-12-R1 midio que el nucleo robusto son DOS
    complejos, 1gwv (UDP) y 1lbk (GSH).
  - METALES: dentro, pero AGRUPADOS. Con 29 complejos, solo ZN (n=21) admite una lectura
    de familia y esa es descriptiva; CA (7), MG (3), MN (3) y CU (2) NO se leen.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import analisis_rec12_cofactores as r12       # METALES, sellado en REC-12
import run_rec11_aguas_denovo as r11          # _brazo y el protocolo, sellado en REC-11

FAMILIA_CON_LECTURA = "ZN"                    # la unica con n suficiente; declarado antes


def _vina() -> str:
    return os.environ.get("REC05_VINA", os.environ.get("REC11_VINA", "/usr/local/bin/vina"))


def _es_metal(linea: str) -> bool:
    """Un atomo de metal en un PDBQT: SOLO por nombre de residuo, columnas 18-20.

    Se probo antes de sellar mirando tambien el nombre de atomo y el campo de tipo, y era
    un error grave: en un PDBQT la columna 13-16 del carbono alfa de CUALQUIER residuo es
    `CA`, que colisiona con el calcio, y las columnas 77-78 llevan el tipo de AutoDock, no
    el simbolo quimico, donde `NA` es un nitrogeno aceptor y no el sodio. Con esos dos
    criterios el brazo SIN se quedaba sin proteina: entre 200 y 3900 atomos retirados por
    complejo. Por nombre de residuo no hay colision: un ion metalico es su propio residuo
    y ningun aminoacido estandar comparte codigo con el conjunto METALES.
    """
    return linea[17:20].strip().upper() in r12.METALES


def _sin_metales(texto: str) -> Tuple[str, int, List[str]]:
    """El PDBQT sin ningun atomo de metal, cuantos se quitaron y de que especies."""
    fuera, quitados, especies = [], 0, []
    for l in texto.splitlines():
        if l.startswith(("ATOM", "HETATM")) and len(l) >= 20 and _es_metal(l):
            quitados += 1
            especies.append(l[17:20].strip().upper() or l[12:16].strip().upper())
            continue
        fuera.append(l)
    return "\n".join(fuera) + "\n", quitados, sorted(set(especies))


def analizar(ws_text: str, pid: str, estrato: str, familias: List[str]) -> Dict[str, Any]:
    import molflex as mf

    ws = Path(ws_text)
    out: Dict[str, Any] = {"pid": pid, "estrato": estrato, "familias_REC08EXT": familias}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen, lig = w / "rec.pdbqt", w / "center.json", w / r11.LIGANDO
    if not all(p.exists() for p in (rec, cen, lig, w / "index_map.json")):
        out["error"] = "SIN_MATERIAL"
        return out
    centro = json.loads(cen.read_text(encoding="utf-8"))
    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    s2m = {int(s): int(m) for s, m in
           json.loads((w / "index_map.json").read_text(encoding="utf-8"))}

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        rec_sin = tmp / f"{pid}_rec_sin_metales.pdbqt"
        texto, quitados, especies = _sin_metales(rec.read_text(encoding="utf-8", errors="replace"))
        rec_sin.write_text(texto, encoding="utf-8")
        out["atomos_metal_quitados"] = quitados
        out["especies_quitadas"] = especies
        if quitados == 0:
            out["error"] = "SIN_METAL_EN_EL_PDBQT"
            out["t_s"] = round(time.time() - t0, 1)
            return out

        v = _vina()
        out["CON"] = r11._brazo(v, rec, lig, centro, crystal, s2m, tmp, pid, "con")
        out["SIN"] = r11._brazo(v, rec_sin, lig, centro, crystal, s2m, tmp, pid, "sin")

    a, b = out["CON"], out["SIN"]
    if a["oraculo"] is not None and b["oraculo"] is not None:
        out["delta_oraculo"] = round(a["oraculo"] - b["oraculo"], 3)   # >0 => SIN mejor
        out["discordante"] = a["cubierto"] != b["cubierto"]
        out["gana_SIN"] = bool(b["cubierto"] and not a["cubierto"])
        out["gana_CON"] = bool(a["cubierto"] and not b["cubierto"])
    out["t_s"] = round(time.time() - t0, 1)
    return out


def _bloque(rows: List[Dict[str, Any]], etiqueta: str, mcnemar, mde) -> Dict[str, Any]:
    con = sum(1 for r in rows if r["CON"]["cubierto"])
    sin = sum(1 for r in rows if r["SIN"]["cubierto"])
    b = sum(1 for r in rows if r.get("gana_SIN"))
    c = sum(1 for r in rows if r.get("gana_CON"))
    n = len(rows)
    disc = round((b + c) / n, 4) if n else None
    return {"etiqueta": etiqueta, "n": n,
            "cobertura_CON": {"n": con, "frac": round(con / n, 4) if n else None},
            "cobertura_SIN": {"n": sin, "frac": round(sin / n, 4) if n else None},
            "b_gana_SIN": b, "c_gana_CON": c,
            "mcnemar_p_exacto": round(mcnemar(b, c), 6) if n else None,
            "discordancia": disc,
            "mde_observado_pp": round(mde(n, disc) * 100, 2) if n and disc else None}


def main() -> int:
    from estadistica_fnd04 import mcnemar_exacto, efecto_minimo_detectable

    ap = argparse.ArgumentParser(description="REC-05: metales sobre docking de novo, pareado")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limite", type=int, default=None,
                    help="solo prueba tecnica; nunca produce decision")
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "REC-05"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Cohorte derivada de artefactos sellados, no escrita a mano.
    estrato = {}
    for l in (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            estrato[r["pid"]] = r.get("estrato", "RESTO")
    cohorte: List[Tuple[str, str, List[str]]] = []
    for l in (art / "REC-08-EXT" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if not l.strip():
            continue
        r = json.loads(l)
        if r["pid"] in estrato and (r.get("metales_sitio") or 0) > 0:
            cohorte.append((r["pid"], estrato[r["pid"]], sorted(r.get("especies_metal", []))))
    cohorte.sort()
    if args.limite:
        cohorte = cohorte[:args.limite]
    print(f"[REC-05] cohorte={len(cohorte)} workers={args.workers}", flush=True)

    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(analizar, str(ws), pid, est, fam): pid for pid, est, fam in cohorte}
        for n, fut in enumerate(as_completed(futs), 1):
            r = fut.result()
            filas.append(r)
            with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                for x in sorted(filas, key=lambda y: y["pid"]):
                    fh.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
            print(f"  [{n}/{len(cohorte)}] {r['pid']} CON={r.get('CON',{}).get('oraculo')} "
                  f"SIN={r.get('SIN',{}).get('oraculo')} metales={r.get('atomos_metal_quitados')} "
                  f"disc={r.get('discordante')} ({r.get('t_s')}s)", flush=True)

    ok = [r for r in filas if "CON" in r and "SIN" in r and r.get("delta_oraculo") is not None]
    primaria = _bloque(ok, "TODOS_LOS_METALES", mcnemar_exacto, efecto_minimo_detectable)
    zn = [r for r in ok if FAMILIA_CON_LECTURA in (r.get("familias_REC08EXT") or [])]
    sec_zn = _bloque(zn, f"FAMILIA_{FAMILIA_CON_LECTURA}", mcnemar_exacto,
                     efecto_minimo_detectable) if zn else None

    p = primaria["mcnemar_p_exacto"]
    if args.limite:
        lectura = "NO_LEER_GATES_TECNICOS"
    elif p is not None and p < 0.05 and primaria["b_gana_SIN"] > primaria["c_gana_CON"]:
        lectura = "QUITARLOS_MEJORA"
    elif p is not None and p < 0.05 and primaria["c_gana_CON"] > primaria["b_gana_SIN"]:
        lectura = "CONSERVARLOS_ES_NECESARIO"
    else:
        lectura = "SIN_DIFERENCIA_DETECTABLE"

    familias = {}
    for r in ok:
        for f in (r.get("familias_REC08EXT") or []):
            familias[f] = familias.get(f, 0) + 1

    metrics = {
        "experiment_id": "REC-05",
        "tipo": "intervencion pareada con re-alcance, regla de lectura y MDE preregistrados",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {"exh": r11.EXH, "num_modes": r11.NUM_MODES, "semillas": list(r11.SEMILLAS),
                   "box": r11.BOX, "umbral_A": r11.UMBRAL_A, "ligando": r11.LIGANDO,
                   "variable_unica": "el receptor: con todos sus metales contra sin ninguno",
                   "metrica": "rmsd_pose_pocket sin alineamiento",
                   "protocolo_importado_de": "run_rec11_aguas_denovo._brazo (sellado en REC-11)",
                   "metales_importados_de": "analisis_rec12_cofactores.METALES (sellado en REC-12)"},
        "n_complejos": len(filas), "n_ok": len(ok),
        "cantidad_primaria": dict(primaria, lectura_preregistrada=lectura),
        "secundario_familia_ZN": dict(sec_zn, nota="descriptivo; unica familia con n") if sec_zn else None,
        "familias_presentes": dict(sorted(familias.items(), key=lambda x: -x[1])),
        "familias_declaradas_NO_LEIBLES": ["CA", "MG", "MN", "CU"],
        "limites_declarados": [
            "re-alcance: aguas fuera -REC-11 no lo autorizo- y cofactores fuera -REC-12-R1 midio n=2-",
            "el gate por familia del REC-05 original NO es alcanzable a este n y se declaro antes de correr",
            "un solo conformero, igual que REC-11: mide el efecto a conformero igualado, no la cobertura alcanzable",
            "quitarlos todos no es la unica alternativa; no se evaluan politicas intermedias",
            "no toca ningun artefacto sellado ni cambia ningun receptor",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    (out_dir / "failures.jsonl").write_text(
        "".join(json.dumps({"pid": r["pid"], "error": r["error"]}, ensure_ascii=False) + "\n"
                for r in filas if "error" in r), encoding="utf-8", newline="\n")
    print(f"[REC-05] LISTO n={primaria['n']} CON={primaria['cobertura_CON']['n']} "
          f"SIN={primaria['cobertura_SIN']['n']} b={primaria['b_gana_SIN']} "
          f"c={primaria['c_gana_CON']} p={p} MDE={primaria['mde_observado_pp']}pp "
          f"lectura={lectura}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
