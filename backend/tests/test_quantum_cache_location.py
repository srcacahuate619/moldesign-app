"""El caché cuántico es estado de usuario, no parte del bundle inmutable."""

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[2] / "scripts" / "compute_quantum_features.py"
SPEC = importlib.util.spec_from_file_location("moldesign_compute_quantum_features", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
quantum = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(quantum)


def test_quantum_cache_respects_local_data_dir(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))

    expected = tmp_path / "quantum_cache.db"
    assert quantum.quantum_cache_path() == expected

    connection = quantum._get_qc_db()
    connection.close()
    assert expected.is_file()


def test_xtb_resolution_has_no_machine_specific_fallback():
    source = Path(quantum.__file__).read_text(encoding="utf-8")

    assert "D:\\moldesign-app" not in source
