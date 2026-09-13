"""La preparacion del receptor recorrida ENTERA, como en una maquina limpia.

Ninguna prueba ejecutaba `prepare_target` de punta a punta: todas entraban por
`_filter_pdb_content`, por `preparer_multichain` o por un `AsyncMock`. Con esa
cobertura, la funcion que prepara TODOS los receptores del producto llego a la
rama final con un `NameError` -`etiqueta_cadena`, una variable local de otra
funcion- y la suite entera siguio en verde. En esta maquina tampoco se veia:
`~/MolDesign` lleva meses de uso y sirve el `.pdbqt` de la cache antes de llegar
ahi. En una instalacion nueva no hay cache, y CADA acoplamiento moria.

La otra mitad es de procedencia. `prepare_target` escribia una copia filtrada
por cadena para el rescoring y acto seguido la volvia a leer como origen. Esa
copia no conserva los `REMARK`, asi que la unidad biologica ya no se podia
generar: los quince objetivos cuyo sitio se forma con una cadena que SOLO existe
en el ensamblaje preparaban media cavidad. Aqui no se veia porque
`data/target_library` -material de esta maquina, que NO viaja en el instalador-
adelantaba una estructura completa.

De ahi la forma de estas pruebas: se siembra el crudo depositado igual que lo
hace el instalador, sobre un almacenamiento vacio, y se mira el receptor que
sale.
"""

from __future__ import annotations

import gzip
import json
from pathlib import Path

import pytest

from services.docking import preparer
from services.docking.preparer import (
    ProteinPreparationError,
    prepare_target,
    prepared_receptor_chains,
)

RAIZ = Path(__file__).resolve().parents[2]
ESTRUCTURAS = RAIZ / "data" / "targets"
CATALOGO = RAIZ / "curated_targets.json"
BIBLIOTECA = RAIZ / "data" / "target_library"

#: 1C6X -proteasa del VIH-1-. Cabe ENTERA dentro del radio de recorte: 1510 de
#: sus 1514 atomos estan a menos de 30 A del centro. Es el caso que confundia
#: `trim_to_pocket`, cuyo «se recorto algo» vale `False` tanto cuando no hay
#: nada cerca del centro como cuando no hacia falta recortar nada.
RECEPTOR_QUE_CABE_ENTERO = "1C6X"

#: 5VA1 -receptor de glutamato metabotropico-. Su sitio se forma entre A y B, y
#: la cadena B SOLO existe en la unidad biologica: el archivo depositado trae
#: una sola. Se elige entre los quince porque es el UNICO sin copia en
#: `data/target_library`, y por tanto el unico que recorre en esta maquina el
#: mismo camino que recorreria en una instalacion limpia.
RECEPTOR_DE_ENSAMBLAJE = "5VA1"


def _catalogo(pdb_id: str) -> dict:
    for objetivo in json.loads(CATALOGO.read_text(encoding="utf-8")):
        if (objetivo.get("pdb_id") or "").upper() == pdb_id.upper():
            return objetivo
    raise AssertionError(
        f"{pdb_id} ya no esta en el catalogo. Esta prueba se quedaria sin material: "
        "elige otro objetivo con `site_chains` que solo existan en el ensamblaje y "
        "actualiza RECEPTOR_DE_ENSAMBLAJE."
    )


def _sembrar_como_el_instalador(pdb_id: str, destino: Path) -> None:
    """Escribe `targets/<ID>/raw.pdb` desde el `.pdb.gz` empaquetado.

    Es exactamente lo que hace `semilla_estructuras` al arrancar. Se replica en
    vez de llamarla porque sembrar las 407 descomprimiria ~2 GB por prueba.
    """
    comprimido = ESTRUCTURAS / f"{pdb_id}.pdb.gz"
    assert comprimido.is_file(), (
        f"{comprimido} no existe. El instalador empaqueta esta estructura; si ha "
        "desaparecido del arbol, el objetivo no llegaria al usuario."
    )
    crudo = destino / "targets" / pdb_id.upper() / "raw.pdb"
    crudo.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(comprimido, "rt", encoding="utf-8", errors="replace") as entrada:
        crudo.write_text(entrada.read(), encoding="utf-8")


@pytest.fixture
def instalacion_limpia(tmp_path, monkeypatch) -> Path:
    """Un almacenamiento de usuario recien creado, sin cache de nada.

    Se parchean LOS DOS `settings`. `preparer` y `local_storage` hacen cada uno
    su `get_settings()` al importarse, y en la suite completa no siempre son el
    mismo objeto: `test_app_mode` limpia el `lru_cache` y `test_api` asigna
    sobre el singleton. Parcheando solo el de `preparer`, la escritura se iba a
    `~/MolDesign`: esta prueba pasaba en solitario y, dentro de la suite,
    preparaba el receptor sobre los datos reales del usuario.

    Por eso la ultima linea comprueba donde va a escribir en vez de suponerlo.
    """
    from utils import local_storage

    datos = tmp_path / "MolDesign" / "data"
    datos.mkdir(parents=True)
    temporal = tmp_path / "vina"
    temporal.mkdir()
    for ajustes in (preparer.settings, local_storage.settings):
        monkeypatch.setattr(ajustes, "local_data_dir", str(datos))
        monkeypatch.setattr(ajustes, "vina_temp_dir", str(temporal))
    assert local_storage.data_dir() == datos, (
        "el almacenamiento no quedo aislado; esta prueba escribiria fuera del tmp"
    )
    return datos


def test_el_objetivo_de_referencia_sigue_fuera_de_la_biblioteca_local():
    """Si alguien copia 5VA1 a `data/target_library`, estas pruebas dejan de medir.

    La biblioteca no viaja en el instalador -`bundle_helper` copia
    `data/targets`, no `data/target_library`-, asi que una copia ahi adelanta
    una estructura completa que el usuario nunca tendra, y el camino de la
    instalacion limpia dejaria de recorrerse SIN QUE NADIE LO NOTE.
    """
    copias = list(BIBLIOTECA.glob(f"**/{RECEPTOR_DE_ENSAMBLAJE}.pdb")) if BIBLIOTECA.is_dir() else []
    assert not copias, (
        f"{RECEPTOR_DE_ENSAMBLAJE} tiene copia en {copias}. Esa ruta gana en "
        "`get_target_pdb_path` y enmascara el camino que se quiere probar: elige "
        "otro objetivo y actualiza RECEPTOR_DE_ENSAMBLAJE."
    )


@pytest.mark.asyncio
async def test_el_receptor_conserva_las_cadenas_del_sitio(instalacion_limpia):
    """El recorrido completo, con Meeko de verdad, sobre un disco vacio.

    Comprueba las dos cosas a la vez: que la funcion LLEGA AL FINAL -el
    `NameError` moria justo antes de guardar el `.pdbqt`- y que el receptor
    guardado contiene las dos cadenas que forman el sitio.
    """
    objetivo = _catalogo(RECEPTOR_DE_ENSAMBLAJE)
    cadenas_del_sitio = set(objetivo["site_chains"])
    assert len(cadenas_del_sitio) > 1, "el objetivo de referencia dejo de ser multicadena"

    _sembrar_como_el_instalador(RECEPTOR_DE_ENSAMBLAJE, instalacion_limpia)

    ruta = await prepare_target(
        pdb_id=RECEPTOR_DE_ENSAMBLAJE,
        chain_id=objetivo["chain"],
        center=(objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"]),
        size=(objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"]),
        site_chains=objetivo["site_chains"],
    )

    pdbqt = (instalacion_limpia / ruta).read_text(encoding="utf-8", errors="replace")
    assert prepared_receptor_chains(pdbqt) == cadenas_del_sitio

    # Que la cadena aparezca no basta: antes del arreglo el filtro pedia A+B
    # sobre un archivo con solo A, y el resultado -la cadena A entera- tambien
    # habria pasado un `in`. Lo que falla si el ensamblaje no se genera es que
    # la segunda cadena no aporte ni un atomo.
    atomos: dict[str, int] = {}
    for linea in pdbqt.splitlines():
        if linea.startswith(("ATOM", "HETATM")) and len(linea) > 21:
            atomos[linea[21]] = atomos.get(linea[21], 0) + 1
    assert all(atomos.get(cadena, 0) > 100 for cadena in cadenas_del_sitio), atomos


@pytest.mark.asyncio
async def test_la_copia_para_el_rescoring_sale_del_ensamblaje(instalacion_limpia):
    """La copia que consume el rescoring describe el receptor que se acopla.

    Se escribia desde el archivo depositado, asi que para estos quince le
    faltaba una cadena entera: el rescoring habria puntuado sobre media
    cavidad mientras el docking usaba la completa. Una segunda opinion sobre
    otro receptor no es una segunda opinion.
    """
    objetivo = _catalogo(RECEPTOR_DE_ENSAMBLAJE)
    _sembrar_como_el_instalador(RECEPTOR_DE_ENSAMBLAJE, instalacion_limpia)

    await prepare_target(
        pdb_id=RECEPTOR_DE_ENSAMBLAJE,
        chain_id=objetivo["chain"],
        center=(objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"]),
        size=(objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"]),
        site_chains=objetivo["site_chains"],
    )

    compartido = instalacion_limpia / "targets" / f"{RECEPTOR_DE_ENSAMBLAJE}.pdb"
    assert compartido.is_file(), "la copia para rescoring no se escribio donde el usuario manda"
    assert prepared_receptor_chains(
        compartido.read_text(encoding="utf-8", errors="replace")
    ) == set(objetivo["site_chains"])


@pytest.mark.asyncio
async def test_un_receptor_que_cabe_entero_en_el_radio_se_prepara(instalacion_limpia):
    """No recortar nada no es un fallo, y se confundia con uno.

    `trim_to_pocket` devuelve `n_kept > 0 and n_kept < n_total`, asi que dice
    `False` en dos situaciones opuestas: cuando no hay ningun residuo cerca del
    centro -defecto real- y cuando el receptor entero cabe dentro del radio. La
    proteasa del VIH-1 es el segundo caso, y moria con un mensaje que acusaba a
    su caja de no corresponder a la estructura: el centro esta exactamente sobre
    el centroide de su ligando co-cristalizado, con la cadena mas cercana a 4 A.
    """
    objetivo = _catalogo(RECEPTOR_QUE_CABE_ENTERO)
    assert len(set(objetivo["site_chains"])) > 1, "dejo de ser un sitio de interfaz"
    _sembrar_como_el_instalador(RECEPTOR_QUE_CABE_ENTERO, instalacion_limpia)

    ruta = await prepare_target(
        pdb_id=RECEPTOR_QUE_CABE_ENTERO,
        chain_id=objetivo["chain"],
        center=(objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"]),
        size=(objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"]),
        site_chains=objetivo["site_chains"],
    )

    pdbqt = (instalacion_limpia / ruta).read_text(encoding="utf-8", errors="replace")
    assert prepared_receptor_chains(pdbqt) == set(objetivo["site_chains"])


@pytest.mark.asyncio
async def test_sin_siembra_todavia_no_hace_falta_la_red(instalacion_limpia, monkeypatch):
    """El hueco entre abrir la aplicacion y terminar de sembrar las 407.

    La siembra del arranque corre en un hilo de fondo y tarda decenas de
    segundos. Medido en el gate de Evaluacion sobre el runtime staged: **57 de
    407** sembradas cuando llego la primera peticion. En ese hueco, el control
    de la fuente del receptor bloqueaba —pidiendo importar un receptor que ya
    venia en el instalador— y la preparacion se iba al RCSB, o sea a la RED, en
    un producto que se vende como offline.

    Aqui NO se siembra nada a proposito, y descargar levanta.
    """
    from utils import file_handlers

    async def _no_hay_red(*_args, **_kwargs):
        raise AssertionError("la preparacion pidio red para un receptor empaquetado")

    monkeypatch.setattr(preparer, "download_pdb_from_rcsb", _no_hay_red)
    monkeypatch.setattr(file_handlers, "download_pdb_from_rcsb", _no_hay_red, raising=False)

    # 5VA1 y no 1C6X: el segundo tiene copia en `data/target_library` de esta
    # maquina, que resolveria la fuente sin pasar por la siembra y dejaria la
    # prueba pasando por la razon equivocada.
    objetivo = _catalogo(RECEPTOR_DE_ENSAMBLAJE)
    ruta = await prepare_target(
        pdb_id=RECEPTOR_DE_ENSAMBLAJE,
        chain_id=objetivo["chain"],
        center=(objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"]),
        size=(objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"]),
        site_chains=objetivo["site_chains"],
    )
    assert (instalacion_limpia / ruta).is_file()
    assert (instalacion_limpia / "targets" / RECEPTOR_DE_ENSAMBLAJE / "raw.pdb").is_file(), (
        "la estructura empaquetada no se materializo a peticion"
    )


def test_el_preflight_materializa_la_estructura_empaquetada(instalacion_limpia):
    """El mismo hueco, visto desde la comprobacion previa.

    `_source_pdb_path` devolvia `None` y el control salia `bloquea`. El texto
    que veia el investigador —«importa o prepara el receptor»— describia un
    trabajo que no le tocaba hacer.
    """
    from services.docking import preflight

    assert preflight._source_pdb_path(RECEPTOR_DE_ENSAMBLAJE) is not None


@pytest.mark.asyncio
async def test_un_sitio_que_no_se_puede_formar_se_detiene(instalacion_limpia):
    """Falta una cadena del sitio: se para, no se acopla contra media cavidad.

    Es el modo de fallo C del doc 71, y no dispara ninguna alarma por si solo
    porque Vina devuelve una afinidad con la misma cara que una buena. Antes
    solo quedaba una linea de log diciendo que las cadenas conservadas no eran
    las pedidas.
    """
    objetivo = _catalogo(RECEPTOR_DE_ENSAMBLAJE)
    _sembrar_como_el_instalador(RECEPTOR_DE_ENSAMBLAJE, instalacion_limpia)

    with pytest.raises(ProteinPreparationError) as excinfo:
        await prepare_target(
            pdb_id=RECEPTOR_DE_ENSAMBLAJE,
            chain_id=objetivo["chain"],
            center=(objetivo["grid_center_x"], objetivo["grid_center_y"], objetivo["grid_center_z"]),
            size=(objetivo["grid_size_x"], objetivo["grid_size_y"], objetivo["grid_size_z"]),
            site_chains=[objetivo["chain"], "Z"],
        )
    assert excinfo.value.step == "site_chains_missing"
