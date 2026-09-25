from pathlib import Path


def test_esmfold_logs_follow_data_directory(monkeypatch, tmp_path):
    from sidecars.esmfold.config import _default_log_dir

    monkeypatch.delenv("ESMFOLD_LOG_DIR", raising=False)
    monkeypatch.delenv("MOLDESIGN_TESTING", raising=False)
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    assert _default_log_dir() == tmp_path / "logs" / "esmfold"


def test_esmfold_test_logs_use_temp_not_source(monkeypatch, tmp_path):
    from sidecars.esmfold import config

    monkeypatch.delenv("ESMFOLD_LOG_DIR", raising=False)
    monkeypatch.delenv("LOCAL_DATA_DIR", raising=False)
    monkeypatch.setenv("MOLDESIGN_TESTING", "1")
    monkeypatch.setattr(config.tempfile, "gettempdir", lambda: str(tmp_path))
    log_dir = config._default_log_dir()
    assert log_dir.is_relative_to(tmp_path)
    assert not log_dir.is_relative_to(Path(config.SERVICE_ROOT))
