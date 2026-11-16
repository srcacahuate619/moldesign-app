"""La tabla de reglas de dimorphite-dl se carga una sola vez, aunque varios ligandos arranquen a la vez (hERG, revisión final).

dimorphite-dl 2.0.2 publica `PKaData._instance` antes de cargar las reglas: un segundo hilo que entra en frío recibe la
tabla vacía y `protonate_smiles` devuelve la molécula SIN protonar, sin excepción. `_construir_conformero` corre en el
pool de hilos, así que dos ligandos concurrentes de un lote lo alcanzan. Medido: cisapride, droperidol y haloperidol
salían con 1 candidato (2, 4 y 2 en serie) en 5 de 5 arranques en frío.

Cada modo corre en un proceso nuevo, porque la tabla es un singleton del proceso. El control negativo anula
`preparar_dimorphite` y exige que la carrera reaparezca: sin él, un guardián que nunca falla no demostraría nada.
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

SMILES = {
    "cisapride": "COc1cc(N)c(Cl)cc1C(=O)NC1CCN(CCCOc2ccc(F)cc2)CC1OC",
    "droperidol": "O=C(CCCN1CC=C(n2c(=O)[nH]c3ccccc32)CC1)c1ccc(F)cc1",
    "haloperidol": "O=C(CCCN1CCC(O)(c2ccc(Cl)cc2)CC1)c1ccc(F)cc1",
    "propranolol": "CC(C)NCC(O)COc1cccc2ccccc12",
}

_SONDA = r"""
import json, sys, threading
sys.path.insert(0, sys.argv[1])
modo = sys.argv[2]
smiles = json.loads(sys.argv[3])

import dimorphite_dl
from dimorphite_dl.protonate.data import PKaData
import chem.conformer as conformer

assert PKaData._instance is None, "la tabla ya estaba cargada al entrar"
if modo == "hilos_sin_preparar":
    conformer.preparar_dimorphite = lambda: 0   # el control negativo: sin el candado ni la carga previa

# Los hilos llegan juntos a la enumeración, que es donde está la carrera.
barrera = threading.Barrier(1 if modo == "serie" else len(smiles))
original = dimorphite_dl.protonate_smiles
def con_barrera(*a, **k):
    barrera.wait(timeout=60)
    return original(*a, **k)
dimorphite_dl.protonate_smiles = con_barrera

salida, errores = {}, []
def uno(nombre, smi):
    try:
        r = conformer._construir_conformero(smi, 7.4)
        salida[nombre] = r["estado_del_ligando"]["protonacion"]["alternativas"]
    except BaseException as exc:
        errores.append(f"{nombre}: {type(exc).__name__}: {exc}")

if modo == "serie":
    for n, s in smiles.items():
        uno(n, s)
else:
    hilos = [threading.Thread(target=uno, args=(n, s)) for n, s in smiles.items()]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
print(json.dumps({"alternativas": salida, "errores": errores, "reglas": len(PKaData._data)}))
"""


def _en_un_proceso(modo: str) -> dict:
    entorno = {**os.environ, "PYTHONIOENCODING": "utf-8", "MOLDESIGN_TESTING": "1"}
    hecho = subprocess.run(
        [sys.executable, "-c", _SONDA, str(BACKEND), modo, json.dumps(SMILES)],
        capture_output=True, text=True, encoding="utf-8", env=entorno, timeout=600,
    )
    assert hecho.returncode == 0, hecho.stderr[-2000:]
    return json.loads(hecho.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def serie() -> dict:
    resultado = _en_un_proceso("serie")
    assert not resultado["errores"], resultado["errores"]
    assert resultado["reglas"] > 0
    return resultado


def test_el_arranque_en_frio_con_hilos_enumera_lo_mismo_que_en_serie(serie):
    en_hilos = _en_un_proceso("hilos")
    assert not en_hilos["errores"], en_hilos["errores"]
    assert en_hilos["alternativas"] == serie["alternativas"]
    assert en_hilos["reglas"] == serie["reglas"]
    # La serie no es trivial: al menos un fármaco tiene varios microestados que perder.
    assert max(serie["alternativas"].values()) > 1


def test_control_negativo_sin_preparar_la_tabla_la_carrera_reaparece(serie):
    sin_preparar = _en_un_proceso("hilos_sin_preparar")
    assert not sin_preparar["errores"], sin_preparar["errores"]
    assert sin_preparar["alternativas"] != serie["alternativas"], (
        "la carrera de dimorphite-dl ya no se reproduce: este guardián dejó de ver el defecto")


def test_una_tabla_publicada_y_vacia_se_rehace():
    from dimorphite_dl.protonate.data import PKaData

    from chem.conformer import preparar_dimorphite

    PKaData()
    reglas = len(PKaData._data)
    assert reglas > 0
    guardada, instancia = PKaData._data, PKaData._instance
    try:
        PKaData._data = []          # el estado que deja una carga que falló a medias
        assert preparar_dimorphite() == reglas
    finally:
        PKaData._data, PKaData._instance = guardada, instancia
