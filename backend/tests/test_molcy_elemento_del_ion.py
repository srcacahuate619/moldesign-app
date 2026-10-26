"""SCI-A-028: el PDB visual de Molcy conserva el elemento de los iones del receptor.

El mapa propio de `pdbqt_a_pdb` no tenía metales, y un tipo que no conocía caía a
la primera letra del nombre del átomo: un ``Fe`` conservado salía como ``F``
(flúor) en el archivo que dibuja el motor. Ahora decide el tipo AutoDock con el
decodificador compartido, que distingue ``NA`` (nitrógeno aceptor) de ``Na``
(sodio).
"""
from __future__ import annotations

import pytest

from services.molcy.package import pdbqt_a_pdb


def _linea(registro, serie, nombre, residuo, numero, x, tipo, cadena="A"):
    """Una línea PDBQT con las columnas en su sitio (tipo en 78-79).

    Como en un PDB, un nombre de una o dos letras que no es un elemento de dos
    letras empieza en la columna 14 (« CA » es el carbono alfa; «FE  », el hierro).
    """
    campo = nombre if len(nombre) == 4 else (f"{nombre:<4}" if registro == "HETATM" else f" {nombre:<3}")
    return (f"{registro:<6}{serie:>5} {campo} {residuo:>3} {cadena}{numero:>4}    "
            f"{x:8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{0.0:6.2f}    {0.0:6.3f} {tipo:<2}")


def _receptor(*extra):
    filas = [
        _linea("ATOM", 1, "N", "ALA", 1, 0.0, "NA"),
        _linea("ATOM", 2, "CA", "ALA", 1, 1.5, "C"),
        _linea("ATOM", 3, "O", "ALA", 1, 2.5, "OA"),
        *extra,
    ]
    return ("\n".join(filas) + "\n").encode("utf-8")


def _elementos(pdb: bytes) -> dict[str, str]:
    salida = {}
    for linea in pdb.decode("utf-8").splitlines():
        if linea.startswith(("ATOM", "HETATM")):
            salida[linea[12:16].strip()] = linea[76:78].strip()
    return salida


@pytest.mark.parametrize("nombre, tipo, esperado", [
    ("FE", "Fe", "FE"),
    ("ZN", "Zn", "ZN"),
    ("MG", "Mg", "MG"),
    ("CA", "Ca", "CA"),
    ("NA", "Na", "NA"),
    ("K", "K", "K"),
])
def test_un_ion_conservado_conserva_su_elemento(nombre, tipo, esperado):
    pdb, _huecos, _cadenas, sin = pdbqt_a_pdb(_receptor(
        _linea("HETATM", 9, nombre, nombre, 109, 19.0, tipo)))
    assert _elementos(pdb)[nombre] == esperado
    assert sin == []


def test_el_nitrogeno_aceptor_no_se_vuelve_sodio():
    pdb, *_ = pdbqt_a_pdb(_receptor())
    assert _elementos(pdb)["N"] == "N"
    assert _elementos(pdb)["O"] == "O"


def test_un_tipo_desconocido_no_se_inventa_y_se_declara():
    pdb, _huecos, _cadenas, sin = pdbqt_a_pdb(_receptor(
        _linea("HETATM", 9, "XX", "UNK", 200, 30.0, "Xx")))
    assert _elementos(pdb)["XX"] == ""
    assert sin == ["Xx"]


def test_el_paquete_declara_los_tipos_sin_elemento(tmp_path):
    from services.molcy.package import construir_paquete, sha256

    receptor = _receptor(_linea("HETATM", 9, "XX", "UNK", 200, 30.0, "Xx"))
    construir_paquete(
        tmp_path / "paquete", receptor_pdbqt=receptor, receptor_sha256=sha256(receptor),
        pdb_id="TEST", nombre="prueba", cadena="A", centro=(0.0, 0.0, 0.0),
        tamano=(20.0, 20.0, 20.0), fuente={"origen": "prueba"},
    )
    import json
    escena = json.loads((tmp_path / "paquete" / "scene.json").read_text(encoding="utf-8"))
    assert escena["declarado"]["tipos_sin_elemento"] == ["Xx"]
