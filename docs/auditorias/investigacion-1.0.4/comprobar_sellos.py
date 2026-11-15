"""Ejecuta el verificador base en los experimentos que se citan en esta entrega."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts"))

import validar_sellos

EXPERIMENTS = (
    "CAL-8HFI-01", "CAL-D-01-R4-2-VMAT2-8T69", "DEC-104-D03-R1", "DEC-104-D04-CHEMBL",
    "DEC-104-D05-PROLIF", "DEC-104-D06-8HFI", "DEC-104-D08-REPLAY",
    "FEP-09-R1", "MET-01-R1-ION-DEL-SITIO", "MET-02-R1-SEMILLA",
    "REC-11", "SUP-02-TOTAL-SCORE", "SUP-04-EXHAUSTIVIDAD-8T69", "SUP-05-CORTES-DEL-SITIO",
)


class SelectedExperiments:
    def glob(self, pattern):
        if pattern != "*/manifest.json":
            raise ValueError(pattern)
        base = ROOT / "scripts" / "artifacts_science"
        for experiment in EXPERIMENTS:
            manifest = base / experiment / "manifest.json"
            if not manifest.is_file():
                raise FileNotFoundError(manifest)
            yield manifest


if __name__ == "__main__":
    validar_sellos.ARTEFACTOS = SelectedExperiments()
    if "--solo-hashes" in sys.argv[1:]:
        totals, details = validar_sellos.revisar()
        print(dict(totals))
        print(dict(details["fallos"]))
        sys.exit(bool(details["fallos"]))
    sys.exit(validar_sellos.main())
