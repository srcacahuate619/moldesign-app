"""
deploy-hf.py — Crea repo en HF, sube manifest + ESMFold model.
Uso: python scripts/deploy-hf.py --token hf_...
"""

import argparse
import json
import os
import sys
from pathlib import Path

from huggingface_hub import HfApi, create_repo, upload_file

ROOT = Path(__file__).resolve().parent.parent
TOKEN = None

def step(msg):
    print(f"\n>>> {msg}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True)
    parser.add_argument("--repo", default="moldesign/moldesign-models")
    args = parser.parse_args()

    global TOKEN
    TOKEN = args.token
    REPO = args.repo
    VERSION = "v1.0.0"

    api = HfApi(token=TOKEN)

    # 1. Create repo
    step(f"Creando/verificando repo {REPO}...")
    try:
        url = create_repo(REPO, repo_type="model", private=False, exist_ok=True, token=TOKEN)
        print(f"  Repo listo: {url}")
    except Exception as e:
        print(f"  Error creando repo: {e}")
        return

    # 2. Upload launcher-manifest.json
    step("Subiendo launcher-manifest.json...")
    manifest_path = ROOT / "launcher-manifest.json"
    try:
        url = upload_file(
            path_or_fileobj=str(manifest_path),
            path_in_repo=f"{VERSION}/launcher-manifest.json",
            repo_id=REPO,
            token=TOKEN,
        )
        print(f"  OK: {url}")
    except Exception as e:
        print(f"  Error subiendo manifest: {e}")
        return

    # 3. Upload ESMFold model (7.86 GB)
    esmfold_path = ROOT.parent / "moldesign-app" / "esmfold" / "models" / "pytorch_model.bin"
    if not esmfold_path.exists():
        esmfold_path = ROOT / "frontend" / "src-tauri" / "resources" / "esmfold" / "models" / "pytorch_model.bin"

    if esmfold_path.exists():
        size_gb = esmfold_path.stat().st_size / (1024**3)
        step(f"Subiendo pytorch_model.bin ({size_gb:.2f} GB)... puede tomar varios minutos")
        try:
            url = upload_file(
                path_or_fileobj=str(esmfold_path),
                path_in_repo=f"{VERSION}/esmfold/models/pytorch_model.bin",
                repo_id=REPO,
                token=TOKEN,
            )
            print(f"  OK: {url}")
        except Exception as e:
            print(f"  Error subiendo ESMFold model: {e}")
            return
    else:
        print("  WARN: pytorch_model.bin no encontrado, se omite")

    # 4. Upload manifest also at root (for easy access)
    step("Subiendo manifest a root...")
    try:
        url = upload_file(
            path_or_fileobj=str(manifest_path),
            path_in_repo="launcher-manifest.json",
            repo_id=REPO,
            token=TOKEN,
        )
        print(f"  OK: {url}")
    except Exception as e:
        print(f"  Error subiendo manifest root: {e}")

    print(f"\n{'='*60}")
    print(f"Todo listo! Repo: https://huggingface.co/{REPO}")
    print(f"Manifest: https://huggingface.co/{REPO}/resolve/main/{VERSION}/launcher-manifest.json")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()
