"""A trace must be observational and survive outside the docking session."""
import asyncio
import os
from pathlib import Path
import subprocess
import importlib.util
import json

import pytest

from services.docking import search_trace
from services.docking.vina_service import _docking_cache_fingerprint

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def native_runs(tmp_path_factory):
    root = tmp_path_factory.mktemp("native-vina-search")
    reference = ROOT / "tools/vina/vina.exe"
    if not reference.is_file():
        # Los binarios de Vina no se versionan; su manifiesto sí. En un clon limpio
        # (la CI) `instrumented` lee el manifiesto y no encuentra el binario.
        pytest.skip("Vina is not installed in this tree (binaries are not versioned)")
    binary, identity = search_trace.instrumented(str(reference))
    if identity is None:
        pytest.skip("Native instrumented Vina is not installed")
    receptor = b"ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00     0.000 C\n"
    fixture = (ROOT / "backend/tests/fixtures/meeko_export/paracetamol_9_poses.pdbqt").read_bytes()
    ligand = search_trace.models(fixture)[0]
    (root / "receptor.pdbqt").write_bytes(receptor)
    (root / "ligand.pdbqt").write_bytes(ligand)
    runs = []
    for seed in (42, 7):
        outputs = []
        for tracing in (False, True):
            output = root / f"poses-{seed}-{tracing}.pdbqt"
            prefix = root / f"trace-{seed}"
            env = dict(os.environ); env.pop("VINA_TRACE_PREFIX", None)
            if tracing: env["VINA_TRACE_PREFIX"] = str(prefix)
            result = subprocess.run([binary, "--receptor", str(root / "receptor.pdbqt"),
                "--ligand", str(root / "ligand.pdbqt"), "--center_x", "0", "--center_y", "0",
                "--center_z", "0", "--size_x", "24", "--size_y", "24", "--size_z", "24",
                "--cpu", "1", "--exhaustiveness", "2", "--max_evals", "500",
                "--seed", str(seed), "--out", str(output)],
                capture_output=True, env=env, timeout=45, creationflags=0x08000000 if os.name == "nt" else 0)
            assert result.returncode == 0, result.stderr.decode()
            outputs.append(output.read_bytes())
        assert outputs[0] == outputs[1], "Capturing search changed the docking output"
        runs.append(dict(prefix=prefix, output=output, replicas=2, identity=identity,
                         receptor=receptor, ligand=ligand, seed=seed, cpu=1,
                         center=(0,0,0), size=(24,24,24)))
    return runs


def test_native_capture_does_not_change_docking(native_runs):
    assert len(native_runs) == 2


@pytest.mark.asyncio
async def test_two_searches_frozen_and_recovered_independently(native_runs, monkeypatch):
    stored = {}
    async def write(data, name): stored[name] = data; return name
    async def read(name): return stored[name]
    monkeypatch.setattr(search_trace, "write_bytes", write)
    monkeypatch.setattr(search_trace, "read_bytes", read)
    records = [await search_trace.persist(**run) for run in native_runs]
    assert records[0]["archive_path"] != records[1]["archive_path"]
    for info in records:
        metadata, files = await search_trace.recover(info)
        assert metadata["trace"]["replicas"] == 2
        assert len(metadata["trace"]["resumenes"]) == 2
        assert metadata["trace"]["instantaneas"]
    stored[records[0]["archive_path"]] += b"corrupted"
    with pytest.raises(ValueError, match="hash"):
        await search_trace.recover(records[0])
    await search_trace.recover(records[1])


def test_cache_identity_separates_instrumented_and_old_runs():
    args = dict(receptor_sha256="a"*64, target_chain="A", center=(0,0,0), size=(24,24,24),
                hotspots=[], docking_engine="vina", exhaustiveness=2, num_poses=9, seed=42)
    assert _docking_cache_fingerprint(**args) != _docking_cache_fingerprint(**args, trace_binary_sha256="b"*64)


@pytest.mark.asyncio
async def test_archive_allows_maximum_supported_replica_count(native_runs, tmp_path, monkeypatch):
    # Repeat a measured replica as synthetic archive data to exercise the
    # API's upper bound without running 128 expensive native searches.
    source = native_runs[0]
    prefix = tmp_path / "trace"
    for suffix in ("_task_0.csv", "_task_0.pdbqt"):
        Path(str(prefix) + suffix).write_bytes(Path(str(source["prefix"]) + suffix).read_bytes())
    summary = Path(str(source["prefix"]) + "_task_0_summary.txt").read_text()
    for index in range(search_trace.MAX_REPLICAS):
        Path(str(prefix) + f"_task_{index}_summary.txt").write_text(summary.replace("task=0", f"task={index}"))
    stored = {}
    async def write(data, name): stored[name] = data; return name
    async def read(name): return stored[name]
    monkeypatch.setattr(search_trace, "write_bytes", write)
    monkeypatch.setattr(search_trace, "read_bytes", read)
    info = await search_trace.persist(**{**source, "prefix": prefix, "replicas": search_trace.MAX_REPLICAS})
    metadata, files = await search_trace.recover(info)
    assert metadata["trace"]["replicas"] == 128
    assert len(files) == 131


def test_guard_detects_tampered_native_binary_and_missing_notices(tmp_path):
    spec = importlib.util.spec_from_file_location("trace_build_guard", ROOT / "scripts/build_vina_trace.py")
    guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)
    folder = tmp_path / "tools/vina"; folder.mkdir(parents=True)
    (folder / "vina.exe").write_bytes(b"reference")
    (folder / "vina_trace.exe").write_bytes(b"instrumented")
    (folder / "LICENSE.txt").write_bytes(b"notice")
    info = dict(schema="moldesign.vina-trace/1", binary="vina_trace.exe", upstream_commit=guard.COMMIT,
                reference_binary_sha256=search_trace.sha(b"reference"), binary_sha256=search_trace.sha(b"instrumented"),
                licenses={"LICENSE.txt":search_trace.sha(b"notice")},static_dependencies=[{"name":"test"}])
    manifest=folder/"vina-trace-manifest.json";manifest.write_text(json.dumps(info))
    assert guard.check(tmp_path,sources=False)==[]
    (folder / "vina_trace.exe").write_bytes(b"altered")
    assert "SHA-256 mismatch" in guard.check(tmp_path,sources=False)[0]
    (folder / "vina_trace.exe").write_bytes(b"instrumented")
    info["licenses"]={};manifest.write_text(json.dumps(info))
    assert "Missing notices" in guard.check(tmp_path,sources=False)[0]
