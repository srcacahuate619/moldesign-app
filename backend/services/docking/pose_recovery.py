"""
Recuperar el registro SDF EXACTO de una pose agrupada, o abstenerse diciendo qué falta.

# Por qué hace falta

El ensemble entrega una piscina de K corridas, así que `poses_file_path` del
resultado agrupado es `None` a propósito: apuntar al SDF de la primera corrida
presentaría coordenadas distintas de las poses entregadas. Eso dejaba sin pose
recuperable a todo lo que consume un archivo —MM-GBSA, exportaciones,
interacciones—, y la salida honesta era abstenerse.

`source_provenance` guarda desde el 2026-09-17 la ruta y el rank original de
cada pose. Con eso se podría ir a buscar el registro… y eso es exactamente lo
que ENS-04 declaró insuficiente: **una ruta y un número no demuestran que el
registro que hay ahí sea esta pose**. El archivo puede haber cambiado, el
exportador puede haber reordenado átomos, y un rank fuera de sitio devuelve la
geometría de otra pose con total naturalidad.

# Las puertas, y por qué cada una

    G1  procedencia completa      sin ruta, rank y hashes no se busca nada
    G2  integridad del artefacto  el SDF de hoy es el SDF de la corrida
    G3  integridad de la entrada  la conformación que se acopló es la declarada
    G4  el registro existe        el rank cae dentro del archivo
    G5  identidad química         mismos átomos pesados que la entrada
    G6  correspondencia geométrica cada coordenada entregada está en el registro

G6 es la que de verdad cierra el asunto: el `pdbqt_block` de la pose son las
coordenadas que Vina produjo y que el dossier ya citó. Si cada una de ellas
aparece en el registro recuperado, el registro ES esa pose, sin depender de que
el rank estuviera bien ni de que nadie hubiera reordenado el archivo.

# Lo que NO hace

No genera nada desde el SMILES, no hereda la pose de otra conformación, no
rellena un hash ausente y no reconstruye coordenadas. Si una puerta no pasa,
levanta `PoseNoRecuperable` con el motivo. Abstenerse es una salida válida.

Tampoco deduce elementos de las columnas 77-78 del PDBQT: ahí vive el tipo
AutoDock —`A` es carbono aromático, `NA` nitrógeno aceptor—, y confundirlo con
el símbolo químico es el defecto que hacía ilegible el 76.7% de una cohorte
(ver `services/chemistry/pose_physical_validity.py`). De esas columnas se lee
una sola cosa, la misma que lee ese módulo: si el átomo es un pseudo-átomo de
pegado de macrociclo, que no existe en la molécula ni en el SDF. Las coordenadas
salen de las columnas 31-54 y nada más.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from core.models import DockingPose
from utils.local_storage import read_bytes
from utils.logger import get_logger

log = get_logger(__name__)

#: Tolerancia de la correspondencia geométrica, en ångström.
#:
#: No es un margen de ajuste: es la precisión de los formatos. El PDBQT escribe
#: tres decimales y el SDF cuatro, así que dos representaciones de la MISMA pose
#: pueden diferir en el último dígito del PDBQT. 0.002 Å cubre ese redondeo con
#: holgura y sigue siendo dos órdenes de magnitud menor que cualquier diferencia
#: conformacional real. Ampliarla para que «pase» un caso sería exactamente lo
#: que esta comprobación existe para impedir.
TOLERANCIA_A = 0.002


class PoseNoRecuperable(Exception):
    """No se puede demostrar que el registro recuperado sea esta pose."""


@dataclass(frozen=True)
class PoseRecuperada:
    """El registro SDF verificado, con la medida que lo respalda."""

    sdf_record: str
    poses_file_path: str
    rank_original: int
    conformer_index: int | None
    conformer_path: str
    atomos_verificados: int
    max_desplazamiento_A: float
    #: Pseudo-átomos de pegado de macrociclo descartados del bloque entregado.
    #: No son átomos de la molécula; se informan para que el descarte se vea.
    pseudoatomos_de_pegado: int = 0


# ── Lectura de formatos, sin inferir nada ─────────────────────────────


def _coordenadas_de_pdbqt(bloque: str) -> tuple[list[tuple[float, float, float]], int]:
    """Coordenadas por columnas fijas 31-54, y cuántos pseudo-átomos se descartaron.

    El tipo AutoDock de las columnas 77-78 se lee SÓLO para reconocer los
    pseudo-átomos de pegado que Meeko inserta al abrir un macrociclo —nunca para
    deducir el elemento—. Esos átomos NO existen en la molécula, así que tampoco
    existen en el SDF: exigirles contrapartida haría que toda pose de un ligando
    macrocíclico se declarara irrecuperable. Es la misma convención, con la misma
    tabla, que `services/chemistry/pose_physical_validity.py`.
    """
    from services.chemistry.pose_physical_validity import TIPOS_PEGADO_MACROCICLO

    coordenadas = []
    pegado = 0
    for linea in bloque.splitlines():
        if not linea.startswith(("ATOM", "HETATM")):
            continue
        try:
            punto = (float(linea[30:38]), float(linea[38:46]), float(linea[46:54]))
        except (ValueError, IndexError):
            continue
        if linea[76:78].strip() in TIPOS_PEGADO_MACROCICLO:
            pegado += 1
            continue
        coordenadas.append(punto)
    return coordenadas, pegado


def _atomos_de_registro_sdf(registro: str) -> list[tuple[str, float, float, float]]:
    """(elemento, x, y, z) del bloque de átomos V2000.

    Se lee el texto y no RDKit: sanear la molécula podría cambiar átomos o
    coordenadas, y aquí se compara con lo que se entregó, no con lo que RDKit
    crea que debería ser. Un archivo V3000 se rechaza en vez de interpretarse a
    medias.
    """
    lineas = registro.splitlines()
    if len(lineas) < 4:
        raise PoseNoRecuperable("El registro SDF no tiene cabecera completa.")
    conteos = lineas[3]
    if "V2000" not in conteos:
        raise PoseNoRecuperable(
            "El registro SDF no es V2000; no se interpreta un formato que este "
            "lector no cubre."
        )
    try:
        numero = int(conteos[0:3])
    except ValueError as exc:
        raise PoseNoRecuperable("El registro SDF no declara su número de átomos.") from exc
    atomos = []
    for linea in lineas[4:4 + numero]:
        try:
            atomos.append((
                linea[31:34].strip(),
                float(linea[0:10]), float(linea[10:20]), float(linea[20:30]),
            ))
        except (ValueError, IndexError) as exc:
            raise PoseNoRecuperable("El bloque de átomos del SDF está malformado.") from exc
    if len(atomos) != numero:
        raise PoseNoRecuperable(
            f"El registro declara {numero} átomos y contiene {len(atomos)}."
        )
    return atomos


def _registros(contenido: str) -> list[str]:
    """Parte el SDF en registros. El separador `$$$$` manda sobre todo lo demás.

    Es la misma prioridad que `parse_vina_output_sdf`: una propiedad sin valor no
    puede absorber el fin del registro, porque entonces la metadata de una pose
    se mezclaría con la geometría de la siguiente (ENS-06).
    """
    registros: list[str] = []
    actual: list[str] = []
    for linea in contenido.splitlines():
        if linea.strip() == "$$$$":
            registros.append("\n".join(actual) + "\n")
            actual = []
            continue
        actual.append(linea)
    if any(l.strip() for l in actual):
        # Un registro sin `$$$$` final: se conserva, pero el archivo está
        # truncado y quien lo use tiene que saberlo.
        registros.append("\n".join(actual) + "\n")
    return registros


# ── Las puertas ───────────────────────────────────────────────────────


async def _sha256(object_name: str, que_es: str) -> str:
    try:
        return hashlib.sha256(await read_bytes(object_name)).hexdigest()
    except Exception as exc:                                       # noqa: BLE001
        raise PoseNoRecuperable(
            f"No se puede leer {que_es} ({object_name}): {type(exc).__name__}."
        ) from exc


def _correspondencia_geometrica(
    entregadas: list[tuple[float, float, float]],
    registro: list[tuple[str, float, float, float]],
    tolerancia: float,
) -> tuple[int, float]:
    """Biyección coordenada a coordenada. Devuelve (emparejadas, desplazamiento máximo).

    Greedy con unicidad, y es exacto a esta tolerancia: dos átomos distintos de
    una misma pose no están a 0.002 Å uno del otro, así que no hay ambigüedad
    que un algoritmo de asignación óptima pudiera resolver mejor. Si la hubiera,
    la unicidad falla y se abstiene en vez de elegir.
    """
    libres = list(range(len(registro)))
    maximo = 0.0
    for x, y, z in entregadas:
        candidatos = [
            (((registro[i][1] - x) ** 2 + (registro[i][2] - y) ** 2
              + (registro[i][3] - z) ** 2) ** 0.5, i)
            for i in libres
        ]
        candidatos = [(d, i) for d, i in candidatos if d <= tolerancia]
        if not candidatos:
            raise PoseNoRecuperable(
                "Una coordenada del bloque PDBQT entregado no aparece en el "
                f"registro recuperado (tolerancia {tolerancia} A). El registro "
                "describe otra geometría."
            )
        if len(candidatos) > 1:
            raise PoseNoRecuperable(
                "Dos átomos del registro coinciden con la misma coordenada "
                "entregada; la correspondencia no es biyectiva y no se elige "
                "una por conveniencia."
            )
        distancia, indice = candidatos[0]
        libres.remove(indice)
        maximo = max(maximo, distancia)
    sobrantes = [registro[i][0].upper() for i in libres]
    no_hidrogenos = [s for s in sobrantes if s not in ("H", "D")]
    if no_hidrogenos:
        raise PoseNoRecuperable(
            f"El registro tiene {len(no_hidrogenos)} átomo(s) pesado(s) sin "
            "contrapartida en el bloque entregado "
            f"({', '.join(sorted(set(no_hidrogenos)))}): no es esta pose."
        )
    return len(entregadas), maximo


def _pesados(atomos: list[tuple[str, float, float, float]]) -> dict[str, int]:
    conteo: dict[str, int] = {}
    for elemento, *_ in atomos:
        simbolo = elemento.upper()
        if simbolo in ("H", "D"):
            continue
        conteo[simbolo] = conteo.get(simbolo, 0) + 1
    return conteo


async def recuperar_pose_agrupada(
    pose: DockingPose,
    *,
    tolerancia_A: float = TOLERANCIA_A,
) -> PoseRecuperada:
    """
    Devuelve el registro SDF de esa pose, demostrado, o levanta explicando qué falta.

    Args:
        pose: una pose de una piscina de ensemble, con `source_provenance`.

    Raises:
        PoseNoRecuperable: cualquier puerta que no pase. El mensaje dice cuál.
    """
    procedencia = pose.source_provenance
    if not isinstance(procedencia, dict):
        raise PoseNoRecuperable(
            "La pose no conserva procedencia: es anterior a este contrato y no "
            "se puede reconstruir retroactivamente."
        )

    # ── G1: procedencia completa ──────────────────────────────────────
    archivo = procedencia.get("poses_file_path")
    rank = procedencia.get("rank")
    huella_archivo = procedencia.get("poses_file_sha256")
    entrada = procedencia.get("ligand_input") or {}
    conformero = entrada.get("conformer_path")
    huella_conformero = entrada.get("conformer_sha256")
    faltan = [
        nombre for nombre, valor in (
            ("poses_file_path", archivo),
            ("rank", rank),
            ("poses_file_sha256", huella_archivo),
            ("ligand_input.conformer_path", conformero),
            ("ligand_input.conformer_sha256", huella_conformero),
        ) if not valor
    ]
    if faltan:
        raise PoseNoRecuperable(
            "Procedencia incompleta: falta " + ", ".join(faltan) + ". Un dato "
            "ausente no se sustituye por el de otra corrida."
        )
    if not pose.pdbqt_block:
        raise PoseNoRecuperable(
            "La pose no conserva su bloque PDBQT, que es contra lo que se "
            "comprueba la correspondencia. Sin él no hay nada que demostrar."
        )

    # ── G2 y G3: integridad del artefacto y de la entrada ─────────────
    if await _sha256(archivo, "el archivo de poses") != huella_archivo:
        raise PoseNoRecuperable(
            f"El archivo de poses cambió desde la corrida ({archivo}): su "
            "SHA-256 no coincide con el registrado."
        )
    if await _sha256(conformero, "la conformación de entrada") != huella_conformero:
        raise PoseNoRecuperable(
            f"La conformación de entrada cambió desde la corrida ({conformero}): "
            "su SHA-256 no coincide con el registrado."
        )

    # ── G4: el registro existe donde dice el rank ─────────────────────
    contenido = (await read_bytes(archivo)).decode("utf-8", errors="strict")
    registros = _registros(contenido)
    if not 1 <= int(rank) <= len(registros):
        raise PoseNoRecuperable(
            f"El rank original {rank} cae fuera del archivo, que tiene "
            f"{len(registros)} registro(s)."
        )
    registro = registros[int(rank) - 1]
    atomos = _atomos_de_registro_sdf(registro)

    # ── G5: identidad química contra la entrada, no contra el SMILES ──
    entrada_atomos = _atomos_de_registro_sdf(
        _registros((await read_bytes(conformero)).decode("utf-8", errors="strict"))[0]
    )
    if _pesados(atomos) != _pesados(entrada_atomos):
        raise PoseNoRecuperable(
            "Los átomos pesados del registro no son los de la conformación que "
            f"se acopló: {_pesados(atomos)} frente a {_pesados(entrada_atomos)}."
        )

    # ── G6: correspondencia geométrica con lo que se entregó ──────────
    entregadas, pseudoatomos = _coordenadas_de_pdbqt(pose.pdbqt_block)
    verificados, maximo = _correspondencia_geometrica(
        entregadas, atomos, tolerancia_A
    )
    if verificados == 0:
        raise PoseNoRecuperable(
            "El bloque PDBQT entregado no contiene coordenadas legibles; no se "
            "puede demostrar correspondencia con nada."
        )

    log.info(
        "pose_agrupada_recuperada",
        archivo=archivo,
        rank=int(rank),
        conformer_index=pose.conformer_index,
        atomos=verificados,
        pseudoatomos_de_pegado=pseudoatomos,
        max_desplazamiento_A=round(maximo, 6),
    )
    return PoseRecuperada(
        sdf_record=registro,
        poses_file_path=str(archivo),
        rank_original=int(rank),
        conformer_index=pose.conformer_index,
        conformer_path=str(conformero),
        atomos_verificados=verificados,
        max_desplazamiento_A=maximo,
        pseudoatomos_de_pegado=pseudoatomos,
    )
