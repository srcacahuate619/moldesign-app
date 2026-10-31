"""
api/routers/targets.py

Endpoints para gestión de targets biológicos, incluyendo
búsqueda en AlphaFold DB para targets sin estructura experimental.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.i18n import current_locale
from services.targets.errores_subida import ErrorDeSubida
from core.models import Target, TargetORM, UserORM
from db.repository import Repository
from api.dependencies import get_current_user, get_current_user_optional
from services.targets.calibracion import estado_de_calibracion
from services.targets.disponibilidad import cadenas_truncadas_en_sitio, motivo_no_disponible
from services.targets.access import (
    get_target_for_user,
    require_target_object_access,
    target_is_accessible,
    is_rcsb_pdb_id,
    is_safe_local_target_id,
)

from utils.logger import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/targets", tags=["Targets biológicos"])

class TargetVariantRequest(BaseModel):
    """Receta acotada del MVP; cada POST crea una variante, nunca un UPDATE."""

    name: str = Field(..., min_length=1, max_length=200)
    chain_id: str | None = Field(default=None, min_length=1, max_length=4)
    grid_center: tuple[float, float, float] | None = None
    grid_size: tuple[float, float, float] | None = None
    cofactors_whitelist: list[str] = Field(default_factory=list, max_length=32)

    @field_validator("name", "chain_id")
    @classmethod
    def _strip_text(cls, value):
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            raise ValueError("El texto no puede quedar vacío.")
        return stripped

    @field_validator("cofactors_whitelist")
    @classmethod
    def _normalize_cofactors(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        for raw in values:
            value = raw.strip().upper()
            if not value or len(value) > 8 or not all(c.isalnum() or c in "+-" for c in value):
                raise ValueError("Cada cofactor debe ser un código de residuo válido.")
            if value not in normalized:
                normalized.append(value)
        return sorted(normalized)

    @model_validator(mode="after")
    def validar_caja_variante(self):
        from services.targets.box_validation import validar_caja
        validar_caja(self.grid_center, self.grid_size)
        return self


class TargetIngestRequest(BaseModel):
    pdb_id: str = Field(..., min_length=4, max_length=4, description="PDB ID de 4 caracteres")
    chain_id: str = Field(default="A", description="Cadena de interés")
    is_hot: bool = Field(default=False)
    structural_family: str | None = None
    cofactors_whitelist: list[str] | None = Field(default=None, description="Cofactores manuales a conservar (ej: ['HEM', 'ZN']). Si se omite, se intentará detectar automáticamente desde RCSB.")

@router.post(
    "/ingest",
    status_code=status.HTTP_201_CREATED,
    summary="Ingesta científica de una nueva proteína",
)
async def ingest_target(
    request: TargetIngestRequest,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Inicia el pipeline de ingesta científica:
    - Descarga estructura del RCSB.
    - Descubre pocket automáticamente basado en ligandos experimentales.
    - Mina hotspots (residuos críticos) automáticamente.
    - Prepara el receptor para Vina (PDBQT).
    - Actualiza el catálogo en tiempo real.
    """
    from services.targets.ingestion_manager import ingest_new_target

    try:
        result = await ingest_new_target(
            pdb_id=request.pdb_id,
            db=db,
            chain_id=request.chain_id,
            is_hot=request.is_hot,
            structural_family=request.structural_family,
            cofactors_whitelist=request.cofactors_whitelist,
            user_id=str(current_user.id),
        )
        return result
    except Exception as e:
        log.error("error_ingesta_api", pdb_id=request.pdb_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fallo en la ingesta científica. Por favor verifica el PDB ID y vuelve a intentarlo."
        )

from fastapi import UploadFile, File, Form
@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    summary="Subir y preparar un target personalizado",
)
async def upload_custom_target(
    file: UploadFile = File(...),
    source_file: UploadFile | None = File(
        None, description="Estructura de origen del PDBQT (PDB o mmCIF); opcional, sólo con is_curated"),
    name: str = Form(...),
    is_curated: bool = Form(...),
    modo_preparacion: str | None = Form(
        None, description="automatico (estructura cruda), respetar (estructura ya preparada) o pdbqt"),
    chain_id: str = Form("A"),
    grid_center_x: float | None = Form(None),
    grid_center_y: float | None = Form(None),
    grid_center_z: float | None = Form(None),
    grid_size_x: float = Form(20.0),
    grid_size_y: float = Form(20.0),
    grid_size_z: float = Form(20.0),
    cofactors_whitelist: str | None = Form(None, description="Coma-separated list"),
    is_community: bool = Form(False),
    is_anti_target: bool = Form(False, description="Marcar como anti-target de seguridad"),
    anti_target_risk: str | None = Form(None, description="Descripcion del riesgo de inhibir este target"),
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from services.targets.ingestion_manager import ingest_custom_target

    grid_center = None
    if grid_center_x is not None and grid_center_y is not None and grid_center_z is not None:
        grid_center = (grid_center_x, grid_center_y, grid_center_z)

    grid_size = (grid_size_x, grid_size_y, grid_size_z)
    from services.targets.box_validation import validar_caja
    try:
        center_values = (grid_center_x, grid_center_y, grid_center_z)
        if any(v is not None for v in center_values) and grid_center is None:
            raise ValueError("Debes indicar las tres coordenadas del centro.")
        validar_caja(grid_center, grid_size)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    cofactors = []
    if cofactors_whitelist:
        cofactors = [c.strip().upper() for c in cofactors_whitelist.split(",") if c.strip()]

    # SEC-C08: 31 MiB de archivo deja margen al sobre multipart bajo
    # BodyLimitMiddleware (32 MiB para el cuerpo HTTP completo).
    MAX_SIZE = 31 * 1024 * 1024
    content = await file.read(MAX_SIZE + 1)
    if len(content) > MAX_SIZE:
        return JSONResponse(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, content=ErrorDeSubida(
            "ARCHIVO_DEMASIADO_GRANDE",
            "El archivo supera los 31 MiB. Recorta del archivo las cadenas que no vas a usar, o "
            "súbelo comprimido (.gz).",
            "The file is larger than 31 MiB. Remove the chains you will not use, or upload it "
            "compressed (.gz).",
            estado=413,
        ).como_json(current_locale()))

    origen_content = origen_filename = None
    if source_file is not None and (source_file.filename or "") != "":
        origen_content = await source_file.read(MAX_SIZE + 1)
        origen_filename = source_file.filename
        if len(origen_content) > MAX_SIZE:
            return JSONResponse(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, content=ErrorDeSubida(
                "ARCHIVO_DEMASIADO_GRANDE",
                "La estructura de origen supera los 31 MiB. Recorta las cadenas que no uses, o súbela "
                "comprimida (.gz).",
                "The source structure is larger than 31 MiB. Remove the chains you do not use, or upload it "
                "compressed (.gz).",
                estado=413,
            ).como_json(current_locale()))

    # SEC-C08: el contenido se valida por formato en `leer_subida` (extensión sin distinguir
    # mayúsculas, .gz con tope, contenido que corresponde a la extensión), dentro de la ingesta.

    creator_id = current_user.id
    creator_username = current_user.username

    try:
        result = await ingest_custom_target(
            file_content=content,
            filename=file.filename or "unknown",
            name=name,
            is_curated=is_curated,
            db=db,
            chain_id=chain_id,
            grid_center=grid_center,
            grid_size=grid_size,
            cofactors_whitelist=cofactors,
            creator_id=creator_id,
            creator_username=creator_username,
            is_community=is_community,
            is_anti_target=is_anti_target,
            anti_target_risk=anti_target_risk,
            origen_content=origen_content,
            origen_filename=origen_filename,
            modo_preparacion=modo_preparacion,
        )
        return result
    except ErrorDeSubida as e:
        # Un fallo que la persona puede corregir: se le dice cuál y qué hacer, en su idioma.
        log.warning("upload_target_rechazado", codigo=e.codigo)
        return JSONResponse(status_code=e.estado, content=e.como_json(current_locale()))
    except ValueError as e:
        log.warning("upload_target_validation_error", error=str(e))
        raise HTTPException(status_code=400, detail="Error de validación. Por favor verifica el archivo y los parámetros.")
    except Exception as e:
        log.error("error_upload_target_api", error=str(e))
        raise HTTPException(status_code=500, detail="Error interno al procesar el target.")

@router.get(
    "/",
    response_model=list[Target],
    summary="Listar todos los targets biológicos disponibles",
)
async def list_targets(
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
) -> list[Target]:
    repo = Repository(db)
    all_targets = await repo.get_all_targets()
    # Ensure default target is seeded if empty
    if not all_targets:
        await repo.ensure_default_target()
        all_targets = await repo.get_all_targets()

    targets = []
    for t in all_targets:
        if not target_is_accessible(t, current_user):
            continue
        # FIX (2026-08-04, catálogo de producción): excluir targets NO curados
        # (sin structural_family) del catálogo público. Un target auto-ingestado
        # (PDB tecleado por el usuario) o legacy sin familia NO pasó curación
        # científica: sin family-gating, sin spearman_rho calibrado, sin
        # stacking weights validados → mostrarlo en el selector con familia
        # Default y ρ=null engaña al usuario (ver docs/36 UI-8). Solo el
        # propietario autenticado puede verlo.
        if not t.is_private and not t.is_community and t.structural_family is None:
            continue
        # Retirado del catalogo curado (doc 72). La fila se conserva porque
        # puede haber evaluaciones colgando de ella -y borrarlas seria destruir
        # trabajo del usuario-, pero no se vuelve a ofrecer para evaluar: 2ONV
        # y 5TXJ son cristales de hexapeptido, y una caja de 22 A sobre seis
        # residuos es un 97% de vacio.
        if getattr(t, "retired_reason", None):
            continue
        targets.append(t)

    enriched_targets = []
    con_hotspots: list[tuple[Target, str, str | None]] = []
    for t in targets:
        t_schema = Target.model_validate(t)
        # SC-9: el catálogo declara qué respaldo tiene cada receptor. Estar en
        # el catálogo significa «curado estructuralmente»; sólo un ρ medido
        # significa «calibrado», y hoy no lo tiene ninguno. Que la interfaz
        # tenga el dato es lo que impide que los presente todos igual.
        t_schema.calibracion = estado_de_calibracion(t).to_dict()
        # Una diana que hoy no se puede preparar se lista igual, con su motivo:
        # ocultarla borraría el catálogo; ofrecerla haría fallar la corrida.
        t_schema.motivo_no_disponible = motivo_no_disponible(t.pdb_id)
        t_schema.disponible = t_schema.motivo_no_disponible is None
        # Disponible no es intacta: con la receta v7 una diana puede acoplarse
        # con cadenas laterales del sitio truncadas. Se dice antes de elegirla.
        t_schema.cadenas_truncadas_en_sitio = cadenas_truncadas_en_sitio(t.pdb_id)
        from services.targets.seccion_catalogo import (
            avisos_del_receptor, intentos_del_receptor, seccion_del_receptor, verificacion_del_receptor,
        )
        t_schema.seccion_catalogo = seccion_del_receptor(t)
        t_schema.verificacion = (
            verificacion_del_receptor(t.pdb_id) if t_schema.seccion_catalogo else None
        )
        t_schema.avisos_catalogo = avisos_del_receptor(t.pdb_id) if t_schema.seccion_catalogo else []
        # Intentos publicados, pasen o no: un NO_GO se enseña con sus cifras.
        t_schema.intentos_verificacion = (
            intentos_del_receptor(t.pdb_id) if t_schema.seccion_catalogo else []
        )

        if t_schema.hotspots:
            con_hotspots.append((t_schema, t.pdb_id, t.chain))
        enriched_targets.append(t_schema)

    # Las coordenadas de los hotspots se leen del PDB de cada receptor: E/S de disco y análisis de cientos de archivos.
    # En el bucle de eventos congelaba el backend al abrir cualquier pestaña con el catálogo (2026-10-10): en un hilo.
    await asyncio.to_thread(_coordenadas_de_hotspots, con_hotspots)
    return enriched_targets


def _coordenadas_de_hotspots(con_hotspots: list[tuple[Target, str, str | None]]) -> None:
    """Enriquece los hotspots de cada receptor con las coordenadas de su CA, si el PDB existe."""
    import os

    from services.docking.preparer import get_target_pdb_path
    from utils.structural import get_residue_coordinates

    for t_schema, pdb_id, chain in con_hotspots:
        pdb_path = get_target_pdb_path(pdb_id)

        # Rutas de desarrollo locales alternativas
        if not os.path.exists(pdb_path):
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
            pdb_path = os.path.join(base_dir, f"{pdb_id.lower()}.pdb")
            if not os.path.exists(pdb_path):
                pdb_path = os.path.join(base_dir, f"{pdb_id.upper()}.pdb")
            if not os.path.exists(pdb_path):
                pdb_path = os.path.join(base_dir, "data", "targets", f"{pdb_id}.pdb")

        if os.path.exists(pdb_path):
            h_names = [h.get("name") for h in t_schema.hotspots if h.get("name")]
            # Filtro por la cadena del receptor: evita tomar el CA de un
            # residuo homónimo en otra cadena (complejos multicadena).
            coords_map = get_residue_coordinates(pdb_path, h_names, chain=chain)
            for h in t_schema.hotspots:
                name = h.get("name")
                lookup_name = name.upper() if name else ""
                if ":" in lookup_name:
                    lookup_name = lookup_name.split(":")[-1]

                if lookup_name in coords_map:
                    h["x"] = round(coords_map[lookup_name][0], 2)
                    h["y"] = round(coords_map[lookup_name][1], 2)
                    h["z"] = round(coords_map[lookup_name][2], 2)


@router.post(
    "/{target_id}/share",
    summary="Compartir un target privado con la comunidad",
)
async def share_target_with_community(
    target_id: str,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    from sqlalchemy import select
    from core.models import TargetORM
    import uuid

    stmt = None
    try:
        target_uuid = uuid.UUID(target_id)
        stmt = select(TargetORM).where(TargetORM.id == target_uuid)
    except ValueError:
        stmt = select(TargetORM).where(TargetORM.pdb_id == target_id.upper())

    result = await db.execute(stmt)
    target = result.scalar_one_or_none()

    target = require_target_object_access(target, current_user)

    # Compartir es una mutación reservada al creador incluso si el receptor ya
    # fuera público por otro mecanismo.
    if target.creator_id != current_user.id:
        raise HTTPException(status_code=404, detail="No existe el receptor solicitado.")

    target.is_community = True
    target.is_private = False

    if not target.creator_username:
        target.creator_username = current_user.username

    await db.commit()
    return {"status": "shared", "target_id": str(target.id)}


class ResolveTargetNameRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=100, description="Nombre de la proteína (ej: EGFR, CDK4, 5-HT1A)")
    max_results: int = Field(default=10, ge=1, le=50, description="Máximo de resultados")

class RCSBSearchResult(BaseModel):
    pdb_id: str
    title: str
    method: str
    resolution: float | None
    organism: str

class ResolveTargetNameResponse(BaseModel):
    query: str
    total: int
    results: list[RCSBSearchResult]
    source: str = "RCSB PDB (Search API v2)"


@router.post(
    "/resolve-name",
    response_model=ResolveTargetNameResponse,
    summary="Buscar estructuras en RCSB PDB por nombre de proteína",
)
async def resolve_target_name(
    request: ResolveTargetNameRequest,
    current_user: UserORM = Depends(get_current_user),
):
    """
    Busca estructuras experimentales en RCSB PDB por nombre de proteína.

    El endpoint consulta la RCSB Search API v2 + Data API, retornando
    los mejores resultados ordenados por resolución (mejor primero).

    Útil para el frontend: el usuario escribe "EGFR" y obtiene una lista
    de PDB IDs para seleccionar sin tener que memorizar códigos.

    Ejemplos de búsqueda:
      - "EGFR" → retorna estructuras de EGFR (receptor EGF)
      - "CDK4" → retorna quinasa dependiente de ciclina 4
      - "5-HT1A" → retorna receptor de serotonina 1A
    """
    from utils.file_handlers import search_rcsb_by_name

    try:
        results = await search_rcsb_by_name(
            query=request.query,
            max_results=request.max_results,
        )
        return ResolveTargetNameResponse(
            query=request.query,
            total=len(results),
            results=[RCSBSearchResult(**r) for r in results],
        )
    except Exception as e:
        log.error("resolve_target_name_failed", query=request.query, error=str(e))
        raise HTTPException(status_code=502, detail="RCSB no está disponible para la búsqueda.") from e


class AlphaFoldLookupRequest(BaseModel):
    uniprot_id: str = Field(..., min_length=4, max_length=20, description="UniProt accession (ej: P08908)")


class AlphaFoldEntryResponse(BaseModel):
    uniprot_id: str
    gene: str | None
    organism: str | None
    model_url: str
    mean_plddt: float | None
    high_confidence_residues: int | None
    total_residues: int | None
    warnings: list[str]


class TargetSearchResponse(BaseModel):
    results: list[AlphaFoldEntryResponse]
    source: str = "AlphaFold DB"
    disclaimer: str = (
        "Las estructuras de AlphaFold son modelos computacionales (predicciones). "
        "No equivalen a datos experimentales cryo-EM o cristalográficos. "
        "Los resultados de docking contra estas estructuras tienen mayor incertidumbre."
    )


@router.get(
    "/alphafold/lookup/{uniprot_id}",
    response_model=AlphaFoldEntryResponse,
    summary="Buscar proteína en AlphaFold DB por UniProt ID",
)
async def alphafold_lookup(
    uniprot_id: str,
    current_user: UserORM = Depends(get_current_user),
) -> AlphaFoldEntryResponse:
    """
    Busca una proteína en AlphaFold Database por UniProt accession.

    Devuelve metadata del modelo incluyendo métricas de confianza (pLDDT)
    que deben consultarse antes de usar la estructura para docking.
    """
    from services.alphafold.client import download_structure, lookup_uniprot

    from urllib.error import HTTPError, URLError
    from services.red import SalidaNoAutorizada
    try:
        entry = await lookup_uniprot(uniprot_id.strip().upper())
    except SalidaNoAutorizada as exc:
        raise HTTPException(status_code=403, detail="Salida de red no autorizada.") from exc
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        log.warning("alphafold_lookup_unavailable", error=str(exc))
        raise HTTPException(status_code=503, detail="AlphaFold DB no está disponible.") from exc
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Proteína {uniprot_id} no encontrada en AlphaFold DB",
        )

    # Descargar y analizar confianza
    try:
        structure = await download_structure(entry)
        return AlphaFoldEntryResponse(
            uniprot_id=entry.uniprot_id,
            gene=entry.gene,
            organism=entry.organism,
            model_url=entry.model_url,
            mean_plddt=entry.mean_plddt,
            high_confidence_residues=entry.high_confidence_residues,
            total_residues=entry.total_residues,
            warnings=structure.warnings,
        )
    except SalidaNoAutorizada as exc:
        raise HTTPException(status_code=403, detail="Salida de red no autorizada.") from exc
    except (URLError, HTTPError, TimeoutError, OSError) as exc:
        log.warning("alphafold_structure_unavailable", error=str(exc))
        raise HTTPException(status_code=503, detail="AlphaFold DB no está disponible.") from exc
    except Exception as e:
        log.error("error procesando estructura AlphaFold", error=str(e))
        return AlphaFoldEntryResponse(
            uniprot_id=entry.uniprot_id,
            gene=entry.gene,
            organism=entry.organism,
            model_url=entry.model_url,
            mean_plddt=None,
            high_confidence_residues=None,
            total_residues=None,
            warnings=[
                "No se pudo analizar la estructura AlphaFold.",
                "La estructura puede descargarse manualmente desde AlphaFold DB.",
            ],
        )


@router.get(
    "/alphafold/search",
    response_model=TargetSearchResponse,
    summary="Buscar proteínas por nombre de gen",
)
async def alphafold_search(
    gene: str = Query(..., min_length=2, max_length=50, description="Nombre del gen (ej: HTR1A)"),
    organism: str = Query(default="Homo sapiens", description="Organismo"),
    current_user: UserORM = Depends(get_current_user),
) -> TargetSearchResponse:
    """
    Busca proteínas en AlphaFold DB a través de UniProt por nombre de gen.
    Útil cuando se quiere explorar targets nuevos sin conocer el UniProt ID.
    """
    from services.alphafold.client import search_by_gene

    entries = await search_by_gene(gene.strip(), organism)

    results = [
        AlphaFoldEntryResponse(
            uniprot_id=e.uniprot_id,
            gene=e.gene,
            organism=e.organism,
            model_url=e.model_url,
            mean_plddt=e.mean_plddt,
            high_confidence_residues=e.high_confidence_residues,
            total_residues=e.total_residues,
            warnings=[],
        )
        for e in entries
    ]

    return TargetSearchResponse(results=results)

# ── Community ─────────────────────────────────────────────────────

@router.get("/community", summary="Targets compartidos por la comunidad")
async def get_community_targets(db: AsyncSession = Depends(get_db)):
    """Retorna todos los targets marcados como publicos por la comunidad."""
    repository = Repository(db)
    all_targets = await repository.get_all_targets()
    community = [t for t in all_targets if t.is_community]
    return [Target(
        id=t.id, pdb_id=t.pdb_id, name=t.name, chain=t.chain,
        description=t.description, is_prepared=t.is_prepared,
        requires_cns=t.requires_cns, structural_family=t.structural_family,
        organism=t.organism, resolution=t.resolution,
        hotspots=t.hotspots, affinity_threshold=t.affinity_threshold,
        is_hot=t.is_hot, spearman_rho=t.spearman_rho,
        calibration_date=t.calibration_date,
        grid_center_x=t.grid_center_x, grid_center_y=t.grid_center_y,
        grid_center_z=t.grid_center_z,
        grid_size_x=t.grid_size_x, grid_size_y=t.grid_size_y,
        grid_size_z=t.grid_size_z,
        cofactors_whitelist=t.cofactors_whitelist or [],
        is_private=t.is_private, is_community=t.is_community,
        is_anti_target=t.is_anti_target if hasattr(t, 'is_anti_target') else False,
        anti_target_risk=t.anti_target_risk if hasattr(t, 'anti_target_risk') else None,
        creator_username=t.creator_username,
    ) for t in community]

@router.post("/community/download/{pdb_id}", summary="Descargar target de la comunidad")
async def download_community_target(
    pdb_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: UserORM = Depends(get_current_user),
):
    """
    Descarga un target de la comunidad e ingesta localmente.
    """
    if not is_rcsb_pdb_id(pdb_id.upper()):
        raise HTTPException(status_code=422, detail="PDB ID inválido")
    pdb_id = pdb_id.upper()

    # Ingresar localmente
    from services.targets.ingestion_manager import ingest_new_target
    from services.red import SalidaNoAutorizada
    try:
        result = await ingest_new_target(
            pdb_id=pdb_id, db=db, force_reingest=False,
            user_id=str(current_user.id),
        )
    except SalidaNoAutorizada as exc:
        raise HTTPException(status_code=403, detail="Salida de red no autorizada.") from exc
    except (ConnectionError, TimeoutError, OSError, RuntimeError) as exc:
        log.warning("community_target_download_unavailable", pdb_id=pdb_id, error=str(exc))
        raise HTTPException(status_code=503, detail="El servicio de estructuras no está disponible.") from exc
    return {"success": True, "message": f"Target {pdb_id} descargado e ingerido", "result": result}

async def _read_variant_source_bytes(target: TargetORM) -> bytes:
    """Obtiene la fuente PDB real; un PDBQT externo no se finge como PDB."""

    from pathlib import Path

    from services.docking.preparer import get_target_pdb_path
    from utils.file_handlers import StoragePath
    from utils.local_storage import exists, read_bytes

    logical_raw = StoragePath.target_raw(target.pdb_id)
    if await exists(logical_raw):
        return await read_bytes(logical_raw)

    path = Path(get_target_pdb_path(target.pdb_id))
    if path.is_file() and path.suffix.lower() in {".pdb", ".ent"}:
        return path.read_bytes()

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            "Este receptor sólo conserva un PDBQT preparado y no tiene una fuente PDB "
            "que pueda volver a prepararse. Sube otra preparación PDBQT o parte de un PDB."
        ),
    )


@router.post(
    "/{pdb_id}/variants",
    response_model=Target,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una variante privada e inmutable de preparación",
)
async def create_target_variant(
    pdb_id: str,
    request: TargetVariantRequest,
    current_user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TargetORM:
    """Reutiliza el preparador automático y publica su salida como target propio."""

    from services.targets.ingestion_manager import ingest_custom_target

    repository = Repository(db)
    parent = await get_target_for_user(repository, pdb_id, current_user)
    source_bytes = await _read_variant_source_bytes(parent)

    chain = (request.chain_id or parent.chain or "A").strip().upper()
    center = request.grid_center or (
        float(parent.grid_center_x),
        float(parent.grid_center_y),
        float(parent.grid_center_z),
    )
    size = request.grid_size or (
        float(parent.grid_size_x),
        float(parent.grid_size_y),
        float(parent.grid_size_z),
    )
    recipe = {
        "schema_version": 1,
        "mode": "automatic_meeko",
        "parent_pdb_id": parent.pdb_id,
        "chain": chain,
        "grid_center": [float(value) for value in center],
        "grid_size": [float(value) for value in size],
        "cofactors_whitelist": request.cofactors_whitelist,
        "waters": "remove_all",
        "altloc": "majority_or_default",
    }

    from services.docking.preparer import ligando_del_sitio
    from services.targets import perfil_receptor

    # El ligando del cristal del padre se retira también en la variante; sin él se conservaba como cofactor (8UBR, MET-01).
    ligando_padre = ligando_del_sitio(parent.pdb_id)
    if ligando_padre:
        recipe["site_ligand"] = ligando_padre
    perfil_padre = perfil_receptor.cargar(parent.pdb_id) or {}
    respetando = perfil_padre.get("modo") == perfil_receptor.MODO_RESPETAR
    if respetando:
        # Una variante de un receptor ya preparado parte del mismo archivo y se prepara igual: respetándolo.
        recipe = {**recipe, "mode": "respect_user_preparation", "protonation": "declared_by_user",
                  "waters": "kept_as_uploaded"}
        recipe.pop("cofactors_whitelist", None)
    result = await ingest_custom_target(
        file_content=source_bytes,
        filename=f"{parent.pdb_id}.pdb",
        name=request.name,
        modo_preparacion=perfil_receptor.MODO_RESPETAR if respetando else None,
        is_curated=False,
        db=db,
        chain_id=chain,
        grid_center=center,
        grid_size=size,
        cofactors_whitelist=request.cofactors_whitelist,
        creator_id=current_user.id,
        creator_username=current_user.username,
        is_community=False,
        preparation_parent_id=parent.id,
        preparation_recipe=recipe,
        site_ligand=ligando_padre,
    )
    return result["target"]


@router.get(
    "/{target_id_or_pdb}/pdb",
    response_class=PlainTextResponse,
    summary="Descargar archivo PDB de un target por ID o PDB ID",
)
async def get_target_pdb(
    target_id_or_pdb: str,
    current_user: UserORM | None = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
) -> PlainTextResponse:
    """
    Retorna el archivo PDB del target biológico especificado por su UUID o PDB ID.
    Busca primero localmente y luego descarga de RCSB PDB si no existe.
    """
    from services.docking.preparer import get_target_pdb_path
    from utils.file_handlers import download_pdb_from_rcsb, StoragePath
    from utils.local_storage import exists, read_text
    from fastapi.responses import PlainTextResponse
    from pathlib import Path
    from uuid import UUID

    repository = Repository(db)

    # Intentar resolver como UUID de base de datos
    target = None
    identifier_is_uuid = False
    try:
        target_uuid = UUID(target_id_or_pdb)
        identifier_is_uuid = True
        target = await db.get(TargetORM, target_uuid)
    except ValueError:
        if not is_safe_local_target_id(target_id_or_pdb):
            raise HTTPException(status_code=422, detail="Identificador de receptor inválido")
        target = await repository.get_target_by_pdb_id(target_id_or_pdb.upper())

    if target is not None:
        target = require_target_object_access(target, current_user)
    elif identifier_is_uuid or target_id_or_pdb.upper().startswith("USR_"):
        # UUID y USR_* son identificadores internos. Nunca caen al lookup de
        # archivos ni a RCSB si la fila no existe o dejó de existir.
        raise HTTPException(status_code=404, detail="No existe el receptor solicitado.")

    pdb_id = target.pdb_id if target else target_id_or_pdb.upper()
    if not is_safe_local_target_id(pdb_id) or (target is None and not is_rcsb_pdb_id(pdb_id)):
        raise HTTPException(status_code=404, detail="No existe el receptor solicitado.")

    # 1. Buscar en biblioteca local (pre-cargada)
    try:
        local_path = Path(get_target_pdb_path(pdb_id))
        if local_path.exists():
            return PlainTextResponse(content=local_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        pass

    # 2. Buscar en el almacenamiento local
    raw_path = StoragePath.target_raw(pdb_id)
    try:
        if await exists(raw_path):
            content = await read_text(raw_path)
            return PlainTextResponse(content=content)
    except Exception:
        pass

    # 3. La copia que viaja en el instalador. Materializarla es copiar un archivo
    # del bundle, no descargar. Sin este paso, con un perfil nuevo el visor pedía
    # cualquier receptor del catálogo a RCSB (403 sin consentimiento, o la red en
    # un producto offline) hasta que una comprobación previa lo sembrara: nada
    # llama a la siembra del arranque (QA-031).
    try:
        from services.semilla_estructuras import sembrar_una

        sembrada = await asyncio.to_thread(sembrar_una, pdb_id)
        if sembrada is not None:
            return PlainTextResponse(
                content=sembrada.read_text(encoding="utf-8", errors="replace")
            )
    except Exception:
        pass

    # 4. Descargar de RCSB
    try:
        content = await download_pdb_from_rcsb(
            pdb_id, user_id=str(current_user.id) if current_user else None
        )
        return PlainTextResponse(content=content)
    except Exception as e:
        from services.red import SalidaNoAutorizada
        if isinstance(e, SalidaNoAutorizada):
            raise HTTPException(status_code=403, detail=str(e)) from e
        raise HTTPException(
            status_code=404,
            detail=f"No se pudo encontrar el PDB {pdb_id}."
        )

