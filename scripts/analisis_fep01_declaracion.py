#!/usr/bin/env python3
r"""analisis_fep01_declaracion.py — FEP-01-DECL: ¿declarar tautómeros sube FEP-01 al 80 %?

**Tipo: medición contra una predicción escrita.** `docs/50_ROADMAP.md` §3 y
`AGENTS.md` afirman que declarar tautómeros «sube FEP-01 de 19 % a más del 80 %
de un golpe». Este script lo pone a prueba con la declaración que ya produce el
conformador (`backend/chem/declaracion_tautomeros.py`, tres estados).

Qué cambia respecto de FEP-01
-----------------------------
FEP-01 exigía **un solo tautómero enumerable**. Aquí el criterio pasa a ser
**tautómero declarado**: `RESUELTO_UNICO` o `MULTIESTADO_REQUERIDO` (varios
candidatos, enumeración completa, ninguno descartado y todos en el paquete).
`NO_RESUELTO` —enumeración fallida o cortada en el tope de 32— sigue sin estar
listo. Estereoquímica y atom mapping se toman **tal cual** de los `per_complex`
sellados de `FEP-01` y `FEP-01-PDBBIND`: no se vuelven a medir.

Declarado no es resuelto. Por eso se informa aparte cuántos de los listos lo son
sólo porque su multiestado quedó declarado: un paquete con varios tautómeros
exige a quien calcula tratarlos todos, o elegir uno con evidencia.

    python scripts/analisis_fep01_declaracion.py --salida <dir> [--workers N]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))

PDBBIND = RAIZ / "data" / "pdbbind"
SELLOS = {"molflex_203": RAIZ / "scripts" / "artifacts_science" / "FEP-01" / "per_complex.jsonl",
          "pdbbind": RAIZ / "scripts" / "artifacts_science" / "FEP-01-PDBBIND" / "per_complex.jsonl"}
MODULO = RAIZ / "backend" / "chem" / "declaracion_tautomeros.py"
UMBRAL_GO = 0.80


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _declarar(pid: str) -> dict[str, Any]:
    from rdkit import Chem, RDLogger

    from chem.declaracion_tautomeros import declarar_tautomeros
    RDLogger.DisableLog("rdApp.*")
    sdf = PDBBIND / pid / f"{pid}_ligand.sdf"
    if not sdf.exists():
        return {"pid": pid, "error": "SIN_SDF"}
    mol = Chem.MolFromMolFile(str(sdf))  # la misma lectura que FEP-01
    if mol is None:
        return {"pid": pid, "error": "SDF_ILEGIBLE"}
    d = declarar_tautomeros(Chem.MolToSmiles(mol))
    return {"pid": pid, "estado": d["estado"], "n_candidatos": d["n_candidatos"],
            "enumeracion_completa": d["enumeracion_completa"], "motivo": d["motivo"],
            "n_atomos_tautomericos": len(d["atomos_tautomericos"])}


def _resumen(filas_sello: list[dict], decl: dict[str, dict]) -> dict[str, Any]:
    validas = [f for f in filas_sello if "error" not in f and f["pid"] in decl and "error" not in decl[f["pid"]]]
    estados = Counter(decl[f["pid"]]["estado"] for f in validas)

    def listo(f, criterio_tautomero, con_mapping=True):
        mapping = bool(f.get("mapping_biyectivo") and f.get("mapping_cubre_pesados")) if con_mapping else True
        return bool(not f["estereo_indefinido"] and mapping and criterio_tautomero(f))

    def declarado(f):
        return decl[f["pid"]]["estado"] != "NO_RESUELTO"

    def unico(f):
        return decl[f["pid"]]["estado"] == "RESUELTO_UNICO"

    n = len(validas)
    out = {"n": n, "estados": dict(estados)}
    for etiqueta, con_mapping in (("con_mapping", True), ("sin_mapping", False)):
        l_decl = [f for f in validas if listo(f, declarado, con_mapping)]
        l_unico = [f for f in validas if listo(f, unico, con_mapping)]
        l_sello = [f for f in validas if listo(f, lambda f: not f["tautomero_ambiguo"], con_mapping)]
        out[etiqueta] = {
            "listos_criterio_declarado": len(l_decl), "fraccion_declarado": len(l_decl) / n if n else None,
            "listos_solo_resuelto_unico": len(l_unico), "fraccion_unico": len(l_unico) / n if n else None,
            "listos_criterio_del_sello": len(l_sello),
            "listos_solo_por_multiestado_declarado": len(l_decl) - len(l_unico),
            "bloquea_la_estereoquimica": sum(1 for f in validas if f["estereo_indefinido"]),
            "bloquea_el_tautomero_no_resuelto": sum(1 for f in validas if not declarado(f)),
        }
    return out


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--limite", type=int, help="prueba técnica: sólo los N primeros de cada universo")
    args = ap.parse_args()
    import rdkit

    t0 = time.time()
    sellos = {u: [json.loads(linea) for linea in ruta.open(encoding="utf-8")] for u, ruta in SELLOS.items()}
    if args.limite:
        sellos = {u: filas[:args.limite] for u, filas in sellos.items()}
    pids = sorted({f["pid"] for filas in sellos.values() for f in filas if "error" not in f})
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        decl = {r["pid"]: r for r in ex.map(_declarar, pids, chunksize=16)}

    resultados = {u: _resumen(filas, decl) for u, filas in sellos.items()}
    fraccion = resultados["molflex_203"]["con_mapping"]["fraccion_declarado"]
    decision = None if args.limite else ("GO" if fraccion is not None and fraccion >= UMBRAL_GO else "NO_GO")
    metricas = {
        "experimento": "FEP-01-DECL", "generado_utc": datetime.now(UTC).isoformat(),
        "duracion_s": round(time.time() - t0, 1), "rdkit": rdkit.__version__,
        "modulo_declaracion_sha256": _sha(MODULO),
        "sellos_de_entrada": {u: {"ruta": str(r.relative_to(RAIZ)), "sha256": _sha(r)} for u, r in SELLOS.items()},
        "prediccion_puesta_a_prueba": "docs/50_ROADMAP.md §3: declarar tautómeros sube FEP-01 de 19% a >80%",
        "umbral_go": UMBRAL_GO, "resultados": resultados,
        "decision_por_el_gate": decision or "NO_LEER_PRUEBA_TECNICA",
        "no_demuestra": ("Que el tautómero acoplado sea el correcto. «Declarado» incluye MULTIESTADO_REQUERIDO: "
                         "varios candidatos sin descartar, que quien calcule tiene que tratar."),
    }
    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                              encoding="utf-8", newline="\n")
    with open(args.salida / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for pid in pids:
            fh.write(json.dumps(decl[pid], ensure_ascii=False) + "\n")
    with open(args.salida / "failures.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for pid in pids:
            if "error" in decl[pid]:
                fh.write(json.dumps(decl[pid], ensure_ascii=False) + "\n")
    for u, r in resultados.items():
        c = r["con_mapping"]
        print(f"{u}: n {r['n']}  estados {r['estados']}")
        print(f"   listos (declarado) {c['listos_criterio_declarado']} = {100 * (c['fraccion_declarado'] or 0):.1f}%"
              f"   (sólo único {c['listos_solo_resuelto_unico']}; sello {c['listos_criterio_del_sello']};"
              f" por multiestado {c['listos_solo_por_multiestado_declarado']})")
    print(f"decisión por el gate: {metricas['decision_por_el_gate']}  ({metricas['duracion_s']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
