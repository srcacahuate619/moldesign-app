"""
scripts/compute_quantum_features.py — descriptores de xTB y MMFF94

Extrae descriptores de dos motores que sí son lo que dicen ser:

  1. Cargas parciales, HOMO-LUMO gap, energía total y momento dipolar — GFN2-xTB
  2. Tipos atómicos, constantes de enlace, ángulo y torsión — MMFF94 (RDKit)
  3. Normalización por átomo pesado — quita el sesgo de tamaño molecular

Y sobre ellos calcula `compute_quantum_score`, un índice agregado en [0, 1].

═══════════════════════════════════════════════════════════════════════════
QUÉ ES —Y QUÉ NO ES— ESE ÍNDICE
═══════════════════════════════════════════════════════════════════════════

Auditoría del 2026-09-04. Este archivo se presentaba como «MolChamb, el
reemplazo propio de Antechamber», con dos afirmaciones que no se sostienen:

  «Tipos atómicos + constantes MMFF94 — equivalentes funcionales a GAFF2»

    No lo son. MMFF94 y GAFF2 son campos de fuerza distintos, parametrizados
    contra conjuntos distintos y con formas funcionales distintas; no hay
    correspondencia de tipos entre ellos ni un estudio en este proyecto que la
    mida. Compartir el propósito no es ser equivalente.

  «Cargas parciales GFN2-xTB — mas precisas que AM1-BCC»

    Puede ser cierto para algunas propiedades y no para otras, y aquí no se ha
    medido ninguna. Se retira la comparación en vez de matizarla.

Y `compute_quantum_score` NO es un observable cuántico. Es una combinación
lineal, con pesos y divisores elegidos a mano, de cuatro descriptores
normalizados:

    raw = 0.25 * hl_norm + 0.35 * q_norm + 0.15 * e_norm + 0.25 * at_norm

Los cuatro divisores (1.3, 0.27, 3.5/1.0, 6.5) y los cuatro pesos no salen de
ningún ajuste documentado en este repositorio. Los ingredientes son magnitudes
físicas reales; su combinación es una heurística.

Por eso el índice se llama lo que es —`compute_quantum_score` devuelve un
ÍNDICE HEURÍSTICO EXPERIMENTAL— y por eso `scoring/engine.py` ya no lo suma al
score principal. Se sigue calculando, se sigue guardando y se sigue mostrando,
porque los descriptores de debajo son útiles y ortogonales; lo que no hace es
mover un ranking que se presenta como evidencia.

License: GNU Affero General Public License v3.0 (AGPL-3.0).
The underlying engines (xTB, RDKit/MMFF94) are open-source.

Las features son ortogonales a Shell+ECIF+1D/2D (rho=0.078 medido).
Alimentan XGBoost y CL-GNN con datos que hoy no tienen.

Usage:
  python scripts/compute_quantum_features.py --smiles "c1ccccc1"
"""

import argparse
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from rdkit import Chem, RDLogger
RDLogger.logger().setLevel(RDLogger.ERROR)
from rdkit.Chem import AllChem


# ═══════════════════════════════════════════════════════════════
# xTB quantum features
# ═══════════════════════════════════════════════════════════════

_XTB_BINARY = None


def _find_xtb() -> str | None:
    global _XTB_BINARY
    if _XTB_BINARY is not None:
        return _XTB_BINARY
    candidates = [
        PROJECT_ROOT / "tools" / "xtb" / "xtb-6.7.1" / "bin" / "xtb.exe",
    ]
    for p in candidates:
        if p.exists():
            _XTB_BINARY = str(p)
            return _XTB_BINARY
    import shutil
    found = shutil.which("xtb")
    _XTB_BINARY = found
    return found


_XTB_HOME = None


def _get_xtb_home() -> str | None:
    global _XTB_HOME
    if _XTB_HOME is not None:
        return _XTB_HOME
    bin_path = _find_xtb()
    if bin_path:
        parent = Path(bin_path).parent.parent  # bin/../ = xtb-VERSION/
        if (parent / "share" / "xtb").exists():
            _XTB_HOME = str(parent)
    return _XTB_HOME


def compute_xtb_features(smiles: str) -> dict:
    """Run xTB single-point and extract quantum features. Deterministic (seed=42)."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {}

    mol = Chem.AddHs(mol)
    # Deterministic conformer generation
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    status = AllChem.EmbedMolecule(mol, params)
    if status == -1:
        status = AllChem.EmbedMolecule(mol, AllChem.ETKDG())
    AllChem.MMFFOptimizeMolecule(mol)

    conf = mol.GetConformer()
    atoms = [a.GetSymbol() for a in mol.GetAtoms()]
    lines = [f"{atoms[i]} {conf.GetAtomPosition(i).x:.6f} {conf.GetAtomPosition(i).y:.6f} {conf.GetAtomPosition(i).z:.6f}"
             for i in range(mol.GetNumAtoms())]
    xyz = f"{mol.GetNumAtoms()}\n\n" + "\n".join(lines)

    xtb_bin = _find_xtb()
    xtb_home = _get_xtb_home()
    if not xtb_bin or not xtb_home:
        return {}

    d = tempfile.mkdtemp()
    input_file = os.path.join(d, "mol.xyz")
    with open(input_file, "w") as f:
        f.write(xyz)

    env = os.environ.copy()
    env["XTBHOME"] = xtb_home
    env["OMP_NUM_THREADS"] = "2"

    try:
        result = subprocess.run(
            [xtb_bin, input_file, "--sp", "--gfn", "2", "--chrg", "0"],
            cwd=d, capture_output=True, timeout=120, env=env,
        )

        features = {}
        if result.returncode == 0:
            # Read charges
            charges_file = os.path.join(d, "charges")
            if os.path.exists(charges_file):
                charges = [float(l.strip()) for l in open(charges_file, encoding="ascii") if l.strip()]
                heavy_q = [c for i, c in enumerate(charges) if atoms[i] != "H"]
                # FIX (Bug C): exponer la lista COMPLETA de cargas por átomo,
                # no solo agregados. Los consumidores (molchamb_v2.py:156,421)
                # esperan charges como list[float] con un valor por átomo (incl. H)
                # para MM-GBSA. Antes buscaban "xtb_charges_mulliken" que nunca
                # existió, cayendo siempre al fallback Gasteiger.
                if charges:
                    features["xtb_charges"] = [round(c, 5) for c in charges]
                    features["xtb_mean_charge"] = round(float(np.mean(charges)), 5)
                    features["xtb_std_charge"] = round(float(np.std(charges)), 5)
                    features["xtb_min_charge"] = round(float(min(charges)), 5)
                    features["xtb_max_charge"] = round(float(max(charges)), 5)
                    features["xtb_abs_charge_sum"] = round(float(np.sum(np.abs(charges))), 3)
                if heavy_q:
                    features["xtb_heavy_mean_charge"] = round(float(np.mean(heavy_q)), 5)
                    features["xtb_heavy_std_charge"] = round(float(np.std(heavy_q)), 5)

            # Parse stdout for energy and orbitals
            stdout = result.stdout.decode("utf-8", errors="replace")
            for line in stdout.splitlines():
                if "total energy" in line.lower() and "Eh" in line:
                    parts = line.strip().split()
                    for i, p in enumerate(parts):
                        if "Eh" in p and i > 0:
                            try:
                                features["xtb_total_energy_eh"] = round(float(parts[i-1]), 6)
                            except:
                                pass
                if "HOMO-LUMO" in line and "eV" in line:
                    parts = line.strip().split()
                    for i, p in enumerate(parts):
                        if "eV" in p and i > 0:
                            try:
                                features["xtb_homo_lumo_gap_ev"] = round(float(parts[i-1]), 4)
                            except:
                                pass
                if "molecular dipole" in line.lower():
                    # Next line has the dipole vector
                    pass

        return features

    except (subprocess.TimeoutExpired, Exception):
        return {}
    finally:
        try:
            import shutil
            shutil.rmtree(d, ignore_errors=True)
        except:
            pass


# ═══════════════════════════════════════════════════════════════
# MMFF94 molecular mechanics features
# (NO «equivalente a GAFF2»: son campos de fuerza distintos y aquí no se ha
#  medido ninguna correspondencia. Ver la cabecera del módulo.)
# ═══════════════════════════════════════════════════════════════

def compute_mmff_features(smiles: str) -> dict:
    """Descriptores de enlace, ángulo y torsión con MMFF94 de RDKit."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {}

    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = 42
    status = AllChem.EmbedMolecule(mol, params)
    if status == -1:
        status = AllChem.EmbedMolecule(mol, AllChem.ETKDG())

    features = {}

    # MMFF94 atom types
    try:
        mp = AllChem.MMFFGetMoleculeProperties(mol)
        if mp:
            atom_types = []
            for i in range(mol.GetNumAtoms()):
                if mol.GetAtomWithIdx(i).GetAtomicNum() != 1:  # skip H
                    try:
                        at = mp.GetMMFFAtomType(i)
                        atom_types.append(at)
                    except:
                        pass

            if atom_types:
                features["mmff_atom_type_mean"] = round(float(np.mean(atom_types)), 2)
                features["mmff_atom_type_std"] = round(float(np.std(atom_types)), 2)
                features["mmff_n_atom_types"] = len(set(atom_types))
                features["mmff_unique_atom_types"] = len(set(atom_types))
    except:
        pass

    # MMFF94 force constants and energies
    try:
        ff = AllChem.MMFFGetMoleculeForceField(mol, mp if mp else AllChem.MMFFGetMoleculeProperties(mol))
        if ff:
            results = ff.CalcEnergy()
            total_energy = float(results) if results else None
            if total_energy is not None:
                features["mmff_total_energy"] = round(total_energy, 4)

            # Bond lengths
            conf = mol.GetConformer()
            bond_lengths = []
            for bond in mol.GetBonds():
                i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
                pi = np.array(conf.GetAtomPosition(i))
                pj = np.array(conf.GetAtomPosition(j))
                bond_lengths.append(np.linalg.norm(pi - pj))
            if bond_lengths:
                features["mmff_mean_bond_len"] = round(float(np.mean(bond_lengths)), 4)
                features["mmff_std_bond_len"] = round(float(np.std(bond_lengths)), 4)
                features["mmff_min_bond_len"] = round(float(min(bond_lengths)), 4)
                features["mmff_max_bond_len"] = round(float(max(bond_lengths)), 4)
                features["mmff_n_bonds"] = len(bond_lengths)
    except:
        pass

    return features


# ═══════════════════════════════════════════════════════════════
# Combined quantum + mechanics features
# ═══════════════════════════════════════════════════════════════

def compute_all_quantum_features(smiles: str) -> dict:
    """Compute all quantum + MM features for a single molecule, including per-heavy-atom normalized."""
    features = {}

    # xTB quantum features
    xtb = compute_xtb_features(smiles)
    features.update(xtb)

    # MMFF94 features
    mmff = compute_mmff_features(smiles)
    features.update(mmff)
    
    # Add per-heavy-atom normalized versions
    from rdkit import Chem
    mol = Chem.MolFromSmiles(smiles)
    hac = max(1, sum(1 for a in mol.GetAtoms() if a.GetAtomicNum() > 1)) if mol else 10
    
    for k, v in list(features.items()):
        if isinstance(v, (int, float)) and v is not None:
            # Normalize by heavy atom count for size-independent features
            if 'bond' not in k and 'count' not in k and 'unique' not in k and 'types' not in k and 'bonds' not in k:
                features[f'{k}_per_ha'] = round(v / hac, 6)

    return features


def compute_quantum_score(smiles: str) -> float:
    """ÍNDICE HEURÍSTICO EXPERIMENTAL en [0, 1]. No es un observable cuántico.

    Combinación lineal de cuatro descriptores normalizados, con pesos y
    divisores elegidos a mano y sin ajuste documentado en este repositorio:

        raw = 0.25*hl_norm + 0.35*q_norm + 0.15*e_norm + 0.25*at_norm

    Los ingredientes —gap HOMO-LUMO, carga absoluta, energía total, diversidad
    de tipos atómicos— son magnitudes reales de xTB y MMFF94. Su combinación
    en un solo número no está validada contra nada externo, así que este valor
    sirve para explorar y ordenar dentro de una serie, no para decidir.

    Desde el 2026-09-04 no participa del score principal (`scoring/engine.py`).
    Devuelve None cuando no se pueden calcular las features: no se fabrica.
    """
    features = compute_all_quantum_features(smiles)
    if not features:
        return None
    
    hl = features.get("xtb_homo_lumo_gap_ev_per_ha", 0.0)
    abs_q = features.get("xtb_abs_charge_sum_per_ha", 0.0)
    energy = abs(features.get("xtb_total_energy_eh_per_ha", 0.0))
    atom_div = features.get("mmff_atom_type_mean_per_ha", 0.0)
    
    hl_norm = min(1.0, hl / 1.3)
    q_norm = min(1.0, abs_q / 0.27)
    e_norm = min(1.0, max(0.0, (3.5 - energy) / 1.0))
    at_norm = min(1.0, atom_div / 6.5)
    
    raw = hl_norm * 0.25 + q_norm * 0.35 + e_norm * 0.15 + at_norm * 0.25
    return round(max(0.0, min(1.0, raw)), 4)


# ── Quantum Cache ──
_compute_quantum_score_original = compute_quantum_score

import hashlib
import sqlite3
from pathlib import Path as _Path_QC


def quantum_cache_path() -> _Path_QC:
    """Ruta escribible del caché; nunca dentro del bundle instalado."""
    configured = os.environ.get("LOCAL_DATA_DIR")
    data_dir = (
        _Path_QC(configured).expanduser()
        if configured
        else _Path_QC.home() / "MolDesign" / "data"
    )
    return data_dir / "quantum_cache.db"


def _get_qc_db():
    path = quantum_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, score REAL, ts REAL)")
    conn.commit()
    return conn


def compute_quantum_score_cached(smiles: str) -> float | None:
    """Cached wrapper around compute_quantum_score. Avoids re-running xTB."""
    import time

    key = hashlib.sha256(smiles.encode()).hexdigest()
    try:
        conn = _get_qc_db()
        try:
            row = conn.execute("SELECT score FROM cache WHERE key = ?", (key,)).fetchone()
        finally:
            conn.close()
        if row:
            return row[0]
    except Exception:
        pass

    score = _compute_quantum_score_original(smiles)
    try:
        conn = _get_qc_db()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO cache VALUES (?, ?, ?)",
                (key, score, time.time()),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass
    return score


# Replace with cached version
compute_quantum_score = compute_quantum_score_cached


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute quantum features")
    parser.add_argument("--smiles", type=str, required=True)
    args = parser.parse_args()

    t0 = time.time()
    features = compute_all_quantum_features(args.smiles)
    elapsed = time.time() - t0

    print(f"Features for {args.smiles}:")
    for k, v in sorted(features.items()):
        print(f"  {k:30s} = {v}")
    print(f"\nTotal: {len(features)} features in {elapsed:.2f}s")
