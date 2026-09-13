"""El catalogo declara que cadenas forman el sitio, y cuantas no cuadran.

Doc 71. `chain` dice que cadena se PREPARA; `site_chains` dice cuales FORMAN el
sitio. Confundirlas es lo que producia dockings contra media cavidad —o contra
ninguna—. Estas pruebas fijan las dos cosas que no pueden volver a torcerse:

 1. La anotacion es internamente coherente. Un `site_chain_atoms` que no
    corresponda con `site_chains`, o una evidencia inventada, valen tanto como
    no tener el campo.

 2. **La cadena que se prepara tiene que formar el sitio.** La lista de deuda
    llego a 21 y hoy esta VACIA: los 21 declaraban "A" -el default del ORM- y
    ahora declaran la cadena que mas aporta a su sitio. La prueba se queda
    porque su trabajo empieza ahora: falla si alguien vuelve a meter uno.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

CATALOGO = Path(__file__).resolve().parents[2] / "curated_targets.json"

EVIDENCIAS = {"cocrystal_ligand", "box_volume"}

#: Receptores cuya cadena declarada NO forma el sitio de union. Llego a tener 21
#: -todos declarando el `default="A"` de `TargetORM.chain`- y hoy esta vacia.
#: ESTA LISTA SOLO PUEDE ENCOGER. Si crece, alguien anadio un receptor roto.
LA_DECLARADA_NO_FORMA_EL_SITIO: set[str] = set()


@pytest.fixture(scope="module")
def catalogo() -> list[dict]:
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def test_todos_declaran_que_cadenas_forman_el_sitio(catalogo):
    sin_anotar = [t["pdb_id"] for t in catalogo if not t.get("site_chains")]
    assert not sin_anotar, (
        "estos objetivos no dicen que cadenas forman su sitio: " + ", ".join(sin_anotar)
    )


def test_la_evidencia_es_una_de_las_dos_que_sabemos_producir(catalogo):
    raras = {t["pdb_id"]: t.get("site_evidence") for t in catalogo
             if t.get("site_evidence") not in EVIDENCIAS}
    assert not raras, f"evidencia no reconocida: {raras}"


def test_el_reparto_de_atomos_corresponde_con_las_cadenas_del_sitio(catalogo):
    """Si no coinciden, uno de los dos campos miente y no se sabe cual."""
    descuadres = [
        t["pdb_id"] for t in catalogo
        if sorted((t.get("site_chain_atoms") or {}).keys()) != sorted(t.get("site_chains") or [])
    ]
    assert not descuadres, "cadenas y reparto no coinciden en: " + ", ".join(descuadres)


def test_las_cadenas_van_ordenadas_por_aporte(catalogo):
    """La primera de `site_chains` es la que mas aporta: la interfaz lo asume."""
    desordenados = []
    for t in catalogo:
        atomos = t.get("site_chain_atoms") or {}
        cadenas = t.get("site_chains") or []
        cuentas = [atomos.get(c, 0) for c in cadenas]
        if cuentas != sorted(cuentas, reverse=True):
            desordenados.append(t["pdb_id"])
    assert not desordenados, "site_chains sin ordenar por aporte: " + ", ".join(desordenados)


def test_el_ligando_solo_se_declara_cuando_es_la_evidencia(catalogo):
    """Un `site_ligand` con evidencia de volumen seria un cristal que no se uso."""
    contradictorios = [
        t["pdb_id"] for t in catalogo
        if t.get("site_ligand") and t.get("site_evidence") != "cocrystal_ligand"
    ]
    assert not contradictorios, "declaran ligando sin usarlo: " + ", ".join(contradictorios)


def test_la_cadena_que_se_prepara_forma_el_sitio(catalogo):
    """El invariante del doc 71, con su deuda declarada y acotada.

    Preparar una cadena que no forma el sitio es acoplar contra el vacio o
    contra media cavidad. La lista es la deuda que queda; la prueba existe para
    que no crezca sin que nadie se entere.
    """
    fuera = {
        t["pdb_id"].upper() for t in catalogo
        if (t.get("chain") or "").strip().upper() not in (t.get("site_chains") or [])
    }
    nuevos = fuera - LA_DECLARADA_NO_FORMA_EL_SITIO
    assert not nuevos, (
        "receptores NUEVOS cuya cadena declarada no forma el sitio: "
        + ", ".join(sorted(nuevos))
        + ". Un docking sobre ellos devuelve una afinidad sin sustento fisico."
    )

    rescatados = LA_DECLARADA_NO_FORMA_EL_SITIO - fuera
    assert not rescatados, (
        "estos ya estan arreglados: quitalos de LA_DECLARADA_NO_FORMA_EL_SITIO "
        "para que la deuda declarada siga siendo la real -> " + ", ".join(sorted(rescatados))
    )


def test_los_sitios_entre_cadenas_estan_contados(catalogo):
    """Cuantos son, para que el doc 72 no cite un numero que ya cambio.

    Subio de 98 a 110 al generar la unidad biologica: quince sitios que parecian
    monomericos son interfaces con una copia de simetria.

    OJO con confundirlo con el 101 del doc 71: aquel cuenta los objetivos que
    pierden >=20% de los atomos de la CAJA al conservar una sola cadena. Son
    dos poblaciones distintas que coincidian en tamano por casualidad -99 y 110
    hoy, con 91 en comun-. Medir volumen perdido no es lo mismo que medir
    cuantas cadenas forman el sitio.
    """
    interfaz = [t for t in catalogo if len(t.get("site_chains") or []) > 1]
    assert len(interfaz) == 110, (
        f"el catalogo tiene {len(interfaz)} sitios formados por mas de una cadena "
        "y el doc 72 cita 110. Si cambio la anotacion, actualiza el documento."
    )


FUENTES_DE_HOTSPOT = {"auto_pocket_top15", "box_ligand_contacts"}


def test_todos_declaran_de_donde_salen_sus_hotspots(catalogo):
    """Ninguno viene del RCSB, y el catalogo tiene que decirlo en los 385.

    Marcar solo los rederivados sugeriria que los demas son oficiales del PDB.
    No lo son: `backend/scripts/recure_targets.py` los genero corriendo
    `discover_pocket_from_pdb` sobre los 387. La transparencia es sobre el
    catalogo entero o no es transparencia.
    """
    sin_fuente = [t["pdb_id"] for t in catalogo
                  if t.get("hotspots_source") not in FUENTES_DE_HOTSPOT]
    assert not sin_fuente, (
        "no declaran la procedencia de sus hotspots: " + ", ".join(sin_fuente)
    )


def test_los_rederivados_son_los_que_medimos(catalogo):
    """Nueve, y solo nueve. Ver `docs/auditorias/hotspots_reanotados.json`."""
    rederivados = {t["pdb_id"].upper() for t in catalogo
                   if t.get("hotspots_source") == "box_ligand_contacts"}
    assert rederivados == {
        "1VKG", "1W22", "2NNJ", "2VE3", "4EJJ", "4JV6", "4JV8", "4NY4", "7JVU",
    }, f"la lista de rederivados cambio: {sorted(rederivados)}"


#: Los siete que salieron del catalogo, con su fila completa guardada en
#: `docs/auditorias/receptores_retirados.json`. Dos por no ser receptores
#: -cristales de hexapeptido- y cinco por exigir una decision cientifica que
#: ninguna herramienta puede tomar. Retirarlos no es borrar la evidencia:
#: reponer uno es copiar `fila_completa` de vuelta.
RETIRADOS = {"2ONV", "5TXJ", "1TW7", "5T4X", "6PSD", "6VU4", "5VB8"}


def test_los_no_receptores_estan_fuera(catalogo):
    """Ninguno de los retirados vuelve al catalogo por accidente."""
    ids = {t["pdb_id"].upper() for t in catalogo}
    assert not ids & RETIRADOS, "un receptor retirado volvio al catalogo"
    assert len(catalogo) == 380, (
        f"el catalogo tiene {len(catalogo)} objetivos y se esperaban 380"
    )


@pytest.mark.slow
def test_ninguna_caja_nueva_arranca_en_el_vacio(catalogo):
    """El centro de la caja tiene que estar TOCANDO el bolsillo.

    Medido sobre los 385: la distancia del centro de la caja al atomo de
    proteina mas cercano tiene mediana 3,5 A y p99 5,4 A. Es lo esperable —el
    centro de un bolsillo esta a un radio de van der Waals de su pared—.

    Dos lo superan, y por razones distintas:

      5VB8  10,3 A. Es un canal de sodio TETRAMERICO depositado con UNA sola
            cadena: el PDB dice «AUTHOR DETERMINED BIOLOGICAL UNIT: TETRAMERIC»
            y la unidad hay que generarla con las matrices BIOMT del REMARK 350.
            La caja esta sobre el eje del poro, que es donde el poro estaria; con
            una sola subunidad, tres cuartas partes de su pared no existen en el
            archivo.

      2A3W   8,2 A. Amiloide serico P, decamerico. La caja esta centrada en su
            ligando co-cristalizado, que ocupa una cavidad amplia. El ligando SI
            esta ahi, asi que no es el mismo problema.

    46 de los 385 declaran una unidad biologica que hay que generar con BIOMT,
    pero eso NO es un defecto por si mismo: un sitio contenido en una subunidad
    se acopla bien contra la unidad depositada. Lo que discrimina es esta
    distancia, y solo 5VB8 la supera por esa causa.

    La prueba existe para el receptor que alguien anada manana.
    """
    import gzip
    import math

    estructuras = Path(__file__).resolve().parents[2] / "data" / "targets"
    conocidos = {"5VB8", "2A3W"}
    nuevos = []
    for t in catalogo:
        pdb = t["pdb_id"].upper()
        archivo = estructuras / f"{pdb}.pdb.gz"
        if not archivo.is_file():
            continue
        centro = (t["grid_center_x"], t["grid_center_y"], t["grid_center_z"])
        mejor = 1e9
        with gzip.open(archivo, "rt", encoding="utf-8", errors="replace") as fh:
            for linea in fh:
                if not linea.startswith("ATOM"):
                    continue
                try:
                    d = math.dist(
                        (float(linea[30:38]), float(linea[38:46]), float(linea[46:54])),
                        centro,
                    )
                except ValueError:
                    continue
                if d < mejor:
                    mejor = d
        if mejor > 6.0 and pdb not in conocidos:
            nuevos.append(f"{pdb} ({mejor:.1f} A)")
    assert not nuevos, (
        "cajas cuyo centro esta en el vacio, sin explicacion registrada: "
        + ", ".join(nuevos)
        + ". Comprueba si la unidad biologica hay que generarla con BIOMT."
    )
