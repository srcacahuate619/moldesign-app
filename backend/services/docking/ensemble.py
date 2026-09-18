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

from typing import Any

from core.models import DockingPose, DockingResult
from services.avisos import normalizar_avisos
from utils.logger import get_logger

log = get_logger(__name__)


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


def agrupar_poses(
    resultados: list[tuple[int, DockingResult]],
    num_poses: int,
) -> list[DockingPose]:
    """
    La piscina: junta, reordena por afinidad y renumera.

    El `rank` se REASIGNA sobre la piscina porque el que traía cada pose era su
    posición dentro de SU corrida de Vina: sin renumerar habría nueve poses con
    rank 1. El orden es por afinidad observada, que es el único criterio que
    Vina ofrece y el mismo que usa el camino de una sola conformación.
    """
    piscina: list[DockingPose] = []
    for indice, resultado in resultados:
        for pose in resultado.poses or []:
            piscina.append(_con_procedencia(pose, indice))

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
    avisos: list[str] = []
    tiempo_total = 0.0
    fuente = "sdf"

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
            if incompatibles:
                log.error("ensemble_procedencia_incompatible", indice=indice,
                          campos=incompatibles)
                raise RuntimeError(
                    f"Ensemble: procedencia incompatible en conformacion {indice}: "
                    + ", ".join(incompatibles)
                )
        resultados.append((indice, parcial))
        tiempo_total += float(getattr(parcial, "execution_time_s", 0.0) or 0.0)
        fuente = parcial.parsing_source
        # Se normalizan al fusionar: un ensemble puede mezclar corridas nuevas
        # (con severidad) y heredadas (cadenas sueltas) en la misma lista.
        avisos.extend(normalizar_avisos(getattr(parcial, "scientific_warnings", None)))
        await _informar(on_progress, hechas, total)

    if not resultados:
        raise RuntimeError(
            "Ninguna conformación del ensemble produjo poses: no hay acoplamiento "
            "que documentar."
        )

    entregadas = agrupar_poses(resultados, num_poses)
    conformaciones_con_poses = len({indice for indice, _ in resultados})
    representadas = len({p.conformer_index for p in entregadas})

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
    primera = resultados[0][1]

    return DockingResult(
        best_affinity=entregadas[0].affinity,
        poses=entregadas,
        # La piscina mezcla archivos de K corridas. Apuntar al SDF de la
        # primera presentaría coordenadas distintas de las poses entregadas.
        # Los bloques PDBQT por pose sí sobreviven y son la fuente exacta.
        poses_file_path=None,
        parsing_source=fuente,
        engine_efectivo=primera.engine_efectivo,
        exhaustiveness_efectiva=primera.exhaustiveness_efectiva,
        num_poses_solicitadas=primera.num_poses_solicitadas,
        vina_version=getattr(primera, "vina_version", None),
        vina_random_seed=getattr(primera, "vina_random_seed", None),
        receptor_sha256=getattr(primera, "receptor_sha256", None),
        receptor_path=getattr(primera, "receptor_path", None),
        execution_time_s=tiempo_total,
        scientific_warnings=avisos,
    )
