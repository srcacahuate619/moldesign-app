"""CLAVE-09: la protonación del ligando es reproducible entre procesos, y lo deja dicho.

`dimorphite_dl.protonate_smiles` devolvía la lista en otro orden en cada proceso y
`[0]` hacía irreproducible el `smiles_hash` (corregido el 2026-09-04 con
`elegir_microestado`). Para un paquete que un tercero tiene que reconstruir
(FEP-05/06) no basta con elegir bien: la corrida tiene que registrar con qué versión
y parámetros enumeró, la huella del conjunto de candidatos y si se recortó.

El guardián repite la enumeración y la elección en procesos con distinto
`PYTHONHASHSEED` —la fuente de azar que queda: dimorphite itera `set()` de cadenas y
recorta a `max_variants`— y exige el mismo conjunto y el mismo elegido.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("dimorphite_dl")
pytest.importorskip("rdkit")

BACKEND = Path(__file__).resolve().parents[1]

OCTAHISTIDINA = "N[C@@H](Cc1c[nH]cn1)C(=O)" * 8 + "O"
CASOS = {
    "lisina": "NCCCCC(N)C(=O)O",
    "histidina": "N[C@@H](Cc1c[nH]cn1)C(=O)O",
    "propranolol": "CC(C)NCC(O)COc1cccc2ccccc12",
    # Llega al tope de 128 variantes: es donde el recorte podría depender del orden.
    "octahistidina": OCTAHISTIDINA,
}

_SONDA = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import dimorphite_dl
from chem.conformer import (MAX_VARIANTES_DIMORPHITE, PRECISION_DIMORPHITE,
                            reproduccion_de_la_protonacion)
from chem.ionizacion import elegir_microestado
salida = {}
for nombre, smi in json.loads(sys.argv[2]).items():
    lista = dimorphite_dl.protonate_smiles(smi, ph_min=7.4, ph_max=7.4,
                                           precision=PRECISION_DIMORPHITE,
                                           max_variants=MAX_VARIANTES_DIMORPHITE)
    elegido, _ = elegir_microestado(smi, list(lista), 7.4)
    registro = reproduccion_de_la_protonacion(list(lista), 7.4, dimorphite_dl.__version__)
    salida[nombre] = {"elegido": elegido, **registro}
print(json.dumps(salida))
"""


def _en_un_proceso(semilla: str) -> dict:
    entorno = {**os.environ, "PYTHONHASHSEED": semilla, "PYTHONIOENCODING": "utf-8"}
    hecho = subprocess.run(
        [sys.executable, "-c", _SONDA, str(BACKEND), json.dumps(CASOS)],
        capture_output=True, text=True, encoding="utf-8", env=entorno, timeout=600,
    )
    assert hecho.returncode == 0, hecho.stderr[-2000:]
    return json.loads(hecho.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def tres_procesos():
    return [_en_un_proceso(semilla) for semilla in ("0", "1", "4242")]


@pytest.mark.parametrize("caso", sorted(CASOS))
def test_mismo_conjunto_y_mismo_elegido_en_todos_los_procesos(tres_procesos, caso):
    elegidos = {p[caso]["elegido"] for p in tres_procesos}
    conjuntos = {p[caso]["candidatos_sha256"] for p in tres_procesos}
    assert len(elegidos) == 1, elegidos
    assert len(conjuntos) == 1, conjuntos


def test_el_registro_dice_version_parametros_y_recorte(tres_procesos):
    registro = tres_procesos[0]["lisina"]
    assert registro["version_motor"]
    assert registro["parametros"] == {"ph_min": 7.4, "ph_max": 7.4, "precision": 1.0,
                                      "max_variants": 128}
    assert registro["recortado"] is False
    assert tres_procesos[0]["octahistidina"]["recortado"] is True


def test_el_recorte_se_avisa():
    from services.docking.ligand_state_warnings import avisos_estado_ligando
    from services.avisos import CODIGOS_DE_AVISO
    from core.i18n_plantillas import traducir

    avisos = avisos_estado_ligando({"protonacion": {"recortado": True,
                                                    "parametros": {"max_variants": 128}}})
    (recorte,) = [a for a in avisos if a["codigo"] == "MICROESTADOS_RECORTADOS"]
    assert "MICROESTADOS_RECORTADOS" in CODIGOS_DE_AVISO
    assert recorte["severidad"] == "precaucion"
    assert traducir(recorte["mensaje"], "en").startswith("dimorphite-dl returned 128 microstates")
    assert not [a for a in avisos_estado_ligando({"protonacion": {"recortado": False}})
                if a["codigo"] == "MICROESTADOS_RECORTADOS"]


def test_la_huella_no_depende_del_orden_ni_de_la_grafia():
    from chem.conformer import reproduccion_de_la_protonacion
    a = reproduccion_de_la_protonacion(["C[NH3+]", "CN"], 7.4, "x")
    b = reproduccion_de_la_protonacion(["NC", "[NH3+]C"], 7.4, "x")
    assert a["candidatos_sha256"] == b["candidatos_sha256"]


def test_el_guardian_ve_una_eleccion_por_posicion():
    """Autotest: si se volviera a elegir `lista[0]`, el guardián lo vería.

    El orden de dimorphite cambia entre semillas (medido el 2026-10-20: la lisina
    da tres `[0]` distintos con 0, 1 y 4242). Si dejara de cambiar, esta prueba
    falla y avisa de que el guardián de arriba ya no demuestra nada.
    """
    sonda = _SONDA.replace("elegido, _ = elegir_microestado(smi, list(lista), 7.4)",
                           "elegido = lista[0]")
    assert sonda != _SONDA
    primeros = set()
    for semilla in ("0", "1", "4242"):
        entorno = {**os.environ, "PYTHONHASHSEED": semilla, "PYTHONIOENCODING": "utf-8"}
        hecho = subprocess.run(
            [sys.executable, "-c", sonda, str(BACKEND), json.dumps({"lisina": CASOS["lisina"]})],
            capture_output=True, text=True, encoding="utf-8", env=entorno, timeout=300,
        )
        assert hecho.returncode == 0, hecho.stderr[-2000:]
        primeros.add(json.loads(hecho.stdout.strip().splitlines()[-1])["lisina"]["elegido"])
    assert len(primeros) > 1, "el orden de dimorphite ya no varía: el guardián no ve nada"


def _estado(recortado: bool) -> dict:
    return {"protonacion": {
        "aplicada": True, "ph": 7.4, "alternativas": 128 if recortado else 4,
        "seleccion": {"criterio": "cargas_esperadas_ph_7.4"},
        "version_motor": "2.0.2",
        "parametros": {"ph_min": 7.4, "ph_max": 7.4, "precision": 1.0, "max_variants": 128},
        "candidatos_sha256": "ab" * 32, "recortado": recortado,
    }}


@pytest.mark.parametrize("recortado", [False, True])
def test_el_dossier_lleva_la_enumeracion_y_sale_en_ingles(recortado):
    from core.i18n_plantillas import traducir
    from services.dossier.model import campos_del_estado_del_ligando
    from services.dossier.taxonomy import Estado

    campo = dict(campos_del_estado_del_ligando(_estado(recortado)))["enumeracion"]
    assert campo.texto.startswith("dimorphite-dl 2.0.2 · pH 7.4–7.4 · precisión 1 · máximo 128 · huella abababababab")
    assert (campo.estado is Estado.REVISAR) is recortado
    assert traducir(campo.texto, "en").startswith("dimorphite-dl 2.0.2 · pH 7.4–7.4 · precision 1 · maximum 128")
    assert traducir(campo.etiqueta, "en") == "Microstate enumeration"
    if recortado:
        assert traducir(campo.razon, "en") != campo.razon


def test_una_corrida_anterior_no_inventa_la_enumeracion():
    from services.dossier.model import campos_del_estado_del_ligando
    estado = _estado(False)
    for clave in ("parametros", "candidatos_sha256", "version_motor", "recortado"):
        estado["protonacion"].pop(clave)
    assert "enumeracion" not in dict(campos_del_estado_del_ligando(estado))
