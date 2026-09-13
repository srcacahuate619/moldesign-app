"""
rescoring/scripts/redock_pdbbind.py

Re-dock PDBbind crystal ligands with AutoDock Vina to populate Group B features.

═══════════════════════════════════════════════════════════════════════════
PROBLEMA: En training, Group B features (vina_best_score, pose_score_variance,
pose_score_range, poses_passing_ratio) son siempre 0 porque usamos las poses
cristalográficas de PDBbind, no poses de docking.  En producción, estas
features vienen del docking real.  Esto crea un train/inference mismatch
que hace que el modelo ignore Group B completamente.

SOLUCIÓN: Re-dockear los ligandos cristalográficos contra sus propias
proteínas con Vina, usando el mismo protocolo que en producción.

NOTA: Este proceso es computacionalmente costoso.
  ~5 min/complejo × 3,019 complejos = ~250 horas en 1 core
  Con 6 cores: ~42 horas
  Recomendación: ejecutar en background o en servidor dedicado.

RESULTADO: Los features de Vina se guardan en el cache de features,
permitiendo que el modelo aprenda de la correlación entre score Vina,
varianza de poses, y afinidad experimental.

PREPARACIÓN DE ARCHIVOS (sin binario `obabel` externo):
  - Ligando:  RDKit (lee SDF + H) → Meeko MoleculePreparation/PDBQTWriterLegacy
              (en proceso) → fallback bindings Python de Open Babel.
  - Receptor: bindings Python de Open Babel PDB → PDBQT rígido ("r",
              equivalente a -xr) + sanitización de tags ROOT/BRANCH →
              fallback CLI de Meeko (meeko.cli.mk_prepare_receptor).
═══════════════════════════════════════════════════════════════════════

Uso:
  python scripts/redock_pdbbind.py --data-dir PATH --vina-path PATH [--max-workers N]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np

SEMILLA_VINA = 42  # seed de Vina preregistrada 2026-08-15 (FND-06, cierre de
                   # garantia futura): TODAS las corridas futuras de
                   # flexible_redock la pasan explicitamente via --seed y se
                   # registra como seed_docking en provenance.json.


def prepare_ligand_pdbqt(sdf_path: str, output_path: str) -> bool:
    """
    Convierte el ligando SDF a PDBQT para Vina.

    Cadena de preparación (en proceso, sin binario `obabel`):
      1. RDKit lee el SDF conservando la conformación cristalográfica y
         agrega los hidrógenos faltantes.
      2. Meeko (MoleculePreparation + PDBQTWriterLegacy) genera el PDBQT
         con tipos de átomo AutoDock (misma ruta que
         benchmark_ef_vina._prepare_ligand, adaptada a entrada SDF).
      3. Fallback: bindings Python de Open Babel (SDF → PDBQT, agregando
         hidrógenos), para ligandos que Meeko rechaza.
    Devuelve False solo si toda la cadena falla.
    """
    # 1. RDKit lee el SDF; si no puede, se salta directo al fallback.
    mol = None
    try:
        from rdkit import Chem, RDLogger

        RDLogger.logger().setLevel(RDLogger.ERROR)
        mol = Chem.MolFromMolFile(sdf_path)
    except Exception:
        mol = None

    # 2. Meeko en proceso (ruta probada en benchmark_ef_vina.py).
    if mol is not None:
        try:
            from meeko import MoleculePreparation, PDBQTWriterLegacy

            mol = Chem.AddHs(mol)
            preparator = MoleculePreparation()
            mol_setups = preparator.prepare(mol)
            if mol_setups:
                pdbqt_string, is_ok, _ = PDBQTWriterLegacy.write_string(mol_setups[0])
                if is_ok and pdbqt_string:
                    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                    Path(output_path).write_text(pdbqt_string)
                    if Path(output_path).stat().st_size > 10:
                        return True
        except Exception:
            pass

    # 3. Fallback: bindings Python de Open Babel (sin binario externo).
    try:
        from openbabel import openbabel as ob

        conv = ob.OBConversion()
        conv.SetInAndOutFormats("sdf", "pdbqt")
        obmol = ob.OBMol()
        if conv.ReadFile(obmol, sdf_path):
            obmol.AddHydrogens()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            if conv.WriteFile(obmol, output_path):
                if Path(output_path).exists() and Path(output_path).stat().st_size > 10:
                    return True
    except Exception:
        pass

    return False


def _sanitize_pdbqt_rigid(pdbqt_path: str) -> bool:
    """Elimina tags ROOT/ENDROOT/BRANCH/ENDBRANCH del PDBQT rígido.

    Open Babel puede agregar tags de residuos flexibles en receptores
    grandes y el parser rígido de Vina los rechaza. Misma lógica que
    benchmark_ef_vina._sanitize_pdbqt_rigid. Retorna True si el archivo
    final existe con tamaño mínimo válido.
    """
    p = Path(pdbqt_path)
    if not p.exists() or p.stat().st_size <= 100:
        return False
    with open(pdbqt_path) as f:
        lines = f.readlines()
    cleaned = [l for l in lines if not l.startswith(("ROOT", "ENDROOT", "BRANCH", "ENDBRANCH"))]
    if len(cleaned) < len(lines):
        with open(pdbqt_path, "w") as f:
            f.writelines(cleaned)
    return True


def prepare_receptor_pdbqt(pdb_path: str, output_path: str) -> bool:
    """
    Prepara el receptor PDBQT desde el PDB.

    Cadena de preparación:
      1. Bindings Python de Open Babel: PDB → PDBQT rígido (opción "r",
         equivalente a `obabel -xr`), conservando los protones existentes
         del PDB (los *_protein.pdb de PDBbind ya traen hidrógenos).
      2. Sanitización: se eliminan tags ROOT/ENDROOT/BRANCH/ENDBRANCH.
      3. Fallback: CLI de Meeko (meeko 0.7.1, subproceso con timeout 60s):
         `python -m meeko.cli.mk_prepare_receptor --read_pdb PDB -p PDBQT`.
    Devuelve False solo si ambas rutas fallan.
    """
    # 1. Bindings Python de Open Babel (en proceso, sin binario obabel).
    try:
        from openbabel import openbabel

        conv = openbabel.OBConversion()
        conv.SetInFormat("pdb")
        conv.SetOutFormat("pdbqt")
        conv.AddOption("r", openbabel.OBConversion.OUTOPTIONS)
        mol = openbabel.OBMol()
        if conv.ReadFile(mol, pdb_path):
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            conv.WriteFile(mol, output_path)
    except Exception:
        pass

    if _sanitize_pdbqt_rigid(output_path):
        return True

    # 2. Fallback: CLI de Meeko (subproceso con timeout de 60s).
    try:
        out_resolved = Path(output_path).resolve()
        result = subprocess.run(
            [
                sys.executable, "-m", "meeko.cli.mk_prepare_receptor",
                "--read_pdb", str(Path(pdb_path).resolve()),
                "-p", str(out_resolved),
            ],
            capture_output=True, text=True, timeout=60,
            cwd=str(out_resolved.parent),
        )
        if result.returncode == 0:
            # Meeko escribe output_path tal cual; si detecta residuos
            # flexibles agrega el sufijo "_rigid" antes de ".pdbqt".
            rigid_candidate = out_resolved.with_name(out_resolved.stem + "_rigid.pdbqt")
            if rigid_candidate.exists() and not out_resolved.exists():
                rigid_candidate.replace(out_resolved)
            if out_resolved.exists() and out_resolved.stat().st_size > 100:
                return True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    except Exception:
        pass

    return False


def find_binding_center(sdf_path: str) -> tuple[float, float, float] | None:
    """
    Calculate binding site center from crystal ligand coordinates.
    This is the centroid of the ligand heavy atoms.

    Robustez (2026-08-13): algunos SDF de PDBbind no kekulizan en RDKit
    (~10-30% de la muestra) y antes se saltaban silenciosamente. Estrategia:
      1. RDKit con sanitize=False (coordenadas no necesitan kekulización).
      2. Fallback: bindings de Open Babel (centroide de átomos pesados).
    """
    coords: list[list[float]] = []

    # 1. RDKit sin sanitizar: solo nos interesan las coordenadas 3D.
    try:
        from rdkit import Chem, RDLogger

        RDLogger.logger().setLevel(RDLogger.ERROR)
        mol = Chem.MolFromMolFile(sdf_path, sanitize=False, removeHs=False)
        if mol is not None and mol.GetNumConformers() > 0:
            conf = mol.GetConformer()
            coords = [
                [float(v) for v in conf.GetAtomPosition(i)]
                for i in range(mol.GetNumAtoms())
                if mol.GetAtomWithIdx(i).GetAtomicNum() > 1
            ]
    except Exception:
        coords = []

    # 2. Fallback: Open Babel (lee SDF, centroide de átomos pesados).
    if not coords:
        try:
            from openbabel import openbabel as ob

            conv = ob.OBConversion()
            conv.SetInFormat("sdf")
            obmol = ob.OBMol()
            if conv.ReadFile(obmol, sdf_path):
                for atom in ob.OBMolAtomIter(obmol):
                    if atom.GetAtomicNum() > 1:
                        coords.append([atom.GetX(), atom.GetY(), atom.GetZ()])
        except Exception:
            coords = []

    if not coords:
        return None

    center = np.array(coords).mean(axis=0)
    return (float(center[0]), float(center[1]), float(center[2]))


def run_vina_redocking(
    pdb_id: str,
    protein_pdb: str,
    ligand_sdf: str,
    vina_path: str,
    work_dir: str,
) -> tuple[dict[str, float] | None, str]:
    """
    Run Vina re-docking for a single PDBbind complex.

    Returns (features, reason): features dict with Group B features, or
    None with an explicit reason on failure. Ningún fallo es silencioso:
    el llamador registra el motivo para el manifest de integridad.
    """
    work = Path(work_dir)
    work.mkdir(parents=True, exist_ok=True)

    lig_pdbqt = str(work / f"{pdb_id}_lig.pdbqt")
    rec_pdbqt = str(work / f"{pdb_id}_rec.pdbqt")

    # Prepare receptor
    if not prepare_receptor_pdbqt(protein_pdb, rec_pdbqt):
        return None, "receptor_prep_failed"

    # Prepare ligand
    if not prepare_ligand_pdbqt(ligand_sdf, lig_pdbqt):
        return None, "ligand_prep_failed"

    # Find binding center from crystal ligand
    center = find_binding_center(ligand_sdf)
    if center is None:
        return None, "binding_center_failed"

    cx, cy, cz = center

    # Run Vina
    out_pdbqt = str(work / f"{pdb_id}_out.pdbqt")
    cmd = [
        vina_path,
        "--receptor", rec_pdbqt,
        "--ligand", lig_pdbqt,
        "--center_x", str(cx),
        "--center_y", str(cy),
        "--center_z", str(cz),
        "--size_x", "25",
        "--size_y", "25",
        "--size_z", "25",
        "--exhaustiveness", "8",
        "--num_modes", "9",
        "--seed", str(SEMILLA_VINA),
        "--out", out_pdbqt,
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=300,
        )
        if result.returncode != 0:
            return None, f"vina_returncode_{result.returncode}"
    except subprocess.TimeoutExpired:
        return None, "vina_timeout_300s"
    except FileNotFoundError:
        return None, "vina_binary_not_found"

    # Parse scores from output
    scores = []
    for line in result.stdout.split("\n"):
        parts = line.strip().split()
        if len(parts) >= 4 and parts[0].isdigit():
            try:
                scores.append(float(parts[1]))
            except ValueError:
                continue

    if not scores:
        return None, "vina_no_scores_parsed"

    # FND-06: provenance canonico por corrida (key = pid|flexible_redock|pid).
    # Emision post-dock, nunca tumba el redock.
    try:
        _escribir_provenance(work, pdb_id, center, vina_path)
    except Exception:
        pass

    return {
        "vina_best_score": scores[0],
        "pose_score_variance": float(np.var(scores)) if len(scores) > 1 else 0.0,
        "pose_score_range": scores[-1] - scores[0] if len(scores) > 1 else 0.0,
        "poses_passing_ratio": sum(1 for s in scores if s < -5.0) / len(scores),
    }, "ok"


_VERSION_VINA_CACHE: dict = {}


def _version_vina(vina_path: str) -> str:
    """Version del binario Vina (probe --version, cache por proceso)."""
    import re

    if vina_path not in _VERSION_VINA_CACHE:
        try:
            r = subprocess.run([vina_path, "--version"], capture_output=True,
                               text=True, timeout=10)
            m = re.search(r"v(\d+\.\d+(?:\.\d+)?)", r.stdout or "")
            _VERSION_VINA_CACHE[vina_path] = m.group(1) if m else "unknown"
        except Exception:
            _VERSION_VINA_CACHE[vina_path] = "unknown"
    return _VERSION_VINA_CACHE[vina_path]


def _escribir_provenance(work, pdb_id, center, vina_path) -> None:
    """Escribe provenance.json canonico (FND-06) en el workdir del complejo.

    Registro del contrato v1.1 con clave pid|flexible_redock|pid. El ligando
    es la conformacion cristalografica (conformer_id="crystal"): no hay
    generacion estocastica de conformeros, por eso seed_conformer="crystal";
    seed_docking es la semilla preregistrada de Vina (--seed 42).
    """
    registro = {
        "key": f"{pdb_id}|flexible_redock|{pdb_id}",
        "pid": pdb_id,
        "source": "flexible_redock",
        "file_stem": pdb_id,
        "seed_conformer": "crystal",
        "seed_docking": SEMILLA_VINA,
        "conformer_id": "crystal",
        "exhaustiveness": 8,
        "num_modes": 9,
        "box": {"center": [round(float(c), 3) for c in center],
                "size": [25.0, 25.0, 25.0],
                "method": "center_from_crystal_ligand"},
        "preparation": {
            "ligand": {"method": "meeko_molecule_preparation_conformacion_cristal",
                       "tool": "meeko", "version": "0.7.1",
                       "fallback": "openbabel_sdf2pdbqt"},
            "receptor": {"protonation": "pdb_original",
                         "tool": "openbabel_pdb2pdbqt_rigido",
                         "fallback": "meeko_cli_mk_prepare_receptor"},
        },
        "engine": {"name": "vina", "version": _version_vina(vina_path)},
        "experiment_id": "flexible_redock",
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    (work / "provenance.json").write_text(
        json.dumps(registro, indent=2, ensure_ascii=False), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(
        description="Re-dock PDBbind crystals with Vina for Group B features"
    )
    parser.add_argument("--data-dir", required=True, help="PDBbind data directory")
    parser.add_argument("--vina-path", default="vina", help="Path to Vina executable")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--output", default=None, help="Output JSON with results")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    cache_dir = data_dir / "vina_redock_cache"
    cache_dir.mkdir(exist_ok=True)

    work_dir = data_dir / "vina_redock_work"
    work_dir.mkdir(exist_ok=True)

    # Find complexes
    complexes = []
    for d in sorted(data_dir.iterdir()):
        if not d.is_dir():
            continue
        pdb = d / f"{d.name}_protein.pdb"
        sdf = d / f"{d.name}_ligand.sdf"
        if pdb.exists() and sdf.exists():
            cache_file = cache_dir / f"{d.name}.json"
            if not cache_file.exists():
                complexes.append((d.name, str(pdb), str(sdf)))

    print(f"Found {len(complexes)} complexes to re-dock")
    print(f"Estimated time: {len(complexes) * 5 / args.max_workers / 60:.1f} hours")
    print(f"Results will be cached in: {cache_dir}")

    n_success = 0
    n_failed = 0
    failures: dict[str, str] = {}
    t0 = time.time()

    with ProcessPoolExecutor(max_workers=args.max_workers) as executor:
        futures = {
            executor.submit(
                run_vina_redocking,
                pdb_id, prot, sdf, args.vina_path,
                str(work_dir / pdb_id),
            ): pdb_id
            for pdb_id, prot, sdf in complexes
        }

        for future in as_completed(futures):
            pdb_id = futures[future]
            try:
                result, reason = future.result(timeout=600)
                if result is not None:
                    cache_file = cache_dir / f"{pdb_id}.json"
                    cache_file.write_text(json.dumps(result))
                    n_success += 1
                else:
                    failures[pdb_id] = reason
                    n_failed += 1
            except Exception as e:
                failures[pdb_id] = f"worker_exception:{type(e).__name__}"
                n_failed += 1

            total = n_success + n_failed
            if total % 50 == 0 or total <= 5:
                elapsed = time.time() - t0
                rate = total / elapsed if elapsed > 0 else 0
                eta = (len(complexes) - total) / rate / 3600 if rate > 0 else 0
                print(
                    f"[{total}/{len(complexes)}] "
                    f"success={n_success} failed={n_failed} "
                    f"ETA={eta:.1f}h"
                )

    # Manifest de fallos con motivo (nunca silencioso)
    if failures:
        fail_path = cache_dir / "redock_failures.json"
        fail_path.write_text(json.dumps(failures, indent=2, sort_keys=True))
        print(f"Failures manifest: {fail_path} ({len(failures)} entradas)")

    print(f"\nDone: {n_success} success, {n_failed} failed")
    print(f"Total time: {(time.time() - t0) / 3600:.1f} hours")


if __name__ == "__main__":
    main()
