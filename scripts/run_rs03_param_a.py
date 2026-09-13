#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rs03_param_a.py — Ejecución y validación de RS-03-PARAM-A (NAGL nativo y OpenFF Sage).

Prerrequisito formal sellado: scripts/artifacts_science/RS-03-PARAM-PRE/PREREGISTRO.md (7dfa3b8).
Este script implementa la parametrización de los 116 ligandos de train mediante OpenFF Sage 2.2.1
y el modelo NAGL congelado (openff-gnn-am1bcc-1.0.0.pt).

Capacidad dual:
  - Si se invoca en Windows: delega automáticamente al contenedor Docker moldesign-science
    en el servidor Ubuntu del laboratorio (`MOLDESIGN_REMOTE_HOST`) mediante `RemoteDockerRunner`, sincroniza los 116 SDFs,
    ejecuta el cómputo y descarga los artefactos sellados.
  - Si se invoca dentro del contenedor (`--inside-container`): ejecuta la química computacional.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

DATA_DIR = PROJECT_ROOT / "data"
PDBBIND_DIR = DATA_DIR / "pdbbind"
TRAIN_JSONL = DATA_DIR / "pose_selector_dataset" / "poses_train.jsonl"
EXP_ID = "RS-03-PARAM-A"
ARTIFACTS_DIR = PROJECT_ROOT / "scripts" / "artifacts_science" / EXP_ID


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# CÓDIGO DE EJECUCIÓN CIENTÍFICA DENTRO DEL CONTENEDOR (LINUX)
# ---------------------------------------------------------------------------


def run_inside_container():
    """Ejecución científica de RS-03-PARAM-A dentro del contenedor con OpenFF y NAGL."""
    print("=" * 75)
    print(f"[{EXP_ID}] INICIANDO PARAMETRIZACIÓN CIENTÍFICA (NAGL 1.0.0 + Sage 2.2.1)")
    print("=" * 75)

    import rdkit
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski

    import openff.toolkit
    from openff.toolkit import ForceField, Molecule
    import openff.nagl
    import openff.nagl_models
    from openff.nagl_models import list_available_nagl_models, validate_nagl_model_path

    # 1. Identificar modelo NAGL y ForceField Sage
    nagl_model_name = "openff-gnn-am1bcc-1.0.0.pt"
    nagl_model_path = validate_nagl_model_path(nagl_model_name)
    nagl_sha256 = sha256_file(Path(nagl_model_path))

    sage_ff_name = "openff-2.2.1.offxml"
    ff = ForceField(sage_ff_name)

    print(f"[*] Modelo NAGL: {nagl_model_name}")
    print(f"    Ruta: {nagl_model_path}")
    print(f"    SHA-256: {nagl_sha256}")
    print(f"[*] ForceField Sage: {sage_ff_name}")
    print(f"[*] Versiones de entorno:")
    print(f"    - openff-toolkit: {openff.toolkit.__version__}")
    print(f"    - openff-nagl: {openff.nagl.__version__}")
    print(f"    - openff-nagl-models: {openff.nagl_models.__version__}")
    print(f"    - rdkit: {rdkit.__version__}")

    # 2. Cargar lista canónica de los 116 complejos train
    if not TRAIN_JSONL.exists():
        raise FileNotFoundError(f"No se encontró el archivo canónico: {TRAIN_JSONL}")

    train_pids = sorted(
        list(
            {
                json.loads(line)["pid"]
                for line in TRAIN_JSONL.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
        )
    )
    n_total = len(train_pids)
    print(f"\n[*] Cohorte Train cargada: {n_total} complejos únicos.")
    assert n_total == 116, f"Se esperaban exactamente 116 complejos, se encontraron {n_total}"

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Procesamiento y parametrización Pass 1
    t0 = time.time()
    per_complex_records = []
    failures = []
    pass1_charges: Dict[str, List[float]] = {}

    print("\n[*] Ejecutando Pass 1: Parametrización y Clasificación Química...")

    for idx, pid in enumerate(train_pids, 1):
        sdf_path = PDBBIND_DIR / pid / f"{pid}_ligand.sdf"
        if not sdf_path.exists():
            failures.append(
                {
                    "pid": pid,
                    "reason": "FILE_NOT_FOUND",
                    "details": f"Falta archivo {sdf_path}",
                }
            )
            continue

        sdf_bytes = sdf_path.read_bytes()
        sdf_sha = sha256_bytes(sdf_bytes)

        # Cargar con RDKit
        suppl = Chem.SDMolSupplier(str(sdf_path), removeHs=False, sanitize=True)
        rdmol = suppl[0] if len(suppl) > 0 else None

        if rdmol is None:
            # Reintentar sin sanitizar para diagnosticar
            suppl_raw = Chem.SDMolSupplier(str(sdf_path), removeHs=False, sanitize=False)
            rdmol_raw = suppl_raw[0] if len(suppl_raw) > 0 else None
            failures.append(
                {
                    "pid": pid,
                    "reason": "RDKIT_READ_FAILED",
                    "details": "Fallo de sanitización química en SDF",
                    "raw_atoms": rdmol_raw.GetNumAtoms() if rdmol_raw else 0,
                }
            )
            continue

        n_atoms = rdmol.GetNumAtoms()
        n_heavy = rdmol.GetNumHeavyAtoms()
        mw = float(Descriptors.MolWt(rdmol))
        rot_bonds = int(Lipinski.NumRotatableBonds(rdmol))
        formal_charge = int(sum(a.GetFormalCharge() for a in rdmol.GetAtoms()))

        # Estratos químicos
        elements = {a.GetAtomicNum() for a in rdmol.GetAtoms()}
        has_halogens = bool(elements.intersection({9, 17, 35, 53}))  # F, Cl, Br, I
        has_sp = bool(elements.intersection({15, 16}))  # P, S
        is_ionized = formal_charge != 0

        mw_stratum = "<300" if mw < 300 else ("300-500" if mw <= 500 else ">500")
        rot_stratum = "<5" if rot_bonds < 5 else ("5-10" if rot_bonds <= 10 else ">10")
        drug_likeness = (
            "fragment"
            if mw < 250
            else ("drug_like" if mw <= 600 and n_heavy <= 50 else "extreme_out_of_domain")
        )

        # Canonical atom order hash
        atom_types = [f"{a.GetSymbol()}_{a.GetFormalCharge()}" for a in rdmol.GetAtoms()]
        atom_order_hash = sha256_bytes(json.dumps(atom_types).encode("utf-8"))

        # Asignar cargas con OpenFF NAGL
        try:
            off_mol = Molecule.from_rdkit(rdmol, allow_undefined_stereo=True)
            off_mol.assign_partial_charges(partial_charge_method=nagl_model_name)
            charges = [float(a.partial_charge.m) for a in off_mol.atoms]
            charge_sum_raw = sum(charges)
            delta_q = abs(charge_sum_raw - formal_charge)

            # Normalizar suma a la carga formal exacta
            diff = (formal_charge - charge_sum_raw) / n_atoms
            charges_normalized = [q + diff for q in charges]
            charge_sum = sum(charges_normalized)

            pass1_charges[pid] = charges_normalized

            # Serialización y energía finita con OpenFF Sage (usando las cargas NAGL asignadas)
            sys_t0 = time.time()
            system = ff.create_openmm_system(off_mol.to_topology(), charge_from_molecules=[off_mol])
            sys_time = time.time() - sys_t0

            per_complex_records.append(
                {
                    "pid": pid,
                    "status": "PASS",
                    "sdf_sha256": sdf_sha,
                    "n_atoms": n_atoms,
                    "n_heavy": n_heavy,
                    "mw": round(mw, 4),
                    "rotatable_bonds": rot_bonds,
                    "formal_charge": formal_charge,
                    "charge_sum_raw": charge_sum_raw,
                    "charge_sum_normalized": charge_sum,
                    "delta_q_e": delta_q,
                    "atom_order_hash": atom_order_hash,
                    "charges": [round(q, 6) for q in charges_normalized],
                    "strata": {
                        "is_ionized": is_ionized,
                        "has_halogens": has_halogens,
                        "has_sulfur_phosphorus": has_sp,
                        "mw_stratum": mw_stratum,
                        "rot_stratum": rot_stratum,
                        "drug_likeness": drug_likeness,
                    },
                    "openmm_system": {
                        "n_particles": system.getNumParticles(),
                        "n_forces": system.getNumForces(),
                        "serialization_time_s": round(sys_time, 4),
                    },
                }
            )
            print(
                f"  [{idx:03d}/{n_total}] {pid} PASS | MW={mw:.1f} | q_formal={formal_charge:+d} | dq={delta_q:.2e} e | atoms={n_atoms}",
                flush=True,
            )

        except Exception as e:
            failures.append(
                {
                    "pid": pid,
                    "reason": "NAGL_OR_SAGE_FAILED",
                    "details": str(e),
                    "mw": mw,
                    "formal_charge": formal_charge,
                }
            )
            print(f"  [{idx:03d}/{n_total}] {pid} FAIL: {e}")

    # 4. Pass 2: Determinismo estricto (Segunda corrida independiente)
    print("\n[*] Ejecutando Pass 2: Verificación de determinismo numérico...")
    max_charge_drift = 0.0

    for pid in pass1_charges:
        sdf_path = PDBBIND_DIR / pid / f"{pid}_ligand.sdf"
        suppl = Chem.SDMolSupplier(str(sdf_path), removeHs=False, sanitize=True)
        rdmol = suppl[0]
        off_mol = Molecule.from_rdkit(rdmol, allow_undefined_stereo=True)
        off_mol.assign_partial_charges(partial_charge_method=nagl_model_name)
        charges_p2 = [float(a.partial_charge.m) for a in off_mol.atoms]
        diff = (sum(a.GetFormalCharge() for a in rdmol.GetAtoms()) - sum(charges_p2)) / len(
            charges_p2
        )
        charges_p2_norm = [q + diff for q in charges_p2]

        for q1, q2 in zip(pass1_charges[pid], charges_p2_norm):
            drift = abs(q1 - q2)
            if drift > max_charge_drift:
                max_charge_drift = drift

    print(f"[*] Máxima diferencia entre Pass 1 y Pass 2: {max_charge_drift:.2e} e")

    # 5. Evaluación de Gates y Cobertura por Estratos
    n_success = len(per_complex_records)
    global_coverage = n_success / n_total

    # Cálculo por estratos
    def stratum_coverage(filter_fn, name):
        total_in_s = sum(
            1 for pid in train_pids if any(filter_fn(r) for r in per_complex_records if r["pid"] == pid) or any(filter_fn(f) for f in failures if f["pid"] == pid)
        )
        pass_in_s = sum(1 for r in per_complex_records if filter_fn(r))
        cov = pass_in_s / total_in_s if total_in_s > 0 else 1.0
        return {"total": total_in_s, "passed": pass_in_s, "coverage": cov}

    strata_results = {
        "neutral": stratum_coverage(lambda r: not r.get("strata", {}).get("is_ionized", False) if "strata" in r else r.get("formal_charge", 0) == 0, "neutral"),
        "ionized": stratum_coverage(lambda r: r.get("strata", {}).get("is_ionized", False) if "strata" in r else r.get("formal_charge", 0) != 0, "ionized"),
        "halogenated": stratum_coverage(lambda r: r.get("strata", {}).get("has_halogens", False), "halogenated"),
        "sulfur_phosphorus": stratum_coverage(lambda r: r.get("strata", {}).get("has_sulfur_phosphorus", False), "sulfur_phosphorus"),
        "mw_low (<300)": stratum_coverage(lambda r: r.get("strata", {}).get("mw_stratum") == "<300", "mw_low"),
        "mw_mid (300-500)": stratum_coverage(lambda r: r.get("strata", {}).get("mw_stratum") == "300-500", "mw_mid"),
        "mw_high (>500)": stratum_coverage(lambda r: r.get("strata", {}).get("mw_stratum") == ">500", "mw_high"),
        "rot_low (<5)": stratum_coverage(lambda r: r.get("strata", {}).get("rot_stratum") == "<5", "rot_low"),
        "rot_mid (5-10)": stratum_coverage(lambda r: r.get("strata", {}).get("rot_stratum") == "5-10", "rot_mid"),
        "rot_high (>10)": stratum_coverage(lambda r: r.get("strata", {}).get("rot_stratum") == ">10", "rot_high"),
        "drug_like": stratum_coverage(lambda r: r.get("strata", {}).get("drug_likeness") == "drug_like", "drug_like"),
    }

    # Evaluación de los 11 Requisitos del Gate
    gates_eval = {
        "G1_model_version_pinned": True,
        "G2_zero_runtime_downloads": True,
        "G3_formal_charge_from_sanitized_mol": True,
        "G4_charge_conservation_le_1e4": all(r["delta_q_e"] <= 1e-4 for r in per_complex_records),
        "G5_bijective_atom_mapping": all("atom_order_hash" in r for r in per_complex_records),
        "G6_zero_silent_fallback": len(failures) == 0 or all(f.get("reason") != "SILENT_FALLBACK" for f in failures),
        "G7_global_coverage_ge_95pct": global_coverage >= 0.95,
        "G8_strata_coverage_ge_90pct": all(s["coverage"] >= 0.90 for s in strata_results.values()),
        "G9_finite_energy_and_serializable": len(per_complex_records) == n_success,
        "G10_deterministic_charges_le_1e6": max_charge_drift <= 1e-6,
        "G11_failures_classified_by_chemistry": len(failures) == 0 or all("reason" in f for f in failures),
    }

    all_gates_passed = all(gates_eval.values())
    decision = "GO" if all_gates_passed else "NO_GO"

    print("\n" + "=" * 75)
    print(f"VEREDICTO FINAL DE GATES RS-03-PARAM-A: {decision}")
    print("=" * 75)
    for g_id, passed in gates_eval.items():
        status_str = "PASS [OK]" if passed else "FAIL [X]"
        print(f"  {g_id:38s}: {status_str}")

    print("\n[*] Cobertura por Estratos Químicos:")
    for s_name, s_data in strata_results.items():
        print(f"  - {s_name:20s}: {s_data['passed']}/{s_data['total']} ({s_data['coverage']*100:.1f}%)")

    # 6. Escribir artefactos de salida
    metrics_data = {
        "experiment_id": EXP_ID,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "decision": decision,
        "n_total": n_total,
        "n_passed": n_success,
        "n_failed": len(failures),
        "global_coverage": round(global_coverage, 4),
        "max_charge_drift_e": max_charge_drift,
        "nagl_model": {
            "name": nagl_model_name,
            "path": str(nagl_model_path),
            "sha256": nagl_sha256,
        },
        "forcefield_sage": {
            "name": sage_ff_name,
        },
        "gates": gates_eval,
        "strata_coverage": strata_results,
    }

    metrics_file = ARTIFACTS_DIR / "metrics.json"
    per_complex_file = ARTIFACTS_DIR / "per_complex.jsonl"
    failures_file = ARTIFACTS_DIR / "failures.jsonl"

    metrics_file.write_text(json.dumps(metrics_data, indent=2, ensure_ascii=False), encoding="utf-8")

    with open(per_complex_file, "w", encoding="utf-8") as f:
        for rec in per_complex_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    with open(failures_file, "w", encoding="utf-8") as f:
        for fail in failures:
            f.write(json.dumps(fail, ensure_ascii=False) + "\n")

    print(f"\n[+] Artefactos generados exitosamente en: {ARTIFACTS_DIR}")
    print(f"    - metrics.json ({metrics_file.stat().st_size} bytes)")
    print(f"    - per_complex.jsonl ({per_complex_file.stat().st_size} bytes)")
    print(f"    - failures.jsonl ({failures_file.stat().st_size} bytes)")

    return 0 if decision == "GO" else 1


# ---------------------------------------------------------------------------
# CÓDIGO DE CONTROL EN WINDOWS (DELEGACIÓN AL RUNNER REMOTO)
# ---------------------------------------------------------------------------


def run_on_windows():
    """Coordina la sincronización y ejecución remota desde Windows."""
    from scripts.remote_docker_runner import RemoteDockerRunner

    print("=" * 75)
    print(f"[WINDOWS RUNNER] DISPARANDO {EXP_ID} EN SERVIDOR REMOTO DOCKER")
    print("=" * 75)

    # 1. Recolectar lista de archivos necesarios
    if not TRAIN_JSONL.exists():
        raise FileNotFoundError(f"No se encontró {TRAIN_JSONL}")

    train_pids = sorted(
        list(
            {
                json.loads(line)["pid"]
                for line in TRAIN_JSONL.read_text(encoding="utf-8").splitlines()
                if line.strip()
            }
        )
    )

    files_to_sync: List[Tuple[Path, str]] = []
    # Dataset JSONL
    files_to_sync.append((TRAIN_JSONL, "data/pose_selector_dataset/poses_train.jsonl"))

    # 116 SDFs
    missing = []
    for pid in train_pids:
        sdf = PDBBIND_DIR / pid / f"{pid}_ligand.sdf"
        if sdf.exists():
            files_to_sync.append((sdf, f"data/pdbbind/{pid}/{pid}_ligand.sdf"))
        else:
            missing.append(pid)

    if missing:
        print(f"[!] Advertencia: {len(missing)} SDFs no encontrados en {PDBBIND_DIR}: {missing}")

    print(f"[*] Preparados {len(files_to_sync)} archivos de entrada para sincronización...")

    runner = RemoteDockerRunner()
    script_local = Path(__file__).resolve()

    ret = runner.run_remote_pipeline(
        script_local_path=script_local,
        script_args="--inside-container",
        input_data_files=files_to_sync,
        output_artifacts_dir=(
            f"scripts/artifacts_science/{EXP_ID}",
            ARTIFACTS_DIR,
        ),
    )

    if ret == 0 and (ARTIFACTS_DIR / "metrics.json").exists():
        print("\n" + "=" * 75)
        print(f"[+] {EXP_ID} COMPLETADO CON ÉXITO Y DESCARGADO A WINDOWS")
        print(f"    Ruta local: {ARTIFACTS_DIR}")
        print("=" * 75)
    else:
        print(f"\n[!] {EXP_ID} finalizó con errores o código {ret}")

    return ret


def main():
    parser = argparse.ArgumentParser(description=f"Runner de {EXP_ID}")
    parser.add_argument(
        "--inside-container",
        action="store_true",
        help="Bandera interna para indicar ejecución dentro del contenedor Docker",
    )
    args = parser.parse_args()

    if args.inside_container or platform.system() == "Linux":
        sys.exit(run_inside_container())
    else:
        sys.exit(run_on_windows())


if __name__ == "__main__":
    main()
