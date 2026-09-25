"""Reconstruir AD 7D a partir del pool Fase A, sin tocar el holdout.

Ejemplo:
 python rescoring/scripts/build_applicability_domain.py --csv <pool.csv> --index <INDEX_faseA>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from applicability_domain import AD_DESCRIPTORS, ApplicabilityDomainChecker
from model_manifest import sha256_file


def build(csv_path: Path, index_path: Path, artifacts_dir: Path) -> dict:
    split_path = artifacts_dir / "split_config.json"
    manifest_path = artifacts_dir / "model-manifest.json"
    split = json.loads(split_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != ["pdb_id", *AD_DESCRIPTORS]:
            raise ValueError("Columnas del CSV no coinciden con el contrato AD 7D")
        rows = list(reader)
    ids = [row["pdb_id"].lower() for row in rows]
    holdout = [item.lower() for item in split["frozen_test_set"]]
    index_ids = [line.split()[0].lower() for line in index_path.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.startswith("#")]
    if (len(ids) != 537 or len(set(ids)) != len(ids) or len(holdout) != 328
            or len(set(holdout)) != len(holdout) or len(index_ids) != 865
            or len(set(index_ids)) != len(index_ids)
            or set(ids) != set(index_ids) - set(holdout)
            or set(ids) & set(holdout)):
        raise ValueError("CSV, índice Fase A y holdout no forman la partición 537/328")
    rows.sort(key=lambda row: row["pdb_id"].lower())
    X = np.asarray([[float(row[name]) for name in AD_DESCRIPTORS] for row in rows], dtype=float)
    if not np.isfinite(X).all():
        raise ValueError("CSV contiene NaN o infinito")
    for key in ("model_a_universal", "classifier_binder"):
        entry = manifest["models"][key]
        if sha256_file(artifacts_dir / entry["file"]) != entry["sha256"]:
            raise ValueError(f"Modelo {key} no coincide con el manifiesto sellado")
    artifact = ApplicabilityDomainChecker.build_from_training_data(X, AD_DESCRIPTORS)
    artifact.update({
        "artifact_version": 2,
        "space": "physicochemical_7d_phase_a_pool",
        "source_csv_sha256": sha256_file(csv_path),
        "source_index_sha256": sha256_file(index_path),
        "split_config_sha256": sha256_file(split_path),
        "training_ids_sha256": hashlib.sha256(("\n".join(sorted(ids)) + "\n").encode()).hexdigest(),
        "holdout_ids_sha256": hashlib.sha256(("\n".join(sorted(holdout)) + "\n").encode()).hexdigest(),
        "model_a_sha256": manifest["models"]["model_a_universal"]["sha256"],
        "classifier_sha256": manifest["models"]["classifier_binder"]["sha256"],
        "holdout_excluded": len(holdout),
    })
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--index", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, default=ROOT / "artifacts")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    result = build(args.csv, args.index, args.artifacts)
    data = (json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output = args.artifacts / "applicability_domain.json"
    if args.check:
        if output.read_bytes() != data:
            raise ValueError("AD no coincide con el CSV y los modelos declarados")
        print("AD verificado:", sha256_file(output))
    else:
        output.write_bytes(data)
        print("AD escrito:", sha256_file(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
