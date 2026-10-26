from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, get_db, get_current_user_optional
from core.models import UserORM
from db.repository import Repository
from services.avisos import textos
from services.docking.protocolo_de_producto import describir_protocolo
from services.targets.calibracion import estado_de_calibracion


#: Tolerancia al comparar la afinidad guardada con la de la pose top-1 (redondeo a 2 decimales).
_TOLERANCIA_AFINIDAD = 0.005


def _origen_de_la_afinidad(res: Any) -> str | None:
    """«vina» si la afinidad guardada es, comprobado, la de la pose top-1 de Vina.

    SCI-A-011: antes de la v16 del esquema `affinity_kcal` podía contener la
    regresión de XGBoost convertida a kcal/mol, escrita encima del score de Vina
    y sin nada que lo distinguiera (`core/database.py`). La ficha la rotulaba
    «Afinidad calculada (Vina)» igual. Sólo se acredita Vina cuando la corrida
    guarda versión de Vina y poses, y la afinidad coincide con la mejor de ellas;
    si no, «no_acreditado». ``None`` sin afinidad.
    """
    afinidad = getattr(res, "affinity_kcal", None)
    if not isinstance(afinidad, (int, float)) or isinstance(afinidad, bool):
        return None
    poses = getattr(res, "docking_poses", None)
    if isinstance(poses, str):
        import json
        try:
            poses = json.loads(poses)
        except ValueError:
            poses = None
    afinidades = [p.get("affinity") for p in poses or [] if isinstance(p, dict)]
    afinidades = [a for a in afinidades if isinstance(a, (int, float)) and not isinstance(a, bool)]
    if getattr(res, "vina_version", None) and afinidades \
            and abs(float(afinidad) - min(afinidades)) <= _TOLERANCIA_AFINIDAD:
        return "vina"
    return "no_acreditado"


def _hotspots_tocados(valor: Any) -> list[str] | None:
    """La lista evaluada (también vacía) o ``None`` si nadie la evaluó."""
    if valor is None:
        return None
    if isinstance(valor, str):
        import json
        try:
            valor = json.loads(valor)
        except ValueError:
            return None
    return [str(v) for v in valor] if isinstance(valor, list) else None
from utils.instantes import instante_utc
from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/moldex", tags=["Moldex"])


# ── Contrato declarado (MOLDEX-INT-013) ──────────────────────────────────────
#
# La ruta devolvía `dict[str, Any]`, así que no aparecía en el OpenAPI
# versionado y la guarda de contrato del frontend no podía cubrirla: mantenerlo
# alineado dependía de que alguien se acordara. Todos los campos científicos son
# opcionales de verdad —una corrida heredada no tiene procedencia, y RDKit puede
# no calcular un descriptor—, y ninguno se rellena con un valor por defecto:
# `null` significa «no se midió», nunca cero.


class MoldexTargetRead(BaseModel):
    pdb_id: str
    name: str | None = None
    family: str | None = None
    hotspots: list[Any] = Field(default_factory=list)
    #: Sólo la ρ respaldada por una medida con n, IC y protocolo (SCI-A-005).
    spearman_rho: float | None = None
    #: El estado de `services/targets/calibracion.py` (nivel, respaldo, ρ sin respaldo).
    calibracion: dict[str, Any] | None = None


class MoldexMetricsRead(BaseModel):
    #: kcal/mol. Más negativo = mejor.
    affinity: float | None = None
    #: «vina» si se comprobó que es la de la pose top-1 de Vina; si no, «no_acreditado» (SCI-A-011).
    affinity_origin: Literal["vina", "no_acreditado"] | None = None
    log_p: float | None = None
    #: Daltons.
    mw: float | None = None
    #: Å².
    tpsa: float | None = None
    #: Escala 0-100.
    score: float | None = None
    #: RTMScore (legacy). Nulo en toda corrida de la app de escritorio: sus pesos no
    #: viajan y el puente directo no la calcula. Se conserva por las bases antiguas.
    gnn_score: float | None = None
    #: CL-GNN. EXPERIMENTAL: se calcula y se guarda, pero pesa 0.0 en el ranking
    #: (sus AUC históricos no son del SHA-256 que viaja; stacking_weights.json).
    clgnn_score: float | None = None
    lipinski_pass: bool | None = None
    veber_pass: bool | None = None


class MoldexProvenanceRead(BaseModel):
    """Identidad y condiciones de la corrida que produjo las métricas.

    `receptor_path` NO se publica: es una ruta local de la cuenta y EVAL-INT-008
    fijó que no se renderiza. Para decidir compatibilidad basta el hash.
    """

    task_id: str | None = None
    receptor_sha256: str | None = None
    engine_version: str | None = None
    random_seed: int | None = None
    docking_protocol: dict[str, Any] | None = None
    #: Si la corrida es comparable con las de hoy (receta del receptor y
    #: calibración del ranking). Ver `services/docking/protocolo_de_producto.py`.
    protocolo: dict[str, Any] | None = None


class MoldexSealRead(BaseModel):
    certified: bool
    tx_signature: str | None = None
    certified_task_id: str | None = None
    certified_total_score: float | None = None
    #: MOLDEX-SCI-001. `None` es indeterminado, y no puede leerse como «coincide».
    matches_current_run: bool | None = None


class MoldexMoleculeRead(BaseModel):
    #: Id de la MOLÉCULA (receptor + ligando). Es el que esperan los endpoints de
    #: archivos, certificado y render; varias fichas pueden compartirlo.
    id: str
    #: Identidad única de la FICHA: una corrida guardada. Una molécula se evalúa
    #: muchas veces y cada evaluación guardada es una ficha propia, así que `id`
    #: ya no basta para seleccionar, ordenar ni pintar una lista. En fichas
    #: heredadas (sin snapshot de corrida) coincide con `id`.
    entry_id: str
    #: Nombre con el que se guardó ESTA evaluación, si se le puso uno.
    saved_name: str | None = None
    name: str
    smiles: str
    smiles_hash: str
    created_at: str
    evaluated_at: str | None = None
    target: MoldexTargetRead
    metrics: MoldexMetricsRead
    provenance: MoldexProvenanceRead
    scientific_warnings: list[str] = Field(default_factory=list)
    #: `None` = no evaluado; `[]` = evaluado sin aciertos (SCI-A-010).
    hotspots_hit: list[str] | None = None
    blockchain: MoldexSealRead


class MoldexCatalogRead(BaseModel):
    count: int
    total: int
    limit: int | None = None
    offset: int
    has_next: bool
    results: list[MoldexMoleculeRead] = Field(default_factory=list)


def _estado_del_sello(res: Any) -> dict[str, Any]:
    """Declara qué certificó el sello y si sigue describiendo la fila vigente.

    MOLDEX-SCI-001. `evaluation_results` es la proyección mutable de la última
    evaluación: al reevaluar la molécula se reescriben score, afinidad, receptor
    y semilla, pero el sello se queda. Sin esta comparación, la ficha mostraba
    la insignia CERTIFIED junto a cifras que la cadena nunca atestiguó.

    `matches_current_run` tiene tres valores y los tres significan cosas
    distintas:

    - ``True``  — el sello describe la corrida que la ficha está mostrando;
    - ``False`` — la molécula se reevaluó después de certificarla; lo sellado y
      lo mostrado son corridas distintas;
    - ``None``  — indeterminado. O no hay sello, o es anterior a v14 y no
      registra qué corrida cubrió. Suponer que coincide sería reintroducir el
      defecto, así que no se supone.
    """
    firma = res.blockchain_tx_id
    if not firma:
        return {
            "certified": False,
            "tx_signature": None,
            "certified_task_id": None,
            "certified_total_score": None,
            "matches_current_run": None,
        }

    from services.blockchain.sello import sello_describe_la_corrida

    task_sellada = res.certified_task_id
    score_sellado = res.certified_total_score
    coincide = sello_describe_la_corrida(
        tx_id=firma,
        certified_task_id=task_sellada,
        certified_total_score=score_sellado,
        task_id=res.task_id,
        total_score=res.total_score,
    )

    return {
        "certified": True,
        "tx_signature": firma,
        "certified_task_id": task_sellada,
        "certified_total_score": score_sellado,
        "matches_current_run": coincide,
    }

@router.get(
    "",
    response_model=MoldexCatalogRead,
    summary="Obtiene el catálogo de moléculas evaluadas (Moldex)",
)
async def get_moldex(
    target_pdb_id: str | None = Query(None, description="Filtrar por ID de PDB (ej: 7E2Y)"),
    limit: int | None = Query(
        None,
        ge=1,
        le=200,
        description="Máximo número de moléculas a devolver. Default None = todas (legacy compat).",
    ),
    offset: int = Query(0, ge=0, description="Índice a partir del cual empezar (para paginación)."),
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    repo = Repository(db)

    if current_user is None:
        return {
            "count": 0,
            "total": 0,
            "limit": limit,
            "offset": offset,
            "has_next": False,
            "results": [],
        }

    results, total = await repo.get_moldex_molecules(
        user_id=current_user.id,
        target_pdb_id=target_pdb_id,
        limit=limit,
        offset=offset,
    )

    # Formatear respuesta para la UI de Pokedex
    catalog = []
    for res in results:
        mol = res.molecule
        target = mol.target

        saved_name = getattr(res, "saved_name", None)
        catalog.append({
            "id": str(mol.id),
            "entry_id": f"{mol.id}:{res.task_id}" if res.task_id else str(mol.id),
            "saved_name": saved_name,
            "name": saved_name or mol.name or f"Ligando {mol.smiles_hash[:8]}",
            "smiles": mol.smiles,
            "smiles_hash": mol.smiles_hash,
            # Con su zona (UTC): sin ella el navegador leía hora local.
            "created_at": instante_utc(mol.created_at),
            # Fecha de la evaluación, distinta de la creación de la molécula.
            # El cliente ya ordenaba por este campo; nunca se emitía.
            "evaluated_at": instante_utc(res.evaluated_at),
            # MOLDEX-INT-007. Sin esto una ficha no puede decir de qué corrida
            # salió su número, y ni el sello (MOLDEX-SCI-001) ni la comparación
            # (MOLDEX-SCI-004) pueden comprobar contra qué se están midiendo.
            # Todo sale de la fila que ya se cargó: ni join ni consulta extra.
            # `receptor_path` se omite a propósito — es una ruta local del
            # usuario y EVAL-INT-008 fijó que no se publica. Para decidir
            # compatibilidad basta el hash.
            "provenance": {
                "task_id": res.task_id,
                "receptor_sha256": res.receptor_sha256,
                "engine_version": res.vina_version,
                "random_seed": res.vina_random_seed,
                "docking_protocol": res.docking_protocol,
                "protocolo": describir_protocolo(
                    res.docking_protocol,
                    getattr(res, "weights_calibration_id", None),
                    getattr(res, "target_family", None) or target.structural_family,
                ),
            },
            "target": {
                "pdb_id": target.pdb_id,
                "name": target.name,
                "family": target.structural_family,
                "hotspots": target.hotspots or [],
                # SCI-A-005: los dos `spearman_rho` del catálogo valen 0.0, el
                # valor por defecto, y Moldex los publicaba como «correlación del
                # benchmark». Sale la ρ sólo si está respaldada (n, IC, protocolo);
                # el estado completo viaja con ella.
                "spearman_rho": estado_de_calibracion(target).spearman_rho,
                "calibracion": estado_de_calibracion(target).to_dict(),
            },
            "metrics": {
                "affinity": res.affinity_kcal,
                "affinity_origin": _origen_de_la_afinidad(res),
                "log_p": res.log_p,
                "mw": res.molecular_weight,
                "tpsa": res.tpsa,
                "score": res.total_score,
                "gnn_score": res.gnn_score,
                "clgnn_score": res.clgnn_score,
                "lipinski_pass": res.lipinski_pass,
                "veber_pass": res.veber_pass,
            },
            "scientific_warnings": textos(res.scientific_warnings),
            # SCI-A-010: `None` = no evaluado, `[]` = evaluado sin aciertos. `or []`
            # publicaba los dos como «0 tocados».
            "hotspots_hit": _hotspots_tocados(res.hotspots_hit),
            "blockchain": _estado_del_sello(res),
        })

    has_next = (offset + (limit or len(catalog))) < total if limit is not None else False

    return {
        "count": len(catalog),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_next": has_next,
        "results": catalog,
    }


class MoldexUbicacionRead(BaseModel):
    """Dónde vive lo que Moldex guarda. Moldex no guarda archivos sueltos: guarda FILAS."""

    carpeta_datos: str
    base_de_datos: str


def _ubicacion() -> MoldexUbicacionRead:
    from utils.local_storage import data_dir

    datos = data_dir()
    return MoldexUbicacionRead(carpeta_datos=str(datos), base_de_datos=str(datos / "moldesign_local.db"))


@router.get("/ubicacion", response_model=MoldexUbicacionRead)
async def ubicacion_de_moldex(_user: UserORM = Depends(get_current_user)):
    """Carpeta de datos y base SQLite donde se guardan las fichas de Moldex y los archivos de sus corridas."""
    return _ubicacion()


@router.post("/ubicacion/abrir", response_model=MoldexUbicacionRead)
async def abrir_ubicacion_de_moldex(_user: UserORM = Depends(get_current_user)):
    """Abre la carpeta de datos en el explorador. Sólo ésa: nunca una ruta que llegue en la petición."""
    import subprocess
    import sys

    from utils.procesos import BANDERAS_SIN_VENTANA

    destino = _ubicacion()
    ruta = destino.carpeta_datos
    comando = (["explorer.exe", ruta] if sys.platform == "win32"
               else ["open", ruta] if sys.platform == "darwin" else ["xdg-open", ruta])
    subprocess.Popen(comando, creationflags=BANDERAS_SIN_VENTANA)
    return destino
