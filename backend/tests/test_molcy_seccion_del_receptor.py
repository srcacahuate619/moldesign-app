"""La sección del catálogo viaja a `scene.json`: el vídeo rotula «Demostración» igual que la aplicación.

La aplicación etiqueta cada receptor del catálogo y la etiqueta viaja a dossier, Preparación, resultados, Moldex y
lotes. El vídeo era la única vista sin ella. Ahora `receptor.seccion` lo escribe el backend y el motor lo lee al
titular el vídeo (`scripts/variables/titulos.py` del motor, con su prueba allí).
"""
from __future__ import annotations

import json
from pathlib import Path

from services.molcy.package import construir_paquete, sha256

RAIZ = Path(__file__).resolve().parents[1]


def _linea(registro, serie, nombre, residuo, numero, x, tipo, cadena="A"):
    campo = nombre if len(nombre) == 4 else (f"{nombre:<4}" if registro == "HETATM" else f" {nombre:<3}")
    return (f"{registro:<6}{serie:>5} {campo} {residuo:>3} {cadena}{numero:>4}    "
            f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{0.0:6.2f}    {0.0:6.3f} {tipo:<2}")


def _receptor() -> bytes:
    filas = [
        _linea("ATOM", 1, "N", "ALA", 1, 0.0, "NA"),
        _linea("ATOM", 2, "CA", "ALA", 1, 1.5, "C"),
        _linea("ATOM", 3, "O", "ALA", 1, 2.5, "OA"),
    ]
    return ("\n".join(filas) + "\n").encode("utf-8")


def _paquete(destino: Path, **extra) -> dict:
    receptor = _receptor()
    construir_paquete(
        destino, receptor_pdbqt=receptor, receptor_sha256=sha256(receptor),
        pdb_id="TEST", nombre="prueba", cadena="A", centro=(0.0, 0.0, 0.0),
        tamano=(20.0, 20.0, 20.0), fuente={"origen": "prueba"}, **extra,
    )
    return json.loads((destino / "scene.json").read_text(encoding="utf-8"))


def test_la_escena_declara_la_seccion_del_catalogo(tmp_path):
    escena = _paquete(tmp_path / "paquete", seccion="demostracion")
    assert escena["receptor"]["seccion"] == "demostracion"


def test_sin_seccion_la_escena_la_declara_nula(tmp_path):
    escena = _paquete(tmp_path / "paquete")
    assert escena["receptor"]["seccion"] is None


def test_la_ruta_de_video_pasa_la_seccion_del_receptor():
    """El router de Molcy es quien llama al constructor: si deja de pasar la sección, el vídeo vuelve a salir sin etiqueta."""
    fuente = (RAIZ / "api" / "routers" / "molcy.py").read_text(encoding="utf-8")
    funcion = fuente[fuente.index("def _escribir_paquete("):]
    funcion = funcion[:funcion.index("\ndef ", 1)]
    assert "seccion=seccion_del_receptor(target)" in funcion


def test_el_motor_lee_la_seccion_del_contrato():
    """El motor vendorizado tiene que leer el mismo campo que escribe el backend."""
    motor = RAIZ.parent / "tools" / "molcy" / "scripts" / "nucleo" / "ciencia.py"
    assert 'self.datos["receptor"].get("seccion")' in motor.read_text(encoding="utf-8")
