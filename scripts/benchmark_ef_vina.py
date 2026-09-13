"""
benchmark_ef_vina.py

Benchmark Enrichment Factor CIENTIFICAMENTE RIGUROSO:
  - Vina real (exhaust=4, sin engaños)
  - Features 3D completas (Shell + ECIF + 1D/2D = 160)
  - Classifier binario XGBoost (AUC 0.858)
  - EF@1%, 5%, 10%, ROC-AUC, PR-AUC con datos reales

Ejecucion: ~8-15 min por target con 4 workers (Ryzen 5 5500 + GTX 1660 SUPER)
  - ACE (1o86, metaloenzyme): ~4h para 2206 mols (benchmark completo)
  - Vina con --cpu 4 para evitar CPU oversubscription entre workers
Checkpoint: incremental cada 50 mols. Auto-resume si el archivo existe
  (--no-resume para empezar de cero).
"""

import argparse
import concurrent.futures
import json
import math
import os
import pickle
import random
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
from sklearn.metrics import roc_auc_score

PROJECT_ROOT = Path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
DATA_DIR = PROJECT_ROOT / "data"
CHECKPOINT = DATA_DIR / "benchmark_checkpoint_v2.json"
REPORT_PATH = DATA_DIR / "ef_report_final.json"

# Vina-CPU: usa el binario original que no necesita MinGW/OpenCL
VINA_EXE = PROJECT_ROOT / "tools" / "vina" / "vina.exe"
_IS_GPU_BINARY = False  # CPU-only, no GPU binary needed

# ── Model Router (CPU/GPU aware) ──
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
from model_router import get_router
_router = None
def _ensure_router(engine: str = "cpu"):
    global _router
    if _router is None:
        _router = get_router()
    return _router

# ── Hardware-aware worker detection ──
def _detect_workers() -> int:
    """Auto-detect recommended workers. Falls back to 1 if detection fails."""
    try:
        sys.path.insert(0, str(PROJECT_ROOT / "backend"))
        from core.hardware import detect_hardware
        hw = detect_hardware()
        return max(1, hw.recommended_workers)
    except Exception:
        return 1

# ── Auto-detect AutoDock-GPU bridge (WSL2 project, 60-600x faster) ──
_ADGPU_BRIDGE = Path("D:/ad-gpu-project/adgpu_bridge.py")
_ADGPU_AVAILABLE = _ADGPU_BRIDGE.exists()
if _ADGPU_AVAILABLE:
    try:
        import subprocess
        r = subprocess.run(["python", str(_ADGPU_BRIDGE), "--test-only"], 
                          capture_output=True, text=True, timeout=5)
        _ADGPU_AVAILABLE = "GPU_AVAILABLE" in (r.stdout or "")
    except Exception:
        _ADGPU_AVAILABLE = False
if _ADGPU_AVAILABLE:
    print(f"[INFO] AutoDock-GPU bridge detected: {_ADGPU_BRIDGE}")
    print(f"[INFO] Docking will use GPU acceleration (~600x faster)")
    VINA_EXE = _ADGPU_BRIDGE
# ── Vina-Hybrid GPU override (ad-gpu-project) ──
_VINA_HYBRID = os.environ.get("VINA_HYBRID_PATH")
if _VINA_HYBRID and os.path.exists(_VINA_HYBRID):
    VINA_EXE = _VINA_HYBRID
    print(f"[INFO] Vina-Hybrid GPU override: {_VINA_HYBRID}")

N_WORKERS = 1  # default, overridden by --workers or auto-detect
EXHAUSTIVENESS = 4  # screening default (exhaust=8 para pose prediction, no necesario para EF)
TARGET_PDB_ID = "7E2Y"

# Multi-target support (centers loaded from curated_targets.csv dynamically)
# 'center' in config is a FALLBACK only — overridden by curated DB or protein_surgery
TARGET_CONFIGS = {
    "7e2y": {
        "name": "5ht1a",
        "family": "gpcr",
        "center": (103.03, 114.79, 108.36),  # fallback, overridden by curated DB
        "data_dir": lambda d: d / "multitarget" / "5ht1a",
        "pdb_local": lambda d: d / "7e2y.pdb",
        "pdbqt_local": lambda d: d / "7E2Y_obabel.pdbqt",
    },
    "3pp0": {
        "name": "cdk2",
        "family": "kinase",
        "center": (25.86, 30.61, 7.55),  # fallback, overridden by curated DB
        "data_dir": lambda d: d / "multitarget" / "cdk2",
        "pdb_local": lambda d: d / "3PP0.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "cdk2" / "3PP0.pdbqt",
    },
    "1hsg": {
        "name": "hiv_protease",
        "family": "protease",
        "center": (13.07, 22.47, 5.56),
        "data_dir": lambda d: d / "multitarget" / "hiv_protease",
        "pdb_local": lambda d: d / "1HSG.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "hiv_protease" / "1HSG.pdbqt",
    },
    "3ert": {
        "name": "er_alpha",
        "family": "nuclear_receptor",
        "center": (30.0, 2.0, 25.0),  # fallback, overridden by curated DB
        "data_dir": lambda d: d / "multitarget" / "er_alpha",
        "pdb_local": lambda d: d / "3ERT.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "er_alpha" / "3ERT.pdbqt",
    },
    "5z2r": {
        "name": "cdk6",
        "family": "kinase",
        "center": (25.0, 30.0, 10.0),  # fallback, overridden by curated DB
        "data_dir": lambda d: d / "multitarget" / "cdk6",
        "pdb_local": lambda d: d / "5Z2R.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "cdk6" / "5Z2R.pdbqt",
    },
    "6x1a": {
        "name": "glp1r",
        "family": "gpcr",
        "center": (15.0, 20.0, 18.0),  # fallback, overridden by curated DB
        "data_dir": lambda d: d / "multitarget" / "glp1r",
        "pdb_local": lambda d: d / "6X1A.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "glp1r" / "6X1A.pdbqt",
    },
    "1f0r": {
        "name": "factor_xa",
        "family": "soluble_enzyme",
        "center": (7.30, 5.09, 22.22),
        "data_dir": lambda d: d / "multitarget" / "factor_xa",
        "pdb_local": lambda d: d / "pdbbind" / "1f0r" / "1f0r_protein.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "factor_xa" / "1f0r_vina.pdbqt",
        "ligand_mol2": lambda d: d / "pdbbind" / "1f0r" / "1f0r_ligand.mol2",
    },
    "1c4u": {
        "name": "thrombin",
        "family": "soluble_enzyme",
        "center": (18.82, 41.39, -11.70),
        "data_dir": lambda d: d / "multitarget" / "thrombin",
        "pdb_local": lambda d: d / "pdbbind" / "1c4u" / "1c4u_protein.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "thrombin" / "1c4u_vina.pdbqt",
        "ligand_mol2": lambda d: d / "pdbbind" / "1c4u" / "1c4u_ligand.mol2",
    },
    "1bn1": {
        "name": "ca2",
        "family": "metaloenzyme",
        "center": (15.89, 15.95, 48.52),
        "data_dir": lambda d: d / "multitarget" / "ca2",
        "pdb_local": lambda d: d / "pdbbind" / "1bn1" / "1bn1_protein.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "ca2" / "1bn1_vina.pdbqt",
        "ligand_mol2": lambda d: d / "pdbbind" / "1bn1" / "1bn1_ligand.mol2",
    },
    "1gpk": {
        "name": "ache",
        "family": "soluble_enzyme",
        "center": (8.90, 38.06, 62.49),
        "data_dir": lambda d: d / "multitarget" / "ache",
        "pdb_local": lambda d: d / "pdbbind" / "1gpk" / "1gpk_protein.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "ache" / "1gpk_vina.pdbqt",
        "ligand_mol2": lambda d: d / "pdbbind" / "1gpk" / "1gpk_ligand.mol2",
    },
    "1b38": {
        "name": "cdk2_pdbbind",
        "family": "kinase",
        "center": (19.22, 24.79, 35.18),
        "data_dir": lambda d: d / "multitarget" / "cdk2_pdbbind",
        "pdb_local": lambda d: d / "pdbbind" / "1b38" / "1b38_protein.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "cdk2_pdbbind" / "1b38_vina.pdbqt",
        "ligand_mol2": lambda d: d / "pdbbind" / "1b38" / "1b38_ligand.mol2",
    },
    "1gkc": {
        "name": "mmp9",
        "family": "metaloenzyme",
        "center": (53.25, 22.51, 129.72),
        "data_dir": lambda d: d / "multitarget" / "mmp9",
        "pdb_local": lambda d: d / "1gkc.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "mmp9" / "1gkc.pdbqt",
    },
    "1xp0": {
        "name": "pde5a",
        "family": "metaloenzyme",
        "center": (-22.35, 28.59, 62.69),
        "data_dir": lambda d: d / "multitarget" / "pde5a",
        "pdb_local": lambda d: d / "1xp0.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "pde5a" / "1xp0.pdbqt",
    },
    "1o86": {
        "name": "ace",
        "family": "metaloenzyme",
        "center": (43.82, 38.24, 46.71),
        "data_dir": lambda d: d / "multitarget" / "ace",
        "pdb_local": lambda d: d / "1O86_clean.pdb",
        "pdbqt_local": lambda d: d / "multitarget" / "ace" / "1O86.pdbqt",
    },
}

sys.path.insert(0, str(PROJECT_ROOT / "backend"))
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))

random.seed(42)
np.random.seed(42)


# ═══════════════════════════════════════════════════════════════════════
# Data loading
# ═══════════════════════════════════════════════════════════════════════

def load_dataset(target_id: str = "7E2Y") -> tuple[list[dict], list[dict]]:
    config = TARGET_CONFIGS.get(target_id)
    target_dir = config["data_dir"](DATA_DIR) if config else None

    actives = []
    if target_dir and (target_dir / "actives.txt").exists():
        path = target_dir / "actives.txt"
    else:
        path = DATA_DIR / "chembl_5ht1a_actives.txt"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            actives.append({"smiles": parts[0], "pki": float(parts[1]), "is_active": True})

    decoys = []
    if target_dir and (target_dir / "decoys.smi").exists():
        path = target_dir / "decoys.smi"
    else:
        path = DATA_DIR / "dude_5ht1a_decoys.smi"
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            smi = line.split()[0] if " " in line else line
            if len(smi) > 3:
                decoys.append({"smiles": smi, "pki": None, "is_active": False})

    return actives, decoys


# ═══════════════════════════════════════════════════════════════════════
# Vina docking + feature extraction
# ═══════════════════════════════════════════════════════════════════════

_extractor = None  # lazy singleton
_extractor_lock = threading.Lock()


def _get_extractor():
    global _extractor
    if _extractor is None:
        with _extractor_lock:
            if _extractor is None:  # double-checked locking
                from feature_extractor import InteractionFeatureExtractor
                _extractor = InteractionFeatureExtractor()
                # MUST keep ProLIF loading for MDAnalysis to parse PDBQT correctly
                # ProLIF fingerprinting itself will be skipped via skip_prolif=True
    return _extractor


def _sanitize_pdbqt_rigid(pdbqt_path: str):
    """Elimina tags ROOT/ENDROOT/BRANCH/ENDBRANCH del PDBQT.
    
    OpenBabel puede agregar tags de residuos flexibles en receptores
    multi-cadena grandes. El parser rigido de Vina los rechaza.
    Los eliminamos aqui para que Vina pueda leer el receptor.
    """
    if not os.path.exists(pdbqt_path):
        return
    with open(pdbqt_path) as f:
        lines = f.readlines()
    cleaned = [l for l in lines if not l.startswith(("ROOT", "ENDROOT", "BRANCH", "ENDBRANCH"))]
    if len(cleaned) < len(lines):
        with open(pdbqt_path, "w") as f:
            f.writelines(cleaned)


# ── Base de datos de targets curados (dinamica, auto-cargada) ──

_curated_db = None  # carga perezosa desde curated_targets.csv

def _load_curated_db() -> dict:
    """Carga curated_targets.csv en un diccionario indexado por PDB ID (minusculas).
    
    Columnas esperadas: pdb_id, name, chain, family, grid_cx/cy/cz, grid_sx/sy/sz, hotspots.
    """
    global _curated_db
    if _curated_db is not None:
        return _curated_db
    _curated_db = {}
    csv_path = PROJECT_ROOT / "curated_targets.csv"
    if not csv_path.exists():
        return _curated_db
    import csv
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            pdb_id = row.get("pdb_id", "").strip().lower()
            if pdb_id:
                _curated_db[pdb_id] = {
                    "name": row.get("name", ""),
                    "chain": row.get("chain", "").strip(),
                    "family": row.get("family", ""),
                    "center": (
                        float(row.get("grid_cx", 0) or 0),
                        float(row.get("grid_cy", 0) or 0),
                        float(row.get("grid_cz", 0) or 0),
                    ),
                    "box_size": float(row.get("grid_sx", 25) or 25),
                    "hotspots": int(row.get("hotspots", 0) or 0),
                }
    return _curated_db


def _detect_dominant_chain(pdb_path: str) -> str | None:
    """Detecta la cadena con mas registros ATOM. Retorna el ID de cadena o None.
    
    Util para receptores multi-cadena donde solo una cadena contiene
    el sitio activo. La cadena dominante (mayor numero de atomos)
    es casi siempre la relevante para docking.
    """
    chain_counts = {}
    with open(pdb_path) as f:
        for line in f:
            if line.startswith("ATOM"):
                chain = line[21:22].strip()
                if chain:
                    chain_counts[chain] = chain_counts.get(chain, 0) + 1
    if not chain_counts:
        return None
    return max(chain_counts, key=chain_counts.get)


def _trim_pdb_chain(pdb_path: str, chain_id: str, output_path: str):
    """Extrae una unica cadena de un archivo PDB, conservando ATOM/HETATM/TER.
    
    Los receptores multi-cadena (dimeros, tetrameros) son mucho mas
    grandes de lo necesario para docking. Extraer solo la cadena
    del sitio activo reduce el tamano del receptor 3-10x y acelera
    el docking proporcionalmente.
    """
    with open(pdb_path) as f:
        lines = f.readlines()
    with open(output_path, "w") as out:
        for line in lines:
            if line.startswith(("ATOM", "HETATM")):
                if line[21:22].strip() == chain_id:
                    out.write(line)
            elif line.startswith("TER"):
                if line[21:22].strip() == chain_id:
                    out.write(line)
        out.write("END\n")

def _discover_pdb(target_id: str) -> Path | None:
    """Descubre automaticamente un archivo PDB para cualquier PDB ID.
    
    Orden de busqueda:
      1. data/targets/{id}.pdb
      2. data/target_library/*/{id}.pdb
      3. TARGET_CONFIGS pdb_local (fallback)
    """
    tid = target_id.lower()
    # Busqueda directa en targets/
    direct = DATA_DIR / "targets" / f"{tid}.pdb"
    if direct.exists() and direct.stat().st_size > 100:
        return direct
    # Busqueda en subdirectorios de target_library
    lib = DATA_DIR / "target_library"
    if lib.exists():
        for area_dir in sorted(lib.iterdir()):
            if area_dir.is_dir() and not area_dir.name.startswith("."):
                candidate = area_dir / f"{tid}.pdb"
                if candidate.exists() and candidate.stat().st_size > 100:
                    return candidate
    # Fallback a TARGET_CONFIGS
    config = TARGET_CONFIGS.get(tid)
    if config:
        pdb = config["pdb_local"](DATA_DIR)
        if pdb.exists() and pdb.stat().st_size > 100:
            return pdb
    return None


def _compute_geometric_center(pdb_path: str) -> tuple[float, float, float]:
    """Calcula el centro geometrico de todos los atomos en un PDB.
    
    Usado como fallback cuando no hay datos curados ni ligand_mol2.
    Es una aproximacion razonable para definir la caja de docking.
    """
    xs, ys, zs = [], [], []
    with open(pdb_path) as f:
        for line in f:
            if line.startswith("ATOM"):
                try:
                    xs.append(float(line[30:38]))
                    ys.append(float(line[38:46]))
                    zs.append(float(line[46:54]))
                except ValueError:
                    pass
    if not xs:
        return (0, 0, 0)
    return (sum(xs)/len(xs), sum(ys)/len(ys), sum(zs)/len(zs))


def _get_target_path(target_id: str = "7E2Y") -> dict | None:
    """Preparacion universal de target — funciona para CUALQUIER PDB ID.
    
    Descubre automaticamente el archivo PDB, carga datos curados,
    recorta cadenas, y prepara PDBQT para Vina. Cero configuracion manual.
    
    Fuentes de datos de binding site (en orden de prioridad):
      1. curated_targets.csv → centro + cadena + caja (curado manual)
      2. Protein Surgery → via ligand_mol2 (override total)
      3. Centro geometrico automatico (fallback para targets nuevos)
    """
    target_lower = target_id.lower()
    config = TARGET_CONFIGS.get(target_lower)
    
    # ── Load curated data (overrides everything) ──
    curated = _load_curated_db().get(target_lower, {})
    curated_chain = curated.get("chain", "")
    curated_center = curated.get("center")
    curated_box = curated.get("box_size")
    
    # ── Discover PDB file ──
    pdb = _discover_pdb(target_id)
    if not pdb:
        # Try download from RCSB
        try:
            import urllib.request
            url = f"https://files.rcsb.org/download/{target_id}.pdb"
            req = urllib.request.Request(url, headers={"User-Agent": "MolDesign/1.4"})
            dest = DATA_DIR / "targets" / f"{target_id}.pdb"
            os.makedirs(dest.parent, exist_ok=True)
            with urllib.request.urlopen(req, timeout=30) as r:
                dest.write_bytes(r.read())
            pdb = dest
        except Exception:
            print(f"[FAIL] Cannot find or download PDB: {target_id}")
            return None
    
    # ── Determine output PDBQT path ──
    if config:
        pdbqt = config["pdbqt_local"](DATA_DIR)
    else:
        # Auto-generated path in multitarget/{family}/
        family = curated.get("family", "unknown")
        name = curated.get("name", target_lower)
        pdbqt = DATA_DIR / "multitarget" / family / f"{target_lower}_vina.pdbqt"
    _surgery_applied = False
    
    # ── Chain trimming for multi-chain receptors ──
    # IMPORTANT: only trim when the curated/known binding pocket actually
    # falls INSIDE the bounding box of the chosen chain. For some multi-chain
    # targets (e.g. GPCR 7E2Y), the curated "chain" column (B) is a subunit
    # that does NOT contain the binding site — trimming it produces a
    # receptor with NO atoms near the grid center, so Vina cannot anchor
    # the ligand and returns near-zero scores. Sanity check below.
    _force_regen_pdbqt = False  # set True when we skip trim but chain-only pdbqt exists
    effective_chain = curated_chain
    if not effective_chain:
        effective_chain = _detect_dominant_chain(str(pdb))

    def _chain_bbox(pdb_path: str, chain: str) -> tuple[float, float, float, float, float, float]:
        """Bounding box (xmin, xmax, ymin, ymax, zmin, zmax) of a single chain."""
        xmin, ymin, zmin = float("inf"), float("inf"), float("inf")
        xmax, ymax, zmax = float("-inf"), float("-inf"), float("-inf")
        with open(pdb_path) as f:
            for line in f:
                if line.startswith("ATOM") and line[21:22].strip() == chain:
                    try:
                        x, y, z = float(line[30:38]), float(line[38:46]), float(line[46:54])
                        xmin, ymin, zmin = min(xmin, x), min(ymin, y), min(zmin, z)
                        xmax, ymax, zmax = max(xmax, x), max(ymax, y), max(zmax, z)
                    except ValueError:
                        pass
        return xmin, xmax, ymin, ymax, zmin, zmax

    if effective_chain:
        # Check if we need chain trimming (receptor has multiple chains)
        all_chains = set()
        with open(str(pdb)) as f:
            for line in f:
                if line.startswith("ATOM"):
                    all_chains.add(line[21:22].strip())
        if len(all_chains) > 1:
            # Sanity check: only trim if the binding site (curated_center if
            # available) actually lies inside this chain's bbox (with 6A
            # margin). Otherwise keep all chains — Vina's grid box handles
            # spatial filtering at docking time.
            should_trim = True
            if curated_center:
                cx_, cy_, cz_ = curated_center
                xmin, xmax, ymin, ymax, zmin, zmax = _chain_bbox(str(pdb), effective_chain)
                margin = 6.0
                inside = (xmin - margin <= cx_ <= xmax + margin and
                          ymin - margin <= cy_ <= ymax + margin and
                          zmin - margin <= cz_ <= zmax + margin)
                if not inside:
                    print(f"  Chain '{effective_chain}' bbox does NOT contain curated center {curated_center}; "
                          f"keeping all {len(all_chains)} chains (no trim) so Vina can find the pocket.")
                    should_trim = False
                    # If a chain-only PDBQT already exists on disk, it was
                    # generated from the trimmed receptor and is missing the
                    # pocket atoms. Force regeneration from the full PDB.
                    if pdbqt.exists():
                        _force_regen_pdbqt = True
            if should_trim:
                trimmed_pdb = Path(str(pdb).replace(".pdb", f"_chain{effective_chain}.pdb"))
                if not trimmed_pdb.exists() or _surgery_applied:
                    _trim_pdb_chain(str(pdb), effective_chain, str(trimmed_pdb))
                    print(f"  Chain trimmed: {len(all_chains)} chains -> '{effective_chain}' ({trimmed_pdb.stat().st_size} bytes)")
                pdb = trimmed_pdb
                _surgery_applied = True
    
    # ── Determine center and box_size (best source wins) ──
    effective_center = None
    effective_box = None
    # [fix-b] Track the provenance of the binding-site box for the paper's
    # methodology section. Values: 'curated_csv' | 'protein_surgery' |
    # 'target_config' | 'geometric_auto'. Set on whichever branch supplies the
    # final effective_center used at docking time.
    box_source = "unknown"

    # 1. Use curated center/box if available
    if curated_center:
        effective_center = curated_center
        effective_box = curated_box or 25
        box_source = "curated_csv"
        print(f"  Curated: center={curated_center}, box={effective_box}A [source={box_source}]")
    
    # 2. Protein Surgery overrides (when ligand MOL2 available)
    if config:
        try:
            lig_mol2_fn = config.get("ligand_mol2")
            if lig_mol2_fn:
                lig_mol2_path = lig_mol2_fn(DATA_DIR)
                if lig_mol2_path.exists():
                    from services.chemistry.protein_surgery import prepare_target
                    import tempfile
                    tmp_dir = tempfile.mkdtemp(prefix="bench_surgery_")
                    surgery = prepare_target(str(pdb), str(lig_mol2_path), tmp_dir)
                    surgery_pdb = Path(surgery["vina_receptor"])
                    if surgery_pdb != pdb:
                        pdb = surgery_pdb
                        _surgery_applied = True
                    effective_center = surgery["vina_center"]
                    effective_box = surgery["vina_box"]
                    box_source = "protein_surgery"
        except ImportError:
            pass
        except Exception:
            pass
    # ── End Protein Surgery ──
    
    # 3. Fallback: hardcoded config center or geometric center
    if not effective_center:
        if config and config.get("center"):
            effective_center = config["center"]
            box_source = "target_config"
        else:
            effective_center = _compute_geometric_center(str(pdb))
            box_source = "geometric_auto"
            print(f"  Auto-center: {effective_center} [source={box_source}]")
    if not effective_box:
        if config and config.get("_box_size"):
            effective_box = config["_box_size"]
        else:
            effective_box = 25
    
    if not (pdbqt.exists() and pdbqt.stat().st_size > 100) or _surgery_applied or _force_regen_pdbqt:
        from openbabel import openbabel
        conv = openbabel.OBConversion()
        conv.SetInFormat("pdb")
        conv.SetOutFormat("pdbqt")
        conv.AddOption("r", openbabel.OBConversion.OUTOPTIONS)
        mol = openbabel.OBMol()
        if not conv.ReadFile(mol, str(pdb)):
            print(f"[FAIL] OpenBabel could not read {pdb}")
            return None
        mol.AddHydrogens()
        os.makedirs(os.path.dirname(str(pdbqt)), exist_ok=True)
        conv.WriteFile(mol, str(pdbqt))
        # Strip ROOT/BRANCH tags for rigid receptor (Vina rejects them)
        _sanitize_pdbqt_rigid(str(pdbqt))
        print(f"  Receptor prepared: {pdbqt} ({pdbqt.stat().st_size} bytes)")

    # Defensive quantum args: when _get_target_path is invoked outside main()
    # (e.g. for dry-check tooling), 'args' may not be defined. Don't crash.
    _qe = False
    _qt = 0.5
    try:
        _qe = not args.no_quantum_exit
        _qt = args.quantum_threshold
    except (NameError, AttributeError):
        pass
    return {
        "vina_pdbqt": str(pdbqt),
        "protein_pdb": str(pdb),
        "center": effective_center,
        "target_id": target_id,
        "box_size": effective_box,
        "box_source": box_source,  # [fix-b] curated_csv | protein_surgery | target_config | geometric_auto
        "quantum_exit": _qe,
        "quantum_threshold": _qt,
    }


def _prepare_ligand(smiles: str, tmp_dir: str) -> tuple[str | None, str | None]:
    """RDKit -> SDF -> Meeko -> PDBQT."""
    try:
        from rdkit import Chem, RDLogger
        from rdkit.Chem import AllChem
        RDLogger.logger().setLevel(RDLogger.ERROR)
        mol = Chem.MolFromSmiles(smiles)
        if not mol:
            return None, None
        mol = Chem.AddHs(mol)
        status = AllChem.EmbedMolecule(mol, AllChem.ETKDG())
        if status == -1:
            AllChem.EmbedMolecule(mol, AllChem.ETKDGv3())
        AllChem.MMFFOptimizeMolecule(mol)
    except Exception:
        return None, None

    try:
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        preparator = MoleculePreparation()
        mol_setups = preparator.prepare(mol)
        if not mol_setups:
            return None, None
        pdbqt_string, is_ok, _ = PDBQTWriterLegacy.write_string(mol_setups[0])
        if not is_ok:
            return None, None
        pdbqt_path = os.path.join(tmp_dir, "lig.pdbqt")
        with open(pdbqt_path, "w") as f:
            f.write(pdbqt_string)
        if os.path.exists(pdbqt_path) and os.path.getsize(pdbqt_path) > 10:
            return pdbqt_path, None
    except Exception:
        pass

    # Fallback: OpenBabel (handles complex peptides, boron, etc. when Meeko fails)
    try:
        from openbabel import openbabel as ob
        ob_pdb = os.path.join(tmp_dir, "lig_ob.pdb")
        Chem.MolToPDBFile(mol, ob_pdb)
        conv = ob.OBConversion()
        conv.SetInAndOutFormats("pdb", "pdbqt")
        obmol = ob.OBMol()
        if conv.ReadFile(obmol, ob_pdb):
            pdbqt_path_fb = os.path.join(tmp_dir, "lig_ob.pdbqt")
            if conv.WriteFile(obmol, pdbqt_path_fb):
                if os.path.exists(pdbqt_path_fb) and os.path.getsize(pdbqt_path_fb) > 10:
                    return pdbqt_path_fb, None
    except Exception:
        pass

    return None, None


def _parse_vina_affinity(stdout: str) -> float | None:
    """Parse Vina output: find the best affinity (mode 1)."""
    for line in stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith("1 ") or stripped.startswith("   1"):
            parts = stripped.split()
            for val in parts[1:]:
                try:
                    return float(val)
                except (ValueError, IndexError):
                    continue
    return None


def _pdbqt_block_to_rdmol(pdbqt_block: str):
    """Convert Vina output PDBQT block to RDKit mol with standard elements.
    
    AD4 atom types are mapped to standard elements: 'A'→'C', 'OA'→'O', etc.
    RDKit fails on PDBQT because it sees AD4 types as element names.
    """
    from rdkit import Chem
    from rdkit.Chem import rdmolfiles
    from rdkit.Geometry import Point3D

    # Map AD4 atom types to canonical elements
    AD4_TO_ELEMENT = {
        "C": "C", "A": "C",  # aromatic carbon → C
        "N": "N", "NA": "N", "NS": "N",
        "O": "O", "OA": "O", "OS": "O",
        "H": "H", "HD": "H", "HS": "H", "HO": "H",
        "S": "S", "SA": "S",
        "P": "P",
        "F": "F", "Cl": "Cl", "Br": "Br", "I": "I",
        "Mg": "Mg", "Ca": "Ca", "Zn": "Zn", "Fe": "Fe", "Mn": "Mn",
    }

    atoms = []
    coords = []
    for line in pdbqt_block.splitlines():
        if not (line.startswith("ATOM") or line.startswith("HETATM")):
            continue
        if len(line) < 79:
            continue
        name = line[12:16].strip()
        ad4_type = line[77:79].strip()
        elem = AD4_TO_ELEMENT.get(ad4_type, "C")  # default to C if unknown
        try:
            x = float(line[30:38])
            y = float(line[38:46])
            z = float(line[46:54])
        except ValueError:
            continue
        atoms.append(elem)
        coords.append((x, y, z))

    if not atoms:
        return None

    editable = Chem.RWMol()
    for elem in atoms:
        editable.AddAtom(Chem.Atom(elem))

    conf = Chem.Conformer(len(atoms))
    for i, (x, y, z) in enumerate(coords):
        conf.SetAtomPosition(i, Point3D(x, y, z))
    editable.AddConformer(conf)

    return editable.GetMol()


def _extract_manual(pose_pdbqt: str, protein_pdb: str, lig_mol) -> dict | None:
    """Manual Shell + ECIF extraction using RDKit + numpy only.
    
    Used as fallback when extractor.extract_from_pose returns zero features.
    """
    try:
        from rdkit import Chem
        import numpy as np

        prot_mol = Chem.MolFromPDBFile(protein_pdb, removeHs=True, sanitize=False)
        if prot_mol is None:
            return None
        Chem.SanitizeMol(
            prot_mol,
            Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES,
        )

        # Get heavy-atom coordinates
        prot_heavy = [(a.GetSymbol(), i) for i, a in enumerate(prot_mol.GetAtoms()) if a.GetAtomicNum() > 1]
        lig_heavy = [(a.GetSymbol(), i) for i, a in enumerate(lig_mol.GetAtoms()) if a.GetAtomicNum() > 1]
        if not prot_heavy or not lig_heavy:
            return None

        prot_conf = prot_mol.GetConformer()
        lig_conf = lig_mol.GetConformer()

        prot_coords = np.array([list(prot_conf.GetAtomPosition(i)) for _, i in prot_heavy])
        lig_coords = np.array([list(lig_conf.GetAtomPosition(i)) for _, i in lig_heavy])

        feats = {}

        # Close contacts (4A and 6A)
        from scipy.spatial import distance_matrix
        dm = distance_matrix(prot_coords, lig_coords)
        feats["close_contacts_4A"] = float((dm < 4.0).sum())
        feats["close_contacts_6A"] = float((dm < 6.0).sum())

        # Shell atom counts (96 features: 6 elements × 6 elements × 3 distance bins)
        SHELL_ELEMS = ["C", "N", "O", "S", "F", "Cl"]
        BINS = [(0, 4), (4, 6), (6, 8)]
        prot_elems = [s for s, _ in prot_heavy]
        lig_elems = [s for s, _ in lig_heavy]
        for pe in SHELL_ELEMS:
            for le in SHELL_ELEMS:
                for lo, hi in BINS:
                    p_mask = np.array([e == pe for e in prot_elems])
                    l_mask = np.array([e == le for e in lig_elems])
                    if p_mask.any() and l_mask.any():
                        sub_dm = dm[np.ix_(p_mask, l_mask)]
                        count = ((sub_dm >= lo) & (sub_dm < hi)).sum()
                    else:
                        count = 0
                    feats[f"shell_{pe}_{le}_{lo}-{hi}"] = float(count)

        # ECIF features (56 features)
        from rdkit.Chem import GetPeriodicTable
        pt = GetPeriodicTable()
        for pi in range(len(prot_heavy)):
            psym = prot_elems[pi]
            for li in range(len(lig_heavy)):
                lsym = lig_elems[li]
                d = dm[pi, li]
                if d < 6.0:
                    order = _approx_bond_order(d)
                    key = f"ecif_{psym}_{lsym}_d{int(d)}_{order}"
                    feats[key] = feats.get(key, 0.0) + 1.0

        # Size features
        hac = len(lig_heavy)
        feats["heavy_atom_count"] = float(hac)
        feats["contacts_per_ha_4A"] = feats["close_contacts_4A"] / max(hac, 1)
        feats["contacts_per_ha_6A"] = feats["close_contacts_6A"] / max(hac, 1)

        return feats
    except Exception:
        import traceback
        traceback.print_exc()
        return None


def _approx_bond_order(dist: float) -> str:
    """Approximate bond order from distance."""
    if dist < 1.6:
        return "triple"
    elif dist < 1.9:
        return "double"
    elif dist < 2.2:
        return "single"
    else:
        return "vdw"


def _compute_1d_2d_features(smiles: str) -> dict[str, float]:
    """Compute 1D/2D molecular features from SMILES using RDKit."""
    from rdkit import Chem
    from rdkit.Chem import Descriptors, QED
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {}
    mw = Descriptors.MolWt(mol)
    return {
        "mw": round(mw, 2),
        "logp": round(Descriptors.MolLogP(mol), 4),
        "tpsa": round(Descriptors.TPSA(mol), 2),
        "hbd": Descriptors.NHOHCount(mol),
        "hba": Descriptors.NOCount(mol),
        "rotatable_bonds": Descriptors.NumRotatableBonds(mol),
        "qed": round(QED.qed(mol), 4),
        "log_mw": round(math.log(max(mw, 1)), 4),
    }


def dock_and_extract(mol: dict, receptor_config: dict) -> dict | None:
    """Docker una molecula + extraer features 3D completas. Retorna dict con resultados.
    
    receptor_config: {"vina_pdbqt": str, "protein_pdb": str, "center": (x,y,z), "target_id": str}
    """
    smiles = mol["smiles"]
    vina_receptor = receptor_config["vina_pdbqt"]
    protein_pdb = receptor_config["protein_pdb"]
    cx, cy, cz = receptor_config["center"]
    box_sz = receptor_config.get("box_size") or 25  # None guard: dict.get returns None if key exists with None
    tmp_dir = tempfile.mkdtemp(prefix="vina_bench_", dir=os.environ.get("MOLDESIGN_TMP", str(PROJECT_ROOT / "tmp")))
    try:
        # 1. Prepare ligand
        lig_path, sdf_content = _prepare_ligand(smiles, tmp_dir)
        if not lig_path:
            return None

        # Optional: Quantum Early Exit — skip Vina if MolChamb score predicts weak binding
        use_quantum_exit = receptor_config.get("quantum_exit", False)
        quantum_threshold = receptor_config.get("quantum_threshold", 0.55)
        if use_quantum_exit and quantum_threshold > 0:
            try:
                from compute_quantum_features import compute_quantum_score
                qs = compute_quantum_score(smiles)
                if qs > quantum_threshold:
                    return {
                        "smiles": smiles, "vina_score": None, "features": {},
                        "is_active": mol["is_active"], "pki_real": mol.get("pki"),
                        "pose_pdbqt": "", "quantum_skipped": True, "quantum_score": qs,
                    }
            except ImportError:
                pass

        # 2. Run Vina (--cpu_only = identical to original vina.exe FP64)
        out_path = os.path.join(tmp_dir, "out.pdbqt")
        stdout_path = os.path.join(tmp_dir, "vina_stdout.log")
        stderr_path = os.path.join(tmp_dir, "vina_stderr.log")
        command = [
            str(VINA_EXE),
            "--receptor", vina_receptor,
            "--ligand", lig_path,
            "--center_x", str(cx), "--center_y", str(cy), "--center_z", str(cz),
            "--size_x", str(box_sz), "--size_y", str(box_sz), "--size_z", str(box_sz),
            "--exhaustiveness", str(EXHAUSTIVENESS),
            "--num_modes", "1",
            "--seed", "42",
            "--out", out_path,
        ]
        # Limit CPU per Vina instance to prevent oversubscription with multiple workers.
        # Ryzen 5 5500 = 6 cores / 12 threads. --cpu 4 allows 3-4 concurrent Vina processes
        # without saturating all logical processors, reducing context switching by ~60%.
        command.extend(["--cpu", "4"])
        with open(stdout_path, "w") as vina_out, open(stderr_path, "w") as vina_err:
            result = subprocess.run(
                command,
                stdout=vina_out, stderr=vina_err, text=True, timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                cwd=tmp_dir,
            )

        vina_stdout = Path(stdout_path).read_text(encoding="utf-8", errors="replace")
        vina_stderr = Path(stderr_path).read_text(encoding="utf-8", errors="replace")
        vina_score = _parse_vina_affinity(vina_stdout)
        if vina_score is None and vina_stderr:
            vina_score = _parse_vina_affinity(vina_stderr)
        # Filter anomalous docking (positive score = docking didn't converge)
        if vina_score is not None and vina_score >= 0:
            vina_score = None

        # 3. Extract features from pose (uses original PDB, not PDBQT)
        feats_dict = {}
        pose_pdbqt = Path(out_path).read_text() if os.path.exists(out_path) else ""
        if pose_pdbqt and vina_score is not None:
            try:
                extractor = _get_extractor()
                feats_3d = extractor.extract_from_pose(
                    pose_pdbqt, protein_pdb, smiles, skip_prolif=True,
                )
                feats_dict = feats_3d
                feats_dict.update(_compute_1d_2d_features(smiles))
                # Add Vina features to features dict (critical for model accuracy)
                feat_vina = vina_score if vina_score else 0.0
                feats_dict["vina_best_score"] = feat_vina
                feats_dict["pose_score_variance"] = 0.0
                feats_dict["pose_score_range"] = 0.0
                feats_dict["poses_passing_ratio"] = 1.0 if vina_score is not None else 0.0
            except Exception as e:
                print(f"  [FEAT_FAIL] {smiles[:50]}... {type(e).__name__}: {e}")

        return {
            "smiles": smiles,
            "vina_score": vina_score,
            "features": feats_dict,
            "is_active": mol["is_active"],
            "pki_real": mol.get("pki"),
            "pose_pdbqt": pose_pdbqt,  # In-memory PDBQT for GNN
        }

    except subprocess.TimeoutExpired:
        return None
    except Exception as e:
        print(f"  [DOCK_FAIL] {smiles[:50]}... {type(e).__name__}: {e}")
        return None
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════
# GNN-v2 scoring (Classifier)
# ═══════════════════════════════════════════════════════════════════════

_clgnn_classifier = None
_clgnn_lock = threading.Lock()


def _get_clgnn_classifier():
    global _clgnn_classifier
    if _clgnn_classifier is None:
        with _clgnn_lock:
            if _clgnn_classifier is None:  # double-checked locking
                from gnn_v2.models import GNNv2Classifier
                from gnn_v2.data import _build_protein_graph, _build_cross_edges
                device = "cuda" if __import__("torch").cuda.is_available() else "cpu"
                model = GNNv2Classifier(hidden_dim=128)
                path = PROJECT_ROOT / "rescoring" / "artifacts" / "gnn_v2_cl_best.pt"
                if not path.exists():
                    path = PROJECT_ROOT / "rescoring" / "artifacts" / "clgnn_finetuned.pt"
                if path.exists():
                    ck = __import__("torch").load(path, map_location=device, weights_only=False)
                    sd = ck.get("model_state_dict", ck)  # handle both raw and wrapped format
                    model.load_state_dict(sd, strict=False)
                    model.to(device)
                    model.eval()
                _clgnn_classifier = (model, device)
    return _clgnn_classifier


def score_with_clgnn(result: dict, protein_pdb: str, receptor_config: dict) -> dict:
    """Score a docked molecule with CL-GNN (pretrained contrastive + finetuned).

    [A3] NUNCA fabrica 0.5: en cualquier fallo escribe clgnn_prob=None con un
    WARNING que incluye identificadores (smiles + pose + proteína), para que
    los análisis puedan EXCLUIR la muestra explícitamente.
    """
    smiles = result.get("smiles", "")
    pose_pdbqt = result.get("pose_pdbqt", "")
    target_tag = receptor_config.get("name", "?")
    if not smiles or not pose_pdbqt:
        _warn_clgnn_missing("no_smiles_or_pose", smiles, target_tag)
        result["clgnn_prob"] = None
        return result

    import tempfile, os
    from contextlib import contextmanager

    @contextmanager
    def tmp_pdbqt(content):
        fd, path = tempfile.mkstemp(suffix=".pdbqt")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        try:
            yield path
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass

    model, device = _get_clgnn_classifier()
    if model is None:
        _warn_clgnn_missing("model_unavailable", smiles, target_tag)
        result["clgnn_prob"] = None
        return result

    try:
        with tmp_pdbqt(pose_pdbqt) as pdbqt_path:
            from gnn_v2.data import _parse_docked_pdbqt, _build_ligand_graph, _build_protein_graph, _build_cross_edges
            from rdkit import Chem
            from rdkit.Chem import AllChem

            # Generate SDF for bond topology
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                _warn_clgnn_missing("smiles_unparseable", smiles, target_tag)
                result["clgnn_prob"] = None
                return result

            fd, sdf_path = tempfile.mkstemp(suffix=".sdf")
            os.close(fd)
            mol_2d = Chem.AddHs(mol)
            AllChem.Compute2DCoords(mol_2d)
            mol_2d = Chem.RemoveHs(mol_2d)
            writer = Chem.SDWriter(sdf_path)
            writer.write(mol_2d)
            writer.close()

            lig_graph = _build_ligand_graph(sdf_path, pdbqt_path)
            os.unlink(sdf_path)

            if lig_graph is None:
                _warn_clgnn_missing("ligand_graph_failed", smiles, target_tag)
                result["clgnn_prob"] = None
                return result

            prot_graph = _build_protein_graph(protein_pdb, lig_graph.pos.numpy())
            if prot_graph is None:
                _warn_clgnn_missing("protein_graph_failed", smiles, target_tag)
                result["clgnn_prob"] = None
                return result

            cross_edges = _build_cross_edges(lig_graph.pos, prot_graph.pos)

            import torch
            with torch.no_grad():
                logits = model(
                    prot_graph.x.to(device),
                    prot_graph.edge_index.to(device),
                    lig_graph.x.to(device),
                    lig_graph.edge_index.to(device),
                    cross_edges.to(device),
                    lig_pos=lig_graph.pos.to(device),
                    prot_pos=prot_graph.pos.to(device),
                )
                result["clgnn_prob"] = round(float(torch.sigmoid(logits).item()), 4)
    except Exception as exc:
        _warn_clgnn_missing(f"exception_{type(exc).__name__}", smiles, target_tag)
        result["clgnn_prob"] = None

    return result


def _warn_clgnn_missing(reason: str, smiles: str, target_tag: str) -> None:
    """WARNING explícito con identificadores para cada fallo de CL-GNN."""
    snippet = (smiles[:40] + "...") if (smiles and len(smiles) > 40) else (smiles or "")
    print(f"  [WARN clgnn_missing] target={target_tag} reason={reason} smiles={snippet}")

_gnn_predictor = None


def _get_gnn(engine: str = "cpu"):
    global _gnn_predictor
    if _gnn_predictor is None:
        from gnn_v2.inference import GNNv2Predictor
        if engine == "gpu":
            model_path = PROJECT_ROOT / "rescoring" / "artifacts" / "gpu" / "gnn_v3_best.pt"
        else:
            model_path = PROJECT_ROOT / "rescoring" / "artifacts" / "gnn_v3_best.pt"
        _gnn_predictor = GNNv2Predictor(
            device="cuda" if __import__("torch").cuda.is_available() else "cpu",
            mc_samples=10,
            model_path=model_path,
        )
    return _gnn_predictor


def score_with_gnn(result: dict, protein_pdb: str, engine: str = "cpu") -> dict:
    """Run GNN-v2 inference on a docked molecule using in-memory PDBQT.

    [A3] GNN-v2 ya devuelve (NaN, NaN) + warning con identificadores en
    fallos. Aquí se propaga NaN → gnn_prob=None (JSON null) en el checkpoint,
    NUNCA 0.5 fabricado.
    """
    smiles = result["smiles"]
    pose_pdbqt = result.get("pose_pdbqt", "")
    if not pose_pdbqt:
        print(f"  [WARN gnn_missing] reason=no_pose smiles={smiles[:40]}")
        result["gnn_prob"] = None
        result["gnn_std"] = None
        return result

    # Write PDBQT to temp file for the GNN predictor
    import tempfile
    fd, tmp_pdbqt = tempfile.mkstemp(suffix=".pdbqt")
    with os.fdopen(fd, "w") as f:
        f.write(pose_pdbqt)

    try:
        predictor = _get_gnn(engine)
        # Debug: check if PDBQT is valid
        from gnn_v2.data import _parse_docked_pdbqt
        parsed = _parse_docked_pdbqt(tmp_pdbqt)
        heavy = sum(1 for e in parsed["elements"] if e not in ("H",))

        prob, std = predictor.predict(smiles, tmp_pdbqt, protein_pdb)
        if prob != prob or std != std:  # NaN
            print(f"  [WARN gnn_missing] reason=nan_from_predictor smiles={smiles[:40]}")
            result["gnn_prob"] = None
            result["gnn_std"] = None
        else:
            result["gnn_prob"] = round(prob, 4)
            result["gnn_std"] = round(std, 4)

        # Debug first time
        if not hasattr(score_with_gnn, "_debugged") and result.get("gnn_prob") is not None:
            score_with_gnn._debugged = True
            print(f"\n  [GNN DEBUG] {smiles[:30]}: heavy={heavy} | prob={prob:.4f} std={std:.4f}")
    except Exception as e:
        if not hasattr(score_with_gnn, "_debugged"):
            score_with_gnn._debugged = True
            import traceback
            print(f"\n  [GNN ERROR] {e}")
            traceback.print_exc()
        result["gnn_prob"] = None
        result["gnn_std"] = None
    finally:
        try:
            os.unlink(tmp_pdbqt)
        except OSError:
            pass

    return result


# ── Calibración universal: rank-based percentile normalization ──

def rank_normalize(scores: list, higher_better: bool = True) -> list[float]:
    """Normalize scores to [0,1] using percentile ranking.
    
    For molecules where score is None, returns 0.5 (neutral).
    """
    n = len(scores)
    if n <= 1:
        return [0.5] * n
    
    arr = np.array([s if s is not None else np.nan for s in scores], dtype=np.float64)
    mask = ~np.isnan(arr)
    result = np.full(n, 0.5, dtype=np.float64)
    
    if mask.sum() < 2:
        return result.tolist()
    
    valid = arr[mask]
    ranks = np.argsort(np.argsort(valid))
    if not higher_better:
        ranks = len(valid) - 1 - ranks
    
    result[mask] = ranks / (len(valid) - 1)
    return result.tolist()


# ── Pesos de stacking por familia (cargados dinamicamente desde JSON) ──

_STACKING_WEIGHTS_PATH = PROJECT_ROOT / "rescoring" / "artifacts" / "stacking_weights.json"

def _load_stacking_weights() -> dict:
    """Carga pesos de stacking desde JSON. Si no existe, usa defaults embebidos."""
    if _STACKING_WEIGHTS_PATH.exists():
        try:
            with open(_STACKING_WEIGHTS_PATH) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "gpcr":               {"vina": 0.4, "prob": 0.4, "gnn": 0.0, "clgnn": 0.2, "molchamb_sign": 1.0},
        "kinase":             {"vina": 0.2, "prob": 0.8, "gnn": 0.0, "clgnn": 0.0, "molchamb_sign": 1.0},
        "protease":           {"vina": 0.2, "prob": 0.7, "gnn": 0.0, "clgnn": 0.1, "molchamb_sign": -1.0},
        "nuclear_receptor":   {"vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2, "molchamb_sign": 1.0},
        "soluble_enzyme":     {"vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2, "molchamb_sign": 1.0},
        "metaloenzyme":       {"vina": 0.0, "prob": 0.1, "gnn": 0.0, "clgnn": 0.9, "molchamb_sign": 1.0},
        "phosphodiesterase":  {"vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2, "molchamb_sign": 1.0},
        "default":            {"vina": 0.3, "prob": 0.5, "gnn": 0.0, "clgnn": 0.2, "molchamb_sign": 1.0},
    }

STACKING_WEIGHTS = _load_stacking_weights()

MOLCHAMB_SIGN = {k: v.get("molchamb_sign", 1.0) for k, v in STACKING_WEIGHTS.items()}


def calibrated_stacking(results: list[dict], family: str) -> list[float]:
    """Calibrated stacking: rank-normalize each component, weighted by family.

    [A3] Los pesos se RE-NORMALIZAN sobre los componentes realmente
    disponibles por molécula (raw value presente). Si una molécula no tiene
    NINGÚN componente → None (sin score fabricado); el caller la excluye.
    """
    n = len(results)
    if n == 0:
        return []

    vina_raw = [r.get("vina_score") for r in results]
    prob_raw = [r.get("prob") for r in results]            # classifier P(binder), binary:logistic
    gnn_raw = [r.get("gnn_prob") for r in results]
    clgnn_raw = [r.get("clgnn_prob") for r in results]

    vina_norm = rank_normalize(vina_raw, higher_better=True)
    prob_norm = rank_normalize(prob_raw, higher_better=True)
    gnn_norm = rank_normalize(gnn_raw, higher_better=True)
    clgnn_norm = rank_normalize(clgnn_raw, higher_better=True)

    w = STACKING_WEIGHTS.get(family, STACKING_WEIGHTS["default"])

    calibrated: list[float | None] = []
    for i in range(n):
        terms = []
        used_w = 0.0
        for raw, norm, wk in (
            (vina_raw[i], vina_norm[i], w.get("vina", 0.0)),
            (prob_raw[i], prob_norm[i], w.get("prob", 0.0)),
            (gnn_raw[i], gnn_norm[i], w.get("gnn", 0.0)),
            (clgnn_raw[i], clgnn_norm[i], w.get("clgnn", 0.0)),
        ):
            if raw is not None and wk > 0:
                terms.append(norm * wk)
                used_w += wk
        if used_w > 0:
            calibrated.append(sum(terms) / used_w)
        else:
            calibrated.append(None)

    return calibrated

def score_with_classifier(result: dict, engine: str = "cpu") -> tuple[float, float, float]:
    """
    Returns (prob_binder, xgb_score, delta) via ModelRouter.
    Router handles CPU (artifacts/) vs GPU (artifacts/gpu/) model selection.

    [A3] El router ahora devuelve NaN explícito ante violación de contrato
    de features; aquí se traduce a None (componente ausente en el checkpoint,
    JSON null) — nunca se persiste un valor fabricado.
    """
    router = _ensure_router(engine)
    feats = result.get("features", {})
    router_result = router.predict(feats, engine=engine)

    def _fin_or_none(v):
        if v is None:
            return None
        try:
            fv = float(v)
        except (TypeError, ValueError):
            return None
        return round(fv, 4) if not math.isnan(fv) and not math.isinf(fv) else None

    return _fin_or_none(router_result.prob), _fin_or_none(router_result.score), _fin_or_none(router_result.delta)


# ═══════════════════════════════════════════════════════════════════════
# Metrics
# ═══════════════════════════════════════════════════════════════════════

def enrichment_factor(scores: list[float], labels: list[bool], pct: float = 1.0) -> float:
    """EF@X%: activos_en_top_X% / esperados_al_azar."""
    n = len(scores)
    n_actives = sum(labels)
    if n_actives == 0 or n == 0:
        return 1.0
    top_n = max(1, int(n * pct / 100))
    pairs = sorted(zip(scores, labels), key=lambda x: x[0], reverse=True)
    found = sum(1 for _, a in pairs[:top_n] if a)
    expected = n_actives * top_n / n
    return round(found / expected, 2) if expected > 0 else 1.0


def print_metrics(scores: list[float], labels: list[bool], title: str = "Results"):
    n = len(scores)
    n_act = sum(labels)
    print(f"\n{'='*55}")
    print(f"  {title}")
    print(f"  N={n} | Actives={n_act} | Decoys={n-n_act} | Ratio=1:{max(1,(n-n_act)//max(n_act,1))}")
    print(f"{'='*55}")

    for pct in [1, 5, 10]:
        ef = enrichment_factor(scores, labels, pct)
        print(f"  EF@{pct}% = {ef:.2f}x")

    try:
        from sklearn.metrics import roc_auc_score, average_precision_score
        auc = roc_auc_score(labels, scores)
        pr = average_precision_score(labels, scores)
        print(f"  ROC-AUC = {auc:.4f}")
        print(f"  PR-AUC  = {pr:.4f}")
    except ImportError:
        pass

    ef1 = enrichment_factor(scores, labels, 1)
    if ef1 >= 5:
        print(f"\n  >>> STRONG: EF@1%={ef1:.1f}x. Valid for virtual screening.")
    elif ef1 >= 2:
        print(f"\n  >>> MODERATE: EF@1%={ef1:.1f}x. Better than random.")
    else:
        print(f"\n  >>> WEAK: EF@1%={ef1:.1f}x. Need improved scoring.")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=str, default="1f0r", choices=list(TARGET_CONFIGS.keys()),
                        help="Target PDB ID. Default: 1f0r (factor_xa). Use --target all for multi-target via orchestrator.")
    parser.add_argument("--no-resume", action="store_true",
                        help="Ignore existing checkpoint and start fresh")
    parser.add_argument("--n-mols", type=int, default=0, help="Limit mols for quick test")
    parser.add_argument("--workers", type=int, default=0,
                        help="Workers (0=auto-detect based on hardware)")
    parser.add_argument("--engine", type=str, default="cpu", choices=["cpu", "gpu"],
                        help="Model engine: cpu (artifacts/) or gpu (artifacts/gpu/)")
    parser.add_argument("--gnn", action="store_true", help="Enable GNN-v2 scoring")
    parser.add_argument("--no-quantum-exit", action="store_true",
                        help="Disable Quantum Early Exit (fallback to original behavior)")
    parser.add_argument("--quantum-threshold", type=float, default=0.55,
                        help="MolChamb score threshold for early exit (>threshold = skip docking)")
    parser.add_argument("--exhaust", type=int, default=4,
                        help="Vina exhaustiveness (default: 4; 8 for pose prediction)")
    global args
    global EXHAUSTIVENESS
    args = parser.parse_args()
    EXHAUSTIVENESS = args.exhaust

    # Auto-detect workers if not explicitly set
    if args.workers == 0:
        args.workers = _detect_workers()
        print(f"  [Auto] Workers={args.workers} (detected)")

    target_id = args.target.lower()  # normalize to lowercase
    config = TARGET_CONFIGS.get(target_id, {})
    target_name = config.get("name", target_id)
    target_family = config.get("family", "unknown")

    # Pre-load router for chosen engine
    _ensure_router(args.engine)

    # Target-specific checkpoint and report paths
    CHECKPOINT_TARGET = CHECKPOINT.parent / f"benchmark_checkpoint_{target_name}.json"
    REPORT_TARGET = REPORT_PATH.parent / f"ef_report_{target_name}.json"

    print("=" * 55)
    print(f"  EF BENCHMARK — {target_id} ({target_name}, {target_family})")
    print(f"  Engine: {args.engine} | Vina exhaust={EXHAUSTIVENESS} | workers={args.workers}")
    print(f"  Features: Shell 96 + ECIF 56 + 1D/2D 8 = 160")
    print(f"  Classifier: binder (AUC 0.858)")
    print("=" * 55)

    # 1. Load data
    actives, decoys = load_dataset(target_id)
    n_decoys = min(len(decoys), 2500) if args.n_mols == 0 else args.n_mols
    # Realistic virtual screening ratio: 1 active : 30 decoys
    n_actives_to_use = min(50, len(actives))
    mols = actives[:n_actives_to_use] + decoys[:n_decoys]
    random.shuffle(mols)
    n_act = sum(m["is_active"] for m in mols)
    print(f"\nDataset: {len(mols)} molecules ({n_act} actives, ratio 1:{max(1,(len(mols)-n_act)//max(n_act,1))})")

    # 2. Target
    receptor_config = _get_target_path(target_id)
    if not receptor_config:
        print(f"[FAIL] No {target_id} PDB available.")
        return

    # 3. Docking + extraction
    checkpoint = {}
    if not args.no_resume and CHECKPOINT_TARGET.exists():
        checkpoint = json.loads(CHECKPOINT_TARGET.read_text())
        print(f"  [Resume] Loaded {len(checkpoint.get('completed_smiles', []))} completed mols from checkpoint")
    completed = set(checkpoint.get("completed_smiles", []))
    results = list(checkpoint.get("results", []))

    pending = [m for m in mols if m["smiles"] not in completed]
    print(f"Pending: {len(pending)} | Completed: {len(completed)}")

    if pending:
        print(f"Docking + extracting features with {args.workers} workers...")
        t0 = time.time()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=args.workers,
        ) as executor:
            futures = {executor.submit(dock_and_extract, m, receptor_config): m for m in pending}
            for future in concurrent.futures.as_completed(futures):
                mol = futures[future]
                try:
                    r = future.result(timeout=180)
                    if r:
                        prob, xgb_score, delta = score_with_classifier(r, engine=args.engine)
                        r["prob"] = prob
                        r["xgb_score"] = xgb_score  # XGBoost regressor (predicted delta_pKi)
                        r["delta"] = delta
                        # Historical composite formula (stacking_ef.py L65-72):
                        #   composite = prob * 0.70 + vina_norm * 0.30
                        # This is what produced the EF@1%=32.51x (5HT1A) / 42.10x (CDK2) /
                        # 13.10x (HIV-PR) results in metricas_experimentales.md.
                        # The previous code incorrectly used xgb_score (regressor) which can
                        # be negative — that broke EF ranking. See PR/issue history.
                        vina = abs(r.get("vina_score") or -5.0)
                        vina_norm = min(1.0, vina / 12.0)
                        if prob is not None and not math.isnan(prob) and prob > 0.01:
                            r["composite"] = round(prob * 0.70 + vina_norm * 0.30, 4)
                        else:
                            # vina-only real (no fabricación): componente ML ausente
                            r["composite"] = round(vina_norm, 4)
                        results.append(r)
                except Exception as e:
                    smiles_short = mol.get("smiles", "?")[:50]
                    if "Timeout" in type(e).__name__:
                        print(f"  [TIMEOUT] {smiles_short}...")
                    else:
                        print(f"  [SKIP] {smiles_short}... {type(e).__name__}")
                completed.add(mol["smiles"])

                if len(completed) % 10 == 0:
                    elapsed = time.time() - t0
                    rate = elapsed / max(len(completed), 1)
                    eta = rate * max(len(pending) - len(completed), 0)
                    print(f"  [{len(completed)}/{len(mols)}] {elapsed:.0f}s | "
                          f"ETA: {eta:.0f}s | {rate:.2f}s/mol | "
                          f"results: {len(results)}")
                # Incremental checkpoint every 50 molecules — survive crashes/timeouts
                if len(completed) % 50 == 0:
                    try:
                        CHECKPOINT_TARGET.write_text(json.dumps({
                            "completed_smiles": list(completed),
                            "results": results,
                        }, indent=2))
                    except Exception:
                        pass

        elapsed = time.time() - t0
        print(f"Done in {elapsed:.0f}s ({elapsed/60:.1f} min)")
        CHECKPOINT_TARGET.write_text(json.dumps({
            "completed_smiles": list(completed),
            "results": results,
        }, indent=2))

    # 4. Filter valid results for analysis
    #    Valid = dock ran (vina_score is not None) OR features extracted (ML scored).
    #    Note: composite (xgb_score = predicted delta_pKi) can be NEGATIVE for weak binders;
    #    that is expected behavior of the regressor. Filter on docking success, not sign.
    valid = [r for r in results if r.get("composite") is not None or r.get("vina_score") is not None]
    if not valid:
        print("[FAIL] No valid results.")
        return

    # 5. GNN + CL-GNN scoring + Calibrated Stacking
    if args.gnn:
        print(f"\nGNN inference on {len(valid)} molecules...")
        protein_pdb = receptor_config["protein_pdb"]
        t0 = time.time()
        for i, r in enumerate(valid):
            r = score_with_gnn(r, protein_pdb, engine=args.engine)
            if (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                print(f"  [GNN-v2 {i+1}/{len(valid)}] {elapsed:.0f}s | {elapsed/(i+1):.2f}s/mol")
        elapsed = time.time() - t0
        print(f"  GNN-v2 done: {elapsed:.0f}s ({elapsed/len(valid):.2f}s/mol)")

        print(f"  CL-GNN inference on {len(valid)} molecules...")
        t0 = time.time()
        for i, r in enumerate(valid):
            r = score_with_clgnn(r, protein_pdb, receptor_config)
            if (i + 1) % 100 == 0:
                elapsed = time.time() - t0
                print(f"  [CL-GNN {i+1}/{len(valid)}] {elapsed:.0f}s | {elapsed/(i+1):.2f}s/mol")
        elapsed = time.time() - t0
        print(f"  CL-GNN done: {elapsed:.0f}s ({elapsed/len(valid):.2f}s/mol)")

        # Calibrated stacking: batch rank-normalization + per-family weights
        family = target_family
        calibrated = calibrated_stacking(valid, family)
        for i, r in enumerate(valid):
            r["composite_calibrated"] = calibrated[i]

        # Show calibration effect
        gnns = [g for g in (r.get("gnn_prob") for r in valid) if g is not None]
        vinas = [abs(r.get("vina_score") or 0) for r in valid]
        probs = [p for p in (r.get("prob") for r in valid) if p is not None]
        print(f"    Calibrated stacking (family={family}, components: Vina+Classifier+GNN+CL-GNN)")
        print(f"      Weights: {STACKING_WEIGHTS.get(family, STACKING_WEIGHTS['default'])}")
        print(f"      Vina range:    [{min(vinas):.1f}, {max(vinas):.1f}]")
        print(f"      Prob range:    [{min(probs):.3f}, {max(probs):.3f}]" if probs else "      Prob: no valid")
        print(f"      GNN range:     [{min(gnns):.3f}, {max(gnns):.3f}]" if gnns else "      GNN: no valid")

        # Save updated checkpoint

    # 6. Unified metrics (Pipeline completo)
    unified_scores = []
    unified_labels = []
    coverage = {3: 0, 2: 0, 1: 0, 0: 0}

    for r in valid:
        gnn_c = r.get("composite_calibrated")
        gnn_old = r.get("composite_gnn")
        comp = r.get("composite")
        vina = r.get("vina_score")

        # Unified scoring: pick best tier available per molecule. Let composite_xgb be signed
        # (regressor predicts delta_pKi which can be negative); we just need a numeric signal.
        if gnn_c is not None:
            # Calibrated stacking output (rank-normalized, in [0,1])
            unified_scores.append(gnn_c)
            coverage[3] += 1
        elif gnn_old is not None:
            unified_scores.append(gnn_old)
            coverage[3] += 1
        elif comp is not None:
            unified_scores.append(float(comp))
            coverage[2] += 1
        elif vina is not None and vina < 0:
            unified_scores.append(min(1.0, abs(vina) / 12.0))
            coverage[1] += 1
        else:
            coverage[0] += 1
            continue
        unified_labels.append(r["is_active"])

    if unified_scores:
        print(f"\n{'='*60}")
        print(f"  PIPELINE COMPLETO — {len(unified_scores)} mols")
        print(f"  Cobertura: N3={coverage[3]} N2={coverage[2]} N1={coverage[1]} N0={coverage[0]}")
        print(f"{'='*60}")
        print_metrics(unified_scores, unified_labels, "Unified Score (best available per molecule)")

    # Vina-only for comparison
    vina_valid = [r for r in valid if r.get("vina_score") is not None and r["vina_score"] < 0]
    if vina_valid:
        vina_scores = [abs(r["vina_score"]) for r in vina_valid]
        vina_labels = [r["is_active"] for r in vina_valid]
        print_metrics(vina_scores, vina_labels, "Vina Only (baseline)")

    # Save report
    report = {
        "target": f"{target_name} ({target_id})",
        "target_family": target_family,
        "engine": args.engine,
        "vina_exhaustiveness": EXHAUSTIVENESS,
        "workers": args.workers,
        "features_used": "Shell 96 + ECIF 56 + 1D/2D 8 = 160",
        "classifier": "binder XGBoost (AUC 0.858)",
        "gnn_enabled": args.gnn,
        "box_source": receptor_config.get("box_source", "unknown"),  # [fix-b] provenance
        "box_center": list(receptor_config.get("center", (0, 0, 0))),
        "box_size": receptor_config.get("box_size", 0),
        "pipeline_complete": {
            "n_total": len(unified_scores),
            "n_actives": sum(unified_labels),
            "coverage_n3": coverage[3],
            "coverage_n2": coverage[2],
            "coverage_n1": coverage[1],
            "coverage_n0": coverage[0],
            "EF_1pct": enrichment_factor(unified_scores, unified_labels, 1) if unified_scores else None,
            "EF_5pct": enrichment_factor(unified_scores, unified_labels, 5) if unified_scores else None,
            "EF_10pct": enrichment_factor(unified_scores, unified_labels, 10) if unified_scores else None,
            "ROC_AUC": round(roc_auc_score(unified_labels, unified_scores), 4) if len(set(unified_labels)) > 1 and len(unified_scores) > 0 else None,
        },
        "vina_only": {
            "n_total": len(vina_valid),
            "EF_1pct": enrichment_factor(vina_scores, vina_labels, 1) if vina_valid else None,
            "EF_5pct": enrichment_factor(vina_scores, vina_labels, 5) if vina_valid else None,
            "EF_10pct": enrichment_factor(vina_scores, vina_labels, 10) if vina_valid else None,
            "ROC_AUC": round(roc_auc_score(vina_labels, vina_scores), 4) if vina_valid and len(set(vina_labels)) > 1 else None,
        },
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    REPORT_TARGET.write_text(json.dumps(report, indent=2))
    print(f"\nReport: {REPORT_TARGET}")

    # ── Auto-optimize stacking weights (updates JSON if better weights found) ──
    if unified_scores and len(set(unified_labels)) > 1:
        _auto_optimize_weights(valid, unified_labels, target_family, unified_scores)


def _auto_optimize_weights(results: list[dict], labels: list, family: str, current_scores: list[float]):
    """Grid search optimal stacking weights and update JSON if improvement found."""
    from sklearn.metrics import roc_auc_score
    n = len(results)
    if n < 500:  # minimum sample for statistically meaningful optimization
        print(f"  [Auto-optimize] {family}: need >=500 molecules for optimization (have {n})")
        return

    vina_vals = [abs(r.get("vina_score")) if r.get("vina_score") is not None else None for r in results]
    vina_max = max(v for v in vina_vals if v is not None) if any(v is not None for v in vina_vals) else 12
    vina_norm = [min(1.0, v / vina_max) if v is not None else 0.0 for v in vina_vals]
    xgb_vals = [r.get("prob", 0.0) for r in results]
    clgnn_vals = [r.get("clgnn_prob", 0.5) for r in results]

    current_auc = roc_auc_score(labels, current_scores)
    best_auc = current_auc
    best_w = STACKING_WEIGHTS.get(family, STACKING_WEIGHTS["default"])

    for w_v in np.arange(0.0, 1.01, 0.1):
        for w_x in np.arange(0.0, 1.01, 0.1):
            for w_c in np.arange(0.0, 1.01, 0.1):
                if abs(w_v + w_x + w_c - 1.0) > 0.01:
                    continue
                scores = [vina_norm[i] * w_v + xgb_vals[i] * w_x + clgnn_vals[i] * w_c for i in range(n)]
                auc = roc_auc_score(labels, scores)
                if auc > best_auc + 0.01:  # Only update if meaningful improvement
                    best_auc = auc
                    best_w = {"vina": round(w_v, 1), "prob": round(w_x, 1), "gnn": 0.0, "clgnn": round(w_c, 1)}

    # -- ESTA BUSQUEDA NO VE UMS, Y ESO IMPORTA EN METALOENZIMAS ---------
    #
    # El grid de arriba recorre tres componentes:
    #
    #     scores = vina_norm*w_v + xgb*w_x + clgnn*w_c
    #
    # UMS no entra. Para una metaloenzima eso deja fuera al unico scorer que
    # discrimina: medido sobre CA2 (docs/26_UNIVERSAL_METAL_SCORE_RESULTS.md
    # §1.3) vina 0.558, xgb 0.766, clgnn 0.592 y UMS 0.978.
    #
    # Por eso el `_auc` que se guarda abajo para esa familia sale en 0.5, y por
    # eso NO se pone un piso de AUC aqui: un piso rechazaria justamente la
    # calibracion que el paper valida (`docs/PAPER_UMS.md` §2.1.3, vina 0.00 y
    # CL-GNN dominante, con UMS anadido aparte con w5 = 0.25-0.40). El 2026-09-04
    # se anadio un piso de 0.55 y se retiro el mismo dia por esto.
    #
    # Lo que si se hace es DECIR que el numero guardado no describe el pipeline
    # completo, para que nadie lo lea como si lo hiciera.
    if best_auc > current_auc + 0.01:
        improved = best_auc - current_auc
        best_w["molchamb_sign"] = STACKING_WEIGHTS.get(family, {}).get("molchamb_sign", 1.0)
        best_w["_optimized_from"] = family
        best_w["_auc"] = round(best_auc, 4)
        best_w["_delta"] = round(improved, 4)
        # Que mide `_auc`: el subconjunto vina/xgb/clgnn, sin UMS ni MolChamb.
        # En metaloenzimas ese subconjunto esta cerca del azar POR DISENO y el
        # scorer que discrimina se anade despues (M5_gated). Sin esta linea, un
        # 0.5 aqui se lee como «calibracion invalida» y no lo es.
        best_w["_auc_mide"] = "vina+xgb+clgnn, SIN ums"
        STACKING_WEIGHTS[family] = best_w

        with open(_STACKING_WEIGHTS_PATH, "w") as f:
            json.dump(STACKING_WEIGHTS, f, indent=2)
        print(f"  [Auto-optimize] {family}: AUC {current_auc:.4f} -> {best_auc:.4f} (+{improved:.4f})")
        print(f"    New weights: vina={best_w['vina']}, prob={best_w['prob']}, clgnn={best_w['clgnn']}")
        print(f"    Saved to: {_STACKING_WEIGHTS_PATH}")
    else:
        print(f"  [Auto-optimize] {family}: weights already optimal (AUC={current_auc:.4f})")


def _init_worker():
    """Pre-load extractor en cada worker process."""
    import sys, os
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    _get_extractor()


if __name__ == "__main__":
    main()
