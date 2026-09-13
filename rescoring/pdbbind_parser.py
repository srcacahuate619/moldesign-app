"""
rescoring/pdbbind_parser.py

Parser para PDBbind refined set usando ODDT.

Responsabilidades:
  1. Cargar PDBbind refined set via ODDT
  2. Extraer metadata por complejo (PDB ID, resolución, binding data, tipo)
  3. Exponer iterador limpio para downstream (auditoría, features, training)

ODDT provee la clase oddt.datasets.pdbbind que lee PDBbind data
desde un directorio local. Soporta versiones 2007-2020.

IMPORTANTE: ODDT NO descarga datos automáticamente.
Los datos de PDBbind deben descargarse manualmente o reconstruirse
desde fuentes públicas (RCSB PDB + BindingDB).
Ver scripts/setup_pdbbind.py para más detalles.

Estructura de directorio esperada por ODDT:
  <home>/
    INDEX_refined_data.<version>   (e.g., INDEX_refined_data.2020)
    <pdb_id>/
      <pdb_id>_protein.pdb
      <pdb_id>_pocket.pdb          (opcional)
      <pdb_id>_ligand.sdf

Nota: Este módulo corre dentro del contenedor Python 3.12 donde ODDT está
disponible. No usar en el backend principal (Python 3.14).
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from logger import get_logger

log = get_logger(__name__)


def _safe_get(obj: Any, key: str, default: Any = None) -> Any:
    """
    Acceder a un campo de un objeto que puede ser dict o tener atributos.

    ODDT retorna entries que en algunas versiones son dicts y en otras objetos
    con atributos. Esta función intenta ambas formas defensivamente.
    """
    # Intentar dict-like
    try:
        return obj[key]
    except (KeyError, TypeError, IndexError):
        pass
    # Intentar attribute-like
    try:
        return getattr(obj, key, default)
    except Exception:
        return default


@dataclass
class PDBBindComplex:
    """Un complejo proteína-ligando de PDBbind."""

    pdb_id: str
    resolution: float  # Å
    release_year: int
    binding_data_raw: str  # e.g., "Kd=1.5nM", "Ki=340nM"
    binding_type: str  # "Kd", "Ki", "IC50", "EC50", etc.
    binding_value_nm: float  # valor numérico en nM
    pki: float  # -log10(binding_value_M) = pKd o pKi
    ligand_smiles: str
    # Precisión del dato de binding:
    #   "exact"       → operador =  (dato experimental directo)
    #   "approximate" → operador ~  (estimación, no publicado exacto)
    #   "upper_bound" → operador <  (solo se sabe que es menor que...)
    #   "lower_bound" → operador >  (solo se sabe que es mayor que...)
    #   "unknown"     → no determinado
    # Solo "exact" debería usarse para training de ML.
    binding_precision: str = "unknown"
    # Set de origen: "refined", "other", "core"
    # refined = alta curación, other = general/menos curado
    source_set: str = "unknown"
    # Paths a archivos
    protein_pdb_path: str | None = None
    ligand_sdf_path: str | None = None
    ligand_mol2_path: str | None = None
    # Metadata computed later
    n_heavy_atoms: int = 0
    molecular_weight: float = 0.0
    # Estado de auditoría
    audit_passed: bool = False
    audit_failures: list[str] = field(default_factory=list)


# Regex para parsear binding data de PDBbind INDEX
# Formatos: "Kd=1.5nM", "Ki=340uM", "IC50=0.3mM", "Kd~5.6nM"
# Captura: (tipo) (operador) (valor) (unidad)
# El operador indica la calidad del dato:
#   = → medición experimental directa (USAR para training)
#   ~ → valor aproximado (NO usar para training)
#   > → límite inferior, valor real es mayor (NO usar)
#   < → límite superior, valor real es menor (NO usar)
BINDING_RE = re.compile(
    r"(Kd|Ki|IC50|EC50)\s*([=~<>])\s*([\d.]+)\s*(fM|pM|nM|uM|mM|M)",
    re.IGNORECASE,
)

# Mapa de operador → precisión semántica
OPERATOR_TO_PRECISION: dict[str, str] = {
    "=": "exact",
    "~": "approximate",
    "<": "upper_bound",
    ">": "lower_bound",
}

# Factores de conversión a nanomolar
UNIT_TO_NM: dict[str, float] = {
    "fm": 1e-6,
    "pm": 1e-3,
    "nm": 1.0,
    "um": 1e3,
    "mm": 1e6,
    "m": 1e9,
}


def parse_binding_string(raw: str) -> tuple[str, float, float, str]:
    """
    Parsear un string de binding affinity de PDBbind.

    Args:
        raw: e.g., "Kd=1.5nM", "Ki~340uM", "Ki>100nM"

    Returns:
        (binding_type, value_nm, pki, precision)
        donde precision es "exact", "approximate", "upper_bound", o "lower_bound"

    Raises:
        ValueError si no se puede parsear
    """
    match = BINDING_RE.search(raw)
    if not match:
        raise ValueError(f"No se pudo parsear binding data: '{raw}'")

    binding_type = match.group(1)
    operator = match.group(2)
    value = float(match.group(3))
    unit = match.group(4).lower()

    value_nm = value * UNIT_TO_NM[unit]

    # pKi = -log10(Kd_en_M) = -log10(Kd_en_nM * 1e-9) = 9 - log10(Kd_en_nM)
    if value_nm <= 0:
        raise ValueError(f"Binding value no positivo: {value_nm}")

    pki = 9.0 - np.log10(value_nm)
    precision = OPERATOR_TO_PRECISION.get(operator, "unknown")

    return binding_type, value_nm, round(pki, 4), precision


class PDBBindParser:
    """
    Parser para PDBbind refined set.

    Soporta dos modos:
      1. ODDT mode: carga directa con oddt.datasets.pdbbind (preferido)
      2. Index mode: parsea el archivo INDEX de PDBbind manualmente (fallback)
    """

    def __init__(self, data_dir: str | Path | None = None):
        """
        Args:
            data_dir: directorio con datos de PDBbind.
                      Si None, intenta ODDT primero, luego busca en data/pdbbind/
        """
        self._data_dir = Path(data_dir) if data_dir else None
        self._complexes: list[PDBBindComplex] = []
        self._loaded = False

    @property
    def n_complexes(self) -> int:
        return len(self._complexes)

    @property
    def complexes(self) -> list[PDBBindComplex]:
        if not self._loaded:
            raise RuntimeError("Datos no cargados. Ejecutar load() primero.")
        return self._complexes

    def load(self, include_other: bool = False) -> int:
        """
        Cargar PDBbind. Intenta ODDT primero, luego index file manual.

        Args:
            include_other: Si True, carga tambien el "other/general" set
                           ademas del refined set. El other set es menos
                           curado pero aporta ~14,000 complejos adicionales
                           criticos para diversidad de familias proteicas.

        ODDT requiere:
          - data_dir con las carpetas {pdb_id}/ de complejos
          - INDEX_refined_data.{version} en data_dir

        Returns:
            número de complejos cargados
        """
        total = 0

        # ─── Cargar refined set ───
        if self._data_dir and self._data_dir.exists():
            try:
                n = self._load_oddt()
                if n > 0:
                    total += n
                    log.info("pdbbind_refined_loaded_oddt", n_complexes=n)
            except Exception as e:
                log.warning("pdbbind_oddt_failed", error=str(e))

                # Fallback: intentar desde index file sin ODDT
                try:
                    n = self._load_from_index(source_set="refined")
                    if n > 0:
                        total += n
                        log.info("pdbbind_refined_loaded_index", n_complexes=n)
                except Exception as e2:
                    log.warning("pdbbind_refined_index_failed", error=str(e2))

            # ─── Cargar other/general set ───
            if include_other:
                try:
                    n_before = len(self._complexes)
                    n = self._load_from_index(source_set="other")
                    n_other = len(self._complexes) - n_before
                    if n_other > 0:
                        total += n_other
                        log.info("pdbbind_other_loaded", n_complexes=n_other)
                    else:
                        log.warning(
                            "pdbbind_other_empty",
                            msg="No se encontro INDEX del other set. "
                            "Verifique que INDEX_general_PL_data.2020 existe.",
                        )
                except Exception as e:
                    log.warning("pdbbind_other_failed", error=str(e))

        if total > 0:
            self._loaded = True
            log.info("pdbbind_total_loaded", n_complexes=total)
            return total

        log.error(
            "pdbbind_not_available",
            msg=(
                "No se pudo cargar PDBbind. "
                "Ejecute scripts/setup_pdbbind.py para preparar los datos."
            ),
        )
        return 0

    @staticmethod
    def _detect_version(data_dir: Path) -> int | None:
        """Detectar versión de PDBbind a partir de los INDEX files presentes."""
        for version in [2020, 2019, 2018, 2016, 2015, 2014, 2013, 2007]:
            index_file = data_dir / f"INDEX_refined_data.{version}"
            if index_file.exists():
                return version
            # Algunos formatos tienen subcarpeta index/
            index_file2 = data_dir / "index" / f"INDEX_refined_data.{version}"
            if index_file2.exists():
                return version
        return None

    def _load_oddt(self) -> int:
        """
        Cargar PDBbind via ODDT.

        ODDT 0.7 API:
          pdbbind(home=str, version=int, default_set='refined')
          Retorna un iterable de _pdbbind_id con .protein, .ligand, .pocket
          y acceso al INDEX para pdbid, resolution, release_year, activity.
        """
        from oddt.datasets import pdbbind as PDBBindDataset

        version = self._detect_version(self._data_dir)
        if version is None:
            raise FileNotFoundError(
                f"No se encontró INDEX file de PDBbind en {self._data_dir}. "
                "Descargue PDBbind desde pdbbind.org.cn o reconstruya desde RCSB."
            )

        log.info(
            "pdbbind_loading_oddt",
            home=str(self._data_dir),
            version=version,
        )

        ds = PDBBindDataset(
            home=str(self._data_dir),
            version=version,
            default_set="refined",
        )

        # Iterar entries del INDEX
        for i, pdb_id in enumerate(ds.ids):
            try:
                activity_raw = ds.activities[i] if i < len(ds.activities) else ""

                # Parsear binding data
                try:
                    btype, value_nm, pki, precision = parse_binding_string(str(activity_raw))
                except ValueError:
                    btype, value_nm, pki, precision = "unknown", 0.0, 0.0, "unknown"

                # Construir paths esperados
                complex_dir = self._data_dir / pdb_id
                protein_path = complex_dir / f"{pdb_id}_protein.pdb"
                ligand_sdf = complex_dir / f"{pdb_id}_ligand.sdf"
                ligand_mol2 = complex_dir / f"{pdb_id}_ligand.mol2"

                cpx = PDBBindComplex(
                    pdb_id=pdb_id,
                    resolution=0.0,  # Se puede enriquecer después del INDEX
                    release_year=0,
                    binding_data_raw=str(activity_raw),
                    binding_type=btype,
                    binding_value_nm=value_nm,
                    pki=pki,
                    ligand_smiles="",  # Se extrae en auditoría desde SDF
                    binding_precision=precision,
                    source_set="refined",  # ODDT carga refined por defecto
                    protein_pdb_path=(
                        str(protein_path) if protein_path.exists() else None
                    ),
                    ligand_sdf_path=(
                        str(ligand_sdf) if ligand_sdf.exists() else None
                    ),
                    ligand_mol2_path=(
                        str(ligand_mol2) if ligand_mol2.exists() else None
                    ),
                )
                self._complexes.append(cpx)
            except Exception as e:
                log.warning(
                    "pdbbind_entry_skip", pdb_id=str(pdb_id), error=str(e)
                )

        return len(self._complexes)

    def _load_from_index(self, source_set: str = "refined") -> int:
        """
        Cargar PDBbind desde INDEX file manual.

        El INDEX file de PDBbind tiene formato:
          PDB_ID  resolution  release_year  binding_data  ligand_name

        Args:
            source_set: "refined" o "other" — se anota en cada complejo
        """
        index_candidates = [
            # Refined set
            self._data_dir / "INDEX_refined_data.2020",
            self._data_dir / "INDEX_refined_data.2019",
            self._data_dir / "INDEX_refined_data.txt",
            self._data_dir / "index" / "INDEX_refined_data.2020",
        ]

        if source_set == "other":
            # El INDEX del "other" set usa nombre diferente
            index_candidates = [
                self._data_dir / "INDEX_general_PL_data.2020",
                self._data_dir / "INDEX_general_PL.2020",
                self._data_dir / "INDEX_general_PL_data.txt",
                self._data_dir / "index" / "INDEX_general_PL_data.2020",
            ]

        index_file = None
        for candidate in index_candidates:
            if candidate.exists():
                index_file = candidate
                break

        if not index_file:
            raise FileNotFoundError(
                f"No se encontró INDEX file en {self._data_dir}. "
                f"Buscados: {[str(c) for c in index_candidates]}"
            )

        log.info("pdbbind_loading_index", path=str(index_file))

        with open(index_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                parts = line.split()
                if len(parts) < 4:
                    continue

                pdb_id = parts[0].lower()
                try:
                    resolution = float(parts[1])
                except ValueError:
                    resolution = 0.0
                try:
                    release_year = int(parts[2])
                except ValueError:
                    release_year = 0

                # Binding data: todo a partir del campo 3 hasta el final
                binding_raw = " ".join(parts[3:])

                try:
                    btype, value_nm, pki, precision = parse_binding_string(binding_raw)
                except ValueError:
                    btype, value_nm, pki, precision = "unknown", 0.0, 0.0, "unknown"

                # Buscar archivos de estructura
                complex_dir = self._data_dir / pdb_id
                protein_path = complex_dir / f"{pdb_id}_protein.pdb"
                ligand_sdf = complex_dir / f"{pdb_id}_ligand.sdf"
                ligand_mol2 = complex_dir / f"{pdb_id}_ligand.mol2"

                cpx = PDBBindComplex(
                    pdb_id=pdb_id,
                    resolution=resolution,
                    release_year=release_year,
                    binding_data_raw=binding_raw,
                    binding_type=btype,
                    binding_value_nm=value_nm,
                    pki=pki,
                    ligand_smiles="",  # Se extrae en auditoría desde SDF
                    binding_precision=precision,
                    source_set=source_set,
                    protein_pdb_path=str(protein_path) if protein_path.exists() else None,
                    ligand_sdf_path=str(ligand_sdf) if ligand_sdf.exists() else None,
                    ligand_mol2_path=str(ligand_mol2) if ligand_mol2.exists() else None,
                )
                self._complexes.append(cpx)

        return len(self._complexes)

    def iter_with_structures(self) -> Iterator[PDBBindComplex]:
        """Iterar solo complejos que tienen archivos de estructura."""
        for cpx in self._complexes:
            if cpx.protein_pdb_path and cpx.ligand_sdf_path:
                yield cpx

    def get_by_pdb_id(self, pdb_id: str) -> PDBBindComplex | None:
        """Buscar complejo por PDB ID."""
        pdb_id = pdb_id.lower()
        for cpx in self._complexes:
            if cpx.pdb_id == pdb_id:
                return cpx
        return None

    def summary(self) -> dict[str, Any]:
        """Estadísticas del dataset cargado."""
        if not self._complexes:
            return {"n_complexes": 0, "loaded": False}

        resolutions = [c.resolution for c in self._complexes if c.resolution > 0]
        pkis = [c.pki for c in self._complexes if c.pki > 0]
        btypes: dict[str, int] = {}
        precisions: dict[str, int] = {}
        sources: dict[str, int] = {}
        for c in self._complexes:
            btypes[c.binding_type] = btypes.get(c.binding_type, 0) + 1
            precisions[c.binding_precision] = precisions.get(c.binding_precision, 0) + 1
            sources[c.source_set] = sources.get(c.source_set, 0) + 1

        return {
            "n_complexes": len(self._complexes),
            "loaded": self._loaded,
            "resolution_mean": round(float(np.mean(resolutions)), 2) if resolutions else None,
            "resolution_median": round(float(np.median(resolutions)), 2) if resolutions else None,
            "pki_mean": round(float(np.mean(pkis)), 2) if pkis else None,
            "pki_range": [round(float(min(pkis)), 2), round(float(max(pkis)), 2)] if pkis else None,
            "binding_types": btypes,
            "binding_precisions": precisions,
            "source_sets": sources,
            "with_structures": sum(
                1 for c in self._complexes
                if c.protein_pdb_path and c.ligand_sdf_path
            ),
        }
