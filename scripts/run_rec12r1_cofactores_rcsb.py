#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""REC-12-R1: el inventario de cofactores del sitio, desde la entrada original de RCSB.

REC-12 salio INCONCLUSIVE porque su G1 de validez de la fuente fallo: 1 de 48 = 0.0208.
La causa quedo medida: `data/pdbbind/<pid>/<pid>_protein.pdb` viene LIMPIADO por PDBBind
-conserva aguas y metales y elimina el resto de heteroatomos-, asi que el cero de
cofactores que produjo era del ARCHIVO y no de las estructuras. Lo que eso establecio es
un punto ciego: todos los receptores del programa se construyeron desde esa fuente, y si
a alguno le falta un NAD, un FAD o un hemo para tener el sitio completo, la evidencia se
pierde en el mismo archivo del que se parte.

Este R1 cambia UNA sola cosa: la fuente de la estructura original pasa a ser la entrada
de RCSB. El analisis es el de REC-12, importado del modulo sellado y no reescrito, tal
como exige el docs/49 seccion 17 -un artefacto sellado no se edita ni para una extension
compatible; se extiende por composicion-.

Ampliacion declarada ANTES de correr: sobre la entrada cruda de RCSB aparecen aditivos de
cristalizacion -glicerol, sulfato, PEG- que en el `_protein.pdb` limpiado no existian.
Contarlos como cofactores inflaria el inventario. Por eso se declara aqui, antes de mirar,
la lista ADITIVOS, y se reportan DOS cuentas por complejo: la bruta y la que excluye
aditivos. El gate se lee sobre la segunda.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

# Modulo sellado de REC-12: se importa, no se copia ni se edita.
import analisis_rec12_cofactores as r12

URL = "https://files.rcsb.org/download/{pid}.pdb"
REINTENTOS, PAUSA_S = 3, 2.0

# Aditivos de cristalizacion y crioprotectores. Declarado ANTES de ejecutar.
# No son cofactores funcionales; su presencia junto al sitio es un artefacto del
# experimento de difraccion, no parte del sistema biologico.
ADITIVOS = {
    "GOL", "EDO", "PEG", "PG4", "PGE", "1PE", "2PE", "P6G", "PE4", "MPD", "BU3",
    "SO4", "PO4", "NO3", "ACT", "ACY", "FMT", "CIT", "FLC", "TLA", "MLA", "MLI",
    "DMS", "TRS", "EPE", "MES", "BTB", "BIS", "IMD", "CAC", "PIN", "HEP",
    "BME", "DTT", "MRD", "IPA", "ETA", "URE", "GLC", "NAG", "BOG", "LDA", "C8E",
    "AZI", "CYN", "SCN", "OXL", "TAR", "SIN", "MAE", "PYR",
}


def _descargar(pid: str, destino: Path) -> Dict[str, Any]:
    """Baja <pid>.pdb de RCSB. Idempotente: si ya existe con contenido, no repite."""
    if destino.exists() and destino.stat().st_size > 0:
        return {"pid": pid, "estado": "YA_PRESENTE", "bytes": destino.stat().st_size}
    destino.parent.mkdir(parents=True, exist_ok=True)
    ultimo = ""
    for intento in range(1, REINTENTOS + 1):
        try:
            with urllib.request.urlopen(URL.format(pid=pid), timeout=60) as resp:
                datos = resp.read()
            tmp = destino.with_suffix(".pdb.part")
            tmp.write_bytes(datos)
            tmp.replace(destino)
            return {"pid": pid, "estado": "DESCARGADO", "bytes": len(datos)}
        except urllib.error.HTTPError as ex:
            ultimo = f"HTTP {ex.code}"
            if ex.code == 404:
                break          # no existe en formato PDB legacy; no se reintenta
        except Exception as ex:                      # noqa: BLE001
            ultimo = f"{type(ex).__name__}"
        if intento < REINTENTOS:
            time.sleep(PAUSA_S)
    return {"pid": pid, "estado": "SIN_ENTRADA_PDB", "motivo": ultimo}


def _inventario(pid: str, estrato: str, orig: Path, prep: Path, sdf: Path,
                mf: Any) -> Dict[str, Any]:
    """El analisis de REC-12, con sus funciones y sus constantes, sobre otra fuente."""
    f: Dict[str, Any] = {"pid": pid, "estrato": estrato}
    if not orig.exists() or not prep.exists() or not sdf.exists():
        f["error"] = "SIN_ESTRUCTURA"
        return f
    crystal = mf.leer_ligando(sdf)
    if crystal is None:
        f["error"] = "SDF_ILEGIBLE"
        return f
    conf = crystal.GetConformer()
    lig_pts = [(conf.GetAtomPosition(a.GetIdx()).x, conf.GetAtomPosition(a.GetIdx()).y,
                conf.GetAtomPosition(a.GetIdx()).z)
               for a in crystal.GetAtoms() if a.GetAtomicNum() > 1]
    prep_pts = r12._todos(prep)

    hets = r12._hetatm(orig)
    f["hetatm_no_agua_no_metal_en_toda_la_estructura"] = sum(
        1 for resn, el, _x, _y, _z in hets
        if resn not in r12.AGUAS and el not in r12.METALES and resn not in r12.METALES)

    bruto: List[str] = []
    cof: List[str] = []
    vivos = 0
    for resn, el, x, y, z in hets:
        if resn in r12.AGUAS or el in r12.METALES or resn in r12.METALES:
            continue
        if not r12._cerca(x, y, z, lig_pts, r12.R_SITIO):
            continue
        # el propio ligando figura como HETATM: se descarta por solapamiento exacto
        if r12._cerca(x, y, z, lig_pts, r12.TOL):
            continue
        bruto.append(resn)
        if resn in ADITIVOS:
            continue
        cof.append(resn)
        if r12._cerca(x, y, z, prep_pts, r12.TOL):
            vivos += 1

    f["bruto_atomos_sitio"] = len(bruto)
    f["especies_bruto"] = sorted(set(bruto))
    f["aditivos_atomos_sitio"] = len(bruto) - len(cof)
    f["especies_aditivos"] = sorted({r for r in bruto if r in ADITIVOS})
    f["cofactores_atomos_sitio"] = len(cof)
    f["cofactores_conservados"] = vivos
    f["cofactores_perdidos"] = len(cof) - vivos
    f["especies"] = sorted(set(cof))
    f["tiene_cofactor"] = bool(cof)
    return f


def main() -> int:
    import molflex as mf

    ap = argparse.ArgumentParser(
        description="REC-12-R1: cofactores del sitio desde la entrada original de RCSB")
    ap.add_argument("--workspace", default="/workspace")
    ap.add_argument("--solo-descargar", action="store_true",
                    help="baja las entradas y termina; no produce lectura")
    args = ap.parse_args()
    ws = Path(args.workspace)
    art = ws / "scripts" / "artifacts_science"
    out_dir = art / "REC-12-R1"
    out_dir.mkdir(parents=True, exist_ok=True)
    crudo = ws / "data" / "rcsb"

    m13: Dict[str, str] = {}
    for l in (art / "MF-13" / "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            m13[r["pid"]] = r.get("estrato", "RESTO")

    r09: Dict[str, Any] = {}
    p09 = art / "REC-09" / "per_complex.jsonl"
    if p09.exists():
        for l in p09.read_text(encoding="utf-8").splitlines():
            if l.strip():
                r = json.loads(l)
                r09[r["pid"]] = r

    descargas = []
    for n, pid in enumerate(sorted(m13), 1):
        d = _descargar(pid, crudo / f"{pid}.pdb")
        descargas.append(d)
        if n % 20 == 0 or d["estado"] == "SIN_ENTRADA_PDB":
            print(f"  [{n}/{len(m13)}] {pid} {d['estado']}", flush=True)
    sin_entrada = [d["pid"] for d in descargas if d["estado"] == "SIN_ENTRADA_PDB"]
    print(f"[REC-12-R1] descargas: {len(descargas)-len(sin_entrada)}/{len(descargas)} "
          f"disponibles; sin entrada PDB: {sin_entrada}", flush=True)
    if args.solo_descargar:
        return 0

    filas: List[Dict[str, Any]] = []
    especies = Counter()
    for pid, estrato in sorted(m13.items()):
        f = _inventario(pid, estrato, crudo / f"{pid}.pdb",
                        ws / "data" / "molflex_train_v2" / pid / pid / "rec.pdbqt",
                        ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf", mf)
        if pid in r09:
            f["score_cristal"] = r09[pid].get("score_con_aguas")
            f["absurdo"] = r09[pid].get("absurdo")
            f["aguas_bloqueantes"] = r09[pid].get("n_aguas_bloqueantes")
        for r in set(f.get("especies", [])):
            especies[r] += 1
        filas.append(f)

    ok = [f for f in filas if "cofactores_atomos_sitio" in f]
    con = [f for f in ok if f["tiene_cofactor"]]
    perdidos = [f for f in ok if f.get("cofactores_perdidos", 0) > 0]
    absurdos = [f for f in ok if f.get("absurdo")]
    sin_agua_bloq = [f for f in absurdos if (f.get("aguas_bloqueantes") or 0) == 0]

    con_hetatm = sum(1 for f in ok if f.get("hetatm_no_agua_no_metal_en_toda_la_estructura", 0) > 0)
    g1 = round(con_hetatm / len(ok), 4) if ok else 0.0
    g1_pasa = g1 >= 0.05

    if not g1_pasa:
        lectura = "LA_FUENTE_TAMPOCO_SIRVE"
    elif perdidos:
        lectura = "HAY_RECEPTORES_INCOMPLETOS"
    else:
        lectura = "NINGUN_RECEPTOR_PIERDE_COFACTORES"

    out = {
        "analisis_id": "REC-12-R1",
        "tipo": "inventario desde la fuente original, con gate de validez de la fuente",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fuente": "https://files.rcsb.org/download/<pid>.pdb",
        "cambio_unico_frente_a_REC-12": "la estructura original; el analisis se importa del modulo sellado",
        "config": {"r_sitio_A": r12.R_SITIO, "tol_A": r12.TOL,
                   "n_aditivos_declarados": len(ADITIVOS)},
        "descargas": {"disponibles": len(descargas) - len(sin_entrada),
                      "de": len(descargas), "sin_entrada_pdb": sin_entrada},
        "n_complejos": len(filas), "n_ok": len(ok),
        "G1_VALIDEZ_DE_LA_FUENTE": {
            "definicion": "fraccion de complejos cuya estructura original contiene algun HETATM que no es agua ni metal, en cualquier parte",
            "con_hetatm": con_hetatm, "de": len(ok), "fraccion": g1,
            "minimo": 0.05, "pasa": g1_pasa,
            "referencia_REC-12": {"fraccion": 0.0208, "paso": False}},
        "inventario": {
            "complejos_con_cofactor_en_el_sitio": len(con),
            "complejos_con_cofactor_PERDIDO": len(perdidos),
            "pids_con_cofactor_perdido": sorted(f["pid"] for f in perdidos),
            "especies_mas_frecuentes": especies.most_common(15),
            "atomos_aditivos_en_sitio_total": sum(f.get("aditivos_atomos_sitio", 0) for f in ok)},
        "secundario_descriptivo": {
            "nota": "sin gate; REC-09 dejo 1d7i y 1ew9 sin explicar",
            "cristales_absurdos": len(absurdos),
            "absurdos_sin_agua_bloqueante": sorted(f["pid"] for f in sin_agua_bloq),
            "de_esos_con_cofactor_en_el_sitio": sorted(
                f["pid"] for f in sin_agua_bloq if f.get("tiene_cofactor"))},
        "lectura_preregistrada": lectura,
        "limites_declarados": [
            "la entrada de RCSB es la unidad asimetrica depositada, no la assembly biologica; REC-08 gobierna esa cuestion y aqui no se toca",
            "un cofactor cerca del sitio no demuestra que el sitio lo necesite; establece que el receptor preparado no lo tiene",
            "la lista ADITIVOS se declaro antes de ejecutar y es finita: una especie no listada cuenta como cofactor",
            "no cambia ningun receptor ni re-sella ningun artefacto",
        ],
    }
    (out_dir / "metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                          encoding="utf-8", newline="\n")
    (out_dir / "per_complex.jsonl").write_text(
        "".join(json.dumps(f, ensure_ascii=False, sort_keys=True) + "\n" for f in filas),
        encoding="utf-8", newline="\n")
    (out_dir / "failures.jsonl").write_text(
        "".join(json.dumps({"pid": f["pid"], "error": f["error"]}, ensure_ascii=False) + "\n"
                for f in filas if "error" in f),
        encoding="utf-8", newline="\n")
    print(f"[REC-12-R1] G1={g1} pasa={g1_pasa} con_cofactor={len(con)} "
          f"perdidos={len(perdidos)} lectura={lectura}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
