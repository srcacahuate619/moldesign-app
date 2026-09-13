"""Receptor multicadena: sólo los pedazos del sitio, vengan de la cadena que vengan.

# El problema que resuelve

`preparer.py` conserva **una sola cadena**, la que declara el catálogo
(`if current_chain != chain_id: continue`). Esa decisión no fue un descuido: la
tomó `SESSION_SUMMARY_v1.6` para resolver un problema real —Vina acoplando
contra dímeros y tetrámeros enteros, con receptores de 5,8 y 10,5 MB.

Pero para un sitio activo que se forma **entre** cadenas, recortar a una sola
deja al ligando acoplando contra media cavidad. Medido en `docs/71`: 101
objetivos del catálogo pierden ≥20% de los átomos de su caja de docking, y la
proteasa del VIH (1TW7) es el caso de libro — 281 y 286 átomos de cada monómero
a 12 Å del centro del sitio.

# La solución NO es quedarse con todas las cadenas enteras

Eso reintroduciría exactamente el problema que v1.6 resolvió. Lo que hace falta
es **el sitio, completo, y nada más**: los residuos que forman el bolsillo,
vengan de la cadena que vengan, aunque una aporte el 3%.

# Esto ya estaba resuelto en este repositorio

`services/chemistry/protein_surgery.py:trim_to_pocket` hace precisamente eso, y
lleva tiempo en producción para MM-GBSA (25 Å) y para la ventana de ProLIF
(20 Å). Sus dos propiedades son las que hacen falta aquí:

  * **Agnóstico a la cadena.** Indexa por `(chain, resnum, inscode)`, así que
    conserva residuos de TODAS las cadenas que caigan en el radio.
  * **Nunca corta a mitad de residuo.** Un residuo entra entero o no entra. Sin
    eso, Meeko recibiría fragmentos de cadena principal y produciría basura.

Este módulo no reimplementa nada: **encadena esa función con la política de
heteroátomos y aguas que ya aplica `preparer.py`**, para que el receptor
multicadena obedezca las mismas reglas que el de una cadena. Duplicar el
recorte habría creado una segunda implementación que puede divergir, que es el
modo de fallo que este repositorio lleva toda la sesión persiguiendo.

# Qué NO decide este módulo

Cuándo usarlo. Que un objetivo se prepare en modo multicadena es una decisión
del catálogo, no de esta función: cambia los números respecto al método
anterior y exige un corrigendum sobre lo ya sellado (ver `docs/71` §2.3).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)

#: Aguas. Misma definición que `preparer._WATER_RESIDUES`; se importa de allí
#: para que no puedan divergir.
from services.docking.preparer import _WATER_RESIDUES  # noqa: E402

#: Alcance de van der Waals: lo que un ligando situado en el borde de la caja
#: puede tocar por fuera de ella. Un receptor recortado justo en la pared de la
#: caja deja al ligando acoplando contra el vacío en los bordes.
ALCANCE_VDW_A = 4.0


def radio_para_caja(lados: tuple[float, float, float] | float) -> float:
    """El radio de recorte que corresponde a esta caja de docking.

    **No es un parámetro: es una consecuencia.** El receptor tiene que conservar
    todo residuo que un ligando pueda tocar desde CUALQUIER punto de la caja, o
    sea la caja más el alcance de van der Waals. Como esfera, eso es la
    semidiagonal del cubo más ese alcance::

        r = (√3/2)·lado + 4 Å

    La primera versión de este módulo fijaba 12 Å y justificaba que «cubre con
    holgura una caja de 25 Å». Es falso: la semidiagonal de esa caja es 21,7 Å,
    así que 12 Å ni siquiera llega a la esfera inscrita. Medido sobre 1TW7 —la
    proteasa del VIH, el caso de libro del doc 71— con r=12 Å se pierden **389
    de los 926 átomos** que el ligando podría tocar: el 42%. Con el radio
    derivado, cero.

    Y el temor que motivó la preparación de una sola cadena en v1.6 —receptores
    de 5 y 10 MB— no reaparece. Medido sobre las seis estructuras más grandes del
    catálogo, todas de ~49.000 átomos, el recorte deja entre 2.170 y 2.992
    átomos: entre el 4,4% y el 6,1%.

    Las cajas del catálogo van de 20,6 a 50 Å de lado, así que un radio constante
    no puede ser correcto para las dos puntas.
    """
    lado = float(max(lados)) if isinstance(lados, (tuple, list)) else float(lados)
    return lado * math.sqrt(3) / 2.0 + ALCANCE_VDW_A


#: Sólo para llamadas que no traen caja. Corresponde a una de 25 Å, que es la
#: mediana del catálogo. Preferir siempre `radio_para_caja`.
RADIO_SITIO_A = radio_para_caja(25.0)


@dataclass(frozen=True)
class RecorteMultichain:
    """Qué quedó del receptor, para poder declararlo en el dossier."""

    ruta: Path
    cadenas: dict[str, int]          #: átomos conservados por cadena
    residuos: int
    atomos: int
    radio: float
    #: Cadenas que aportan al sitio y que el modo de UNA cadena habría tirado.
    cadenas_recuperadas: tuple[str, ...]


def preparar_receptor_multichain(
    pdb_entrada: str | Path,
    centro_sitio: tuple[float, float, float],
    cadena_declarada: str,
    *,
    radio: float = RADIO_SITIO_A,
    salida: str | Path | None = None,
    conservar_aguas: bool = False,
) -> RecorteMultichain:
    """Recorta el receptor al sitio, conservando residuos de todas las cadenas.

    Args:
        pdb_entrada: PDB completo, sin filtrar por cadena.
        centro_sitio: centro de la caja de docking.
        cadena_declarada: la del catálogo. **No filtra**: sólo sirve para
            informar de qué cadenas se habrían perdido en el modo anterior.
        radio: Å alrededor del centro. Un residuo entra si CUALQUIER átomo suyo
            cae dentro.
        conservar_aguas: por defecto no. Ver `docs/51_POLITICA_DE_AGUAS.md`:
            quitarlas da 96/116 de cobertura frente a 94/116 conservándolas
            (`REC-11`, McNemar p=0.81, SIN_DIFERENCIA_DETECTABLE). La política
            vigente es quitarlas, y este módulo no la cambia.

    Raises:
        ValueError: si el recorte se queda sin átomos. Un receptor vacío no
            puede acoplar nada, y devolverlo en silencio produciría una
            afinidad sin sustento — que es justo el fallo que `docs/71`
            documenta para los objetivos con la cadena mal anotada.
    """
    from services.chemistry.protein_surgery import trim_to_pocket

    entrada = Path(pdb_entrada)
    destino = Path(salida) if salida else entrada.with_name(entrada.stem + "_sitio.pdb")

    ruta, recortado = trim_to_pocket(
        str(entrada), tuple(centro_sitio), radius=float(radio), output_pdb=str(destino)
    )
    if not recortado:
        # `trim_to_pocket` devuelve el archivo ORIGINAL cuando no encuentra
        # residuos en el radio. Seguir adelante con eso entregaria la proteina
        # ENTERA haciendola pasar por un sitio recortado —el mismo fallo
        # silencioso que este modulo existe para evitar—. Lo detecto el
        # control con un centro absurdo (999, 999, 999), que devolvia las dos
        # cadenas completas en lugar de fallar.
        raise ValueError(
            f"El centro {tuple(centro_sitio)} no tiene ningun residuo de "
            f"{entrada.name} a {radio} A. O el centro del sitio esta mal, o no "
            "corresponde a esta estructura. No se prepara un receptor a ciegas."
        )

    # Política de heteroátomos, la MISMA que aplica el modo de una cadena: fuera
    # aguas y ligandos co-cristalizados. Un ligando dejado dentro ocuparía el
    # bolsillo que se quiere sondear.
    conservadas: dict[str, int] = {}
    residuos: set[tuple[str, str]] = set()
    lineas: list[str] = []
    for linea in Path(ruta).read_text(encoding="utf-8", errors="replace").splitlines():
        if not linea.startswith(("ATOM", "HETATM")):
            continue
        residuo = linea[17:20].strip().upper()
        if residuo in _WATER_RESIDUES and not conservar_aguas:
            continue
        if linea.startswith("HETATM"):
            # Sólo se conservan aguas cuando se piden; el resto de HETATM
            # -ligandos, tampones, crioprotectores- no forma parte del receptor.
            if not (conservar_aguas and residuo in _WATER_RESIDUES):
                continue
        cadena = linea[21]
        conservadas[cadena] = conservadas.get(cadena, 0) + 1
        residuos.add((cadena, linea[22:27].strip()))
        lineas.append(linea)

    if not lineas:
        raise ValueError(
            f"El recorte de {entrada.name} a {radio} A del centro {centro_sitio} no "
            "dejo ningun atomo de proteina. Un receptor vacio no puede acoplar nada: "
            "revisa el centro del sitio antes de seguir."
        )

    destino.write_text("\n".join(lineas) + "\nEND\n", encoding="utf-8")

    recuperadas = tuple(sorted(c for c in conservadas if c.strip() != cadena_declarada.strip()))
    log.info(
        "receptor_multichain_preparado",
        pdb=entrada.name,
        radio=radio,
        cadenas=conservadas,
        residuos=len(residuos),
        cadenas_recuperadas=recuperadas,
    )
    return RecorteMultichain(
        ruta=destino,
        cadenas=conservadas,
        residuos=len(residuos),
        atomos=len(lineas),
        radio=float(radio),
        cadenas_recuperadas=recuperadas,
    )
