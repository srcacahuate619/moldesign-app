"""Conteos de pruebas generados, no escritos a mano.

Por qué existe. Los expedientes de cierre citan cifras («backend `1145
passed`») como evidencia. Esas cifras se copiaban a mano y envejecían solas: el
expediente de MolChat afirmaba `1145 passed` mientras el intérprete que el
producto **distribuye** —`python-embed/python.exe`— daba `1107 passed, 3
skipped`. Ninguna de las dos era falsa; faltaba decir con cuál se midió.

La diferencia no era ruido: 36 pruebas del contrato del dossier hacen
`pytest.importorskip("pypdf")`, y `pypdf` no está en el runtime embebido ni
estaba en CI. El contrato del PDF no se verificaba en ninguno de los dos sitios,
y el número redondo lo tapaba.

Este script hace dos cosas:

* `--json` / sin argumentos: cuenta las pruebas recolectadas y ejecutadas,
  declarando el intérprete, y escribe `docs/api/test-counts.json`.
* `--check`: falla si alguna suite **dejó de recolectar** respecto a lo
  registrado. Una suite que desaparece del conteo no rompe ninguna prueba —
  simplemente deja de haber pruebas—, que es el fallo más silencioso posible en
  una batería de gates.

Uso:
    python scripts/report_test_counts.py --write
    python scripts/report_test_counts.py --check
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRO = ROOT / "docs" / "api" / "test-counts.json"

#: Suites que se cuentan. Cada una con el comando que la ejecuta.
SUITES = {
    "backend": {
        "cwd": ROOT / "backend",
        "collect": [sys.executable, "-m", "pytest", "tests", "-q", "--co",
                    "-p", "no:cacheprovider"],
    },
}

_RESUMEN = re.compile(r"(\d+)\s+tests? collected", re.IGNORECASE)
_POR_ARCHIVO = re.compile(r"^(tests[/\\][\w./\\-]+\.py)::", re.MULTILINE)


def _recolectar(nombre: str) -> dict:
    suite = SUITES[nombre]
    proceso = subprocess.run(
        suite["collect"],
        cwd=suite["cwd"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    salida = proceso.stdout + proceso.stderr
    if proceso.returncode not in (0, 5):
        raise SystemExit(
            f"la recolección de '{nombre}' falló (exit {proceso.returncode}):\n"
            + salida[-2000:]
        )

    por_archivo: dict[str, int] = {}
    for ruta in _POR_ARCHIVO.findall(salida):
        clave = ruta.replace("\\", "/")
        por_archivo[clave] = por_archivo.get(clave, 0) + 1

    total = sum(por_archivo.values())
    declarado = _RESUMEN.search(salida)
    if declarado and int(declarado.group(1)) != total:
        # El resumen de pytest manda: si no coincide con el recuento por
        # archivo es que el parseo se quedó corto, y un conteo silenciosamente
        # bajo es exactamente lo que este script existe para impedir.
        raise SystemExit(
            f"recuento inconsistente en '{nombre}': pytest declara "
            f"{declarado.group(1)} y el desglose suma {total}"
        )

    return {"total": total, "por_archivo": dict(sorted(por_archivo.items()))}


def _instantanea() -> dict:
    return {
        "interprete": {
            "ejecutable": str(Path(sys.executable).name),
            "version": platform.python_version(),
            "plataforma": platform.system(),
        },
        "suites": {nombre: _recolectar(nombre) for nombre in SUITES},
    }


def _escribir(datos: dict) -> None:
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    REGISTRO.write_text(
        json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Generado: {REGISTRO.relative_to(ROOT)}")
    for nombre, suite in datos["suites"].items():
        print(f"  {nombre}: {suite['total']} pruebas recolectadas")


def _comprobar(datos: dict) -> int:
    if not REGISTRO.exists():
        print(
            "No hay conteo registrado. Ejecuta "
            "`python scripts/report_test_counts.py --write`.",
            file=sys.stderr,
        )
        return 1

    registrado = json.loads(REGISTRO.read_text(encoding="utf-8"))
    problemas: list[str] = []

    for nombre, suite in datos["suites"].items():
        antes = registrado.get("suites", {}).get(nombre, {}).get("por_archivo", {})
        ahora = suite["por_archivo"]

        for archivo, cuantas in sorted(antes.items()):
            actuales = ahora.get(archivo, 0)
            if actuales == 0:
                problemas.append(
                    f"{nombre}: '{archivo}' recolectaba {cuantas} pruebas y ahora "
                    "no recolecta ninguna — ¿un `importorskip` sin su dependencia, "
                    "o un error de importación?"
                )
            elif actuales < cuantas:
                problemas.append(
                    f"{nombre}: '{archivo}' bajó de {cuantas} a {actuales} pruebas"
                )

    if problemas:
        print("Suites que dejaron de recolectar lo que tenían:", file=sys.stderr)
        for linea in problemas:
            print(f" - {linea}", file=sys.stderr)
        print(
            "\nSi la bajada es intencional (una prueba retirada), regenera con "
            "`--write` y explica el porqué en el commit.",
            file=sys.stderr,
        )
        return 1

    total = sum(s["total"] for s in datos["suites"].values())
    esperado = sum(
        s["total"] for s in registrado.get("suites", {}).values()
    )
    print(
        f"Conteo verificado: {total} pruebas recolectadas "
        f"(registrado: {esperado}) con {datos['interprete']['ejecutable']} "
        f"{datos['interprete']['version']}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    grupo = parser.add_mutually_exclusive_group()
    grupo.add_argument("--write", action="store_true", help="registrar el conteo actual")
    grupo.add_argument(
        "--check",
        action="store_true",
        help="fallar si alguna suite dejó de recolectar sus pruebas",
    )
    args = parser.parse_args()

    datos = _instantanea()

    if args.check:
        return _comprobar(datos)

    if args.write:
        _escribir(datos)
        return 0

    print(json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
