"""
build_gnn_graphs_batch.py - Construye GNN graphs para complejos PDBbind
usando coordenadas cristalograficas (SDF) cuando no hay PDBQT dockeado.

Para contrastive pretraining: solo necesita estructura 3D, no dockeo.
"""
import sys, os, time, json
from pathlib import Path

sys.path.insert(0, str(Path("D:/moldesign-build/rescoring")))

import numpy as np
import torch
from torch_geometric.data import Data

from gnn_v2.data import (
    PDBBIND_DIR, REDOCK_DIR, INDEX_PATH,
    _build_protein_graph, _build_cross_edges,
    POCKET_CUTOFF, CROSS_CUTOFF, SPATIAL_EDGE_CUTOFF,
    ELEM_TO_IDX, AD4_TO_ELEMENT, AMINO_ACIDS,
)

PROJECT_ROOT = Path("D:/moldesign-build")
OUT_DIR = PROJECT_ROOT / "data" / "gnn_v31" / "curated_new"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _build_ligand_graph_from_sdf(sdf_path):
    """
    Build ligand graph using SDF coordinates (crystal structure).
    Alternative to _build_ligand_graph which requires docked PDBQT.
    """
    from rdkit import Chem
    
    mol = Chem.SDMolSupplier(str(sdf_path), removeHs=True)
    try:
        mol = next(mol)
    except StopIteration:
        pass
    if mol is None:
        return None
    
    conf = mol.GetConformer()
    if conf is None:
        return None
    
    heavy_atoms = [a for a in mol.GetAtoms() if a.GetAtomicNum() > 1]
    if len(heavy_atoms) < 5 or len(heavy_atoms) > 120:
        return None
    
    # Build node features
    features = []
    coords = []
    for atom in heavy_atoms:
        elem = atom.GetSymbol()
        elem_idx = ELEM_TO_IDX.get(elem, len(ELEM_TO_IDX) - 1)
        elem_onehot = np.zeros(len(ELEM_TO_IDX), dtype=np.float32)
        elem_onehot[elem_idx] = 1.0
        
        hyb = str(atom.GetHybridization())
        hyb_onehot = np.zeros(4, dtype=np.float32)
        if "SP2" in hyb: hyb_onehot[1] = 1.0
        elif "SP3" in hyb: hyb_onehot[2] = 1.0
        elif "SP" in hyb: hyb_onehot[0] = 1.0
        else: hyb_onehot[3] = 1.0
        
        degree = min(atom.GetDegree(), 6)
        charge = atom.GetFormalCharge()
        aromatic = 1.0 if atom.GetIsAromatic() else 0.0
        in_ring = 1.0 if atom.IsInRing() else 0.0
        
        feat = np.concatenate([
            elem_onehot, hyb_onehot,
            np.array([degree / 6.0, (charge + 2.0) / 4.0, aromatic, in_ring], dtype=np.float32),
        ])
        features.append(feat)
        
        pos = conf.GetAtomPosition(atom.GetIdx())
        coords.append([pos.x, pos.y, pos.z])
    
    x = np.array(features, dtype=np.float32)
    coords_np = np.array(coords, dtype=np.float32)
    
    # Edges: covalent bonds + spatial edges
    atom_idx_in_heavy = {}
    heavy_idx = 0
    for atom in mol.GetAtoms():
        if atom.GetAtomicNum() > 1:
            atom_idx_in_heavy[atom.GetIdx()] = heavy_idx
            heavy_idx += 1
    
    bond_pairs = set()
    for bond in mol.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()
        if i in atom_idx_in_heavy and j in atom_idx_in_heavy:
            hi_i = atom_idx_in_heavy[i]
            hi_j = atom_idx_in_heavy[j]
            bond_pairs.add((hi_i, hi_j))
            bond_pairs.add((hi_j, hi_i))
    
    # Spatial edges
    coords_pt = torch.tensor(coords_np, dtype=torch.float32)
    for i in range(len(coords_pt)):
        for j in range(i + 1, len(coords_pt)):
            if (i, j) in bond_pairs:
                continue
            if torch.norm(coords_pt[i] - coords_pt[j]) < SPATIAL_EDGE_CUTOFF:
                bond_pairs.add((i, j))
                bond_pairs.add((j, i))
    
    if not bond_pairs:
        return None
    
    edge_index = torch.tensor(list(bond_pairs), dtype=torch.long).t().contiguous()
    return Data(x=torch.tensor(x, dtype=torch.float32), pos=coords_pt, edge_index=edge_index)


def build_single_graph(pdb_id, pdb_dir, use_docked=True):
    """
    Build a single complex graph. Uses crystal SDF coords.
    """
    protein_pdb = str(pdb_dir / f"{pdb_id}_protein.pdb")
    ligand_sdf = str(pdb_dir / f"{pdb_id}_ligand.sdf")
    
    if not os.path.exists(protein_pdb) or not os.path.exists(ligand_sdf):
        return None
    
    # Ligand graph from SDF (crystal coords)
    lig_graph = _build_ligand_graph_from_sdf(ligand_sdf)
    if lig_graph is None:
        return None
    
    # Protein graph (pocket only)
    lig_coords = lig_graph.pos.numpy()
    prot_graph = _build_protein_graph(protein_pdb, lig_coords)
    if prot_graph is None:
        return None
    
    # Cross edges
    cross_edges = _build_cross_edges(lig_graph.pos, prot_graph.pos)
    
    return {
        "protein": prot_graph,
        "ligand": lig_graph,
        "cross": cross_edges,
        "y": 0.0,
        "y_binary": 1,
        "pdb_id": pdb_id,
    }


def main():
    # Load PDB IDs
    pids_refined = OUT_DIR / "pids_refined_new.txt"
    pids_general = OUT_DIR / "pids_general_for_contrastive.txt"
    
    all_pids = []
    label = []
    for f, src_label in [(pids_refined, "refined"), (pids_general, "general")]:
        if f.exists():
            ids = [l.strip() for l in open(f).read().split("\n") if l.strip()]
            all_pids.extend(ids)
            label.extend([src_label] * len(ids))
    
    print(f"Total PDBs to process: {len(all_pids)}")
    print(f"  Refined: {all_pids.count('refined')}")
    print(f"  General: {all_pids.count('general')}")
    
    # Load pKi for refined
    pki_map = {}
    if INDEX_PATH.exists():
        with open(INDEX_PATH) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if len(parts) >= 6 and parts[4] == "//":
                    try:
                        pid = parts[0].lower()
                        pki = float(parts[5])
                        if pki > 0:
                            pki_map[pid] = pki
                    except:
                        pass
    
    print(f"  Loaded {len(pki_map)} pKi values from INDEX")
    
    # Build graphs
    graphs = []
    failed = 0
    start = time.time()
    
    for i, pid in enumerate(all_pids):
        pdb_dir = PDBBIND_DIR / pid
        graph = build_single_graph(pid, pdb_dir, use_docked=False)
        if graph is not None:
            # Add pKi if available
            if pid in pki_map:
                graph["y"] = pki_map[pid]
                graph["y_binary"] = 1 if pki_map[pid] > 7.0 else 0
            graphs.append(graph)
        else:
            failed += 1
        
        if (i + 1) % 200 == 0:
            elapsed = time.time() - start
            rate = (i + 1) / elapsed
            eta = (len(all_pids) - i - 1) / rate
            print(f"  [{i+1}/{len(all_pids)}] built {len(graphs)} graphs, "
                  f"{failed} failed [{elapsed:.0f}s, ETA {eta:.0f}s]")
    
    elapsed = time.time() - start
    print(f"\n  Done: {len(graphs)} graphs built ({failed} failed) in {elapsed:.0f}s")
    print(f"  Rate: {len(graphs)/max(1,elapsed):.1f} graphs/s")
    
    # Save as .pt file
    out_path = OUT_DIR / "gnn_general_complexes.pt"
    torch.save((tuple(graphs), {}), out_path)
    print(f"  Saved: {out_path} ({out_path.stat().st_size/1024/1024:.1f} MB)")
    
    # Also save pids for each
    pids_done = [g["pdb_id"] for g in graphs]
    with open(OUT_DIR / "pids_successful.txt", "w") as f:
        for pid in pids_done:
            f.write(pid + "\n")
    print(f"  Saved: {OUT_DIR / 'pids_successful.txt'}")


if __name__ == "__main__":
    main()
