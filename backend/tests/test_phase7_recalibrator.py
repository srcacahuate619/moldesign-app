from scoring.auto_recalibrator import AutoRecalibrator
from scoring.calibration_health import CalibrationHealthMonitor, CheckStatus
from scoring.sci_config_registry import SciConfigRegistry


def test_legacy_normalization_is_declared_unavailable_and_never_proposed(tmp_path):
    registry = SciConfigRegistry.create_default()
    report = CalibrationHealthMonitor(registry).run_local_checks()
    normalization = next(c for c in report.checks if c.check_name == "normalization_coverage")
    assert normalization.status == CheckStatus.UNABLE

    proposal = AutoRecalibrator(
        registry=registry, artifacts_dir=tmp_path,
    ).run_local()
    assert all(
        change.parameter_name != "affinity_normalization_range"
        for change in proposal.proposed_changes
    )
