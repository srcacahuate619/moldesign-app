"""
generate-manifest.py — Genera launcher-manifest.json para la distribución de modelos.
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Qwen models point to OFFICIAL HuggingFace repos — no need to self-host
# ESMFold model is self-hosted in moldesign/moldesign-models
MODELS = [
    {
        "id": "llm-qwen05",
        "name": "Qwen 2.5 0.5B Instruct (Q4_K_M)",
        "filename": "models/llm/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "category": "llm",
        "required_for": ["molchat"],
        "gpu_required": False,
        "official_hf": True,
        "url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
    },
    {
        "id": "llm-qwen15",
        "name": "Qwen 2.5 1.5B Instruct (Q4_K_M)",
        "filename": "models/llm/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "category": "llm",
        "required_for": [],
        "gpu_required": False,
        "official_hf": True,
        "url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
    },
    {
        "id": "esmfold-weights",
        "name": "ESMFold v1 Weights",
        "filename": "esmfold/models/pytorch_model.bin",
        "category": "esmfold",
        "required_for": ["evaluation"],
        "gpu_required": True,
        "official_hf": False,
        "url": None,  # filled dynamically based on --hf-user/--hf-repo
    },
]


def sha256(path: Path) -> str:
    sha = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


def build_manifest(version: str = "1.0.0", hf_user: str = "moldesign", hf_repo: str = "moldesign-models"):
    hf_base = f"https://huggingface.co/{hf_user}/{hf_repo}/resolve/main/v{version}"

    models_out = []
    total_bytes = 0

    for m in MODELS:
        if m["official_hf"]:
            # Qwen models: use official HF URL, skip SHA-256 (we trust official)
            models_out.append({
                "id": m["id"],
                "name": m["name"],
                "filename": m["filename"],
                "category": m["category"],
                "size_bytes": 0,  # unknown, frontend will show from Content-Length
                "sha256": "",     # skip verification for official models
                "urls": [m["url"]],
                "required_for": m["required_for"],
                "gpu_required": m["gpu_required"],
            })
        else:
            # ESMFold: compute local SHA-256 and use our HF repo
            local = ROOT.parent / "moldesign-app" / "esmfold" / "models" / "pytorch_model.bin"
            alt = ROOT / "frontend" / "src-tauri" / "resources" / "esmfold" / "models" / "pytorch_model.bin"
            path = local if local.exists() else alt

            if not path.exists():
                print(f"  [WARN] {m['id']}: no encontrado, se omite")
                continue

            print(f"  Calculando SHA-256: {m['filename']}...")
            h = sha256(path)
            size = path.stat().st_size
            total_bytes += size

            models_out.append({
                "id": m["id"],
                "name": m["name"],
                "filename": m["filename"],
                "category": m["category"],
                "size_bytes": size,
                "sha256": h,
                "urls": [f"{hf_base}/esmfold/models/pytorch_model.bin"],
                "required_for": m["required_for"],
                "gpu_required": m["gpu_required"],
            })

    manifest = {
        "version": version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_bytes": total_bytes,
        "models": models_out,
    }

    out_path = ROOT / "launcher-manifest.json"
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\n  Manifest: {out_path}")
    print(f"  Version: {version}")
    print(f"  Models: {len(models_out)}")
    print(f"  Self-hosted: {total_bytes / (1024**3):.2f} GB")
    print(f"  Remote (official HF): Qwen models")

    print(f"\n  Upload ESMFold model to:")
    print(f"    {hf_base}/esmfold/models/pytorch_model.bin")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--hf-user", default="srcacahuate")
    parser.add_argument("--hf-repo", default="moldesign-models")
    args = parser.parse_args()
    build_manifest(args.version, args.hf_user, args.hf_repo)


if __name__ == "__main__":
    main()
