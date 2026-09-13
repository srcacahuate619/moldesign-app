"""
scoring/auto_recalibrator.py

Auto-Recalibrator Pipeline — Recalibración científica semi-automática.

Propósito:
  Orquestar la recalibración del pipeline científico cuando el
  CalibrationHealthMonitor detecta que los parámetros están obsoletos
  o cuando nueva evidencia justifica un re-anclaje.

Filosofía:
  - SEMI-automático: propone cambios, no los aplica a ciegas.
  - Cada paso produce evidencia auditable.
  - Si un paso falla, el pipeline se degrada graciosamente.
  - NO altera la configuración de producción directamente.
  - Genera un RecalibrationProposal que debe ser revisado.

Pipeline de recalibración:
  1. Ejecutar CalibrationHealthMonitor → detectar qué necesita actualización.
  2. Si hay mejor PDB: alertar (no cambiar automáticamente, requiere validación manual).
  3. Si normalization drift: proponer nuevo rango basado en benchmark real.
  4. Si panel stale: proponer expansión del panel.
  5. Generar RecalibrationProposal con cambios sugeridos y evidencia.

Uso como script:
  python -m scoring.auto_recalibrator --output artifacts/recalibration_proposal.json

Uso programático:
  from scoring.auto_recalibrator import AutoRecalibrator
  recalibrator = AutoRecalibrator()
  proposal = await recalibrator.run()

Limitaciones:
  - No puede validar la calidad de una nueva estructura PDB sin docking real.
  - No puede evaluar el impacto de re-anclaje sin re-correr todo el benchmark.
  - No reemplaza el juicio de un químico medicinal o bioinformático.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from scoring.sci_config_registry import (
    SciConfigRegistry,
    ParameterReference,
)

from utils.logger import get_logger

log = get_logger(__name__)
from scoring.calibration_health import (
    CalibrationHealthMonitor,
    CheckStatus,
)


class ProposalAction(str, Enum):
    """Tipo de acción propuesta."""
    UPDATE_PARAMETER = "update_parameter"
    EXPAND_PANEL = "expand_panel"
    RE_RUN_BENCHMARK = "re_run_benchmark"
    EVALUATE_NEW_PDB = "evaluate_new_pdb"
    FORCE_REPREPARE = "force_reprepare"
    NO_ACTION = "no_action"


class ProposalPriority(str, Enum):
    """Prioridad de ejecución."""
    CRITICAL = "critical"   # Blocker: parámetro incorrecto
    HIGH = "high"           # Debería ejecutarse pronto
    MEDIUM = "medium"       # Mejora recomendada
    LOW = "low"             # Nice to have
    INFO = "info"           # Solo informativo


@dataclass
class ProposedChange:
    """Un cambio individual propuesto por el auto-recalibrator."""
    action: ProposalAction
    priority: ProposalPriority
    parameter_name: str | None
    current_value: Any
    proposed_value: Any
    reason: str
    evidence: str
    requires_benchmark: bool = False
    requires_human_review: bool = False
    command_to_execute: str | None = None  # Comando sugerido para ejecutar


@dataclass
class RecalibrationProposal:
    """
    Propuesta completa de recalibración generada por el AutoRecalibrator.

    No aplica cambios directamente. El operador o un pipeline automatizado
    (con validación) debe decidir qué cambios aceptar.
    """
    generated_at: str
    registry_hash_before: str
    health_report_summary: dict
    proposed_changes: list[ProposedChange] = field(default_factory=list)
    overall_recommendation: str = ""
    estimated_impact: str = ""

    def add_change(self, change: ProposedChange) -> None:
        self.proposed_changes.append(change)

    @property
    def has_critical_changes(self) -> bool:
        return any(c.priority == ProposalPriority.CRITICAL for c in self.proposed_changes)

    @property
    def n_changes(self) -> int:
        return len(self.proposed_changes)

    def to_dict(self) -> dict:
        return {
            "generated_at": self.generated_at,
            "registry_hash_before": self.registry_hash_before,
            "health_report_summary": self.health_report_summary,
            "n_proposed_changes": self.n_changes,
            "has_critical_changes": self.has_critical_changes,
            "overall_recommendation": self.overall_recommendation,
            "estimated_impact": self.estimated_impact,
            "proposed_changes": [asdict(c) for c in self.proposed_changes],
        }

    def save(self, path: str | Path) -> Path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return out


class AutoRecalibrator:
    """
    Pipeline de recalibración semi-automática.

    Workflow:
      1. Crea SciConfigRegistry (o carga uno existente)
      2. Ejecuta CalibrationHealthMonitor
      3. Analiza los hallazgos del health report
      4. Genera propuestas de cambio específicas y accionables
      5. Retorna RecalibrationProposal

    Los cambios NO se aplican automáticamente. La propuesta es un documento
    que debe ser revisado antes de aplicar cambios.
    """

    def __init__(
        self,
        registry: SciConfigRegistry | None = None,
        benchmark_path: str | Path | None = None,
        panel_path: str | Path | None = None,
        artifacts_dir: str | Path = "artifacts",
    ) -> None:
        self._registry = registry or SciConfigRegistry.create_default()
        self._benchmark_path = Path(benchmark_path) if benchmark_path else None
        self._panel_path = Path(panel_path) if panel_path else None
        self._artifacts_dir = Path(artifacts_dir)

    async def run(self) -> RecalibrationProposal:
        """
        Ejecuta el pipeline completo de recalibración.

        Retorna una propuesta con todos los cambios sugeridos.
        """
        # 1. Health check
        monitor = CalibrationHealthMonitor(
            self._registry,
            benchmark_path=self._benchmark_path,
            panel_path=self._panel_path,
        )
        health_report = await monitor.run_all_checks()

        # 2. Crear propuesta
        proposal = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before=self._registry.generate_hash(),
            health_report_summary={
                "overall_status": health_report.overall_status.value,
                "n_pass": sum(1 for c in health_report.checks if c.status == CheckStatus.PASS),
                "n_warning": sum(1 for c in health_report.checks if c.status == CheckStatus.WARNING),
                "n_fail": sum(1 for c in health_report.checks if c.status == CheckStatus.FAIL),
            },
        )

        # 3. Analizar cada check y generar propuestas
        for check in health_report.checks:
            self._analyze_check(check, proposal)

        # 4. Analizar normalization drift si hay benchmark
        if self._benchmark_path and self._benchmark_path.exists():
            self._propose_normalization_reanchor(proposal)

        # 5. Overall recommendation
        proposal.overall_recommendation = self._compute_overall_recommendation(proposal)
        proposal.estimated_impact = self._estimate_impact(proposal)

        return proposal

    def run_local(self) -> RecalibrationProposal:
        """Versión síncrona con solo checks locales (sin red)."""
        monitor = CalibrationHealthMonitor(
            self._registry,
            benchmark_path=self._benchmark_path,
            panel_path=self._panel_path,
        )
        health_report = monitor.run_local_checks()

        proposal = RecalibrationProposal(
            generated_at=datetime.now(UTC).isoformat(),
            registry_hash_before=self._registry.generate_hash(),
            health_report_summary={
                "overall_status": health_report.overall_status.value,
                "n_pass": sum(1 for c in health_report.checks if c.status == CheckStatus.PASS),
                "n_warning": sum(1 for c in health_report.checks if c.status == CheckStatus.WARNING),
                "n_fail": sum(1 for c in health_report.checks if c.status == CheckStatus.FAIL),
            },
        )

        for check in health_report.checks:
            self._analyze_check(check, proposal)

        if self._benchmark_path and self._benchmark_path.exists():
            self._propose_normalization_reanchor(proposal)

        proposal.overall_recommendation = self._compute_overall_recommendation(proposal)
        proposal.estimated_impact = self._estimate_impact(proposal)
        return proposal

    def _analyze_check(
        self,
        check: Any,  # HealthCheckResult
        proposal: RecalibrationProposal,
    ) -> None:
        """Convierte un health check result en propuestas de cambio."""

        if check.status == CheckStatus.PASS:
            return  # No action needed

        if check.check_name == "parameter_staleness":
            stale_params = check.details.get("stale_parameters", [])
            for sp in stale_params:
                proposal.add_change(ProposedChange(
                    action=ProposalAction.RE_RUN_BENCHMARK,
                    priority=ProposalPriority.MEDIUM,
                    parameter_name=sp["parameter"],
                    current_value=f"last updated {sp['days_since_update']} days ago",
                    proposed_value="re-calibrate with current benchmark",
                    reason=f"Parameter exceeds freshness window ({sp['max_age_days']} days).",
                    evidence=f"Last update: {sp['days_since_update']} days ago",
                    requires_benchmark=True,
                    command_to_execute=(
                        "cd backend && python -m scripts.calibrate_external_panel "
                        "--panel artifacts/bindingdb_5ht1a_panel.json "
                        "--output artifacts/external_calibration_report.json"
                    ),
                ))

        elif check.check_name == "better_pdb_structure":
            better = check.details.get("better_structures", [])
            for struct in better[:2]:  # Top 2 alternatives
                proposal.add_change(ProposedChange(
                    action=ProposalAction.EVALUATE_NEW_PDB,
                    priority=ProposalPriority.HIGH,
                    parameter_name="target_pdb_id",
                    current_value=check.details.get("current_pdb"),
                    proposed_value=struct["pdb_id"],
                    reason=(
                        f"Structure {struct['pdb_id']} has resolution "
                        f"{struct['resolution']} Å vs current "
                        f"{check.details.get('current_resolution')} Å."
                    ),
                    evidence="RCSB PDB search for UniProt P08908 (5-HT1A human)",
                    requires_human_review=True,
                    requires_benchmark=True,
                    command_to_execute=(
                        f"python scripts/extract_grid_from_ligand.py "
                        f"--pdb-id {struct['pdb_id']} --chain A"
                    ),
                ))

        elif check.check_name == "normalization_coverage":
            issues = check.details.get("issues", [])
            if check.recommendation:
                proposal.add_change(ProposedChange(
                    action=ProposalAction.UPDATE_PARAMETER,
                    priority=ProposalPriority.MEDIUM,
                    parameter_name="affinity_normalization_range",
                    current_value=[
                        check.details.get("normalization_best"),
                        check.details.get("normalization_worst"),
                    ],
                    proposed_value=check.recommendation,
                    reason="; ".join(issues),
                    evidence=f"Observed range: [{check.details.get('observed_min_affinity')}, {check.details.get('observed_max_affinity')}] kcal/mol",
                ))

        elif check.check_name == "panel_quality":
            if check.status in (CheckStatus.WARNING, CheckStatus.FAIL):
                proposal.add_change(ProposedChange(
                    action=ProposalAction.EXPAND_PANEL,
                    priority=ProposalPriority.MEDIUM,
                    parameter_name=None,
                    current_value=check.details.get("n_molecules"),
                    proposed_value="40+ molecules with >= 4 log units range",
                    reason="; ".join(check.details.get("issues", [])),
                    evidence="Warren et al. (2006): >= 30 molecules recommended for statistical power",
                    command_to_execute=(
                        "cd backend && python -m scripts.fetch_bindingdb_5ht1a_panel "
                        "--limit 40 --affinity-cutoff-nm 1000000"
                    ),
                ))

        elif check.check_name == "grid_adequacy":
            if check.status in (CheckStatus.WARNING, CheckStatus.FAIL):
                proposal.add_change(ProposedChange(
                    action=ProposalAction.UPDATE_PARAMETER,
                    priority=ProposalPriority.HIGH,
                    parameter_name="grid_size",
                    current_value=check.details.get("grid_size"),
                    proposed_value=[25.0, 25.0, 25.0],
                    reason=check.message,
                    evidence="Feinstein & Brylinski (2015) J Mol Graph Model 62:43-47",
                    requires_benchmark=True,
                    command_to_execute="Update vina_size_x/y/z in config.py to 25.0",
                ))

        elif check.check_name == "software_versions":
            if check.status == CheckStatus.FAIL:
                proposal.add_change(ProposedChange(
                    action=ProposalAction.NO_ACTION,
                    priority=ProposalPriority.CRITICAL,
                    parameter_name=None,
                    current_value=check.details.get("versions"),
                    proposed_value="Install missing software",
                    reason=check.message,
                    evidence="Critical dependencies missing",
                    requires_human_review=True,
                ))

    def _propose_normalization_reanchor(self, proposal: RecalibrationProposal) -> None:
        """
        Si hay benchmark data, propone re-anclaje de normalización basado
        en las afinidades realmente observadas.

        Estrategia:
          - best = percentil 5 de afinidades observadas (redondeado a 0.5)
          - worst = percentil 95 (redondeado a 0.5)
          - Esto evita que outliers distorsionen el rango.
        """
        if self._benchmark_path is None or not self._benchmark_path.exists():
            return

        try:
            benchmark = json.loads(self._benchmark_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        records = benchmark.get("results", benchmark.get("accepted", []))
        affinities: list[float] = []
        for rec in records:
            aff = rec.get("best_affinity_kcal") or rec.get("predicted_affinity_kcal")
            if aff is not None:
                affinities.append(float(aff))

        if len(affinities) < 5:
            return  # Not enough data

        affinities.sort()
        n = len(affinities)

        # Percentiles
        p5_idx = max(0, int(n * 0.05))
        p95_idx = min(n - 1, int(n * 0.95))
        p5 = affinities[p5_idx]
        p95 = affinities[p95_idx]

        # Redondear a 0.5 kcal/mol
        proposed_best = math.floor(p5 * 2) / 2.0   # Redondea hacia abajo (más negativo)
        proposed_worst = math.ceil(p95 * 2) / 2.0   # Redondea hacia arriba (menos negativo)

        # Asegurar rango mínimo de 4 kcal/mol
        if (proposed_worst - proposed_best) < 4.0:
            midpoint = (proposed_best + proposed_worst) / 2.0
            proposed_best = midpoint - 2.0
            proposed_worst = midpoint + 2.0

        current_best = self._registry.get_value("affinity_normalization_best") or -10.0
        current_worst = self._registry.get_value("affinity_normalization_worst") or -4.0

        # Solo proponer si el cambio es significativo (> 0.5 kcal/mol)
        best_diff = abs(proposed_best - current_best)
        worst_diff = abs(proposed_worst - current_worst)

        if best_diff > 0.5 or worst_diff > 0.5:
            proposal.add_change(ProposedChange(
                action=ProposalAction.UPDATE_PARAMETER,
                priority=ProposalPriority.HIGH,
                parameter_name="affinity_normalization_range",
                current_value={"best": current_best, "worst": current_worst},
                proposed_value={"best": proposed_best, "worst": proposed_worst},
                reason=(
                    f"Benchmark data suggests re-anchoring. "
                    f"Observed P5={p5:.2f}, P95={p95:.2f} kcal/mol. "
                    f"Current range [{current_best}, {current_worst}] → "
                    f"Proposed [{proposed_best}, {proposed_worst}]."
                ),
                evidence=(
                    f"Based on {n} docking results. "
                    f"Observed range: [{affinities[0]:.2f}, {affinities[-1]:.2f}] kcal/mol."
                ),
                requires_benchmark=False,  # Already based on benchmark
            ))

    def _compute_overall_recommendation(self, proposal: RecalibrationProposal) -> str:
        """Genera una recomendación general basada en las propuestas."""
        if not proposal.proposed_changes:
            return (
                "No changes needed. All parameters are within their freshness window "
                "and consistent with available evidence."
            )

        n_critical = sum(1 for c in proposal.proposed_changes if c.priority == ProposalPriority.CRITICAL)
        n_high = sum(1 for c in proposal.proposed_changes if c.priority == ProposalPriority.HIGH)
        n_medium = sum(1 for c in proposal.proposed_changes if c.priority == ProposalPriority.MEDIUM)
        n_human = sum(1 for c in proposal.proposed_changes if c.requires_human_review)

        parts = []
        if n_critical:
            parts.append(f"{n_critical} CRITICAL action(s) require immediate attention")
        if n_high:
            parts.append(f"{n_high} HIGH-priority change(s) recommended")
        if n_medium:
            parts.append(f"{n_medium} MEDIUM-priority improvement(s) suggested")
        if n_human:
            parts.append(f"{n_human} change(s) require human review before applying")

        return ". ".join(parts) + "."

    def _estimate_impact(self, proposal: RecalibrationProposal) -> str:
        """Estima el impacto de aplicar todos los cambios propuestos."""
        if not proposal.proposed_changes:
            return "No changes → no impact."

        impacts = set()
        for change in proposal.proposed_changes:
            if change.action == ProposalAction.UPDATE_PARAMETER:
                if "normalization" in (change.parameter_name or ""):
                    impacts.add("Scores will change for all molecules (re-normalization)")
                elif "grid" in (change.parameter_name or ""):
                    impacts.add("Docking results will change (grid box modification)")
            elif change.action == ProposalAction.EVALUATE_NEW_PDB:
                impacts.add("ALL docking results must be recalculated (new target)")
            elif change.action == ProposalAction.FORCE_REPREPARE:
                impacts.add("Receptor PDBQT must be regenerated")
            elif change.action == ProposalAction.EXPAND_PANEL:
                impacts.add("Calibration metrics may change (larger panel)")

        if not impacts:
            return "Changes are informational only."

        return " | ".join(sorted(impacts))

    def apply_non_destructive_changes(
        self,
        proposal: RecalibrationProposal,
    ) -> list[str]:
        """
        Aplica cambios que NO requieren revisión humana y NO destruyen datos.

        Esto SOLO actualiza el SciConfigRegistry (no la configuración activa).
        Retorna lista de cambios aplicados.

        Cambios que NO se aplican automáticamente:
        - EVALUATE_NEW_PDB (requiere validación manual)
        - Cualquier cambio con requires_human_review=True
        - Cualquier cambio con requires_benchmark=True que no esté basado en benchmark
        """
        applied = []
        for change in proposal.proposed_changes:
            if change.requires_human_review:
                continue
            if change.action == ProposalAction.EVALUATE_NEW_PDB:
                continue
            if change.action == ProposalAction.NO_ACTION:
                continue

            if (
                change.action == ProposalAction.UPDATE_PARAMETER
                and change.parameter_name
                and not change.requires_benchmark
            ):
                param = self._registry.get(change.parameter_name)
                if param is not None:
                    param.add_version(
                        value=change.proposed_value,
                        reason=change.reason,
                        reference=ParameterReference(
                            source="AutoRecalibrator",
                            method="Automatic re-anchoring based on benchmark data",
                            notes=change.evidence,
                        ),
                    )
                    applied.append(
                        f"Updated {change.parameter_name}: "
                        f"{change.current_value} → {change.proposed_value}"
                    )

        return applied


async def main_async() -> None:
    """Entry point para ejecución como script."""
    import argparse

    parser = argparse.ArgumentParser(description="MolDesign Auto-Recalibrator")
    parser.add_argument(
        "--benchmark",
        type=str,
        default="artifacts/benchmark_reference_report.json",
        help="Path to benchmark results JSON",
    )
    parser.add_argument(
        "--panel",
        type=str,
        default="artifacts/bindingdb_5ht1a_panel.json",
        help="Path to calibration panel JSON",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="artifacts/recalibration_proposal.json",
        help="Path to write the proposal",
    )
    parser.add_argument(
        "--registry-output",
        type=str,
        default="artifacts/sci_config_registry.json",
        help="Path to save updated registry",
    )
    parser.add_argument(
        "--auto-apply",
        action="store_true",
        help="Auto-apply non-destructive changes to registry (NOT to production config)",
    )
    args = parser.parse_args()

    benchmark_path = Path(args.benchmark) if Path(args.benchmark).exists() else None
    panel_path = Path(args.panel) if Path(args.panel).exists() else None

    recalibrator = AutoRecalibrator(
        benchmark_path=benchmark_path,
        panel_path=panel_path,
    )

    proposal = await recalibrator.run()

    # Save proposal
    proposal.save(args.output)

    log.info(
        "recalibration_proposal_generated",
        generated_at=str(proposal.generated_at),
        registry_hash=proposal.registry_hash_before,
        n_changes=proposal.n_changes,
        has_critical=proposal.has_critical_changes,
        overall_recommendation=proposal.overall_recommendation,
        estimated_impact=proposal.estimated_impact,
        output_path=args.output,
    )

    for i, change in enumerate(proposal.proposed_changes, 1):
        log.info(
            "recalibration_change",
            index=i,
            action=change.action.value,
            priority=change.priority.value,
            parameter=change.parameter_name or "N/A",
            reason=change.reason,
            command=change.command_to_execute or "",
        )

    if args.auto_apply:
        applied = recalibrator.apply_non_destructive_changes(proposal)
        if applied:
            log.info(
                "recalibration_auto_applied",
                changes=applied,
                registry_output=args.registry_output,
            )
            recalibrator._registry.save(args.registry_output)
        else:
            log.info("recalibration_no_auto_applied", reason="all require human review or benchmark")
    else:
        # Always save the registry for reference
        recalibrator._registry.save(args.registry_output)
        log.info("recalibration_registry_saved", path=args.registry_output)


def main() -> None:
    import asyncio
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
