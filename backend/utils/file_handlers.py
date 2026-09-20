"""
utils/file_handlers.py

Descarga desde RCSB PDB, parsers de formato molecular y StoragePath
(nombres lógicos de objetos). El almacenamiento real en desktop es el
disco local: ver utils/local_storage.py (F-03, 2026-08-13).

MolDesign es desktop-only. Las operaciones de almacenamiento viven en
``utils/local_storage.py``; aquí quedan:

1. StoragePath: fuente única de las rutas lógicas de almacenamiento.
2. Funciones RCSB: search_rcsb_by_name, download_pdb_from_rcsb,
   fetch_target_cofactors_from_rcsb.
3. Parsers de formato molecular: parse_vina_output_sdf,
   parse_vina_output_pdbqt, extract_pdbqt_poses, validate_pdbqt_content.

Convención de nombres lógicos (persistidos bajo settings.local_data_dir):
    targets/{pdb_id}/raw.pdb                    → proteína raw del RCSB PDB
    targets/{pdb_id}/prepared.pdbqt             → proteína preparada para Vina
    ligands/{smiles_hash}/conformer.sdf         → conformer 3D del ligando
    ligands/{smiles_hash}/vina_input.pdbqt      → ligando preparado para Vina
    poses/{smiles_hash}/{target_pdb_id}/poses.sdf → poses de docking
    poses/{smiles_hash}/{target_pdb_id}/vina.log  → log de Vina

Los prefijos lógicos (`targets/`, `ligands/`, `poses/`) son parte del
contrato de datos: NO cambiarlos, romperían los archivos ya guardados.
"""

import os
import re
import tempfile
from contextlib import contextmanager
from pathlib import Path

import httpx

from core.config import get_settings
from utils.logger import get_logger

log = get_logger(__name__)
settings = get_settings()
# ── Construcción de rutas lógicas de almacenamiento ───────────────────────────

class StoragePath:
    """
    Centraliza la construcción de las rutas lógicas de almacenamiento.

    Mismo principio que CacheKey en utils/cache.py:
    una sola fuente de verdad para las rutas lógicas.
    En desktop estos nombres se resuelven a disco vía utils/local_storage.py.
    """

    @staticmethod
    def target_raw(pdb_id: str) -> str:
        """Proteína raw descargada del RCSB PDB."""
        return f"targets/{pdb_id.upper()}/raw.pdb"

    @staticmethod
    def target_prepared(pdb_id: str) -> str:
        """Proteína preparada para AutoDock Vina (.pdbqt)."""
        return f"targets/{pdb_id.upper()}/prepared.pdbqt"

    @staticmethod
    def ligand_conformer(smiles_hash: str) -> str:
        """Conformer 3D del ligando generado por RDKit (.sdf)."""
        return f"ligands/{smiles_hash}/conformer.sdf"

    @staticmethod
    def ligand_vina_input(smiles_hash: str) -> str:
        """Ligando convertido al formato .pdbqt para Vina."""
        return f"ligands/{smiles_hash}/vina_input.pdbqt"

    @staticmethod
    def ligand_vina_input_provenance(smiles_hash: str) -> str:
        """De qué conformero salió ese `.pdbqt`, para poder reutilizarlo.

        Sin este registro, un `vina_input.pdbqt` en caché es indistinguible de
        uno construido desde OTRA conformación: es exactamente lo que ocurrió
        con los hashes derivados del ensemble (ENS-05). Un archivo que no puede
        demostrar de dónde salió se vuelve a preparar.
        """
        return f"ligands/{smiles_hash}/vina_input.source.json"

    @staticmethod
    def docking_poses(smiles_hash: str, target_pdb_id: str) -> str:
        """Poses de docking retornadas por Vina (.sdf)."""
        return f"poses/{smiles_hash}/{target_pdb_id.upper()}/poses.sdf"

    @staticmethod
    def docking_log(smiles_hash: str, target_pdb_id: str) -> str:
        """Log de texto de AutoDock Vina (para debugging)."""
        return f"poses/{smiles_hash}/{target_pdb_id.upper()}/vina.log"

    @staticmethod
    def docking_poses_run(
        smiles_hash: str, target_pdb_id: str, protocol_fingerprint: str
    ) -> str:
        """Poses inmutables de una configuración concreta de docking."""
        return (
            f"runs/docking/{smiles_hash}/{target_pdb_id.upper()}/"
            f"{protocol_fingerprint}/poses.sdf"
        )

    @staticmethod
    def docking_log_run(
        smiles_hash: str, target_pdb_id: str, protocol_fingerprint: str
    ) -> str:
        """Log inmutable de una configuración concreta de docking."""
        return (
            f"runs/docking/{smiles_hash}/{target_pdb_id.upper()}/"
            f"{protocol_fingerprint}/vina.log"
        )

    @staticmethod
    def prepared_receptor_snapshot(receptor_sha256: str) -> str:
        """Copia content-addressed del receptor que una corrida sí utilizó."""
        return f"runs/receptors/{receptor_sha256.lower()}.pdbqt"


# ── Archivos temporales ──────────────────────────────────────────────────────


@contextmanager
def temp_output_file(suffix: str = ".sdf") -> Path:
    """
    Crea un archivo temporal vacío para que Vina escriba su output.

    Uso en vina_service.py:
        with temp_output_file(suffix=".sdf") as output_path:
            await _run_vina(receptor, ligand, output_path)
            # copiar output_path al storage local después
            await write_file(output_path, StoragePath.docking_poses(...))
    """
    tmp = tempfile.NamedTemporaryFile(
        suffix=suffix,
        delete=False,
        dir=settings.vina_temp_dir,
    )
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        yield tmp_path
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass


# ── Búsqueda en RCSB PDB por nombre de proteína ────────────────────────────

async def search_rcsb_by_name(
    query: str,
    max_results: int = 10,
    min_resolution: float | None = None,
) -> list[dict]:
    """
    Buscar estructuras en RCSB PDB por nombre de proteína usando RCSB Search API v2.

    Args:
        query: Nombre de la proteína (ej: "EGFR", "5-HT1A", "CDK4")
        max_results: Máximo de resultados a retornar
        min_resolution: Resolución mínima en Å (default None = sin filtro)

    Returns:
        Lista de dicts con: pdb_id, title, method, resolution, organism, ligands
    """
    import httpx

    search_url = "https://search.rcsb.org/rcsbsearch/v2/query"

    search_payload = {
        "query": {
            "type": "group",
            "logical_operator": "and",
            "nodes": [
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "rcsb_entry_info.structure_determination_methodology",
                        "operator": "exact_match",
                        "value": "experimental",
                    },
                },
                {
                    "type": "terminal",
                    "service": "text",
                    "parameters": {
                        "attribute": "struct.title",
                        "operator": "contains_phrase",
                        "value": query,
                    },
                },
            ],
        },
        "return_type": "entry",
        "request_options": {
            "paginate": {"start": 0, "rows": max_results},
            "sort": [{"sort_by": "rcsb_entry_info.resolution_combined", "direction": "asc"}],
        },
    }

    log.info("searching_rcsb_by_name", query=query, url=search_url)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(search_url, json=search_payload)
            resp.raise_for_status()
            data = resp.json()

        result_ids = [entry["identifier"] for entry in data.get("result_set", [])]
        log.info("rcsb_search_results", query=query, n_results=len(result_ids))

        # Fetch details for each result
        results = []
        for pdb_id in result_ids:
            detail = await _fetch_rcsb_entry_detail(pdb_id)
            if detail:
                results.append(detail)

        # Filter by resolution if specified
        if min_resolution is not None:
            results = [r for r in results if r.get("resolution") is None or r["resolution"] <= min_resolution]

        return results

    except Exception as e:
        log.error("rcsb_search_failed", query=query, error=str(e))
        return []


async def _fetch_rcsb_entry_detail(pdb_id: str) -> dict | None:
    """Fetch detailed metadata for a PDB entry from RCSB Data API."""
    import httpx

    detail_url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id.upper()}"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(detail_url)
            if resp.status_code != 200:
                return None
            data = resp.json()

        # Extract relevant metadata
        struct = data.get("struct", {})
        exptl = data.get("exptl", [{}])
        rcsb_entry_info = data.get("rcsb_entry_info", {})

        # Get resolution
        resolution = rcsb_entry_info.get("resolution_combined", [None])
        if isinstance(resolution, list):
            resolution = resolution[0] if resolution else None

        # Get experimental method
        method = exptl[0].get("method", "Unknown") if exptl else "Unknown"

        # Get organism
        entity_src = data.get("rcsb_entity_source_organism", [{}])
        organism = entity_src[0].get("scientific_name", "Unknown") if entity_src else "Unknown"

        return {
            "pdb_id": pdb_id.upper(),
            "title": struct.get("title", "No title"),
            "method": method,
            "resolution": resolution,
            "organism": organism,
        }

    except Exception as e:
        log.warning("rcsb_entry_detail_failed", pdb_id=pdb_id, error=str(e))
        return None


# ── Descarga desde RCSB PDB ───────────────────────────────────────────────────

async def download_pdb_from_rcsb(pdb_id: str) -> str:
    """
    Descarga la estructura de una proteina desde el RCSB PDB publico.

    v1.5: Primero busca en cache local (para modo offline/Steam).
    Si no esta en cache, intenta descargar. Si falla la red, lanza error claro.

    Retorna el contenido del archivo .pdb como string.
    """
    pdb_id = pdb_id.upper()

    # 1. Cache local (pre-bundled para modo offline / Steam)
    local_cache = Path(os.getenv("MOLDESIGN_PDB_CACHE", str(
        Path.home() / "MolDesign" / "data" / "pdb_cache"
    )))
    local_pdb = local_cache / f"{pdb_id}.pdb"
    if local_pdb.exists():
        content = local_pdb.read_text(encoding="utf-8")
        if "ATOM" in content or "HETATM" in content:
            log.info("pdb_from_local_cache", pdb_id=pdb_id)
            return content

    # 2. Descarga desde RCSB
    url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
    log.info("descargando estructura PDB desde RCSB", pdb_id=pdb_id, url=url)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
        content = response.text
    except Exception as e:
        raise RuntimeError(
            f"No se pudo obtener la estructura PDB '{pdb_id}'. "
            f"Verifica tu conexion a internet o asegurate de tener el archivo "
            f"en {local_pdb}. Error: {e}"
        ) from e

    # Validación básica: un .pdb válido siempre contiene líneas ATOM o HETATM
    if "ATOM" not in content and "HETATM" not in content:
        raise ValueError(
            f"El archivo descargado para '{pdb_id}' no parece ser un PDB válido. "
            "Verifica que el PDB ID sea correcto."
        )

    log.info(
        "estructura PDB descargada",
        pdb_id=pdb_id,
        size_bytes=len(content.encode()),
    )
    return content


async def fetch_target_cofactors_from_rcsb(pdb_id: str) -> list[str]:
    """
    Descarga la metadata oficial de RCSB PDB para descubrir cofactores orgánicos y metales
    esenciales de una proteína. Devuelve una lista de los IDs (3 letras) de todos los 
    HETATMs que deben preservarse en el pocket (e.g. ['HEM', 'NAD', 'ZN', 'MG']).
    """
    url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id.upper()}"
    log.info("buscando cofactores en RCSB PDB", pdb_id=pdb_id, url=url)

    cofactors = set()

    # Excluir explícitamente cristalográficos, azúcares y solventes comunes
    skip_res = {"HOH", "WAT", "DOD", "SO4", "PO4", "PEG", "EDO", "ACT", "GOL", "DMS", "CL", "BR", "IOD"}

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url)
            if response.status_code == 200:
                data = response.json()
                nonpolymers = data.get("nonpolymer_entities", [])
                for entity in nonpolymers:
                    comp = entity.get("nonpolymer_comp", {})
                    comp_id = comp.get("chem_comp_id", "").upper()

                    if not comp_id or comp_id in skip_res:
                        continue

                    # Añadir a la lista de cofactores permitidos
                    cofactors.add(comp_id)

            return list(cofactors)
        except Exception as e:
            log.warning("error buscando cofactores en rcsb", pdb_id=pdb_id, error=str(e))
            return []


# ── Parsers de formato molecular ──────────────────────────────────────────────

def parse_vina_output_sdf(sdf_content: str) -> list[dict]:
    """
    Parsea el archivo .sdf de output exportado por Meeko (mk_export) desde
    el PDBQT de AutoDock Vina.

    Meeko 0.5+ escribe los metadatos de cada pose dentro de una propiedad
    JSON bajo la clave ``meeko``. Ésta es la cabecera REAL, copiada de una
    salida de `mk_export` y no de la especificación —la diferencia importa y
    se explica más abajo, en el `re.match` que la reconoce::

        >  <meeko>  (1)
        {"free_energy": -8.5, "intermolecular_energy": -9.1, ...}

        $$$$

    Para compatibilidad con versiones previas o herramientas alternativas
    (OpenBabel, etc.) que escriben propiedades individuales, también se
    soporta el formato heredado::

        > <minimizedAffinity>
        -8.5

    Nota: Meeko NO exporta RMSD lower/upper bound al SDF, pues esos
    valores solo existen en las líneas ``REMARK VINA RESULT:`` del PDBQT.
    Aquí se dejan en 0.0; es `vina_service` quien los fusiona desde el PDBQT
    emparejando por posición. Un 0.0 entregado al usuario no sería un dato
    ausente: afirmaría que esa pose es idéntica a la pose 1.

    Retorna lista de dicts con rank, affinity, rmsd_lb, rmsd_ub.
    El orden en el SDF corresponde al rank (pose 1 = mejor afinidad).

    Esta función no usa RDKit para parsear el SDF porque queremos
    que funcione incluso si RDKit no está disponible (ej. en tests).
    """
    import json as _json

    poses: list[dict] = []
    current_props: dict = {}
    reading_field: str | None = None
    rank = 0
    records = 0

    for line in sdf_content.splitlines():
        stripped = line.strip()

        # Record boundaries take priority over missing or malformed field values.
        if stripped == "$$$$":
            records += 1
            if "affinity" in current_props:
                rank += 1
                poses.append({
                    "rank":     rank,
                    "affinity": current_props["affinity"],
                    "rmsd_lb":  current_props.get("rmsd_lb", 0.0),
                    "rmsd_ub":  current_props.get("rmsd_ub", 0.0),
                })
            current_props = {}
            reading_field = None
            continue


        # SDF writers vary between ``> <field>`` and ``>  <field>``, y algunos
        # añaden el índice del registro DESPUÉS del nombre.
        #
        # EL FALLO QUE ARREGLA. Este `re.match` terminaba en ``>\s*$``, es decir
        # exigía que la línea acabara justo tras el ángulo de cierre. Meeko
        # escribe ``>  <meeko>  (1) ``, así que NINGUNA de sus propiedades casaba
        # y esta función devolvía `[]` para todo SDF de Meeko. Open Babel escribe
        # ``>  <REMARK>`` sin sufijo y sí casaba: el ancla se ajustó al respaldo
        # mientras el camino principal llevaba roto desde siempre, y el docstring
        # ilustraba una cabecera escrita a mano que ningún programa emite.
        #
        # Medido el 2026-09-19 sobre ENS-PILOT-01: 172 acoplamientos, 171 al
        # respaldo de Open Babel, CERO por Meeko. La regresión está en
        # `test_lector_de_sdf_de_meeko.py`, que parsea archivos REALES de
        # `mk_export` y no cabeceras inventadas.
        #
        # Lo que se exige es el nombre entre ángulos al principio de la línea.
        # Lo que venga después es decisión del escritor, no parte del contrato.
        field_match = re.match(r"^>\s+<([^>]+)>", stripped)
        field_name = field_match.group(1) if field_match else None

        # ── Meeko JSON format: > <meeko> ──────────────────────────────────
        if field_name == "meeko":
            reading_field = "meeko_json"
            continue

        if field_name == "REMARK":
            reading_field = "remark"
            continue

        if reading_field == "meeko_json" and stripped:
            try:
                meeko_data = _json.loads(stripped)
                if isinstance(meeko_data, dict) and "free_energy" in meeko_data:
                    current_props["affinity"] = float(meeko_data["free_energy"])
            except (ValueError, _json.JSONDecodeError):
                log.warning(
                    "JSON inválido en propiedad <meeko> del SDF",
                    raw=stripped[:200],
                )
            reading_field = None
            continue

        # Open Babel preserves Vina's original remark in a string property:
        # ``REMARK VINA RESULT: <affinity> <rmsd_lb> <rmsd_ub>``.  Reading this
        # property is important because the converted SDF is the structural
        # artifact that will be persisted when it is the successful fallback.
        # The values remain the same Vina values; no score is inferred here.
        if reading_field == "remark" and stripped:
            vina_match = re.search(
                r"VINA\s+RESULT:\s+"
                r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+"
                r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+"
                r"([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)",
                stripped,
                flags=re.IGNORECASE,
            )
            if vina_match:
                affinity, rmsd_lb, rmsd_ub = vina_match.groups()
                current_props.update(
                    affinity=float(affinity),
                    rmsd_lb=float(rmsd_lb),
                    rmsd_ub=float(rmsd_ub),
                )
            reading_field = None
            continue

        # ── Legacy format: > <minimizedAffinity> ─────────────────────────
        if field_name == "minimizedAffinity":
            reading_field = "affinity"
            continue
        elif field_name == "minimizedRMSD_lowerBound":
            reading_field = "rmsd_lb"
            continue
        elif field_name == "minimizedRMSD_upperBound":
            reading_field = "rmsd_ub"
            continue

        if reading_field in ("affinity", "rmsd_lb", "rmsd_ub") and stripped:
            try:
                current_props[reading_field] = float(stripped)
            except ValueError:
                log.warning(
                    "valor no numérico en output de Vina",
                    field=reading_field,
                    value=stripped,
                )
            reading_field = None
            continue


    if poses and len(poses) != records:
        # Callers pair this list positionally with original PDBQT models.
        # Skipping unannotated records shifts scores onto another geometry.
        # Return no SDF scores so Vina can recover from its PDBQT/stdout path.
        log.warning("sdf_partial_affinity_metadata", records=records, poses=len(poses))
        return []

    if not poses:
        # Un SDF de `mk_export` sobre una salida de Vina SÍ trae la afinidad en
        # su propiedad `meeko`; llegar aquí con uno significa que la corrida no
        # la produjo —un SDF minimizado sin acoplar, por ejemplo—, no que el
        # formato carezca de metadatos. Esa creencia, escrita aquí como si fuera
        # normal, es lo que dejó pasar el ancla del `re.match` de más arriba.
        # Los SDF de Open Babel con propiedad REMARK se resuelven antes y no
        # llegan a este punto.
        log.debug("SDF de Vina no contiene metadatos de afinidad; se usará fallback PDBQT")

    return poses


def fusionar_rmsd_desde_pdbqt(
    poses_sdf: list[dict], pdbqt_content: str
) -> tuple[list[dict], dict]:
    """Completa `rmsd_lb`/`rmsd_ub` de las poses del SDF con los del PDBQT.

    Meeko exporta la afinidad en su propiedad `meeko`, pero NO el RMSD contra la
    pose 1: esos dos números viven únicamente en las líneas ``REMARK VINA
    RESULT`` que escribe Vina. Entregarlos en 0.0 no sería un dato ausente:
    afirmaría que todas las poses son idénticas a la primera, y el dossier lo
    imprime como tal.

    El emparejamiento es POSICIONAL —igual que el de los bloques PDBQT— y sólo
    se hace si ambos recuentos coinciden. Desalinearlo pondría el RMSD de una
    pose sobre la geometría de otra, que es justo lo que el invariante
    todo-o-nada de `parse_vina_output_sdf` existe para impedir; ante la duda se
    deja el 0.0 y se declara en el diagnóstico, en vez de inventar una pareja.

    La afinidad NO se sobrescribe: viene del SDF, que es lo que
    ``parsing_source="sdf"`` declara. Se contrasta contra la del PDBQT porque
    ambas salen de la misma línea de Vina, así que una divergencia sería un
    defecto de procedencia y no un redondeo.

    Devuelve una lista NUEVA y un diagnóstico; no muta la entrada.
    """
    poses_pdbqt = parse_vina_output_pdbqt(pdbqt_content)
    diagnostico: dict = {
        "poses_en_sdf": len(poses_sdf),
        "poses_en_pdbqt": len(poses_pdbqt),
        "fusionado": False,
        "afinidades_discrepantes": [],
    }

    if not poses_sdf or len(poses_pdbqt) != len(poses_sdf):
        return [dict(p) for p in poses_sdf], diagnostico

    fusionadas: list[dict] = []
    # `strict=True` y no por estilo: aquí arriba ya se comprobó que los
    # recuentos coinciden, así que un desajuste sería un fallo de lógica y debe
    # reventar en vez de truncar en silencio la lista de poses.
    for desde_sdf, desde_pdbqt in zip(poses_sdf, poses_pdbqt, strict=True):
        pose = dict(desde_sdf)
        pose["rmsd_lb"] = desde_pdbqt["rmsd_lb"]
        pose["rmsd_ub"] = desde_pdbqt["rmsd_ub"]
        if abs(float(pose["affinity"]) - float(desde_pdbqt["affinity"])) > 1e-3:
            diagnostico["afinidades_discrepantes"].append({
                "rank": pose["rank"],
                "sdf": float(pose["affinity"]),
                "pdbqt": float(desde_pdbqt["affinity"]),
            })
        fusionadas.append(pose)

    diagnostico["fusionado"] = True
    return fusionadas, diagnostico


def parse_vina_output_pdbqt(pdbqt_content: str) -> list[dict]:
    # Parsea poses desde el output `.pdbqt` de Vina.
    #
    # Vina escribe una línea por pose con el patrón:
    #     REMARK VINA RESULT: <affinity> <rmsd_lb> <rmsd_ub>
    #
    # Este parser sirve como fallback trazable cuando el SDF exportado por Meeko
    # no contiene propiedades de afinidad/RMSD.
    result_pattern = re.compile(
        r"^REMARK\s+VINA\s+RESULT:\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)\s+([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)"
    )

    poses: list[dict] = []
    rank = 0

    for line in pdbqt_content.splitlines():
        match = result_pattern.match(line.strip())
        if not match:
            continue

        rank += 1
        affinity, rmsd_lb, rmsd_ub = match.groups()
        poses.append(
            {
                "rank": rank,
                "affinity": float(affinity),
                "rmsd_lb": float(rmsd_lb),
                "rmsd_ub": float(rmsd_ub),
            }
        )

    if not poses:
        log.warning("no se encontraron líneas REMARK VINA RESULT en output PDBQT")

    return poses


def extract_pdbqt_poses(pdbqt_content: str) -> list[str]:
    # Divide un archivo PDBQT multi-modelo de Vina en bloques individuales.
    # Cada bloque corresponde a una pose (MODEL ... ENDMDL).
    models = []
    current_model = []
    in_model = False

    for line in pdbqt_content.splitlines():
        if line.startswith("MODEL"):
            in_model = True
            current_model = [line]
        elif line.startswith("ENDMDL"):
            current_model.append(line)
            models.append("\n".join(current_model))
            in_model = False
        elif in_model:
            current_model.append(line)

    return models


def validate_pdbqt_content(content: str) -> tuple[bool, str | None]:
    # Valida que un archivo .pdbqt tiene el formato correcto para Vina.
    #
    # Vina es muy sensible al formato .pdbqt - un archivo malformado
    # causa que Vina salga con código 1 sin mensaje de error útil.
    #
    # Retorna (is_valid, error_message).
    lines = content.splitlines()

    has_atom_lines = any(
        line.startswith(("ATOM", "HETATM", "ROOT", "ENDROOT", "BRANCH"))
        for line in lines
    )

    if not has_atom_lines:
        return False, "El archivo .pdbqt no contiene líneas ATOM/HETATM/ROOT"

    # Verificar que las líneas ATOM tienen la longitud correcta (≥ 54 chars)
    atom_lines = [l for l in lines if l.startswith(("ATOM", "HETATM"))]
    short_lines = [l for l in atom_lines if len(l) < 54]
    if short_lines:
        return False, (
            f"{len(short_lines)} líneas ATOM tienen formato inválido "
            f"(longitud < 54 chars). Primera línea problemática: '{short_lines[0][:30]}...'"
        )

    return True, None
