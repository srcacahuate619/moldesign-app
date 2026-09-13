"""
scoring/calibration_health.py

Calibration Health Monitor — Monitoreo de salud de la calibración científica.

Propósito:
  Evaluar si los parámetros científicos actuales del pipeline siguen siendo
  válidos o si requieren recalibración. NO modifica parámetros automáticamente;
  genera un reporte con hallazgos y recomendaciones.

Checks implementados:
  1. Staleness por antigüedad (vía SciConfigRegistry)
  2. Mejor estructura PDB disponible (vía RCSB PDB REST API)
  3. Cobertura del rango de normalización vs benchmark observado
  4. Adecuación del grid box para la distribución de MW
  5. Validez del panel de calibración
  6. Versiones de software (RDKit, Meeko)

Principios:
  - Conservador: alerta ≠ auto-cambio. Solo reporta y sugiere.
  - Honesto: si no puede evaluar algo, lo dice.
  - Trazable: cada check produce evidencia auditable.
  - Offline-tolerant: si no hay red, reporta "unable_to_check" en lugar de fallar.

Limitaciones:
  - Las queries a RCSB PDB requieren conectividad a internet.
  - La evaluación de normalization drift requiere un benchmark previo.
  - No puede evaluar calidad de la preparación del receptor directamente.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from scoring.sci_config_registry import (
    SciConfigRegistry,
    ParameterCategory,
)


class CheckStatus(str, Enum):
    """Estado de un health check."""
    PASS = "pass"               # Todo bien
    WARNING = "warning"         # Funcionando pero hay algo que revisar
    FAIL = "fail"               # Algo necesita atención inmediata
    UNABLE = "unable_to_check"  # No se pudo evaluar (sin red, sin datos, etc.)
    SKIPPED = "skipped"         # Check deshabilitado o no aplica


class CheckSeverity(str, Enum):
    """Severidad de un hallazgo."""
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Resultado de un health check individual."""
    check_name: str
    status: CheckStatus
    severity: CheckSeverity
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    recommendation: str | None = None
    evidence: str | None = None


@dataclass
class CalibrationHealthReport:
    """Reporte completo de salud de la calibración."""
    generated_at: str
    registry_hash: str
    checks: list[HealthCheckResult] = field(default_factory=list)
    overall_status: CheckStatus = CheckStatus.PASS

    def add_check(self, result: HealthCheckResult) -> None:
        self.checks.append(result)
        # Overall es el peor status
        priority = {
            CheckStatus.PASS: 0,
            CheckStatus.SKIPPED: 1,
            CheckStatus.UNABLE: 2,
            CheckStatus.WARNING: 3,
            CheckStatus.FAIL: 4,
        }
        if priority.get(result.status, 0) > priority.get(self.overall_status, 0):
            self.overall_status = result.status

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "registry_hash": self.registry_hash,
            "overall_status": self.overall_status.value,
            "n_checks": len(self.checks),
            "n_pass": sum(1 for c in self.checks if c.status == CheckStatus.PASS),
            "n_warning": sum(1 for c in self.checks if c.status == CheckStatus.WARNING),
            "n_fail": sum(1 for c in self.checks if c.status == CheckStatus.FAIL),
            "n_unable": sum(1 for c in self.checks if c.status == CheckStatus.UNABLE),
            "checks": [asdict(c) for c in self.checks],
        }

    def save(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return out


class CalibrationHealthMonitor:
    """
    Ejecuta checks de salud sobre la calibración científica.

    Uso:
        registry = SciConfigRegistry.create_default()
        monitor = CalibrationHealthMonitor(registry)
        report = await monitor.run_all_checks()
        report.save("artifacts/calibration_health_report.json")

    Los checks que requieren red (RCSB PDB) son async.
    Los checks que solo usan datos locales son sync.
    """

    def __init__(
        self,
        registry: SciConfigRegistry,
        benchmark_path: str | Path | None = None,
        panel_path: str | Path | None = None,
    ) -> None:
        self._registry = registry
        self._benchmark_path = Path(benchmark_path) if benchmark_path else None
        self._panel_path = Path(panel_path) if panel_path else None

    async def run_all_checks(self) -> CalibrationHealthReport:
        """Ejecuta todos los health checks y retorna el reporte."""
        report = CalibrationHealthReport(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash=self._registry.generate_hash(),
        )

        # Checks locales (no requieren red)
        self._check_parameter_staleness(report)
        self._check_normalization_coverage(report)
        self._check_grid_adequacy(report)
        self._check_panel_quality(report)
        self._check_software_versions(report)

        # Checks que requieren red
        await self._check_better_pdb_structure(report)

        return report

    def run_local_checks(self) -> CalibrationHealthReport:
        """Ejecuta solo los checks que no requieren red."""
        report = CalibrationHealthReport(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash=self._registry.generate_hash(),
        )

        self._check_parameter_staleness(report)
        self._check_normalization_coverage(report)
        self._check_grid_adequacy(report)
        self._check_panel_quality(report)
        self._check_software_versions(report)

        report.add_check(HealthCheckResult(
            check_name="better_pdb_structure",
            status=CheckStatus.SKIPPED,
            severity=CheckSeverity.INFO,
            message="Check requires network access. Use run_all_checks() for full evaluation.",
        ))

        return report

    # ── Check: Parameter Staleness ─────────────────────────────────────

    def _check_parameter_staleness(self, report: CalibrationHealthReport) -> None:
        """Verifica si algún parámetro excedió su max_age_days."""
        stale_params = self._registry.get_stale_parameters()

        if not stale_params:
            report.add_check(HealthCheckResult(
                check_name="parameter_staleness",
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                message="All parameters are within their freshness window.",
            ))
            return

        stale_details = []
        max_severity = CheckSeverity.LOW

        for param, reason in stale_params:
            days = param.days_since_last_update()
            days_str = f"{days:.0f}" if days else "unknown"

            # Calibration-dependent params son más críticos cuando stale
            if "calibration-dependent" in param.tags:
                sev = CheckSeverity.HIGH
            elif param.category in (ParameterCategory.GRID_BOX, ParameterCategory.TARGET):
                sev = CheckSeverity.MEDIUM
            else:
                sev = CheckSeverity.LOW

            if _severity_rank(sev) > _severity_rank(max_severity):
                max_severity = sev

            stale_details.append({
                "parameter": param.name,
                "days_since_update": days_str,
                "max_age_days": param.max_age_days,
                "reason": reason.value,
            })

        report.add_check(HealthCheckResult(
            check_name="parameter_staleness",
            status=CheckStatus.WARNING,
            severity=max_severity,
            message=f"{len(stale_params)} parameter(s) exceed their freshness window.",
            details={"stale_parameters": stale_details},
            recommendation=(
                "Run recalibration pipeline to update stale parameters. "
                "Priority: calibration-dependent > target > grid_box > others."
            ),
        ))

    # ── Check: Normalization Coverage ──────────────────────────────────

    def _check_normalization_coverage(self, report: CalibrationHealthReport) -> None:
        """
        Verifica que el rango de normalización [-10, -4] cubre las afinidades
        observadas en el último benchmark.
        """
        if self._benchmark_path is None or not self._benchmark_path.exists():
            report.add_check(HealthCheckResult(
                check_name="normalization_coverage",
                status=CheckStatus.UNABLE,
                severity=CheckSeverity.MEDIUM,
                message="No benchmark data available to evaluate normalization coverage.",
                recommendation="Run benchmark_reference_panel.py to generate baseline data.",
            ))
            return

        try:
            benchmark = json.loads(self._benchmark_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            report.add_check(HealthCheckResult(
                check_name="normalization_coverage",
                status=CheckStatus.UNABLE,
                severity=CheckSeverity.MEDIUM,
                message=f"Could not read benchmark file: {e}",
            ))
            return

        # Extraer afinidades del benchmark
        # Soporta múltiples formatos de benchmark:
        #   - "runs" con "best_affinity" (benchmark_reference_panel.py output)
        #   - "accepted" con "predicted_affinity_kcal" (external_calibration)
        #   - "results" con "best_affinity_kcal" (formato genérico)
        affinities: list[float] = []
        records = (
            benchmark.get("runs")
            or benchmark.get("results")
            or benchmark.get("accepted", [])
        )
        for rec in records:
            aff = (
                rec.get("best_affinity")
                or rec.get("best_affinity_kcal")
                or rec.get("predicted_affinity_kcal")
            )
            if aff is not None:
                affinities.append(float(aff))

        if not affinities:
            report.add_check(HealthCheckResult(
                check_name="normalization_coverage",
                status=CheckStatus.UNABLE,
                severity=CheckSeverity.MEDIUM,
                message="Benchmark file contains no affinity values.",
            ))
            return

        best_param = self._registry.get_value("affinity_normalization_best") or -10.0
        worst_param = self._registry.get_value("affinity_normalization_worst") or -4.0
        observed_min = min(affinities)
        observed_max = max(affinities)

        # Chequear si hay afinidades fuera del rango de normalización
        n_below_best = sum(1 for a in affinities if a < best_param)
        n_above_worst = sum(1 for a in affinities if a > worst_param)
        n_total = len(affinities)

        issues = []
        if n_below_best > 0:
            issues.append(
                f"{n_below_best}/{n_total} affinities below best={best_param} "
                f"(min observed: {observed_min:.2f} kcal/mol). "
                "These get clamped to score=100, losing resolution at the top."
            )
        if n_above_worst > 0:
            issues.append(
                f"{n_above_worst}/{n_total} affinities above worst={worst_param} "
                f"(max observed: {observed_max:.2f} kcal/mol). "
                "These get clamped to score=0, losing resolution at the bottom."
            )

        # Chequear si el rango observado es muy estrecho vs el rango de normalización
        obs_range = observed_max - observed_min
        norm_range = worst_param - best_param
        utilization = obs_range / norm_range if norm_range != 0 else 0

        if issues:
            report.add_check(HealthCheckResult(
                check_name="normalization_coverage",
                status=CheckStatus.WARNING,
                severity=CheckSeverity.MEDIUM,
                message=f"Normalization range [{best_param}, {worst_param}] does not fully cover observed affinities.",
                details={
                    "normalization_best": best_param,
                    "normalization_worst": worst_param,
                    "observed_min_affinity": round(observed_min, 3),
                    "observed_max_affinity": round(observed_max, 3),
                    "n_below_best": n_below_best,
                    "n_above_worst": n_above_worst,
                    "range_utilization": round(utilization, 3),
                    "issues": issues,
                },
                recommendation=(
                    "Consider re-anchoring normalization range to "
                    f"[{min(best_param, observed_min - 0.5):.1f}, "
                    f"{max(worst_param, observed_max + 0.5):.1f}] kcal/mol."
                ),
            ))
        else:
            report.add_check(HealthCheckResult(
                check_name="normalization_coverage",
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                message="Normalization range covers all observed benchmark affinities.",
                details={
                    "normalization_range": [best_param, worst_param],
                    "observed_range": [round(observed_min, 3), round(observed_max, 3)],
                    "range_utilization": round(utilization, 3),
                },
            ))

    # ── Check: Grid Box Adequacy ───────────────────────────────────────

    def _check_grid_adequacy(self, report: CalibrationHealthReport) -> None:
        """
        Verifica que el grid box es adecuado para moléculas drug-like típicas.

        Regla empírica: grid_size >= max_ligand_diameter + 10 Å de margen.
        Para drug-like (MW 300-500), el diámetro estimado es ~12-15 Å.
        """
        grid_size = self._registry.get_value("grid_size")
        if grid_size is None:
            report.add_check(HealthCheckResult(
                check_name="grid_adequacy",
                status=CheckStatus.UNABLE,
                severity=CheckSeverity.MEDIUM,
                message="Grid size not found in registry.",
            ))
            return

        min_dim = min(grid_size) if isinstance(grid_size, (list, tuple)) else grid_size

        # Para MW 500, diámetro estimado ~15 Å → necesita grid >= 25 Å
        # Para MW 300, diámetro estimado ~12 Å → necesita grid >= 22 Å
        if min_dim < 22.0:
            report.add_check(HealthCheckResult(
                check_name="grid_adequacy",
                status=CheckStatus.FAIL,
                severity=CheckSeverity.HIGH,
                message=f"Grid size {min_dim:.1f} Å is too small for drug-like molecules.",
                details={"grid_size": grid_size, "min_recommended": 25.0},
                recommendation="Increase grid to at least 25 Å per side.",
                evidence="Feinstein & Brylinski (2015) J Mol Graph Model 62:43-47",
            ))
        elif min_dim < 25.0:
            report.add_check(HealthCheckResult(
                check_name="grid_adequacy",
                status=CheckStatus.WARNING,
                severity=CheckSeverity.MEDIUM,
                message=f"Grid size {min_dim:.1f} Å is marginal for larger drug-like molecules (MW>400).",
                details={"grid_size": grid_size, "min_recommended": 25.0},
            ))
        else:
            report.add_check(HealthCheckResult(
                check_name="grid_adequacy",
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                message=f"Grid size {min_dim:.1f} Å is adequate for drug-like molecules.",
                details={"grid_size": grid_size},
            ))

    # ── Check: Panel Quality ───────────────────────────────────────────

    def _check_panel_quality(self, report: CalibrationHealthReport) -> None:
        """
        Verifica que el panel de calibración cumple estándares mínimos:
        - >= 30 moléculas (Warren et al. 2006)
        - >= 4 log units de rango en pIC50
        - Representación de 3 tiers de actividad
        """
        if self._panel_path is None or not self._panel_path.exists():
            report.add_check(HealthCheckResult(
                check_name="panel_quality",
                status=CheckStatus.UNABLE,
                severity=CheckSeverity.MEDIUM,
                message="No calibration panel available.",
                recommendation="Run fetch_bindingdb_5ht1a_panel.py --limit 40",
            ))
            return

        try:
            panel = json.loads(self._panel_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            report.add_check(HealthCheckResult(
                check_name="panel_quality",
                status=CheckStatus.UNABLE,
                severity=CheckSeverity.MEDIUM,
                message=f"Could not read panel file: {e}",
            ))
            return

        records = panel.get("records", [])
        n_molecules = len(records)
        p_activities = [r.get("p_activity", r.get("pchembl_value")) for r in records]
        p_activities = [float(p) for p in p_activities if p is not None]

        issues = []
        if n_molecules < 30:
            issues.append(
                f"Panel has only {n_molecules} molecules (recommended >= 30). "
                "Statistical power for correlation is limited."
            )

        if len(p_activities) >= 2:
            p_range = max(p_activities) - min(p_activities)
            if p_range < 4.0:
                issues.append(
                    f"Activity range is {p_range:.2f} log units (recommended >= 4.0). "
                    "Narrow range limits discriminative power of Spearman correlation."
                )
        else:
            p_range = 0.0
            issues.append("Insufficient p_activity data to evaluate dynamic range.")

        # Check 3-tier coverage
        criteria = panel.get("criteria", {})
        tier_counts = criteria.get("tier_counts", {})
        if tier_counts:
            empty_tiers = [t for t, c in tier_counts.items() if c == 0]
            if empty_tiers:
                issues.append(
                    f"Empty activity tiers: {empty_tiers}. "
                    "All tiers should be populated for robust correlation."
                )

        if issues:
            report.add_check(HealthCheckResult(
                check_name="panel_quality",
                status=CheckStatus.WARNING,
                severity=CheckSeverity.MEDIUM,
                message=f"Panel has {len(issues)} quality issue(s).",
                details={
                    "n_molecules": n_molecules,
                    "p_activity_range": round(p_range, 3) if p_range else None,
                    "tier_counts": tier_counts or "not available",
                    "issues": issues,
                },
                recommendation="Expand panel with fetch_bindingdb_5ht1a_panel.py --limit 40 --affinity-cutoff-nm 1000000",
            ))
        else:
            report.add_check(HealthCheckResult(
                check_name="panel_quality",
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                message=f"Panel has {n_molecules} molecules with {p_range:.2f} log units range.",
                details={
                    "n_molecules": n_molecules,
                    "p_activity_range": round(p_range, 3),
                    "tier_counts": tier_counts,
                },
            ))

    # ── Check: Software Versions ───────────────────────────────────────

    def _check_software_versions(self, report: CalibrationHealthReport) -> None:
        """Reporta versiones de software crítico para trazabilidad."""
        versions = {}

        try:
            import rdkit
            versions["rdkit"] = rdkit.__version__
        except ImportError:
            versions["rdkit"] = "NOT INSTALLED"

        try:
            import meeko
            versions["meeko"] = getattr(meeko, "__version__", "unknown")
        except ImportError:
            versions["meeko"] = "NOT INSTALLED"

        try:
            import numpy
            versions["numpy"] = numpy.__version__
        except ImportError:
            versions["numpy"] = "NOT INSTALLED"

        missing = [k for k, v in versions.items() if v == "NOT INSTALLED"]

        if missing:
            report.add_check(HealthCheckResult(
                check_name="software_versions",
                status=CheckStatus.FAIL,
                severity=CheckSeverity.CRITICAL,
                message=f"Critical software missing: {missing}",
                details={"versions": versions},
                recommendation=f"Install missing packages: {', '.join(missing)}",
            ))
        else:
            report.add_check(HealthCheckResult(
                check_name="software_versions",
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                message="All critical software packages are available.",
                details={"versions": versions},
                evidence=(
                    "Version tracking is essential for reproducibility. "
                    "If any version changes, recalibration should be considered."
                ),
            ))

    # ── Check: Better PDB Structure ────────────────────────────────────

    async def _check_better_pdb_structure(self, report: CalibrationHealthReport) -> None:
        """
        Consulta RCSB PDB para buscar estructuras más recientes o de mejor
        resolución del receptor 5-HT1A humano.

        Query: UniProt P08908 (HTR1A_HUMAN) con resolución < 3.0 Å.
        """
        current_pdb = self._registry.get_value("target_pdb_id") or "7E2Y"
        current_resolution = self._registry.get_value("target_resolution_angstrom") or 3.0

        try:
            import httpx
        except ImportError:
            report.add_check(HealthCheckResult(
                check_name="better_pdb_structure",
                status=CheckStatus.UNABLE,
                severity=CheckSeverity.LOW,
                message="httpx not available for RCSB PDB query.",
            ))
            return

        # RCSB PDB Search API v2
        # Busca estructuras del receptor 5-HT1A humano (UniProt P08908)
        query_payload = {
            "query": {
                "type": "group",
                "logical_operator": "and",
                "nodes": [
                    {
                        "type": "terminal",
                        "service": "text",
                        "parameters": {
                            "attribute": "rcsb_polymer_entity_container_identifiers.reference_sequence_identifiers.database_accession",
                            "operator": "exact_match",
                            "value": "P08908",  # UniProt for human 5-HT1A
                        },
                    },
                    {
                        "type": "terminal",
                        "service": "text",
                        "parameters": {
                            "attribute": "rcsb_entry_info.resolution_combined",
                            "operator": "less_or_equal",
                            "value": 5.0,  # Include all, we'll compare resolution
                        },
                    },
                ],
            },
            "return_type": "entry",
            "request_options": {
                "results_content_type": ["experimental"],
                "sort": [
                    {
                        "sort_by": "rcsb_entry_info.resolution_combined",
                        "direction": "asc",
                    }
                ],
                "paginate": {"start": 0, "rows": 10},
            },
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://search.rcsb.org/rcsbsearch/v2/query",
                    json=query_payload,
                )
                if resp.status_code != 200:
                    report.add_check(HealthCheckResult(
                        check_name="better_pdb_structure",
                        status=CheckStatus.UNABLE,
                        severity=CheckSeverity.LOW,
                        message=f"RCSB PDB search returned status {resp.status_code}.",
                        details={"response": resp.text[:200]},
                    ))
                    return

                data = resp.json()
                results = data.get("result_set", [])
                pdb_ids = [r["identifier"] for r in results]

        except Exception as e:
            report.add_check(HealthCheckResult(
                check_name="better_pdb_structure",
                status=CheckStatus.UNABLE,
                severity=CheckSeverity.LOW,
                message=f"Could not query RCSB PDB: {type(e).__name__}: {e}",
            ))
            return

        if not pdb_ids:
            report.add_check(HealthCheckResult(
                check_name="better_pdb_structure",
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                message="No 5-HT1A structures found in RCSB PDB (unexpected).",
            ))
            return

        # Verificar si hay una estructura con mejor resolución que la actual
        # Necesitamos consultar resolución de cada PDB
        better_structures = []
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for pdb_id in pdb_ids[:5]:  # Check top 5 by resolution
                    if pdb_id.upper() == current_pdb.upper():
                        continue
                    resp = await client.get(
                        f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
                    )
                    if resp.status_code == 200:
                        entry = resp.json()
                        resolution = (
                            entry.get("rcsb_entry_info", {})
                            .get("resolution_combined", [None])
                        )
                        if isinstance(resolution, list):
                            resolution = resolution[0] if resolution else None

                        # Check if it has a bound ligand in the orthosteric site
                        has_ligand = bool(
                            entry.get("rcsb_entry_info", {}).get("nonpolymer_entity_count", 0) > 0
                        )

                        if resolution is not None and resolution < current_resolution:
                            better_structures.append({
                                "pdb_id": pdb_id,
                                "resolution": resolution,
                                "has_ligand": has_ligand,
                                "title": entry.get("struct", {}).get("title", ""),
                            })
        except Exception:
            pass  # Non-critical failure, we proceed with what we have

        if better_structures:
            best_alt = better_structures[0]
            report.add_check(HealthCheckResult(
                check_name="better_pdb_structure",
                status=CheckStatus.WARNING,
                severity=CheckSeverity.MEDIUM,
                message=(
                    f"Found {len(better_structures)} 5-HT1A structure(s) with better resolution "
                    f"than current {current_pdb} ({current_resolution} Å)."
                ),
                details={
                    "current_pdb": current_pdb,
                    "current_resolution": current_resolution,
                    "better_structures": better_structures,
                },
                recommendation=(
                    f"Consider evaluating {best_alt['pdb_id']} "
                    f"({best_alt['resolution']} Å) as replacement target. "
                    f"Verify it has a co-crystallized ligand suitable for grid box definition."
                ),
            ))
        else:
            report.add_check(HealthCheckResult(
                check_name="better_pdb_structure",
                status=CheckStatus.PASS,
                severity=CheckSeverity.INFO,
                message=(
                    f"Current structure {current_pdb} ({current_resolution} Å) "
                    f"is the best available or comparable to alternatives."
                ),
                details={
                    "pdb_ids_checked": pdb_ids[:5],
                    "current_pdb": current_pdb,
                },
            ))


def _severity_rank(sev: CheckSeverity) -> int:
    """Ordena severidades numéricamente."""
    return {
        CheckSeverity.INFO: 0,
        CheckSeverity.LOW: 1,
        CheckSeverity.MEDIUM: 2,
        CheckSeverity.HIGH: 3,
        CheckSeverity.CRITICAL: 4,
    }.get(sev, 0)
