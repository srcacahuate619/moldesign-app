"""El receptor multicadena conserva el sitio entero y nada más.

# Qué protege

`preparer.py` recorta a UNA cadena. Esa decisión resolvió un problema real
—`SESSION_SUMMARY_v1.6`: Vina acoplando contra dímeros y tetrámeros enteros, con
receptores de 5,8 y 10,5 MB— pero para un sitio que se forma entre cadenas deja
al ligando acoplando contra media cavidad.

Estas pruebas fijan las tres propiedades que hacen utilizable la alternativa, y
que son fáciles de romper sin darse cuenta:

1. **Se conservan residuos de TODAS las cadenas del sitio.** Es el punto entero.
2. **No se arrastra la proteína completa.** Si no, se reintroduce el problema
   que v1.6 resolvió.
3. **Un centro que no toca la estructura FALLA.** No se devuelve un receptor a
   ciegas.

La tercera nació de un control que la primera versión no pasó: `trim_to_pocket`
devuelve el archivo ORIGINAL cuando no encuentra residuos en el radio, y el
módulo lo procesaba entregando la proteína entera disfrazada de sitio recortado.
"""

from __future__ import annotations

import textwrap

import pytest

from services.docking.preparer_multichain import preparar_receptor_multichain


def _pdb_de_dos_cadenas(tmp_path):
    """Dos cadenas con un sitio compartido en el origen, y una tercera lejos.

    A y B ponen residuos cerca de (0,0,0); C esta a 40 A y no debe entrar.
    """
    lineas = []
    n = 1

    def atomo(nombre, resn, cadena, resi, x, y, z):
        nonlocal n
        lineas.append(
            f"ATOM  {n:5d}  {nombre:<3s} {resn} {cadena}{resi:4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           {nombre[0]}"
        )
        n += 1

    # Cadena A: dos residuos pegados al centro
    for i, dz in enumerate((0.0, 2.0), start=1):
        for nombre, dx in (("N", 0.0), ("CA", 1.5), ("C", 2.5), ("O", 3.0)):
            atomo(nombre, "ALA", "A", i, dx, 0.0, dz)
    # Cadena B: dos residuos igual de cerca, al otro lado
    for i, dz in enumerate((0.0, 2.0), start=1):
        for nombre, dx in (("N", 0.0), ("CA", -1.5), ("C", -2.5), ("O", -3.0)):
            atomo(nombre, "GLY", "B", i, dx, 1.0, dz)
    # Cadena C: lejos del sitio, no debe aparecer
    for nombre, dx in (("N", 40.0), ("CA", 41.5), ("C", 42.5), ("O", 43.0)):
        atomo(nombre, "LEU", "C", 1, dx, 40.0, 40.0)
    # Un agua pegada al centro: la politica vigente la retira
    lineas.append(
        f"HETATM{n:5d}  O   HOH A 900       0.500   0.500   0.500  1.00  0.00           O"
    )

    p = tmp_path / "dos_cadenas.pdb"
    p.write_text("\n".join(lineas) + "\nEND\n", encoding="utf-8")
    return p


def test_conserva_residuos_de_todas_las_cadenas_del_sitio(tmp_path):
    """Aunque el catalogo declare 'A', la cadena B forma parte del sitio."""
    pdb = _pdb_de_dos_cadenas(tmp_path)
    r = preparar_receptor_multichain(
        pdb, (0.0, 0.0, 1.0), cadena_declarada="A",
        radio=12.0, salida=tmp_path / "sitio.pdb",
    )
    assert "A" in r.cadenas and "B" in r.cadenas, (
        f"el sitio se forma entre A y B; se conservaron {r.cadenas}"
    )
    assert r.cadenas_recuperadas == ("B",), (
        "B es exactamente lo que el modo de una cadena habria tirado"
    )


def test_no_arrastra_lo_que_esta_lejos_del_sitio(tmp_path):
    """Si entrara la cadena C, se reintroduce el problema que v1.6 resolvio."""
    pdb = _pdb_de_dos_cadenas(tmp_path)
    r = preparar_receptor_multichain(
        pdb, (0.0, 0.0, 1.0), cadena_declarada="A",
        radio=12.0, salida=tmp_path / "sitio.pdb",
    )
    assert "C" not in r.cadenas, (
        f"la cadena C esta a 40 A del sitio y no debe entrar; quedo {r.cadenas}"
    )


def test_retira_las_aguas_como_el_modo_de_una_cadena(tmp_path):
    """La politica de aguas (docs/51) es la misma en los dos modos."""
    pdb = _pdb_de_dos_cadenas(tmp_path)
    r = preparar_receptor_multichain(
        pdb, (0.0, 0.0, 1.0), cadena_declarada="A",
        radio=12.0, salida=tmp_path / "sitio.pdb",
    )
    texto = r.ruta.read_text(encoding="utf-8")
    assert "HOH" not in texto, "la politica vigente retira las aguas del receptor"


def test_un_centro_que_no_toca_la_estructura_falla(tmp_path):
    """El fallo silencioso que la primera version tenia.

    `trim_to_pocket` devuelve el PDB ORIGINAL cuando no hay residuos en el
    radio. Sin esta guarda, un centro equivocado entregaba la proteina COMPLETA
    haciendola pasar por un sitio recortado — y el docking habria producido una
    afinidad sobre un receptor que nadie pidio.
    """
    pdb = _pdb_de_dos_cadenas(tmp_path)
    with pytest.raises(ValueError, match="no tiene ningun residuo"):
        preparar_receptor_multichain(
            pdb, (999.0, 999.0, 999.0), cadena_declarada="A",
            radio=12.0, salida=tmp_path / "vacio.pdb",
        )
