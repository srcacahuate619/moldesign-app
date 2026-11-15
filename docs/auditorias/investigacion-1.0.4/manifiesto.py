"""Genera o comprueba el manifiesto de la entrega y de sus entradas locales."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "77aeb73775fd334a24bbe5e3e7382dd2d456379e"
EXPERIMENTS = "scripts/artifacts_science"
NUEVOS = ("DEC-104-D03-R1", "DEC-104-D04-CHEMBL", "DEC-104-D05-PROLIF", "DEC-104-D06-8HFI", "DEC-104-D08-REPLAY")
ENTRADAS = [
    "backend/data/anti_dianas_bowes44.json",
    "curated_targets.json",
    "docs/auditorias/metales_junto_al_sitio_2026-10-11.json",
    "docs/auditorias/convencion-plddt-boltz-chai-2026-11-15/manifiesto.json",
    "scripts/colab_plddt/analisis_plddt.py",
    f"{EXPERIMENTS}/CAL-8HFI-01/entrada/protocolo.json",
    f"{EXPERIMENTS}/REC-11/per_complex.jsonl",
    f"{EXPERIMENTS}/MET-01-R1-ION-DEL-SITIO/per_complex.jsonl",
    f"{EXPERIMENTS}/SUP-04-EXHAUSTIVIDAD-8T69/metrics.json",
    f"{EXPERIMENTS}/SUP-04-EXHAUSTIVIDAD-8T69/per_complex.jsonl",
]
PDB_IDS = ("5IKR", "5VA1", "6LQA", "7KWE", "7SRQ", "8HFI", "8WE8", "8ZYQ", "9EQG")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--generar", action="store_true")
    mode.add_argument("--comprobar", action="store_true")
    args = parser.parse_args()
    manifest = HERE / "manifiesto.json"
    files = {}
    for path in HERE.rglob("*"):
        if path.is_file() and path != manifest and "__pycache__" not in path.parts:
            files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())
    for experiment in NUEVOS:
        for path in (ROOT / EXPERIMENTS / experiment).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                files[path.relative_to(ROOT).as_posix()] = sha(path.read_bytes())

    git_inputs = {}
    for path in ENTRADAS:
        git_bytes = subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)
        if (ROOT / path).read_bytes().replace(b"\r\n", b"\n") != git_bytes.replace(b"\r\n", b"\n"):
            raise ValueError(f"Entrada modificada respecto de {BASE}: {path}")
        git_inputs[path] = sha(git_bytes)

    branch = {
        f"{rev}:{path}": sha(subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT))
        for rev, path in (
            ("fd2189bd", "scripts/amina_pka_01/conjunto.json"),
            ("665a473b", "scripts/amina_pka_01/resultados.json"),
            ("665a473b", "docs/auditorias/AMINA-PKA-01.md"),
        )
    }
    pdbs = {
        pdb: {
            "origen": f"https://doi.org/10.2210/pdb{pdb}/pdb",
            "sha256_pdb_gz_local": sha((ROOT / "data" / "targets" / f"{pdb}.pdb.gz").read_bytes()),
        }
        for pdb in PDB_IDS
    }
    payload = {
        "base_producto": BASE,
        "consulta_web_fechas_locales": ["2026-11-14", "2026-11-15"],
        "archivos_entrega_sha256": files,
        "entradas_revision_base_sha256_blobs_git": git_inputs,
        "entradas_amina_pka_01_sha256_blobs_git": branch,
        "depositos_pdb_cc0_1_0": pdbs,
    }
    if args.generar:
        manifest.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    elif json.loads(manifest.read_text(encoding="utf-8")) != payload:
        raise SystemExit("Difieren las entradas o los archivos de entrega")
    print(f"SHA-256 comprobados o registrados: {len(files) + len(git_inputs) + len(branch) + len(pdbs)}")


if __name__ == "__main__":
    main()
