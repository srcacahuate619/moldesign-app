r"""ABS-TR-01-VALIDEZ-R1: la misma validez de Preparación, con la regla de metales en dos niveles (2026-10-24).

Reutiliza `scripts/abs_tr_01/abs_tr_01.py` tal cual —es un activo sellado de ABS-TR-01-VALIDEZ y no se edita— y sólo cambia
dónde escribe: `scripts/artifacts_science/ABS-TR-01-VALIDEZ-R1/`. La entrada (referencia de los revisores, sistemas, CCD y
protocolo) se copia byte a byte de la sellada; el arnés comprueba sus hashes antes de evaluar.
Registro previo: D:\moldesign-audits\ABS_TR_01_R1\REGISTRO_PREVIO.md.

    python-embed\python.exe scripts\abs_tr_01_r1\abs_tr_01_r1.py preparar
    python-embed\python.exe scripts\abs_tr_01_r1\abs_tr_01_r1.py ejecutar --shard 1 --shards 2
    python-embed\python.exe scripts\abs_tr_01_r1\abs_tr_01_r1.py analizar
"""
from __future__ import annotations

import importlib.util
import shutil
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("abs_tr_01", AQUI.parent / "abs_tr_01" / "abs_tr_01.py")
abs_tr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(abs_tr)

ORIGEN = abs_tr.RAIZ / "scripts" / "artifacts_science" / "ABS-TR-01-VALIDEZ" / "entrada"
abs_tr.EXP = abs_tr.RAIZ / "scripts" / "artifacts_science" / "ABS-TR-01-VALIDEZ-R1"
abs_tr.ENTRADA = abs_tr.EXP / "entrada"
abs_tr.TRABAJO = abs_tr.EXP / "_work"


def preparar() -> int:
    """Copia la entrada sellada sin tocarla; se niega si ya hay una distinta."""
    for origen in sorted(ORIGEN.rglob("*")):
        if origen.is_dir():
            continue
        destino = abs_tr.ENTRADA / origen.relative_to(ORIGEN)
        if destino.exists():
            if destino.read_bytes() != origen.read_bytes():
                raise SystemExit(f"{destino} existe y difiere de la entrada sellada")
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origen, destino)
    print(f"entrada copiada de {ORIGEN}")
    return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["preparar"]:
        raise SystemExit(preparar())
    raise SystemExit(abs_tr.main())
