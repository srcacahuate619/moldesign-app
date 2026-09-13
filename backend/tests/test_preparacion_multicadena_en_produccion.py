"""El receptor multicadena, conectado al camino real de preparacion.

Doc 71, modo de fallo C. `preparer.py` conservaba SOLO la cadena declarada. Para
un sitio que se forma ENTRE cadenas -la proteasa del VIH es el caso de libro- eso
deja al ligando acoplando contra media cavidad.

El modulo `preparer_multichain` existia desde `3f0ef0d` pero nadie lo invocaba.
Estas pruebas fijan las tres cosas que hacen que ahora si se invoque, y bien:

 1. El filtro conserva TODAS las cadenas del sitio, no solo la declarada.
 2. El radio de recorte se DERIVA de la caja, y el invariante que lo justifica
    -no se pierde ningun atomo que el ligando pueda tocar- se comprueba, no se
    promete.
 3. El modo sale de `site_chains`; con una sola cadena el comportamiento
    historico queda intacto byte a byte.
"""

from __future__ import annotations

import gzip
import math
from pathlib import Path

import pytest

from services.docking.preparer import (
    _filter_pdb_content,
    prepared_receptor_matches_chain,
)
from services.docking.preparer_multichain import ALCANCE_VDW_A, radio_para_caja

ESTRUCTURAS = Path(__file__).resolve().parents[2] / "data" / "targets"
CATALOGO = Path(__file__).resolve().parents[2] / "curated_targets.json"


#: El receptor multicadena de referencia. 5COP es la proteasa del VIH SALVAJE:
#: su sitio activo esta en la interfaz del dimero, con 54 atomos de contacto por
#: cada cadena y evidencia de ligando co-cristalizado.
#:
#: Antes era 1TW7 -la proteasa multirresistente-, que se retiro del catalogo
#: porque sus diez hotspots estaban a 16-25 A del sitio. Al retirarlo, `_caja`
#: hacia `pytest.skip` y ESTA PRUEBA SE APAGABA SIN QUE NADIE LO NOTARA: el
#: invariante del radio dejaba de comprobarse en silencio. Por eso ahora falla.
RECEPTOR_DE_INTERFAZ = "5COP"


def _caja(pdb_id: str) -> tuple[tuple[float, float, float], float]:
    """El centro y el lado REALES del catalogo.

    No se escriben a mano. La primera version de esta prueba llevaba un centro
    inventado para 6HW5: el recorte pasaba por vacio -no habia atomos cerca- y
    la asercion se cumplia por la razon equivocada. Una prueba que pasa sin
    tocar lo que dice medir es peor que no tenerla.

    Y si el receptor ya no esta en el catalogo, esto FALLA en vez de saltar: un
    `skip` aqui apaga el invariante del radio sin dejar rastro.
    """
    import json

    for t in json.loads(CATALOGO.read_text(encoding="utf-8")):
        if (t.get("pdb_id") or "").upper() == pdb_id.upper():
            return ((t["grid_center_x"], t["grid_center_y"], t["grid_center_z"]),
                    max(t["grid_size_x"], t["grid_size_y"], t["grid_size_z"]))
    raise AssertionError(
        f"{pdb_id} ya no esta en el catalogo. Esta prueba se quedaria sin material "
        "y el invariante del radio dejaria de comprobarse: elige otro receptor de "
        "interfaz y actualiza RECEPTOR_DE_INTERFAZ."
    )


def _leer(pdb_id: str) -> str:
    f = ESTRUCTURAS / f"{pdb_id}.pdb.gz"
    if not f.is_file():
        pytest.skip(f"falta {f}")
    with gzip.open(f, "rt", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _atomos(contenido: str) -> list[tuple[str, tuple[float, float, float]]]:
    salida = []
    for linea in contenido.splitlines():
        if not linea.startswith(("ATOM", "HETATM")):
            continue
        try:
            salida.append((linea[21].strip(),
                           (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))))
        except ValueError:
            continue
    return salida


# ── El radio: una consecuencia, no un parametro ──────────────────────────────

def test_el_radio_crece_con_la_caja():
    """Las cajas del catalogo van de 20,6 a 50 A: un radio fijo no puede servir."""
    assert radio_para_caja(22.0) < radio_para_caja(30.0) < radio_para_caja(50.0)
    # Semidiagonal del cubo mas el alcance de van der Waals.
    assert radio_para_caja(30.0) == pytest.approx(30.0 * math.sqrt(3) / 2 + ALCANCE_VDW_A)


def test_el_radio_derivado_no_pierde_nada_de_lo_que_el_ligando_puede_tocar():
    """EL INVARIANTE. Es lo que convierte el radio en una consecuencia.

    Todo atomo que este dentro de la caja mas el alcance de van der Waals tiene
    que sobrevivir al recorte. Si alguien baja el radio, esta prueba lo dice.

    Con los 12 A fijos de la primera version se perdian 389 de los 926 atomos
    alcanzables de la proteasa del VIH -el 42%-, que es el mismo defecto que el modulo existe
    para reparar, entrando por otra puerta.
    """
    contenido = _leer(RECEPTOR_DE_INTERFAZ)
    # La caja de 5COP, centrada en la interfaz catalitica del dimero.
    centro, lado = _caja(RECEPTOR_DE_INTERFAZ)
    radio = radio_para_caja(lado)

    medio = lado / 2 + ALCANCE_VDW_A
    alcanzables = [
        p for _, p in _atomos(contenido)
        if all(abs(p[i] - centro[i]) <= medio for i in range(3))
    ]
    assert alcanzables, f"la caja de {RECEPTOR_DE_INTERFAZ} deberia contener atomos"

    perdidos = [p for p in alcanzables if math.dist(p, centro) > radio]
    assert not perdidos, (
        f"{len(perdidos)} de {len(alcanzables)} atomos alcanzables quedan fuera de un "
        f"radio de {radio:.1f} A. El ligando acoplaria contra el vacio en los bordes."
    )


def test_el_radio_derivado_sigue_resolviendo_el_problema_de_tamano():
    """La v1.6 recortaba a una cadena por receptores de 5 y 10 MB. Sigue resuelto.

    Sobre la proteasa el recorte conserva casi todo -es un dimero pequeno- pero sobre un
    complejo grande tiene que dejar una fraccion menor. Se comprueba con 6HW5,
    49.296 atomos.
    """
    contenido = _leer("6HW5")
    centro, lado = _caja("6HW5")
    radio = radio_para_caja(lado)
    todos = _atomos(contenido)
    dentro = [p for _, p in todos if math.dist(p, centro) <= radio]
    assert len(todos) > 40000, "6HW5 deberia ser un complejo grande"
    # Y el recorte tiene que pasar POR el sitio, no por el vacio.
    assert len(dentro) > 1000, (
        f"solo {len(dentro)} atomos dentro del radio: el centro no cae sobre la proteina "
        "y la prueba no estaria midiendo el recorte"
    )
    assert len(dentro) / len(todos) < 0.15, (
        f"el recorte conserva {len(dentro)}/{len(todos)} atomos: demasiado para "
        "haber resuelto el problema de tamano de la v1.6"
    )


# ── El filtro: todas las cadenas del sitio ───────────────────────────────────

def test_el_filtro_conserva_todas_las_cadenas_pedidas():
    contenido = _leer(RECEPTOR_DE_INTERFAZ)
    una = _filter_pdb_content(contenido, "A", keep_hetatm=True)
    dos = _filter_pdb_content(contenido, {"A", "B"}, keep_hetatm=True)

    cadenas_una = {c for c, _ in _atomos(una)}
    cadenas_dos = {c for c, _ in _atomos(dos)}
    assert cadenas_una == {"A"}
    assert cadenas_dos == {"A", "B"}
    assert len(_atomos(dos)) > len(_atomos(una))


def test_una_sola_cadena_se_comporta_igual_que_antes():
    """El modo historico no cambia: mismo resultado con str o con conjunto."""
    contenido = _leer(RECEPTOR_DE_INTERFAZ)
    assert (_filter_pdb_content(contenido, "A", keep_hetatm=True)
            == _filter_pdb_content(contenido, {"A"}, keep_hetatm=True))


# ── La cache no puede servir un receptor por otro ────────────────────────────

def test_la_cache_distingue_una_cadena_de_varias():
    """Servir el receptor de una cadena a una corrida multicadena seria el fallo
    del doc 71 devuelto por la puerta de atras, y en silencio."""
    pdbqt_una = "ATOM      1  N   ALA A   1      0.0   0.0   0.0  1.00  0.00\n"
    pdbqt_dos = pdbqt_una + "ATOM      2  N   ALA B   1      0.0   0.0   0.0  1.00  0.00\n"

    assert prepared_receptor_matches_chain(pdbqt_una, "A")
    assert prepared_receptor_matches_chain(pdbqt_una, {"A"})
    assert not prepared_receptor_matches_chain(pdbqt_una, {"A", "B"})
    assert prepared_receptor_matches_chain(pdbqt_dos, {"A", "B"})
    assert not prepared_receptor_matches_chain(pdbqt_dos, "A")
