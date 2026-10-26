"""Ingesta de los receptores propios que no pasan por la receta del catálogo.

``ingestion_manager.ingest_custom_target`` decide el camino según lo que trae la
persona y delega aquí lo que no es «estructura cruda»:

* camino C — un PDBQT listo para Vina, con o sin su estructura de origen;
* camino B — una estructura ya preparada por el equipo, que se respeta.

Aquí se guardan los archivos de la subida, el perfil del receptor y la fila de la
base de datos. La preparación en sí vive en ``services/docking/preparer_propio.py``
y ``preparer_respetando.py``.
"""

from __future__ import annotations

import uuid
from typing import Any

from core.models import TargetORM
from services.docking.preparer_propio import pdbqt_como_pdb, preparar_pdbqt
from services.targets import perfil_receptor
from services.targets.conversion_mmcif import a_pdb_clasico
from services.targets.entrada_receptor import FORMATO_PDBQT
from services.targets.errores_subida import ErrorDeSubida
from services.targets.normalizar_pdb import normalizar_pdb
from services.targets.pdbqt_propio import analizar_pdbqt, exigir_correspondencia, sha256_de
from services.targets.prediccion import analizar as analizar_prediccion
from services.targets.prediccion import sin_estructura_de_origen as prediccion_sin_origen
from services.targets.sitio_de_union import anotar_sitio
from utils.file_handlers import StoragePath
from utils.local_storage import write_bytes, write_text
from utils.logger import get_logger

log = get_logger(__name__)


async def ingestar_pdbqt(
    *,
    pdb_id: str,
    archivo,
    origen=None,
    name: str,
    db: Any,
    chain_id: str,
    grid_center: tuple[float, float, float] | None,
    grid_size: tuple[float, float, float],
    cofactors_whitelist: list[str] | None,
    creator_id: uuid.UUID | None,
    creator_username: str | None,
    is_community: bool,
    is_anti_target: bool,
    anti_target_risk: str | None,
    preparation_parent_id: uuid.UUID | None,
    preparation_recipe: dict | None,
    organism: str | None,
    resolution: float | None,
    preparation_provenance,
) -> dict:
    """Camino C: el PDBQT se evalúa tal cual; con su estructura de origen, además, se audita.

    ``archivo`` es el PDBQT y ``origen`` (opcional) la estructura de la que salió, ambos ya leídos
    por ``entrada_receptor.leer_subida``. Con origen se comprueba, antes de guardar nada, que los dos
    describen el mismo receptor: si no, se rechaza con la medida.
    """
    if not grid_center:
        raise ErrorDeSubida(
            "PDBQT_SIN_CAJA",
            "Un PDBQT no dice dónde está el sitio de unión: indica el centro de la caja de búsqueda "
            "(x, y, z, en Å) y vuelve a subirlo.",
            "A PDBQT does not say where the binding site is: give the center of the search box "
            "(x, y, z, in Å) and upload it again.",
        )
    # ``archivo`` ya viene descomprimido y comprobado (extensión, tope, contenido).
    contenido = archivo.contenido
    texto = archivo.texto
    resumen = analizar_pdbqt(texto)
    sha = sha256_de(contenido)
    centro = tuple(float(v) for v in grid_center)
    tamano = tuple(float(v) for v in grid_size)

    texto_origen = correspondencia = None
    normalizacion: dict = {}
    sitio: dict = {}
    # Sin la estructura de origen no hay factor B ni método: no se puede saber si el receptor es una predicción.
    prediccion, plddt = prediccion_sin_origen(), None
    if origen is not None:
        if origen.formato == FORMATO_PDBQT:
            raise ErrorDeSubida(
                "ORIGEN_ES_PDBQT",
                f"«{origen.nombre}» es otro PDBQT: la estructura de origen tiene que ser de la que salió "
                "el receptor, en PDB o mmCIF (con la protonación y las especies originales).",
                f"«{origen.nombre}» is another PDBQT: the source structure must be the one the receptor "
                "came from, in PDB or mmCIF (with the original protonation and species).",
            )
        texto_origen, declarado = a_pdb_clasico(origen)
        texto_origen, normalizacion = normalizar_pdb(texto_origen)
        # Antes de guardar nada: un origen que no es el de este PDBQT daría una auditoría falsa.
        correspondencia = exigir_correspondencia(texto_origen, texto)
        sitio = anotar_sitio(texto_origen, centro, tamano) or {}
        from services.targets.ingestion_manager import extract_pdb_metadata

        metadatos = extract_pdb_metadata(texto_origen)
        organism = metadatos.get("organism") or organism
        resolution = metadatos.get("resolution") or resolution
        prediccion, plddt = analizar_prediccion(
            origen.formato, origen.texto, texto_origen,
            {c["original"]: c["pdb"] for c in (declarado.get("conversion") or {}).get("cadenas", [])} or None,
        )

    ruta_receptor = StoragePath.target_upload(pdb_id, "receptor.pdbqt")
    await write_bytes(contenido, ruta_receptor)
    if archivo.comprimido:
        # El archivo tal como llegó, para que otra persona pueda comprobar su hash.
        await write_bytes(archivo.original, StoragePath.target_upload(pdb_id, archivo.nombre_almacenado))
    ruta_origen = None
    if origen is not None:
        ruta_origen = StoragePath.target_raw(pdb_id)
        await write_text(ruta_origen, texto_origen)
        await write_bytes(origen.original, StoragePath.target_upload(pdb_id, f"origen{origen.extension}"
                                                                      + (".gz" if origen.comprimido else "")))
    perfil = {
        "pdb_id": pdb_id,
        "modo": perfil_receptor.MODO_PDBQT,
        "camino": "C",
        "receptor_sha256": sha,
        "chain": chain_id,
        "entrada": archivo.identidad(),
        "origen": (
            {**origen.identidad(), **declarado, **({"normalizacion": normalizacion} if normalizacion else {})}
            if origen is not None else None
        ),
        "correspondencia": correspondencia,
        "prediccion": prediccion,
        **({"plddt_residuos": plddt} if plddt else {}),
        "almacen": {"receptor": ruta_receptor, "origen": ruta_origen},
    }
    await perfil_receptor.guardar(pdb_id, perfil)
    prepared_path = await preparar_pdbqt(pdb_id, {**perfil, "schema": perfil_receptor.SCHEMA},
                                         center=centro, size=tamano)
    # La copia en PDB que consumen el rescoring y la validación física: los mismos átomos.
    await write_text(f"targets/{pdb_id}.pdb", pdbqt_como_pdb(texto))

    receta = preparation_recipe or {
        "schema_version": 1,
        "mode": "external_pdbqt",
        "chain": chain_id,
        "grid_center": list(centro),
        "grid_size": list(tamano),
        "cofactors_whitelist": sorted(set(cofactors_whitelist or [])),
        **({"source_sha256": origen.sha256_contenido} if origen is not None else {}),
    }
    procedencia = preparation_provenance(source_bytes=contenido, prepared_bytes=contenido, recipe=receta)
    target = TargetORM(
        pdb_id=pdb_id,
        name=name,
        chain=chain_id,
        grid_center_x=centro[0], grid_center_y=centro[1], grid_center_z=centro[2],
        grid_size_x=tamano[0], grid_size_y=tamano[1], grid_size_z=tamano[2],
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
        **procedencia,
        **sitio,
        cofactors_whitelist=cofactors_whitelist or [],
        organism=organism,
        resolution=resolution,
        spearman_rho=None,
    )
    db.add(target)
    await db.commit()
    log.info("ingesta_pdbqt_propio", pdb_id=pdb_id, atomos=resumen.atomos, cadenas=resumen.cadenas,
             con_origen=origen is not None)
    resultado = {
        "success": True,
        "message": f"Target personalizado {pdb_id} subido exitosamente.",
        "target": target,
    }
    if origen is None:
        resultado["aviso_sin_origen"] = (
            "Sin la estructura de origen MolDesign no puede auditar qué se retiró al preparar este PDBQT: "
            "súbela para que Preparación lo audite."
        )
    return resultado
