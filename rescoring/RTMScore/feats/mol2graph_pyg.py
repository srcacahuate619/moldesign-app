"""
RTMScore/feats/mol2graph_pyg.py — PyG graph construction for RTMScore.

PyG equivalent of mol2graph_rdmda_res.py. Builds torch_geometric.data.Data
objects instead of dgl.DGLGraph, preserving the same node/edge features and
atomic positions.

The graph structure (nodes, edges, features) is IDENTICAL to the DGL version.
Only the container changes: dgl.DGLGraph → torch_geometric.data.Data.
"""
import re
from itertools import permutations

import MDAnalysis as mda
import numpy as np
import torch as th
from MDAnalysis.analysis import distances
from rdkit import Chem
from scipy.spatial import distance_matrix
from torch_geometric.data import Data

METAL = ["LI","NA","K","RB","CS","MG","TL","CU","AG","BE","NI","PT","ZN","CO","PD","AG","CR","FE","V","MN","HG",'GA',
         "CD","YB","CA","SN","PB","EU","SR","SM","BA","RA","AL","IN","TL","Y","LA","CE","PR","ND","GD","TB","DY","ER",
         "TM","LU","HF","ZR","CE","U","PU","TH"]
RES_MAX_NATOMS = 24


def _pad_positions(positions_list, max_natoms):
    """Pad residue atom positions to max_natoms with NaN, or truncate if larger."""
    padded = []
    for pos in positions_list:
        n_atoms = len(pos)
        pos_arr = np.array(pos[:max_natoms])
        if n_atoms < max_natoms:
            pad = np.full((max_natoms - n_atoms, 3), np.nan)
            pos_arr = np.concatenate([pos_arr, pad], axis=0)
        padded.append(pos_arr)
    return np.array(padded)


def prot_to_graph(prot, cutoff):
    """Build PyG Data graph from protein PDB file."""
    u = mda.Universe(prot)
    num_residues = len(u.residues)

    actual_max = max((len(res.atoms) for res in u.residues), default=0)
    max_natoms = max(actual_max, RES_MAX_NATOMS)

    # Node features
    res_feats = np.array([calc_res_features(res) for res in u.residues])
    x = th.tensor(res_feats, dtype=th.float32)

    # Edge construction
    edgeids, distm = obatin_edge(u, cutoff)
    if edgeids:
        src_list, dst_list = zip(*edgeids)
        edge_index = th.tensor([src_list, dst_list], dtype=th.long)
        # Add reverse edges (undirected)
        rev_index = th.tensor([dst_list, src_list], dtype=th.long)
        edge_index = th.cat([edge_index, rev_index], dim=1)

        # Edge features
        ca_pos = np.array([obtain_ca_pos(res) for res in u.residues])
        center_pos = u.atoms.center_of_mass(compound='residues')

        dis_matx_ca = distance_matrix(ca_pos, ca_pos)
        cadist = th.tensor([dis_matx_ca[i,j] for i,j in zip(src_list, dst_list)], dtype=th.float32) * 0.1

        dis_matx_center = distance_matrix(center_pos, center_pos)
        cedist = th.tensor([dis_matx_center[i,j] for i,j in zip(src_list, dst_list)], dtype=th.float32) * 0.1

        edge_connect = th.tensor([check_connect(u, x, y) for x,y in zip(src_list, dst_list)], dtype=th.float32)
        distm_t = th.tensor(distm, dtype=th.float32)

        edge_attr = th.cat([edge_connect.view(-1,1), cadist.view(-1,1), cedist.view(-1,1), distm_t], dim=1)
        edge_attr = th.cat([edge_attr, edge_attr], dim=0)  # duplicate for reverse edges
    else:
        edge_index = th.zeros((2, 0), dtype=th.long)
        edge_attr = th.zeros((0, 4), dtype=th.float32)

    # Positions (padded to max_natoms)
    all_positions = [res.atoms.positions for res in u.residues]
    pos = th.tensor(_pad_positions(all_positions, max_natoms), dtype=th.float32)

    data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr, pos=pos)
    return data


def obtain_ca_pos(res):
    if obtain_resname(res) == "M":
        return res.atoms.positions[0]
    else:
        try:
            return res.atoms.select_atoms("name CA").positions[0]
        except:
            return res.atoms.positions.mean(axis=0)


def one_of_k_encoding(x, allowable_set):
    if x not in allowable_set:
        raise Exception(f"input {x} not in allowable set {allowable_set}")
    return [x == s for s in allowable_set]


def one_of_k_encoding_unk(x, allowable_set):
    if x not in allowable_set:
        x = allowable_set[-1]
    return [x == s for s in allowable_set]


def obtain_self_dist(res):
    try:
        xx = res.atoms
        dists = distances.self_distance_array(xx.positions)
        ca = xx.select_atoms("name CA")
        c = xx.select_atoms("name C")
        n = xx.select_atoms("name N")
        o = xx.select_atoms("name O")
        return [dists.max()*0.1, dists.min()*0.1,
                distances.dist(ca,o)[-1][0]*0.1,
                distances.dist(o,n)[-1][0]*0.1,
                distances.dist(n,c)[-1][0]*0.1]
    except:
        return [0, 0, 0, 0, 0]


def obtain_dihediral_angles(res):
    try:
        phi = res.phi_selection().dihedral.value() if res.phi_selection() is not None else 0
        psi = res.psi_selection().dihedral.value() if res.psi_selection() is not None else 0
        omega = res.omega_selection().dihedral.value() if res.omega_selection() is not None else 0
        chi1 = res.chi1_selection().dihedral.value() if res.chi1_selection() is not None else 0
        return [phi*0.01, psi*0.01, omega*0.01, chi1*0.01]
    except:
        return [0, 0, 0, 0]


def calc_res_features(res):
    return np.array(
        one_of_k_encoding_unk(obtain_resname(res),
            ['GLY','ALA','VAL','LEU','ILE','PRO','PHE','TYR','TRP','SER','THR','CYS','MET',
             'ASN','GLN','ASP','GLU','LYS','ARG','HIS','MSE','CSO','PTR','TPO','KCX','CSD',
             'SEP','MLY','PCA','LLP','M','X']) +
        obtain_self_dist(res) +
        obtain_dihediral_angles(res)
    )


def obtain_resname(res):
    if res.resname[:2] == "CA": return "CA"
    elif res.resname[:2] == "FE": return "FE"
    elif res.resname[:2] == "CU": return "CU"
    else: resname = res.resname.strip()
    return "M" if resname in METAL else resname


def obatin_edge(u, cutoff=10.0):
    edgeids = []
    dismin = []
    dismax = []
    for res1, res2 in permutations(u.residues, 2):
        dist = calc_dist(res1, res2)
        if dist.min() <= cutoff:
            edgeids.append([res1.ix, res2.ix])
            dismin.append(dist.min()*0.1)
            dismax.append(dist.max()*0.1)
    return edgeids, np.array([dismin, dismax]).T


def check_connect(u, i, j):
    if abs(i-j) != 1:
        return 0
    else:
        i = min(i, j)
        nb1 = len(u.residues[i].get_connections("bonds"))
        nb2 = len(u.residues[i+1].get_connections("bonds"))
        nb3 = len(u.residues[i:i+2].get_connections("bonds"))
        return 1 if nb1 + nb2 == nb3 + 1 else 0


def calc_dist(res1, res2):
    dist_array = distances.distance_array(res1.atoms.positions, res2.atoms.positions)
    return dist_array


def calc_atom_features(atom, explicit_H=False):
    results = (one_of_k_encoding_unk(atom.GetSymbol(),
        ['C','N','O','S','F','P','Cl','Br','I','B','Si','Fe','Zn','Cu','Mn','Mo','other']) +
        one_of_k_encoding(atom.GetDegree(), [0,1,2,3,4,5,6]) +
        [atom.GetFormalCharge(), atom.GetNumRadicalElectrons()] +
        one_of_k_encoding_unk(atom.GetHybridization(),
            [Chem.rdchem.HybridizationType.SP, Chem.rdchem.HybridizationType.SP2,
             Chem.rdchem.HybridizationType.SP3, Chem.rdchem.HybridizationType.SP3D,
             Chem.rdchem.HybridizationType.SP3D2, 'other']) +
        [atom.GetIsAromatic()])
    if not explicit_H:
        results = results + one_of_k_encoding_unk(atom.GetTotalNumHs(), [0,1,2,3,4])
    return np.array(results)


def calc_bond_features(bond, use_chirality=True):
    bt = bond.GetBondType()
    bond_feats = [
        bt == Chem.rdchem.BondType.SINGLE, bt == Chem.rdchem.BondType.DOUBLE,
        bt == Chem.rdchem.BondType.TRIPLE, bt == Chem.rdchem.BondType.AROMATIC,
        bond.GetIsConjugated(), bond.IsInRing()]
    if use_chirality:
        bond_feats += one_of_k_encoding_unk(str(bond.GetStereo()),
            ["STEREONONE", "STEREOANY", "STEREOZ", "STEREOE"])
    return np.array(bond_feats).astype(int)


def load_mol(molpath, explicit_H=False, use_chirality=True):
    if re.search(r'.pdb$', molpath):
        mol = Chem.MolFromPDBFile(molpath, removeHs=not explicit_H)
    elif re.search(r'.mol2$', molpath):
        mol = Chem.MolFromMol2File(molpath, removeHs=not explicit_H)
    elif re.search(r'.sdf$', molpath):
        mol = Chem.MolFromMolFile(molpath, removeHs=not explicit_H)
    else:
        raise OSError("only .pdb|.sdf|.mol2 supported!")
    if use_chirality:
        Chem.AssignStereochemistryFrom3D(mol)
    return mol


def mol_to_graph(mol, explicit_H=False, use_chirality=True):
    """Build PyG Data graph from RDKit Mol."""
    num_atoms = mol.GetNumAtoms()
    atom_feats = np.array([calc_atom_features(a, explicit_H=explicit_H) for a in mol.GetAtoms()])

    if use_chirality:
        chiralcenters = Chem.FindMolChiralCenters(mol, force=True, includeUnassigned=True, useLegacyImplementation=False)
        chiral_arr = np.zeros([num_atoms, 3])
        for (i, rs) in chiralcenters:
            if rs == 'R': chiral_arr[i,0] = 1
            elif rs == 'S': chiral_arr[i,1] = 1
            else: chiral_arr[i,2] = 1
        atom_feats = np.concatenate([atom_feats, chiral_arr], axis=1)

    x = th.tensor(atom_feats, dtype=th.float32)

    # Positions
    atom_coords = mol.GetConformer().GetPositions()
    pos = th.tensor(atom_coords, dtype=th.float32)

    # Edges
    src_list, dst_list = [], []
    bond_feats_all = []
    num_bonds = mol.GetNumBonds()
    for i in range(num_bonds):
        bond = mol.GetBondWithIdx(i)
        u, v = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        bond_feats = calc_bond_features(bond, use_chirality=use_chirality)
        src_list.extend([u, v])
        dst_list.extend([v, u])
        bond_feats_all.append(bond_feats)
        bond_feats_all.append(bond_feats)

    if len(src_list) > 0:
        edge_index = th.tensor([src_list, dst_list], dtype=th.long)
        edge_attr = th.tensor(np.array(bond_feats_all), dtype=th.float32)
    else:
        edge_index = th.zeros((2, 0), dtype=th.long)
        edge_attr = th.zeros((0, len(bond_feats_all[0]) if bond_feats_all else 10), dtype=th.float32)

    data = Data(x=x, edge_index=edge_index, edge_attr=edge_attr, pos=pos)
    return data


def mol_to_graph2(prot_path, lig_path, cutoff=10.0, explicit_H=False, use_chirality=True):
    """Build both protein and ligand graphs (PyG version)."""
    gp = prot_to_graph(prot_path, cutoff)
    lig = load_mol(lig_path, explicit_H=explicit_H, use_chirality=use_chirality)
    gl = mol_to_graph(lig, explicit_H=explicit_H, use_chirality=use_chirality)
    return gp, gl
