#!/usr/bin/env python3
r"""Subida de receptores propios por la API, como la aplicación: qué entra y qué se evalúa.

Levanta un backend con datos desechables (el arnés de `check:evaluation-runtime`, vía
`scripts/calibracion_receptor.py::Backend`), sube cada caso por `POST /targets/upload`
y, si se acepta, evalúa un ligando con `/evaluation/preflight` + `/evaluation/submit`.

Uso (con el Python embebido):

    D:\moldesign-build\python-embed\python.exe ^
        D:\moldesign-build\docs\encargos\receptores-propios-1-0-2\qa_subida_receptores.py ^
        --raiz D:\moldesign-build\.worktrees\receptores-propios ^
        --casos casos.json --salida D:\moldesign-audits\receptores-propios-AAAAMMDD

`--raiz` es obligatorio: el backend, `tools/vina` y los módulos se toman de ese árbol.

`casos.json` es una lista de objetos:

    {"archivo": "ruta al archivo",            # se sube con su nombre (o "nombre")
     "nombre": "8HFI_CRUDO.PDB",               # opcional: nombre con el que se sube
     "campos": {"is_curated": "false", "chain_id": "A", ...},  # campos del formulario
     "origen": "ruta opcional a la estructura de origen",       # si el endpoint lo admite
     "campo_origen": "source_file",            # nombre del campo del archivo de origen
     "esperado": {"http": 201, "evaluacion": "SUCCESS"}}         # lo que el caso exige

Sin `--casos`, repite los cuatro casos medidos el 2026-10-09 (`informe_20261009.json`).
Escribe `informe.json` con lo observado frente a lo esperado y sale con código 1 si algún
caso no cumple lo esperado.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

def _raiz() -> Path:
    """El árbol cuyo backend se prueba: `--raiz` (el worktree de la sesión).

    Importa `calibracion_receptor` y el arnés de la puerta DESDE ese árbol, así
    que el backend que se levanta, `tools/vina` y `python-embed` son los suyos.
    Sin `--raiz` probaría el árbol donde vive este archivo, que no es el que se
    está cambiando.
    """
    for i, arg in enumerate(sys.argv):
        if arg == "--raiz" and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1]).resolve()
        if arg.startswith("--raiz="):
            return Path(arg.split("=", 1)[1]).resolve()
    raise SystemExit("Falta --raiz: la raíz del worktree cuyo backend se prueba.")


RAIZ = _raiz()
if not (RAIZ / "scripts" / "calibracion_receptor.py").is_file():
    raise SystemExit(f"{RAIZ} no parece la raíz de un worktree de MolDesign.")
sys.path.insert(0, str(RAIZ / "scripts"))
import calibracion_receptor as cr  # noqa: E402

DESIPRAMINA = "CNCCCN1c2ccccc2CCc2ccccc21"
CENTRO_8HFI = ("100.281", "100.843", "101.442")
FUENTE = Path(r"D:\moldesign-audits\cal-8hfi-01\datos-01\targets\8HFI")


def _casos_por_defecto() -> list[dict]:
    caja = {"chain_id": "A", "grid_center_x": CENTRO_8HFI[0], "grid_center_y": CENTRO_8HFI[1],
            "grid_center_z": CENTRO_8HFI[2], "grid_size_x": "30", "grid_size_y": "30", "grid_size_z": "30"}
    pdbqt = str(next(FUENTE.glob("prepared-*.pdbqt")))
    return [
        {"archivo": pdbqt, "nombre": "8hfi_curado.pdbqt", "campos": {**caja, "is_curated": "true"},
         "esperado": {"http": 201, "evaluacion": "SUCCESS"}},
        {"archivo": str(FUENTE / "raw.pdb"), "nombre": "8hfi_crudo.pdb", "campos": {**caja, "is_curated": "false"},
         "esperado": {"http": 201, "evaluacion": "SUCCESS"}},
        {"archivo": str(FUENTE / "raw.pdb"), "nombre": "8HFI_CRUDO.PDB", "campos": {**caja, "is_curated": "false"},
         "esperado": {"http": 201, "evaluacion": "SUCCESS"}},
        {"archivo": r"D:\moldesign-audits\verificacion-8hfi-20261008\fuentes\8HFI.cif", "nombre": "8hfi.cif",
         "campos": {**caja, "is_curated": "false"}, "esperado": {"http": 201, "evaluacion": "SUCCESS"}},
    ]


def _multipart(campos: dict[str, str], archivos: list[tuple[str, str, bytes]]) -> tuple[bytes, str]:
    limite = uuid.uuid4().hex
    partes = [f'--{limite}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
              for k, v in campos.items()]
    for campo, nombre, contenido in archivos:
        partes.append(f'--{limite}\r\nContent-Disposition: form-data; name="{campo}"; filename="{nombre}"\r\n'
                      "Content-Type: application/octet-stream\r\n\r\n".encode() + contenido + b"\r\n")
    partes.append(f"--{limite}--\r\n".encode())
    return b"".join(partes), f"multipart/form-data; boundary={limite}"


def subir(be: cr.Backend, caso: dict) -> tuple[int, dict]:
    archivo = Path(caso["archivo"])
    archivos = [("file", caso.get("nombre") or archivo.name, archivo.read_bytes())]
    if caso.get("origen"):
        origen = Path(caso["origen"])
        archivos.append((caso.get("campo_origen", "source_file"), origen.name, origen.read_bytes()))
    campos = {"name": f"prueba {archivos[0][1]}", **caso.get("campos", {})}
    cuerpo, tipo = _multipart(campos, archivos)
    req = urllib.request.Request(be.base + "/targets/upload", data=cuerpo, method="POST",
                                 headers={"Authorization": f"Bearer {be.token}", "Content-Type": tipo})
    try:
        with urllib.request.urlopen(req, timeout=1800) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, {"detail": e.read().decode("utf-8", "replace")[:800]}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 2)[1])
    p.add_argument("--raiz", required=True, help="raíz del worktree cuyo backend se prueba")
    p.add_argument("--casos")
    p.add_argument("--salida", required=True)
    p.add_argument("--smiles", default=DESIPRAMINA)
    a = p.parse_args()
    salida = Path(a.salida)
    casos = json.loads(Path(a.casos).read_text(encoding="utf-8")) if a.casos else _casos_por_defecto()
    informe, fallan = [], 0
    with cr.Backend(salida / "datos") as be:
        for caso in casos:
            codigo, cuerpo = subir(be, caso)
            target = (cuerpo.get("target") or {}) if isinstance(cuerpo, dict) else {}
            fila = {"caso": caso.get("nombre") or Path(caso["archivo"]).name, "campos": caso.get("campos"),
                    "origen": caso.get("origen"), "http": codigo,
                    "detalle": cuerpo.get("detail") if codigo >= 400 else cuerpo.get("message"),
                    "pdb_id": target.get("pdb_id")}
            if codigo < 400 and fila["pdb_id"]:
                try:
                    r = be.evaluar(a.smiles, fila["pdb_id"], caso.get("campos", {}).get("chain_id", "A"), 42,
                                   f"subida-{fila['caso']}")
                    res = r["resultado"]
                    prov = (res.get("docking_protocol") or {}).get("execution_provenance") or {}
                    prep = prov.get("receptor_prep") or {}
                    fila.update({"evaluacion": "SUCCESS", "E_top1": res.get("affinity_kcal"),
                                 "segundos": r["segundos"], "receptor_sha256": prov.get("receptor_sha256"),
                                 "species_diff": bool(prep.get("species_diff")),
                                 "protonation_method": prep.get("protonation_method")})
                except Exception as exc:  # noqa: BLE001 - se registra
                    fila.update({"evaluacion": "FALLA", "error": str(exc)[:600]})
            esperado = caso.get("esperado") or {}
            fila["cumple"] = all(fila.get(k) == v for k, v in esperado.items())
            fallan += not fila["cumple"]
            informe.append(fila)
            print(json.dumps(fila, ensure_ascii=False), flush=True)
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "informe.json").write_text(json.dumps(informe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{len(informe) - fallan}/{len(informe)} casos cumplen lo esperado")
    return 1 if fallan else 0


if __name__ == "__main__":
    raise SystemExit(main())
