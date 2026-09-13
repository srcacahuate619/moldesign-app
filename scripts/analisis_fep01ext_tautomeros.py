#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""analisis_fep01ext_tautomeros.py — FEP-01-EXT: ¿dónde están los protones, realmente?

`FEP-01` midió que **164 de 203 ligandos (81%) tienen más de un tautómero enumerable y el
pipeline no declara cuál usa**. Ese es el cuello que impide ser FEP+ ready: el tautómero
decide qué átomos donan y cuáles aceptan puentes de hidrógeno, que es la interacción que
domina el reconocimiento molecular.

Pero `FEP-01` contó **ambigüedad**, no **consecuencia**. Este experimento mide la
consecuencia.

Qué se compara
--------------
Para cada ligando: el tautómero **tal como está en el fichero** —el que el pipeline lee y
dockea— contra el tautómero **canónico** que elige un canonicalizador estándar.

La comparación NO se hace por conteo de donadores y aceptores. Un sondeo previo mostró
casos con tautómero distinto y **los mismos** HBD/HBA totales: el protón se mueve de un
átomo a otro sin cambiar la suma. Contar totales oculta exactamente lo que importa.

Se compara **átomo por átomo**: cuántos hidrógenos lleva cada átomo pesado antes y
después. Eso localiza el protón, que es la cantidad física relevante.

Lo que este experimento NO afirma
---------------------------------
**El tautómero canónico no es «el correcto».** Es la salida de una heurística de
puntuación, no una predicción de la población dominante en solución a pH fisiológico.
`FEP-01` ya declaró esa misma limitación para la enumeración.

Por tanto lo que se mide es **DESACUERDO** entre lo que hay en el fichero y lo que elegiría
un canonicalizador estándar. Desacuerdo no es error: es la señal de que ahí hay una
decisión que nadie tomó explícitamente, y que para FEP+ hay que tomar y declarar.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))


def perfil_h(m) -> Dict[int, int]:
    """Hidrogenos totales por atomo pesado, indexado por posicion. Es donde esta el proton."""
    return {a.GetIdx(): a.GetTotalNumHs()
            for a in m.GetAtoms() if a.GetAtomicNum() > 1}


def main() -> int:
    ap = argparse.ArgumentParser(description="FEP-01-EXT: consecuencia de la ambiguedad tautomerica")
    ap.add_argument("--workspace", default=str(PROJECT_ROOT))
    args = ap.parse_args()
    ws = Path(args.workspace)
    out = ws / "scripts" / "artifacts_science" / "FEP-01-EXT"
    out.mkdir(parents=True, exist_ok=True)

    from rdkit import Chem, RDLogger
    RDLogger.DisableLog("rdApp.*")
    from rdkit.Chem.MolStandardize import rdMolStandardize
    import molflex as mf

    fep01 = {}
    for l in (ws / "scripts" / "artifacts_science" / "FEP-01" /
              "per_complex.jsonl").read_text(encoding="utf-8").splitlines():
        if l.strip():
            r = json.loads(l)
            fep01[r["pid"]] = r

    te = rdMolStandardize.TautomerEnumerator()
    t0 = time.time()
    filas: List[Dict[str, Any]] = []
    for pid, base in sorted(fep01.items()):
        r: Dict[str, Any] = {"pid": pid, "split": base.get("split"),
                             "n_tautomeros": base.get("n_tautomeros"),
                             "tautomero_ambiguo": base.get("tautomero_ambiguo")}
        m = mf.leer_ligando(ws / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf")
        if m is None:
            r["error"] = "SDF_ILEGIBLE"
            filas.append(r)
            continue
        try:
            actual = Chem.RemoveAllHs(Chem.Mol(m))
            canon = te.Canonicalize(actual)
        except Exception as e:
            r["error"] = f"CANONICALIZACION_FALLO: {type(e).__name__}"
            filas.append(r)
            continue

        s_act, s_can = Chem.MolToSmiles(actual), Chem.MolToSmiles(canon)
        r["smiles_distinto"] = (s_act != s_can)

        pa, pc = perfil_h(actual), perfil_h(canon)
        if set(pa) != set(pc):
            # el canonicalizador no preserva la indexacion: no se puede comparar por atomo
            r["error"] = "INDEXACION_NO_PRESERVADA"
            filas.append(r)
            continue
        movidos = [i for i in pa if pa[i] != pc[i]]
        r["n_atomos_con_h_distinto"] = len(movidos)
        r["patron_h_cambia"] = len(movidos) > 0
        r["atomos_movidos"] = [{"idx": i, "sim": pa[i], "elem": actual.GetAtomWithIdx(i).GetSymbol(),
                                "canon": pc[i]} for i in movidos[:10]]
        r["n_pesados"] = actual.GetNumAtoms()
        filas.append(r)

    with open(out / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in filas:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    ok = [r for r in filas if "error" not in r]
    amb = [r for r in ok if r.get("tautomero_ambiguo")]
    cambia = [r for r in ok if r.get("patron_h_cambia")]
    smiles_dist = [r for r in ok if r.get("smiles_distinto")]
    # el caso silencioso: SMILES distinto pero mismo numero total de H movidos = 0
    silencioso = [r for r in ok if r.get("smiles_distinto") and not r.get("patron_h_cambia")]

    metrics = {
        "experiment_id": "FEP-01-EXT",
        "tipo": "medicion de consecuencia, sin gates de decision",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "n_complejos": len(filas),
        "n_ok": len(ok),
        "n_error": len(filas) - len(ok),
        "errores": {r["pid"]: r["error"] for r in filas if "error" in r},
        "G1_validez": {"criterio": ">=95% procesables",
                       "tasa": round(len(ok) / len(filas), 4) if filas else None,
                       "pass": (len(ok) / len(filas) >= 0.95) if filas else False},
        "G2_desacuerdo_de_smiles": {
            "n": len(smiles_dist), "de": len(ok),
            "fraccion": round(len(smiles_dist) / len(ok), 4) if ok else None},
        "G3_el_proton_se_mueve": {
            "definicion": "algun atomo pesado cambia su numero de hidrogenos",
            "n": len(cambia), "de": len(ok),
            "fraccion": round(len(cambia) / len(ok), 4) if ok else None,
            "atomos_movidos_mediana": (round(median(r["n_atomos_con_h_distinto"]
                                                    for r in cambia), 1) if cambia else 0)},
        "desacuerdo_sin_mover_protones": {
            "definicion": "SMILES distinto pero ningun atomo cambia su numero de H; "
                          "el canonicalizador reordena o kekuliza sin mover el proton",
            "n": len(silencioso)},
        "cruce_con_FEP_01": {
            "ambiguos_segun_FEP_01": len(amb),
            "de_esos_el_proton_se_mueve": sum(1 for r in amb if r.get("patron_h_cambia")),
            "no_ambiguos_donde_el_proton_SI_se_mueve":
                sum(1 for r in ok if not r.get("tautomero_ambiguo") and r.get("patron_h_cambia"))},
        "limitacion_declarada": (
            "El tautomero canonico NO es 'el correcto': es una heuristica de puntuacion, no "
            "una prediccion de la poblacion dominante a pH fisiologico. Se mide DESACUERDO "
            "entre el fichero y un canonicalizador estandar, no error."),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=1),
                                      encoding="utf-8", newline="\n")

    g = metrics
    print(f"[FEP-01-EXT] {len(filas)} ligandos en {g['duration_seconds']}s")
    print(f"  validez                 : {g['G1_validez']['tasa']}  pass={g['G1_validez']['pass']}")
    print(f"  SMILES distinto         : {g['G2_desacuerdo_de_smiles']['n']}/{len(ok)} "
          f"({g['G2_desacuerdo_de_smiles']['fraccion']})")
    print(f"  EL PROTON SE MUEVE      : {g['G3_el_proton_se_mueve']['n']}/{len(ok)} "
          f"({g['G3_el_proton_se_mueve']['fraccion']}), mediana "
          f"{g['G3_el_proton_se_mueve']['atomos_movidos_mediana']} atomos")
    print(f"  desacuerdo sin mover H  : {g['desacuerdo_sin_mover_protones']['n']}")
    c = g["cruce_con_FEP_01"]
    print(f"  ambiguos segun FEP-01   : {c['ambiguos_segun_FEP_01']}, de esos el proton se "
          f"mueve en {c['de_esos_el_proton_se_mueve']}")
    print(f"  NO ambiguos y aun asi el proton se mueve: "
          f"{c['no_ambiguos_donde_el_proton_SI_se_mueve']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
