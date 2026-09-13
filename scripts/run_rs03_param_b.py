#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_rs03_param_b.py — RS-03-PARAM-B: referencia AM1-BCC estratificada (AmberTools).

Prerrequisito formal sellado:
  - scripts/artifacts_science/RS-03-PARAM-B-PRE/PREREGISTRO.md (sellado GO, 147abb1)
  - scripts/artifacts_science/RS-03-PARAM-PRE/PREREGISTRO.md (maestro, 7dfa3b8)

Objetivo: caracterizar las cargas NAGL nativas (RS-03-PARAM-A, sellado GO 93541c9) frente
a la referencia AM1-BCC (AmberTools antechamber + sqm) en el contenedor Ubuntu
`moldesign-science:latest`, SIN usarse como selector: PROHIBIDO seleccionar NAGL por RMSD
ni Top-1 (PRE maestro §4). Solo caracterización descriptiva estratificada.

Capacidad dual (patrón RS-03-PARAM-A):
  - Windows: delega al contenedor via RemoteDockerRunner (sincroniza SDF y A/per_complex,
    ejecuta el cómputo, descarga artefactos sellados).
  - Contenedor (--inside-container): ejecuta la química AM1-BCC y la comparación.
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

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_ID = "RS-03-PARAM-B"

# ---------------------------------------------------------------------------
# Modo contenedor: cómputo AM1-BCC y comparación con NAGL
# ---------------------------------------------------------------------------


def _inside_container(workspace: Path, pids_filter: Optional[List[str]] = None,
                      timeout_s: int = 300, out_name: str = EXPERIMENT_ID) -> int:
    """Ejecuta la química AM1-BCC (AmberTools) y compara con NAGL (desde A).

    pids_filter: si no es None, procesa solo esos pids (ejecución por shards
    independientes; los resultados se fusionan después por unión de pid).
    out_name: nombre del directorio de salida bajo scripts/artifacts_science/.
    Cada shard escribe en su propio directorio: NUNCA se sobreescribe el
    resultado de otro shard (incidencia de 2026-08-17, ver LECTURA.md).
    """
    import subprocess
    import tempfile

    import numpy as np
    from rdkit import Chem
    from rdkit.Chem import AllChem, Descriptors, Lipinski

    import openmm
    import openmm.unit as ommunit
    from openff.toolkit import ForceField, Molecule
    from openff.units import unit as offunit

    # e·Å -> Debye
    EA_TO_DEBYE = 4.803204712

    # antechamber -at gaff escribe tipos GAFF (c3, hn, oh, py, cl, br...) en la
    # columna 6 del mol2; solo cl/br son elementos de dos letras.
    _GAFF_TWO_LETTER = {"cl": "Cl", "br": "Br"}

    def _elem_from_atom_type(atom_type: str) -> str:
        base = atom_type.split(".")[0]  # tolera también tipos SYBYL (C.3)
        low = base.lower()
        if low[:2] in _GAFF_TWO_LETTER:
            return _GAFF_TWO_LETTER[low[:2]]
        return base[0].upper()

    def sha256_bytes(b: bytes) -> str:
        h = hashlib.sha256()
        h.update(b)
        return h.hexdigest()

    def load_jsonl(path: Path) -> List[Dict[str, Any]]:
        rows = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rows.append(json.loads(line))
        return rows

    pdbbind_dir = workspace / "data" / "pdbbind"
    a_dir = workspace / "scripts" / "artifacts_science" / "RS-03-PARAM-A"
    out_dir = workspace / "scripts" / "artifacts_science" / out_name
    out_dir.mkdir(parents=True, exist_ok=True)

    # Cohorte = 116 ligandos train que A parametrizó con éxito (status PASS)
    a_rows = [r for r in load_jsonl(a_dir / "per_complex.jsonl") if r.get("status") == "PASS"]
    if pids_filter is not None:
        wanted = set(pids_filter)
        a_rows = [r for r in a_rows if r["pid"] in wanted]
        print(f"[*] Filtro activo: {len(a_rows)} ligandos de {len(wanted)} pids solicitados.")
    print(f"[*] Cohorte (de A PASS): {len(a_rows)} ligandos.")

    # Detectar binarios AmberTools
    def _bin(name: str) -> Optional[str]:
        try:
            r = subprocess.run(["which", name], capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except Exception:
            pass
        return None

    antechamber = _bin("antechamber")
    sqm = _bin("sqm")
    print(f"[*] AmberTools: antechamber={antechamber} sqm={sqm}")
    if not antechamber or not sqm:
        print("[!] AmberTools no encontrado en el contenedor. Abortando.")
        return 2

    # Sage 2.2.1: mismo force field que A; solo difieren las cargas (PRE-B §3)
    sage_ff_name = "openff-2.2.1.offxml"
    ff = ForceField(sage_ff_name)
    print(f"[*] ForceField Sage: {sage_ff_name} | OpenMM {openmm.version.version}")

    def _dipole_debye(charges: List[float], coords_ang) -> float:
        """Dipolo de cargas puntuales sobre la geometría del SDF, origen en el
        centro geométrico de masa-neutral (origen documentado: necesario porque
        para especies ionizadas el dipolo depende del origen)."""
        q = np.asarray(charges, dtype=float)
        r = np.asarray(coords_ang, dtype=float)
        origin = r.mean(axis=0)
        mu = ((r - origin) * q[:, None]).sum(axis=0)
        return float(np.linalg.norm(mu) * EA_TO_DEBYE)

    def _single_point_kjmol(off_mol, charges: List[float], coords_ang) -> Dict[str, Any]:
        """Energía potencial de punto único (vacío) con Sage 2.2.1 y las cargas
        dadas. Plataforma Reference: determinista y monohilo (PRE-B §5.6)."""
        mol = Molecule(off_mol)
        mol.partial_charges = np.asarray(charges, dtype=float) * offunit.elementary_charge
        system = ff.create_openmm_system(mol.to_topology(), charge_from_molecules=[mol])
        integrator = openmm.VerletIntegrator(1.0 * ommunit.femtoseconds)
        platform = openmm.Platform.getPlatformByName("Reference")
        context = openmm.Context(system, integrator, platform)
        try:
            context.setPositions(np.asarray(coords_ang, dtype=float) * 0.1 * ommunit.nanometer)
            energy = context.getState(getEnergy=True).getPotentialEnergy().value_in_unit(
                ommunit.kilojoule_per_mole)
        finally:
            del context
            del integrator
        return {
            "energy_kjmol": round(float(energy), 6),
            "finite": bool(np.isfinite(energy)),
            "n_particles": system.getNumParticles(),
            "n_forces": system.getNumForces(),
        }

    per_complex: List[Dict[str, Any]] = []
    failures: List[Dict[str, Any]] = []
    strata_stats: Dict[str, Dict[str, Any]] = {}

    def _acc_strata(rec: Dict[str, Any], key: str, value: str, dq_mean: float, dq_max: float):
        s = strata_stats.setdefault(key, {})
        bucket = s.setdefault(value, {"n": 0, "sum_abs_dq": 0.0, "max_abs_dq": 0.0})
        bucket["n"] += 1
        bucket["sum_abs_dq"] += dq_mean
        bucket["max_abs_dq"] = max(bucket["max_abs_dq"], dq_max)

    t0 = time.time()
    for idx, rec in enumerate(a_rows, 1):
        pid = rec["pid"]
        sdf_path = pdbbind_dir / pid / f"{pid}_ligand.sdf"
        nagl_charges = rec.get("charges", [])
        formal_charge = int(rec.get("formal_charge", 0))
        n_atoms = int(rec.get("n_atoms", 0))
        strata = rec.get("strata", {})

        if not sdf_path.exists():
            failures.append({"pid": pid, "reason": "FILE_NOT_FOUND", "details": str(sdf_path)})
            continue
        if not nagl_charges:
            failures.append({"pid": pid, "reason": "NO_NAGL_CHARGES_FROM_A"})
            continue

        try:
            suppl = Chem.SDMolSupplier(str(sdf_path), removeHs=False, sanitize=True)
            rdmol = suppl[0]
            if rdmol is None:
                failures.append({"pid": pid, "reason": "RDKIT_READ_FAILED"})
                continue
            n_hvy = rdmol.GetNumHeavyAtoms()

            # AM1-BCC con antechamber: SDF -> mol2 con cargas AM1-BCC
            with tempfile.TemporaryDirectory() as td:
                td_p = Path(td)
                in_sdf = td_p / f"{pid}_ligand.sdf"
                out_mol2 = td_p / f"{pid}.mol2"
                in_sdf.write_bytes(sdf_path.read_bytes())
                cmd = [
                    antechamber,
                    "-i", str(in_sdf), "-fi", "sdf",
                    "-o", str(out_mol2), "-fo", "mol2",
                    "-c", "bcc",  # AM1-BCC
                    "-nc", str(formal_charge),  # carga neta del ligando sanitizado
                    "-s", "2",
                ]
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, cwd=td)
                if r.returncode != 0 or not out_mol2.exists():
                    failures.append(
                        {
                            "pid": pid,
                            "reason": "ANTECHAMBER_FAILED",
                            "details": (r.stderr or r.stdout)[-500:],
                        }
                    )
                    continue

                # Parsear el mol2 (sección @<TRIPOS>ATOM): cargas AM1-BCC (col 9),
                # coordenadas (cols 3-5) y tipo de átomo GAFF (col 6).
                am1bcc_charges: List[float] = []
                mol2_elements: List[str] = []
                mol2_coords: List[List[float]] = []
                in_atom = False
                for line in out_mol2.read_text(errors="replace").splitlines():
                    if line.startswith("@<TRIPOS>ATOM"):
                        in_atom = True
                        continue
                    if line.startswith("@<TRIPOS>") and not line.startswith("@<TRIPOS>ATOM"):
                        in_atom = False
                    if in_atom and line.strip():
                        parts = line.split()
                        if len(parts) >= 9:
                            try:
                                am1bcc_charges.append(float(parts[8]))
                                mol2_coords.append([float(parts[2]), float(parts[3]), float(parts[4])])
                            except ValueError:
                                continue
                            mol2_elements.append(_elem_from_atom_type(parts[5]))

            if len(am1bcc_charges) != len(nagl_charges):
                failures.append(
                    {
                        "pid": pid,
                        "reason": "CHARGE_COUNT_MISMATCH",
                        "nagl": len(nagl_charges),
                        "am1bcc": len(am1bcc_charges),
                    }
                )
                continue

            # Mapeo biyectivo (PRE-B §5.3): antechamber debe preservar el orden
            # atómico del SDF. Se verifica por elemento Y por coordenadas contra
            # el mol sanitizado que usó A; si no coincide, la comparación por
            # índice sería inválida -> FAIL (nunca comparación silenciosa).
            sdf_elements = [a.GetSymbol() for a in rdmol.GetAtoms()]
            coords = rdmol.GetConformer().GetPositions()
            if sdf_elements != mol2_elements:
                mism = [
                    {"i": i, "sdf": s, "mol2": m}
                    for i, (s, m) in enumerate(zip(sdf_elements, mol2_elements))
                    if s != m
                ][:10]
                failures.append(
                    {"pid": pid, "reason": "ATOM_ORDER_MISMATCH_ELEMENT", "details": mism}
                )
                continue
            max_dr = float(np.abs(np.asarray(mol2_coords) - np.asarray(coords)).max())
            if max_dr > 5e-3:
                failures.append(
                    {"pid": pid, "reason": "ATOM_ORDER_MISMATCH_COORDS",
                     "max_dr_angstrom": round(max_dr, 6)}
                )
                continue

            # Comparación por átomo |q_NAGL - q_AM1-BCC|
            abs_dq = [abs(float(n) - float(a)) for n, a in zip(nagl_charges, am1bcc_charges)]
            dq_mean = sum(abs_dq) / len(abs_dq)
            dq_max = max(abs_dq)
            sum_nagl = float(sum(nagl_charges))
            sum_am1bcc = float(sum(am1bcc_charges))
            delta_mol_charge = abs(sum_nagl - sum_am1bcc)

            # Dipolo de cargas puntuales sobre la geometría del SDF (PRE-B §5.5)
            dipolo_nagl = _dipole_debye([float(q) for q in nagl_charges], coords)
            dipolo_am1bcc = _dipole_debye(am1bcc_charges, coords)

            # Estabilidad de energías con Sage 2.2.1 (PRE-B §5.6): el sistema
            # cargado con AM1-BCC debe serializar y dar energía finita. Se calcula
            # también con las cargas NAGL de A para caracterizar el efecto.
            off_mol = Molecule.from_rdkit(rdmol, allow_undefined_stereo=True)
            e_am1bcc = _single_point_kjmol(off_mol, am1bcc_charges, coords)
            e_nagl = _single_point_kjmol(off_mol, [float(q) for q in nagl_charges], coords)

            row = {
                "pid": pid,
                "status": "PASS",
                "sdf_sha256": sha256_bytes(sdf_path.read_bytes()),
                "n_atoms": n_atoms,
                "n_heavy": n_hvy,
                "formal_charge": formal_charge,
                "sum_q_nagl": round(sum_nagl, 6),
                "sum_q_am1bcc": round(sum_am1bcc, 6),
                "delta_mol_charge_e": round(delta_mol_charge, 6),
                "delta_q_am1bcc_vs_formal_e": round(abs(sum_am1bcc - formal_charge), 6),
                "abs_dq_mean_e": round(dq_mean, 6),
                "abs_dq_max_e": round(dq_max, 6),
                "atom_order_match": True,
                "atom_order_max_dr_angstrom": round(max_dr, 6),
                "dipolo_debye": round(dipolo_am1bcc, 6),
                "dipolo_nagl_debye": round(dipolo_nagl, 6),
                "delta_dipolo_debye": round(abs(dipolo_am1bcc - dipolo_nagl), 6),
                "energy_am1bcc_kjmol": e_am1bcc["energy_kjmol"],
                "energy_nagl_kjmol": e_nagl["energy_kjmol"],
                "delta_energy_kjmol": round(
                    e_am1bcc["energy_kjmol"] - e_nagl["energy_kjmol"], 6),
                "energy_finite": bool(e_am1bcc["finite"] and e_nagl["finite"]),
                "openmm_system": {
                    "n_particles": e_am1bcc["n_particles"],
                    "n_forces": e_am1bcc["n_forces"],
                },
                "charges_am1bcc": [round(q, 6) for q in am1bcc_charges],
                "strata": strata,
            }
            per_complex.append(row)

            # Estratificación
            _acc_strata(strata_stats, "is_ionized", str(bool(strata.get("is_ionized"))), dq_mean, dq_max)
            _acc_strata(strata_stats, "has_halogens", str(bool(strata.get("has_halogens"))), dq_mean, dq_max)
            _acc_strata(strata_stats, "has_sulfur_phosphorus", str(bool(strata.get("has_sulfur_phosphorus"))), dq_mean, dq_max)
            _acc_strata(strata_stats, "mw_stratum", strata.get("mw_stratum", "?"), dq_mean, dq_max)
            _acc_strata(strata_stats, "rot_stratum", strata.get("rot_stratum", "?"), dq_mean, dq_max)
            _acc_strata(strata_stats, "drug_likeness", strata.get("drug_likeness", "?"), dq_mean, dq_max)

            print(
                f"  [{idx:03d}/{len(a_rows)}] {pid} PASS | dq_mean={dq_mean:.3f} "
                f"dq_max={dq_max:.3f} | mu_am1bcc={dipolo_am1bcc:.2f} D "
                f"mu_nagl={dipolo_nagl:.2f} D | dE={row['delta_energy_kjmol']:.2f} kJ/mol",
                flush=True,
            )

        except subprocess.TimeoutExpired:
            failures.append({"pid": pid, "reason": f"ANTECHAMBER_TIMEOUT_{timeout_s}S"})
        except Exception as e:
            failures.append({"pid": pid, "reason": "AM1BCC_FAILED", "details": str(e)})

    # Agregar estadísticas por estrato (media)
    for key, buckets in strata_stats.items():
        for value, b in buckets.items():
            b["mean_abs_dq_e"] = round(b["sum_abs_dq"] / b["n"], 6) if b["n"] else 0.0
            b.pop("sum_abs_dq", None)

    n_pass = len(per_complex)
    n_fail = len(failures)
    global_mean_dq = (
        round(sum(r["abs_dq_mean_e"] for r in per_complex) / n_pass, 6) if n_pass else 0.0
    )
    global_max_dq = max((r["abs_dq_max_e"] for r in per_complex), default=0.0)

    n_energy_finite = sum(1 for r in per_complex if r.get("energy_finite"))
    mean_delta_dipolo = (
        round(sum(r["delta_dipolo_debye"] for r in per_complex) / n_pass, 6) if n_pass else 0.0
    )
    max_delta_dipolo = max((r["delta_dipolo_debye"] for r in per_complex), default=0.0)
    mean_abs_delta_e = (
        round(sum(abs(r["delta_energy_kjmol"]) for r in per_complex) / n_pass, 6) if n_pass else 0.0
    )
    max_abs_delta_e = max((abs(r["delta_energy_kjmol"]) for r in per_complex), default=0.0)
    max_dq_formal_am1bcc = max(
        (r["delta_q_am1bcc_vs_formal_e"] for r in per_complex), default=0.0)

    metrics = {
        "experiment_id": EXPERIMENT_ID,
        "shard_out_name": out_name,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": round(time.time() - t0, 2),
        "decision": "GO",  # referencia descriptiva: no selector
        "cohorte": "116 ligandos train (PASS de RS-03-PARAM-A)",
        "n_total": len(a_rows),
        "n_passed": n_pass,
        "n_failed": n_fail,
        "coverage_vs_a": round(n_pass / len(a_rows), 4) if a_rows else 0.0,
        "global_abs_dq_mean_e": global_mean_dq,
        "global_abs_dq_max_e": round(global_max_dq, 6),
        "max_delta_q_am1bcc_vs_formal_e": round(max_dq_formal_am1bcc, 6),
        "n_energy_finite": n_energy_finite,
        "n_atom_order_match": n_pass,
        "mean_delta_dipolo_debye": mean_delta_dipolo,
        "max_delta_dipolo_debye": round(max_delta_dipolo, 6),
        "mean_abs_delta_energy_kjmol": mean_abs_delta_e,
        "max_abs_delta_energy_kjmol": round(max_abs_delta_e, 6),
        "strata_stats": strata_stats,
        "nota_selector": "AM1-BCC es referencia estratificada, no verdad absoluta. PROHIBIDO seleccionar NAGL por RMSD ni Top-1 (PRE maestro §4). Sin gate de aceptacion/rechazo de NAGL.",
        "antechamber": antechamber,
        "sqm": sqm,
        "garantia_cuarentena": "cero val40/test/D-RC-CONFIRM; cohorte = 116 train PASS de A",
    }

    _atomic_write(out_dir / "metrics.json", json.dumps(metrics, ensure_ascii=False, indent=1) + "\n")
    with open(out_dir / "per_complex.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in per_complex:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(out_dir / "failures.jsonl", "w", encoding="utf-8", newline="\n") as f:
        for r in failures:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n[*] B completado: {n_pass} PASS, {n_fail} FAIL, dq_mean global={global_mean_dq} e")
    return 0 if n_pass > 0 else 3


def _atomic_write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Modo Windows: delegación al contenedor
# ---------------------------------------------------------------------------


def _delegar_contenedor() -> int:
    from remote_docker_runner import RemoteDockerRunner

    ws = Path(os.environ.get("MOLDESIGN_REMOTE_WORKSPACE", "/home/srcacahuate619/moldesign-env"))
    a_dir_rel = "scripts/artifacts_science/RS-03-PARAM-A"
    b_dir_rel = f"scripts/artifacts_science/{EXPERIMENT_ID}"

    # Inputs: los 116 SDF train + per_complex de A (cargas NAGL)
    train_jsonl = PROJECT_ROOT / "data" / "pose_selector_dataset" / "poses_train.jsonl"
    train_pids = sorted(
        json.loads(line)["pid"]
        for line in train_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )
    input_files: List[Tuple[Path, str]] = []
    for pid in train_pids:
        sdf = PROJECT_ROOT / "data" / "pdbbind" / pid / f"{pid}_ligand.sdf"
        input_files.append((sdf, f"data/pdbbind/{pid}/{pid}_ligand.sdf"))
    a_per_complex = PROJECT_ROOT / "scripts" / "artifacts_science" / "RS-03-PARAM-A" / "per_complex.jsonl"
    input_files.append((a_per_complex, f"{a_dir_rel}/per_complex.jsonl"))

    with RemoteDockerRunner() as runner:
        return runner.run_remote_pipeline(
            script_local_path=Path(__file__).resolve(),
            script_args="--inside-container",
            input_data_files=input_files,
            output_artifacts_dir=(b_dir_rel, PROJECT_ROOT / "scripts" / "artifacts_science" / EXPERIMENT_ID),
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="RS-03-PARAM-B: referencia AM1-BCC estratificada")
    parser.add_argument("--inside-container", action="store_true", help="Ejecutar química dentro del contenedor")
    parser.add_argument("--workspace", default="/workspace", help="Workspace dentro del contenedor")
    parser.add_argument("--pids", nargs="*", default=None, help="Solo estos pids (shard)")
    parser.add_argument("--pids-file", default=None, help="Fichero con un pid por línea (shard)")
    parser.add_argument("--out-name", default=EXPERIMENT_ID,
                        help="Directorio de salida bajo scripts/artifacts_science/ (un shard = un directorio)")
    parser.add_argument("--timeout", type=int, default=300, help="Timeout por ligando en segundos (default 300)")
    args = parser.parse_args()

    pids = args.pids
    if args.pids_file:
        pids = [
            line.strip()
            for line in Path(args.pids_file).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    if args.inside_container or platform.system() != "Windows":
        return _inside_container(Path(args.workspace), pids_filter=pids,
                                 timeout_s=args.timeout, out_name=args.out_name)
    return _delegar_contenedor()


if __name__ == "__main__":
    sys.exit(main())
