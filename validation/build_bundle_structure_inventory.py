"""Inventario de estructuras DISTRIBUIDAS en el bundle, cruzado con la fuga.

Existe porque el piloto PILOT-0 contó mal: buscó `*.pdb` y no vio los 407
`*.pdb.gz`, y de ahi dedujo que solo tres estructuras viajaban. El conteo real
es 411 ficheros. La leccion no es aritmetica sino de metodo, y por eso este
script inventaria por extension explicita y publica los conteos fisicos.

Separa dos preguntas que el piloto habia fundido en una:

  DISTRIBUIDA   el fichero viaja en el bundle -> se puede abrir sin red.
                Es una propiedad del empaquetado.
  EXTERNAL      el complejo no aparece en ninguna fuente de exposicion.
                Es una propiedad de la procedencia cientifica.

Una estructura puede ser DISTRIBUIDA y a la vez SEEN: 1GKC lo es. Deducir
independencia cientifica de la presencia en disco fue exactamente el error.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCT_ROOT = Path(os.environ.get("MOLDESIGN_PRODUCT_ROOT", r"D:/moldesign-build")).resolve()

EXTENSIONES = (".pdb", ".pdb.gz", ".pdbqt", ".pdbqt.gz", ".cif", ".cif.gz", ".ent", ".ent.gz")

# Palabras que identifican a las dianas RELATED en el nombre curado. La lista es
# deliberadamente corta y explicita: un emparejamiento por subcadena suelta
# marcaria RELATED cualquier cosa.
PISTAS_RELATED = {
    "CA2": ("carbonic anhydrase",),
    "MMP9": ("matrix metalloproteinase-9", "matrix metalloproteinase 9", "mmp-9", "mmp9", "gelatinase b"),
    "ACE": ("angiotensin converting enzyme", "angiotensin-converting enzyme"),
    "5HT1A": ("5-ht1a", "5ht1a", "serotonin 1a", "htr1a"),
    "CDK2": ("cyclin-dependent kinase 2", "cyclin dependent kinase 2", "cdk2"),
    "ER_ALPHA": ("estrogen receptor",),
    "FACTOR_XA": ("factor xa", "coagulation factor x"),
    "HIV_PROTEASE": ("hiv-1 protease", "hiv protease", "hiv-1 proteinase"),
    "THROMBIN": ("thrombin", "alpha-thrombin"),
}

RE_PDB_ID = re.compile(r"^([0-9][a-z0-9]{3})", re.IGNORECASE)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _extension(nombre: str) -> str | None:
    bajo = nombre.lower()
    for ext in sorted(EXTENSIONES, key=len, reverse=True):
        if bajo.endswith(ext):
            return ext
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--product-root", type=Path, default=PRODUCT_ROOT)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "validation" / "leakage" / "bundle_structures.json")
    args = ap.parse_args()

    src = args.product_root.resolve()
    targets = src / "frontend" / "src-tauri" / "resources" / "data" / "targets"
    if not targets.is_dir():
        raise SystemExit(f"No existe {targets}")

    fuga_path = ROOT / "validation" / "leakage" / "seen_inventory.json"
    fuga = json.load(io.open(fuga_path, encoding="utf-8"))
    seen = {k.lower(): v for k, v in fuga["seen_pdb_ids"].items()}

    curados_path = src / "frontend" / "src-tauri" / "resources" / "curated_targets.json"
    nombres: dict[str, str] = {}
    if curados_path.is_file():
        for t in json.load(io.open(curados_path, encoding="utf-8")):
            pid = (t.get("pdb_id") or "").lower()
            if pid:
                nombres[pid] = t.get("name") or ""

    por_extension: dict[str, int] = {}
    ficheros: list[dict] = []
    ids: dict[str, list[str]] = {}

    for p in sorted(targets.rglob("*")):
        if not p.is_file():
            continue
        ext = _extension(p.name)
        if ext is None:
            por_extension["(otras)"] = por_extension.get("(otras)", 0) + 1
            continue
        por_extension[ext] = por_extension.get(ext, 0) + 1
        m = RE_PDB_ID.match(p.name)
        pid = m.group(1).lower() if m else None
        ficheros.append({"fichero": p.name, "ext": ext, "bytes": p.stat().st_size,
                         "pdb_id": pid})
        if pid:
            ids.setdefault(pid, []).append(p.name)

    def clasificar(pid: str) -> tuple[str, dict]:
        detalle: dict = {}
        if pid in seen:
            detalle["fuentes_seen"] = seen[pid]
            return "SEEN", detalle
        nombre = (nombres.get(pid) or "").lower()
        for diana, pistas in PISTAS_RELATED.items():
            if any(pista in nombre for pista in pistas):
                detalle["diana_related"] = diana
                detalle["nombre_curado"] = nombres.get(pid)
                return "RELATED", detalle
        return "EXTERNAL", detalle

    clasificacion: dict[str, dict] = {}
    resumen = {"SEEN": 0, "RELATED": 0, "EXTERNAL": 0}
    for pid in sorted(ids):
        nivel, detalle = clasificar(pid)
        resumen[nivel] += 1
        clasificacion[pid] = {"nivel": nivel, "ficheros": sorted(ids[pid]),
                              "nombre": nombres.get(pid), **detalle}

    confirmaciones = {}
    for pid in ("1gkc", "1o86", "3dc3", "3pp0", "7e2y"):
        confirmaciones[pid.upper()] = {
            "distribuida": pid in ids,
            "ficheros": sorted(ids.get(pid, [])),
            "nivel_de_fuga": clasificacion.get(pid, {}).get("nivel"),
        }

    salida = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "product_root": str(src).replace("\\", "/"),
        "directorio": str(targets.relative_to(src)).replace("\\", "/"),
        "conteos_fisicos": {
            "ficheros_totales": len(ficheros) + por_extension.get("(otras)", 0),
            "ficheros_de_estructura": len(ficheros),
            "por_extension": dict(sorted(por_extension.items())),
            "pdb_ids_distintos": len(ids),
        },
        "clasificacion_de_fuga_de_lo_distribuido": resumen,
        "confirmaciones_solicitadas": confirmaciones,
        "metodo": {
            "DISTRIBUIDA": "el fichero existe bajo data/targets; se puede abrir sin red.",
            "SEEN": "el PDB exacto aparece en seen_inventory.json.",
            "RELATED": "el nombre curado del PDB coincide con una de las 9 dianas "
                       "expuestas. Emparejamiento por subcadena sobre una lista corta "
                       "y explicita.",
            "EXTERNAL": "ni SEEN ni RELATED por el metodo anterior.",
            "limite_declarado": "RELATED se calcula sobre `name` de curated_targets.json. "
                                "Un PDB sin nombre curado, o con un nombre que no menciona "
                                "la diana, puede quedar EXTERNAL siendo RELATED. La cifra "
                                "de EXTERNAL es por tanto una COTA SUPERIOR, no un recuento "
                                "verificado, y no sustituye a la curacion manual de cohorte.",
        },
        "advertencia": "DISTRIBUIDA y EXTERNAL son propiedades independientes. "
                       "1GKC es DISTRIBUIDA y SEEN. Deducir una de otra fue el error "
                       "que corrige este inventario.",
        "estructuras": clasificacion,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with io.open(args.out, "w", encoding="utf-8") as fh:
        json.dump(salida, fh, indent=2, ensure_ascii=False)

    print(f"ficheros de estructura: {len(ficheros)}")
    for ext, n in sorted(por_extension.items()):
        print(f"  {ext}: {n}")
    print(f"pdb_ids distintos: {len(ids)}")
    print(f"  SEEN={resumen['SEEN']}  RELATED={resumen['RELATED']}  EXTERNAL(cota sup.)={resumen['EXTERNAL']}")
    for k, v in confirmaciones.items():
        print(f"  {k}: distribuida={v['distribuida']} nivel={v['nivel_de_fuga']}")
    print(f"-> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
