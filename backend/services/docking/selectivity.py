"""
services/docking/selectivity.py

Multi-target selectivity panel for drug safety profiling.

Docks the same molecule against a panel of anti-targets
to compute a selectivity score: ON_target / max(OFF_target).

Anti-targets are proteins whose inhibition causes toxicity:
- hERG (KCNH2): cardiac potassium channel -> arrhythmia
- CYP3A4: drug metabolism -> drug-drug interactions
- 5-HT2B: serotonin receptor -> cardiac valvulopathy
- PDE3: phosphodiesterase -> cardiac contractility
- NavAb is a bacterial channel; it is not a NaV1.5 safety assay.

All structures from RCSB PDB, pre-cached locally.

Referencias:

  Bowes et al. (2012) "Reducing safety-related drug attrition: the use of in
  vitro pharmacological profiling". Nature Reviews Drug Discovery.
  — de donde sale la composición del panel.

  Zhu Y., Rahman T. (2026) "Benchmarking co-folding tools on Nav, Cav and Kv
  channels". Frontiers in Biophysics 4:1937302.
  — por qué hERG (5VA1) se acopla sobre la estructura
  experimental ensamblada y no sobre un modelo de co-plegamiento: en canales
  de membrana esas herramientas colapsan la cavidad del poro, que es
  justamente lo que el panel mide. Ver `anti_target_sitio.py`.

v1.5 (Julio 2026): Reemplazado ThreadPoolExecutor + asyncio.new_event_loop()
por asyncio.Semaphore + await directo. El patron anterior era incompatible con
ProactorEventLoop de Windows (subprocess en threads no-principales causaba
deadlocks y fugas de handles).
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from services.docking.selectividad_margen import margen_de_selectividad
from services.docking.anti_target_sitio import (
    AntiDianaSinSitio,
    resolver_sitio_de_anti_diana,
)

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()

# -- Anti-target panel ----------------------------------------------------------
# Referencia: Bowes et al. 2012, Nat Rev Drug Discov 11:909-922, tabla 1: panel
# mínimo de 44 dianas asociadas a reacciones adversas, propuesto por
# AstraZeneca, GSK, Novartis y Pfizer (lo implementa SafetyScreen44 de Eurofins).
#
# Por defecto se acoplan dos dianas de ese panel con cavidad validada: hERG y
# 5-HT2B. CYP3A4 salió del panel predeterminado: no está entre las 44 (su
# inhibición es una interacción fármaco-fármaco, que ADMET ya estima) y su
# estructura 4NY4 no se puede preparar sin plantilla del hemo (DOCK-003).

ANTI_TARGET_PANEL = [
    {
        "pdb_id": "5VA1",
        "name": "hERG (KCNH2)",
        "chain": "A",
        "category": "Cardiac",
        "risk": "Arritmia cardiaca (QT prolongation). Retiro de Terfenadina, Cisaprida, Grepafloxacino.",
        "center": (73.15, 73.15, 78.53),
        "size": (28.8, 28.8, 30.0),
        "affinity_threshold": -7.0,
    },
    {
        "pdb_id": "7SRQ",
        "name": "5-HT2B (HTR2B)",
        "chain": "R",
        "category": "CNS/Safety",
        "risk": "Agonismo 5-HT2B causa valvulopatia cardiaca. Fenfluramina, Pergolida retirados.",
        "center": (152.587, 158.245, 155.595),
        "size": (18.0, 18.0, 18.0),
        "affinity_threshold": -7.5,
    },

]

#: Las 44 dianas del panel, con la estructura que cada una haya superado la
#: validación. Lo genera `scripts/build_bowes44_panel.py` desde un redocking real
#: del ligando cocristalizado; ver `docs/auditorias/ae4db6a/bowes44_validacion.json`.
RUTA_PANEL_BOWES = Path(__file__).resolve().parents[2] / "data" / "anti_dianas_bowes44.json"


@lru_cache(maxsize=1)
def panel_bowes_2012() -> list[dict[str, Any]]:
    """Las 44 dianas del panel mínimo de Bowes 2012, en el orden del archivo.

    Cada fila trae su `estado`. Sólo las `validada` pueden acoplarse: llevan
    caja, cadenas del sitio y las cifras del redocking que lo respaldan. Las
    demás se listan con su motivo y la interfaz no deja seleccionarlas.
    """
    try:
        datos = json.loads(RUTA_PANEL_BOWES.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        log.warning("panel_bowes_ilegible", ruta=str(RUTA_PANEL_BOWES), error=str(exc))
        return []
    return list(datos.get("dianas") or [])


def anti_dianas_seleccionables_de_bowes() -> dict[str, dict[str, Any]]:
    """Las del panel de Bowes que se pueden acoplar, por PDB ID."""
    return {
        str(fila["pdb_id"]).upper(): {
            "pdb_id": str(fila["pdb_id"]).upper(),
            "name": f"{fila['assay']} ({fila.get('gen') or '—'})",
            "chain": fila.get("chain") or "A",
            "category": f"Bowes 2012 · {fila.get('familia') or 'panel'}",
            "risk": fila.get("riesgo") or "",
            "center": tuple(fila["center"]),
            "size": tuple(fila["size"]),
            "site_chains": fila.get("site_chains"),
            "affinity_threshold": fila.get("affinity_threshold") or -7.0,
        }
        for fila in panel_bowes_2012()
        if fila.get("estado") == "validada" and fila.get("center") and fila.get("size")
    }




@dataclass
class SelectivityResult:
    on_target_affinity: float | None = None
    on_target_pdb: str = ""
    off_targets: list[dict] = field(default_factory=list)
    selectivity_ratio: float | None = None
    #: ΔΔG = ΔG_off − ΔG_on, en kcal/mol. La magnitud que manda.
    delta_delta_g_kcal: float | None = None
    #: La anti-diana que define el margen: la que une más fuerte.
    peor_anti_diana: str | None = None
    safety_flags: list[str] = field(default_factory=list)
    execution_time_s: float = 0.0
    #: Sobre cuántas anti-dianas se calculó el cociente, de cuántas se pidieron.
    #: El cociente es un mínimo sobre lo evaluado: con cobertura incompleta
    #: puede ser optimista, y sin estos dos números no hay forma de saberlo.
    anti_dianas_evaluadas: int = 0
    anti_dianas_solicitadas: int = 0


async def seleccionar_anti_dianas(
    anti_targets: list[str] | None,
    repository: Any | None = None,
) -> tuple[list[dict], list[str]]:
    """Las anti-dianas a evaluar y las que se pidieron y no existen.

    LO QUE ARREGLA. Aquí había un `[t for t in ANTI_TARGET_PANEL if t["pdb_id"]
    in anti_targets]`. La interfaz ofrece elegir también las anti-dianas subidas
    por el usuario —`/pro/anti-targets` las lista junto a las del panel—, y ese
    filtro las TIRABA en silencio: el usuario marcaba seis, se acoplaban cinco,
    y el cociente de selectividad se calculaba sobre las cinco sin decir que
    faltaba una. Un panel de seguridad que declara menos cobertura de la que
    aparenta es exactamente el defecto que este producto existe para no cometer.
    """
    por_id = {t["pdb_id"]: t for t in ANTI_TARGET_PANEL}
    # Las del panel de Bowes traen su caja y su sitio validados: mandan sobre el
    # catálogo y sobre la rama de «anti-diana del usuario».
    por_id.update({k: v for k, v in anti_dianas_seleccionables_de_bowes().items()
                   if k not in por_id})

    if anti_targets is None:
        return list(ANTI_TARGET_PANEL), []

    pedidas = [str(pid).strip().upper() for pid in anti_targets if str(pid).strip()]
    elegidas: list[dict] = []
    desconocidas: list[str] = []

    for pid in pedidas:
        if pid in por_id:
            elegidas.append(por_id[pid])
            continue
        # Anti-diana del usuario: su caja y su umbral viven en el catálogo.
        fila = None
        if repository is not None:
            try:
                fila = await repository.get_target_by_pdb_id(pid)
            except Exception as exc:  # noqa: BLE001 — se reporta, no se traga
                log.warning(
                    "anti_target_no_resuelta",
                    pdb_id=pid,
                    error=f"{type(exc).__name__}: {exc}",
                )
        if fila is None:
            desconocidas.append(pid)
            continue
        sugerida = por_id.get(pid, {})
        elegidas.append(
            {
                "pdb_id": pid,
                "name": sugerida.get("name") or getattr(fila, "name", None) or pid,
                "category": sugerida.get("category") or "Custom",
                "risk": sugerida.get("risk")
                or getattr(fila, "anti_target_risk", None)
                or f"Anti-diana aportada por el usuario: {getattr(fila, 'name', pid)}",
                "chain": getattr(fila, "chain", None) or "A",
                # Sin `center`/`size` a propósito: los toma del catálogo el
                # resolvedor, que además rechaza una caja en el origen.
                "affinity_threshold": getattr(fila, "affinity_threshold", None) or -7.0,
            }
        )

    return elegidas, desconocidas


def validar_protocolo_panel(protocol: dict[str, Any] | None) -> tuple[int, int, int]:
    """Exige que el docking anti-diana repita los parámetros Vina de la corrida."""
    if not isinstance(protocol, dict) or protocol.get("engine") != "vina":
        raise ValueError("Selectividad no comparable: falta protocolo Vina principal")
    if (protocol.get("conformers_generated") or 1) > 1:
        raise ValueError("Selectividad no comparable: ensemble principal sin ensemble anti-diana")
    values = tuple(protocol.get(key) for key in ("exhaustiveness", "num_poses", "seed"))
    if any(value is None or isinstance(value, bool) or not isinstance(value, int)
           for value in values):
        raise ValueError("Selectividad no comparable: protocolo Vina principal incompleto")
    exhaustiveness, num_poses, seed = values
    if exhaustiveness < 1 or num_poses < 1 or seed < 0:
        raise ValueError("Selectividad no comparable: parámetros Vina inválidos")
    return exhaustiveness, num_poses, seed


async def run_selectivity_panel(
    smiles: str,
    smiles_hash: str,
    on_target_pdb: str,
    on_target_affinity: float,
    num_workers: int = 2,
    anti_targets: list[str] | None = None,
    repository: Any | None = None,
    docking_protocol: dict[str, Any] | None = None,
) -> SelectivityResult:
    """
    Run docking against anti-target panel (async nativa, sin threads).

    Usa asyncio.Semaphore para limitar concurrencia de subprocesos Vina.
    Compatible con ProactorEventLoop de Windows.

    `repository` resuelve la composición del sitio de cada anti-diana contra el
    catálogo. Sin él, una anti-diana cuyo sitio abarque varias cadenas se
    prepararía con una sola —media cavidad— y el panel devolvería un número de
    seguridad sobre un bolsillo que no existe.
    """
    import time
    from services.docking.vina_service import run_vina_docking

    start = time.monotonic()
    exhaustiveness, num_poses, seed = validar_protocolo_panel(docking_protocol)

    targets, desconocidas = await seleccionar_anti_dianas(anti_targets, repository)

    if not targets and not desconocidas:
        return SelectivityResult(
            on_target_affinity=on_target_affinity,
            on_target_pdb=on_target_pdb,
        )

    sem = asyncio.Semaphore(num_workers)

    async def dock_one(at: dict) -> dict:
        pdb_id = at["pdb_id"]
        # ── El sitio, resuelto contra el catálogo ANTES de acoplar ───────────
        # Ver `anti_target_sitio.py`: hERG (5VA1) declara
        # `site_chains` de dos y tres cadenas, y este camino las preparaba con
        # una. Son las dos anti-dianas cardíacas del panel.
        sitio = await resolver_sitio_de_anti_diana(at, repository) if repository else None
        if isinstance(sitio, AntiDianaSinSitio):
            log.warning("anti_target_sin_sitio", target=pdb_id, motivo=sitio.motivo)
            return {
                "pdb_id": pdb_id,
                "name": at["name"],
                "category": at.get("category", "Safety"),
                "risk": at.get("risk", ""),
                "affinity": None,
                "poses": 0,
                "threshold": at.get("affinity_threshold", -7.0),
                "status": "sin_sitio",
                "error": sitio.motivo,
            }

        async with sem:
            try:
                docking = await run_vina_docking(
                    smiles_hash=smiles_hash,
                    smiles=smiles,
                    target_pdb_id=pdb_id,
                    target_chain=sitio.chain if sitio else at.get("chain", "A"),
                    target_center=sitio.center if sitio else at.get("center"),
                    target_size=sitio.size if sitio else at.get("size"),
                    site_chains=sitio.site_chains if sitio else None,
                    exhaustiveness=exhaustiveness,
                    num_poses=num_poses,
                    seed=seed,
                )
                return {
                    "pdb_id": pdb_id,
                    "name": at["name"],
                    "category": at.get("category", "Safety"),
                    "risk": at.get("risk", ""),
                    "affinity": docking.best_affinity if docking else None,
                    "poses": len(docking.poses) if docking and docking.poses else 0,
                    "threshold": at["affinity_threshold"],
                    "site_chains": sitio.site_chains if sitio else None,
                    "procedencia_caja": sitio.procedencia_caja if sitio else "panel",
                    "docking_protocol": {"engine": "vina", "exhaustiveness": exhaustiveness,
                                         "num_poses": num_poses, "seed": seed,
                                         "smiles_hash": smiles_hash},
                    "status": "ok",
                }
            except Exception as e:
                error_msg = str(e)[:200]
                if "ProteinPreparation" in str(type(e).__name__) or "prepare" in error_msg.lower():
                    status = "unpreparable"
                    reason = "PDB no se pudo preparar para docking"
                elif "VinaExecutable" in str(type(e).__name__) or "vina" in error_msg.lower():
                    status = "no_vina"
                    reason = "Vina no encontrado"
                elif "download" in error_msg.lower() or "rcsb" in error_msg.lower() or "PDB" in error_msg:
                    status = "no_pdb"
                    reason = "Estructura PDB no disponible"
                elif "timeout" in error_msg.lower():
                    status = "timeout"
                    reason = "Timeout -- docking excedio el tiempo limite"
                else:
                    status = "failed"
                    reason = error_msg

                log.warning("anti_target_failed", target=pdb_id, status=status)
                return {
                    "pdb_id": pdb_id,
                    "name": at["name"],
                    "category": at.get("category", "Safety"),
                    "risk": at.get("risk", ""),
                    "affinity": None,
                    "poses": 0,
                    "status": status,
                    "error": reason,
                }

    results = await asyncio.gather(
        *[dock_one(t) for t in targets],
        return_exceptions=True,
    )
    results = [r for r in results if isinstance(r, dict)]

    # -- Compute selectivity metrics --------------------------------------------
    safety_flags = [
        "Los scores de Vina entre receptores distintos no son energías libres "
        "experimentales directamente comparables; el margen es exploratorio."
    ]
    # `None` hasta que alguna anti-diana devuelva afinidad. Antes empezaba en
    # 0.0, que además de ser un valor que ninguna anti-diana produce, hacía que
    # «no se une a ninguna» —el mejor caso— fuera indistinguible de «no se
    # evaluó ninguna».
    worst_off_affinity: float | None = None
    peor_anti_diana: str | None = None

    # Lo que se pidió y no existe se DECLARA. Antes desaparecía del filtro y el
    # cociente salía calculado sobre menos anti-dianas de las que el usuario
    # había marcado, sin ninguna señal de que faltara ninguna.
    for pid in desconocidas:
        safety_flags.append(
            f"NO EVALUADA {pid}: se pidió como anti-diana y no está ni en el panel "
            f"ni en el catálogo de este equipo. El cociente de selectividad de abajo "
            f"NO la incluye."
        )
        results.append(
            {
                "pdb_id": pid,
                "name": pid,
                "category": "Safety",
                "risk": "",
                "affinity": None,
                "poses": 0,
                "threshold": -7.0,
                "status": "desconocida",
                "error": "no está en el panel ni en el catálogo de este equipo",
            }
        )

    for r in results:
        aff = r.get("affinity")
        threshold = r.get("threshold", -7.0)
        if aff is not None:
            if aff < threshold:
                safety_flags.append(
                    f"ALERTA {r['name']}: afinidad {aff:.1f} kcal/mol < umbral {threshold:.1f}. "
                    f"Riesgo: {r.get('risk', 'Desconocido')}"
                )
            if worst_off_affinity is None or aff < worst_off_affinity:
                worst_off_affinity = aff
                peor_anti_diana = r.get("name") or r.get("pdb_id")
        elif r.get("status") == "sin_sitio":
            safety_flags.append(
                f"NO EVALUADA {r['name']}: {r.get('error', 'sin sitio resoluble')}"
            )
        elif r.get("status") != "desconocida":
            safety_flags.append(f"Sin datos para {r['name']} -- no se pudo evaluar")

    # ── El margen, en kcal/mol ──────────────────────────────────────────────
    #
    # `selectivity_ratio` era ΔG_on / ΔG_off: un cociente de energías libres, sin
    # sentido termodinámico, que daba el MISMO 2.00 a un margen de 5 kcal/mol y
    # a uno de 3 —un factor de treinta de diferencia— y se indefinía justo
    # cuando la molécula no se unía a la anti-diana, que es el mejor caso.
    # Ver `services/docking/selectividad_margen.py`.
    #
    # Se sigue calculando y guardando para no romper lo que ya está en la base,
    # pero NO decide nada: el veredicto sale de ΔΔG.
    margen = margen_de_selectividad(on_target_affinity, worst_off_affinity, peor_anti_diana)
    delta_delta_g = margen.delta_delta_g if margen else None

    selectivity_ratio = None
    if on_target_affinity is not None and worst_off_affinity is not None and worst_off_affinity < 0:
        selectivity_ratio = round(on_target_affinity / worst_off_affinity, 2)

    evaluadas = sum(1 for r in results if r.get("affinity") is not None)
    solicitadas = len(targets) + len(desconocidas)

    elapsed = time.monotonic() - start
    log.info(
        "selectivity_panel_complete",
        targets=len(results),
        evaluadas=evaluadas,
        solicitadas=solicitadas,
        flags=len(safety_flags),
        delta_delta_g=delta_delta_g,
        elapsed_s=round(elapsed, 1),
    )

    return SelectivityResult(
        on_target_affinity=on_target_affinity,
        on_target_pdb=on_target_pdb,
        off_targets=results,
        selectivity_ratio=selectivity_ratio,
        delta_delta_g_kcal=delta_delta_g,
        peor_anti_diana=peor_anti_diana,
        safety_flags=safety_flags,
        execution_time_s=round(elapsed, 1),
        anti_dianas_evaluadas=evaluadas,
        anti_dianas_solicitadas=solicitadas,
    )
