"""Registra y verifica la huella de los artefactos de la investigación D-04."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    protocol = digest(HERE / "PROTOCOLO.md")
    assert protocol == (HERE / "PROTOCOLO.sha256").read_text().split()[0]
    output = HERE / "manifiesto.json"
    files = sorted(path for path in HERE.iterdir() if path.is_file() and path != output)
    reference = ROOT / "scripts/artifacts_science/DEC-104-D04-CHEMBL/per_complex.jsonl"
    controls_path = "backend/tests/test_especie_en_revision.py"
    controls_lf = (ROOT / controls_path).read_bytes().replace(b"\r\n", b"\n")
    measures = json.loads((HERE / "medidas.json").read_bytes())
    sources = sorted({row["url"] for row in measures["fuentes"].values()})
    data = {
        "fecha_local": "2026-11-15",
        "base": "ffddd7e92d60d2ec0f8c9ecb8879c3388de3ffd5",
        "toolchain": {"python": "3.11.9", "rdkit": "2025.09.6", "dimorphite-dl": "2.0.2"},
        "protocolo_sha256": protocol,
        "archivos_sha256": {path.name: digest(path) for path in files},
        "referencias_locales_sha256": {
            reference.relative_to(ROOT).as_posix(): digest(reference),
            "docs/auditorias/investigacion-1.0.4/medir_d04.py": digest(HERE.parent / "investigacion-1.0.4/medir_d04.py"),
        },
        "referencias_locales_lf_sha256": {controls_path: hashlib.sha256(controls_lf).hexdigest()},
        "sdf_fuente": {
            "url": "https://github.com/czodrowskilab/Machine-learning-meets-pKa",
            "nombre": "chembl25.sdf",
            "sha256": "d727e142e729b1f47b27bf5fc695b3accd98d3bdfb3335b330190139c1990ad6",
            "licencia_declarada_por_el_derivado": "CC BY 4.0",
            "licencia_del_ChEMBL_subyacente": "CC BY-SA 3.0",
        },
        "fuentes_de_pKa_consultadas": sources,
        "procedencia_de_literatura": "Consulta del 15 de noviembre de 2026, con DOI, URL y localizador en el CSV. Los textos fuente no se redistribuyen. El hash corresponde a la extracción local, no a la página.",
    }
    if options.check:
        if json.loads(output.read_bytes()) != data:
            raise SystemExit("El manifiesto difiere de los archivos o del conjunto de referencia")
        print(f"Verificados {len(files)} artefactos y 3 referencias locales.")
    else:
        output.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
