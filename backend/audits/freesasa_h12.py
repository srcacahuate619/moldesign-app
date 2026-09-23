#!/usr/bin/env python3
r"""freesasa_h12.py — MM-GBSA, H12a: FreeSASA reproduce la SASA exacta por átomo, también en Br e I.

**Tipo: medición de un método geométrico contra la referencia exacta.** Primera
mitad de H12 (`docs/validacion_mmgbsa.md`): antes de proponer FreeSASA como
término no polar del MM-GBSA de reemplazo en lugar de LCPO, se mide si
reproduce la SASA numéricamente exacta de cada átomo —la misma referencia
contra la que LCPO falló para Br e I en H1 y H2— con la RDKit 2025.09.6 que
viaja en el producto.

Mismas geometrías que H1 (las 121 topologías de `lcpo_bri_h1.py`), mismos
radios para los dos métodos: Bondi para los átomos pesados, H excluido
(convención de LCPO), sonda 1,4 Å. Referencia: `sasa_numerica` (Shrake-Rupley,
50 000 puntos por átomo, sin modificar) de `lcpo_vs_sasa_exacta.py`.

Gate (fijado antes de medir): por átomo pesado, p95 de |FreeSASA − exacta|
≤ 0,5 Å² y máximo ≤ 1,0 Å², en todos los elementos y por separado en Br e I;
y mediana del tiempo de FreeSASA por ligando ≤ 50 ms. El fondo de LCPO era
mediana 2,81 Å² y p90 7,25 Å².

    python backend/audits/freesasa_h12.py medir --trabajo <dir con las topologías de H1> --salida <crudo.json>
    python backend/audits/freesasa_h12.py resumir --crudo <crudo.json> --artefactos <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from lcpo_vs_sasa_exacta import RADIO_SONDA, sasa_numerica  # noqa: E402 - sin modificar

BONDI = {6: 1.70, 7: 1.55, 8: 1.52, 9: 1.47, 15: 1.80, 16: 1.80, 17: 1.75, 35: 1.85, 53: 1.98}
SIMBOLO = {6: "C", 7: "N", 8: "O", 9: "F", 15: "P", 16: "S", 17: "Cl", 35: "Br", 53: "I"}
PUNTOS = 50_000
TOPE_P95, TOPE_MAX, TOPE_MS = 0.5, 1.0, 50.0


def _uno(pid: str, trabajo: str) -> dict[str, Any]:
    from openmm import app, unit
    from rdkit import Chem
    from rdkit.Chem import rdFreeSASA
    from rdkit.Geometry import Point3D
    try:
        carpeta = Path(trabajo) / pid
        top = app.AmberPrmtopFile(str(carpeta / "ligand.prmtop"))
        xyz = np.array(app.AmberInpcrdFile(str(carpeta / "ligand.inpcrd")).positions.value_in_unit(unit.angstrom))
        numeros = [a.element.atomic_number for a in top.topology.atoms()]
        radios = [0.0 if z == 1 else BONDI[z] for z in numeros]
        rw = Chem.RWMol()
        for z in numeros:
            rw.AddAtom(Chem.Atom(z))
        conf = Chem.Conformer(len(numeros))
        for k, p in enumerate(xyz):
            conf.SetAtomPosition(k, Point3D(*map(float, p)))
        mol = rw.GetMol()
        mol.AddConformer(conf, assignId=True)
        opciones = rdFreeSASA.SASAOpts(rdFreeSASA.SASAAlgorithm.LeeRichards, rdFreeSASA.SASAClassifier.Protor)
        tiempos = []
        for _ in range(5):
            t0 = time.perf_counter()
            rdFreeSASA.CalcSASA(mol, radios, confIdx=-1, opts=opciones)
            tiempos.append((time.perf_counter() - t0) * 1000)
        freesasa = np.array([float(a.GetProp("SASA")) for a in mol.GetAtoms()])
        exacta = sasa_numerica(xyz, np.array([r + RADIO_SONDA if r else 0.0 for r in radios]), PUNTOS, 0.0)
        return {"pid": pid, "estado": "ok", "ms_mediana": float(np.median(tiempos)),
                "atomos": [{"z": z, "freesasa_A2": round(float(freesasa[i]), 4), "exacta_A2": round(float(exacta[i]), 4)}
                           for i, z in enumerate(numeros) if z != 1]}
    except Exception as exc:  # noqa: BLE001 - un fallo es un resultado: se registra, no se oculta
        return {"pid": pid, "estado": "fallo", "motivo": f"{type(exc).__name__}: {exc}"[:400]}


def medir(args) -> int:
    import rdkit
    salida = Path(args.salida)
    if salida.exists():
        raise SystemExit(f"{salida} ya existe")
    pids = sorted(p.name for p in Path(args.trabajo).iterdir() if (p / "ligand.prmtop").is_file())
    resultados = []
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        for f in as_completed([ex.submit(_uno, p, str(args.trabajo)) for p in pids]):
            resultados.append(f.result())
    resultados.sort(key=lambda r: r["pid"])
    salida.write_text(json.dumps({"experimento": "MMGBSA-H12A-FREESASA", "rdkit": rdkit.__version__,
                                  "ejecutable": sys.executable, "puntos_referencia": PUNTOS,
                                  "ligandos": resultados}, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{sum(r['estado'] == 'ok' for r in resultados)}/{len(resultados)} medidos; escrito {salida}")
    return 0


def resumir(args) -> int:
    crudo_ruta = Path(args.crudo)
    crudo = json.loads(crudo_ruta.read_text(encoding="utf-8"))
    ok = [r for r in crudo["ligandos"] if r["estado"] == "ok"]
    difs: dict[str, list[float]] = {}
    for r in ok:
        for a in r["atomos"]:
            difs.setdefault(SIMBOLO[a["z"]], []).append(abs(a["freesasa_A2"] - a["exacta_A2"]))
    todas = [d for v in difs.values() for d in v]

    def est(v):
        v = np.array(v)
        return {"n": int(v.size), "mediana_A2": float(np.median(v)), "p95_A2": float(np.percentile(v, 95)),
                "max_A2": float(v.max())}

    tabla = {"todos": est(todas), **{e: est(v) for e, v in sorted(difs.items())}}
    ms = float(np.median([r["ms_mediana"] for r in ok]))
    pasa = {k: tabla[k]["p95_A2"] <= TOPE_P95 and tabla[k]["max_A2"] <= TOPE_MAX for k in ("todos", "Br", "I")}
    metricas = {"experimento": "MMGBSA-H12A-FREESASA", "rdkit": crudo["rdkit"],
                "crudo": {"archivo": crudo_ruta.name, "sha256": hashlib.sha256(crudo_ruta.read_bytes()).hexdigest()},
                "n_ligandos": len(ok), "fallos": [r for r in crudo["ligandos"] if r["estado"] != "ok"],
                "tabla_abs_freesasa_menos_exacta": tabla, "ms_mediana_por_ligando": ms,
                "topes": {"p95_A2": TOPE_P95, "max_A2": TOPE_MAX, "ms": TOPE_MS},
                "pasa": pasa, "pasa_gate": all(pasa.values()) and ms <= TOPE_MS and not
                [r for r in crudo["ligandos"] if r["estado"] != "ok"]}
    destino = Path(args.artefactos)
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                          encoding="utf-8", newline="\n")
    with open(destino / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in crudo["ligandos"]:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    for k, v in tabla.items():
        print(f"  {k:6s} n {v['n']:5d}  mediana {v['mediana_A2']:.4f}  p95 {v['p95_A2']:.4f}  máx {v['max_A2']:.4f}")
    print(f"ms por ligando (mediana) {ms:.2f}; gate {'PASA' if metricas['pasa_gate'] else 'NO PASA'}")
    return 0


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="etapa", required=True)
    m = sub.add_parser("medir")
    m.add_argument("--trabajo", type=Path, required=True)
    m.add_argument("--salida", type=Path, required=True)
    m.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    m.set_defaults(func=medir)
    r = sub.add_parser("resumir")
    r.add_argument("--crudo", type=Path, required=True)
    r.add_argument("--artefactos", type=Path, required=True)
    r.set_defaults(func=resumir)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
