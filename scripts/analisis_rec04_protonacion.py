#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_rec04_protonacion.py — REC-04a: auditoría de protonación (FEP-01/FEP-02).

**Tipo: medición.** Auditoría del material en disco. Sin docking.

Por qué esto y por qué ahora
----------------------------
Con MolDesign posicionado como **software de entrada que prepara paquetes para FEP+**,
la protonación deja de ser un detalle y pasa a ser la causa de fallo número uno: un
estado de protonación mal asignado en un residuo del sitio o en el ligando arruina un
cálculo de energía libre entero, y lo hace en silencio.

`REC-04` está en la cartera B sin ejecutar. `FEP-01` (integridad química del ligando:
«estereo, tautómero, protonación, carga y atom mapping explícitos») y `FEP-02`
(integridad del receptor) están en la cartera H, también sin artefactos.

La versión completa de `REC-04` —¿cambia el ranking al variar la protonación?— exige
re-dockear y va al servidor. Ésta es la parte que se puede hacer sin docking y que hay
que hacer **antes**: **¿qué decisiones de protonación toma hoy el pipeline, y cuáles
toma en silencio?**

El hallazgo que motiva la auditoría
-----------------------------------
El `provenance.json` del propio pipeline declara:

    "receptor": {"protonation": "pdb_original", "tool": "openbabel_pdb2pdbqt_rigido"}

Es decir: **el pipeline no toma ninguna decisión de protonación del receptor**. Hereda
la que traiga el fichero de PDBBind. Para docking con Vina eso es defendible —su función
de puntuación es poco sensible a hidrógenos—, pero para un paquete FEP+ es un hueco
declarado que hay que cuantificar.

Qué se mide
-----------
Por complejo:

  * **receptor**: ¿trae hidrógenos el PDB? ¿cuántos residuos titulables hay en el sitio
    (HIS, ASP, GLU, LYS, ARG, CYS, TYR)? **HIS** aparte, porque es el ambiguo a pH 7.4
    y el que más daño hace en FEP+;
  * **ligando**: carga formal del SDF, número de átomos con carga, y si RDKit detecta
    grupos ionizables cuyo estado a pH 7.4 diferiría del que trae el fichero.

No se propone una corrección. Se mide el tamaño del hueco.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

PDBBIND = PROJECT_ROOT / "data" / "pdbbind"
MAT = PROJECT_ROOT / "data" / "molflex_train_v2"
ART = PROJECT_ROOT / "scripts" / "artifacts_science"
OUT_DIR = ART / "REC-04"
TITULABLES = {"HIS", "ASP", "GLU", "LYS", "ARG", "CYS", "TYR"}
RADIO_SITIO = 8.0

# grupos cuyo estado de ionizacion a pH 7.4 suele diferir del que trae un SDF
IONIZABLES = {
    "acido_carboxilico": "[CX3](=O)[OX2H1]",
    "carboxilato": "[CX3](=O)[OX1-]",
    "amina_primaria": "[NX3;H2;!$(N[!#6]);!$(N=*)]",
    "amina_secundaria": "[NX3;H1;!$(N[!#6]);!$(N=*)]",
    "amidina_guanidina": "[NX3][CX3]=[NX2]",
    "tetrazol": "c1nnn[nH]1",
    "fosfato_sulfato": "[PX4,SX4](=O)([OX2H1,OX1-])",
}


def _analizar(pid: str) -> Dict[str, Any]:
    from rdkit import Chem
    out: Dict[str, Any] = {"pid": pid}
    prot = PDBBIND / pid / f"{pid}_protein.pdb"
    sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
    if not prot.exists() or not sdf.exists():
        out["error"] = "SIN_FICHEROS"
        return out
    cen_f = MAT / pid / pid / "center.json"
    centro = json.loads(cen_f.read_text(encoding="utf-8")) if cen_f.exists() else None

    n_h = 0
    residuos_sitio = Counter()
    residuos_todos = Counter()
    vistos = set()
    for l in prot.read_text(encoding="utf-8", errors="replace").splitlines():
        if l[:6].strip() not in ("ATOM", "HETATM") or len(l) < 54:
            continue
        nombre = l[12:16].strip()
        rn = l[17:20].strip()
        if nombre.startswith("H") or (len(nombre) > 1 and nombre[0].isdigit()
                                      and nombre[1] == "H"):
            n_h += 1
        if rn not in TITULABLES:
            continue
        clave = (l[21:22], l[22:26].strip(), rn)
        if clave in vistos:
            continue
        vistos.add(clave)
        residuos_todos[rn] += 1
        if centro is not None:
            try:
                d2 = sum((float(l[30 + 8 * k:38 + 8 * k]) - centro[k]) ** 2 for k in range(3))
            except ValueError:
                continue
            if d2 <= RADIO_SITIO ** 2:
                residuos_sitio[rn] += 1
    out["receptor_tiene_hidrogenos"] = bool(n_h > 0)
    out["n_hidrogenos_receptor"] = n_h
    out["titulables_en_sitio"] = dict(residuos_sitio)
    out["n_titulables_sitio"] = sum(residuos_sitio.values())
    out["his_en_sitio"] = residuos_sitio.get("HIS", 0)
    out["n_titulables_total"] = sum(residuos_todos.values())

    mol = Chem.MolFromMolFile(str(sdf))
    if mol is None:
        mol = Chem.MolFromMolFile(str(sdf), sanitize=False, removeHs=False)
    if mol is None:
        out["error_ligando"] = "SDF_ILEGIBLE"
        return out
    out["carga_formal_sdf"] = int(Chem.GetFormalCharge(mol))
    out["n_atomos_cargados"] = sum(1 for a in mol.GetAtoms() if a.GetFormalCharge() != 0)
    grupos = {}
    for nombre, sma in IONIZABLES.items():
        patron = Chem.MolFromSmarts(sma)
        if patron is None:
            continue
        k = len(mol.GetSubstructMatches(patron))
        if k:
            grupos[nombre] = k
    out["grupos_ionizables"] = grupos
    # discrepancia: hay grupos que a pH 7.4 estarian ionizados pero el SDF trae carga 0
    neutro_pero_ionizable = (out["carga_formal_sdf"] == 0 and
                             any(g in grupos for g in ("acido_carboxilico", "amina_primaria",
                                                       "amina_secundaria", "amidina_guanidina",
                                                       "tetrazol", "fosfato_sulfato")))
    out["ligando_neutro_pese_a_ionizable"] = bool(neutro_pero_ionizable)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="REC-04a: auditoria de protonacion")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    args = ap.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pids = sorted(p.name for p in MAT.iterdir() if p.is_dir())
    print(f"[REC-04a] {len(pids)} complejos de train, {args.workers} procesos", flush=True)

    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for i, r in enumerate(ex.map(_analizar, pids), 1):
            filas.append(r)
            if i % 25 == 0:
                print(f"  [{i}/{len(pids)}] ({round(time.time()-t0)}s)", flush=True)
    with open(OUT_DIR / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for x in filas:
            fh.write(json.dumps(x, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    con_h = sum(1 for r in ok if r["receptor_tiene_hidrogenos"])
    his = [r for r in ok if r.get("his_en_sitio", 0) > 0]
    neutro_ion = [r for r in ok if r.get("ligando_neutro_pese_a_ionizable")]
    cargas = Counter(r.get("carga_formal_sdf") for r in ok if "carga_formal_sdf" in r)
    grupos_tot = Counter()
    for r in ok:
        for g, k in (r.get("grupos_ionizables") or {}).items():
            grupos_tot[g] += 1
    metrics = {
        "experiment_id": "REC-04a",
        "tipo": "auditoria (sin docking); parte sin computo de REC-04, insumo de FEP-01/FEP-02",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "hallazgo_de_partida": ("el provenance del pipeline declara receptor.protonation = "
                                "'pdb_original': NO se toma ninguna decision de protonacion, "
                                "se hereda la del fichero de PDBBind"),
        "n_complejos": len(filas), "n_ok": len(ok),
        "receptor": {
            "con_hidrogenos": con_h,
            "sin_hidrogenos": len(ok) - con_h,
            "titulables_en_sitio_mediana": int(median(r["n_titulables_sitio"] for r in ok)),
            "complejos_con_HIS_en_sitio": len(his),
            "his_en_sitio_mediana_cuando_hay": (int(median(r["his_en_sitio"] for r in his))
                                                if his else 0),
        },
        "ligando": {
            "distribucion_carga_formal": {str(k): v for k, v in sorted(cargas.items())},
            "complejos_con_grupo_ionizable": len([r for r in ok if r.get("grupos_ionizables")]),
            "grupos_mas_frecuentes": dict(grupos_tot.most_common(6)),
            "neutros_pese_a_ionizable": len(neutro_ion),
        },
        "limitacion": ("SMARTS de ionizables es una heuristica gruesa, no un predictor de pKa; "
                       "marca candidatos a revision, no errores confirmados. Y no se mide el "
                       "EFECTO sobre el ranking: eso es REC-04 completo y exige re-dockear"),
    }
    (OUT_DIR / "metrics_auditoria.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("\n" + json.dumps({"receptor": metrics["receptor"], "ligando": metrics["ligando"]},
                            ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
