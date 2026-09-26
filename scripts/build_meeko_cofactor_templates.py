#!/usr/bin/env python3
r"""Plantillas Meeko locales para los cofactores que Meeko no trae (DOCK-003).

# Por qué

Meeko 0.7.1 trae plantillas para aminoácidos, variantes y fosfo-residuos
(SEP, TPO, PTR), pero no para el hemo, las flavinas ni los nucleótidos. Ante
un residuo desconocido, `mk_prepare_receptor` descarga su definición del CCD
del RCSB en cada preparación: la aplicación funciona sin red, así que la fase 1
bloqueó esos receptores. Aquí las definiciones se descargan UNA vez, se
versionan con su SHA-256 y las plantillas se reconstruyen sin red con el mismo
camino que usa Meeko (`chemtempgen`: from_cif → make_canonical →
make_pretty_smiles → ResidueTemplate_check).

# Parches declarados

El CCD deja sin definir la carga formal del hierro (`?`) en HEM y HEC, y
`chemtempgen` no puede construir la molécula. Se fija a 0 y, en el hemo, los
oxígenos de los propionatos pasan de −1 a 0 para que la neutralización del
metal no deje una valencia imposible (lo mismo que hizo la investigación de la
fase 1); `make_canonical` los desprotona después. Vina tipifica el Fe como
metal y no usa cargas parciales: la plantilla sirve para acoplar con Vina, no
valida el estado redox ni sirve para un cálculo que use esas cargas.

# Uso

    python scripts/build_meeko_cofactor_templates.py --descargar   # red: CCD del RCSB
    python scripts/build_meeko_cofactor_templates.py --write
    python scripts/build_meeko_cofactor_templates.py --check
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
import tempfile
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DESTINO = RAIZ / "backend" / "data" / "meeko_templates"
CCD = DESTINO / "ccd"
PLANTILLAS = DESTINO / "cofactores.json"
MANIFIESTO = DESTINO / "manifest.json"

#: Cofactores orgánicos que el preparador conserva (`_STANDARD_RESIDUES`) y que
#: Meeko no trae. Los metales sueltos van por `cofactors_whitelist`.
COFACTORES = ("ADP", "ATP", "FAD", "FMN", "HEC", "HEM", "NAD", "NAP", "SAM", "SF4")

#: (patrón de línea del CIF, sustitución, motivo). Se aplican antes de construir.
PARCHES: dict[str, list[tuple[str, str, str]]] = {
    "HEM": [
        (r"^(_chem_comp\.pdbx_formal_charge\s+)\?", r"\g<1>0", "carga global sin definir"),
        (r"^(HEM\s+FE\s+FE\s+FE\s+)\?", r"\g<1>0", "carga del Fe sin definir en el CCD"),
        (r"^(HEM\s+O2A\s+O2A\s+O\s+)-1", r"\g<1>0", "propionato: make_canonical lo desprotona"),
        (r"^(HEM\s+O2D\s+O2D\s+O\s+)-1", r"\g<1>0", "propionato: make_canonical lo desprotona"),
    ],
    "HEC": [
        (r"^(_chem_comp\.pdbx_formal_charge\s+)\?", r"\g<1>0", "carga global sin definir"),
        (r"^(HEC\s+FE\s+FE\s+FE\s+)\?", r"\g<1>0", "carga del Fe sin definir en el CCD"),
        (r"^(HEC\s+O2A\s+O2A\s+O\s+)-1", r"\g<1>0", "propionato: make_canonical lo desprotona"),
        (r"^(HEC\s+O2D\s+O2D\s+O\s+)-1", r"\g<1>0", "propionato: make_canonical lo desprotona"),
    ],
    "SF4": [
        (r"^(_chem_comp\.pdbx_formal_charge\s+)\?", r"\g<1>0", "carga global sin definir"),
        (r"^(SF4\s+FE\d\s+FE\d\s+FE\s+)\?", r"\g<1>0", "carga de los cuatro Fe sin definir en el CCD"),
    ],
}


def _sha256(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def descargar() -> None:
    CCD.mkdir(parents=True, exist_ok=True)
    for res in COFACTORES:
        url = f"https://files.rcsb.org/ligands/download/{res}.cif"
        with urllib.request.urlopen(url, timeout=60) as r:
            (CCD / f"{res}.cif").write_bytes(r.read())
        print(f"  {res}: {url}")


def _construir(res: str):
    from meeko import chemtempgen as ctg
    from rdkit.Chem import rdmolops

    texto = (CCD / f"{res}.cif").read_text(encoding="utf-8")
    for patron, sustitucion, _ in PARCHES.get(res, []):
        texto, n = re.subn(patron, sustitucion, texto, flags=re.M)
        if n == 0:
            raise RuntimeError(f"{res}: el parche {patron!r} no encontró su línea en el CIF")
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / f"{res}.cif"
        ruta.write_text(texto, encoding="utf-8")
        with ctg.ChemicalComponent_LoggingControler():
            cc = ctg.ChemicalComponent.from_cif(str(ruta), res)
    if cc is None:
        raise RuntimeError(f"{res}: chemtempgen no pudo leer el CIF")
    cc = copy.deepcopy(cc).make_canonical(acidic_proton_loc=ctg.acidic_proton_loc_canonical)
    if len(rdmolops.GetMolFrags(cc.rdkit_mol)) > 1:
        raise RuntimeError(f"{res}: la molécula se fragmenta al canonicalizar")
    cc = cc.make_pretty_smiles()
    cc.ResidueTemplate_check()
    return cc


def construir() -> tuple[str, dict]:
    import importlib.metadata

    from meeko import chemtempgen as ctg

    componentes = [_construir(res) for res in COFACTORES]
    with tempfile.TemporaryDirectory() as tmp:
        salida = Path(tmp) / "t.json"
        ctg.export_chem_templates_to_json(componentes, str(salida))
        texto = json.dumps(json.loads(salida.read_text(encoding="utf-8")), indent=1, sort_keys=True) + "\n"
    manifiesto = {
        "_doc": "Generado por scripts/build_meeko_cofactor_templates.py; no editar a mano.",
        "meeko": importlib.metadata.version("meeko"),
        "rdkit": importlib.metadata.version("rdkit"),
        "ccd": {res: {"url": f"https://files.rcsb.org/ligands/download/{res}.cif",
                      "sha256": _sha256(CCD / f"{res}.cif")} for res in COFACTORES},
        "parches": {res: [motivo for _, _, motivo in p] for res, p in PARCHES.items()},
        "plantillas_sha256": hashlib.sha256(texto.encode("utf-8")).hexdigest(),
        "uso": "Sólo para acoplar con Vina: Vina tipifica los átomos y no usa cargas parciales.",
    }
    return texto, manifiesto


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--descargar", action="store_true")
    modo.add_argument("--write", action="store_true")
    modo.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    if args.descargar:
        descargar()
        return 0
    texto, manifiesto = construir()
    manifiesto_txt = json.dumps(manifiesto, indent=1, ensure_ascii=False) + "\n"
    if args.write:
        PLANTILLAS.write_text(texto, encoding="utf-8", newline="\n")
        MANIFIESTO.write_text(manifiesto_txt, encoding="utf-8", newline="\n")
        print(f"Generado: {len(COFACTORES)} plantillas, sha256 {manifiesto['plantillas_sha256'][:16]}…")
        return 0
    actual = (PLANTILLAS.read_text(encoding="utf-8") if PLANTILLAS.is_file() else "",
              MANIFIESTO.read_text(encoding="utf-8") if MANIFIESTO.is_file() else "")
    if actual != (texto, manifiesto_txt):
        print("Plantillas de cofactores desactualizadas: ejecuta --write y revisa el diff.")
        return 1
    print(f"Plantillas de cofactores al día ({len(COFACTORES)}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
