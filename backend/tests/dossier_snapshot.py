"""Generador determinista de las salidas españolas protegidas por la Fase 0."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from services.dossier.model import build_case_dossier
from services.dossier.package import construir_paquete
from services.dossier.pdf import _CANDIDATAS_DE_FUENTE, render_dossier_pdf
from tests.fixtures_dossier import caso_completo

SNAPSHOT_DIR = Path(__file__).resolve().parent / "snapshots" / "dossier_es"
LOCK_DEL_RUNTIME = BACKEND / "requirements-embed.lock.txt"

#: Las salidas cuyos bytes dependen de la versión de reportlab: el manifiesto
#: lleva el SHA-256 y el tamaño del PDF. Con reportlab 4.5.1 el PDF de la
#: instantánea pesa 101 644 bytes y con 4.2.0, 100 500.
DEPENDEN_DE_REPORTLAB = frozenset({"manifest.json"})


#: SHA-256 de las cuatro Arial con las que se fijó la instantánea. Cada Windows trae las suyas: «es Windows» no
#: basta, y el 2026-11-01 la CI pública dio otro PDF que el Windows 11 donde se escribió.
HUELLA_DE_LA_FUENTE = "4481faa17b2718878b2d7338ff7ae4f603b0eb47b477e917be2184748919616c"


def huella_de_la_fuente() -> str | None:
    resumen = hashlib.sha256()
    for ruta in _CANDIDATAS_DE_FUENTE[0]:
        try:
            resumen.update(Path(ruta).read_bytes())
        except OSError:
            return None
    return resumen.hexdigest()


def fuente_de_la_instantanea() -> bool:
    """El PDF de la instantánea incrusta Arial; otra fuente, u otra versión de ella, cambia sus bytes y su hash."""
    return huella_de_la_fuente() == HUELLA_DE_LA_FUENTE


def mismo_pdf_que_la_instantanea() -> bool:
    return reportlab_de_este_interprete() == reportlab_del_runtime() and fuente_de_la_instantanea()


def manifiesto_sin_el_pdf(contenido: bytes) -> dict:
    """El manifiesto sin el hash ni el tamaño del PDF, lo único suyo que depende de la máquina."""
    manifiesto = json.loads(contenido)
    entradas = [entrada for entrada in manifiesto["files"] if entrada["path"] == "dossier.pdf"]
    assert len(entradas) == 1, "el manifiesto tiene que declarar un solo dossier.pdf"
    del entradas[0]["sha256"], entradas[0]["tamano"]
    return manifiesto


def reportlab_del_runtime() -> str:
    """La versión de reportlab del intérprete que se distribuye (y de la CI)."""
    for linea in LOCK_DEL_RUNTIME.read_text(encoding="utf-8").splitlines():
        if linea.lower().startswith("reportlab=="):
            return linea.split("==", 1)[1].strip()
    raise RuntimeError(f"{LOCK_DEL_RUNTIME.name} no fija reportlab")


def reportlab_de_este_interprete() -> str:
    import reportlab

    return reportlab.Version


def salidas_espanol() -> dict[str, bytes]:
    caso = caso_completo()
    dossier = build_case_dossier(**caso)
    paquete, _entradas, raiz = construir_paquete(
        dossier=dossier,
        pdf_bytes=render_dossier_pdf(dossier).getvalue(),
        projection_json=caso["projection"].model_dump_json(indent=2),
    )
    with zipfile.ZipFile(io.BytesIO(paquete)) as archivo:
        return {
            "dossier.json": dossier.json_canonico().encode("utf-8"),
            "README.md": archivo.read(f"{raiz}/README.md"),
            "manifest.json": archivo.read(f"{raiz}/manifest.json"),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="escribe las instantáneas actuales")
    args = parser.parse_args()
    if args.write and reportlab_de_este_interprete() != reportlab_del_runtime():
        # El 2026-10-06 se escribió con reportlab 4.5.1 (el Python de desarrollo)
        # y la prueba falló desde entonces con el runtime distribuido y en la CI.
        print(f"Instantáneas NO escritas: este intérprete trae reportlab "
              f"{reportlab_de_este_interprete()} y el runtime distribuido "
              f"{reportlab_del_runtime()}. Escríbelas con python-embed.")
        return 2
    if args.write and not fuente_de_la_instantanea():
        print("Instantáneas NO escritas: el PDF no llevaría la Arial de HUELLA_DE_LA_FUENTE. Si Windows la cambió, "
              "actualiza esa huella a propósito y explícalo en el commit.")
        return 2
    actuales = salidas_espanol()
    if args.write:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        for nombre, contenido in actuales.items():
            (SNAPSHOT_DIR / nombre).write_bytes(contenido)
        print(f"Instantáneas escritas: {SNAPSHOT_DIR}")
        return 0

    diferencias = []
    for nombre, contenido in actuales.items():
        ruta = SNAPSHOT_DIR / nombre
        if not ruta.is_file() or ruta.read_bytes() != contenido:
            diferencias.append(nombre)
    if diferencias:
        print("Instantáneas españolas distintas o ausentes: " + ", ".join(diferencias))
        return 1
    print("Instantáneas españolas verificadas: dossier.json, README.md, manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
