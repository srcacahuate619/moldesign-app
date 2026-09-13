"""
La especie que se acopla no siempre es la que el usuario escribió.

`generate_conformer` hace dos sustituciones antes de generar coordenadas:

  1. `TautomerEnumerator().Canonicalize()` — elige UN tautómero entre los que
     enumera, con la función de puntuación de RDKit, y descarta el resto.
  2. `dimorphite_dl.protonate_smiles(pH 7.4)` — devuelve una LISTA de estados
     de protonación y el código se queda con el primero.

Las dos son defendibles. Ninguna se declaraba. Medido con aspirina sobre el
intérprete empaquetado:

    entrada    CC(=O)Oc1ccccc1C(=O)O
    acoplada   CC(=O)Oc1ccccc1C(=O)[O-]      2 tautómeros enumerados

Es decir, se acopla una especie con carga −1 que nadie escribió. Y el hash de
entrada —el que sella la corrida— se recalcula sobre la forma transformada,
así que la huella describe la molécula sustituida mientras el caso enseña la
del usuario.

Además, las dos operaciones van dentro de un `except` que sólo escribe en el
log: sin `dimorphite_dl` instalado la corrida sigue con la forma neutra, y dos
equipos distintos acoplan moléculas distintas a partir del mismo SMILES.
"""

import asyncio

import pytest

from chem.conformer import generate_conformer

ASPIRINA = "CC(=O)Oc1ccccc1C(=O)O"
CAFEINA = "Cn1cnc2c1c(=O)n(C)c(=O)n2C"


@pytest.fixture(scope="module")
def estado_aspirina():
    return asyncio.run(generate_conformer(ASPIRINA))["estado_del_ligando"]


def test_se_registra_lo_que_entro_y_lo_que_se_acopla(estado_aspirina):
    assert estado_aspirina["smiles_entrada"] == ASPIRINA
    assert estado_aspirina["smiles_acoplado"]
    # El registro existe precisamente porque pueden diferir.
    assert "cambio_respecto_a_la_entrada" in estado_aspirina


def test_la_aspirina_se_acopla_desprotonada(estado_aspirina):
    """El caso concreto que destapó el hueco."""
    assert estado_aspirina["cambio_respecto_a_la_entrada"] is True
    assert "[O-]" in estado_aspirina["smiles_acoplado"], (
        "a pH 7.4 el carboxilo está ionizado; lo que importa es que se DIGA"
    )


def test_se_cuentan_las_alternativas_descartadas(estado_aspirina):
    """«Tautómero canónico» suena a que sólo había uno. Había dos."""
    taut = estado_aspirina["tautomeria"]
    assert taut["aplicada"] is True
    assert taut["motor"].startswith("RDKit")
    assert taut["alternativas"] is not None and taut["alternativas"] >= 1

    prot = estado_aspirina["protonacion"]
    if prot["aplicada"]:
        assert prot["ph"] == 7.4
        assert prot["motor"] == "dimorphite-dl"
        assert prot["alternativas"] is not None


def test_una_molecula_sin_grupos_ionizables_no_cambia():
    """La cafeína no tiene nada que protonar a pH 7.4: no debe declararse cambio."""
    estado = asyncio.run(generate_conformer(CAFEINA))["estado_del_ligando"]
    assert estado["smiles_entrada"] == estado["smiles_acoplado"]
    assert estado["cambio_respecto_a_la_entrada"] is False


def test_si_un_paso_no_corre_se_declara_el_motivo(monkeypatch):
    """Sin dimorphite-dl la corrida sigue con la forma neutra. Eso se dice."""
    import builtins

    real_import = builtins.__import__

    def sin_dimorphite(nombre, *args, **kwargs):
        if nombre == "dimorphite_dl":
            raise ImportError("simulado: no instalado")
        return real_import(nombre, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sin_dimorphite)
    estado = asyncio.run(generate_conformer(ASPIRINA))["estado_del_ligando"]

    assert estado["protonacion"]["aplicada"] is False
    assert "no está instalado" in estado["protonacion"]["motivo"]
    # Y la especie acoplada es la neutra, no la ionizada.
    assert "[O-]" not in estado["smiles_acoplado"]
