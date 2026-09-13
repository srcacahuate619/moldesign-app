"""
gnn_v2/inference.py — GNN-v2 inference for single molecules with docked poses.

Usage (standalone):
  python -m gnn_v2.inference --smiles "NCCC1=CNC2=C1C=C(O)C=C2" --pdbqt pose.pdbqt --protein 7E2Y.pdb
  
Usage (from benchmark):
  from gnn_v2.inference import GNNv2Predictor
  p = GNNv2Predictor()
  prob, std = p.predict(smiles, docked_pdbqt_path, protein_pdb_path)
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

# Module-level logger (used throughout for warnings on silent returns).
_log = logging.getLogger("gnn_v2.inference")
if not _log.handlers:  # avoid duplicate handlers when model is loaded multiple times
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[gnn_v2] %(levelname)s %(message)s"))
    _log.addHandler(_h)
    _log.setLevel(logging.INFO)
    _log.propagate = False


class _SilentFailure(Exception):
    """Lightweight marker for known silent-fallthrough cases inside GNN-v2.

    Using a small wrapper exception lets the main ``predict()`` caller apply a
    single ``logger.warning`` + counter bump on every silent path WITHOUT
    winning the silent return at every internal helper.  This guarantees the
    bench pipeline never forgets the user about a silent-return (was the
    principal pre-Bucket-A.3 bug)."""

from gnn_v2.data import (
    ELEMENTS,
    ELEM_TO_IDX,
    _build_cross_edges,
    _build_protein_graph,
    _parse_docked_pdbqt,
)
from gnn_v2.models import GNNv2Classifier

ARTIFACTS_DIR = PROJECT_ROOT / "rescoring" / "artifacts"
GPU_MODEL_PATH = ARTIFACTS_DIR / "gpu" / "gnn_v3_best.pt"
CPU_MODEL_PATH = ARTIFACTS_DIR / "gnn_v3_best.pt"
MODEL_PATH = GPU_MODEL_PATH if GPU_MODEL_PATH.exists() else CPU_MODEL_PATH

class GNNv2Predictor:
    """Wraps GNN-v2 model for single-molecule inference with docked poses."""

    def __init__(self, device: str = "auto", mc_samples: int = 20, model_path: Path | None = None):
        if device == "auto":
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
        self.mc_samples = mc_samples
        self.model = None
        self._model_path = model_path or MODEL_PATH
        self.silent_failures: int = 0
        self._last_silent_reason: str | None = None
        self._load_model()

    def _load_model(self):
        checkpoint = torch.load(self._model_path, map_location=self.device, weights_only=False)
        # v1.7: Soporte dual — checkpoint legacy (bare state_dict) y formato nuevo (dict con keys)
        if isinstance(checkpoint, dict) and "model_state_dict" in checkpoint:
            state_dict = checkpoint["model_state_dict"]
        else:
            state_dict = checkpoint  # bare state_dict (formato clgnn_finetuned.pt)
        # Detectar hidden_dim dinámicamente
        hidden_dim = state_dict["prot_encoder.in_proj.weight"].shape[0]
        self.model = GNNv2Classifier(hidden_dim=hidden_dim, dropout=0.0)
        for m in self.model.modules():
            if isinstance(m, torch.nn.Dropout):
                m.p = 0.3
        missing, unexpected = self.model.load_state_dict(state_dict, strict=False)
        if missing:
            _log.warning("gnn_weights_missing: %d keys — %s", len(missing), str(missing)[:200])
        if unexpected:
            _log.warning("gnn_weights_unexpected: %d keys — %s", len(unexpected), str(unexpected)[:200])
        self.model.to(self.device)

    def predict(self, smiles: str, docked_pdbqt_path: str, protein_pdb_path: str) -> tuple[float, float]:
        """
        Predict P(binder) with MC Dropout uncertainty.

        Args:
            smiles: SMILES string of the ligand
            docked_pdbqt_path: Path to Vina docked PDBQT output
            protein_pdb_path: Path to protein PDB file

        Returns:
            (prob, std) — mean probability and standard deviation.

        [A3] En cualquier fallo interno el retorno es (NaN, NaN) con WARNING
        que incluye identificadores (smiles + rutas de pose/proteína). El
        valor 0.5 neutral jamás se fabrica: NaN es la señal explícita de
        "sin predicción" para los callers (benchmark, stacking, runner).
        """
        # Generate 2D SDF from SMILES (bond topology only)
        sdf_path = self._smiles_to_2d_sdf(smiles)
        if sdf_path is None:
            return self._record_silent("smiles_invalid_no_2d_sdf", smiles, docked_pdbqt_path, protein_pdb_path)

        try:
            prob, std = self._predict_from_files(sdf_path, docked_pdbqt_path, protein_pdb_path)
            return float(prob), float(std)
        except _SilentFailure as silent:
            # Known silent-fallthrough case (e.g. no pocket residues in graph).
            reason = str(silent.args[0]) if silent.args else "silent"
            return self._record_silent(reason, smiles, docked_pdbqt_path, protein_pdb_path)
        except Exception as exc:
            return self._record_silent(
                f"exception_{type(exc).__name__}", smiles, docked_pdbqt_path, protein_pdb_path
            )
        finally:
            if sdf_path and os.path.exists(sdf_path):
                try:
                    os.unlink(sdf_path)
                except OSError:
                    pass

    def _record_silent(
        self,
        reason: str,
        smiles: str | None = None,
        docked_pdbqt_path: str | None = None,
        protein_pdb_path: str | None = None,
    ) -> tuple[float, float]:
        """Increment silent-failure counter, log a WARNING with identifiers and
        return (NaN, NaN) — NUNCA (0.5, 1.0) fabricado.

        [A3] NaN + identificadores (smiles, pose PDBQT, proteína PDB) permite
        al caller EXCLUIR la molécula de forma explícita y auditable. Reasons
        tracked include:
            - smiles_invalid_no_2d_sdf      RDKit could not parse the SMILES
            - ligand_graph_failed           SDF->PDBQT atom count mismatch
            - protein_graph_failed_no_pocket_residues  Cα in pocket = 0 (DNA, RNA, glycan, etc.)
            - exception_<ExceptionClass>     Unexpected runtime exception
        """
        self.silent_failures += 1
        self._last_silent_reason = reason
        snippet = (smiles[:40] + "...") if (smiles and len(smiles) > 40) else (smiles or "")
        pose_snippet = (str(docked_pdbqt_path)[-60:]) if docked_pdbqt_path else ""
        protein_snippet = (str(protein_pdb_path)[-60:]) if protein_pdb_path else ""
        _log.warning(
            "[silent] %s | reason=%s | smiles=%s | pose=%s | protein=%s | cumulative=%d",
            "GNN-v2 fallthrough", reason, snippet, pose_snippet, protein_snippet,
            self.silent_failures,
        )
        return float("nan"), float("nan")

    def reset_silent_failures(self) -> None:
        """Reset the per-run silent-failure counter (called between datasets)."""
        self.silent_failures = 0
        self._last_silent_reason = None

    def _smiles_to_2d_sdf(self, smiles: str) -> str | None:
        """Convert SMILES to 2D SDF (bond topology only, coords don't matter)."""
        from rdkit import Chem, RDLogger
        from rdkit.Chem import AllChem
        RDLogger.logger().setLevel(RDLogger.ERROR)

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return None
        mol = Chem.AddHs(mol)
        AllChem.Compute2DCoords(mol)
        mol = Chem.RemoveHs(mol)

        fd, path = tempfile.mkstemp(suffix=".sdf")
        os.close(fd)
        writer = Chem.SDWriter(path)
        writer.write(mol)
        writer.close()
        return path

    def _predict_from_files(self, sdf_path: str, docked_pdbqt_path: str, protein_pdb_path: str) -> tuple[float, float]:
        """Core prediction: construct graphs → run MC inference.

        On any silent failure this raises `_SilentFailure`; `predict()` then
        returns ``(NaN, NaN)`` via `_record_silent`. NO 0.5 is ever fabricated:
        NaN is the explicit "no prediction" signal for the caller.
        Caller (`predict()`) already increments the lifetime `silent_failures`
        counter on the predictor instance; thresholds and benchmark reports
        should sample it after a run.
        """
        # Ligand graph
        lig_graph = self._build_ligand_graph_from_sdf_pdbqt(sdf_path, docked_pdbqt_path)
        if lig_graph is None:
            raise _SilentFailure("ligand_graph_failed")

        # Protein graph
        lig_coords = lig_graph.pos.numpy()
        prot_graph = _build_protein_graph(protein_pdb_path, lig_coords)
        if prot_graph is None:
            raise _SilentFailure("protein_graph_failed_no_pocket_residues")

        # Cross edges
        cross_edges = _build_cross_edges(lig_graph.pos, prot_graph.pos)

        # Move to device
        prot_x = prot_graph.x.to(self.device)
        prot_ei = prot_graph.edge_index.to(self.device)
        lig_x = lig_graph.x.to(self.device)
        lig_ei = lig_graph.edge_index.to(self.device)
        cross_ei = cross_edges.to(self.device)
        lig_pos = lig_graph.pos.to(self.device)
        prot_pos = prot_graph.pos.to(self.device)

        # MC inference
        self.model.train()  # keep dropout active
        samples = []
        with torch.no_grad():
            for _ in range(self.mc_samples):
                logits = self.model(prot_x, prot_ei, lig_x, lig_ei, cross_ei,
                                   lig_pos=lig_pos, prot_pos=prot_pos)
                samples.append(torch.sigmoid(logits).item())

        prob = np.mean(samples)
        std = np.std(samples)
        return prob, std

    def _build_ligand_graph_from_sdf_pdbqt(self, sdf_path: str, pdbqt_path: str):
        """Build ligand graph from 2D SDF (bond topology) + docked PDBQT (3D coords)."""
        from rdkit import Chem, RDLogger
        RDLogger.logger().setLevel(RDLogger.ERROR)

        import torch
        from torch_geometric.data import Data

        # SDF for bond topology
        mol = Chem.SDMolSupplier(sdf_path, removeHs=True)[0]
        if mol is None:
            mol = Chem.MolFromMolFile(sdf_path, removeHs=True, sanitize=False)
        if mol is None:
            return None

        # Docked PDBQT for 3D coords
        parsed = _parse_docked_pdbqt(pdbqt_path)
        docked_elements = [e for e in parsed["elements"] if e not in ("H",)]
        docked_coords = parsed["coords"][[i for i, e in enumerate(parsed["elements"]) if e not in ("H",)]]

        rdkit_heavy = [a for a in mol.GetAtoms() if a.GetAtomicNum() > 1]
        if len(docked_elements) != len(rdkit_heavy):
            return None  # atom count mismatch

        # Build node features
        # NOTE: ELEMENTS and ELEM_TO_IDX imported from gnn_v2.data in Bucket A.1
        # (was duplicated local 10-element array; removed - now uses the 30-element
        # alphabet from data module).
        features = []
        for atom in rdkit_heavy:
            elem = atom.GetSymbol()
            elem_idx = ELEM_TO_IDX.get(elem, len(ELEMENTS) - 1)
            elem_onehot = np.zeros(len(ELEMENTS), dtype=np.float32)
            elem_onehot[elem_idx] = 1.0

            hyb = str(atom.GetHybridization())
            hyb_onehot = np.zeros(4, dtype=np.float32)
            if "SP2" in hyb:
                hyb_onehot[1] = 1.0
            elif "SP3" in hyb:
                hyb_onehot[2] = 1.0
            elif "SP" in hyb:
                hyb_onehot[0] = 1.0
            else:
                hyb_onehot[3] = 1.0

            degree = min(atom.GetDegree(), 6)
            charge = atom.GetFormalCharge()
            aromatic = 1.0 if atom.GetIsAromatic() else 0.0
            in_ring = 1.0 if atom.IsInRing() else 0.0

            feat = np.concatenate([
                elem_onehot,
                hyb_onehot,
                np.array([degree / 6.0, (charge + 2.0) / 4.0, aromatic, in_ring], dtype=np.float32),
            ])
            features.append(feat)

        x = torch.tensor(np.array(features, dtype=np.float32))
        coords = torch.tensor(docked_coords[:len(rdkit_heavy)], dtype=torch.float32)

        # Edges: covalent bonds + spatial edges
        atoms_list = list(mol.GetAtoms())
        bond_pairs = set()
        for bond in mol.GetBonds():
            i = bond.GetBeginAtomIdx()
            j = bond.GetEndAtomIdx()
            hi_i = sum(1 for a in atoms_list[:i] if a.GetAtomicNum() > 1)
            hi_j = sum(1 for a in atoms_list[:j] if a.GetAtomicNum() > 1)
            if hi_i < len(docked_elements) and hi_j < len(docked_elements):
                bond_pairs.add((hi_i, hi_j))
                bond_pairs.add((hi_j, hi_i))

        # Spatial edges (< 4A)
        for i in range(len(coords)):
            for j in range(i + 1, len(coords)):
                if (i, j) in bond_pairs:
                    continue
                if torch.norm(coords[i] - coords[j]) < 4.0:
                    bond_pairs.add((i, j))
                    bond_pairs.add((j, i))

        edge_index = torch.tensor(list(bond_pairs), dtype=torch.long).t().contiguous()
        return Data(x=x, pos=coords, edge_index=edge_index)


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--smiles", required=True)
    parser.add_argument("--pdbqt", required=True, help="Docked PDBQT path")
    parser.add_argument("--protein", required=True, help="Protein PDB path")
    parser.add_argument("--mc-samples", type=int, default=20)
    args = parser.parse_args()

    pred = GNNv2Predictor(mc_samples=args.mc_samples)
    prob, std = pred.predict(args.smiles, args.pdbqt, args.protein)
    print(f"P(binder) = {prob:.4f} ± {std:.4f}")
