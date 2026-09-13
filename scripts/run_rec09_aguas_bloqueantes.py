#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rec09_aguas_bloqueantes.py — REC-09: las aguas que el pipeline conserva, ¿bloquean el sitio?

Corre en el contenedor `moldesign-lab` del servidor, el mismo de `MF-13` y `MF-29-EMP`.

De donde sale
-------------
`MF-13` encontro cristales que puntuan absurdamente mal -`1fkh` a -1.631 y `1ew8` a -2.181-
y escribio en su lectura que *«un cristal que puntua -1.63 o -2.18 kcal/mol no es un fallo
de la funcion de puntuacion: es un sistema mal montado»*, apuntando a que faltase un
cofactor, un metal o una agua estructural, o a protonacion incorrecta. `MF-29-EMP-COR`
agravo el caso: `1ew8` preparado flexible puntua **+1.714**, positivo.

Pero `REC-08-EXT` ya midio que la preparacion **no pierde nada**: de 42 metales del sitio
conserva 42, y de 1788 aguas del sitio conserva 1788. El problema no es lo que falta.

**La hipotesis se invierte: el problema es lo que SOBRA.** El pipeline conserva TODAS las
aguas -y esa politica nadie la declaro, es el hallazgo abierto de `REC-08-EXT`-, incluidas
las que el ligando desplaza al unirse. Un agua que ocupa el sitio choca con el ligando
cristalografico y dispara el termino de repulsion de Vina. `1ew8` conserva 511 atomos de
agua en su `rec.pdbqt`.

Que se mide
-----------
Para cada complejo de train, sin recomputar ningun docking:

  1. Aguas del receptor con algun atomo a **<= d_clash de un atomo pesado del ligando
     cristalografico**. `d_clash = 2.6 A`, el mismo valor que `MF-28` declaro antes de
     correr para su criterio de nodo libre. Se reusa y no se ajusta.
  2. `score_only` del cristal contra `rec.pdbqt` tal cual -> `score_con_aguas`.
  3. `score_only` del cristal contra el mismo receptor **sin las aguas que chocan** y solo
     esas -> `score_sin_bloqueantes`.
  4. `delta = score_con_aguas - score_sin_bloqueantes`. Es **> 0** cuando quitarlas mejora.

El cristal se prepara **rigido**, el `rigid_str` de `molflex.escribir_pdbqt`, identico a
`MF-13`. Misma caja de 25 A, misma semilla 42, mismo binario. La leccion de
`MF-29-EMP-COR` aplicada: los dos scores de cada pareja salen del MISMO PDBQT de ligando,
asi que la comparacion no cruza escalas torsionales -y como el ligando no cambia entre los
dos brazos, la penalizacion se cancela en el `delta` sea cual sea-.

Umbral de «absurdo», declarado ANTES y no ajustado
--------------------------------------------------
`score_cristal >= -3.0 kcal/mol`. No se elige mirando estos datos: sale de la lectura ya
sellada de `MF-13`, que nombro -1.631 y -2.181 como sistemas mal montados. Ningun ligando
cristalizado une asi de mal.

Lectura preregistrada
---------------------
`f` = fraccion de los complejos ABSURDOS que se **normalizan** al quitar las aguas
bloqueantes, entendiendo por normalizar que su score baje de -3.0.

  * `f >= 0.70` **y** delta mediano en los NO absurdos < 0.5 -> **LAS AGUAS BLOQUEAN**.
    Conservarlas todas es un defecto de produccion y la politica hay que cambiarla, no solo
    declararla.
  * `f <= 0.30` -> **LAS AGUAS NO SON LA EXPLICACION**. Hay que buscar en cofactores no
    metalicos -HETATM que no son ni agua ni metal, que nadie ha inventariado- o en
    protonacion.
  * intermedio, o `f >= 0.70` con delta mediano en los NO absurdos >= 0.5 -> **MIXTO**: si
    quitar aguas mejora a todos por igual, el efecto es global y no explica el absurdo.

El control de los NO absurdos esta en la regla a proposito: sin el, cualquier mejora se
leeria como confirmacion.

Gate de validez, ANTES del primario
-----------------------------------
**G1**: `score_con_aguas` reproduce el `score_cristal` de `MF-13` dentro de 0.10 kcal/mol en
>= 95% de los complejos. Es la comprobacion de que se esta puntuando lo mismo que puntuo
`MF-13`; si no reproduce, el brazo de comparacion no es el suyo y nada de esto se lee.

Limites declarados ANTES de correr
----------------------------------
1. **Esto no decide la politica de aguas por si solo.** Mide una consecuencia concreta de
   conservarlas: si bloquean el sitio del propio cristal. Una politica de aguas necesita
   ademas el efecto sobre el docking de novo, que aqui no se toca.
2. **No relee `MF-13`.** Su `~30% de puntuacion` incluye complejos que no son absurdos y
   sobre los que esto no dice nada.
3. Quitar un agua que el ligando desplaza es **fisicamente correcto**; quitar una
   estructural que media un puente de hidrogeno, no. Este experimento no las distingue: usa
   un criterio puramente geometrico de choque. Por eso su lectura, si sale, es que la
   politica hay que **decidirla**, no que la respuesta sea «quitarlas todas».
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

BOX = 25.0
SEED = 42
D_CLASH = 2.6          # el mismo que MF-28 declaro antes de correr
UMBRAL_ABSURDO = -3.0  # de la lectura sellada de MF-13
G1_TOL = 0.10
G1_MIN = 0.95
DELTA_CONTROL_MAX = 0.5
RESNAMES_AGUA = {"HOH", "WAT", "DOD"}


def _vina() -> str:
    return os.environ.get("REC09_VINA", "/usr/local/bin/vina")


def _correr_vina(args: List[str], timeout: int = 120) -> Optional[str]:
    try:
        p = subprocess.run([_vina()] + args, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    return p.stdout if p.returncode == 0 else None


def _score(texto: str) -> Optional[float]:
    for l in texto.splitlines():
        if "Estimated Free Energy of Binding" in l:
            try:
                return float(l.split(":")[1].split()[0])
            except (IndexError, ValueError):
                return None
    return None


def _caja(c) -> List[str]:
    return ["--center_x", str(c[0]), "--center_y", str(c[1]), "--center_z", str(c[2]),
            "--size_x", str(BOX), "--size_y", str(BOX), "--size_z", str(BOX)]


def _parsear_receptor(texto: str) -> List[Tuple[str, Optional[Tuple[float, float, float]], str]]:
    """Devuelve (linea, coords o None, resname) por linea del PDBQT."""
    filas = []
    for l in texto.splitlines():
        if l.startswith(("ATOM", "HETATM")):
            try:
                xyz = (float(l[30:38]), float(l[38:46]), float(l[46:54]))
            except (ValueError, IndexError):
                xyz = None
            filas.append((l, xyz, l[17:20].strip().upper()))
        else:
            filas.append((l, None, ""))
    return filas


def analizar(ws: Path, pid: str, estrato: str, ref: Dict[str, Any], tmp: Path) -> Dict[str, Any]:
    import molflex as mf
    from meeko import MoleculePreparation
    from rdkit import Chem

    out: Dict[str, Any] = {"pid": pid, "estrato": estrato,
                           "score_cristal_mf13": ref.get("score_cristal")}
    t0 = time.time()
    w = ws / "data" / "molflex_train_v2" / pid / pid
    rec, cen = w / "rec.pdbqt", w / "center.json"
    if not rec.exists() or not cen.exists():
        out["error"] = "SIN_RECEPTOR_O_CAJA"
        return out
    centro = json.loads(cen.read_text(encoding="utf-8"))

    crystal = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
    if crystal is None:
        out["error"] = "SDF_ILEGIBLE"
        return out
    try:
        mh = Chem.AddHs(crystal, addCoords=True)
        setups = MoleculePreparation().prepare(mh, conformer_id=0)
        rigid, _flex, mapa, _err = mf.escribir_pdbqt(setups[0])
    except Exception as ex:
        out["error"] = f"MEEKO:{type(ex).__name__}:{str(ex)[-100:]}"
        return out
    if not rigid or not mapa:
        out["error"] = "PREP_CRISTAL_FALLO"
        return out
    lig = tmp / f"{pid}_cristal.pdbqt"
    lig.write_text(rigid, encoding="utf-8")

    # atomos pesados del ligando cristalografico
    conf = crystal.GetConformer()
    pesados = [(conf.GetAtomPosition(a.GetIdx()).x, conf.GetAtomPosition(a.GetIdx()).y,
                conf.GetAtomPosition(a.GetIdx()).z)
               for a in crystal.GetAtoms() if a.GetAtomicNum() > 1]
    out["n_atomos_pesados_ligando"] = len(pesados)

    filas = _parsear_receptor(rec.read_text(encoding="utf-8", errors="replace"))
    d2 = D_CLASH * D_CLASH
    n_agua_total = sum(1 for _l, xyz, rn in filas if rn in RESNAMES_AGUA and xyz)
    bloqueantes = set()
    for i, (_l, xyz, rn) in enumerate(filas):
        if rn not in RESNAMES_AGUA or xyz is None:
            continue
        for (lx, ly, lz) in pesados:
            if (xyz[0]-lx)**2 + (xyz[1]-ly)**2 + (xyz[2]-lz)**2 <= d2:
                bloqueantes.add(i)
                break
    out["n_atomos_agua_receptor"] = n_agua_total
    out["n_aguas_bloqueantes"] = len(bloqueantes)

    base = _caja(centro) + ["--seed", str(SEED), "--cpu", "1", "--score_only"]
    s1 = _correr_vina(["--receptor", str(rec), "--ligand", str(lig)] + base)
    out["score_con_aguas"] = _score(s1) if s1 else None

    if bloqueantes:
        rec2 = tmp / f"{pid}_rec_sin_bloqueantes.pdbqt"
        rec2.write_text("\n".join(l for i, (l, _x, _r) in enumerate(filas)
                                  if i not in bloqueantes) + "\n", encoding="utf-8")
        s2 = _correr_vina(["--receptor", str(rec2), "--ligand", str(lig)] + base)
        out["score_sin_bloqueantes"] = _score(s2) if s2 else None
        try:
            rec2.unlink()
        except OSError:
            pass
    else:
        out["score_sin_bloqueantes"] = out["score_con_aguas"]

    a, b = out.get("score_con_aguas"), out.get("score_sin_bloqueantes")
    if a is not None and b is not None:
        out["delta"] = round(a - b, 3)                 # >0 => quitarlas mejora
        out["absurdo"] = bool(a >= UMBRAL_ABSURDO)
        out["normaliza"] = bool(a >= UMBRAL_ABSURDO and b < UMBRAL_ABSURDO)
    r13 = ref.get("score_cristal")
    if a is not None and r13 is not None:
        out["g1_delta_vs_mf13"] = round(abs(a - r13), 3)
        out["g1_reproduce"] = bool(abs(a - r13) <= G1_TOL)
    try:
        lig.unlink()
    except OSError:
        pass
    out["t_s"] = round(time.time() - t0, 1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-09: aguas que bloquean el sitio del cristal")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--limite", type=int, default=None)
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "REC-09"
    out_dir.mkdir(parents=True, exist_ok=True)

    m13 = {}
    for l in (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            m13[r["pid"]] = r
    jobs = sorted((pid, r.get("estrato", "RESTO"), r) for pid, r in m13.items())
    if args.limite:
        jobs = jobs[:args.limite]

    print(f"[REC-09] {len(jobs)} complejos | d_clash={D_CLASH} A | "
          f"umbral absurdo={UMBRAL_ABSURDO} | workers={args.workers}", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            futs = {ex.submit(analizar, ws, pid, est, ref, tmp): pid for pid, est, ref in jobs}
            for i, fut in enumerate(as_completed(futs), 1):
                filas.append(fut.result())
                r = filas[-1]
                if i % 10 == 0 or r.get("absurdo") or r.get("error"):
                    print(f"  [{i}/{len(jobs)}] {r['pid']} aguas_bloq={r.get('n_aguas_bloqueantes')} "
                          f"con={r.get('score_con_aguas')} sin={r.get('score_sin_bloqueantes')} "
                          f"delta={r.get('delta')} absurdo={r.get('absurdo')} "
                          f"{r.get('error','')} ({round(time.time()-t0)}s)", flush=True)
                with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
                    for x in filas:
                        fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "delta" in r]
    g1 = [r for r in filas if r.get("g1_reproduce") is not None]
    g1_frac = (sum(1 for r in g1 if r["g1_reproduce"]) / len(g1)) if g1 else 0.0
    absurdos = [r for r in ok if r["absurdo"]]
    normales = [r for r in ok if not r["absurdo"]]
    n_norm = sum(1 for r in absurdos if r["normaliza"])
    f = (n_norm / len(absurdos)) if absurdos else None
    d_control = median([r["delta"] for r in normales]) if normales else None

    lectura = None
    if f is not None:
        if f >= 0.70 and d_control is not None and d_control < DELTA_CONTROL_MAX:
            lectura = "LAS_AGUAS_BLOQUEAN"
        elif f <= 0.30:
            lectura = "LAS_AGUAS_NO_SON_LA_EXPLICACION"
        else:
            lectura = "MIXTO"

    metrics = {
        "experiment_id": "REC-09",
        "tipo": "medicion de consecuencia con regla de lectura preregistrada",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "config": {"d_clash_A": D_CLASH, "umbral_absurdo_kcal": UMBRAL_ABSURDO,
                   "box": BOX, "seed": SEED, "g1_tolerancia": G1_TOL,
                   "delta_control_max": DELTA_CONTROL_MAX,
                   "ligando": "cristal preparado RIGIDO, identico a MF-13",
                   "resnames_agua": sorted(RESNAMES_AGUA)},
        "n_complejos": len(filas), "n_ok": len(ok),
        "gate_validez": {
            "G1_reproduce_score_cristal_de_MF13": {
                "fraccion": round(g1_frac, 4), "minimo": G1_MIN,
                "tolerancia_kcal": G1_TOL, "pasa": bool(g1_frac >= G1_MIN)}},
        "cantidad_primaria": {
            "definicion": "fraccion de complejos ABSURDOS (score_con_aguas >= -3.0) que bajan de -3.0 al quitar SOLO las aguas que chocan",
            "n_absurdos": len(absurdos), "n_normalizan": n_norm,
            "fraccion": round(f, 4) if f is not None else None,
            "control_delta_mediano_en_no_absurdos": round(d_control, 3) if d_control is not None else None,
            "lectura_preregistrada": lectura},
        "contexto": {
            "complejos_con_alguna_agua_bloqueante": sum(1 for r in ok if r["n_aguas_bloqueantes"] > 0),
            "aguas_bloqueantes_mediana": median([r["n_aguas_bloqueantes"] for r in ok]) if ok else None,
            "aguas_bloqueantes_max": max((r["n_aguas_bloqueantes"] for r in ok), default=None),
            "delta_mediano_global": round(median([r["delta"] for r in ok]), 3) if ok else None,
            "absurdos": sorted([r["pid"] for r in absurdos])},
        "limites_declarados": [
            "no decide la politica de aguas por si solo: mide una consecuencia concreta, no el efecto sobre docking de novo",
            "no relee MF-13; su ~30% de puntuacion incluye complejos que no son absurdos",
            "criterio de choque puramente geometrico: no distingue agua desplazable de agua estructural, por eso su lectura es que la politica hay que DECIDIRLA",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    print(f"[REC-09] LISTO n={len(ok)} G1={round(g1_frac,4)} absurdos={len(absurdos)} "
          f"normalizan={n_norm} f={f} control={d_control} lectura={lectura} "
          f"({round(time.time()-t0)}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
