#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""confirm_denylist.py — auditoría de la cuarentena materializada de FND-05 (ITERACIÓN 4).

La cohorte confirmatoria D-RC-CONFIRM (112 complejos, `candidates.jsonl` con
SHA-256 C12FB947A3B4068F164595D193147ECA9E4EB31C67B85142733E8CBBA7A26959)
queda en cuarentena: sus pids están PROHIBIDOS en cualquier dataset o
experimento futuro del programa. Este script audita listas de pids contra la
denylist y verifica que la cohorte actual sigue siendo la congelada.

Protección de integridad: antes de operar, compara el SHA-256 de
`candidates.jsonl` actual contra el registrado en la denylist; si difiere,
aborta con "cohorte cambiada, denylist obsoleto" (la cuarentena pierde sentido
si la cohorte ya no es la congelada).

Solo biblioteca estándar.

Uso:

  python scripts/confirm_denylist.py --list
  python scripts/confirm_denylist.py --check <archivo_con_pids_uno_por_linea>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

RUTA_DENYLIST_DEFAULT = (
    Path(__file__).resolve().parent
    / "artifacts_science" / "FND-05" / "denylist_pids.json"
)

MENSAJE_OBSOLETA = "cohorte cambiada, denylist obsoleto"


def _sha256_archivo(path: Path) -> str:
    """SHA-256 de un archivo, leyendo por bloques."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for bloque in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest().upper()


def cargar_denylist(path: Path | str = RUTA_DENYLIST_DEFAULT) -> dict:
    """Carga la denylist y verifica el SHA-256 de candidates.jsonl actual.

    El hash esperado se lee del campo `sha256_candidates`; el archivo
    `candidates.jsonl` se busca en el MISMO directorio de la denylist. Si el
    hash actual difiere del registrado, lanza RuntimeError con el mensaje
    "cohorte cambiada, denylist obsoleto".
    """
    path = Path(path)
    with open(path, encoding="utf-8") as fh:
        denylist = json.load(fh)
    esperado = str(denylist.get("sha256_candidates", "")).strip().upper()
    candidatos = path.parent / "candidates.jsonl"
    if not candidatos.is_file():
        raise RuntimeError(MENSAJE_OBSOLETA)
    actual = _sha256_archivo(candidatos)
    if esperado and actual != esperado:
        raise RuntimeError(MENSAJE_OBSOLETA)
    return denylist


def verificar_pids(pids, denylist) -> list:
    """Devuelve los pids denylistados presentes en `pids` (normalizados a minúsculas).

    `pids` puede ser cualquier iterable de cadenas (se normalizan con strip y
    minúsculas). Devuelve la lista de violaciones en orden de aparición.
    """
    prohibidos = {str(p).strip().lower() for p in denylist.get("pids", [])}
    violaciones: list[str] = []
    for p in pids:
        pid = str(p).strip().lower()
        if pid in prohibidos and pid not in violaciones:
            violaciones.append(pid)
    return violaciones


def leer_pids_archivo(path: Path) -> list[str]:
    """Lee pids uno por línea (ignora vacíos y comentarios con #)."""
    pids: list[str] = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for linea in fh:
            pid = linea.split("#", 1)[0].strip()
            if pid:
                pids.append(pid.lower())
    return pids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audita pids contra la cuarentena de la cohorte FND-05.")
    parser.add_argument("--list", action="store_true",
                        help="imprime los 112 pids de la denylist")
    parser.add_argument("--check", metavar="ARCHIVO",
                        help="lee pids uno por línea y reporta violaciones (exit 1 si hay)")
    args = parser.parse_args()

    try:
        denylist = cargar_denylist()
    except (RuntimeError, FileNotFoundError, OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.list:
        for pid in denylist.get("pids", []):
            print(pid)
        return 0

    if args.check:
        pids = leer_pids_archivo(Path(args.check))
        violaciones = verificar_pids(pids, denylist)
        if violaciones:
            print(f"VIOLACIONES: {len(violaciones)} pid(s) denylistado(s) "
                  f"presentes de {len(pids)} revisados:")
            for pid in violaciones:
                print(f"  - {pid}")
            print(f"Regla: {denylist.get('rule', '')}")
            return 1
        print(f"OK: 0 violaciones en {len(pids)} pid(s) revisados")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
