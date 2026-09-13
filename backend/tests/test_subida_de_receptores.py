"""Subir un receptor: el modo automatico y el manual, sobre estructuras reales.

El catalogo curado esta auditado receptor por receptor, pero el usuario puede
traer el suyo por dos caminos, y ninguno de los dos estaba comprobado de punta a
punta:

    AUTOMATICO   el usuario teclea un PDB ID y el sistema decide el sitio.
                 `discover_pocket_from_pdb` detecta el ligando co-cristalizado
                 o, si no lo hay, cae a MolPocket sobre la estructura apo.
    MANUAL       el usuario sube un .pdb con su caja. El sistema no decide el
                 sitio, pero SI tiene que medir que cadenas lo forman.

Lo que estas pruebas fijan es el contrato de producto: el automatico acierta en
al menos el 95% de las estructuras, y el manual no deja un receptor peor anotado
que uno del catalogo.

MEDIDO SOBRE LAS 385 ESTRUCTURAS LOCALES: 385 de 385 (100%), de las cuales 90
pasaron por la rama apo de MolPocket. La prueba corre una muestra sembrada para
no tardar media hora; el barrido completo esta en el doc 72.
"""

from __future__ import annotations

import gzip
import json
import random
from pathlib import Path

import pytest

from services.targets.sitio_de_union import anotar_sitio
from utils.scientific import audit_scientific_quality
from utils.structural import discover_pocket_from_pdb

RAIZ = Path(__file__).resolve().parents[2]
ESTRUCTURAS = RAIZ / "data" / "targets"
CATALOGO = RAIZ / "curated_targets.json"

#: El contrato: el modo automatico no puede fallar mas de uno de cada veinte.
UMBRAL_DE_EXITO = 0.95

#: Cuantas estructuras. Con 24 la prueba tarda ~35 s (1,4 s por estructura, de
#: las cuales las apo cargan con la teselacion de Delaunay de MolPocket).
TAMANO_DE_LA_MUESTRA = 24

#: Sembrada, para que un fallo sea reproducible y no dependa del dia.
SEMILLA = 42

#: El receptor de interfaz de referencia. 5COP es la proteasa del VIH salvaje:
#: sitio en la interfaz del dimero, con ligando co-cristalizado. Antes era 1TW7,
#: retirado del catalogo por tener los hotspots a 16-25 A del sitio.
REFERENCIA = "5COP"


def _catalogo() -> list[dict]:
    if not CATALOGO.is_file():
        pytest.skip("falta curated_targets.json")
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def _muestra() -> list[dict]:
    objetivos = [t for t in _catalogo()
                 if (ESTRUCTURAS / f"{t['pdb_id'].upper()}.pdb.gz").is_file()]
    if len(objetivos) < TAMANO_DE_LA_MUESTRA:
        pytest.skip("no hay estructuras locales suficientes")
    random.Random(SEMILLA).shuffle(objetivos)
    return objetivos[:TAMANO_DE_LA_MUESTRA]


def _leer(pdb_id: str) -> str:
    with gzip.open(ESTRUCTURAS / f"{pdb_id.upper()}.pdb.gz", "rt",
                   encoding="utf-8", errors="replace") as fh:
        return fh.read()


@pytest.mark.slow
def test_el_modo_automatico_acierta_al_menos_en_el_95_por_ciento():
    """El contrato de producto del modo automatico.

    Si esto baja del 95%, el usuario que teclea un PDB ID acaba en el modo
    manual mas de una vez de cada veinte, que es donde tiene que poner de su
    parte lo que el producto promete quitarle.
    """
    muestra = _muestra()
    fallos = []
    for objetivo in muestra:
        pdb = objetivo["pdb_id"].upper()
        try:
            r = discover_pocket_from_pdb(_leer(pdb), objetivo.get("chain") or "A")
        except Exception as exc:  # noqa: BLE001 - cualquier excepcion es un fallo
            fallos.append(f"{pdb}: {type(exc).__name__}: {exc}")
            continue
        if not r.get("success"):
            fallos.append(f"{pdb}: {r.get('error')}")

    exito = (len(muestra) - len(fallos)) / len(muestra)
    assert exito >= UMBRAL_DE_EXITO, (
        f"el modo automatico acierta en el {exito*100:.0f}% de {len(muestra)} estructuras, "
        f"por debajo del {UMBRAL_DE_EXITO*100:.0f}% que promete el producto. "
        f"Fallos: {'; '.join(fallos)}"
    )


@pytest.mark.slow
def test_el_automatico_resuelve_tambien_las_estructuras_apo():
    """Sin la rama de MolPocket, un cuarto del catalogo no se podria ingerir.

    De las 385 estructuras locales, 90 no tienen ligando co-cristalizado. Si el
    fallback apo se rompiera, el modo automatico caeria del 100% al 77% sin que
    ninguna prueba de la ruta holo se enterase.
    """
    apo = 0
    for objetivo in _muestra():
        r = discover_pocket_from_pdb(_leer(objetivo["pdb_id"]), objetivo.get("chain") or "A")
        if r.get("apo_molpocket"):
            apo += 1
            assert r.get("success"), f"{objetivo['pdb_id']}: la rama apo devolvio fallo"
            assert r.get("grid_center"), f"{objetivo['pdb_id']}: la rama apo no dio centro"
    assert apo > 0, "la muestra no incluyo ninguna estructura apo; sube el tamano o la semilla"


def test_el_modo_manual_anota_el_sitio_igual_que_el_catalogo():
    """Un receptor subido a mano no puede quedar peor anotado que uno curado.

    Es el caso de la proteasa del VIH: si un usuario la sube con su caja, el
    sistema tiene que ver que el sitio lo forman DOS cadenas. Sin eso,
    `prepare_target` conserva una y el ligando acopla contra media cavidad, que
    es el modo de fallo C del doc 71.
    """
    objetivos = {t["pdb_id"].upper(): t for t in _catalogo()}
    # Si desaparece se FALLA, no se salta: un skip apagaria la unica prueba del
    # camino manual sin dejar rastro.
    assert REFERENCIA in objetivos, (
        f"{REFERENCIA} ya no esta en el catalogo y esta prueba se quedaria sin "
        "material: elige otro receptor de interfaz"
    )
    t = objetivos[REFERENCIA]

    sitio = anotar_sitio(
        _leer(REFERENCIA),
        (t["grid_center_x"], t["grid_center_y"], t["grid_center_z"]),
        (t["grid_size_x"], t["grid_size_y"], t["grid_size_z"]),
    )
    assert sitio is not None
    assert len(sitio["site_chains"]) == 2, (
        f"el sitio lo forman dos cadenas y se detectaron {sitio['site_chains']}"
    )
    # Y coincide con lo que el catalogo ya declara: una sola implementacion.
    assert sitio["site_chains"] == t["site_chains"]
    assert sitio["site_chain_atoms"] == t["site_chain_atoms"]
    assert sitio["site_evidence"] == t["site_evidence"]


def test_el_modo_manual_no_inventa_sitio_donde_no_hay_receptor():
    """Con una caja fuera de la proteina se devuelve None, no un sitio vacio.

    Devolver `{"site_chains": []}` haria que la tarjeta dijese «Sitio sin medir»
    -que es cierto- pero tambien dejaria pasar en silencio una caja absurda.
    """
    assert anotar_sitio(_leer(REFERENCIA), (999.0, 999.0, 999.0), (25.0, 25.0, 25.0)) is None


# ── Doc 71, defecto C1 ───────────────────────────────────────────────────────

CLAIMS_PROHIBIDAS = ("micromolar", "nanomolar", "in vivo", "in vitro", "IC50", "Kd", "Ki ")


@pytest.mark.parametrize("afinidad", [-2.0, -5.9, -6.5, -9.0, -12.0])
def test_el_informe_no_traduce_una_afinidad_de_vina_a_potencia(afinidad):
    """C1, el defecto critico del doc 71.

    El informe explica que una afinidad de Vina NO es energia libre, y dos
    parrafos despues afirmaba «rango micromolar alto, probablemente insuficiente
    para actividad farmacologica in vivo». Son dos saltos que su propia premisa
    prohibe: de un score a una constante de disociacion, y de esa constante a la
    actividad en un organismo.

    En un producto cuya propuesta es saber cuando NO confiar, esto pesa mas que
    cualquier defecto de codigo: es el informe contradiciendo su contrato.
    """
    avisos = audit_scientific_quality(
        affinity_kcal=afinidad, heavy_atom_count=25, log_p=2.5,
        docking_poses=[], hotspots=[], hotspots_hit=[],
    )
    texto = " ".join(avisos)
    encontradas = [c for c in CLAIMS_PROHIBIDAS if c.lower() in texto.lower()]
    assert not encontradas, (
        f"el informe traduce el score de Vina a {encontradas} con afinidad {afinidad}: "
        f"{texto}"
    )


def test_el_informe_si_dice_cuando_el_score_es_debil():
    """Borrar la inferencia no puede costar la senal: el aviso sigue existiendo,
    pero acotado a la escala en la que ese numero significa algo."""
    avisos = audit_scientific_quality(
        affinity_kcal=-5.2, heavy_atom_count=25, log_p=2.5,
        docking_poses=[], hotspots=[], hotspots_hit=[],
    )
    debil = [a for a in avisos if "escala de Vina" in a]
    assert debil, f"no se avisa de un score debil: {avisos}"
    assert "ordena candidatos" in debil[0]


def test_no_hay_guiones_tipograficos_en_los_avisos():
    """Van al PDF, y el doc 71 (defecto D2) ya registra glifos que se extraen
    como cuadrados. Un `U+2212` en vez de un guion normal es la misma familia de
    problema, y perjudica busqueda y copiado."""
    avisos = audit_scientific_quality(
        affinity_kcal=-5.2, heavy_atom_count=25, log_p=2.5,
        docking_poses=[], hotspots=[], hotspots_hit=[],
    )
    for aviso in avisos:
        raros = {c for c in aviso if c in "−–—"}
        assert not raros, f"caracteres problematicos {raros} en: {aviso}"
