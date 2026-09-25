"""
api/routers/protein_surgery.py — Endpoints para cirugia estructural de proteinas.

Expone funciones de protein_surgery.py como endpoints HTTP seguros.
Todas las operaciones son locales (no requieren servicios externos).

Seguridad:
  - No expone rutas del sistema de archivos.
  - Los archivos temporales se limpian al finalizar.
  - Validacion estricta de inputs con Pydantic.
  - Los errores internos se traducen a mensajes genericos.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/proteins/surgery", tags=["Protein Surgery"])


# ── Request / Response Models ────────────────────────────────────────────────


class MetalFeaturesRequest(BaseModel):
    smiles: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="SMILES del ligando a analizar.",
    )


class MetalFeaturesResponse(BaseModel):
    sulfonamide_count: int = 0
    carboxylate_count: int = 0
    thiol_count: int = 0
    hydroxamic_acid_count: int = 0
    imidazole_count: int = 0
    phosphate_count: int = 0
    zn_binding_groups_total: int = 0
    has_metal_binding_potential: bool = False


class DetectMetalsRequest(BaseModel):
    pdb_content: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="Contenido PDB completo de la proteina.",
    )


class DetectedMetal(BaseModel):
    element: str
    position_x: float
    position_y: float
    position_z: float


class DetectMetalsResponse(BaseModel):
    metals: list[DetectedMetal]
    count: int


class DynamicBoxRequest(BaseModel):
    ligand_pdb_content: str = Field(
        ...,
        min_length=10,
        max_length=500000,
        description="Contenido PDB/SDF del ligando cocristalizado.",
    )


class DynamicBoxResponse(BaseModel):
    center_x: float
    center_y: float
    center_z: float
    size: float
    ligand_span_x: float
    ligand_span_y: float
    ligand_span_z: float


class ValidateVinaAtomsRequest(BaseModel):
    smiles: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="SMILES a validar.",
    )


class ValidateVinaAtomsResponse(BaseModel):
    all_supported: bool
    unsupported_elements: list[str]


class PrepareTargetRequest(BaseModel):
    protein_pdb_content: str = Field(
        ...,
        min_length=50,
        max_length=500000,
        description="Contenido PDB de la proteina.",
    )



class PrepareTargetResponse(BaseModel):
    success: bool
    box_source: str
    vina_center_x: float
    vina_center_y: float
    vina_center_z: float
    vina_size: float
    metal_count: int
    chain_count: dict[str, int]
    warnings: list[str]


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post(
    "/metal-features",
    response_model=MetalFeaturesResponse,
    summary="Detectar grupos quelantes de metales",
    description="Analiza un SMILES en busca de grupos funcionales con afinidad por cationes metalicos (Zn, Fe, Mg). Ideal para predecir actividad en metaloenzimas.",
    status_code=status.HTTP_200_OK,
)
async def metal_features_endpoint(request: MetalFeaturesRequest) -> MetalFeaturesResponse:
    """Detecta grupos quelantes de metales en un ligando."""
    try:
        from services.chemistry.protein_surgery import metal_features
        result = metal_features(request.smiles)
        return MetalFeaturesResponse(
            sulfonamide_count=result.get("sulfonamide_count", 0),
            carboxylate_count=result.get("carboxylate_count", 0),
            thiol_count=result.get("thiol_count", 0),
            hydroxamic_acid_count=result.get("hydroxamic_acid_count", 0),
            imidazole_count=result.get("imidazole_count", 0),
            phosphate_count=result.get("phosphate_count", 0),
            zn_binding_groups_total=result.get("zn_binding_groups_total", 0),
            has_metal_binding_potential=bool(result.get("has_metal_binding_potential", 0)),
        )
    except Exception as e:
        log.error("metal_features_failed", error=str(e))
        raise HTTPException(503, "No se pudieron calcular los grupos quelantes") from e


@router.post(
    "/detect-metals",
    response_model=DetectMetalsResponse,
    summary="Detectar iones metalicos en estructura proteica",
    description="Escanea un archivo PDB en busca de atomos de metales de transicion (Zn, Fe, Mg, Mn, Ca, Co, Ni, Cu, Cd, Hg).",
    status_code=status.HTTP_200_OK,
)
async def detect_metals_endpoint(request: DetectMetalsRequest) -> DetectMetalsResponse:
    """Detecta iones metalicos en una estructura PDB."""
    tmp = tempfile.NamedTemporaryFile(suffix=".pdb", delete=False, mode="w", encoding="utf-8")
    try:
        tmp.write(request.pdb_content)
        tmp.close()

        from services.chemistry.protein_surgery import detect_metals_in_protein
        metals = detect_metals_in_protein(tmp.name)
        return DetectMetalsResponse(
            metals=[
                DetectedMetal(
                    element=m["element"],
                    position_x=float(m["position"][0]),
                    position_y=float(m["position"][1]),
                    position_z=float(m["position"][2]),
                )
                for m in metals
            ],
            count=len(metals),
        )
    except Exception as e:
        log.error("detect_metals_failed", error=str(e))
        raise HTTPException(503, "No se pudo detectar metales en la estructura") from e
    finally:
        try:
            Path(tmp.name).unlink(missing_ok=True)
        except Exception:
            pass


@router.post(
    "/dynamic-box",
    response_model=DynamicBoxResponse,
    summary="Calcular caja de docking optima desde ligando",
    description="Calcula el centro de masa y el tamano de caja de Vina a partir de las coordenadas 3D de un ligando cocristalizado.",
    status_code=status.HTTP_200_OK,
)
async def dynamic_box_endpoint(request: DynamicBoxRequest) -> DynamicBoxResponse:
    """Calcula la grid box de Vina desde un ligando."""
    try:
        from rdkit import Chem
        import numpy as np

        mol = Chem.MolFromPDBBlock(request.ligand_pdb_content) or Chem.MolFromMolBlock(request.ligand_pdb_content)
        if mol is None or mol.GetNumAtoms() == 0 or mol.GetNumConformers() == 0:
            raise HTTPException(422, "No hay coordenadas válidas de ligando para calcular la caja")

        conf = mol.GetConformer()
        coords = np.array([(conf.GetAtomPosition(i).x, conf.GetAtomPosition(i).y, conf.GetAtomPosition(i).z) for i in range(mol.GetNumAtoms())])
        if not np.isfinite(coords).all():
            raise HTTPException(422, "Las coordenadas del ligando deben ser finitas")
        cx, cy, cz = float(np.mean(coords[:, 0])), float(np.mean(coords[:, 1])), float(np.mean(coords[:, 2]))
        span_x = float(np.max(coords[:, 0]) - np.min(coords[:, 0]))
        span_y = float(np.max(coords[:, 1]) - np.min(coords[:, 1]))
        span_z = float(np.max(coords[:, 2]) - np.min(coords[:, 2]))
        padding = 8.0
        box_size = max(12.0, min(22.0, max(span_x, span_y, span_z) + padding))

        return DynamicBoxResponse(center_x=cx, center_y=cy, center_z=cz, size=round(box_size, 1), ligand_span_x=round(span_x, 2), ligand_span_y=round(span_y, 2), ligand_span_z=round(span_z, 2))
    except HTTPException:
        raise
    except ImportError as e:
        raise HTTPException(503, "El componente de análisis estructural no está disponible") from e
    except Exception as e:
        log.warning("dynamic_box_failed", error=str(e))
        raise HTTPException(500, "No se pudo calcular la caja del ligando") from e


@router.post(
    "/validate-atoms",
    response_model=ValidateVinaAtomsResponse,
    summary="Validar atomos compatibles con Vina",
    description="Verifica si todos los atomos en un SMILES son compatibles con AutoDock Vina (H, C, N, O, F, P, S, Cl, Br, I).",
    status_code=status.HTTP_200_OK,
)
async def validate_vina_atoms_endpoint(request: ValidateVinaAtomsRequest) -> ValidateVinaAtomsResponse:
    """Valida compatibilidad atomica con Vina."""
    try:
        from services.chemistry.protein_surgery import validate_vina_atoms
        ok, unsupported = validate_vina_atoms(request.smiles)
        return ValidateVinaAtomsResponse(
            all_supported=ok,
            unsupported_elements=sorted(unsupported),
        )
    except Exception as e:
        log.error("validate_vina_atoms_failed", error=str(e))
        raise HTTPException(503, "No se pudo validar compatibilidad atómica") from e


@router.post(
    "/prepare",
    response_model=PrepareTargetResponse,
    summary="Preparar receptor para docking",
    description=(
        "Orquesta la preparacion completa de un receptor: "
        "analisis de cadenas, deteccion de metales, calculo de pocket, "
        "trimming de cadenas y generacion de PDBQT. "
        "Requiere el PDB de la proteina. El sitio sólo se deriva de "
        "coordenadas presentes en el PDB."
    ),
    status_code=status.HTTP_200_OK,
)
async def prepare_target_endpoint(request: PrepareTargetRequest) -> PrepareTargetResponse:
    """Analiza la estructura sin usar un SMILES como localizador espacial."""
    from services.chemistry.protein_surgery import prepare_target
    try:
        with tempfile.TemporaryDirectory(prefix="surgery_") as work_dir:
            protein_file = Path(work_dir) / "input.pdb"
            protein_file.write_text(request.protein_pdb_content, encoding="utf-8")
            result = prepare_target(str(protein_file), output_dir=work_dir)
            chain_info = result.get("chains", {})
            if isinstance(chain_info, dict):
                chain_count = chain_info
            elif isinstance(chain_info, list):
                chain_count = {}
                for chain in chain_info:
                    chain_count[chain] = chain_count.get(chain, 0) + 1
            else:
                chain_count = {}
            return PrepareTargetResponse(
                success=True,
                box_source=str(result.get("box_source", "sin_definir")),
                vina_center_x=float(result.get("vina_center", (0, 0, 0))[0]),
                vina_center_y=float(result.get("vina_center", (0, 0, 0))[1]),
                vina_center_z=float(result.get("vina_center", (0, 0, 0))[2]),
                vina_size=float(result.get("vina_box", 22.0)),
                metal_count=len(result.get("metal_atoms", [])),
                chain_count=chain_count,
                warnings=result.get("warnings", []),
            )
    except Exception as exc:
        log.error("prepare_target_failed", error=str(exc))
        raise HTTPException(503, "No se pudo preparar el receptor") from exc
