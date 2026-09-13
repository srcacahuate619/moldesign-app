"""En qué régimen de tamaño cae una molécula, según criterios publicados.

# El problema que resuelve

Este proyecto tenía sus propios umbrales de tamaño, escritos en `core/config.py`:

    mol_min_molecular_weight = 100.0    # aviso
    mol_max_molecular_weight = 800.0    # aviso
    mol_max_heavy_atoms      = 80       # ERROR, detiene la corrida

Ninguno corresponde a un criterio de la literatura. El 800 no es una frontera
publicada de nada, y el 80 —el único que bloquea— no aparece en ninguna regla
de drug-likeness. Eran números inventados decidiendo qué entra al producto.

La química medicinal tiene estas fronteras definidas y citadas desde hace
décadas, y este módulo las adopta en lugar de inventar:

    Molécula pequeña    Rule of Five       MW <= 500           Lipinski et al. 1997
    Más allá de Ro5     bRo5               500 < MW <= 1000    Doak et al. 2014
    Fuera de alcance    —                  MW > 1000, o > 70 átomos (Ghose 1999)

# Las referencias, y qué dice cada una

**Rule of Five** — Lipinski, Lombardo, Dominy, Feeney,
*Adv. Drug Deliv. Rev.* 23 (1997) 3-25; revisado en 46 (2001) 3-26.
MW <= 500, logP <= 5, HBD <= 5, HBA <= 10. Es la definición operativa de
«molécula pequeña oral» en la industria, y ya está implementada en
`chem/properties.py::LipinskiRule` — este módulo sólo usa su corte de MW para
delimitar el régimen.

**Beyond Rule of Five (bRo5)** — Doak, Over, Giordanetto, Kihlberg,
*Chem. Biol.* 21 (2014) 1115-1142, «Oral druggable space beyond the rule of 5».
Delimita 500 < MW <= 1000 como un espacio con fármacos orales reales
—macrociclos, péptidos cíclicos, inhibidores de interacción proteína-proteína—
que la Ro5 excluye. Por eso aquí NO se rechaza: se declara. Rechazarlo sería
afirmar que ese espacio no existe, y existe.

**Ghose** — Ghose, Viswanadhan, Wendoloski, *J. Comb. Chem.* 1 (1999) 55-68.
Su rango de átomos, 20-70, ya está en `chem/properties.py::GhoseRule`. Su tope
de 70 átomos pesados es el que se usa aquí como frontera superior dura, y
coincide con lo que da la conversión desde 1000 Da.

**Rule of Three** — Congreve, Carr, Murray, Jhoti,
*Drug Discov. Today* 8 (2003) 876-877. MW < 300, cLogP <= 3, HBD <= 3, HBA <= 3.
Es el criterio de ENTRADA de una quimioteca de fragmentos, no una clasificación
de moléculas — ver la nota sobre `cumple_ro3` más abajo.

# La conversión MW <-> átomos pesados, medida y no supuesta

Los regímenes se definen por MW, que es como los publican. Pero varias partes
del pipeline razonan en átomos pesados (Vina, la eficiencia de ligando, el
coste del muestreo conformacional), así que hacen falta las dos.

La equivalencia se midió sobre once fármacos reales, del benceno a la
ciclosporina:

    benceno       78 Da /  6 HA = 13.02      imatinib      494 / 37 = 13.34
    paracetamol  151 / 11 = 13.74            atorvastatina 559 / 41 = 13.63
    aspirina     180 / 13 = 13.86            ritonavir     735 / 51 = 14.41
    ibuprofeno   206 / 15 = 13.75            ciclosporina 1203 / 85 = 14.15
    cafeína      194 / 14 = 13.87
    acetazolamida 222 / 13 = 17.10   <- la más alta: azufre por todas partes
    lisinopril   300 / 21 = 14.30

Mediana 13.86 Da por átomo pesado. De ahí:

    MW  300  ->  ~22 átomos pesados
    MW  500  ->  ~36 átomos pesados
    MW 1000  ->  ~72 átomos pesados

El 72 concuerda con el tope de 70 de Ghose por un camino independiente, y por
eso el límite duro se pone en 70: es el número publicado, y la medición lo
corrobora en vez de contradecirlo.

# Qué significa cada régimen PARA ESTE PRODUCTO

No es una etiqueta decorativa: cambia qué se puede afirmar del resultado.

    RO5     El régimen para el que todo lo demás está calibrado: Lipinski,
            Veber, Ghose, Egan, Muegge, los umbrales de eficiencia de ligando y
            la función de puntuación de Vina. Es el estándar de la aplicación.

    BRO5    Espacio oral real pero fuera de la calibración de las reglas. Corre
            igual; lo que cambia es que las reglas de Ro5 dejan de ser un
            criterio y se dice.

    FUERA   Por encima de 1000 Da o de 70 átomos pesados no hay ninguna regla
            de las implementadas que aplique, el muestreo conformacional de
            Vina se degrada y el resultado no es interpretable con lo que este
            producto sabe medir.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

# ── Fronteras publicadas ─────────────────────────────────────────────────
#
# En Da. Se escriben aquí, una vez, con la referencia al lado, en vez de
# repartidas por `config.py` como ajustes configurables: NO son ajustes. Mover
# una de estas es cambiar de qué habla el producto, no afinar un parámetro.

#: Rule of Three (Congreve et al. 2003). Marca `cumple_ro3`; no es un régimen.
MW_FRAGMENTO = 300.0

#: Rule of Five (Lipinski et al. 1997). Techo de «molécula pequeña».
MW_RO5 = 500.0

#: Beyond Rule of Five (Doak et al. 2014). Techo del espacio oral conocido.
MW_BRO5 = 1000.0

#: Ghose et al. 1999, rango de átomos 20-70. El tope superior, que además
#: coincide con los ~72 que da la conversión desde 1000 Da.
HA_MAXIMO = 70

#: Equivalentes en átomos pesados de las fronteras de MW, medidos (ver módulo).
#: Son una conversión, NO un criterio: ver `clasificar`.
HA_FRAGMENTO = 22
HA_RO5 = 36

#: Mínimo por debajo del cual no hay nada que acoplar. No es un criterio
#: publicado: es el suelo mecánico de Vina, que necesita algo que rotar y
#: contactos que contar. Se declara como lo que es.
HA_MINIMO = 5


class Regimen(str, Enum):
    """Régimen de tamaño. El valor es el que viaja al frontend y al dossier."""

    RO5 = "ro5"
    BRO5 = "bro5"
    FUERA_DE_ALCANCE = "fuera_de_alcance"


@dataclass(frozen=True)
class Clasificacion:
    """El régimen de una molécula, con de dónde sale y qué implica."""

    regimen: Regimen
    #: Nombre legible, para la interfaz.
    etiqueta: str
    #: La referencia que define esta frontera.
    criterio: str
    #: Qué se puede y qué no se puede afirmar de un resultado en este régimen.
    implicacion: str
    #: `True` sólo para FUERA_DE_ALCANCE: la corrida no debe continuar.
    bloquea: bool = False
    #: Si además satisface el corte de masa de la Rule of Three. NO es un
    #: régimen aparte: es un subconjunto del espacio Ro5. Ver `clasificar`.
    cumple_ro3: bool = False
    #: Cuando MW y átomos pesados apuntan a regímenes distintos, qué pasó.
    #: `None` si concuerdan.
    discrepancia: str | None = None


_RO5 = Clasificacion(
    regimen=Regimen.RO5,
    etiqueta="Molécula pequeña (Ro5)",
    criterio="Rule of Five (Lipinski et al., Adv. Drug Deliv. Rev. 23:3, 1997): MW ≤ 500 Da",
    implicacion=(
        "Régimen estándar de la aplicación. Es para el que están calibradas las "
        "reglas de drug-likeness implementadas (Lipinski, Veber, Ghose, Egan, "
        "Muegge), los umbrales de eficiencia de ligando y la función de "
        "puntuación de Vina."
    ),
)

_BRO5 = Clasificacion(
    regimen=Regimen.BRO5,
    etiqueta="Más allá de Ro5 (bRo5)",
    criterio=(
        "Beyond Rule of Five (Doak, Over, Giordanetto, Kihlberg, Chem. Biol. "
        "21:1115, 2014): 500 < MW ≤ 1000 Da"
    ),
    implicacion=(
        "Espacio con fármacos orales reales —macrociclos, péptidos cíclicos, "
        "inhibidores de interacción proteína-proteína— que la regla de los "
        "cinco excluye por construcción. La corrida se ejecuta; lo que deja de "
        "aplicar son los filtros de Ro5 y los umbrales de eficiencia de "
        "ligando, que no están calibrados a este tamaño."
    ),
)

_FUERA = Clasificacion(
    regimen=Regimen.FUERA_DE_ALCANCE,
    etiqueta="Fuera del alcance de la aplicación",
    criterio=(
        f"Por encima del espacio bRo5 (MW > {MW_BRO5:.0f} Da) o del rango de "
        f"átomos de Ghose et al. 1999 ({HA_MAXIMO} átomos pesados)"
    ),
    implicacion=(
        "Ninguna de las reglas de drug-likeness implementadas cubre este "
        "tamaño, el muestreo conformacional de Vina se degrada, y el resultado "
        "no sería interpretable con lo que este producto sabe medir. La corrida "
        "se detiene en vez de producir un número que nadie puede leer."
    ),
    bloquea=True,
)

_POR_REGIMEN = {
    Regimen.RO5: _RO5,
    Regimen.BRO5: _BRO5,
    Regimen.FUERA_DE_ALCANCE: _FUERA,
}


def clasificar(peso_molecular: float, atomos_pesados: int) -> Clasificacion:
    """El régimen de una molécula.

    ═════════════════════════════════════════════════════════════════════
    MANDA EL PESO MOLECULAR, NO LOS ÁTOMOS
    ═════════════════════════════════════════════════════════════════════

    Las tres fronteras están publicadas EN MASA MOLECULAR. La equivalencia en
    átomos pesados de este módulo es una conversión medida, no un criterio:
    útil para los sitios que razonan en átomos, pero derivada.

    La primera versión de esta función tomaba el régimen más restrictivo de los
    dos, y al medirla sobre fármacos reales salió el error: **imatinib, MW
    493.6, caía en bRo5** porque tiene 37 átomos pesados y la conversión da 36.
    Imatinib cumple la regla de los cinco por masa; llamarlo bRo5 es dejar que
    una aproximación propia contradiga el criterio citado.

    Así que el peso decide. Los átomos sólo intervienen en dos casos, los dos
    justificados:

      1. **Como tope duro superior**: 70 átomos pesados es el límite del rango
         de Ghose et al. 1999, un criterio publicado por derecho propio, no una
         conversión. Una molécula con más de 70 átomos queda fuera aunque su
         masa no llegue a 1000 Da.
      2. **Cuando no hay masa**: se usa la conversión y se dice.

    Si las dos magnitudes apuntan a regímenes distintos, el resultado lo fija
    el peso y la discrepancia se registra en `discrepancia` en vez de
    resolverse en silencio.

    ═════════════════════════════════════════════════════════════════════
    RO3 NO ES UN RÉGIMEN, ES UNA MARCA
    ═════════════════════════════════════════════════════════════════════

    La Rule of Three (Congreve et al. 2003) es el criterio de ENTRADA de una
    quimioteca de fragmentos, no una clasificación de moléculas. La aspirina
    pesa 180 Da y cumple Ro3; llamarla «fragmento» sería etiquetar un fármaco
    como algo que no es.

    Se expone como `cumple_ro3` porque cambia cómo se lee el resultado —a este
    tamaño la afinidad es baja por construcción y la eficiencia de ligando es
    alta por construcción— sin afirmar que la molécula sea un fragmento.
    """
    if not peso_molecular or peso_molecular <= 0:
        base = _POR_REGIMEN[_regimen_por_atomos(atomos_pesados)]
        return replace(
            base,
            cumple_ro3=atomos_pesados < HA_FRAGMENTO,
            discrepancia=(
                "No se pudo calcular la masa molecular: el régimen se dedujo de "
                f"{atomos_pesados} átomos pesados por la conversión medida "
                "(~13.9 Da/átomo), que es una aproximación."
            ),
        )

    # Tope duro por átomos: es el rango publicado de Ghose, no una conversión.
    if atomos_pesados > HA_MAXIMO:
        return replace(
            _FUERA,
            cumple_ro3=False,
            discrepancia=(
                f"MW {peso_molecular:.0f} Da cabría en el espacio bRo5, pero la "
                f"molécula tiene {atomos_pesados} átomos pesados y el rango de "
                f"Ghose et al. 1999 termina en {HA_MAXIMO}."
            )
            if peso_molecular <= MW_BRO5
            else None,
        )

    por_peso = _regimen_por_peso(peso_molecular)
    por_atomos = _regimen_por_atomos(atomos_pesados)

    discrepancia = None
    if por_atomos is not por_peso:
        discrepancia = (
            f"MW {peso_molecular:.0f} Da sitúa la molécula en "
            f"«{_POR_REGIMEN[por_peso].etiqueta}» y sus {atomos_pesados} átomos "
            f"pesados en «{_POR_REGIMEN[por_atomos].etiqueta}». Manda la masa, "
            "que es la magnitud en la que están publicadas las fronteras."
        )

    return replace(
        _POR_REGIMEN[por_peso],
        cumple_ro3=peso_molecular < MW_FRAGMENTO,
        discrepancia=discrepancia,
    )


def _regimen_por_peso(mw: float) -> Regimen:
    if mw <= MW_RO5:
        return Regimen.RO5
    if mw <= MW_BRO5:
        return Regimen.BRO5
    return Regimen.FUERA_DE_ALCANCE


def _regimen_por_atomos(ha: int) -> Regimen:
    if ha <= HA_RO5:
        return Regimen.RO5
    if ha <= HA_MAXIMO:
        return Regimen.BRO5
    return Regimen.FUERA_DE_ALCANCE
