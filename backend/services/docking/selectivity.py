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
- NaV1.5: sodium channel -> cardiac conduction block

All structures from RCSB PDB, pre-cached locally.

Referencias:

  Bowes et al. (2012) "Reducing safety-related drug attrition: the use of in
  vitro pharmacological profiling". Nature Reviews Drug Discovery.
  — de donde sale la composición del panel.

  Zhu Y., Rahman T. (2026) "Benchmarking co-folding tools on Nav, Cav and Kv
  channels". Frontiers in Biophysics 4:1937302.
  — por qué hERG (5VA1) y NaV1.5 (6MVW) se acoplan sobre la estructura
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
from dataclasses import dataclass, field
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
# Curated from Bowes et al. 2012 and AstraZeneca safety panels.
# Each anti-target has a PDB ID, grid box, and clinical relevance.

ANTI_TARGET_PANEL = [
    {
        "pdb_id": "5VA1",
        "name": "hERG (KCNH2)",
        "chain": "A",
        "category": "Cardiac",
        "risk": "Arritmia cardiaca (QT prolongation). Retiro de Terfenadina, Cisaprida, Grepafloxacino.",
        "center": (79.14, 68.54, 78.53),
        "size": (24.0, 24.0, 24.0),
        "affinity_threshold": -7.0,
    },
    {
        "pdb_id": "4NY4",
        "name": "CYP3A4",
        "chain": "A",
        "category": "Metabolism",
        "risk": "Inhibir CYP3A4 causa interacciones droga-droga. Responsable del metabolismo >50% de farmacos.",
        "center": (-21.94, -17.84, -9.84),
        "size": (22.0, 22.0, 22.0),
        "affinity_threshold": -8.0,
    },
    {
        "pdb_id": "4NC3",
        "name": "5-HT2B (HTR2B)",
        "chain": "A",
        "category": "CNS/Safety",
        "risk": "Agonismo 5-HT2B causa valvulopatia cardiaca. Fenfluramina, Pergolida retirados.",
        "center": (-22.06, -18.62, 12.05),
        "size": (22.0, 22.0, 22.0),
        "affinity_threshold": -7.5,
    },
    {
        "pdb_id": "1SO2",
        "name": "PDE3A",
        "chain": "A",
        "category": "Cardiac",
        "risk": "Inhibicion de PDE3 afecta contractilidad. Milrinona solo uso hospitalario.",
        "center": (69.46, 12.39, 27.22),
        "size": (22.0, 22.0, 22.0),
        "affinity_threshold": -8.0,
    },
    {
        "pdb_id": "6MVW",
        "name": "NaV1.5 (SCN5A)",
        "chain": "A",
        "category": "Cardiac",
        "risk": "Bloqueo de canales de sodio causa arritmia. Flecainida muestra el mecanismo.",
        "center": (125.44, 163.44, 14.78),
        "size": (24.0, 24.0, 24.0),
        "affinity_threshold": -7.5,
    },
]


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

    if not anti_targets:
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
        elegidas.append(
            {
                "pdb_id": pid,
                "name": getattr(fila, "name", None) or pid,
                "category": "Custom",
                "risk": getattr(fila, "anti_target_risk", None)
                or f"Anti-diana aportada por el usuario: {getattr(fila, 'name', pid)}",
                "chain": getattr(fila, "chain", None) or "A",
                # Sin `center`/`size` a propósito: los toma del catálogo el
                # resolvedor, que además rechaza una caja en el origen.
                "affinity_threshold": getattr(fila, "affinity_threshold", None) or -7.0,
            }
        )

    return elegidas, desconocidas


async def run_selectivity_panel(
    smiles: str,
    smiles_hash: str,
    on_target_pdb: str,
    on_target_affinity: float,
    num_workers: int = 2,
    anti_targets: list[str] | None = None,
    repository: Any | None = None,
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
        # Ver `anti_target_sitio.py`: hERG (5VA1) y NaV1.5 (6MVW) declaran
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
    safety_flags = []
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


def get_anti_target_list() -> list[dict]:
    """Return ALL available anti-targets: DB-backed + hardcoded defaults."""
    targets = list(ANTI_TARGET_PANEL)

    try:
        import asyncio
        from core.database import get_db_session
        from db.repository import Repository

        async def _fetch():
            async with get_db_session() as db:
                repo = Repository(db)
                db_targets = await repo.get_anti_targets()
                for t in db_targets:
                    targets.append({
                        "pdb_id": t.pdb_id,
                        "name": t.name,
                        "category": "Custom",
                        "risk": getattr(t, "anti_target_risk", None) or f"Target subido por el usuario: {t.name}",
                        "center": (t.grid_center_x or 0, t.grid_center_y or 0, t.grid_center_z or 0),
                        "size": (t.grid_size_x or 20, t.grid_size_y or 20, t.grid_size_z or 20),
                        "affinity_threshold": t.affinity_threshold or -7.0,
                        "chain": t.chain or "A",
                        "source": "user",
                    })

        try:
            asyncio.get_running_loop()
            # Ya estamos en un event loop — crear task
            asyncio.ensure_future(_fetch())
        except RuntimeError:
            # No hay event loop — crear uno temporal
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(_fetch())
            finally:
                loop.close()
    except Exception:
        pass

    return [
        {
            "pdb_id": t["pdb_id"],
            "name": t["name"],
            "category": t.get("category", "Custom"),
            "risk": t.get("risk", ""),
            "threshold_kcal": t["affinity_threshold"],
        }
        for t in targets
    ]
