"""
api/routers/suggestions.py

Endpoint de generación de sugerencias moleculares.

Permite al usuario obtener sugerencias de modificación molecular
después de una evaluación, para guiar la optimización iterativa.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/suggestions", tags=["Generación de novo"])


class SuggestionRequest(BaseModel):
    smiles: str = Field(..., min_length=1, max_length=2000)
    properties: dict[str, Any] | None = Field(default=None, description="Propiedades fisicoquímicas calculadas")
    scores: dict[str, Any] | None = Field(default=None, description="Scores de evaluación")
    max_suggestions: int = Field(default=5, ge=1, le=10)


class SuggestionItem(BaseModel):
    smiles: str
    name: str
    description: str
    rationale: str
    modification_type: str
    expected_effect: str
    confidence: str
    source: str
    warnings: list[str]


class SuggestionResponse(BaseModel):
    success: bool
    suggestions: list[SuggestionItem]
    method: str
    warnings: list[str]
    disclaimer: str = (
        "Las sugerencias son hipótesis computacionales basadas en reglas de química medicinal. "
        "No se garantiza que mejoren la actividad biológica. "
        "Evalúe cada sugerencia con el pipeline completo antes de aceptarla."
    )


from fastapi import APIRouter, Request
from api.dynamic_limiter import limiter

@router.post(
    "/generate",
    response_model=SuggestionResponse,
    summary="Generar sugerencias de modificación molecular",
)
@limiter.limit("10/minute")
async def generate_suggestions(data: SuggestionRequest, request: Request) -> SuggestionResponse:
    """
    Genera sugerencias de modificación molecular usando reglas de química medicinal.

    Las sugerencias consideran:
    - Propiedades fisicoquímicas actuales (si se proporcionan)
    - Scores de evaluación (si se proporcionan)
    - Transformaciones bioisostéricas conocidas
    - Reglas de optimización de Lipinski/Veber

    Cada sugerencia incluye tipo, razonamiento y nivel de confianza.
    """
    from services.denovo.generator import generate_suggestions as gen_suggestions

    result = gen_suggestions(
        smiles=data.smiles,
        properties=data.properties,
        scores=data.scores,
        max_suggestions=data.max_suggestions,
    )

    suggestions = [
        SuggestionItem(
            smiles=s.smiles,
            name=s.name,
            description=s.description,
            rationale=s.rationale,
            modification_type=s.modification_type,
            expected_effect=s.expected_effect,
            confidence=s.confidence,
            source=s.source,
            warnings=s.warnings,
        )
        for s in result.suggestions
    ]

    return SuggestionResponse(
        success=result.success,
        suggestions=suggestions,
        method=result.method,
        warnings=result.warnings,
    )
