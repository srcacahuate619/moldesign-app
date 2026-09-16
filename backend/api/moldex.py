from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user_optional
from core.models import UserORM
from db.repository import Repository
from services.avisos import textos
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
    spearman_rho: float | None = None


class MoldexMetricsRead(BaseModel):
    #: kcal/mol. Más negativo = mejor.
    affinity: float | None = None
    log_p: float | None = None
    #: Daltons.
    mw: float | None = None
    #: Å².
    tpsa: float | None = None
    #: Escala 0-100.
    score: float | None = None
    gnn_score: float | None = None
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


class MoldexSealRead(BaseModel):
    certified: bool
    tx_signature: str | None = None
    certified_task_id: str | None = None
    certified_total_score: float | None = None
    #: MOLDEX-SCI-001. `None` es indeterminado, y no puede leerse como «coincide».
    matches_current_run: bool | None = None


class MoldexMoleculeRead(BaseModel):
    id: str
    name: str
    smiles: str
    smiles_hash: str
    created_at: str
    evaluated_at: str | None = None
    target: MoldexTargetRead
    metrics: MoldexMetricsRead
    provenance: MoldexProvenanceRead
    scientific_warnings: list[str] = Field(default_factory=list)
    hotspots_hit: list[str] = Field(default_factory=list)
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

    task_sellada = res.certified_task_id
    score_sellado = res.certified_total_score

    if task_sellada is None:
        coincide = None
    else:
        # El cero medido es un valor válido, no un faltante: se compara con
        # `is not None`, nunca por veracidad (MOLDEX-SCI-002).
        coincide = task_sellada == res.task_id and score_sellado == res.total_score

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

        catalog.append({
            "id": str(mol.id),
            "name": mol.name or f"Ligando {mol.smiles_hash[:8]}",
            "smiles": mol.smiles,
            "smiles_hash": mol.smiles_hash,
            "created_at": mol.created_at.isoformat(),
            # Fecha de la evaluación, distinta de la creación de la molécula.
            # El cliente ya ordenaba por este campo; nunca se emitía.
            "evaluated_at": (
                res.evaluated_at.isoformat() if res.evaluated_at is not None else None
            ),
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
            },
            "target": {
                "pdb_id": target.pdb_id,
                "name": target.name,
                "family": target.structural_family,
                "hotspots": target.hotspots or [],
                "spearman_rho": target.spearman_rho,
            },
            "metrics": {
                "affinity": res.affinity_kcal,
                "log_p": res.log_p,
                "mw": res.molecular_weight,
                "tpsa": res.tpsa,
                "score": res.total_score,
                "gnn_score": res.gnn_score,
                "lipinski_pass": res.lipinski_pass,
                "veber_pass": res.veber_pass,
            },
            "scientific_warnings": textos(res.scientific_warnings),
            "hotspots_hit": res.hotspots_hit or [],
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
