"""Reportes IA asociados a resultados de evaluación.

El transporte síncrono y SSE conserva sus rutas bajo ``/evaluation`` al ser
incluido como subrouter. La preparación determinista de datos vive en
``services.ai.report_context``; este módulo conserva autorización, cache y
entrega de cada modalidad.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_optional
from api.dynamic_limiter import get_dynamic_limit, limiter
from api.routers.evaluation_access import require_owned_molecule
from core.database import get_db
from core.models import UserORM
from db.repository import Repository
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter(tags=["Evaluación científica"])


class AIReportResponse(BaseModel):
    ai_report: str | None


@router.get(
    "/ai-report/{molecule_id}/stream",
    response_class=StreamingResponse,
    summary="Generar reporte IA bajo demanda (Streaming SSE)",
)
async def generate_ai_report_stream_endpoint(
    molecule_id: uuid.UUID,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    from services.ai.interpreter import ReporteBloqueado, stream_ollama_report
    from services.ai.report_context import build_evaluation_report_request

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)

    if result is None:
        raise HTTPException(status_code=404, detail="No existe resultado")

    mol_row = await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=molecule_id,
        current_user=current_user,
        forbidden_detail="Sin permiso",
    )

    if result.ai_report:
        async def cached_stream():
            import json
            yield f"data: {json.dumps(result.ai_report)}\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    try:
        from core.models import TargetORM
        target_row = await db.get(TargetORM, mol_row.target_id) if mol_row else None

        ai_request = build_evaluation_report_request(
            result=result,
            molecule_smiles=mol_row.smiles if mol_row else "N/A",
            target_name=target_row.name if target_row else "N/A",
            mutation_type=mol_row.mutation_type if mol_row else None,
            target_hotspots=target_row.hotspots if target_row else [],
            user_id=str(mol_row.user_id) if mol_row and mol_row.user_id else None,
        )

        async def generate_and_save_stream():
            full_text = ""
            try:
                from core.database import get_db_session
                import json
                async for chunk in stream_ollama_report(ai_request):
                    full_text += chunk
                    yield f"data: {json.dumps(chunk)}\n\n"

                if full_text:
                    async with get_db_session() as session:
                        repo = Repository(session)
                        await repo.upsert_evaluation_result(
                            molecule_id=molecule_id,
                            ai_report=full_text,
                        )
            except ReporteBloqueado as bloqueo:
                # Se entrega el motivo y **no se persiste**: el reporte se sirve
                # desde `ai_report` en cuanto existe, así que guardar aquí el
                # aviso dejaría a esta molécula sin reporte para siempre, incluso
                # después de autorizar el destino.
                log.info("reporte_ia_sse_no_enviado", molecule_id=str(molecule_id))
                yield f"data: {json.dumps(str(bloqueo))}\n\n"
            except Exception as e:
                log.error("Error in SSE stream", error=str(e))
                import json
                yield f'data: {json.dumps("Error generando reporte. Por favor intenta de nuevo.")}\n\n'

        return StreamingResponse(generate_and_save_stream(), media_type="text/event-stream")
    except Exception as e:
        log.error("Error pre-generando reporte IA streaming", error=str(e))
        async def err_stream():
            yield 'data: "Error al iniciar streaming"\n\n'
        return StreamingResponse(err_stream(), media_type="text/event-stream")


@router.post(
    "/ai-report/{molecule_id}",
    response_model=AIReportResponse,
    summary="Generar reporte IA bajo demanda para una molécula evaluada",
)
@limiter.limit(get_dynamic_limit)
async def generate_ai_report_endpoint(
    molecule_id: uuid.UUID,
    request: Request,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> AIReportResponse:
    """Genera, persiste y devuelve el reporte IA de una evaluación."""
    from services.ai.interpreter import ReporteBloqueado, safe_generate_ai_report
    from services.ai.report_context import build_evaluation_report_request

    repository = Repository(db)
    result = await repository.get_evaluation_result(molecule_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe resultado para molecule_id={molecule_id}",
        )

    mol_row = await require_owned_molecule(
        repository=repository,
        db=db,
        molecule_id=molecule_id,
        current_user=current_user,
        forbidden_detail="No tienes permiso para acceder a este reporte.",
    )

    if result.ai_report:
        return AIReportResponse(ai_report=result.ai_report)

    try:
        from core.models import TargetORM
        target_row = await db.get(TargetORM, mol_row.target_id)

        ai_request = build_evaluation_report_request(
            result=result,
            molecule_smiles=mol_row.smiles if mol_row else "N/A",
            target_name=target_row.name if target_row else "N/A",
            mutation_type=mol_row.mutation_type if mol_row else None,
            target_hotspots=target_row.hotspots if target_row else [],
            user_id=str(mol_row.user_id) if mol_row and mol_row.user_id else None,
        )

        report = await safe_generate_ai_report(ai_request)

        if report:
            await repository.upsert_evaluation_result(
                molecule_id=molecule_id,
                ai_report=report,
            )

        return AIReportResponse(ai_report=report)

    except ReporteBloqueado as bloqueo:
        # 409, no 500: no falló nada. El reporte habría salido de la máquina
        # hacia un destino que esta cuenta no autorizó, y no se persiste nada
        # para que autorizarlo y reintentar produzca el reporte de verdad.
        log.info("reporte_ia_no_enviado", molecule_id=str(molecule_id))
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(bloqueo),
        ) from None

    except Exception as e:
        log.error("Error generando reporte IA bajo demanda", error=str(e), molecule_id=str(molecule_id))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error interno al generar el reporte IA. Por favor intenta más tarde.",
        ) from e
