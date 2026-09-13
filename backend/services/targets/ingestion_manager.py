"""
services/targets/ingestion_manager.py

Motor de ingesta científica de proteínas.
Automatiza la descarga, análisis de pockets y preparación estructural.
"""

import hashlib
import json
import uuid
from importlib import metadata
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import TargetORM
from db.repository import Repository
from services.docking.preparer import prepare_target
from utils.file_handlers import download_pdb_from_rcsb, StoragePath, fetch_target_cofactors_from_rcsb
from services.chemistry.censo_de_aguas import invalidar_censo
from utils.local_storage import exists, read_bytes, read_text, write_text
from services.targets.sitio_de_union import anotar_sitio
from utils.structural import discover_pocket_from_pdb
from utils.logger import get_logger

log = get_logger(__name__)


def _toolchain_identity() -> dict[str, str]:
    """Versiones efectivas que convierten una receta en un artefacto."""

    try:
        meeko_version = metadata.version("meeko")
    except metadata.PackageNotFoundError:
        meeko_version = "unknown"
    return {
        "moldesign_preparation_policy": "1",
        "meeko": meeko_version,
    }


def _preparation_provenance(
    *, source_bytes: bytes, prepared_bytes: bytes, recipe: dict,
    toolchain: dict | None = None,
) -> dict[str, object]:
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    prepared_sha = hashlib.sha256(prepared_bytes).hexdigest()
    effective_toolchain = toolchain or _toolchain_identity()
    canonical = json.dumps(
        {
            "source_sha256": source_sha,
            "recipe": recipe,
            "toolchain": effective_toolchain,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return {
        "receptor_source_sha256": source_sha,
        "prepared_receptor_sha256": prepared_sha,
        "preparation_fingerprint": hashlib.sha256(canonical).hexdigest(),
        "preparation_recipe": recipe,
        "preparation_toolchain": effective_toolchain,
    }

async def ingest_new_target(
    pdb_id: str,
    db: AsyncSession,
    chain_id: str = "A",
    ligand_chain: str | None = None,
    is_hot: bool = False,
    structural_family: str | None = None,
    cofactors_whitelist: list[str] | None = None,
    force_reingest: bool = False
) -> dict:
    """
    Orquesta la ingesta completa de un target desde el PDB ID.
    1. Descarga metadata y estructura.
    2. Descubre pocket automáticamente.
    3. Prepara receptor (PDBQT).
    4. Persiste en DB.
    """
    pdb_id = pdb_id.upper().strip()
    repo = Repository(db)

    # 1. Verificar si ya existe
    existing = await repo.get_target_by_pdb_id(pdb_id)
    if existing and existing.is_prepared and not force_reingest:
        return {"success": True, "message": f"Target {pdb_id} ya existe y está preparado.", "target": existing}

    # 2. Descargar PDB crudo
    log.info("ingesta_iniciada", pdb_id=pdb_id)
    raw_path = StoragePath.target_raw(pdb_id)
    if not await exists(raw_path):
        pdb_content = await download_pdb_from_rcsb(pdb_id)
        await write_text(raw_path, pdb_content)
        # El censo de aguas se cachea por (pdb_id, caja) y no puede enterarse
        # solo de que el archivo cambió. Ver `services/chemistry/censo_de_aguas`.
        invalidar_censo(pdb_id)
    else:
        pdb_content = await read_text(raw_path)

    # 3. Descubrir Pocket y Hotspots
    pocket_info = discover_pocket_from_pdb(pdb_content, chain_id, ligand_chain)
    if not pocket_info["success"]:
        log.warning("pocket_discovery_fallido", pdb_id=pdb_id,
                    error=pocket_info.get("error"),
                    warnings=pocket_info.get("warnings", []))
        raise ValueError(
            f"No se pudo detectar automaticamente el sitio activo para {pdb_id}. "
            f"{pocket_info.get('error', 'Error desconocido')}. "
            "Usa el modo MANUAL para proporcionar coordenadas del grid box."
        )

    # Use auto-detected chain if available
    detected_chain = pocket_info.get("detected_chain", chain_id)
    if detected_chain != chain_id:
        log.info("cadena_autodetectada", pdb_id=pdb_id,
                 esperada=chain_id, detectada=detected_chain)

    center = pocket_info["grid_center"]
    size = pocket_info.get("grid_size", (25.0, 25.0, 25.0))
    hotspots = pocket_info["suggested_hotspots"]
    auto_warnings = pocket_info.get("warnings", [])
    all_ligands_found = pocket_info.get("all_ligands_found", [])

    # Extraer el nombre de 3 letras del ligando de referencia
    ligand_name = pocket_info.get("ligand_name", "")
    main_ligand_name = ligand_name[:3] if ligand_name else ""

    # 3.5 Cofactors Whitelist (Automatizado si no se provee)
    if cofactors_whitelist is None:
        cofactors_whitelist = await fetch_target_cofactors_from_rcsb(pdb_id)

    # Asegurarnos de no conservar el ligando principal contra el que vamos a hacer docking
    if main_ligand_name and main_ligand_name in cofactors_whitelist:
        cofactors_whitelist.remove(main_ligand_name)
        log.info("ligando principal removido de la lista blanca", pdb_id=pdb_id, removed=main_ligand_name)

    log.info("cofactores a conservar", pdb_id=pdb_id, whitelist=cofactors_whitelist)

    # 3.6 Que cadenas forman el sitio (doc 71). Se mide sobre el PDB COMPLETO:
    # filtrarlo antes haria imposible ver que el sitio se forma ENTRE cadenas, y
    # el receptor se prepararia con media cavidad. Es la misma funcion que anota
    # el catalogo curado, no una segunda implementacion.
    sitio = anotar_sitio(pdb_content, center, size) or {}
    if len(sitio.get("site_chains") or []) > 1:
        log.info("sitio_multicadena_detectado", pdb_id=pdb_id,
                 cadenas=sitio["site_chains"], evidencia=sitio.get("site_evidence"))

    # 4. Preparar Estructuralmente (PDBQT)
    try:
        prepared_file_path = await prepare_target(
            pdb_id=pdb_id,
            chain_id=detected_chain,
            site_chains=sitio.get("site_chains"),
            center=center,
            size=size,
            force_reprepare=True,
            cofactors_whitelist=cofactors_whitelist
        )
    except Exception as e:
        log.error("preparacion_fallida", pdb_id=pdb_id, error=str(e))
        raise

    # 5. Persistir en DB
    if not existing:
        # v1.7: Resolver nombre biológico desde el HEADER/TITLE del PDB
        _target_name = pdb_id
        if pdb_content and isinstance(pdb_content, str):
            for line in pdb_content.split("\n"):
                stripped = line.strip()
                if stripped.startswith("TITLE "):
                    _target_name = stripped[6:80].strip().rstrip(".").strip().strip('"').strip("'")
                    break
                elif stripped.startswith("HEADER") and _target_name == pdb_id:
                    comp = stripped[10:50].strip().split()
                    if comp:
                        _target_name = comp[0]
        target = TargetORM(
            pdb_id=pdb_id,
            name=_target_name,
            chain=chain_id,
            grid_center_x=center[0],
            grid_center_y=center[1],
            grid_center_z=center[2],
            grid_size_x=size[0],
            grid_size_y=size[1],
            grid_size_z=size[2],
            requires_cns=False,
            is_prepared=True,
            prepared_file_path=prepared_file_path,
            is_hot=is_hot,
            # Un PDB auto-ingerido proviene de RCSB y no es información
            # privada. Tampoco tiene un propietario único: varias cuentas
            # pueden evaluar el mismo PDB. Se mantiene fuera del catálogo por
            # carecer de curación científica (structural_family=None), no
            # fingiendo una propiedad que dejaría una fila huérfana.
            is_private=False,
            is_community=False,
            structural_family=structural_family,
            hotspots=hotspots,
            # Doc 71. Sin esto la tarjeta diria «Sitio sin medir» y la
            # preparacion volveria a conservar una sola cadena.
            **sitio,
            hotspots_source="auto_pocket_top15",
            cofactors_whitelist=cofactors_whitelist
        )
        db.add(target)
    else:
        existing.is_prepared = True
        existing.prepared_file_path = prepared_file_path
        existing.grid_center_x = center[0]
        existing.grid_center_y = center[1]
        existing.grid_center_z = center[2]
        for campo, valor in sitio.items():
            setattr(existing, campo, valor)
        existing.hotspots = hotspots
        existing.cofactors_whitelist = cofactors_whitelist
        if structural_family:
            existing.structural_family = structural_family
        existing.is_hot = is_hot
        target = existing

    await db.commit()
    log.info("ingesta_completada", pdb_id=pdb_id, center=center, hotspots_count=len(hotspots))

    return {
        "success": True,
        "pdb_id": pdb_id,
        "center": center,
        "hotspots_mined": len(hotspots),
        "ligand_reference": pocket_info.get("ligand_id"),
        "target": target,  # BUGFIX: caller needs the TargetORM to use after ingestion
    }

def extract_pdb_metadata(pdb_text: str) -> dict:
    """
    Extrae metadatos del PDB como el organismo (científico o común) y la resolución.
    """
    organism = None
    resolution = None
    for line in pdb_text.splitlines():
        if line.startswith("SOURCE"):
            if "ORGANISM_SCIENTIFIC:" in line:
                org_part = line.split("ORGANISM_SCIENTIFIC:")[1].split(";")[0].strip().title()
                if org_part:
                    organism = org_part
            elif "ORGANISM_COMMON:" in line and not organism:
                org_part = line.split("ORGANISM_COMMON:")[1].split(";")[0].strip().title()
                if org_part:
                    organism = org_part
        elif line.startswith("REMARK   2 RESOLUTION."):
            parts = line.split()
            for p in parts:
                try:
                    val = float(p)
                    resolution = val
                    break
                except ValueError:
                    continue
    return {"organism": organism, "resolution": resolution}

async def ingest_custom_target(
    file_content: bytes,
    filename: str,
    name: str,
    is_curated: bool,
    db: AsyncSession,
    chain_id: str = "A",
    grid_center: tuple[float, float, float] | None = None,
    grid_size: tuple[float, float, float] = (20.0, 20.0, 20.0),
    cofactors_whitelist: list[str] | None = None,
    creator_id: uuid.UUID | None = None,
    creator_username: str | None = None,
    is_community: bool = False,
    is_anti_target: bool = False,
    anti_target_risk: str | None = None,
    preparation_parent_id: uuid.UUID | None = None,
    preparation_recipe: dict | None = None,
) -> dict:
    """
    Ingesta un target subido manualmente por el usuario.
    Si is_curated=True, asume que es un archivo .pdbqt listo.
    Si is_curated=False, asume que es un .pdb y lo cura.
    """
    import uuid
    pdb_id = f"USR_{uuid.uuid4().hex[:6].upper()}"
    repo = Repository(db)

    log.info("ingesta_custom_iniciada", pdb_id=pdb_id, is_curated=is_curated)

    # Intentar extraer metadatos del archivo subido
    extracted_organism = None
    extracted_resolution = None
    try:
        decoded_text = file_content.decode('utf-8', errors='ignore')
        metadata = extract_pdb_metadata(decoded_text)
        extracted_organism = metadata.get("organism")
        extracted_resolution = metadata.get("resolution")
    except Exception as e:
        log.warning("error_extracting_metadata_from_custom_target", error=str(e))

    if is_curated:
        if not filename.endswith(".pdbqt"):
            raise ValueError("Los archivos curados deben ser formato .pdbqt")
        if not grid_center:
            raise ValueError("Debe proporcionar las coordenadas del grid (centro) para archivos curados (.pdbqt)")

        prepared_path = StoragePath.target_prepared(pdb_id)
        await write_text(prepared_path, file_content.decode('utf-8'))

        # La cadena la define el usuario (chain_id) o default A — en modo
        # manual el PDBQT ya viene preparado, no hay detección de cadena.
        detected_chain = chain_id or "A"
        recipe = preparation_recipe or {
            "schema_version": 1,
            "mode": "external_pdbqt",
            "chain": detected_chain,
            "grid_center": list(grid_center),
            "grid_size": list(grid_size),
            "cofactors_whitelist": sorted(set(cofactors_whitelist or [])),
        }
        provenance = _preparation_provenance(
            source_bytes=file_content,
            prepared_bytes=file_content,
            recipe=recipe,
        )

        target = TargetORM(
            pdb_id=pdb_id,
            name=name,
            chain=detected_chain,
            grid_center_x=grid_center[0],
            grid_center_y=grid_center[1],
            grid_center_z=grid_center[2],
            grid_size_x=grid_size[0],
            grid_size_y=grid_size[1],
            grid_size_z=grid_size[2],
            requires_cns=False,
            is_prepared=True,
            prepared_file_path=prepared_path,
            is_hot=False,
            is_private=not is_community,
            is_community=is_community,
            is_anti_target=is_anti_target,
            anti_target_risk=anti_target_risk,
            creator_id=creator_id,
            creator_username=creator_username,
            preparation_parent_id=preparation_parent_id,
            **provenance,
            cofactors_whitelist=cofactors_whitelist or [],
            organism=extracted_organism,
            resolution=extracted_resolution,
            spearman_rho=None
        )
        db.add(target)
        await db.commit()
        return {"success": True, "message": f"Target personalizado {pdb_id} subido exitosamente.", "target": target}
    else:
        if not filename.endswith(".pdb"):
            raise ValueError("Los archivos crudos deben ser formato .pdb")

        raw_path = StoragePath.target_raw(pdb_id)
        log.info("ingesta_custom_decodificando_archivo", pdb_id=pdb_id)
        try:
            decoded_content = file_content.decode('utf-8')
            log.info("ingesta_custom_decodificado_ok", pdb_id=pdb_id, size=len(decoded_content))
        except Exception as e:
            log.error("ingesta_custom_decodificado_error", pdb_id=pdb_id, error=str(e))
            raise ValueError(f"El archivo no es UTF-8 válido: {str(e)}")

        log.info("ingesta_custom_subiendo_storage_raw", pdb_id=pdb_id, path=raw_path)
        await write_text(raw_path, decoded_content)
        # Misma razón que arriba: la estructura depositada acaba de cambiar.
        invalidar_censo(pdb_id)
        log.info("ingesta_custom_subido_storage_raw_ok", pdb_id=pdb_id)

        pdb_text = file_content.decode('utf-8')
        hotspots = []
        center = grid_center
        auto_chain = chain_id

        if not center:
            # Intentar descubrir pocket
            pocket_info = discover_pocket_from_pdb(pdb_text, chain_id)
            if not pocket_info["success"]:
                raise ValueError(
                    f"No se pudo autodescubrir el sitio activo: {pocket_info.get('error')}. "
                    "Por favor proporciona las coordenadas manuales del grid box."
                )
            center = pocket_info["grid_center"]
            hotspots = pocket_info["suggested_hotspots"]
            # Use auto-detected chain if available
            auto_chain = pocket_info.get("detected_chain", chain_id)
            if auto_chain != chain_id:
                log.info("cadena_autodetectada_custom", detectada=auto_chain, original=chain_id)

        # Que cadenas forman el sitio (doc 71). Vale igual para un archivo subido
        # a mano: un usuario que suba la proteasa del VIH tiene el mismo derecho
        # a que no se le acople contra media cavidad.
        sitio = anotar_sitio(pdb_text, center, grid_size) or {}
        if len(sitio.get("site_chains") or []) > 1:
            log.info("sitio_multicadena_detectado_custom", pdb_id=pdb_id,
                     cadenas=sitio["site_chains"], evidencia=sitio.get("site_evidence"))

        # Curacion
        try:
            prepared_file_path = await prepare_target(
                pdb_id=pdb_id,
                chain_id=auto_chain,
                site_chains=sitio.get("site_chains"),
                center=center,
                size=grid_size,
                force_reprepare=True,
                cofactors_whitelist=cofactors_whitelist or []
            )
        except Exception as e:
            log.error("preparacion_custom_fallida", pdb_id=pdb_id, error=str(e))
            raise ValueError(f"Error curando el receptor: {str(e)}")

        prepared_bytes = await read_bytes(prepared_file_path)
        recipe = preparation_recipe or {
            "schema_version": 1,
            "mode": "automatic_meeko",
            "chain": auto_chain,
            "grid_center": [float(value) for value in center],
            "grid_size": [float(value) for value in grid_size],
            "cofactors_whitelist": sorted(set(cofactors_whitelist or [])),
            "waters": "remove_all",
            "altloc": "majority_or_default",
        }
        provenance = _preparation_provenance(
            source_bytes=file_content,
            prepared_bytes=prepared_bytes,
            recipe=recipe,
        )

        target = TargetORM(
            pdb_id=pdb_id,
            name=name,
            chain=auto_chain,
            grid_center_x=center[0],
            grid_center_y=center[1],
            grid_center_z=center[2],
            grid_size_x=grid_size[0],
            grid_size_y=grid_size[1],
            grid_size_z=grid_size[2],
            requires_cns=False,
            is_prepared=True,
            prepared_file_path=prepared_file_path,
            is_hot=False,
            is_private=not is_community,
            is_community=is_community,
            is_anti_target=is_anti_target,
            anti_target_risk=anti_target_risk,
            creator_id=creator_id,
            creator_username=creator_username,
            preparation_parent_id=preparation_parent_id,
            **provenance,
            hotspots=hotspots,
            **sitio,
            hotspots_source="auto_pocket_top15" if hotspots else None,
            cofactors_whitelist=cofactors_whitelist or [],
            organism=extracted_organism,
            resolution=extracted_resolution,
            spearman_rho=None
        )
        db.add(target)
        await db.commit()
        return {"success": True, "message": f"Target personalizado {pdb_id} curado e ingestado exitosamente.", "target": target}
