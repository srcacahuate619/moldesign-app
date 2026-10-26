"""Build the audited Apache-2.0 Vina sources; never run the private Molcy binary."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "third_party/vina_trace"
DEST = ROOT / "tools/vina"
COMMIT = "8eb40404f4f45608acb3b01427587ac049f27c1f"
NOTICES = (("gcc-libs", "COPYING3", "GPL-3.0.txt"),
           ("gcc-libs", "COPYING.RUNTIME", "GCC-exception-3.1.txt"),
           ("gcc-libs", "COPYING.LIB", "LGPL-2.1.txt"),
           ("gcc-libs", "README", "gcc-runtime.txt"),
           ("libwinpthread", "COPYING", "winpthreads.txt"),
           ("boost", "LICENSE", "Boost-1.0.txt"),
           ("crt", "COPYING", "MinGW-CRT.txt"),
           ("crt", "COPYING.MinGW-w64-runtime.txt", "MinGW-runtime.txt"),
           ("crt", "COPYING.MinGW-w64.txt", "MinGW-w64.txt"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root=ROOT, *, sources=True):
    folder = root / "tools/vina"
    try:
        info = json.loads((folder / "vina-trace-manifest.json").read_text(encoding="utf-8"))
        if info.get("schema") != "moldesign.vina-trace/1" or info.get("binary") != "vina_trace.exe" or info.get("upstream_commit") != COMMIT:
            return ["Invalid Vina trace manifest"]
        if not info.get("licenses") or not info.get("static_dependencies"):
            return ["Missing notices for Vina's statically linked dependencies"]
        for name, key in (("vina.exe", "reference_binary_sha256"), ("vina_trace.exe", "binary_sha256")):
            if digest(folder / name) != info[key]:
                return [f"Vina SHA-256 mismatch: {name}"]
        for name, expected in info.get("licenses", {}).items():
            if not (folder / name).resolve().is_relative_to(folder.resolve()) or digest(folder / name) != expected:
                return [f"Vina license mismatch: {name}"]
        if sources:
            source = root / "third_party/vina_trace"
            actual = {p.relative_to(source).as_posix(): digest(p) for p in source.rglob("*")
                      if p.is_file() and p.suffix != ".tar"}
            if actual != info["source_files"]:
                return ["Vina trace source hashes mismatch; rebuild before packaging"]
    except (OSError, KeyError, ValueError) as exc:
        return [f"Vina trace missing or invalid: {type(exc).__name__}"]
    return []


def build(compiler: Path):
    build_dir = ROOT / ".tmp-vina-trace/build"
    build_dir.mkdir(parents=True, exist_ok=True)
    notices = DEST / "trace-licenses"
    notices.mkdir(exist_ok=True)
    for directory, name, target in NOTICES:
        (notices / target).write_bytes((compiler.parent.parent / "share/licenses" / directory / name).read_bytes())
    (notices / "Apache-2.0.txt").write_bytes((SOURCE / "LICENSE").read_bytes())
    files = sorted((SOURCE / "src/lib").glob("*.cpp")) + [SOURCE / "src/main/main.cpp"]
    # Only two compiler processes; no shell, no makefile commands, all outputs in the workspace.
    def run(args):
        env = dict(os.environ)
        env["PATH"] = str(compiler.parent) + os.pathsep + env.get("PATH", "")
        result = subprocess.run([str(compiler), *args], cwd=build_dir, capture_output=True,
                                text=True, timeout=240, creationflags=0x08000000, env=env)
        if result.returncode:
            raise RuntimeError(f"compiler exit={result.returncode}: {result.stderr[-12000:]} {result.stdout[-2000:]}")
    flags = ["-O2", "-DNDEBUG", "-std=c++17", "-pthread", "-D_WIN32_WINNT=0x0602",
             "-I" + str(SOURCE / "src/lib"), "-DVERSION=\"v1.2.7-trace\""]
    def compile_one(path):
        obj = build_dir / (path.stem + ".o")
        run([*flags, "-c", str(path), "-o", str(obj)])
        return obj
    with ThreadPoolExecutor(max_workers=2) as pool:
        objects = list(pool.map(compile_one, files))
    binary = DEST / "vina_trace.exe"
    run(["-static", "-pthread", *map(str, objects), "-lboost_thread-mt",
         "-lboost_filesystem-mt", "-lboost_program_options-mt", "-lboost_serialization-mt",
         "-o", str(binary)])
    version = subprocess.run([str(compiler), "--version"], capture_output=True,
                             text=True, check=True, creationflags=0x08000000).stdout.splitlines()[0]
    manifest = {"schema": "moldesign.vina-trace/1", "license": "Apache-2.0",
                "upstream_commit": COMMIT, "upstream_version": "1.2.7", "compiler": version,
                "binary": "vina_trace.exe", "binary_sha256": digest(binary),
                "reference_binary_sha256": digest(DEST / "vina.exe"),
                "capture": "vina_monte_carlo_bfgs_interno",
                "source_files": {p.relative_to(SOURCE).as_posix(): digest(p)
                                 for p in sorted(SOURCE.rglob("*")) if p.is_file() and p.suffix != ".tar"}}
    boost_header = compiler.parent.parent / "include/boost/version.hpp"
    import re
    # BOOST_VERSION (109100) lleva el parche; BOOST_LIB_VERSION ("1_91") no.
    numero = int(re.search(r"#define BOOST_VERSION (\d+)", boost_header.read_text()).group(1))
    boost_version = f"{numero // 100000}.{numero // 100 % 1000}.{numero % 100}"
    manifest["licenses"] = {p.relative_to(DEST).as_posix(): digest(p) for p in sorted(notices.iterdir())}
    manifest["static_dependencies"] = [{"name": "Boost", "version": boost_version, "license": "BSL-1.0"},
        {"name": "GCC runtime", "version": version.split()[-1], "license": "GPL-3.0-or-later WITH GCC-exception-3.1"},
        {"name": "winpthreads/MinGW CRT", "license": "MIT AND BSD-3-Clause AND LicenseRef-MinGW-runtime-notices", "notices": "trace-licenses/"}]
    (DEST / "vina-trace-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Built Vina 1.2.7 trace: {binary.stat().st_size} bytes; {manifest['binary_sha256']}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        problems = check()
        print("\n".join(problems) if problems else "Vina trace sources and binary verified")
        raise SystemExit(bool(problems))
    if not args.compiler:
        parser.error("--compiler is required to build")
    build(args.compiler.resolve(strict=True))
