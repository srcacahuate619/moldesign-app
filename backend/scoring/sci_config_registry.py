"""
scoring/sci_config_registry.py

Scientific Configuration Registry — Registro versionado de parámetros científicos.

Propósito:
  Centralizar todos los parámetros científicos del pipeline de docking/scoring
  con trazabilidad completa: quién los definió, por qué, cuándo, y qué evidencia
  los respalda. Esto permite:
    1. Auditar la procedencia de cada decisión paramétrica.
    2. Detectar automáticamente cuándo un parámetro está "stale" (obsoleto).
    3. Comparar versiones históricas de la configuración.
    4. Re-anclar parámetros cuando nueva evidencia lo justifique.

Principios:
  - Ningún parámetro científico debe existir sin referencia.
  - Los cambios se documentan, no se sobreescriben silenciosamente.
  - La detección de obsolescencia es conservadora: alerta ≠ auto-cambio.
  - El registro es serializable a JSON para persistencia y auditoría.

Limitaciones:
  - Las entradas de stacking selladas son la configuración M4 activa; otros
    consumidores deben declarar explícitamente si sólo auditan o si aplican valores.
  - Los cambios sugeridos requieren validación humana o del CalibrationHealthMonitor.
  - No sustituye a peer review ni a validación experimental.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ParameterCategory(str, Enum):
    """Categorías funcionales de parámetros científicos."""
    TARGET = "target"                # PDB id, chain, organism
    GRID_BOX = "grid_box"            # Center, size
    DOCKING_ENGINE = "docking_engine" # Exhaustiveness, seed, cpu
    NORMALIZATION = "normalization"   # Affinity range, scoring curves
    SCORING_WEIGHTS = "scoring_weights"  # Component weights
    ADME_RULES = "adme_rules"        # Lipinski, Veber thresholds
    VALIDATION = "validation"        # MW limits, atom counts


class StalenessReason(str, Enum):
    """Razones por las que un parámetro podría estar obsoleto."""
    AGE = "age"                      # Tiempo desde última calibración
    BETTER_STRUCTURE = "better_structure"  # Existe PDB con mejor resolución
    NORMALIZATION_DRIFT = "normalization_drift"  # Benchmark muestra rango diferente
    PANEL_EXPANDED = "panel_expanded"  # Panel de calibración creció significativamente
    SOFTWARE_UPDATE = "software_update"  # Vina/RDKit/Meeko actualizados
    MANUAL_REVIEW = "manual_review"     # Revisión humana pendiente


@dataclass
class ParameterReference:
    """Referencia bibliográfica o metodológica para un parámetro."""
    source: str             # Ej: "Trott & Olson (2010) J Comput Chem 31:455-461"
    doi: str | None = None  # DOI si es publicación
    method: str | None = None  # Ej: "Centroide geométrico de SRO en 7E2Y"
    notes: str | None = None


@dataclass
class ParameterVersion:
    """Una versión específica de un parámetro científico."""
    value: Any                              # El valor del parámetro
    version: int                            # Número de versión (1-indexed)
    adopted_at: str                         # ISO timestamp
    reason: str                             # Por qué se adoptó este valor
    reference: ParameterReference           # Evidencia que lo respalda
    calibration_id: str | None = None       # ID del reporte de calibración asociado
    superseded_at: str | None = None        # Cuándo fue reemplazado (None = activo)

    def is_active(self) -> bool:
        return self.superseded_at is None


@dataclass
class SciParameter:
    """
    Un parámetro científico con historial completo de versiones.

    Cada parámetro tiene:
      - name: identificador único (ej. "affinity_normalization_best")
      - category: clasificación funcional
      - unit: unidad física (ej. "kcal/mol", "Å", "adimensional")
      - description: qué representa y por qué importa
      - versions: historial completo de valores
      - staleness_policy: condiciones bajo las cuales se considera obsoleto
    """
    name: str
    category: ParameterCategory
    unit: str
    description: str
    versions: list[ParameterVersion] = field(default_factory=list)
    # Máximo de días sin recalibración antes de alertar
    max_age_days: int = 90
    # Tags adicionales para búsqueda/filtrado
    tags: list[str] = field(default_factory=list)

    @property
    def current_version(self) -> ParameterVersion | None:
        """Retorna la versión activa (no superseded)."""
        for v in reversed(self.versions):
            if v.is_active():
                return v
        return None

    @property
    def current_value(self) -> Any:
        """Retorna el valor activo o None."""
        cv = self.current_version
        return cv.value if cv else None

    def days_since_last_update(self) -> float | None:
        """Días desde la última actualización."""
        cv = self.current_version
        if cv is None:
            return None
        adopted = datetime.fromisoformat(cv.adopted_at)
        # Asegurar timezone-aware para evitar TypeError en resta
        if adopted.tzinfo is None:
            adopted = adopted.replace(tzinfo=UTC)
        now = datetime.now(UTC)
        return (now - adopted).total_seconds() / 86400.0

    def is_stale(self) -> bool:
        """¿El parámetro necesita recalibración por antigüedad?"""
        days = self.days_since_last_update()
        if days is None:
            return True  # Sin versión = definitivamente stale
        return days > self.max_age_days

    def add_version(
        self,
        value: Any,
        reason: str,
        reference: ParameterReference,
        calibration_id: str | None = None,
    ) -> ParameterVersion:
        """
        Agrega una nueva versión, superseding la anterior.

        No modifica la configuración activa del sistema — solo el registro.
        El CalibrationHealthMonitor o un humano debe decidir si aplicar.
        """
        now = datetime.now(UTC).isoformat()

        # Supersede la versión activa anterior
        for v in self.versions:
            if v.is_active():
                v.superseded_at = now

        new_version = ParameterVersion(
            value=value,
            version=len(self.versions) + 1,
            adopted_at=now,
            reason=reason,
            reference=reference,
            calibration_id=calibration_id,
        )
        self.versions.append(new_version)
        return new_version


class SciConfigRegistry:
    """
    Registro centralizado de parámetros científicos del pipeline.

    Uso:
        registry = SciConfigRegistry.create_default()
        affinity_best = registry.get("affinity_normalization_best")
        stale = registry.get_stale_parameters()
        registry.save("artifacts/sci_config_registry.json")

    Diseño:
      - Inmutable en operación normal: solo se modifica vía add_version() o update().
      - Serializable a JSON para auditoría y persistencia.
      - No accede a la red — los checks de freshness están en CalibrationHealthMonitor.
    """

    def __init__(self) -> None:
        self._parameters: dict[str, SciParameter] = {}
        self._created_at: str = datetime.now(UTC).isoformat()
        self._last_modified: str = self._created_at

    def register(self, param: SciParameter) -> None:
        """Registra un nuevo parámetro en el registry."""
        if param.name in self._parameters:
            raise ValueError(f"Parameter '{param.name}' already registered. Use update() to modify.")
        self._parameters[param.name] = param
        self._last_modified = datetime.now(UTC).isoformat()

    def get(self, name: str) -> SciParameter | None:
        """Obtiene un parámetro por nombre."""
        return self._parameters.get(name)

    def get_value(self, name: str) -> Any:
        """Obtiene el valor activo de un parámetro, o None."""
        param = self._parameters.get(name)
        return param.current_value if param else None

    def get_all(self) -> dict[str, SciParameter]:
        """Retorna todos los parámetros registrados."""
        return dict(self._parameters)

    def get_by_category(self, category: ParameterCategory) -> list[SciParameter]:
        """Filtra parámetros por categoría."""
        return [p for p in self._parameters.values() if p.category == category]

    def get_stale_parameters(self) -> list[tuple[SciParameter, StalenessReason]]:
        """
        Identifica parámetros que necesitan recalibración.

        Retorna lista de (parámetro, razón) para cada parámetro stale.
        Solo evalúa staleness por antigüedad aquí.
        Staleness por mejor estructura o drift se evalúa en CalibrationHealthMonitor.
        """
        stale: list[tuple[SciParameter, StalenessReason]] = []
        for param in self._parameters.values():
            if param.is_stale():
                stale.append((param, StalenessReason.AGE))
        return stale

    def update(
        self,
        name: str,
        value: Any,
        reason: str,
        reference: ParameterReference,
        calibration_id: str | None = None,
    ) -> ParameterVersion:
        """
        Actualiza un parámetro existente con una nueva versión.

        No modifica la configuración activa — solo el registro.
        """
        param = self._parameters.get(name)
        if param is None:
            raise KeyError(f"Parameter '{name}' not found in registry.")
        new_ver = param.add_version(value, reason, reference, calibration_id)
        self._last_modified = datetime.now(UTC).isoformat()
        return new_ver

    def generate_hash(self) -> str:
        """SHA-256 del estado actual del registry para trazabilidad."""
        snapshot = {
            name: param.current_value
            for name, param in sorted(self._parameters.items())
        }
        blob = json.dumps(snapshot, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def to_dict(self) -> dict:
        """Serializa el registry completo a diccionario."""
        return {
            "registry_version": "1.0.0",
            "created_at": self._created_at,
            "last_modified": self._last_modified,
            "config_hash": self.generate_hash(),
            "parameters": {
                name: asdict(param) for name, param in self._parameters.items()
            },
        }

    def save(self, path: str | Path) -> Path:
        """Persiste el registry a un archivo JSON."""
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return out

    @staticmethod
    def load(path: str | Path) -> SciConfigRegistry:
        """Carga un registry desde JSON."""
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        registry = SciConfigRegistry()
        registry._created_at = data.get("created_at", registry._created_at)
        registry._last_modified = data.get("last_modified", registry._last_modified)

        for name, pdata in data.get("parameters", {}).items():
            versions = []
            for vdata in pdata.get("versions", []):
                ref_data = vdata.get("reference", {})
                ref = ParameterReference(
                    source=ref_data.get("source", "unknown"),
                    doi=ref_data.get("doi"),
                    method=ref_data.get("method"),
                    notes=ref_data.get("notes"),
                )
                versions.append(ParameterVersion(
                    value=vdata["value"],
                    version=vdata["version"],
                    adopted_at=vdata["adopted_at"],
                    reason=vdata["reason"],
                    reference=ref,
                    calibration_id=vdata.get("calibration_id"),
                    superseded_at=vdata.get("superseded_at"),
                ))

            param = SciParameter(
                name=name,
                category=ParameterCategory(pdata["category"]),
                unit=pdata.get("unit", ""),
                description=pdata.get("description", ""),
                versions=versions,
                max_age_days=pdata.get("max_age_days", 90),
                tags=pdata.get("tags", []),
            )
            registry._parameters[name] = param

        expected_hash = data.get("config_hash")
        if expected_hash and registry.generate_hash() != expected_hash:
            raise ValueError(
                "SciConfigRegistry corrupto o editado sin re-sellar: "
                f"hash esperado {expected_hash}, obtenido {registry.generate_hash()}"
            )

        return registry

    def summary(self) -> dict:
        """Resumen legible del estado del registry."""
        total = len(self._parameters)
        stale = len(self.get_stale_parameters())
        categories = {}
        for p in self._parameters.values():
            cat = p.category.value
            categories[cat] = categories.get(cat, 0) + 1

        return {
            "total_parameters": total,
            "stale_parameters": stale,
            "healthy_parameters": total - stale,
            "categories": categories,
            "config_hash": self.generate_hash(),
            "last_modified": self._last_modified,
        }

    @staticmethod
    def create_default() -> SciConfigRegistry:
        """
        Crea el registry con los parámetros científicos del MVP actual.

        Cada parámetro incluye su valor, referencia, y justificación.
        Esta es la "fotografía" del estado científico del sistema.
        """
        registry = SciConfigRegistry()
        now = datetime.now(UTC).isoformat()

        # ── Target ──────────────────────────────────────────────────────
        registry.register(SciParameter(
            name="target_pdb_id",
            category=ParameterCategory.TARGET,
            unit="PDB ID",
            description=(
                "PDB ID de la estructura del receptor 5-HT1A usada para docking. "
                "Debe ser la estructura con mejor resolución disponible que contenga "
                "un ligando co-cristalizado en el sitio ortostérico."
            ),
            max_age_days=180,  # Verificar cada 6 meses si hay mejor estructura
            tags=["5-HT1A", "GPCR", "serotonin"],
            versions=[ParameterVersion(
                value="7E2Y",
                version=1,
                adopted_at=now,
                reason=(
                    "Cryo-EM 3.0 Å del complejo 5-HT1A–Gi con serotonina. "
                    "Reemplaza 3RZY (FABP4, target incorrecto)."
                ),
                reference=ParameterReference(
                    source="Xu et al., Nature 592:469-473 (2021)",
                    doi="10.1038/s41586-021-03376-8",
                    method="Selección manual de la mejor estructura cryo-EM disponible en RCSB PDB",
                    notes="Al momento de selección, 7E2Y es la estructura más usada para docking 5-HT1A.",
                ),
            )],
        ))

        registry.register(SciParameter(
            name="target_chain",
            category=ParameterCategory.TARGET,
            unit="chain ID",
            description="Cadena del receptor en el PDB. Auth chain en 7E2Y.",
            max_age_days=180,
            versions=[ParameterVersion(
                value="R",
                version=1,
                adopted_at=now,
                reason="Cadena R (auth) es el receptor 5-HT1A en 7E2Y.",
                reference=ParameterReference(
                    source="PDB 7E2Y header",
                    method="Inspección de cadenas en el archivo PDB",
                ),
            )],
        ))

        registry.register(SciParameter(
            name="target_resolution_angstrom",
            category=ParameterCategory.TARGET,
            unit="Å",
            description="Resolución de la estructura cristalográfica/cryo-EM.",
            max_age_days=180,
            versions=[ParameterVersion(
                value=3.0,
                version=1,
                adopted_at=now,
                reason="Resolución reportada en el header de 7E2Y.",
                reference=ParameterReference(
                    source="RCSB PDB entry 7E2Y",
                    doi="10.1038/s41586-021-03376-8",
                ),
            )],
        ))

        # ── Grid Box ───────────────────────────────────────────────────
        registry.register(SciParameter(
            name="grid_center",
            category=ParameterCategory.GRID_BOX,
            unit="Å (x, y, z)",
            description=(
                "Centro del grid box de docking. Calculado como centroide geométrico "
                "del ligando co-cristalizado (SRO) en 7E2Y cadena R."
            ),
            max_age_days=180,
            versions=[ParameterVersion(
                value=[103.03, 114.79, 108.36],
                version=1,
                adopted_at=now,
                reason="Centroide de SRO calculado con scripts/extract_grid_from_ligand.py",
                reference=ParameterReference(
                    source="Morris et al. (2009) J Comput Chem 30:2785-2791",
                    method="Centroide geométrico de átomos pesados del ligando co-cristalizado",
                    notes="python scripts/extract_grid_from_ligand.py --pdb-id 7E2Y --ligand-id SRO --chain R",
                ),
            )],
        ))

        registry.register(SciParameter(
            name="grid_size",
            category=ParameterCategory.GRID_BOX,
            unit="Å (x, y, z)",
            description=(
                "Tamaño del grid box de docking. 25 Å por lado para acomodar "
                "moléculas drug-like (MW 300-500) más grandes que serotonina (MW=176)."
            ),
            max_age_days=90,
            versions=[ParameterVersion(
                value=[25.0, 25.0, 25.0],
                version=1,
                adopted_at=now,
                reason=(
                    "Upgrade de 20³ a 25³ Å. Grid de 20 Å penaliza moléculas "
                    "drug-like típicas (MW 300-500) que son 2-3x más grandes que serotonina."
                ),
                reference=ParameterReference(
                    source="Feinstein & Brylinski (2015) J Mol Graph Model 62:43-47",
                    method="Regla empírica: grid debe cubrir ligando + 8-10 Å de margen",
                    notes=(
                        "Para serotonina (diámetro ~7Å) un grid de 20Å basta, "
                        "pero para drug-like (diámetro ~12-15Å) se necesita ≥25Å."
                    ),
                ),
            )],
        ))

        # ── Docking Engine ─────────────────────────────────────────────
        registry.register(SciParameter(
            name="vina_exhaustiveness_production",
            category=ParameterCategory.DOCKING_ENGINE,
            unit="adimensional",
            description=(
                "Exhaustiveness de Vina para uso interactivo. Balance velocidad/calidad."
            ),
            max_age_days=365,
            versions=[ParameterVersion(
                value=8,
                version=1,
                adopted_at=now,
                reason="Default de Vina 1.2.x. Apropiado para uso interactivo del MVP.",
                reference=ParameterReference(
                    source="Trott & Olson (2010) J Comput Chem 31:455-461",
                    notes="exhaustiveness=8 fue el default original de Vina.",
                ),
            )],
        ))

        registry.register(SciParameter(
            name="vina_exhaustiveness_calibration",
            category=ParameterCategory.DOCKING_ENGINE,
            unit="adimensional",
            description=(
                "Exhaustiveness alta para scripts de calibración/benchmark "
                "donde la calidad importa más que la velocidad."
            ),
            max_age_days=365,
            versions=[ParameterVersion(
                value=32,
                version=1,
                adopted_at=now,
                reason=(
                    "exhaustiveness=32 reduce la varianza del score significativamente. "
                    "~4x más lento que 8, pero necesario para calibración confiable."
                ),
                reference=ParameterReference(
                    source="Trott & Olson (2010) J Comput Chem 31:455-461",
                    notes=(
                        "La varianza del score converge aproximadamente con sqrt(exhaustiveness). "
                        "32 = 2x la desviación estándar de 8."
                    ),
                ),
            )],
        ))

        registry.register(SciParameter(
            name="vina_seed",
            category=ParameterCategory.DOCKING_ENGINE,
            unit="entero",
            description="Semilla para reproducibilidad determinística de Vina.",
            max_age_days=365,
            versions=[ParameterVersion(
                value=42,
                version=1,
                adopted_at=now,
                reason="Semilla fija para reproducibilidad determinística.",
                reference=ParameterReference(
                    source="Convención del proyecto MolDesign",
                    method="Semilla arbitraria fija; cualquier entero es válido",
                ),
            )],
        ))

        # ── Normalization ──────────────────────────────────────────────
        registry.register(SciParameter(
            name="affinity_normalization_best",
            category=ParameterCategory.NORMALIZATION,
            unit="kcal/mol",
            description=(
                "Afinidad que mapea a score=100. Debe ser un valor excelente "
                "pero alcanzable para el target específico."
            ),
            max_age_days=90,  # Re-evaluar cada trimestre
            tags=["normalization", "affinity", "calibration-dependent"],
            versions=[ParameterVersion(
                value=-10.0,
                version=1,
                adopted_at=now,
                reason=(
                    "Basado en el rango típico de Vina para GPCRs. "
                    "Los mejores ligandos conocidos de 5-HT1A suelen dar -8 a -10 kcal/mol."
                ),
                reference=ParameterReference(
                    source="Trott & Olson (2010), rango empírico observado",
                    notes=(
                        "PENDIENTE RE-ANCLAJE: este valor debe recalibrarse con el benchmark "
                        "real contra 7E2Y una vez completada la corrección HETATM."
                    ),
                ),
            )],
        ))

        registry.register(SciParameter(
            name="affinity_normalization_worst",
            category=ParameterCategory.NORMALIZATION,
            unit="kcal/mol",
            description=(
                "Afinidad que mapea a score=0. Representa interacción no específica."
            ),
            max_age_days=90,
            tags=["normalization", "affinity", "calibration-dependent"],
            versions=[ParameterVersion(
                value=-4.0,
                version=1,
                adopted_at=now,
                reason="Afinidades peores que -4 indican interacción no específica con GPCRs.",
                reference=ParameterReference(
                    source="Empirical range from literature",
                    notes="Conservatively captures the full dynamic range of Vina for drug-like molecules.",
                ),
            )],
        ))

        # ── Scoring Weights ────────────────────────────────────────────
        registry.register(SciParameter(
            name="score_weights",
            category=ParameterCategory.SCORING_WEIGHTS,
            unit="fracciones (suman 1.0)",
            description=(
                "Pesos del score compuesto: afinidad, ADME, drug-likeness. "
                "Afinidad recibe más peso porque es el componente basado en simulación."
            ),
            max_age_days=180,
            versions=[ParameterVersion(
                value={"affinity": 0.45, "adme": 0.30, "druglikeness": 0.25},
                version=1,
                adopted_at=now,
                reason=(
                    "Afinidad tiene el peso más alto como métrica principal de interacción. "
                    "ADME y drug-likeness son filtros heurísticos complementarios."
                ),
                reference=ParameterReference(
                    source="Decisión de diseño MolDesign MVP",
                    notes=(
                        "Estos pesos son una heurística de priorización. No pretenden "
                        "reflejar contribuciones biológicas reales."
                    ),
                ),
            )],
        ))

        # ── ADME Rules ─────────────────────────────────────────────────
        registry.register(SciParameter(
            name="lipinski_thresholds",
            category=ParameterCategory.ADME_RULES,
            unit="varios",
            description="Umbrales de la Regla de 5 de Lipinski para drug-likeness oral.",
            max_age_days=365,  # Reglas bien establecidas
            versions=[ParameterVersion(
                value={"MW": 500, "logP": 5.0, "HBD": 5, "HBA": 10},
                version=1,
                adopted_at=now,
                reason="Regla de 5 original de Lipinski.",
                reference=ParameterReference(
                    source="Lipinski et al. (1997) Adv Drug Deliv Rev 23:3-25",
                    doi="10.1016/S0169-409X(96)00423-1",
                    notes="Regla heurística ampliamente aceptada para filtrado inicial.",
                ),
            )],
        ))

        registry.register(SciParameter(
            name="veber_thresholds",
            category=ParameterCategory.ADME_RULES,
            unit="varios",
            description="Umbrales de Veber para biodisponibilidad oral.",
            max_age_days=365,
            versions=[ParameterVersion(
                value={"TPSA": 140, "RotBonds": 10},
                version=1,
                adopted_at=now,
                reason="Reglas de Veber para biodisponibilidad oral.",
                reference=ParameterReference(
                    source="Veber et al. (2002) J Med Chem 45:2615-2623",
                    doi="10.1021/jm020017n",
                ),
            )],
        ))

        # ── Validation ─────────────────────────────────────────────────
        registry.register(SciParameter(
            name="molecular_weight_range",
            category=ParameterCategory.VALIDATION,
            unit="Da",
            description="Rango de peso molecular aceptable para validación de entrada.",
            max_age_days=365,
            versions=[ParameterVersion(
                value={"min": 100.0, "max": 800.0},
                version=1,
                adopted_at=now,
                reason=(
                    "Rango conservador que incluye fragmentos (100+) hasta "
                    "moléculas drug-like complejas (800). Excluye péptidos grandes."
                ),
                reference=ParameterReference(
                    source="Convención MolDesign MVP",
                    notes="El límite superior podría extenderse para PROTACs en futuras fases.",
                ),
            )],
        ))

        return registry
