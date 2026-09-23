#!/usr/bin/env python3
r"""analisis_fep08_control_positivo.py — FEP-08: ¿distingue el auditor una preparación experta?

**Tipo: control positivo.** Un auditor de readiness que marcara igual una
estructura preparada por expertos para FEP relativo que una sin preparar no
estaría midiendo preparación. El protein-ligand-benchmark de OpenFF (datos CC BY
4.0, código MIT) está preparado precisamente para RBFE: proteína lista, ligandos
con protonación y tautómero elegidos por sus curadores y poses de partida.

Se le aplican **sin modificarlas** las funciones selladas de `FEP-01`
(`scripts/analisis_fep01_integridad.py::_analizar`) y `FEP-02`
(`scripts/analisis_fep02_receptor.py::_analizar`), por composición: se les
cambia el directorio de datos (`PDBBIND`, `MATS`) por una copia con el mismo
formato, como hace `analisis_fep_pdbbind.py`. La declaración de tautómeros es la
de `backend/chem/declaracion_tautomeros.py`.

Predicciones declaradas antes de medir
--------------------------------------
(a) **Preparación.** El receptor documentable de FEP-02 (sin huecos de numeración
    y sitio en una sola cadena) es más frecuente en OpenFF que en PDBBind (39,7 %,
    `FEP-02-PDBBIND`) por al menos 20 puntos.
(b) **Química.** La fracción de ligandos con un único tautómero enumerable NO se
    distingue de PDBBind (21,6 %, `FEP-01-DECL`) en más de 15 puntos: el número de
    tautómeros depende de la molécula, no de quién la preparó.

    python scripts/analisis_fep08_control_positivo.py --plb <repo> --salida <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "backend"))
sys.path.insert(0, str(RAIZ / "scripts"))
ART = RAIZ / "scripts" / "artifacts_science"
REF_RECEPTOR_PDBBIND = 1543 / 3887   # FEP-02-PDBBIND, documentables_para_fep / evaluados
REF_UNICO_PDBBIND = 1003 / 4641      # FEP-01-DECL, RESUELTO_UNICO / legibles
MARGEN_A, MARGEN_B = 0.20, 0.15


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def _cargar(nombre: str):
    ruta = RAIZ / "scripts" / f"{nombre}.py"
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod, ruta


def main() -> int:
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plb", type=Path, required=True, help="clon de openforcefield/protein-ligand-benchmark")
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--limite", type=int, help="prueba técnica: sólo N dianas; no se lee el gate")
    args = ap.parse_args()
    import rdkit
    from rdkit import Chem, RDLogger

    from chem.declaracion_tautomeros import declarar_tautomeros
    RDLogger.DisableLog("rdApp.*")
    t0 = time.time()
    fep01, ruta01 = _cargar("analisis_fep01_integridad")
    fep02, ruta02 = _cargar("analisis_fep02_receptor")
    commit_plb = subprocess.run(["git", "-C", str(args.plb), "rev-parse", "HEAD"],
                                capture_output=True, text=True).stdout.strip()

    dianas = sorted(p.name for p in (args.plb / "data").iterdir()
                    if (p / "01_protein" / "crd" / "protein.pdb").is_file() and (p / "02_ligands" / "ligands.sdf").is_file())
    if args.limite:
        dianas = dianas[:args.limite]

    receptores, ligandos = [], []
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        for t in dianas:
            mols = [m for m in Chem.SDMolSupplier(str(args.plb / "data" / t / "02_ligands" / "ligands.sdf"),
                                                  removeHs=False) if m is not None]
            # Receptor: la función sellada define el sitio con el primer ligando del SDF.
            carpeta = base / t
            carpeta.mkdir()
            shutil.copy(args.plb / "data" / t / "01_protein" / "crd" / "protein.pdb", carpeta / f"{t}_protein.pdb")
            Chem.MolToMolFile(mols[0], str(carpeta / f"{t}_ligand.sdf"))
            fep02.PDBBIND = base
            receptores.append({"diana": t, "n_ligandos": len(mols), **fep02._analizar({"pid": t, "split": "plb"})})
            # Ligandos: uno por carpeta, con el formato que espera FEP-01.
            for k, m in enumerate(mols):
                nombre = m.GetProp("_Name") if m.HasProp("_Name") else f"lig{k}"
                pid = f"{t}__{k:03d}"
                (base / pid).mkdir()
                Chem.MolToMolFile(m, str(base / pid / f"{pid}_ligand.sdf"))
                fep01.PDBBIND = base
                fep01.MATS = {"plb": base / "_sin_mapping"}
                fila = fep01._analizar({"pid": pid, "split": "plb"})
                if "error" not in fila:
                    lectura = Chem.MolFromMolFile(str(base / pid / f"{pid}_ligand.sdf"))
                    d = declarar_tautomeros(Chem.MolToSmiles(lectura))
                    fila.update({"estado_tautomero": d["estado"], "n_candidatos": d["n_candidatos"],
                                 "entrada_es_canonico": bool(d["candidatos"]) and any(
                                     c["es_entrada"] and c["es_canonico"] for c in d["candidatos"])})
                ligandos.append({"diana": t, "ligando": nombre, **fila})

    validos = [f for f in ligandos if "error" not in f]
    estados = Counter(f["estado_tautomero"] for f in validos)
    frac_unico = estados.get("RESUELTO_UNICO", 0) / len(validos) if validos else None
    rec_ok = [r for r in receptores if "error" not in r]
    frac_doc = sum(r["documentado_para_fep"] for r in rec_ok) / len(rec_ok) if rec_ok else None
    pred_a = frac_doc is not None and frac_doc >= REF_RECEPTOR_PDBBIND + MARGEN_A
    pred_b = frac_unico is not None and abs(frac_unico - REF_UNICO_PDBBIND) <= MARGEN_B
    decision = "NO_LEER_PRUEBA_TECNICA" if args.limite else ("GO" if pred_a and pred_b else "NO_GO")
    metricas = {
        "experimento": "FEP-08-CONTROL-POSITIVO", "generado_utc": datetime.now(UTC).isoformat(),
        "duracion_s": round(time.time() - t0, 1), "rdkit": rdkit.__version__,
        "fuente": {"repo": "openforcefield/protein-ligand-benchmark", "commit": commit_plb,
                   "licencia_datos": "CC BY 4.0 (LICENSE_DATA)", "licencia_codigo": "MIT"},
        "funciones_selladas_reutilizadas": {"FEP-01": {"ruta": str(ruta01.relative_to(RAIZ)), "sha256": _sha(ruta01)},
                                            "FEP-02": {"ruta": str(ruta02.relative_to(RAIZ)), "sha256": _sha(ruta02)}},
        "declaracion_sha256": _sha(RAIZ / "backend" / "chem" / "declaracion_tautomeros.py"),
        "receptores": {"n": len(rec_ok), "documentados_para_fep": sum(r["documentado_para_fep"] for r in rec_ok),
                       "fraccion": frac_doc, "con_huecos": sum(r["tiene_huecos"] for r in rec_ok),
                       "sitio_entre_cadenas": sum(r["sitio_entre_cadenas"] for r in rec_ok),
                       "referencia_pdbbind": REF_RECEPTOR_PDBBIND},
        "ligandos": {"n": len(validos), "fallos": len(ligandos) - len(validos), "estados_tautomero": dict(estados),
                     "fraccion_unico": frac_unico, "referencia_pdbbind": REF_UNICO_PDBBIND,
                     "estereo_indefinido": sum(f["estereo_indefinido"] for f in validos),
                     "entrada_igual_al_canonico_de_rdkit": sum(f.get("entrada_es_canonico", False) for f in validos),
                     "carga_formal_no_nula": sum(1 for f in validos if f["carga_formal"])},
        "predicciones": {"a_preparacion_receptor": {"umbral": REF_RECEPTOR_PDBBIND + MARGEN_A, "cumple": pred_a},
                         "b_quimica_tautomeros": {"intervalo": [REF_UNICO_PDBBIND - MARGEN_B, REF_UNICO_PDBBIND + MARGEN_B],
                                                  "cumple": pred_b}},
        "decision_por_el_gate": decision,
        "no_demuestra": ("Con 15 dianas, la fracción de receptores tiene una resolución de ~7 puntos. Tampoco "
                         "dice que las elecciones de los curadores sean correctas: sólo si el auditor las distingue."),
    }
    args.salida.mkdir(parents=True, exist_ok=True)
    (args.salida / "metrics.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=1) + "\n",
                                              encoding="utf-8", newline="\n")
    with open(args.salida / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for r in receptores:
            fh.write(json.dumps({"tipo": "receptor", **r}, ensure_ascii=False) + "\n")
        for f in ligandos:
            fh.write(json.dumps({"tipo": "ligando", **f}, ensure_ascii=False) + "\n")
    with open(args.salida / "failures.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for f in receptores + ligandos:
            if "error" in f:
                fh.write(json.dumps(f, ensure_ascii=False) + "\n")
    r, lg = metricas["receptores"], metricas["ligandos"]
    print(f"receptores: {r['documentados_para_fep']}/{r['n']} documentables ({100 * (r['fraccion'] or 0):.1f} %;"
          f" PDBBind {100 * REF_RECEPTOR_PDBBIND:.1f} %); con huecos {r['con_huecos']}, sitio entre cadenas {r['sitio_entre_cadenas']}")
    print(f"ligandos: {lg['n']} ({lg['fallos']} fallos); tautómeros {lg['estados_tautomero']};"
          f" único {100 * (lg['fraccion_unico'] or 0):.1f} % (PDBBind {100 * REF_UNICO_PDBBIND:.1f} %);"
          f" estéreo indefinido {lg['estereo_indefinido']}; entrada = canónico {lg['entrada_igual_al_canonico_de_rdkit']}")
    print(f"predicción a {pred_a}, b {pred_b}; decisión por el gate: {decision} ({metricas['duracion_s']} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
