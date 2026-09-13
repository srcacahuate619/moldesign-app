# scripts/bundle_full_offline.py
import shutil
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
RESOURCES = ROOT / "frontend" / "src-tauri" / "resources"

# 1. Run the standard staging process
print(">>> Running standard resource staging...")
import subprocess
result = subprocess.run([sys.executable, str(ROOT / "scripts" / "bundle_helper.py")], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print("Staging failed:", result.stderr)
    sys.exit(1)

# 2. Stage Qwen LLM weights (1.12 GB)
QWEN_SRC = ROOT / "models" / "llm" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
QWEN_DST = RESOURCES / "models" / "llm" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
if QWEN_SRC.exists():
    print(f">>> Copying Qwen LLM model weights (~1.1 GB)...")
    QWEN_DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(QWEN_SRC, QWEN_DST)
    print("  [OK] LLM weights copied.")
else:
    print(f"  WARNING: Qwen weights not found at {QWEN_SRC}")

# 3. Stage ESMFold weights (8.44 GB)
ESMFOLD_WEIGHTS_SRC = Path("D:/moldesign-app/esmfold/models/pytorch_model.bin")
ESMFOLD_WEIGHTS_DST = RESOURCES / "esmfold" / "models" / "pytorch_model.bin"
if ESMFOLD_WEIGHTS_SRC.exists():
    print(f">>> Copying ESMFold PyTorch weights (~8.4 GB)...")
    ESMFOLD_WEIGHTS_DST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(ESMFOLD_WEIGHTS_SRC, ESMFOLD_WEIGHTS_DST)
    print("  [OK] ESMFold weights copied.")
else:
    print(f"  WARNING: ESMFold weights not found at {ESMFOLD_WEIGHTS_SRC}")

# 4. Stage Target Library PDBs (270 MB)
TARGET_LIB_SRC = ROOT / "data" / "target_library"
TARGET_LIB_DST = RESOURCES / "data" / "target_library"
if TARGET_LIB_SRC.exists():
    print(f">>> Copying Target Library PDBs (~270 MB)...")
    shutil.copytree(TARGET_LIB_SRC, TARGET_LIB_DST, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True)
    print("  [OK] Target Library PDBs copied.")
else:
    print(f"  WARNING: Target Library not found at {TARGET_LIB_SRC}")

total = sum(1 for _ in RESOURCES.rglob("*") if _.is_file())
size_gb = sum(f.stat().st_size for f in RESOURCES.rglob("*") if f.is_file()) / (1024 * 1024 * 1024)
print(f"\n>>> Full Offline Bundle Staged: {total} files, {size_gb:.2f} GB")
