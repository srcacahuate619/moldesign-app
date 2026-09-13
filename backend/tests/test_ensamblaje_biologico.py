"""La unidad biologica: generarla, y no perderla al recortar.

Un PDB deposita la **unidad asimetrica**: lo que hizo falta para describir el
cristal. La **unidad biologica** es la forma funcional. Cuando el ensamblaje
tiene simetria interna que coincide con la del cristal basta depositar una
fraccion, y el resto se reconstruye con las matrices `BIOMT` del `REMARK 350`.

NavAb (5VB8) lo declara con todas las letras::

    AUTHOR DETERMINED BIOLOGICAL UNIT: TETRAMERIC

Medido sobre el catalogo antes de arreglarlo: **31 objetivos tenian atomos que
faltaban dentro de su caja de docking, y diez superaban el 40%**. Es el mismo
defecto que el modo C del doc 71 -el sitio se forma entre copias y solo se
conserva una- pero generado por la simetria cristalografica en vez de por el
filtrado de cadena, y era invisible a todas las comprobaciones anteriores porque
todas leian las coordenadas depositadas.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from services.chemistry.ensamblaje_biologico import (
    generar_unidad_biologica,
    leer_matrices,
)

RAIZ = Path(__file__).resolve().parents[2]
ESTRUCTURAS = RAIZ / "data" / "targets"
CATALOGO = RAIZ / "curated_targets.json"

#: Tetramero cuyo sitio forman dos subunidades: la depositada y una copia.
TETRAMERO = "6SX5"
#: Sin nada que generar. Sirve para comprobar que no se toca lo que no hay que
#: tocar, que son 341 de los 380 del catalogo.
SIN_SIMETRIA = "7E2Y"


def _leer(pdb_id: str) -> str:
    f = ESTRUCTURAS / f"{pdb_id}.pdb.gz"
    if not f.is_file():
        pytest.skip(f"falta {f}")
    with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _cadenas(pdb_text: str) -> dict[str, int]:
    salida: dict[str, int] = {}
    for l in pdb_text.splitlines():
        if l.startswith(("ATOM", "HETATM")) and len(l) > 21:
            salida[l[21]] = salida.get(l[21], 0) + 1
    return salida


# ── Generar ──────────────────────────────────────────────────────────────────

def test_genera_las_copias_que_el_pdb_declara():
    ens = generar_unidad_biologica(_leer(TETRAMERO), pdb_id=TETRAMERO)
    assert ens.generado
    assert ens.operadores == 4
    assert len(ens.cadenas_originales) == 1
    assert len(ens.cadenas_finales) == 4
    cadenas = _cadenas(ens.pdb)
    assert len(cadenas) == 4
    # Las cuatro copias tienen el mismo numero de atomos: son la misma cadena.
    assert len(set(cadenas.values())) == 1


def test_no_toca_lo_que_no_hay_que_tocar():
    """341 de los 380 no tienen nada que generar. Ahi la funcion es la identidad."""
    original = _leer(SIN_SIMETRIA)
    ens = generar_unidad_biologica(original, pdb_id=SIN_SIMETRIA)
    assert not ens.generado
    assert ens.pdb == original, "se modifico un PDB que no tenia simetria que aplicar"


def test_las_copias_no_colisionan_de_identificador():
    """Dos cadenas con el mismo identificador y los mismos numeros de residuo se
    fundirian en `trim_to_pocket`, que indexa por (cadena, numero, inscode)."""
    ens = generar_unidad_biologica(_leer(TETRAMERO), pdb_id=TETRAMERO)
    assert len(set(ens.cadenas_finales)) == len(ens.cadenas_finales)
    for c in ens.cadenas_originales:
        assert c in ens.cadenas_finales, "una copia piso el identificador del original"


def test_es_determinista():
    """La cache del receptor preparado compara conjuntos de cadenas. Si los
    nombres cambiaran entre corridas, se invalidaria el `.pdbqt` en cada
    arranque y el usuario esperaria de mas para siempre."""
    a = generar_unidad_biologica(_leer(TETRAMERO), pdb_id=TETRAMERO)
    b = generar_unidad_biologica(_leer(TETRAMERO), pdb_id=TETRAMERO)
    assert a.pdb == b.pdb
    assert a.cadenas_finales == b.cadenas_finales


def test_solo_lee_el_ensamblaje_principal():
    """Varias entradas declaran mas de un ensamblaje -formas alternativas, o el
    contenido de la unidad asimetrica frente al biologico-. Mezclarlos generaria
    copias que nadie pidio."""
    matrices = leer_matrices(_leer(TETRAMERO))
    assert len(matrices) == 4, f"se leyeron {len(matrices)} matrices en vez de las de BIOMOLECULE 1"


def test_sin_remark_350_devuelve_la_entrada():
    texto = "ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00\nEND\n"
    ens = generar_unidad_biologica(texto)
    assert not ens.generado
    assert ens.pdb == texto


# ── No perderla al recortar ──────────────────────────────────────────────────

def test_el_recorte_del_receptor_conserva_las_cadenas():
    """EL DEFECTO QUE ESTO CAZA, y casi se me pasa.

    `trim_to_pocket` pasa el resultado por PDBFixer cuando el recorte quita mas
    del 50% de los atomos, para tapar los extremos rotos. PDBFixer reescribe el
    PDB a traves de la topologia de OpenMM y RENOMBRA LAS CADENAS.

    Medido sobre 6SX5, cuyo sitio forman la cadena A y su copia de simetria D:

        tras filtrar a {A, D}    {'A': 2079, 'D': 2079}
        con caps                 {'A': 1423}      <- la D desaparecio
        sin caps                 {'A': 700, 'D': 1345}

    El receptor perdia media cavidad EN SILENCIO, que es exactamente el defecto
    que el recorte multicadena existe para reparar. Los caps siguen activos por
    defecto porque MM-GBSA los necesita: un terminal roto falsea la energia.
    """
    from core.config import get_settings
    from services.docking.preparer import _filter_pdb_content, _recortar_al_sitio

    Path(get_settings().vina_temp_dir).mkdir(parents=True, exist_ok=True)
    objetivos = {t["pdb_id"].upper(): t for t in json.loads(CATALOGO.read_text(encoding="utf-8"))}
    assert TETRAMERO in objetivos, f"{TETRAMERO} ya no esta en el catalogo"
    t = objetivos[TETRAMERO]

    sitio = sorted(set(t["site_chains"]))
    assert len(sitio) >= 2, (
        f"{TETRAMERO} deberia tener un sitio de varias cadenas tras generar el "
        f"ensamblaje, y tiene {sitio}"
    )
    centro = (t["grid_center_x"], t["grid_center_y"], t["grid_center_z"])
    tamano = (t["grid_size_x"], t["grid_size_y"], t["grid_size_z"])

    ens = generar_unidad_biologica(_leer(TETRAMERO), pdb_id=TETRAMERO)
    filtrado = _filter_pdb_content(ens.pdb, set(sitio), keep_hetatm=True)
    recortado = _recortar_al_sitio(
        filtrado, pdb_id=TETRAMERO, center=centro, size=tamano, cadenas=sitio)

    conservadas = set(_cadenas(recortado))
    assert conservadas == set(sitio), (
        f"el recorte perdio cadenas: pedidas {sitio}, conservadas {sorted(conservadas)}. "
        "Si volvio PDBFixer, renombro las cadenas y el receptor perdio media cavidad."
    )


def test_los_caps_siguen_activos_por_defecto():
    """MM-GBSA y la ventana de ProLIF los necesitan: apagarlos ahi cambiaria una
    energia. La diferencia es deliberada y va por argumento, no por copia."""
    import inspect

    from services.chemistry import protein_surgery

    firma = inspect.signature(protein_surgery.trim_to_pocket)
    assert firma.parameters["apply_caps"].default is True
