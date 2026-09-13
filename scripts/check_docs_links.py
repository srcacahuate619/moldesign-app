"""Detecta enlaces Markdown locales rotos en la documentación.

Uso:
    python scripts/check_docs_links.py --report
    python scripts/check_docs_links.py --check

No consulta la red: sólo valida rutas relativas a cada archivo Markdown. Los
links HTTP(S), mailto, anchors internos y referencias externas se omiten a
propósito; un link checker HTTP pertenece a una campaña separada porque no
debe volver frágil el build desktop por disponibilidad de terceros.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LINK = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)]+)\)")
EXTERNAL_PREFIXES = ("#", "http://", "https://", "mailto:", "tel:", "data:")


def _local_target(raw_target: str) -> str | None:
    target = raw_target.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")].strip()
    else:
        # Markdown admite un título opcional: (file.md "título").
        target = target.split(maxsplit=1)[0]

    if not target or target.lower().startswith(EXTERNAL_PREFIXES):
        return None
    return target.split("#", maxsplit=1)[0].split("?", maxsplit=1)[0]


def find_broken_links() -> list[tuple[Path, int, str]]:
    broken: list[tuple[Path, int, str]] = []
    for source in sorted(DOCS.rglob("*.md")):
        for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), start=1):
            # Un SMILES como ``C[C@H](CS)`` no es un enlace Markdown.
            prose = re.sub(r"`[^`]*`", "", line)
            for raw_target in LINK.findall(prose):
                target = _local_target(raw_target)
                if target is None:
                    continue
                if not (source.parent / target).resolve().exists():
                    broken.append((source, line_number, raw_target))
    return broken


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--report", action="store_true", help="informa sin fallar")
    mode.add_argument("--check", action="store_true", help="falla si hay enlaces locales rotos")
    args = parser.parse_args()

    broken = find_broken_links()
    if broken:
        print(f"Enlaces locales rotos: {len(broken)}")
        for source, line_number, target in broken:
            print(f" - {source.relative_to(ROOT)}:{line_number} -> {target}")
        return 1 if args.check else 0

    print("Documentación: todos los enlaces locales son válidos")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
