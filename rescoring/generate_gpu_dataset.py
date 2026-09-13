"""
rescoring/generate_gpu_dataset.py

NO SE DISTRIBUYE. Dependencia de DESARROLLO, no del runtime.

Este módulo importa los bindings de Python de Open Babel (`from openbabel import
openbabel`). Open Babel es GPL-2.0-only, y GPL-2.0-only es incompatible con la
AGPL-3.0-only bajo la que se publica MolDesign: importarlo desde código que se
distribuye convertiría las dos obras en una sola. Aquí es legítimo porque este
archivo **genera datasets de entrenamiento** y no viaja en el instalador.

Quién lo garantiza, y no de palabra:
  - `scripts/bundle_helper.py` lo excluye del runtime empaquetado
    (`RESCORING_FUERA_DEL_RUNTIME_FILES`);
  - `scripts/check_openbabel_boundary.py` comprueba sobre el BUNDLE REAL que no
    está, y lee esa misma lista para autorizarlo aquí. Si alguien lo autoriza
    sin excluirlo, la guarda lo caza en el artefacto.

Si algún día este código hiciera falta en producción, la conversión se hace con
`services.external_tools.open_babel`, que invoca `obabel.exe` por subproceso.
Ver `docs/79_ADR_FRONTERA_OPEN_BABEL.md`.

Genera el dataset de entrenamiento para los modelos GPU re-entrenados.

Flujo por complejo PDBbind:
  1. Leer split_config.json → IDs de train + val + test (los mismos del modelo CPU)
  2. Preparar receptor: {id}_protein.pdb → {id}_protein.pdbqt (via Meeko/obabel)
  3. Preparar ligando:  {id}_ligand.sdf  → {id}_ligand.pdbqt  (via Meeko)
  4. Dock con orchestrator.py (GPU search → CPU refine → fallback CPU)
  5. Extraer las 167 features 3D con feature_extractor.extract_single_complex()
  6. Guardar en data/gpu_poses/dataset_gpu.parquet

Checkpointing: reanudable si se interrumpe. Cada complejo se guarda
incrementalmente en dataset_gpu.parquet (sobrescribiendo con los datos actualizados).

Uso:
    cd rescoring
    python generate_gpu_dataset.py
    python generate_gpu_dataset.py --workers 4 --dry-run    # solo audit
    python generate_gpu_dataset.py --ids 1f0r 10gs 184l     # subset
    python generate_gpu_dataset.py --resume                  # reanuda desde checkpoint

Salida:
    data/gpu_poses/dataset_gpu.parquet   ← dataset completo
    data/gpu_poses/checkpoint.json       ← estado para resume
    data/gpu_poses/log.jsonl             ← log de cada complejo
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

# ── Rutas del proyecto ────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESCORING_DIR = PROJECT_ROOT / "rescoring"
PDBBIND_DIR   = PROJECT_ROOT / "data" / "pdbbind"
GPU_POSES_DIR = PROJECT_ROOT / "data" / "gpu_poses"
GPU_POSES_DIR.mkdir(parents=True, exist_ok=True)

SPLIT_CONFIG  = RESCORING_DIR / "artifacts" / "split_config.json"
CHECKPOINT    = GPU_POSES_DIR / "checkpoint.json"
DATASET_OUT   = GPU_POSES_DIR / "dataset_gpu.parquet"
LOG_FILE      = GPU_POSES_DIR / "log.jsonl"

# ── Binarios ─────────────────────────────────────────────────────────────
VINA_CPU    = PROJECT_ROOT / "tools" / "vina" / "vina.exe"
MEEKO_PREP  = "mk_prepare_ligand.py"   # se llama via python -m meeko

# ── Orchestrator GPU (D:/ad-gpu-project) ─────────────────────────────────
AD_GPU_DIR  = Path("D:/ad-gpu-project")
sys.path.insert(0, str(AD_GPU_DIR))

# ── Imports propios del rescoring ─────────────────────────────────────────
sys.path.insert(0, str(RESCORING_DIR))
from feature_extractor import (
    extract_single_complex,
)

# ── Features 1D/2D (calculadas aquí, no en feature_extractor) ────────────
# Igual que en train_orchestrator.py
RDKIT_1D_FEATURES = [
    "mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed", "log_mw",
]
VINA_FEATURES = [
    "vina_best_score", "pose_score_variance", "pose_score_range", "poses_passing_ratio",
]

# ── Box size por defecto para re-docking PDBbind ─────────────────────────
# 25 Å cubre todos los ligandos típicos de PDBbind
DEFAULT_BOX_SIZE = (25.0, 25.0, 25.0)


# ─────────────────────────────────────────────────────────────────────────
# Dataclasses
# ─────────────────────────────────────────────────────────────────────────

@dataclass
class ComplexResult:
    pdb_id: str
    pki: float
    features: dict
    score: float
    method: str   # "gpu_hybrid" | "cpu_fallback"
    runtime: float
    error: str | None = None


# ─────────────────────────────────────────────────────────────────────────
# Helpers: preparación de archivos
# ─────────────────────────────────────────────────────────────────────────

def _compute_ligand_center(sdf_path: Path) -> tuple[float, float, float]:
    """Calcula el centroide del ligando desde el SDF para definir el box."""
    try:
        from rdkit import Chem
        mol = Chem.SDMolSupplier(str(sdf_path), removeHs=False)[0]
        if mol is None:
            raise ValueError("SDMolSupplier returned None")
        conf = mol.GetConformer()
        coords = conf.GetPositions()
        cx, cy, cz = coords.mean(axis=0)
        return float(cx), float(cy), float(cz)
    except Exception as e:
        raise RuntimeError(f"Cannot compute centroid from {sdf_path}: {e}")


def _sdf_to_pdbqt(sdf_path: Path, out_pdbqt: Path) -> bool:
    """Convierte SDF → PDBQT usando Meeko (idéntico a benchmark_ef_vina.py)."""
    try:
        r = subprocess.run(
            [sys.executable, "-m", "meeko.scripts.mk_prepare_ligand",
             "-i", str(sdf_path), "-o", str(out_pdbqt)],
            capture_output=True, text=True, timeout=30,
            cwd=str(RESCORING_DIR),
        )
        if r.returncode == 0 and out_pdbqt.exists() and out_pdbqt.stat().st_size > 50:
            return True
    except Exception:
        pass

    # Fallback: openbabel Python bindings (no depende de obabel en PATH)
    try:
        from openbabel import openbabel
        conv = openbabel.OBConversion()
        conv.SetInFormat("sdf")
        conv.SetOutFormat("pdbqt")
        mol = openbabel.OBMol()
        if conv.ReadFile(mol, str(sdf_path)):
            mol.AddHydrogens()
            conv.WriteFile(mol, str(out_pdbqt))
            return out_pdbqt.exists() and out_pdbqt.stat().st_size > 50
    except Exception:
        pass
    return False


def _pdb_to_pdbqt_receptor(pdb_path: Path, out_pdbqt: Path) -> bool:
    """Convierte proteína PDB → PDBQT usando openbabel Python bindings.
    Idéntico a como lo hace benchmark_ef_vina.py (from openbabel import openbabel).
    """
    try:
        from openbabel import openbabel
        conv = openbabel.OBConversion()
        conv.SetInFormat("pdb")
        conv.SetOutFormat("pdbqt")
        conv.AddOption("r", openbabel.OBConversion.OUTOPTIONS)  # rigid receptor
        mol = openbabel.OBMol()
        if not conv.ReadFile(mol, str(pdb_path)):
            return False
        mol.AddHydrogens()
        conv.WriteFile(mol, str(out_pdbqt))
        return out_pdbqt.exists() and out_pdbqt.stat().st_size > 100
    except Exception:
        return False


def _compute_rdkit_1d(sdf_path: Path) -> dict[str, float]:
    """Calcula features 1D/2D con RDKit desde el SDF original (no la pose)."""
    zeros = {f: 0.0 for f in RDKIT_1D_FEATURES}
    try:
        from rdkit import Chem
        from rdkit.Chem import QED, Descriptors
        mol = Chem.SDMolSupplier(str(sdf_path), removeHs=True)[0]
        if mol is None:
            return zeros
        mw   = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        tpsa = Descriptors.TPSA(mol)
        hbd  = Descriptors.NumHDonors(mol)
        hba  = Descriptors.NumHAcceptors(mol)
        rot  = Descriptors.NumRotatableBonds(mol)
        qed  = QED.qed(mol)
        import math
        return {
            "mw": mw, "logp": logp, "tpsa": tpsa,
            "hbd": float(hbd), "hba": float(hba),
            "rotatable_bonds": float(rot),
            "qed": qed,
            "log_mw": math.log(mw) if mw > 0 else 0.0,
        }
    except Exception:
        return zeros


# ─────────────────────────────────────────────────────────────────────────
# Procesamiento de un complejo (función top-level para multiprocessing)
# ─────────────────────────────────────────────────────────────────────────

def process_complex(args: dict) -> dict:
    """
    Procesa UN complejo PDBbind:
      protein.pdb + ligand.sdf → dock GPU → extract_single_complex → features dict.

    Diseñado para correr en ProcessPoolExecutor.
    Retorna un dict serializable (no dataclass).
    """
    pdb_id  = args["pdb_id"]
    pki     = args["pki"]
    pdb_dir = Path(args["pdb_dir"])

    protein_pdb = pdb_dir / f"{pdb_id}_protein.pdb"
    ligand_sdf  = pdb_dir / f"{pdb_id}_ligand.sdf"

    t0 = time.perf_counter()

    # Validar archivos
    if not protein_pdb.exists() or not ligand_sdf.exists():
        return {
            "pdb_id": pdb_id, "pki": pki,
            "error": f"Missing files: protein={protein_pdb.exists()} sdf={ligand_sdf.exists()}",
            "features": None, "score": None, "method": "error", "runtime": 0.0,
        }

    with tempfile.TemporaryDirectory(prefix=f"gpu_{pdb_id}_") as work_dir:
        work = Path(work_dir)

        # 1. Calcular features 1D/2D desde ligando original (no pose)
        feat_1d = _compute_rdkit_1d(ligand_sdf)

        # 2. Preparar receptor PDBQT
        receptor_pdbqt = work / f"{pdb_id}_protein.pdbqt"
        if not _pdb_to_pdbqt_receptor(protein_pdb, receptor_pdbqt):
            return {
                "pdb_id": pdb_id, "pki": pki,
                "error": "receptor_pdbqt_failed",
                "features": None, "score": None, "method": "error",
                "runtime": time.perf_counter() - t0,
            }

        # 3. Preparar ligando PDBQT
        ligand_pdbqt = work / f"{pdb_id}_ligand.pdbqt"
        if not _sdf_to_pdbqt(ligand_sdf, ligand_pdbqt):
            return {
                "pdb_id": pdb_id, "pki": pki,
                "error": "ligand_pdbqt_failed",
                "features": None, "score": None, "method": "error",
                "runtime": time.perf_counter() - t0,
            }

        # 4. Calcular centroide del ligando (box center)
        try:
            cx, cy, cz = _compute_ligand_center(ligand_sdf)
        except Exception as e:
            return {
                "pdb_id": pdb_id, "pki": pki,
                "error": f"centroid_failed: {e}",
                "features": None, "score": None, "method": "error",
                "runtime": time.perf_counter() - t0,
            }

        center = (cx, cy, cz)
        size   = DEFAULT_BOX_SIZE

        # 5. Docking GPU → CPU hybrid
        try:
            import sys as _sys
            _ad_gpu_dir = str(Path("D:/ad-gpu-project"))
            if _ad_gpu_dir not in _sys.path:
                _sys.path.insert(0, _ad_gpu_dir)
            from orchestrator import dock as gpu_dock
            dock_result = gpu_dock(
                receptor=str(receptor_pdbqt),
                ligand_pdbqt=str(ligand_pdbqt),
                center=center,
                size=size,
                work_dir=str(work / "dock"),
            )
            score  = dock_result.score
            method = dock_result.method
        except Exception as e:
            return {
                "pdb_id": pdb_id, "pki": pki,
                "error": f"docking_failed: {e}",
                "features": None, "score": None, "method": "error",
                "runtime": time.perf_counter() - t0,
            }

        if score is None:
            return {
                "pdb_id": pdb_id, "pki": pki,
                "error": f"score_is_none: {dock_result.error}",
                "features": None, "score": None, "method": method,
                "runtime": time.perf_counter() - t0,
            }

        # 6. Extraer features 3D desde pose GPU
        # La pose está en work/dock/ — buscamos el PDBQT de salida
        pose_pdbqt_candidates = list((work / "dock").glob("*.pdbqt")) if (work / "dock").exists() else []
        pose_sdf = work / "pose_gpu.sdf"

        # Intentar convertir pose PDBQT → SDF para ProLIF
        pose_converted = False
        if pose_pdbqt_candidates:
            pose_pdbqt = pose_pdbqt_candidates[0]
            
            # GUARDAR LA POSE GPU PARA LA GNN
            pdbs_dir = GPU_POSES_DIR / "pdbs"
            pdbs_dir.mkdir(parents=True, exist_ok=True)
            saved_pose = pdbs_dir / f"{pdb_id}_docked.pdbqt"
            import shutil
            shutil.copy2(pose_pdbqt, saved_pose)

            try:
                r = subprocess.run(
                    ["obabel", str(pose_pdbqt), "-O", str(pose_sdf)],
                    capture_output=True, text=True, timeout=15,
                )
                pose_converted = r.returncode == 0 and pose_sdf.exists() and pose_sdf.stat().st_size > 20
            except Exception:
                pose_converted = False

        # Si no hay pose convertible, usamos el SDF original (geometría cristalográfica)
        ligand_for_features = str(pose_sdf) if pose_converted else str(ligand_sdf)

        try:
            features_3d = extract_single_complex(
                protein_pdb=str(protein_pdb),
                ligand_sdf=ligand_for_features,
            )
        except Exception:
            features_3d = {}

        # 7. Armar el vector completo de features (mismo orden que ALL_FEATURES en train_pipeline)
        # Grupos B (Vina): best_score de GPU, variance/range/ratio = 0 (solo 1 pose)
        feat_vina = {
            "vina_best_score":     score,
            "pose_score_variance": 0.0,
            "pose_score_range":    0.0,
            "poses_passing_ratio": 1.0,
        }

        # Unir todos los grupos
        all_features = {}
        all_features.update(feat_1d)
        all_features.update(feat_vina)
        all_features.update(features_3d)

        runtime = time.perf_counter() - t0

    return {
        "pdb_id": pdb_id,
        "pki":    pki,
        "features": all_features,
        "score":  score,
        "method": method,
        "runtime": round(runtime, 2),
        "error":  None,
    }


# ─────────────────────────────────────────────────────────────────────────
# Cargar split_config
# ─────────────────────────────────────────────────────────────────────────

def load_all_ids_from_split(split_path: Path) -> list[str]:
    """
    Devuelve TODOS los IDs del split: frozen_test_set + train_ids de todos los folds + val_ids.
    De esta forma replicamos exactamente el dataset completo del modelo CPU.
    """
    with open(split_path) as f:
        cfg = json.load(f)

    ids = set()
    ids.update(cfg.get("frozen_test_set", []))
    for fold in cfg.get("folds", []):
        ids.update(fold.get("train_ids", []))
        ids.update(fold.get("val_ids", []))
    return sorted(ids)


def load_pki_map(pdbbind_dir: Path, ids: list[str]) -> dict[str, float]:
    """
    Carga los valores de pKi desde los archivos INDEX de PDBbind.
    Si no hay INDEX, retorna 0.0 para ese ID.
    """
    pki_map: dict[str, float] = {pdb_id: 0.0 for pdb_id in ids}

    # Buscar archivo INDEX en pdbbind_dir
    for index_name in ["INDEX_refined_data.2020", "INDEX_general_PL_data.2020",
                        "INDEX_refined_data.2019", "index_refined_data.csv"]:
        index_path = pdbbind_dir / index_name
        if index_path.exists():
            try:
                with open(index_path) as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        parts = line.split()
                        if len(parts) >= 4:
                            pid = parts[0].lower()
                            if pid in pki_map:
                                try:
                                    pki_map[pid] = float(parts[3])
                                except (ValueError, IndexError):
                                    pass
            except Exception:
                pass
            break

    return pki_map


# ─────────────────────────────────────────────────────────────────────────
# Checkpoint
# ─────────────────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    """Retorna el set de IDs ya procesados exitosamente."""
    if CHECKPOINT.exists():
        try:
            with open(CHECKPOINT) as f:
                data = json.load(f)
            return set(data.get("done", []))
        except Exception:
            return set()
    return set()


def save_checkpoint(done: set[str]) -> None:
    with open(CHECKPOINT, "w") as f:
        json.dump({"done": sorted(done), "n": len(done)}, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────
# Guardar dataset
# ─────────────────────────────────────────────────────────────────────────

def save_dataset(rows: list[dict], out_path: Path) -> None:
    """
    Guarda el dataset como CSV (compatible con pandas/numpy sin pyarrow).
    También genera un Parquet si pyarrow está disponible.
    Cada fila: pdb_id + pki + 167 features.
    """
    records = []
    for row in rows:
        if row["features"] is None:
            continue
        record = {"pdb_id": row["pdb_id"], "pki": row["pki"],
                  "score_gpu": row["score"], "method": row["method"]}
        record.update(row["features"])
        records.append(record)

    if not records:
        print("[WARN] No hay complejos exitosos para guardar.")
        return

    # Siempre guardar CSV (sin dependencias extra)
    csv_path = out_path.with_suffix(".csv")
    try:
        import pandas as pd
        df = pd.DataFrame(records)
        df.to_csv(csv_path, index=False)
        print(f"[SAVE] {len(df)} complejos -> {csv_path}")
        # Intentar Parquet si pyarrow disponible
        try:
            df.to_parquet(out_path, index=False, compression="snappy")
            print(f"[SAVE] También guardado como Parquet: {out_path}")
        except Exception:
            pass  # Sin pyarrow — CSV es suficiente
    except ImportError:
        # Sin pandas: JSON Lines
        alt = out_path.with_suffix(".jsonl")
        with open(alt, "w") as f:
            for row in records:
                f.write(json.dumps(row) + "\n")
        print(f"[SAVE] {len(records)} complejos -> {alt}")


def append_log(row: dict) -> None:
    with open(LOG_FILE, "a") as f:
        safe = {k: v for k, v in row.items() if k != "features"}
        f.write(json.dumps(safe) + "\n")


# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Genera dataset GPU para re-entrenamiento de XGBoost/GNN"
    )
    parser.add_argument("--workers", type=int, default=2,
                        help="Procesos paralelos (default: 2). "
                             "GPU es single-threaded; workers=2 es óptimo.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Solo audita IDs y archivos, no dockea.")
    parser.add_argument("--resume", action="store_true",
                        help="Reanuda desde checkpoint (salta IDs ya procesados).")
    parser.add_argument("--ids", nargs="+", default=None,
                        help="Procesar solo estos IDs específicos (para testing).")
    parser.add_argument("--limit", type=int, default=None,
                        help="Limitar a N complejos (para piloto rápido).")
    args = parser.parse_args()

    print("=" * 65)
    print("  GPU Dataset Generator — MolDesign v4.1")
    print("=" * 65)
    print(f"  PDBbind dir:   {PDBBIND_DIR}")
    print(f"  Output:        {DATASET_OUT}")
    print(f"  Workers:       {args.workers}")
    print(f"  Dry-run:       {args.dry_run}")
    print(f"  Resume:        {args.resume}")
    print()

    # 1. Cargar IDs del split
    if not SPLIT_CONFIG.exists():
        print(f"[ERROR] split_config.json no encontrado: {SPLIT_CONFIG}")
        sys.exit(1)

    all_ids = args.ids if args.ids else load_all_ids_from_split(SPLIT_CONFIG)
    print(f"  IDs en split_config: {len(all_ids)}")

    # 2. Filtrar por archivos existentes en PDBbind
    valid_ids = []
    missing = []
    for pdb_id in all_ids:
        d = PDBBIND_DIR / pdb_id
        prot = d / f"{pdb_id}_protein.pdb"
        lig  = d / f"{pdb_id}_ligand.sdf"
        if prot.exists() and lig.exists():
            valid_ids.append(pdb_id)
        else:
            missing.append(pdb_id)

    print(f"  Con archivos (protein.pdb + ligand.sdf): {len(valid_ids)}")
    if missing:
        print(f"  Sin archivos (se omiten): {len(missing)}")

    if args.dry_run:
        print("\n[DRY-RUN] Audit completo. Sin docking.")
        print(f"  IDs listos para procesar: {len(valid_ids)}")
        return

    # 3. Cargar checkpoint si resume
    done_ids: set[str] = set()
    if args.resume:
        done_ids = load_checkpoint()
        print(f"  Ya procesados (checkpoint): {len(done_ids)}")

    # 4. IDs pendientes
    pending = [pid for pid in valid_ids if pid not in done_ids]
    if args.limit:
        pending = pending[:args.limit]
    print(f"  Por procesar: {len(pending)}")
    print()

    if not pending:
        print("[INFO] Todo ya está procesado. Dataset listo.")
        return

    # 5. Cargar pKi
    pki_map = load_pki_map(PDBBIND_DIR, valid_ids)
    pki_found = sum(1 for v in pki_map.values() if v > 0)
    print(f"  pKi values cargados: {pki_found}/{len(valid_ids)}")
    print()

    # 6. Cargar resultados ya procesados (para re-construir dataset completo)
    all_rows: list[dict] = []
    if args.resume and LOG_FILE.exists():
        # Reconstruir filas desde log (solo las exitosas)
        with open(LOG_FILE) as f:
            for line in f:
                try:
                    row = json.loads(line)
                    if row.get("error") is None and row.get("pdb_id") in done_ids:
                        all_rows.append(row)
                except Exception:
                    pass

    # 7. Procesar en paralelo
    task_args = [
        {
            "pdb_id": pid,
            "pki":    pki_map.get(pid, 0.0),
            "pdb_dir": str(PDBBIND_DIR / pid),
        }
        for pid in pending
    ]

    t_total = time.time()
    n_ok = 0
    n_fail = 0

    print(f"Iniciando docking GPU ({len(task_args)} complejos, {args.workers} workers)...")
    print(f"{'ID':>10s}  {'pKi':>6s}  {'Score':>8s}  {'Method':>12s}  {'Time':>6s}  Status")
    print("-" * 65)

    def _process_and_log(task):
        """Procesa un complejo, loggea y actualiza checkpoint."""
        pid = task["pdb_id"]
        try:
            result = process_complex(task)
        except Exception as e:
            result = {
                "pdb_id": pid, "pki": task["pki"],
                "error": str(e), "features": None,
                "score": None, "method": "error", "runtime": 0.0,
            }
        append_log(result)
        done_ids.add(pid)
        save_checkpoint(done_ids)
        return result

    if args.workers <= 1:
        # ── Modo secuencial (recomendado para GPU) ──
        for i, task in enumerate(task_args):
            pid = task["pdb_id"]
            result = _process_and_log(task)

            if result["error"] is None:
                n_ok += 1
                all_rows.append(result)
                score_str  = f"{result['score']:8.2f}" if result["score"] else "    None"
                method_str = result["method"]
            else:
                n_fail += 1
                score_str  = "   ERROR"
                method_str = result.get("method", "error")

            elapsed = result["runtime"]
            n_done  = i + 1
            print(f"{pid:>10s}  {pki_map.get(pid, 0.0):6.2f}  "
                  f"{score_str}  {method_str:>12s}  {elapsed:5.1f}s  "
                  f"[{n_done}/{len(task_args)}]")

            if n_done % 25 == 0:
                save_dataset(all_rows, DATASET_OUT)
    else:
        # ── Modo paralelo (solo CPU fallback, sin colisiones GPU) ──
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(process_complex, task): task["pdb_id"]
                       for task in task_args}

            for future in as_completed(futures):
                pid = futures[future]
                try:
                    result = future.result(timeout=600)
                except Exception as e:
                    result = {
                        "pdb_id": pid, "pki": pki_map.get(pid, 0.0),
                        "error": str(e), "features": None,
                        "score": None, "method": "error", "runtime": 0.0,
                    }

                append_log(result)
                done_ids.add(pid)
                save_checkpoint(done_ids)

                if result["error"] is None:
                    n_ok += 1
                    all_rows.append(result)
                    score_str  = f"{result['score']:8.2f}" if result["score"] else "    None"
                    method_str = result["method"]
                else:
                    n_fail += 1
                    score_str  = "   ERROR"
                    method_str = result.get("method", "error")

                elapsed = result["runtime"]
                n_done  = n_ok + n_fail
                print(f"{pid:>10s}  {pki_map.get(pid, 0.0):6.2f}  "
                      f"{score_str}  {method_str:>12s}  {elapsed:5.1f}s  "
                      f"[{n_done}/{len(task_args)}]")

                if n_done % 25 == 0:
                    save_dataset(all_rows, DATASET_OUT)

    # 8. GPU-only filter: exclude cpu_fallback complexes
    gpu_rows = [r for r in all_rows if r.get("method") == "gpu_hybrid"]
    n_cpu_fallback = sum(1 for r in all_rows if r.get("method") == "cpu_fallback")
    n_errors = sum(1 for r in all_rows if r.get("method") == "error")
    if n_cpu_fallback:
        print(f"\n  [GPU-FILTER] Excluidos {n_cpu_fallback} cpu_fallback + {n_errors} errores -> {len(gpu_rows)} GPU-only")
    save_dataset(gpu_rows, DATASET_OUT)

    total_time = time.time() - t_total
    print()
    print("=" * 65)
    print(f"  COMPLETADO en {total_time/60:.1f} min")
    print(f"  OK:    {n_ok}")
    print(f"  FAIL:  {n_fail}")
    print(f"  Total: {n_ok + n_fail}")
    print(f"  Dataset: {DATASET_OUT}")
    print(f"  Log:     {LOG_FILE}")
    print()
    print("  Próximo paso:")
    print("    cd rescoring")
    print("    python train_pipeline_gpu.py  ← re-entrena XGBoost con datos GPU")
    print("    python -m gnn_v2.train_gpu    ← re-entrena GNN con datos GPU")
    print("=" * 65)


if __name__ == "__main__":
    main()
