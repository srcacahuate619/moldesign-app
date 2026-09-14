"""El pH deja de estar escrito a mano, y eso no puede cambiar lo de siempre.

═══════════════════════════════════════════════════════════════════════════
POR QUÉ ESTE ARCHIVO
═══════════════════════════════════════════════════════════════════════════

Exponer el pH al usuario tenía una trampa que no se ve leyendo un solo archivo:
`dimorphite_dl` enumeraba los microestados al pH pedido y `elegir_microestado`
escogía entre ellos el más parecido al que se espera a **7.4**, porque
`cargas_esperadas_a_ph_74` llevaba el 7.4 en el nombre y en el cuerpo. Con el
pH fijo eso era consistente; en cuanto se puede mover, deja de serlo, y el
resultado sería peor que no ofrecer el parámetro: una especie elegida con la
predicción del pH equivocado, sin nada en pantalla que lo dijera.

Lo que estas pruebas fijan:

1. **El defecto no cambia.** Sin decir nada se acopla exactamente la misma
   especie y sale el mismo `smiles_hash` que antes de que el pH existiera.
   Si esto se rompe, todas las corridas anteriores dejan de ser comparables.

2. **El pH manda de verdad.** Un ácido entra neutro a pH bajo y como anión a
   pH fisiológico; una amina, al revés.

3. **El hash sigue a la especie.** Dos pH que producen moléculas distintas NO
   pueden compartir entrada de caché de acoplamiento: el hash se recalcula
   sobre el SMILES ya protonado, así que esto es una consecuencia del diseño y
   conviene tener quien la vigile.

4. **Un pH absurdo no se ejecuta en silencio.** Se acota y se deja dicho.

5. **Lo que se guarda es lo que se usó**, no lo que se pidió.
"""

from __future__ import annotations

import pytest

from chem.conformer import (
    PH_MAXIMO,
    PH_MINIMO,
    PH_POR_DEFECTO,
    _construir_conformero,
    acotar_ph,
)
from chem.ionizacion import cargas_esperadas_a_ph, elegir_microestado

pytest.importorskip("rdkit")
pytest.importorskip("dimorphite_dl")


IBUPROFENO = "CC(C)Cc1ccc(cc1)C(C)C(=O)O"
PROPRANOLOL = "CC(C)NCC(O)COc1cccc2ccccc12"
ASPIRINA = "CC(=O)OC1=CC=CC=C1C(=O)O"


# ── 1. El defecto es intocable ──────────────────────────────────────────────

@pytest.mark.parametrize("smiles", [IBUPROFENO, PROPRANOLOL, ASPIRINA])
def test_sin_decir_nada_es_identico_a_pedir_7_4(smiles):
    """El parámetro nuevo no puede mover ni una corrida existente."""
    callado = _construir_conformero(smiles)
    explicito = _construir_conformero(smiles, PH_POR_DEFECTO)

    assert callado["canonical_smiles"] == explicito["canonical_smiles"]
    assert callado["smiles_hash"] == explicito["smiles_hash"]


def test_el_defecto_sigue_siendo_el_fisiologico():
    assert PH_POR_DEFECTO == 7.4


# ── 2. El pH cambia la especie que se acopla ────────────────────────────────

def test_un_acido_entra_neutro_a_ph_bajo_y_anionico_a_fisiologico():
    """pKa ~4.9: por debajo está protonado, por encima disociado."""
    acido = _construir_conformero(IBUPROFENO, 1.0)["canonical_smiles"]
    anion = _construir_conformero(IBUPROFENO, 7.4)["canonical_smiles"]

    assert "[O-]" not in acido, f"a pH 1 no debería estar disociado: {acido}"
    assert "[O-]" in anion, f"a pH 7.4 debería estar disociado: {anion}"


def test_una_amina_entra_cationica_a_fisiologico_y_neutra_a_ph_alto():
    """pKa ~9.5: al revés que el ácido, y por eso vale como contraste."""
    cation = _construir_conformero(PROPRANOLOL, 7.4)["canonical_smiles"]
    neutra = _construir_conformero(PROPRANOLOL, 12.0)["canonical_smiles"]

    assert "+" in cation, f"a pH 7.4 la amina debería estar protonada: {cation}"
    assert "+" not in neutra, f"a pH 12 no debería estarlo: {neutra}"


def test_la_prediccion_de_cargas_depende_del_ph():
    """Es la función que el selector usa para decidir. Si no se mueve, nada se mueve."""
    a_bajo = cargas_esperadas_a_ph(IBUPROFENO, 1.0)
    a_fisiologico = cargas_esperadas_a_ph(IBUPROFENO, 7.4)

    assert a_bajo is not None and a_fisiologico is not None
    # (cationes, aniones): el ácido sólo aporta aniones, y sólo por encima del pKa.
    assert a_bajo[1] == 0
    assert a_fisiologico[1] == 1


# ── 3. El hash sigue a la especie, así que la caché no las confunde ─────────

def test_dos_ph_con_especies_distintas_no_comparten_hash():
    """Compartir hash sería compartir conformero, fila en la base y caché."""
    bajo = _construir_conformero(IBUPROFENO, 1.0)
    alto = _construir_conformero(IBUPROFENO, 7.4)

    assert bajo["canonical_smiles"] != alto["canonical_smiles"]
    assert bajo["smiles_hash"] != alto["smiles_hash"]


def test_dos_ph_con_la_MISMA_especie_si_comparten_hash():
    """Y esto también es correcto: la misma molécula es la misma corrida.

    A pH 10 y 12 el ibuprofeno está disociado en los dos casos, así que es
    literalmente el mismo sistema y reutilizar el resultado no es un error.
    """
    diez = _construir_conformero(IBUPROFENO, 10.0)
    doce = _construir_conformero(IBUPROFENO, 12.0)

    assert diez["canonical_smiles"] == doce["canonical_smiles"]
    assert diez["smiles_hash"] == doce["smiles_hash"]


# ── 4. Un pH imposible no se ejecuta a escondidas ───────────────────────────

@pytest.mark.parametrize(
    "entrada, esperado, hay_aviso",
    [
        (None, PH_POR_DEFECTO, False),
        (7.4, 7.4, False),
        (1.0, PH_MINIMO, False),
        (12.0, PH_MAXIMO, False),
        (0.5, PH_MINIMO, True),
        (14.0, PH_MAXIMO, True),
        (-3.0, PH_MINIMO, True),
        ("siete", PH_POR_DEFECTO, True),
        (float("nan"), PH_POR_DEFECTO, True),
    ],
)
def test_acotar_ph(entrada, esperado, hay_aviso):
    usado, aviso = acotar_ph(entrada)
    assert usado == esperado
    # Acotar en silencio sería ejecutar una química que nadie pidió sin decirlo.
    assert (aviso is not None) == hay_aviso


def test_acotar_nunca_lanza():
    """Un campo mal escrito no puede costar la corrida entera."""
    for basura in (object(), [], {}, "", "7,4"):
        usado, _ = acotar_ph(basura)  # type: ignore[arg-type]
        assert PH_MINIMO <= usado <= PH_MAXIMO


# ── 5. El expediente dice el pH que se usó ──────────────────────────────────

def test_el_estado_del_ligando_guarda_el_ph_ejecutado():
    datos = _construir_conformero(IBUPROFENO, 5.5)
    protonacion = datos["estado_del_ligando"]["protonacion"]

    assert protonacion["ph"] == 5.5
    assert protonacion["ph_solicitado"] == 5.5
    assert protonacion["aviso_de_ph"] is None


def test_si_se_acota_se_guarda_el_usado_y_tambien_el_pedido():
    """Las dos cifras, porque responden a preguntas distintas: qué corrió y
    qué quiso el usuario."""
    datos = _construir_conformero(IBUPROFENO, 20.0)
    protonacion = datos["estado_del_ligando"]["protonacion"]

    assert protonacion["ph"] == PH_MAXIMO
    assert protonacion["ph_solicitado"] == 20.0
    assert "por encima" in (protonacion["aviso_de_ph"] or "")


def test_el_criterio_de_seleccion_nombra_el_ph_real():
    """Iba escrito `cargas_esperadas_ph_7.4` siempre. Alguien va a leer esto
    dentro de un año para saber qué especie se acopló."""
    datos = _construir_conformero(IBUPROFENO, 3.0)
    criterio = datos["estado_del_ligando"]["protonacion"]["seleccion"]

    assert criterio["criterio"] == "cargas_esperadas_ph_3"
    assert criterio["ph"] == 3.0


def test_el_selector_usa_el_ph_que_se_le_da_y_no_el_fisiologico():
    """La prueba directa del acoplamiento que hacía peligroso exponer el pH.

    Se le dan a mano los dos microestados del ibuprofeno y se comprueba que a
    pH 1 elige el neutro y a pH 7.4 el aniónico. Con el 7.4 escrito a mano en
    `cargas_esperadas_a_ph_74`, las dos llamadas devolvían el aniónico.
    """
    neutro = "CC(C)Cc1ccc(C(C)C(=O)O)cc1"
    anion = "CC(C)Cc1ccc(C(C)C(=O)[O-])cc1"

    elegido_bajo, _ = elegir_microestado(neutro, [neutro, anion], 1.0)
    elegido_fisiologico, _ = elegir_microestado(neutro, [neutro, anion], 7.4)

    assert elegido_bajo == neutro
    assert elegido_fisiologico == anion
