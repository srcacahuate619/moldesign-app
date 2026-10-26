"""Los detalles del validador físico salen en inglés en todos sus estados (ABS-TR-01).

La matriz de transmisión de ABS-TR-01 (`test_abs_tr_01_transmision.py`) encontró
que el dossier inglés sólo traducía el detalle de una pose **superada**: el
catálogo tenía esa frase entera como plantilla, y nada más. Una pose fallida, en
revisión o sin evaluar salía en castellano dentro del documento inglés, justo en
los estados que el lector tiene que entender.

El productor (`pose_physical_validity.py`) está sellado por PROD-PV-H-01 y
PROD-PV-H-01-PRE y no se toca. Estas pruebas construyen cada detalle con las
mismas piezas que él usa —sus f-strings copiadas aquí, con valores verosímiles—
y exigen que la traducción no deje castellano. Si el productor cambia una frase,
`test_las_frases_siguen_en_el_productor` falla y obliga a revisar la pareja.
"""

from __future__ import annotations

import inspect

import pytest

from core.i18n_plantillas import _PARECE_CASTELLANO, traducir
from services.chemistry import pose_physical_validity as pv
from services.chemistry import structural_evidence as se

F = pv.FRASE_OBLIGATORIA
CAB = "PoseBusters en configuracion `dock` -sin verdad de terreno, que en produccion no existe-. "

_PROXY = (
    "Bateria completa no ejecutada: PoseBusters fallo al ejecutarse (ImportError). Solo se corrio un "
    "PROXY ENERGETICO RDKit NO CALIBRADO, que **no** es el control "
    "`internal_energy` de PoseBusters: usa MMFF en vez de UFF, "
    "{n} conformeros en vez de {m} y una "
    "razon distinta, y su umbral no esta calibrado contra ninguna medicion. "
    "Razon 1.83 contra un umbral de 1.5: "
    "{rango} de rango. "
    "{extra}"
    "No se evaluaron distancias al receptor, valencias, aromaticidad ni "
    f"planaridad. {F}"
)
_FUERA = ("ESE VALOR FUERA DE RANGO NO ES UN VEREDICTO DE FALLA: `PROD-PV-H-01` midio "
          "que este proxy rechaza el 14.2% de las poses que el control oficial de "
          "PoseBusters aprueba, y siempre en esa direccion. Por eso se reporta como "
          "revision y no como control fallido. ")

DETALLES = {
    "superada": CAB + "Ningun control de quimica o geometria falla. " + F,
    "fallida": CAB + "Fallan 1 controles de quimica o geometria: internal_energy. " + F,
    "fallidas_varias": CAB + "Fallan 2 controles de quimica o geometria: internal_energy, bond_lengths. " + F,
    "revision_no_evaluados": (CAB + "Ningun control de quimica o geometria falla. "
                              "2 controles no devolvieron un booleano y NO se cuentan como superados: "
                              "internal_energy, volume_overlap_with_protein. " + F),
    "revision_carga": (CAB + "Ningun control de quimica o geometria falla. "
                       "No se pudieron cargar entradas (mol_cond_loaded), asi que los controles "
                       "intermoleculares NO se evaluaron: eso es un problema de la entrada, no de la pose. " + F),
    "fallida_y_no_evaluados": (CAB + "Fallan 1 controles de quimica o geometria: bond_angles. "
                               "1 controles no devolvieron un booleano y NO se cuentan como superados: "
                               "internal_energy. " + F),
    "sin_reconstruir": f"No se pudo reconstruir la pose para validarla (index_map_no_biyectivo). {F}",
    "sin_hidrogenos": ("No se pudo reconstruir la representación canónica de hidrógenos "
                       f"(INVARIANTE_CANONICA_VIOLADA). {F}"),
    "proxy_sin_ejecutar": f"El proxy energetico RDKit no pudo ejecutarse (no se pudo parametrizar la molecula). {F}",
    "proxy_dentro": _PROXY.format(n=pv.N_CONFORMEROS_PROXY, m=f"{pv.PB_DOCK_N_CONFORMEROS:.0f}",
                                  rango="dentro", extra=""),
    "proxy_fuera": _PROXY.format(n=pv.N_CONFORMEROS_PROXY, m=f"{pv.PB_DOCK_N_CONFORMEROS:.0f}",
                                 rango="FUERA", extra=_FUERA),
    # structural_evidence.py: la etapa sin veredicto, pose a pose.
    "sin_pdbqt": "La pose no conservó su bloque PDBQT; no hay coordenadas que validar.",
    "sin_receptor": ("No se pudo usar el receptor exacto de esta corrida "
                     "(receptor_no_coincide); no se emite veredicto geométrico."),
    "sin_plantilla": "Sin plantilla química ni SMILES declarados. La química no se deduce de los tipos AutoDock.",
    "validador_lanzo": "El validador lanzó RuntimeError sobre esta pose.",
}


@pytest.mark.parametrize("caso", sorted(DETALLES))
def test_el_detalle_sale_en_ingles(caso):
    original = DETALLES[caso]
    ingles = traducir(original, "en")
    assert ingles != original, f"{caso}: sin traducción"
    assert not _PARECE_CASTELLANO.search(ingles), (caso, ingles)


def test_un_fallo_sigue_diciendo_que_falla_en_ingles():
    ingles = traducir(DETALLES["fallida"], "en")
    assert "internal_energy" in ingles and "fail" in ingles


def test_el_proxy_fuera_de_rango_no_se_traduce_como_fallo():
    ingles = traducir(DETALLES["proxy_fuera"], "en")
    assert "NOT A FAILURE VERDICT" in ingles
    assert "14.2%" in ingles


@pytest.mark.parametrize("modulo,frase", [
    (pv, "PoseBusters en configuracion `dock` -sin verdad de terreno, que "),
    (pv, "Fallan {len(fallan_quimica)} controles de quimica o "),
    (pv, "Ningun control de quimica o geometria falla. "),
    (pv, "asi que los controles intermoleculares NO se evaluaron: eso "),
    (pv, "controles no devolvieron un booleano y NO se "),
    (pv, "No se pudo reconstruir la pose para validarla ({motivo}). "),
    (pv, "No se pudo reconstruir la representación canónica de hidrógenos "),
    (pv, "El proxy energetico RDKit no pudo ejecutarse "),
    (pv, "Bateria completa no ejecutada: {razon_degradacion}. Solo se corrio un "),
    (pv, "ESE VALOR FUERA DE RANGO NO ES UN VEREDICTO DE FALLA: `PROD-PV-H-01` midio "),
    (pv, "No se evaluaron distancias al receptor, valencias, aromaticidad ni "),
    (se, "La pose no conservó su bloque PDBQT; no hay coordenadas que validar."),
    (se, "No se pudo usar el receptor exacto de esta corrida "),
    (se, "Sin plantilla química ni SMILES declarados. La química no se "),
    (se, "El validador lanzó {type(exc).__name__} sobre esta pose."),
])
def test_las_frases_siguen_en_el_productor(modulo, frase):
    assert frase in inspect.getsource(modulo), (
        "El productor cambió una frase de detalle: revisa su pareja en i18n_plantillas.py "
        "y el caso correspondiente de DETALLES.")
