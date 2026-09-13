"""
services/alphafold/client.py

Cliente para la API REST de AlphaFold Database (EBI).

Fuentes de datos:
- AlphaFold DB: https://alphafold.ebi.ac.uk/
- API docs: https://alphafold.ebi.ac.uk/api-docs
- Referencia: Jumper et al., Nature 596:583-589 (2021)
- Cobertura: ~214M proteínas (AlphaFold DB v4)

Principio científico:
  Las estructuras de AlphaFold son modelos computacionales validados
  contra CASP14, con precisión comparable a datos experimentales para
  regiones de alta confianza (pLDDT > 90). Sin embargo, para docking,
  se recomienda usar solo regiones con pLDDT > 70 y reportar
  explícitamente que el target es una estructura predicha.
"""

from __future__ import annotations

import asyncio
import json
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from utils.logger import get_logger

log = get_logger(__name__)

ALPHAFOLD_API_BASE = "https://alphafold.ebi.ac.uk/api"
ALPHAFOLD_FILES_BASE = "https://alphafold.ebi.ac.uk/files"


@dataclass
class AlphaFoldEntry:
    """Metadata de una entrada de AlphaFold DB."""
    uniprot_id: str
    gene: str | None
    organism: str | None
    model_url: str
    pae_url: str | None
    plddt_url: str | None
    confidence_version: int
    model_created_date: str | None
    sequence_length: int | None

    # Cuántos residuos tienen pLDDT > 70 (calculado tras descargar)
    high_confidence_residues: int | None = None
    total_residues: int | None = None
    mean_plddt: float | None = None


@dataclass
class AlphaFoldStructure:
    """Estructura descargada de AlphaFold, lista para preparación."""
    entry: AlphaFoldEntry
    pdb_path: str  # Ruta al archivo PDB/CIF descargado
    plddt_scores: list[float] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _api_get(endpoint: str) -> Any:
    """GET síncrono a la API de AlphaFold DB."""
    url = f"{ALPHAFOLD_API_BASE}{endpoint}"
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as e:
        if e.code == 404:
            return None
        raise
    except URLError as e:
        log.error("error conectando a AlphaFold DB API", error=str(e))
        raise


def _download_file(url: str, dest: str) -> None:
    """Descarga un archivo de AlphaFold DB."""
    req = Request(url)
    with urlopen(req, timeout=120) as response:
        with open(dest, "wb") as f:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                f.write(chunk)


def _parse_plddt_from_pdb(pdb_path: str) -> list[float]:
    """
    Extrae pLDDT scores del B-factor column del PDB de AlphaFold.
    AlphaFold almacena pLDDT como B-factor en las líneas ATOM.
    Solo toma Cα para evitar duplicados por residuo.
    """
    scores = []
    with open(pdb_path) as f:
        for line in f:
            if line.startswith("ATOM") and line[12:16].strip() == "CA":
                try:
                    bfactor = float(line[60:66].strip())
                    scores.append(bfactor)
                except (ValueError, IndexError):
                    continue
    return scores


async def lookup_uniprot(uniprot_id: str) -> AlphaFoldEntry | None:
    """
    Busca una proteína en AlphaFold DB por UniProt accession.

    Args:
        uniprot_id: UniProt accession (ej: P08908 para 5-HT1A humano)

    Returns:
        AlphaFoldEntry con metadata del modelo, o None si no existe.
    """
    loop = asyncio.get_event_loop()
    data = await loop.run_in_executor(
        None, _api_get, f"/prediction/{uniprot_id}"
    )

    if data is None or (isinstance(data, list) and len(data) == 0):
        log.info("proteína no encontrada en AlphaFold DB", uniprot_id=uniprot_id)
        return None

    # La API devuelve una lista; tomamos el primer resultado
    entry_data = data[0] if isinstance(data, list) else data

    return AlphaFoldEntry(
        uniprot_id=entry_data.get("uniprotAccession", uniprot_id),
        gene=entry_data.get("gene"),
        organism=entry_data.get("organismScientificName"),
        model_url=entry_data.get("pdbUrl", ""),
        pae_url=entry_data.get("paeImageUrl"),
        plddt_url=entry_data.get("cifUrl"),
        confidence_version=entry_data.get("confidenceVersion", 0),
        model_created_date=entry_data.get("modelCreatedDate"),
        sequence_length=entry_data.get("uniprotEnd"),
    )


async def download_structure(
    entry: AlphaFoldEntry,
    output_dir: str | None = None,
) -> AlphaFoldStructure:
    """
    Descarga la estructura PDB de AlphaFold DB y analiza la confianza.

    Args:
        entry: Metadata de AlphaFold DB obtenida con lookup_uniprot
        output_dir: Directorio de destino (usa temp si no se especifica)

    Returns:
        AlphaFoldStructure con la ruta al archivo y análisis de confianza.

    Limitaciones transparentes:
    - La estructura es un MODELO computacional, no datos experimentales
    - Regiones con pLDDT < 50 son esencialmente no modeladas
    - Regiones con pLDDT 50-70 deben tratarse con precaución
    - Solo regiones con pLDDT > 70 son razonablemente confiables para docking
    """
    if not entry.model_url:
        raise ValueError(f"No hay URL de modelo para {entry.uniprot_id}")

    if output_dir is None:
        output_dir = tempfile.mkdtemp(prefix="alphafold_")

    pdb_filename = f"AF-{entry.uniprot_id}-F1-model_v4.pdb"
    pdb_path = str(Path(output_dir) / pdb_filename)

    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _download_file, entry.model_url, pdb_path)

    # Analizar confianza
    plddt_scores = await loop.run_in_executor(None, _parse_plddt_from_pdb, pdb_path)

    warnings = []
    high_conf = sum(1 for s in plddt_scores if s > 70)
    total = len(plddt_scores)
    mean_plddt = sum(plddt_scores) / total if total > 0 else 0.0

    entry.high_confidence_residues = high_conf
    entry.total_residues = total
    entry.mean_plddt = round(mean_plddt, 2)

    # Generar warnings científicos
    if mean_plddt < 50:
        warnings.append(
            f"CRÍTICO: pLDDT medio = {mean_plddt:.1f}. "
            "La estructura predicha tiene confianza muy baja. "
            "Los resultados de docking serán ALTAMENTE POCO CONFIABLES."
        )
    elif mean_plddt < 70:
        warnings.append(
            f"ADVERTENCIA: pLDDT medio = {mean_plddt:.1f}. "
            "Regiones significativas de la estructura tienen baja confianza. "
            "Los resultados de docking deben interpretarse con precaución."
        )

    if total > 0 and high_conf / total < 0.5:
        warnings.append(
            f"Solo {high_conf}/{total} residuos ({100*high_conf/total:.0f}%) "
            "tienen pLDDT > 70. Considerar usar solo la región de alta confianza."
        )

    warnings.append(
        "Este target usa una estructura PREDICHA por AlphaFold2 "
        f"(UniProt: {entry.uniprot_id}), no datos experimentales. "
        "Los resultados tienen mayor incertidumbre que con estructuras cryo-EM/cristalográficas."
    )

    log.info(
        "estructura AlphaFold descargada",
        uniprot_id=entry.uniprot_id,
        total_residues=total,
        high_confidence_residues=high_conf,
        mean_plddt=mean_plddt,
        warnings_count=len(warnings),
    )

    return AlphaFoldStructure(
        entry=entry,
        pdb_path=pdb_path,
        plddt_scores=plddt_scores,
        warnings=warnings,
    )


async def search_by_gene(gene_name: str, organism: str = "Homo sapiens") -> list[AlphaFoldEntry]:
    """
    Busca proteínas en AlphaFold DB por nombre de gen.

    Nota: La API de AlphaFold DB no tiene búsqueda directa por gen.
    Este método usa UniProt API como intermediario.

    Args:
        gene_name: Nombre del gen (ej: HTR1A, DRD2)
        organism: Nombre científico del organismo

    Returns:
        Lista de entradas de AlphaFold DB encontradas.
    """
    # Buscar en UniProt primero
    uniprot_url = (
        f"https://rest.uniprot.org/uniprotkb/search?"
        f"query=gene:{gene_name}+AND+organism_name:{organism.replace(' ', '+')}"
        f"&format=json&size=5&fields=accession,gene_names,organism_name"
    )

    loop = asyncio.get_event_loop()

    def _search_uniprot():
        req = Request(uniprot_url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError) as e:
            log.warning("error buscando en UniProt", error=str(e))
            return None

    data = await loop.run_in_executor(None, _search_uniprot)
    if not data or "results" not in data:
        return []

    entries = []
    for result in data["results"][:5]:
        uniprot_id = result.get("primaryAccession")
        if uniprot_id:
            entry = await lookup_uniprot(uniprot_id)
            if entry:
                entries.append(entry)

    return entries
