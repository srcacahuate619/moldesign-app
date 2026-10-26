"""Puertas locales de Molcy: sin build, red, instalación ni videos completos.

Ejemplo (PowerShell):
  & D:/moldesign-build/python-embed/python.exe scripts/verificar_molcy.py \
      --node C:/nvm4w/nodejs/node.exe --motor E:/proyect3d-worktrees/molcy \
      --salida D:/moldesign-build/dist/molcy-devops-20260929

La salida queda en una subcarpeta nueva UUID con logs e informe JSON. Código 1
si falla una puerta, 2 si faltan dependencias existentes. No descarga paquetes.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import secrets
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]


def python_test(path: Path, arguments: list[str]) -> list[str]:
    bootstrap = f"import sys;sys.path.insert(0,{str(path)!r});import pytest;raise SystemExit(pytest.main({arguments!r}))"
    return [sys.executable, "-c", bootstrap]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", type=Path, required=True)
    parser.add_argument("--motor", type=Path, required=True)
    parser.add_argument("--salida", type=Path, required=True)
    args = parser.parse_args()
    if not args.node.is_absolute() or not args.node.is_file(): parser.error("--node requiere un ejecutable existente y absoluto")
    if not args.motor.is_absolute() or not (args.motor / "scripts/pruebas").is_dir(): parser.error("--motor requiere una carpeta Molcy existente y absoluta")
    if not args.salida.is_absolute(): parser.error("--salida requiere una carpeta absoluta")
    frontend = ROOT / "frontend"
    if not (frontend / "node_modules/vitest/vitest.mjs").is_file(): parser.error("Faltan las dependencias frontend existentes")
    output = args.salida / ("verificacion-" + uuid.uuid4().hex)
    output.mkdir(parents=True, exist_ok=False)
    env = {**os.environ, "LOCAL_DATA_DIR": str(output / "datos"), "MOLDESIGN_TESTING": "1",
           "SECRET_KEY": secrets.token_hex(32), "PYTHONUTF8": "1",
           "PATH": str(args.node.parent) + os.pathsep + os.environ.get("PATH", "")}
    test_files = [str(path.relative_to(ROOT / "backend")) for path in sorted((ROOT / "backend/tests").glob("test_molcy_*.py"))]
    gates = [
        ("backend-molcy", ROOT / "backend", python_test(ROOT / "backend", test_files + ["-q", "-p", "no:cacheprovider"])),
        ("frontend-molcy", frontend, [str(args.node), "node_modules/vitest/vitest.mjs", "run", "app/molcy", "components/molcy", "lib/__tests__/molcy.test.ts", "lib/__tests__/idiomasCompletos.test.ts", "lib/__tests__/interfazSinTextoFijo.test.ts"]),
        ("typescript", frontend, [str(args.node), "node_modules/typescript/bin/tsc", "--noEmit", "--incremental", "false"]),
        ("eslint-molcy", frontend, [str(args.node), "node_modules/eslint/bin/eslint.js", "app/molcy", "components/molcy", "lib/molcy.ts", "context/traducciones/molcy.ts"]),
        ("motor-molcy", args.motor, python_test(args.motor / "scripts", ["scripts/pruebas", "-q", "-p", "no:cacheprovider"])),
        ("csp-medios-locales", frontend, [str(args.node), "scripts/check-prod-csp.js"]),
        ("contrato-api", ROOT, [sys.executable, str(ROOT / "scripts/generate_openapi_contract.py"), "--check"]),
    ]
    report = {"schema": "molcy.verificacion/1", "fecha_utc": datetime.now(timezone.utc).isoformat(),
              "python": sys.version, "plataforma": platform.platform(),
              "scope": "molcy", "build": False, "renders_completos": 0, "puertas": []}
    for name, cwd, command in gates:
        started = time.monotonic()
        log = output / f"{name}.log"
        print(f"Verificando {name}…", flush=True)
        try:
            with log.open("w", encoding="utf-8") as stream:
                process = subprocess.run(command, cwd=cwd, env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=600)
            code = process.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            with log.open("a", encoding="utf-8") as stream: stream.write(f"\n{type(exc).__name__}: {exc}\n")
            code = 1
        report["puertas"].append({"nombre": name, "codigo": code, "segundos": round(time.monotonic()-started, 3), "log": str(log)})
        temporary = output / ".informe.tmp"
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, output / "informe.json")
    success = all(gate["codigo"] == 0 for gate in report["puertas"])
    print(f"Resultado: {'correcto' if success else 'fallo'}. Informe: {output / 'informe.json'}")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
