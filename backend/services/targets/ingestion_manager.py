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
from utils.local_storage import exists, read_bytes, read_text, write_bytes, write_text
from services.targets import perfil_receptor
from services.targets.conversion_mmcif import mmcif_a_pdb
from services.targets.entrada_receptor import (
    FORMATO_MMCIF,
    FORMATO_PDBQT,
    FORMATO_PQR,
    leer_subida,
    sin_proteina,
)
from services.targets.lector_pqr import pqr_a_pdb
from services.targets.normalizar_pdb import nombres_charmm_a_pdb, normalizar_pdb
from services.targets.prediccion import analizar as analizar_prediccion
from services.targets.errores_subida import (
    ErrorDeSubida,
    cadenas_con_proteina,
    desde_preparacion,
    error_de_cadena,
)
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
    force_reingest: bool = False,
    user_id: str | None = None,
) -> dict:
    """
    Orquesta la ingesta completa de un target desde el PDB ID.
    1. Descarga metadata y estructura.
    2. Descubre pocket automáticamente.
    3. Prepara receptor (PDBQT).
    4. Persiste en DB.
    """
    from services.targets.access import is_rcsb_pdb_id
    pdb_id = pdb_id.upper().strip()
    if not is_rcsb_pdb_id(pdb_id):
        raise ValueError("PDB ID inválido")
    repo = Repository(db)

    # 1. Verificar si ya existe
    existing = await repo.get_target_by_pdb_id(pdb_id)
    if existing and existing.is_prepared and not force_reingest:
        return {"success": True, "message": f"Target {pdb_id} ya existe y está preparado.", "target": existing}

    # 2. Descargar PDB crudo
    log.info("ingesta_iniciada", pdb_id=pdb_id)
    raw_path = StoragePath.target_raw(pdb_id)
    if not await exists(raw_path):
        pdb_content = await download_pdb_from_rcsb(pdb_id, user_id=user_id)
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
            chain=detected_chain,
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
        existing.chain = detected_chain
        existing.prepared_file_path = prepared_file_path
        existing.grid_center_x = center[0]
        existing.grid_center_y = center[1]
        existing.grid_center_z = center[2]
        existing.grid_size_x = size[0]
        existing.grid_size_y = size[1]
        existing.grid_size_z = size[2]
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
            # Se lee DESPUÉS de «RESOLUTION.»: antes se tomaba el primer número de la línea, que
            # es el «2» de «REMARK   2», y todo PDB subido quedaba con resolución 2,0 Å.
            for p in line.split("RESOLUTION.", 1)[1].split():
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
    origen_content: bytes | None = None,
    origen_filename: str | None = None,
    modo_preparacion: str | None = None,
    site_ligand: str | None = None,
) -> dict:
    """
    Ingesta un target subido manualmente por el usuario.
    `site_ligand` es el ligando del cristal que la preparación retira; lo pasa una variante, heredado de su padre.
    Si is_curated=True, asume que es un archivo .pdbqt listo.
    Si is_curated=False, asume que es un .pdb y lo cura.
    """
    from services.targets.box_validation import validar_caja
    validar_caja(grid_center, grid_size)
    import uuid
    pdb_id = f"USR_{uuid.uuid4().hex[:6].upper()}"
    repo = Repository(db)

    log.info("ingesta_custom_iniciada", pdb_id=pdb_id, is_curated=is_curated)

    # El modo lo elige la persona según lo que trae: estructura cruda (MolDesign la prepara), estructura ya
    # preparada (se respeta) o PDBQT listo para Vina. Cada uno es un camino; ninguno se quita.
    modo = (modo_preparacion or ("pdbqt" if is_curated else perfil_receptor.MODO_AUTOMATICO)).strip().lower()
    if modo not in perfil_receptor.MODOS or (modo == perfil_receptor.MODO_PDBQT) != bool(is_curated):
        raise ErrorDeSubida(
            "MODO_INCOHERENTE",
            f"El modo «{modo_preparacion}» no corresponde a esta subida. Modos: «automatico» (estructura "
            "cruda), «respetar» (estructura ya preparada por tu equipo) y «pdbqt» (PDBQT listo para Vina).",
            f"The mode «{modo_preparacion}» does not match this upload. Modes: «automatico» (raw structure), "
            "«respetar» (structure already prepared by your team) and «pdbqt» (PDBQT ready for Vina).",
        )
    respetar = modo == perfil_receptor.MODO_RESPETAR
    if respetar:
        cofactors_whitelist = []         # el equipo ya decidió qué conservar: no hay lista blanca

    # Lo que llegó: extensión sin distinguir mayúsculas, .gz con tope, contenido que
    # corresponde a la extensión. Cualquier fallo sale con qué pasó y qué hacer.
    archivo = leer_subida(filename, file_content)

    # Intentar extraer metadatos del archivo subido
    extracted_organism = None
    extracted_resolution = None
    try:
        metadata = extract_pdb_metadata(archivo.texto)
        extracted_organism = metadata.get("organism")
        extracted_resolution = metadata.get("resolution")
    except Exception as e:
        log.warning("error_extracting_metadata_from_custom_target", error=str(e))

    origen = None
    if origen_content is not None:
        if not is_curated:
            raise ErrorDeSubida(
                "ORIGEN_SOLO_CON_PDBQT",
                "La estructura de origen sólo se usa con un PDBQT listo para Vina (para auditarlo). Con "
                "«Estructura cruda» el archivo que subes ya es la estructura: quita el segundo archivo.",
                "The source structure is only used with a PDBQT ready for Vina (to audit it). With "
                "«Raw structure» the file you upload already is the structure: remove the second file.",
            )
        origen = leer_subida(origen_filename or "origen", origen_content)

    if is_curated:
        if archivo.formato != FORMATO_PDBQT:
            raise ErrorDeSubida(
                "PDBQT_EXTENSION",
                f"El modo «PDBQT listo para Vina» sólo admite archivos .pdbqt; «{archivo.nombre}» es "
                f"{archivo.formato.upper()}. Si es una estructura que quieres que MolDesign prepare, "
                "elige «Estructura cruda».",
                f"The «PDBQT ready for Vina» mode only accepts .pdbqt files; «{archivo.nombre}» is "
                f"{archivo.formato.upper()}. If it is a structure you want MolDesign to prepare, "
                "choose «Raw structure».",
            )
        from services.targets.ingesta_propia import ingestar_pdbqt

        return await ingestar_pdbqt(
            pdb_id=pdb_id, archivo=archivo, origen=origen, name=name, db=db,
            chain_id=chain_id or "A", grid_center=grid_center, grid_size=grid_size,
            cofactors_whitelist=cofactors_whitelist, creator_id=creator_id,
            creator_username=creator_username, is_community=is_community,
            is_anti_target=is_anti_target, anti_target_risk=anti_target_risk,
            preparation_parent_id=preparation_parent_id, preparation_recipe=preparation_recipe,
            organism=extracted_organism, resolution=extracted_resolution,
            preparation_provenance=_preparation_provenance,
        )
    else:
        if archivo.formato == FORMATO_PDBQT:
            raise ErrorDeSubida(
                "PDBQT_EN_MODO_ESTRUCTURA",
                f"«{archivo.nombre}» es un PDBQT: un receptor que ya está preparado para Vina. Elige "
                "«PDBQT listo para Vina» para evaluarlo tal cual, o sube la estructura de la que salió "
                "(PDB o mmCIF) para que MolDesign la prepare.",
                f"«{archivo.nombre}» is a PDBQT: a receptor already prepared for Vina. Choose "
                "«PDBQT ready for Vina» to evaluate it as is, or upload the structure it came from "
                "(PDB or mmCIF) so MolDesign prepares it.",
            )
        raw_path = StoragePath.target_raw(pdb_id)
        conversion = informe_pqr = None
        if archivo.formato == FORMATO_MMCIF:
            # El pipeline lee PDB clásico: se convierte con una correspondencia explícita de
            # cadenas, residuos de nombre largo y ensamblaje. Lo que no cabe se abstiene con motivo.
            conversion = mmcif_a_pdb(archivo.texto, archivo.nombre)
            pdb_text = conversion.pdb
            metadata = extract_pdb_metadata(pdb_text)
            extracted_organism = metadata.get("organism") or extracted_organism
            extracted_resolution = metadata.get("resolution") or extracted_resolution
        elif archivo.formato == FORMATO_PQR:
            # Un PQR (PDB2PQR) es un PDB con carga y radio: se conservan nombres y coordenadas y se declara que
            # Vina no usa sus cargas.
            pdb_text, informe_pqr = pqr_a_pdb(archivo.texto, archivo.nombre)
        else:
            pdb_text = archivo.texto
        # Varios modelos → el 1; sin columna de elemento → se infiere del nombre. Siempre declarado.
        pdb_text, normalizacion = normalizar_pdb(pdb_text)
        if modo == perfil_receptor.MODO_AUTOMATICO:
            # La receta no conoce HSD/HSE/HSP y borraba esas histidinas; «respetar» traduce por su cuenta.
            pdb_text, nombres_charmm = nombres_charmm_a_pdb(pdb_text)
            if nombres_charmm:
                normalizacion = {**normalizacion, "nombres_charmm": nombres_charmm}
        # Cadenas: se pide la del archivo que subió la persona; si la conversión la renombró (AAA → B)
        # el receptor usa la letra y la correspondencia queda en el informe.
        cadena_original = chain_id
        if conversion is not None:
            chain_id = {c["original"]: c["pdb"] for c in conversion.informe["cadenas"]}.get(chain_id, chain_id)
        if sin_proteina(pdb_text):
            raise ErrorDeSubida(
                "SIN_PROTEINA",
                f"«{archivo.nombre}» no contiene ningún residuo de aminoácido (¿sólo ácidos nucleicos "
                "u otras moléculas?). MolDesign prepara receptores de proteína: sube una estructura "
                "que incluya la proteína diana.",
                f"«{archivo.nombre}» contains no amino-acid residue (only nucleic acids or other "
                "molecules?). MolDesign prepares protein receptors: upload a structure that "
                "includes the target protein.",
            )

        log.info("ingesta_custom_subiendo_storage_raw", pdb_id=pdb_id)
        await write_text(raw_path, pdb_text)
        # Misma razón que arriba: la estructura depositada acaba de cambiar.
        invalidar_censo(pdb_id)
        log.info("ingesta_custom_subido_storage_raw_ok", pdb_id=pdb_id)

        hotspots = []
        center = grid_center
        auto_chain = chain_id

        if not center:
            # Intentar descubrir pocket
            pocket_info = discover_pocket_from_pdb(pdb_text, chain_id)
            if not pocket_info["success"]:
                raise ErrorDeSubida(
                    "SITIO_NO_DETECTADO",
                    "No se pudo detectar el sitio de unión automáticamente "
                    f"({pocket_info.get('error') or 'sin ligando de referencia en el archivo'}). "
                    "Indica el centro de la caja de búsqueda (x, y, z, en Å) y vuelve a subirlo.",
                    "The binding site could not be detected automatically "
                    f"({pocket_info.get('error') or 'no reference ligand in the file'}). "
                    "Give the center of the search box (x, y, z, in Å) and upload it again.",
                )
            center = pocket_info["grid_center"]
            hotspots = pocket_info["suggested_hotspots"]
            # Use auto-detected chain if available
            auto_chain = pocket_info.get("detected_chain", chain_id)
            if auto_chain != chain_id:
                log.info("cadena_autodetectada_custom", detectada=auto_chain, original=chain_id)

        # La cadena declarada tiene que existir: con un sitio entre varias cadenas la preparación
        # usa las del sitio y habría guardado el receptor con una cadena que no está en el archivo.
        con_proteina = cadenas_con_proteina(pdb_text)
        if auto_chain not in con_proteina:
            if conversion is not None:
                disponibles = [c["original"] for c in conversion.informe["cadenas"] if c["pdb"] in con_proteina]
                raise error_de_cadena(cadena_original, disponibles)
            raise error_de_cadena(auto_chain, con_proteina)

        # Que cadenas forman el sitio (doc 71). Vale igual para un archivo subido
        # a mano: un usuario que suba la proteasa del VIH tiene el mismo derecho
        # a que no se le acople contra media cavidad.
        sitio = anotar_sitio(pdb_text, center, grid_size) or {}
        if len(sitio.get("site_chains") or []) > 1:
            log.info("sitio_multicadena_detectado_custom", pdb_id=pdb_id,
                     cadenas=sitio["site_chains"], evidencia=sitio.get("site_evidence"))

        # El perfil va ANTES de preparar: el informe de la preparación copia de él cómo llegó el
        # archivo (formato, hash), y `prepare_target` lo vuelve a leer en cada corrida.
        entrada = archivo.identidad()
        if conversion is not None:
            entrada["conversion"] = conversion.informe
            entrada["avisos"] = sorted({*(entrada.get("avisos") or []), *conversion.informe["avisos"]})
        if informe_pqr is not None:
            entrada["pqr"] = informe_pqr
        if normalizacion:
            entrada["normalizacion"] = normalizacion
        # ¿Es una predicción? Lo dice el propio archivo; la confianza (pLDDT) sólo se lee con una convención
        # verificada en un archivo real de esa fuente (ver `prediccion.py`).
        prediccion, plddt = analizar_prediccion(
            archivo.formato, archivo.texto, pdb_text,
            {c["original"]: c["pdb"] for c in conversion.informe["cadenas"]} if conversion is not None else None,
        )
        await perfil_receptor.guardar(pdb_id, {
            "pdb_id": pdb_id, "modo": modo, "camino": "B" if respetar else "A",
            "entrada": entrada, "prediccion": prediccion,
            **({"plddt_residuos": plddt} if plddt else {}),
            **({"site_ligand": site_ligand.upper()} if site_ligand else {}),
        })
        if archivo.comprimido:
            await write_bytes(archivo.original, StoragePath.target_upload(pdb_id, archivo.nombre_almacenado))

        # Curacion
        try:
            prepared_file_path = await prepare_target(
                pdb_id=pdb_id,
                chain_id=auto_chain,
                site_chains=sitio.get("site_chains"),
                center=center,
                size=grid_size,
                force_reprepare=True,
                cofactors_whitelist=cofactors_whitelist or [],
                site_ligand=site_ligand,
            )
        except Exception as e:
            log.error("preparacion_custom_fallida", pdb_id=pdb_id, error=str(e),
                      detalle=str(getattr(e, "detail", "") or "")[:600])
            raise desde_preparacion(e, cadena=auto_chain, texto_pdb=pdb_text, modo=modo) from e

        prepared_bytes = await read_bytes(prepared_file_path)
        recipe = preparation_recipe or ({
            "schema_version": 1,
            "mode": "respect_user_preparation",
            "chain": auto_chain,
            "grid_center": [float(value) for value in center],
            "grid_size": [float(value) for value in grid_size],
            "protonation": "declared_by_user",
            "waters": "kept_as_uploaded",
            "altloc": "majority_or_default",
        } if respetar else {
            "schema_version": 1,
            "mode": "automatic_meeko",
            "chain": auto_chain,
            "grid_center": [float(value) for value in center],
            "grid_size": [float(value) for value in grid_size],
            "cofactors_whitelist": sorted(set(cofactors_whitelist or [])),
            "waters": "remove_all",
            "altloc": "majority_or_default",
        })
        provenance = _preparation_provenance(
            source_bytes=archivo.contenido,
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
