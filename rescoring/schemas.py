from __future__ import annotations

from pydantic import BaseModel, Field


class PoseData(BaseModel):
    """Una pose individual de Vina."""

    pdbqt_block: str = Field(..., description="Bloque PDBQT de la pose")
    vina_score: float = Field(..., description="Score de Vina (kcal/mol)")
    rmsd_lb: float = Field(0.0, description="RMSD lower bound vs pose 1")
    rmsd_ub: float = Field(0.0, description="RMSD upper bound vs pose 1")


class RescoreRequest(BaseModel):
    """Request para rescoring de una molécula."""

    smiles: str = Field(..., description="SMILES canónico de la molécula")
    target_pdb_path: str = Field(..., description="Path al archivo PDB del target")
    poses: list[PoseData] = Field(..., description="Lista de poses de Vina (típicamente 9)")
    # Propiedades 1D/2D pre-calculadas por el backend
    molecular_weight: float = Field(..., description="Peso molecular (Da)")
    logp: float = Field(..., description="LogP calculado")
    tpsa: float = Field(..., description="TPSA (Å²)")
    hbd: int = Field(..., description="Hydrogen Bond Donors")
    hba: int = Field(..., description="Hydrogen Bond Acceptors")
    rotatable_bonds: int = Field(..., description="Rotatable bonds")
    qed: float = Field(..., description="QED score")
    
    # Configuración del grid (para el filtro de poses)
    grid_center: tuple[float, float, float] | None = Field(None, description="Centro del grid box (x, y, z)")
    grid_size: tuple[float, float, float] | None = Field(None, description="Tamaño del grid box (nx, ny, nz)")
    
    # Familia estructural (para modelo XGBoost especifico)
    target_family: str | None = Field(None, description="Familia estructural del target: gpcr, kinase, protease, nuclear_receptor, soluble_enzyme")
    
    # Nivel 2: GNN Rescoring
    run_gnn: bool = Field(False, description="¿Ejecutar rescoring de nivel 2 con GNN (RTMScore)?")


class PreScoreRequest(BaseModel):
    """Request para pre-scoring rápido (solo 1D/2D)."""
    smiles: str
    molecular_weight: float
    logp: float
    tpsa: float
    hbd: int
    hba: int
    rotatable_bonds: int
    qed: float


class PreScoreResponse(BaseModel):
    """Respuesta de pre-scoring."""
    score: float
    model_version: str
    in_domain: bool


class ApplicabilityDomainResult(BaseModel):
    """Resultado del check de Applicability Domain."""

    in_domain: bool = Field(..., description="¿Molécula dentro del dominio de entrenamiento?")
    mahalanobis_distance: float = Field(..., description="Distancia de Mahalanobis")
    threshold: float = Field(..., description="Umbral (percentil 99 del training set)")
    out_of_range_descriptors: list[str] = Field(
        default_factory=list,
        description="Descriptores fuera de rango (e.g., 'MW: 1250 Da, rango training: 150-750')",
    )
    w_core: float | None = Field(None, description="Peso del modelo Core en el consenso")
    w_extended: float | None = Field(None, description="Peso del modelo Extended en el consenso")
    extended_threshold: float | None = Field(None, description="Umbral del modelo Extended (por defecto 200.0)")


class PoseVarianceResult(BaseModel):
    """Incertidumbre derivada de las 9 poses de Vina."""

    score_variance: float = Field(..., description="Varianza de scores entre las 9 poses")
    score_range: float = Field(..., description="Rango (max - min) de scores")
    poses_analyzed: int = Field(..., description="Número de poses analizadas")
    poses_passing_filter: int = Field(..., description="Poses que pasan el filtro geométrico")
    stability: str = Field(..., description="ALTA / MEDIA / BAJA")


class DeltaResult(BaseModel):
    """Delta de Especificidad 3D."""

    delta: float = Field(..., description="score_A - score_NULL")
    semaphore: str = Field(..., description="GREEN / YELLOW / RED")
    interpretation: str = Field(..., description="Interpretación en lenguaje natural")


class RescoreResponse(BaseModel):
    """Respuesta completa del rescoring."""

    # Scores
    score_a: float = Field(..., description="Score del Modelo A (ranking, features completas)")
    score_null: float = Field(..., description="Score del Modelo NULL (solo descriptores 1D/2D)")
    gnn_score: float | None = Field(None, description="Score calculado por el modelo RTMScore (GNN)")

    # Delta
    delta: DeltaResult

    # Applicability Domain
    applicability_domain: ApplicabilityDomainResult

    # Pose variance
    pose_variance: PoseVarianceResult

    # Features usadas (para auditoría)
    features_used: dict[str, float] = Field(
        default_factory=dict,
        description="Features extraídas y sus valores (transparencia)",
    )

    # Metadata
    model_version: str = Field(..., description="Versión del modelo usado")
    inference_time_ms: float = Field(..., description="Tiempo de inferencia en ms")

    # Warnings
    warnings: list[str] = Field(default_factory=list, description="Warnings científicos")

    # XAI
    shap_values: dict[str, float] | None = Field(None, description="Top contribuciones SHAP de XGBoost")
    gnn_attention: list[float] | None = Field(None, description="Atención GNN por átomo del ligando")
    gnn_attention_svg: str | None = Field(None, description="Mapa de calor 2D SVG generado por RDKit")
    gnn_pharmacophores: dict[str, float] | None = Field(None, description="Desglose porcentual de atención por grupo farmacóforo")
    
    # Classifier
    classifier_prob: float | None = Field(None, description="Probabilidad de ser buen binder (pKi > 7.0)")

    # Transparencia del modelo usado (F-21): familia vs universal + motivo del
    # fallback. Los rellena model_manager.predict() según el quality gate
    # (Spearman >= 0.5 y p < 0.05 para usar el modelo de familia).
    model_used: str | None = Field(None, description="'family' | 'universal' — modelo usado para el score core")
    fallback_reason: str | None = Field(None, description="Motivo del fallback a modelo universal (quality gate o modelo de familia no disponible)")

    # Pose selector (Ruta C v0.6, Fase 4) — opcional: None si el selector no
    # está disponible o degradó. El resto de la respuesta es independiente.
    pose_scores: list[float] | None = Field(None, description="Scores del selector v0.6 por pose (orden del request, mayor = mejor)")
    selected_pose_rank: int | None = Field(None, description="Índice 0-based de la pose seleccionada (tipo-cristal)")
    pose_confidence: float | None = Field(None, description="Margen de confianza top1 − top2 (0 si N==1)")
    pose_abstained: bool | None = Field(None, description="Abstención por margen bajo (regla de Fase 3, t=0.097663)")
    pose_selector_model: str | None = Field(None, description="Identificador del modelo del selector (p. ej. pose_selector_v06)")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model_loaded: bool
    model_version: str | None
    prolif_available: bool
    xgboost_available: bool
    gnn_available: bool
    manifest_valid: bool
    manifest_errors: list[str] = Field(default_factory=list)


class ModelInfoResponse(BaseModel):
    """Metadata del modelo."""

    model_version: str | None
    training_date: str | None
    training_samples: int | None
    ndcg_at_10: float | None
    spearman: float | None
    applicability_domain_threshold: float | None
    families_trained: list[str]
