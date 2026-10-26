"""
Docking de ensemble: K corridas de Vina, una piscina de poses.

# La semántica, dicha entera

Cada conformación de entrada entra a Vina por separado. Las K×N poses que salen
se juntan en UNA piscina, se reordenan por afinidad observada y se entregan las
mejores `num_poses`. Cada pose recuerda de qué conformación salió.

    30 conformaciones × 9 poses = 270 candidatas
    piscina reordenada por afinidad
    top-9 entregado, cada pose con su `conformer_index`

# Por qué la procedencia por pose no es un adorno

Sin ella, la pose 1 podría venir de la conformación 3 y la 2 de la 17 sin que
nada lo dijera. El lector no podría distinguir «la misma solución encontrada dos
veces desde puntos de partida distintos» —que es evidencia de robustez— de «dos
soluciones distintas» —que es ambigüedad—. Es exactamente la lectura que el
ensemble existe para permitir, y se pierde entera si no se guarda de dónde vino
cada pose.

# Lo que este módulo NO hace

No cambia la afinidad de ninguna pose, no minimiza, no descarta poses por su
geometría —de eso se encarga la validación física, después— y no promete que
más conformaciones den mejor top-1. La medición interna dice lo contrario: el
ensemble amplía COBERTURA, y el cuello de botella se desplaza a la selección.

# Degradación

Si una corrida de Vina falla, las demás siguen y la corrida entera se declara
con menos cobertura de la pedida. Perder 29 conformaciones porque la número 17
no acopló sería un precio absurdo.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from copy import deepcopy
from typing import Any

from core.models import DockingPose, DockingResult
from services.avisos import normalizar_avisos
from utils.local_storage import read_bytes
from utils.logger import get_logger

log = get_logger(__name__)


def agrupar_avisos_repetidos(avisos: list[Any], *, acopladas: int) -> list[Any]:
    """CAS-07: una reserva del sistema aparece UNA vez, con su recuento.

    El receptor que acopla el ensemble es el mismo para las K
    conformaciones: sus reservas (protonación, aguas del sitio) llegaban una
    vez por conformación y el resultado guardaba 30 copias idénticas de cada
    una — 64 avisos donde la corrida única tiene cinco. No son 30 decisiones;
    es una, repetida por el mecanismo de fusión.

    La regla:

    - Un aviso estructurado (código/severidad/mensaje idénticos) repetido en
      TODAS las conformaciones que acoplaron se emite una vez con
      «(Aviso idéntico en las N conformaciones que acoplaron.)».
    - Repetido en algunas, con «(Repetido en n de N conformaciones.)»: el
      recuento parcial también se dice.
    - Lo que no es repetición — un aviso exclusivo de una conformación, un
      fallo de acoplamiento, el resumen del ensemble — viaja tal cual: son
      incidencias particulares, no eco del sistema.

    Los avisos en cadena (los fallos y el resumen, históricamente texto
    suelto) pasan intactos: agruparlos exigiría adivinarles un código que
    nadie declaró.
    """
    repeticiones = Counter(
        (a.get("codigo"), a.get("severidad"), a.get("mensaje"))
        for a in avisos
        if isinstance(a, dict)
    )

    agrupados: list[Any] = []
    vistos: set[tuple[Any, Any, Any]] = set()
    for aviso_actual in avisos:
        if not isinstance(aviso_actual, dict):
            agrupados.append(aviso_actual)
            continue
        clave = (
            aviso_actual.get("codigo"),
            aviso_actual.get("severidad"),
            aviso_actual.get("mensaje"),
        )
        if clave in vistos:
            continue
        vistos.add(clave)
        veces = repeticiones[clave]
        if veces <= 1:
            agrupados.append(aviso_actual)
            continue
        mensaje = str(aviso_actual.get("mensaje") or "")
        if veces == acopladas:
            nota = f" (Aviso idéntico en las {veces} conformaciones que acoplaron.)"
        else:
            nota = f" (Repetido en {veces} de {acopladas} conformaciones.)"
        agrupados.append({**aviso_actual, "mensaje": mensaje + nota})
    return agrupados


async def _informar(callback, hechas: int, total: int) -> None:
    """
    Publica el avance. Un fallo aquí NO puede tumbar el acoplamiento.

    El progreso es cortesía; las poses son el producto. Perder una corrida de
    treinta conformaciones porque el bus de eventos parpadeó sería absurdo.
    """
    if callback is None:
        return
    try:
        await callback(hechas, total)
    except Exception as exc:                                       # noqa: BLE001
        log.debug("ensemble_progreso_no_publicado", error=str(exc)[:120])


def _con_procedencia(pose: DockingPose, indice: int) -> DockingPose:
    """Copia la pose sellando de qué conformación vino."""
    return pose.model_copy(update={"conformer_index": indice})


def _entrada_de(conformero: dict[str, Any]) -> dict[str, Any]:
    """La identidad de la geometría que entró a Vina en esa corrida.

    Sin esto, `conformer_index` es una etiqueta y nada más: dice de qué
    conformación se DICE que salió la pose, no qué archivo se acopló. Es la
    diferencia que hizo invisible el defecto ENS-05 durante toda su vida, cuando
    las K corridas recibían la geometría de la conformación 0 y cada pose
    declaraba una procedencia distinta.
    """
    datos = {
        "conformer_path": conformero.get("conformer_path"),
        "conformer_sha256": conformero.get("conformer_sha256"),
        "semilla_conformacional": conformero.get("semilla"),
    }
    # Un diccionario de Nones aparenta un registro que no existe. Si no se sabe
    # nada de la entrada, se dice que no se sabe nada.
    return datos if any(valor is not None for valor in datos.values()) else None


async def _huella_de_archivo(object_name: str | None) -> str | None:
    """SHA-256 del artefacto de poses de una corrida, si se puede leer.

    Es lo que convierte «el registro 3 de este archivo» en una afirmación
    comprobable: sin el hash, recuperar una pose por rank confía en que el
    archivo no haya cambiado, que es justo lo que ENS-04 no aceptó dar por
    supuesto. None significa «no se pudo leer», y quien lo reciba se abstiene.
    """
    if not object_name:
        return None
    try:
        return hashlib.sha256(await read_bytes(object_name)).hexdigest()
    except Exception as exc:                                       # noqa: BLE001
        log.warning("ensemble_artefacto_sin_huella",
                    archivo=object_name, error=str(exc)[:120])
        return None


#: Lo que describe la corrida ENTERA y vale igual para las K conformaciones: la
#: caja y el receptor entran en la huella del caché de Vina, así que dos corridas
#: con valores distintos no pueden haber compartido resultado.
_PROCEDENCIA_COMUN = (
    "box_center", "box_size", "receptor_sha256", "receta_receptor",
    "receptor_prep", "toolchain", "cpu", "app_version", "git_commit",
)

#: Lo que describe UNA corrida de Vina: su ligando, su registro y su archivo de
#: poses. Poner uno solo de estos valores a nivel de la piscina afirmaría que
#: ese archivo contiene las poses entregadas, y no las contiene (son K archivos).
#: `search_trace` tampoco se agrupa: es la traza de una búsqueda, no de la mezcla.
_PROCEDENCIA_POR_CONFORMACION = (
    "ligand_input_sha256", "ligand_input_path", "ligand_pdbqt_sha256",
    "ligand_pdbqt_path", "log_path", "log_sha256", "poses_sha256",
)


def _comparable(valor: Any) -> Any:
    """Los vectores se comparan a 3 decimales, igual que la huella del caché."""
    if (isinstance(valor, (list, tuple)) and valor
            and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in valor)):
        return tuple(round(float(v), 3) for v in valor)
    return valor


def _procedencia(resultado: DockingResult) -> dict[str, Any]:
    procedencia = getattr(resultado, "execution_provenance", None)
    return procedencia if isinstance(procedencia, dict) else {}


def agrupar_procedencia(
    resultados: list[tuple[int, DockingResult]],
    detalles: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """La procedencia de ejecución de la piscina, o `None` si ninguna corrida la tiene.

    El agrupado la perdía entera: el `DockingResult` de la piscina se construía
    sin `execution_provenance`, y la corrida de ensemble quedaba guardada sin
    caja, sin `receptor_prep` y sin toolchain. Moldex la listaba, pero lo que
    necesita una caja verificable (Molcy, el dossier, la comparación SAR) la
    daba por no disponible.

    Reglas, para no inventar lo que no se midió:

    - Un campo común se conserva sólo si TODAS las corridas que acoplaron lo
      traen y coinciden. Si alguna difiere o no lo trae (una caché de otra
      versión de la app, un resultado heredado) queda en `None` y se nombra en
      `campos_heterogeneos`: ni se hereda de la primera corrida ni se tumba la
      evaluación por ello.
    - Lo que es de UNA corrida de Vina viaja en `por_conformacion`, nunca a
      nivel de la piscina. `detalles` suma lo que sólo el ensemble sabe de cada
      conformación (su semilla, su energía MMFF, dónde quedó su archivo de poses,
      cuántas poses dio y la mejor): con eso un lector sabe de cuántas candidatas
      salieron las entregadas sin tener que interpretar un aviso de texto.
    """
    procedencias = [(indice, _procedencia(resultado)) for indice, resultado in resultados]
    if not any(procedencia for _, procedencia in procedencias):
        return None

    agrupada: dict[str, Any] = {}
    heterogeneos: list[str] = []
    for campo in _PROCEDENCIA_COMUN:
        valores = [procedencia.get(campo) for _, procedencia in procedencias]
        primero = valores[0]
        if primero is not None and all(
            _comparable(valor) == _comparable(primero) for valor in valores
        ):
            agrupada[campo] = deepcopy(primero)
            continue
        agrupada[campo] = None
        if any(valor is not None for valor in valores):
            heterogeneos.append(campo)
    if heterogeneos:
        agrupada["campos_heterogeneos"] = heterogeneos

    agrupada["por_conformacion"] = [
        {
            "indice": indice,
            **{
                campo: deepcopy(procedencia[campo])
                for campo in _PROCEDENCIA_POR_CONFORMACION
                if procedencia.get(campo) is not None
            },
            **{
                campo: valor
                for campo, valor in (detalles or {}).get(indice, {}).items()
                if valor is not None
            },
        }
        for indice, procedencia in procedencias
    ]
    return agrupada


def _caja_de(resultado: DockingResult) -> tuple[Any, Any] | None:
    procedencia = _procedencia(resultado)
    centro, lado = _comparable(procedencia.get("box_center")), _comparable(procedencia.get("box_size"))
    return (centro, lado) if centro is not None and lado is not None else None


def agrupar_poses(
    resultados: list[tuple[int, DockingResult]],
    num_poses: int,
    entradas: dict[int, dict[str, Any]] | None = None,
    huellas: dict[int, str | None] | None = None,
) -> list[DockingPose]:
    """
    La piscina: junta, reordena por afinidad y renumera.

    El `rank` se REASIGNA sobre la piscina porque el que traía cada pose era su
    posición dentro de SU corrida de Vina: sin renumerar habría nueve poses con
    rank 1. El orden es por afinidad observada, que es el único criterio que
    Vina ofrece y el mismo que usa el camino de una sola conformación.

    `entradas` asocia cada índice de conformación con la identidad del `.sdf`
    que se acopló, y `huellas` con el SHA-256 del artefacto de poses de esa
    corrida. Ambos son opcionales para no romper a los llamantes existentes: lo
    que no se recibe se declara ausente, nunca se rellena con el de otra
    corrida. Juntos son lo que permite recuperar después el registro exacto de
    una pose y DEMOSTRAR que es esa (ver `services/docking/pose_recovery.py`).
    """
    piscina: list[DockingPose] = []
    for indice, resultado in resultados:
        for pose in resultado.poses or []:
            copia = _con_procedencia(pose, indice)
            copia.source_provenance = deepcopy({
                "rank": pose.rank,
                "poses_file_path": resultado.poses_file_path,
                "poses_file_sha256": (huellas or {}).get(indice),
                "parsing_source": resultado.parsing_source,
                "conversor_estructural": resultado.conversor_estructural,
                "ligand_input": (entradas or {}).get(indice),
            })
            piscina.append(copia)

    # Empate resuelto por conformación y rank original: dos poses con la misma
    # afinidad tienen que salir siempre en el mismo orden, o el paquete
    # reproducible dejaría de serlo.
    piscina.sort(key=lambda p: (p.affinity, p.conformer_index or 0, p.rank))

    entregadas: list[DockingPose] = []
    for posicion, pose in enumerate(piscina[:num_poses], start=1):
        entregadas.append(pose.model_copy(update={"rank": posicion}))
    return entregadas


async def run_ensemble_docking(
    *,
    smiles: str,
    conformeros: list[dict[str, Any]],
    num_poses: int,
    dock_una,
    on_progress=None,
) -> DockingResult:
    """
    Dockea cada conformación y devuelve la piscina como un `DockingResult`.

    Args:
        conformeros: salida de `generate_conformer_ensemble()["conformers"]`.
        dock_una: `async (smiles_hash, smiles) -> DockingResult`. Se inyecta
            para que este módulo no dependa de `vina_service` —y para poder
            probar la semántica de agrupación sin ejecutar Vina.
        on_progress: `async (hechas, total) -> None`, opcional. Se llama al
            terminar cada conformación con el recuento REAL. Con K alto la
            etapa pasa de instantánea a minutos, y una barra sin datos que la
            respalden sería una animación que finge saber cuánto falta.

    NUNCA devuelve un resultado sin poses si al menos una corrida las produjo.
    Si NINGUNA las produjo, propaga el fallo: una molécula sin ninguna pose no
    es una molécula con cobertura reducida, es una evaluación sin docking.
    """
    resultados: list[tuple[int, DockingResult]] = []
    entradas: dict[int, dict[str, Any]] = {}
    huellas: dict[int, str | None] = {}
    detalles: dict[int, dict[str, Any]] = {}
    avisos: list[str] = []
    tiempo_total = 0.0
    fuentes: set[str] = set()

    total = len(conformeros)
    for hechas, conformero in enumerate(conformeros, start=1):
        indice = int(conformero.get("indice", 0))
        try:
            parcial = await dock_una(
                smiles_hash=conformero["smiles_hash"],
                smiles=smiles,
            )
        except Exception as exc:                                   # noqa: BLE001
            avisos.append(
                f"La conformación {indice} no se pudo acoplar "
                f"({type(exc).__name__}); las demás siguen."
            )
            log.warning("ensemble_conformero_fallido", indice=indice, error=str(exc)[:200])
            await _informar(on_progress, hechas, total)
            continue
        if not parcial or not parcial.poses:
            avisos.append(f"La conformación {indice} no produjo poses.")
            await _informar(on_progress, hechas, total)
            continue
        # A single pooled provenance is valid only for a homogeneous protocol.
        # Keep this outside the recoverable docking exception: a mismatch is an
        # integrity failure, not reduced conformational coverage. Missing data
        # must not inherit another run's known provenance either.
        if resultados:
            referencia = resultados[0][1]
            campos = (
                "receptor_sha256", "vina_version", "vina_random_seed",
                "engine_efectivo", "exhaustiveness_efectiva", "num_poses_solicitadas",
            )
            incompatibles = [
                campo for campo in campos
                if getattr(referencia, campo, None) != getattr(parcial, campo, None)
            ]
            # Dos cajas distintas no pueden compartir piscina: sus poses viven
            # en regiones distintas del receptor. Si a una corrida le falta la
            # caja no es incompatibilidad, es un dato ausente (ver
            # `agrupar_procedencia`).
            cajas = (_caja_de(referencia), _caja_de(parcial))
            if None not in cajas and cajas[0] != cajas[1]:
                incompatibles.append("box_center/box_size")
            if incompatibles:
                log.error("ensemble_procedencia_incompatible", indice=indice,
                          campos=incompatibles)
                raise RuntimeError(
                    f"Ensemble: procedencia incompatible en conformacion {indice}: "
                    + ", ".join(incompatibles)
                )
        resultados.append((indice, parcial))
        entradas[indice] = _entrada_de(conformero)
        huellas[indice] = await _huella_de_archivo(parcial.poses_file_path)
        detalles[indice] = {
            "semilla_conformacional": conformero.get("semilla"),
            "energia_mmff": conformero.get("energia"),
            # SCI-A-025: con qué se minimizó ESTA conformación (None si no consta).
            "minimizacion": conformero.get("minimizacion"),
            "poses_file_path": parcial.poses_file_path,
            "num_poses": len(parcial.poses),
            "mejor_afinidad_kcal_mol": parcial.best_affinity,
        }
        tiempo_total += float(getattr(parcial, "execution_time_s", 0.0) or 0.0)
        fuentes.add(parcial.parsing_source)
        # Se normalizan al fusionar: un ensemble puede mezclar corridas nuevas
        # (con severidad) y heredadas (cadenas sueltas) en la misma lista.
        avisos.extend(normalizar_avisos(getattr(parcial, "scientific_warnings", None)))
        await _informar(on_progress, hechas, total)

    if not resultados:
        raise RuntimeError(
            "Ninguna conformación del ensemble produjo poses: no hay acoplamiento "
            "que documentar."
        )

    entregadas = agrupar_poses(resultados, num_poses, entradas, huellas)
    conformaciones_con_poses = len({indice for indice, _ in resultados})
    representadas = len({p.conformer_index for p in entregadas})

    # CAS-07: cada conformación acopló el MISMO receptor y arrastró una
    # copia de sus reservas. Se agrupan con su recuento — quien revisa un caso
    # repetidamente no necesita 30 copias idénticas, y el bloque de
    # incertidumbres del PDF tampoco. Las incidencias particulares y el
    # resumen de abajo viajan intactos.
    avisos = agrupar_avisos_repetidos(avisos, acopladas=conformaciones_con_poses)

    # El denominador dicho en voz alta, igual que en las cohortes: «9 poses» no
    # significa nada si no se sabe de cuántas candidatas salieron.
    avisos.append(
        f"Ensemble conformacional: {conformaciones_con_poses} de "
        f"{len(conformeros)} conformaciones acoplaron; "
        f"{sum(len(r.poses or []) for _, r in resultados)} poses candidatas "
        f"reordenadas por afinidad, {len(entregadas)} entregadas desde "
        f"{representadas} conformación(es). El ensemble amplía la cobertura "
        f"geométrica; no mejora, por sí solo, la elección de la pose top-1."
    )

    # ── La traza de reproducibilidad SOBREVIVE al agrupado ───────────
    #
    # Sin esto, el ensemble habria producido un resultado sin version de motor,
    # sin semilla y sin hash del receptor: el dossier los declararia «no
    # informado» y la validacion fisica se abstendria por RECEPTOR_SIN_HUELLA.
    # El ensemble habria roto, de rebote, todo el aparato de procedencia.
    #
    # Se toman de la PRIMERA corrida con poses: las K comparten receptor y
    # binario por construccion, y la semilla base es la misma. Lo que cambia
    # entre corridas es la conformacion de entrada, y eso viaja por pose.
    # `execution_provenance` (caja, receptor preparado, toolchain) se agrupa
    # con `agrupar_procedencia`: sin ella la corrida se guardaba en Moldex pero
    # ninguna fuente que exigiera una caja verificable podia usarla.
    primera = resultados[0][1]
    winning_index = entregadas[0].conformer_index
    winning_result = next(
        (partial for index, partial in resultados if index == winning_index), None
    )
    winning_hotspots = (
        deepcopy(winning_result.hotspots_hit) if winning_result is not None else None
    )

    return DockingResult(
        best_affinity=entregadas[0].affinity,
        poses=entregadas,
        # La piscina mezcla archivos de K corridas. Apuntar al SDF de la
        # primera presentaría coordenadas distintas de las poses entregadas.
        # Los bloques PDBQT por pose sí sobreviven y son la fuente exacta.
        poses_file_path=None,
        parsing_source=next(iter(fuentes)) if len(fuentes) == 1 else "mixed",
        conversor_estructural=(
            deepcopy(primera.conversor_estructural)
            if all(r.conversor_estructural == primera.conversor_estructural
                   for _, r in resultados) else None
        ),
        engine_efectivo=primera.engine_efectivo,
        exhaustiveness_efectiva=primera.exhaustiveness_efectiva,
        num_poses_solicitadas=primera.num_poses_solicitadas,
        vina_version=getattr(primera, "vina_version", None),
        vina_random_seed=getattr(primera, "vina_random_seed", None),
        receptor_sha256=getattr(primera, "receptor_sha256", None),
        receptor_path=getattr(primera, "receptor_path", None),
        execution_provenance=agrupar_procedencia(resultados, detalles),
        execution_time_s=tiempo_total,
        scientific_warnings=avisos,
        hotspots_hit=winning_hotspots,
    )
