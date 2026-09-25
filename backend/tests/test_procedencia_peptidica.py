"""ENG-A06: los metadatos peptídicos proceden del ejecutor o quedan ausentes."""

from core.models import DockingPose
from services.esmfold.service import ESMFoldService


def test_rmsd_peptidico_no_medido_se_conserva_como_ausente():
    pose = DockingPose(rank=1, affinity=-5.0, rmsd_lb=None, rmsd_ub=None)
    assert pose.rmsd_lb is None
    assert pose.rmsd_ub is None


def test_cliente_propaga_metadata_observada_del_sidecar():
    dato = {
        "success": True,
        "poses": [],
        "best_confidence": None,
        "vina_version": "1.2.7",
        "vina_seed": 73,
        "vina_exhaustiveness": 8,
    }
    resultado = ESMFoldService._parse_response(None, dato, 1.0)
    assert resultado.vina_version == "1.2.7"
    assert resultado.vina_seed == 73
    assert resultado.vina_exhaustiveness == 8


def test_cliente_legacy_no_inventa_metadata_ausente():
    resultado = ESMFoldService._parse_response(None, {"success": True, "poses": []}, 1.0)
    assert resultado.vina_version is None
    assert resultado.vina_seed is None
    assert resultado.vina_exhaustiveness is None


def test_parser_del_sidecar_solo_acepta_stdout_observado(monkeypatch):
    import importlib.util
    import sys
    from pathlib import Path
    from types import ModuleType, SimpleNamespace

    ruta = Path(__file__).resolve().parents[1] / "sidecars/esmfold/predictor.py"
    logger = ModuleType("logger")
    logger.get_logger = lambda _name: SimpleNamespace()
    monkeypatch.setitem(sys.modules, "logger", logger)
    spec = importlib.util.spec_from_file_location("esmfold_predictor_metadata_test", ruta)
    modulo = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, modulo)
    spec.loader.exec_module(modulo)

    assert modulo._metadata_vina("AutoDock Vina v1.2.7\nrandom seed: 73") == ("1.2.7", 73)
    assert modulo._metadata_vina("") == (None, None)
