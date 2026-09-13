"""
gnn_v2/data.py — Protein-Ligand Complex Dataset for GNN-v2.

Graph construction from PDB + docked PDBQT:
  - Protein graph: Cα atoms of binding pocket residues (GAT-ready)
  - Ligand graph: heavy atoms with bond + spatial edges (GIN-ready)
  - Cross edges: ligand atoms → protein residues within 8Å

Output format: per complex:
  protein: Data(x=[N_res, 23], edge_index=[2, E_prot])
  ligand:  Data(x=[N_lig, 17], edge_index=[2, E_lig])
  cross:   edge_index=[2, E_cross]  (lig_idx → prot_idx)
  y:       float (pKi)
  y_binary: int (pKi > 7)
  pdb_id:  str
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path

import numpy as np
import torch
from torch_geometric.data import Data, InMemoryDataset

warnings.filterwarnings("ignore")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PDBBIND_DIR = DATA_DIR / "pdbbind"
REDOCK_DIR = PDBBIND_DIR / "redocked_v2"
CACHE_DIR = PDBBIND_DIR / "feature_cache_v4"
INDEX_PATH = PDBBIND_DIR / "INDEX_refined_data.2020"

# ═══════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════

AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"  # 20 standard, alphabetically
AA_TO_IDX = {aa: i for i, aa in enumerate(AMINO_ACIDS)}
UNK_AA_IDX = 20  # unknown

# 3-letter → 1-letter mapping.
# Standard 20 AAs plus common variants + common PTMs (post-translational
# modifications). Modified residues are mapped to their unmodified parent so
# that the GNN-v2 feature embedding still gets a meaningful residue-type
# signal instead of falling to the UNK bucket.
AA3_TO_AA1 = {
    # Standard 20 AAs
    "ALA": "A", "CYS": "C", "ASP": "D", "GLU": "E", "PHE": "F",
    "GLY": "G", "HIS": "H", "ILE": "I", "LYS": "K", "LEU": "L",
    "MET": "M", "ASN": "N", "PRO": "P", "GLN": "Q", "ARG": "R",
    "SER": "S", "THR": "T", "VAL": "V", "TRP": "W", "TYR": "Y",
    # Non-standard / engineered variants
    "HIE": "H", "HID": "H", "HIP": "H", "CYX": "C",
    "MSE": "M",                                   # selenomethionine (MAD phasing)
    "SEC": "U" if "U" in AMINO_ACIDS else "M",    # selenocysteine (rare, falls back)
    # PTMs (post-translational modifications): map to parent AA
    "SEP": "S",                                   # phosphoserine
    "TPO": "T",                                   # phosphothreonine
    "PTR": "Y",                                   # phosphotyrosine
    "CSO": "C",                                   # S-hydroxycysteine
    "OCS": "C",                                   # cysteinesulfonic acid
    "CME": "C",                                   # S,S-(2-hydroxyethyl)thiocysteine
    "PCA": "E",                                   # pyroglutamate (N-term E)
    "PYL": "K",                                   # pyrrolysine (21st AA in some archaea)
    "FME": "M",                                   # N-formylmethionine (initiator)
    "HIC": "H",                                   # methylhistidine
    "MHO": "M",                                   # S-oxymethionine
    "M3L": "K",                                   # N-methyllysine
    "MLY": "K",                                   # dimethyllysine
    "AIB": "A",                                   # alpha-aminoisobutyric acid
    "BAL": "A",                                   # beta-alanine
    "ORN": "K",                                   # ornithine
    "DAL": "A",                                   # D-alanine
    "DGN": "Q",                                   # D-glutamine
    # Glycosylation / common HETATM cofactors  fall to UNK through AA3_TO_AA1
    # but the atom-level features (elements heavy=CA=C1') still get used
    # for the graph. For DNA / RNA / glycosyl we map to the relevant sub-vector
    # "Z" so they stay distinct from real AA residues.
    # Nucleotide 3-letter codes (added in Bucket A.2, signal "non-AA pocket")
    "DA": "DA", "DT": "DT", "DG": "DG", "DC": "DC",
    "RA": "RA", "RT": "RT", "RG": "RG", "RC": "RC", "RU": "RU", "RI": "RI",
    "A":  "RA", "T":  "RT", "G":  "RG", "C":  "RC", "U":  "RU",
    # Glycans (common monosaccharides)
    "NAG": "NAG", "MAN": "MAN", "BMA": "BMA", "FUC": "FUC",
    "GAL": "GAL", "GLC": "GLC", "NDG": "NAG",
    # Cofactors that often appear co-crystallized in pockets
    "HEM": "HEM", "FAD": "FAD", "NAD": "NAD", "ATP": "ATP", "GTP": "GTP",
    "PLP": "PLP",
}

# Extended element alphabet (was 10, expanded to 30 in Bucket A.1).
# Adding B (boronates, e.g. Bortezomib), Si (organosilicon probes), Se
# (selenocysteine peroxidases), As (arsenic drugs / salvarsan), plus common
# metals and metalloids that appear in medicinal-chem datasets (Mg, Ca, Zn,
# Fe, Mn, Cu, Ni, Co, K, Na).  "X" stays as last-resort unknown bucket.
ELEMENTS = [
    "C", "N", "O", "S",                  # organic backbone
    "P", "F", "Cl", "Br", "I",           # halogen + phosphate
    "B", "Si", "Se", "As", "At",         # boronates, organosilicon, seleno, arsenic
    "Mg", "Ca", "Zn", "Fe", "Mn",        # divalent metals
    "Cu", "Ni", "Co", "K", "Na",         # transition + alkali metals
    "Li", "Sn", "Sb", "Te",              # Li (lithium drugs), Sn, Sb, Te
    "H",                                  # explicit hydrogen if docked
    "X",                                  # catch-all unknown (last resort)
]
ELEM_TO_IDX = {e: i for i, e in enumerate(ELEMENTS)}

HYBRIDIZATION = ["SP", "SP2", "SP3", "OTHER"]

AD4_TO_ELEMENT = {
    "C": "C", "A": "C",                  # aromatic carbon
    "N": "N", "NA": "N", "NS": "N",
    "O": "O", "OA": "O", "OS": "O",
    "H": "H", "HD": "H", "HS": "H", "HO": "H",
    "S": "S", "SA": "S",
    "P": "P",
    "F": "F", "Cl": "Cl", "Br": "Br", "I": "I",
    # extended medicinal-chem elements (added in Bucket A.1)
    "B":  "B",                           # boron (Bortezomib-class proteasome inhibitors)
    "Si": "Si",                          # organosilicon
    "Se": "Se",                          # selenocysteine / selenazoles
    "As": "As",                          # salvarsan / arsenic drugs
    "Li": "Li", "Na": "Na", "K": "K",    # alkali metals
    "Mg": "Mg", "Ca": "Ca", "Zn": "Zn",  # divalent metals
    "Fe": "Fe", "Mn": "Mn",              # transition metals (Fe-S clusters, etc.)
    "Cu": "Cu", "Ni": "Ni", "Co": "Co",
    "Sn": "Sn", "Sb": "Sb", "Te": "Te",
    # catches for non-standard AD4 types (e.g. metalloid weirdness)
    "X": "X",
}

POCKET_CUTOFF = 10.0       # Å from ligand to include residue in pocket
CROSS_CUTOFF = 8.0         # Å ligand atom → protein Cα cross-edge
SPATIAL_EDGE_CUTOFF = 4.0  # Å non-bonded ligand spatial edges
PROT_KNN = 10              # k-NN for protein graph edges


# ═══════════════════════════════════════════════════════════════════════
# Ligand graph from docked PDBQT
# ═══════════════════════════════════════════════════════════════════════

def _parse_docked_pdbqt(pdbqt_path: str) -> dict:
    """Parse Vina output PDBQT → atom elements + 3D coords."""
    atoms = []
    coords = []
    with open(pdbqt_path) as f:
        for line in f:
            if not (line.startswith("ATOM") or line.startswith("HETATM")):
                if line.startswith("ENDMDL"):
                    break
                continue
            if len(line) < 79:
                continue
            ad4_type = line[77:79].strip()
            elem = AD4_TO_ELEMENT.get(ad4_type, line[76:78].strip())
            try:
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            atoms.append(elem)
            coords.append([x, y, z])
    return {"elements": atoms, "coords": np.array(coords, dtype=np.float32)}


def _build_ligand_graph(sdf_path: str, docked_pdbqt_path: str) -> Data | None:
    """Build ligand graph with bond topology from SDF + coords from docked PDBQT."""
    from rdkit import Chem

    # SDF for bond topology
    mol = None
    suppl = Chem.SDMolSupplier(sdf_path, removeHs=True)
    try:
        mol = next(suppl)
    except StopIteration:
        pass
    if mol is None:
        mol = Chem.MolFromMolFile(sdf_path, removeHs=True, sanitize=False)

    if mol is None:
        return None

    # Docked PDBQT for 3D coordinates
    parsed = _parse_docked_pdbqt(docked_pdbqt_path)
    if len(parsed["elements"]) == 0:
        return None

    # Match docked atoms to RDKit atoms by element count
    docked_elements = [e for e in parsed["elements"] if e not in ("H",)]
    docked_coords = parsed["coords"][[i for i, e in enumerate(parsed["elements"]) if e not in ("H",)]]

    rdkit_heavy = [a for a in mol.GetAtoms() if a.GetAtomicNum() > 1]
    if len(docked_elements) != len(rdkit_heavy):
        return None  # atom count mismatch — can't align

    # Build node features (from RDKit)
    pt = Chem.GetPeriodicTable()
    features = []
    for atom in rdkit_heavy:
        elem = atom.GetSymbol()
        elem_idx = ELEM_TO_IDX.get(elem, len(ELEMENTS) - 1)
        elem_onehot = np.zeros(len(ELEMENTS), dtype=np.float32)
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
            elem_onehot,
            hyb_onehot,
            np.array([degree / 6.0, (charge + 2.0) / 4.0, aromatic, in_ring], dtype=np.float32),
        ])
        features.append(feat)

    x = np.array(features, dtype=np.float32)

    # Edges: covalent bonds + spatial edges
    atoms_list = list(mol.GetAtoms())
    bond_pairs = set()
    for bond in mol.GetBonds():
        i = bond.GetBeginAtomIdx()
        j = bond.GetEndAtomIdx()
        # Map to heavy-atom index
        hi_i = sum(1 for a in atoms_list[:i] if a.GetAtomicNum() > 1)
        hi_j = sum(1 for a in atoms_list[:j] if a.GetAtomicNum() > 1)
        if hi_i < len(docked_elements) and hi_j < len(docked_elements):
            bond_pairs.add((hi_i, hi_j))
            bond_pairs.add((hi_j, hi_i))

    # Spatial edges
    coords = torch.tensor(docked_coords[:len(rdkit_heavy)], dtype=torch.float32)
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            if (i, j) in bond_pairs:
                continue
            if torch.norm(coords[i] - coords[j]) < SPATIAL_EDGE_CUTOFF:
                bond_pairs.add((i, j))
                bond_pairs.add((j, i))

    edge_index = torch.tensor(list(bond_pairs), dtype=torch.long).t().contiguous()
    return Data(x=torch.tensor(x, dtype=torch.float32), pos=coords, edge_index=edge_index)


# ═══════════════════════════════════════════════════════════════════════
# Protein graph (Cα level, pocket residues)
# ═══════════════════════════════════════════════════════════════════════

def _build_protein_graph(protein_pdb: str, lig_coords: np.ndarray) -> Data | None:
    """Build protein graph: Cα atoms of pocket residues (within POCKET_CUTOFF of ligand)."""
    from rdkit import Chem

    mol = Chem.MolFromPDBFile(protein_pdb, removeHs=True, sanitize=False)
    if mol is None:
        return None
    Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)

    conf = mol.GetConformer()

    # Extract residues and their Cα atoms (PDB residue info is in atom Info)
    residues = {}  # (chain, resname, residx) → list of atom indices
    ca_atoms = {}  # (chain, resname, residx) → atom index (the Cα)

    for atom in mol.GetAtoms():
        info = atom.GetPDBResidueInfo()
        if info is None:
            continue
        key = (info.GetChainId().strip(), info.GetResidueName().strip(), info.GetResidueNumber())
        if key not in residues:
            residues[key] = []
        residues[key].append(atom.GetIdx())
        if info.GetName().strip() == "CA":
            ca_atoms[key] = atom.GetIdx()

    if len(ca_atoms) == 0:
        return None  # no Cα atoms (unusual PDB)

    # Find pocket residues: any residue atom within POCKET_CUTOFF of any ligand atom
    lig_tensor = torch.tensor(lig_coords, dtype=torch.float32)
    pocket_residues = set()
    for key, atom_idxs in residues.items():
        resname_3 = key[1]
        resname_1 = AA3_TO_AA1.get(resname_3, "")
        # Include the residue if it CAN be mapped to something (AA, PTM, nucleotide,
        # glycan, cofactor).  Pure water (HOH) and bare ions (Zinc magnet) remain
        # without Cα and will be filtered in pocket_with_ca below.
        if not resname_1:
            continue
        for aidx in atom_idxs:
            pos = np.array(conf.GetAtomPosition(aidx))
            dists = np.linalg.norm(lig_coords - pos, axis=1)
            if dists.min() < POCKET_CUTOFF:
                pocket_residues.add(key)
                break

    if len(pocket_residues) == 0:
        return None  # no residues near pocket (protein with no AA/cofactor near ligand)

    # Build node features for pocket Cα atoms
    # Only include residues that have Cα atoms
    pocket_with_ca = [k for k in pocket_residues if k in ca_atoms]
    if len(pocket_with_ca) == 0:
        return None
    
    residue_list = sorted(pocket_with_ca, key=lambda k: ca_atoms[k])
    features = []
    positions = []
    for key in residue_list:
        resname_1 = AA3_TO_AA1.get(key[1], "X")
        aa_idx = AA_TO_IDX.get(resname_1, UNK_AA_IDX)
        aa_onehot = np.zeros(len(AMINO_ACIDS) + 1, dtype=np.float32)
        aa_onehot[aa_idx] = 1.0

        ca_idx = ca_atoms[key]
        pos = np.array(conf.GetAtomPosition(ca_idx), dtype=np.float32)
        positions.append(pos)

        feat = np.concatenate([aa_onehot, pos])
        features.append(feat)

    if len(features) == 0:
        return None

    x = np.array(features, dtype=np.float32)
    positions = np.array(positions, dtype=np.float32)

    # k-NN edges between Cα atoms
    pos_t = torch.tensor(positions, dtype=torch.float32)
    k = min(PROT_KNN, len(positions) - 1)
    edge_pairs = []
    for i in range(len(positions)):
        dists = torch.norm(pos_t - pos_t[i], dim=1)
        _, indices = torch.topk(dists, k + 1, largest=False)
        for j in indices[1:]:  # skip self
            edge_pairs.append((i, int(j)))
            edge_pairs.append((int(j), i))

    edge_index = torch.tensor(edge_pairs, dtype=torch.long).t().contiguous()
    return Data(x=torch.tensor(x, dtype=torch.float32), pos=pos_t, edge_index=edge_index)


# ═══════════════════════════════════════════════════════════════════════
# Cross edges (ligand → protein)
# ═══════════════════════════════════════════════════════════════════════

def _build_cross_edges(lig_pos: torch.Tensor, prot_pos: torch.Tensor) -> torch.Tensor:
    """Build directed cross edges: ligand atom → protein residue within CROSS_CUTOFF."""
    cross_pairs = []
    for i in range(len(lig_pos)):
        dists = torch.norm(prot_pos - lig_pos[i], dim=1)
        close = (dists < CROSS_CUTOFF).nonzero(as_tuple=False).flatten()
        for j in close:
            cross_pairs.append((i, int(j)))
    if not cross_pairs:
        return torch.empty((2, 0), dtype=torch.long)
    return torch.tensor(cross_pairs, dtype=torch.long).t().contiguous()


# ═══════════════════════════════════════════════════════════════════════
# Complex builder
# ═══════════════════════════════════════════════════════════════════════

def build_complex_graph(pdb_id: str) -> dict | None:
    """
    Build protein + ligand + cross graphs for a single PDBbind complex.
    
    Returns:
        {"protein": Data, "ligand": Data, "cross": edge_index, "y": pki, "y_binary": 0/1, "pdb_id": str}
        or None if any component fails.
    """
    protein_pdb = str(PDBBIND_DIR / pdb_id / f"{pdb_id}_protein.pdb")
    ligand_sdf = str(PDBBIND_DIR / pdb_id / f"{pdb_id}_ligand.sdf")
    docked_pdbqt = str(REDOCK_DIR / f"{pdb_id}_docked.pdbqt")

    if not os.path.exists(docked_pdbqt):
        return None

    # Ligand graph from docked pose
    lig_graph = _build_ligand_graph(ligand_sdf, docked_pdbqt)
    if lig_graph is None:
        return None

    # Protein graph (pocket only)
    lig_coords = lig_graph.pos.numpy() if hasattr(lig_graph, "pos") else None
    if lig_coords is None:
        return None
    prot_graph = _build_protein_graph(protein_pdb, lig_coords)
    if prot_graph is None:
        return None

    # Cross edges
    cross_edges = _build_cross_edges(lig_graph.pos, prot_graph.pos)

    # Read pKi label from INDEX
    label_line = ""
    with open(INDEX_PATH) as f:
        for line in f:
            parts = line.strip().split()
            if parts and parts[0] == pdb_id and len(parts) >= 6 and parts[4] == "//":
                label_line = line.strip()
                break

    pki = 0.0
    if label_line:
        parts = label_line.split()
        try:
            pki = float(parts[5])
        except (ValueError, IndexError):
            pass

    return {
        "protein": prot_graph,
        "ligand": lig_graph,
        "cross": cross_edges,
        "y": pki,
        "y_binary": 1 if pki > 7.0 else 0,
        "pdb_id": pdb_id,
    }


# ═══════════════════════════════════════════════════════════════════════
# PyG Dataset
# ═══════════════════════════════════════════════════════════════════════

class PLComplexDataset(InMemoryDataset):
    """PyG-compatible dataset of protein-ligand complex graphs."""

    def __init__(self, root: str = "", transform=None, pre_transform=None, force_reload: bool = False):
        if not root:
            root = str(PROJECT_ROOT / "data" / "gnn_v2_dataset")
        self._complex_ids = None
        self._samples = None
        super().__init__(root, transform, pre_transform)
        data, _ = torch.load(self.processed_paths[0], weights_only=False)
        self._samples = data  # tuple of dicts
        self._data, self.slices = [], {}  # not used, satisfy parent

    @property
    def raw_dir(self) -> str:
        return str(PDBBIND_DIR)

    @property
    def processed_dir(self) -> str:
        return os.path.join(self.root, "processed")

    @property
    def raw_file_names(self):
        return ["INDEX_refined_data.2020"]

    @property
    def processed_file_names(self):
        return ["gnn_v2_complexes.pt"]

    def process(self):
        """Build all complex graphs and save."""
        with open(INDEX_PATH) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        pdb_ids = [l.split()[0] for l in lines]

        data_list = []
        n_failed = 0
        for i, pid in enumerate(pdb_ids):
            graph = build_complex_graph(pid)
            if graph is not None:
                data_list.append(graph)
            else:
                n_failed += 1
            if (i + 1) % 100 == 0:
                print(f"  [{i+1}/{len(pdb_ids)}] built {len(data_list)} complexes, {n_failed} failed")

        print(f"Total: {len(data_list)} complexes ({n_failed} failed)")

        # Save as (data_tuple, empty_slices) for InMemoryDataset compatibility
        torch.save((tuple(data_list), {}), self.processed_paths[0])
        self._complex_ids = pdb_ids

    def len(self) -> int:
        return len(self._samples) if self._samples is not None else 0

    def get(self, idx: int):
        return self._samples[idx]

    @property
    def num_features_prot(self) -> int:
        if self._samples and len(self._samples) > 0:
            return self._samples[0]["protein"].x.size(1)
        return 24  # 21 one-hot + 3 coords

    @property
    def num_features_lig(self) -> int:
        if self._samples and len(self._samples) > 0:
            return self._samples[0]["ligand"].x.size(1)
        return 38  # 30 elem + 4 hyb + 4 misc (Bucket A.1: 30-element alphabet)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(PROJECT_ROOT / "backend"))
    sys.path.insert(0, str(PROJECT_ROOT / "rescoring"))

    print("Building PLComplexDataset...")
    ds = PLComplexDataset(force_reload=True)
    print(f"Dataset: {len(ds)} complexes")
    print(f"Protein features: {ds.num_features_prot}")
    print(f"Ligand features: {ds.num_features_lig}")

    # Show a sample
    sample = ds[0]
    print(f"\nSample ({sample['pdb_id']}):")
    print(f"  Protein: {sample['protein'].x.shape} nodes, {sample['protein'].edge_index.shape[1]} edges")
    print(f"  Ligand:  {sample['ligand'].x.shape} nodes, {sample['ligand'].edge_index.shape[1]} edges")
    print(f"  Cross edges: {sample['cross'].shape[1]}")
    print(f"  pKi: {sample['y']:.2f} (binder: {bool(sample['y_binary'])})")
