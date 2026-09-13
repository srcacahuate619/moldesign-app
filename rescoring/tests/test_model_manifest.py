"""Regression tests for the deterministic v4 model manifest release gate."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from model_manifest import (
    MANIFEST_VERSION,
    REQUIRED_MODEL_KEYS,
    canonical_manifest_bytes,
    default_artifacts_dir,
    load_manifest,
    verify_model_manifest,
)
from pesos_ausentes import motivo, pesos_ausentes, se_exigen_pesos


def _declarados(manifiesto: dict) -> list[str]:
    """Nombres de archivo que el manifiesto declara, a cualquier profundidad."""
    nombres: list[str] = []

    def recorrer(nodo: object) -> None:
        if isinstance(nodo, dict):
            for clave, valor in nodo.items():
                if clave in ("file", "metadata_file") and isinstance(valor, str):
                    nombres.append(valor)
                else:
                    recorrer(valor)
        elif isinstance(nodo, list):
            for valor in nodo:
                recorrer(valor)

    recorrer(manifiesto)
    return nombres


def _saltar_si_faltan_pesos() -> None:
    """El manifiesto declara pesos que el repositorio no distribuye.

    Un clon limpio no los tiene, y el verificador los reportaba como
    `artifact ausente` —un error de contrato— cuando en realidad describe
    correctamente algo que se descarga aparte.
    """
    directorio = default_artifacts_dir()
    try:
        manifiesto = load_manifest(directorio / "model-manifest.json")
    except OSError:
        return
    faltan = pesos_ausentes(directorio, _declarados(manifiesto))
    if faltan and not se_exigen_pesos():
        pytest.skip(motivo(faltan, "declarados por el manifiesto v4"))


def _load_generator_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "generate_model_manifest.py"
    spec = importlib.util.spec_from_file_location("generate_model_manifest_for_test", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def generator():
    return _load_generator_module()


def test_committed_manifest_is_valid_and_complete():
    _saltar_si_faltan_pesos()
    result = verify_model_manifest()
    assert result.valid, result.errors
    assert result.version == MANIFEST_VERSION
    assert set(result.model_keys) == REQUIRED_MODEL_KEYS


def test_generator_check_is_current_and_deterministic(generator):
    _saltar_si_faltan_pesos()
    first = generator.build_manifest()
    second = generator.build_manifest()
    assert canonical_manifest_bytes(first) == canonical_manifest_bytes(second)
    generator.check_manifest()


def test_generator_write_is_idempotent_without_a_timestamp(generator, tmp_path):
    _saltar_si_faltan_pesos()
    output = tmp_path / "model-manifest.json"
    assert generator.write_manifest(output) is True
    first_bytes = output.read_bytes()
    assert generator.write_manifest(output) is False
    assert output.read_bytes() == first_bytes


def test_runtime_verifier_detects_changed_artifact_hash(tmp_path):
    manifest = load_manifest(default_artifacts_dir() / "model-manifest.json")
    manifest["models"]["model_a_universal"]["sha256"] = "0" * 64
    path = tmp_path / "model-manifest.json"
    path.write_bytes(canonical_manifest_bytes(manifest))

    result = verify_model_manifest(path, default_artifacts_dir())
    assert not result.valid
    assert any("sha256 no coincide" in error for error in result.errors)


def test_generator_rejects_downgrade_or_lost_registered_model(generator):
    _saltar_si_faltan_pesos()
    desired = generator.build_manifest()
    downgrade = {
        "manifest_version": MANIFEST_VERSION + 1,
        "models": desired["models"],
    }
    with pytest.raises(generator.ManifestCheckError, match="Downgrade prohibido"):
        generator._assert_safe_transition(downgrade, desired)

    lost_model = {
        "manifest_version": MANIFEST_VERSION,
        "models": {**desired["models"], "future_model": {}},
    }
    with pytest.raises(generator.ManifestCheckError, match="perdería modelos"):
        generator._assert_safe_transition(lost_model, desired)


def test_json_schema_declares_exact_v4_model_set():
    schema_path = default_artifacts_dir() / "model-manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert schema["properties"]["manifest_version"]["const"] == MANIFEST_VERSION
    assert set(schema["properties"]["models"]["required"]) == REQUIRED_MODEL_KEYS
