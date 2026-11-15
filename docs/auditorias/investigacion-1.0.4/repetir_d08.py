"""Repite el control D-08 sin escribir en un directorio ya sellado."""
import argparse
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REPLAY = ROOT / "scripts" / "artifacts_science" / "DEC-104-D08-REPLAY"
ORIGINAL = HERE / "sello-inicial-D08"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida-previa-al-sello-final", action="store_true")
    args = parser.parse_args()
    records = json.loads((REPLAY / "entrada" / "codigo.json").read_text(encoding="utf-8"))
    for path, expected in records["archivos"].items():
        contents = (ROOT / path).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(contents).hexdigest() != expected:
            raise ValueError(f"No coincide con la base fijada: {path}")
    source = REPLAY / "entrada" / "medir_d08.py"
    spec = importlib.util.spec_from_file_location("medir_d08", source)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "backend"))
    spec.loader.exec_module(module)
    names = ("metrics.json", "per_complex.jsonl")
    with tempfile.TemporaryDirectory(prefix="dec-104-d08-") as tmp:
        module.ROOT = ROOT
        module.EXPERIMENTO = Path(tmp)
        module.main()
        for name in names:
            actual = (Path(tmp) / name).read_bytes()
            if actual.replace(b"\r\n", b"\n") != (ORIGINAL / name).read_bytes().replace(b"\r\n", b"\n"):
                raise ValueError(f"El resultado difiere del sello inicial: {name}")
            if args.salida_previa_al_sello_final:
                proc = json.loads((REPLAY / "procedencia.json").read_text(encoding="utf-8"))
                if proc["salidas"]:
                    raise SystemExit("La réplica ya se cerró")
                (REPLAY / name).write_bytes(actual)
            else:
                if actual.replace(b"\r\n", b"\n") != (REPLAY / name).read_bytes().replace(b"\r\n", b"\n"):
                    raise ValueError(f"El resultado difiere de la réplica archivada: {name}")


if __name__ == "__main__":
    main()
