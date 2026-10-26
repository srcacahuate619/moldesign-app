#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rec07r1_grid_5tun.py — REC-07-R1: REC-07 con la cisteína catalítica dentro del receptor.

REC-07 midió el contacto de E64c con `Cys25:SG` sobre un receptor que **no tenía la Cys25**:
su filtro de altloc elegía por residuo la variante mayoritaria contando también los átomos
sin altloc, y en la Cys25 de 5TUN (N, C, O sin altloc; CA, CB, SG en A y B) ganó el vacío.
Quedaron N, C y O, y Meeko descartó el residuo incompleto (`-a`). El «contacto a 0,42 Å» era
el ligando ocupando el hueco de la cisteína (SCI-B-022).

Este runner repite REC-07 con dos cambios, y sólo dos:

1. **Altloc coherente**, la regla de `backend/services/docking/preparer.py`: los átomos sin
   altloc se conservan siempre, y entre las variantes no vacías se elige por ocupación
   acumulada con desempate en A; la elegida se normaliza a altloc vacío. En la Cys25 elige A,
   la convención que el preregistro de REC-07 ya fijaba (§3).
2. **Aborto si falta el ancla**: el receptor acoplado debe contener `Cys25:SG`,
   `His162:NE2` y `Asn182:ND2` a menos de 0,01 Å de sus coordenadas en el PDB (altloc A).

Todo lo demás se importa del runner sellado de REC-07 (brazos, semillas, exhaustividad,
umbral, hotspots, geometría, lectura de poses): la configuración congelada es la misma por
construcción. El ligando es el mismo fichero que acopló REC-07 (SHA-256 `e82cbe4e…`). Las
corridas son independientes (`--cpu 1` cada una) y se lanzan en paralelo.

Preregistro: scripts/artifacts_science/REC-07-R1/PREREGISTRO.md

Uso:
    python scripts/run_rec07r1_grid_5tun.py --workers 10
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_rec07_grid_5tun as rec07  # noqa: E402  (configuración congelada de REC-07)

EXPERIMENT_ID = "REC-07-R1"
OUT_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID
ENTRADA = OUT_DIR / "entrada"
PDB_5TUN = ENTRADA / "5TUN.pdb"
LIGANDO = ENTRADA / "E6C.pdbqt"
LIGANDO_SHA256_REC07 = "e82cbe4e3b62dcdf81fd8c5a51541c9f3e2761f97628aadd130b64272b7805d1"
VINA = PROJECT_ROOT / "tools" / "vina" / "vina.exe"
TOLERANCIA_ANCLA_A = 0.01


def elegir_altloc(pdb_text: str) -> dict[tuple[str, str, str], str]:
    """Variante elegida por residuo, con la regla de preparer.py (ocupación, desempate en A)."""
    ocupacion: dict[tuple[str, str, str], dict[str, float]] = {}
    for l in pdb_text.splitlines():
        if l[:6].strip() not in {"ATOM", "HETATM"} or len(l) < 27:
            continue
        variante = l[16:17].strip()
        if not variante:
            continue
        clave = (l[21:22].strip() or "A", l[22:26].strip(), l[26:27])
        try:
            occ = float(l[54:60])
        except ValueError:
            occ = 0.0
        cuentas = ocupacion.setdefault(clave, {})
        cuentas[variante] = cuentas.get(variante, 0.0) + occ
    return {k: min(v, key=lambda x: (-v[x], x)) for k, v in ocupacion.items()}


def filtrar_pdb_coherente(origen: Path, destino: Path) -> dict[str, Any]:
    """Los filtros de REC-07 (registros, aguas, cadena A, residuo > 0) con altloc coherente."""
    texto = origen.read_text(encoding="utf-8", errors="replace")
    elegido = elegir_altloc(texto)
    salida: list[str] = []
    stats = {"aguas_eliminadas": 0, "otra_cadena": 0, "altloc_descartado": 0, "conservadas": 0}
    for l in texto.splitlines():
        rec = l[:6].strip()
        if rec not in {"ATOM", "HETATM", "TER", "END", "MODEL", "ENDMDL"}:
            continue
        if rec in {"TER", "END", "MODEL", "ENDMDL"}:
            salida.append(l)
            continue
        if len(l) < 27:
            continue
        rn = l[17:20].strip()
        ch = l[21:22].strip() or "A"
        if rn in rec07.AGUAS:
            stats["aguas_eliminadas"] += 1
            continue
        if ch != rec07.CADENA:
            stats["otra_cadena"] += 1
            continue
        try:
            sq = int(l[22:26].strip())
        except ValueError:
            continue
        if sq <= 0:
            continue
        variante = l[16:17].strip()
        if variante:
            if variante != elegido.get((ch, l[22:26].strip(), l[26:27])):
                stats["altloc_descartado"] += 1
                continue
            l = l[:16] + " " + l[17:]
        salida.append(l)
        stats["conservadas"] += 1
    destino.write_text("\n".join(salida) + "\nEND\n", encoding="utf-8")
    stats["altloc_cys25"] = elegido.get((rec07.CADENA, "25", " "), "sin altloc")
    return stats


def atomos_pdbqt(pdbqt: Path) -> dict[str, dict[str, tuple[float, float, float]]]:
    res: dict[str, dict[str, tuple[float, float, float]]] = {}
    for l in pdbqt.read_text(encoding="utf-8", errors="replace").splitlines():
        if not l.startswith(("ATOM", "HETATM")) or len(l) < 54:
            continue
        clave = f"{l[21:22].strip() or 'A'}:{l[17:20].strip()}{l[22:26].strip()}"
        res.setdefault(clave, {})[l[12:16].strip()] = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
    return res


def verificar_anclas(receptor: dict, referencia: dict) -> dict[str, Any]:
    """Cada átomo de la tríada debe estar en el receptor acoplado, donde lo pone el PDB."""
    detalle = {}
    for residuo, atomo in rec07.TRIADA:
        esperado = referencia[residuo][atomo]
        visto = receptor.get(residuo, {}).get(atomo)
        detalle[f"{residuo}:{atomo}"] = {
            "presente": visto is not None,
            "desviacion_A": round(math.dist(esperado, visto), 4) if visto else None,
        }
    ok = all(d["presente"] and d["desviacion_A"] <= TOLERANCIA_ANCLA_A for d in detalle.values())
    return {"ok": ok, "detalle": detalle}


def residuos(pdb_o_pdbqt: Path) -> set[str]:
    return {f"{l[21:22].strip() or 'A'}:{l[17:20].strip()}{l[22:26].strip()}"
            for l in pdb_o_pdbqt.read_text(encoding="utf-8", errors="replace").splitlines()
            if l.startswith(("ATOM", "HETATM")) and len(l) >= 26}


def sha256_file(p: Path) -> str:
    return rec07.sha256_file(p)


def acoplar(rec: Path, lig: Path, brazo: str, seed: int, sg, out: Path) -> dict[str, Any]:
    c, s = rec07.GRIDS[brazo]
    cmd = [str(VINA), "--receptor", str(rec), "--ligand", str(lig),
           "--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
           "--size_x", str(s[0]), "--size_y", str(s[1]), "--size_z", str(s[2]),
           "--exhaustiveness", str(rec07.EXHAUSTIVENESS), "--num_modes", str(rec07.NUM_MODES),
           "--seed", str(seed), "--cpu", str(rec07.CPU), "--out", str(out)]
    t1 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
        rc, texto = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        rc, texto = -9, "timeout"
    fila: dict[str, Any] = {"brazo": brazo, "seed": seed, "rc": rc, "centro": list(c),
                            "tamano": list(s), "wall_s": round(time.time() - t1, 2)}
    valido = rc == 0 and out.exists() and out.stat().st_size > 0
    if valido:
        modos = rec07.parsear_poses(out)
        fila["n_modos"] = len(modos)
        fila["scores_finitos"] = all(m["score"] is not None and math.isfinite(m["score"]) for m in modos)
        fila["geometria_parseable"] = all(m["atomos"] for m in modos)
        valido = 1 <= len(modos) <= rec07.NUM_MODES and fila["scores_finitos"] and fila["geometria_parseable"]
        if modos:
            top = modos[0]
            fila["score_top1"] = top["score"]
            fila["d_min_cys25_sg_top1"] = round(min(math.dist(a, sg) for a in top["atomos"]), 3)
            fila["contacto_top1"] = fila["d_min_cys25_sg_top1"] <= rec07.UMBRAL_CONTACTO_A
            fila["d_min_cys25_sg_mejor_de_9"] = round(
                min(min(math.dist(a, sg) for a in m["atomos"]) for m in modos), 3)
    else:
        fila["n_modos"] = 0
        fila["salida"] = texto[-400:]
    fila["valido"] = valido
    return fila


def _mediana(xs: list[float]):
    xs = sorted(xs)
    if not xs:
        return None
    k = len(xs) // 2
    return round(xs[k] if len(xs) % 2 else (xs[k - 1] + xs[k]) / 2, 3)


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-07-R1: REC-07 con la Cys25 en el receptor")
    ap.add_argument("--workers", type=int, default=10)
    ap.add_argument("--workdir", type=Path, default=OUT_DIR / "_work")
    args = ap.parse_args()
    t0 = time.time()
    hashes_pre = {p.name: sha256_file(p) for p in rec07.RUTAS_PROTEGIDAS if p.exists()}

    if sha256_file(LIGANDO) != LIGANDO_SHA256_REC07:
        print("[REC-07-R1] ABORTA: el ligando no es el que acopló REC-07")
        return 2
    referencia = rec07.leer_atomos(PDB_5TUN)       # primera ocurrencia = altloc A
    geo = rec07.geometria_por_brazo(referencia)
    sg = referencia["A:CYS25"]["SG"]

    wd = args.workdir
    wd.mkdir(parents=True, exist_ok=True)
    filtrado = wd / "5TUN_filtrado.pdb"
    stats = filtrar_pdb_coherente(PDB_5TUN, filtrado)
    rec_pdbqt = wd / "5TUN_receptor.pdbqt"
    if rec_pdbqt.exists():
        rec_pdbqt.unlink()
    c0, s0 = rec07.GRIDS["G_ADAPT"]
    r = subprocess.run(
        [sys.executable, "-m", "meeko.cli.mk_prepare_receptor",
         "--read_pdb", str(filtrado), "-o", str(wd / "5TUN_receptor"), "-p",
         "--box_center", str(c0[0]), str(c0[1]), str(c0[2]),
         "--box_size", str(s0[0]), str(s0[1]), str(s0[2]),
         "--default_altloc", "A", "-a"],
        capture_output=True, text=True, timeout=900)
    if not rec_pdbqt.exists():
        print(f"[REC-07-R1] FALLO preparando receptor:\n{r.stdout[-1500:]}\n{r.stderr[-1500:]}")
        return 2
    if any("HOH" in l for l in rec_pdbqt.read_text(encoding="utf-8", errors="replace").splitlines()):
        print("[REC-07-R1] ABORTA: el receptor conserva aguas")
        return 2
    anclas = verificar_anclas(atomos_pdbqt(rec_pdbqt), referencia)
    eliminados = sorted(residuos(filtrado) - residuos(rec_pdbqt))
    print(f"[REC-07-R1] altloc Cys25={stats['altloc_cys25']} | anclas {anclas} | "
          f"residuos eliminados por Meeko: {eliminados}", flush=True)
    if not anclas["ok"]:
        print("[REC-07-R1] ABORTA: la tríada no está en el receptor acoplado")
        return 2
    sg_receptor = atomos_pdbqt(rec_pdbqt)["A:CYS25"]["SG"]

    trabajos = [(b, s, wd / f"out_{b}_{s}.pdbqt") for b in rec07.GRIDS for s in rec07.SEEDS]
    trabajos += [(b, 42, wd / f"det_{b}_42.pdbqt") for b in rec07.GRIDS]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futuros = [ex.submit(acoplar, rec_pdbqt, LIGANDO, b, s, sg_receptor, out) for b, s, out in trabajos]
        resultados = [f.result() for f in futuros]
    filas = resultados[:len(rec07.GRIDS) * len(rec07.SEEDS)]
    repeticiones = resultados[len(filas):]
    for x in resultados:
        print(f"  {x['brazo']:<9} seed={x['seed']} rc={x['rc']} modos={x.get('n_modos')} "
              f"top1={x.get('score_top1')} d(Cys25)={x.get('d_min_cys25_sg_top1')} {x['wall_s']}s")

    por_brazo = {}
    for brazo in rec07.GRIDS:
        ok = [x for x in filas if x["brazo"] == brazo and x.get("valido")]
        d = [x["d_min_cys25_sg_top1"] for x in ok if "d_min_cys25_sg_top1" in x]
        sc = [x["score_top1"] for x in ok if x.get("score_top1") is not None]
        por_brazo[brazo] = {
            "geometria": geo[brazo],
            "n_corridas": sum(1 for x in filas if x["brazo"] == brazo), "n_validas": len(ok),
            "contacto_top1_n": sum(1 for x in ok if x.get("contacto_top1")),
            "contacto_top1_de": len(rec07.SEEDS),
            "d_cys25_top1_mediana": _mediana(d),
            "d_cys25_top1_min": round(min(d), 3) if d else None,
            "score_top1_mediana": _mediana(sc),
            "score_top1_mejor": round(min(sc), 3) if sc else None,
        }

    d_db = geo["G_DB"]["d_cys25_sg"]
    elegibles = [b for b, g in geo.items() if g["hotspots_dentro"] == g["hotspots_total"]
                 and g["triada_dentro"] == 3 and g["d_cys25_sg"] <= d_db]
    recomendado = min(elegibles, key=lambda b: geo[b]["volumen_A3"]) if elegibles else None
    g4 = g5 = None
    if recomendado:
        r_, db_ = por_brazo[recomendado], por_brazo["G_DB"]
        g4 = r_["contacto_top1_n"] >= 3
        peor = (r_["d_cys25_top1_mediana"] is not None and db_["d_cys25_top1_mediana"] is not None
                and r_["d_cys25_top1_mediana"] - db_["d_cys25_top1_mediana"] > 1.0)
        g5 = r_["contacto_top1_n"] >= db_["contacto_top1_n"] and not peor
    original = {x["brazo"]: x for x in filas if x["seed"] == 42}
    det = [{"brazo": x["brazo"],
            "score_igual": x.get("score_top1") == original[x["brazo"]].get("score_top1"),
            "distancia_igual": x.get("d_min_cys25_sg_top1") == original[x["brazo"]].get("d_min_cys25_sg_top1")}
           for x in repeticiones]
    hashes_post = {p.name: sha256_file(p) for p in rec07.RUTAS_PROTEGIDAS if p.exists()}

    gates = {
        "G0_ancla_en_el_receptor": {
            "criterio": f"Cys25 SG, His162 NE2 y Asn182 ND2 en el receptor acoplado a <= {TOLERANCIA_ANCLA_A} A",
            "detalle": anclas["detalle"], "pass": anclas["ok"]},
        "G1_contencion": {"criterio": "grid recomendado con 15/15 hotspots y 3/3 triada",
                          "recomendado": recomendado, "pass": bool(recomendado)},
        "G2_ancla": {"criterio": f"d(centro, Cys25 SG) <= {d_db} A (G_DB)",
                     "d_recomendado": geo[recomendado]["d_cys25_sg"] if recomendado else None,
                     "d_G_DB": d_db, "pass": bool(recomendado and geo[recomendado]["d_cys25_sg"] <= d_db)},
        "G3_validez_docking": {"criterio": "rc=0, no vacio, 1<=modos<=9, scores finitos, geometria parseable",
                               "n_corridas": len(filas), "n_validas": sum(1 for x in filas if x.get("valido")),
                               "pass": all(x.get("valido") for x in filas)},
        "G4_contacto_catalitico": {"criterio": f"top-1 a <= {rec07.UMBRAL_CONTACTO_A} A de Cys25 SG en >=3 de 5 semillas",
                                   "contacto_n": por_brazo[recomendado]["contacto_top1_n"] if recomendado else None,
                                   "pass": g4},
        "G5_no_regresion": {"criterio": "tasa de contacto no menor que G_DB y mediana no peor por mas de 1.0 A",
                            "pass": g5},
        "G6_determinismo": {"criterio": "misma semilla -> mismo top1 y misma distancia (seed 42, los 3 brazos)",
                            "repeticiones": det,
                            "pass": all(d["score_igual"] and d["distancia_igual"] for d in det)},
        "G7_solo_lectura": {"criterio": "catalogo y CSV conservan su SHA-256",
                            "hashes_pre": hashes_pre, "hashes_post": hashes_post,
                            "pass": hashes_pre == hashes_post},
    }
    metricas = {
        "experiment_id": EXPERIMENT_ID,
        "target": "5TUN",
        "corrige": "REC-07 (SCI-B-022): su receptor no contenia la Cys25",
        "cambios_frente_a_REC07": [
            "altloc coherente (regla de preparer.py): comunes + variante por ocupacion, desempate en A",
            "aborto si la triada no esta en el receptor acoplado",
            "corridas en paralelo, cada una con --cpu 1",
        ],
        "config_docking": {
            "importada_de": "scripts/run_rec07_grid_5tun.py (sellado en REC-07)",
            "exhaustiveness": rec07.EXHAUSTIVENESS, "num_modes": rec07.NUM_MODES, "cpu": rec07.CPU,
            "seeds": list(rec07.SEEDS), "umbral_contacto_A": rec07.UMBRAL_CONTACTO_A,
            "receptor_sha256": sha256_file(rec_pdbqt), "ligando_sha256": sha256_file(LIGANDO),
            "filtro_receptor": stats, "residuos_eliminados_por_meeko": eliminados,
            "meeko_stdout_cola": r.stdout[-600:],
        },
        "por_brazo": por_brazo,
        "recomendado": recomendado,
        "gates": gates,
        "entorno": {
            "python": platform.python_version(), "so": f"{platform.system()} {platform.release()}",
            "vina_sha256": sha256_file(VINA), "workers": args.workers,
            "duracion_s": round(time.time() - t0, 2),
            "generado_utc": datetime.now(timezone.utc).isoformat(),
        },
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for x in filas:
            f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT_DIR / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for x in resultados:
            if not x.get("valido"):
                f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT_DIR / "metrics.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(metricas, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    for nombre in ("5TUN_filtrado.pdb", "5TUN_receptor.pdbqt"):
        shutil.copyfile(wd / nombre, OUT_DIR / nombre)
    for g, d in gates.items():
        print(f"  {g:<26} {'PASS' if d['pass'] else ('FAIL' if d['pass'] is False else 'PENDIENTE')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
