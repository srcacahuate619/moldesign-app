from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "moldesign_vc_runtime_source", ROOT / "scripts" / "vc_runtime_source.py"
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fuente_vc_runtime_versionada_coincide_con_manifiesto():
    source = MODULE.validated_vc_runtime_dir(ROOT)
    assert source == (ROOT / "tools" / "vc-runtime" / "x64").resolve()
    assert {p.name for p in source.glob("*.dll")} == {
        "msvcp140.dll",
        "msvcp140_atomic_wait.dll",
        "vcomp140.dll",
        "vcruntime140.dll",
        "vcruntime140_1.dll",
    }


def test_fuente_vc_runtime_rechaza_un_byte_alterado(tmp_path: Path):
    clone = tmp_path / "repo"
    destination = clone / "tools" / "vc-runtime"
    shutil.copytree(ROOT / "tools" / "vc-runtime", destination)
    victim = destination / "x64" / "msvcp140.dll"
    payload = bytearray(victim.read_bytes())
    payload[-1] ^= 1
    victim.write_bytes(payload)

    with pytest.raises(MODULE.VcRuntimeSourceError, match="SHA-256 incorrecto"):
        MODULE.validated_vc_runtime_dir(clone)