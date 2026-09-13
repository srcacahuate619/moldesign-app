import os
import tempfile
import warnings
from functools import lru_cache

import torch as th
from rdkit import Chem

# [FIX] MDAnalysis 2.8.0 emite DeprecationWarnings por np.bool_ en sus tablas
# de topología internas. El filtro se amplia con `module=r"MDAnalysis"` para
# capturar tanto el módulo raíz como todos sus sub-módulos (topology.tables, etc.)
with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message=r".*np\.bool_.*",
        category=DeprecationWarning,
    )
    import MDAnalysis as mda
from logger import get_logger
from RTMScore.feats.mol2graph_pyg import (
    load_mol,
    mol_to_graph,
    prot_to_graph,
)
from RTMScore.model.model2_pyg import DGLGraphTransformer, RTMScore
from RTMScore.model.utils import calculate_probablity
from torch_geometric.data import Batch

log = get_logger(__name__)
_MODEL_CACHE = {}

# Cache del Universe de proteínas: el target PDB NO cambia entre requests,
# y leer+parsear PDB es ~50-200ms por call. lru_cache por path + mtime evita
# ese coste en llamadas subsiguientes al mismo target.
@lru_cache(maxsize=8)
def _load_protein_universe(protein_pdb_path: str, _mtime: float) -> "mda.Universe":
    """Carga un mda.Universe cacheado por path+mtime.
    El segundo arg (_mtime) invalida el cache si el archivo PDB cambió en disco.
    No usar directamente — usar _get_protein_universe(path).
    """
    return mda.Universe(protein_pdb_path)


def _get_protein_universe(protein_pdb_path: str) -> "mda.Universe":
    """Wrapper que invalida el cache si el archivo PDB cambió en disco."""
    mtime = os.path.getmtime(protein_pdb_path)
    return _load_protein_universe(protein_pdb_path, mtime)

def load_rtmscore_from_checkpoint(model_path: str, device: str = "cpu") -> RTMScore:
    """
    Carga el modelo pre-entrenado de RTMScore infiriendo las dimensiones
    de forma dinámica a partir de las formas de los pesos del checkpoint.
    """
    if model_path in _MODEL_CACHE:
        return _MODEL_CACHE[model_path]

    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Checkpoint de pesos de modelo no encontrado en {model_path}")

    checkpoint = th.load(model_path, map_location=device, weights_only=True)
    state_dict = checkpoint.get("model_state_dict", checkpoint)

    # Inferir dimensiones del modelo a partir del state_dict
    lig_in_channels = state_dict["lig_model.node_encoder.weight"].shape[1]
    lig_edge_features = state_dict["lig_model.edge_encoder.weight"].shape[1]
    
    prot_in_channels = state_dict["prot_model.node_encoder.weight"].shape[1]
    prot_edge_features = state_dict["prot_model.edge_encoder.weight"].shape[1]
    
    hidden_dim = state_dict["MLP.0.weight"].shape[0]
    n_gaussians = state_dict["z_pi.weight"].shape[0]
    
    # Inferir número de capas de Graph Transformer
    gt_layers = set()
    for key in state_dict.keys():
        if "lig_model.gt_block." in key:
            parts = key.split(".")
            if len(parts) > 2 and parts[2].isdigit():
                gt_layers.add(int(parts[2]))
    num_layers = len(gt_layers)

    log.info(
        "rtmscore_model_inferred",
        lig_in=lig_in_channels,
        lig_edge=lig_edge_features,
        prot_in=prot_in_channels,
        prot_edge=prot_edge_features,
        hidden=hidden_dim,
        layers=num_layers,
        gaussians=n_gaussians
    )

    # Instanciar el transformer del ligando
    lig_model = DGLGraphTransformer(
        in_channels=lig_in_channels,
        edge_features=lig_edge_features,
        num_hidden_channels=hidden_dim,
        num_layers=num_layers,
        dropout_rate=0.15
    )
    
    # Instanciar el transformer del receptor
    prot_model = DGLGraphTransformer(
        in_channels=prot_in_channels,
        edge_features=prot_edge_features,
        num_hidden_channels=hidden_dim,
        num_layers=num_layers,
        dropout_rate=0.15
    )
    
    # Instanciar RTMScore completo
    model = RTMScore(
        lig_model=lig_model,
        prot_model=prot_model,
        in_channels=hidden_dim,
        hidden_dim=hidden_dim,
        n_gaussians=n_gaussians,
        dropout_rate=0.15
    )
    
    model.load_state_dict(state_dict)
    model.to(device)
    model.eval()
    
    _MODEL_CACHE[model_path] = model
    return model

def parse_ligand_3d(pose_pdbqt_block: str, smiles: str = "") -> Chem.Mol:
    """
    Intenta parsear el ligando con coordenadas 3D de forma robusta.

    Estrategia (en orden):
      1. Meeko PDBQT → PDB string → RDKit (mejor preservación de tipos atómicos)
      2. Cleaned PDB block parse (rápido, confiable para bloques bien formados)
      3. MDAnalysis conversion flow (robusto para formatos mixtos PDB/PDBQT)
    """
    # Intento 1: Meeko PDBQT → write_pdbqt_string → RDKit PDB parse
    try:
        from meeko import PDBQTMolecule
        pdbqt_mol = PDBQTMolecule(pose_pdbqt_block, is_dlg=False, skip_typing=True)
        # [FIX] export_rdkit_mol() fue removido en Meeko >=0.5.
        # Usar write_pdbqt_string() y parsear el output como PDB con RDKit.
        pdb_string = pdbqt_mol.write_pdbqt_string()
        mol = Chem.MolFromPDBBlock(pdb_string, sanitize=False, removeHs=False)
        if mol is not None and mol.GetNumConformers() > 0:
            try:
                Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
            except Exception:
                pass
            return mol
    except Exception as e:
        log.debug("meeko_parsing_failed", error=str(e))
        
    # Intento 2: Cleaned and truncated PDB block parse (highly robust)
    try:
        clean_lines = []
        for line in pose_pdbqt_block.splitlines():
            if line.startswith(("ATOM", "HETATM")):
                clean_lines.append(line[:66])
            elif line.startswith(("MODEL", "ENDMDL", "TER")):
                clean_lines.append(line)
        clean_block = "\n".join(clean_lines)
        mol = Chem.MolFromPDBBlock(clean_block, sanitize=False)
        if mol is not None and mol.GetNumConformers() > 0:
            try:
                Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
                return mol
            except Exception:
                return mol
    except Exception as e:
        log.debug("cleaned_pdb_unsan_parse_failed", error=str(e))


    # Intento 3: MDAnalysis conversion flow (el más robusto para PDB/PDBQT mixto)
    tmp_clean = None
    tmp_pdb = None
    try:
        fd, tmp_pdb = tempfile.mkstemp(suffix=".pdb")
        os.close(fd)
        with open(tmp_pdb, "w") as f:
            f.write(pose_pdbqt_block)
        
        u_lig = mda.Universe(tmp_pdb)
        # MDAnalysis no siempre adivina elementos de PDBQT automáticamente
        from MDAnalysis.topology.guessers import guess_types
        elements = guess_types(u_lig.atoms.names)
        u_lig.add_TopologyAttr('elements', elements)
        u_lig.add_TopologyAttr('types', elements)
        
        fd2, tmp_clean = tempfile.mkstemp(suffix=".pdb")
        os.close(fd2)
        u_lig.atoms.write(tmp_clean)
        mol = Chem.MolFromPDBFile(tmp_clean, sanitize=False)
        if mol is not None and mol.GetNumConformers() > 0:
            try:
                Chem.SanitizeMol(mol, Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
            except Exception:
                pass
            return mol
    except Exception as e:
        log.warning("mda_ligand_parsing_failed", error=str(e))
    finally:
        if tmp_clean and os.path.exists(tmp_clean):
            os.remove(tmp_clean)
        if tmp_pdb and os.path.exists(tmp_pdb):
            os.remove(tmp_pdb)

    raise ValueError("No se pudo parsear el ligando con 3D coordenadas desde el bloque PDBQT.")

def extract_pocket_mda(protein_pdb: str, ligand_mol: Chem.Mol, cutoff: float = 10.0) -> str:
    """
    Extrae los residuos de la proteína pdb que estén dentro del radio `cutoff`
    del `ligand_mol` usando MDAnalysis, guardándolos en un PDB temporal.
    """
    if ligand_mol.GetNumConformers() == 0:
        log.warning("extract_pocket_no_coords", msg="Ligando sin conformer 3D, usando proteína completa como pocket.")
        # Copiar la proteína completa a un archivo temporal para ser consistente
        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as tmp_pocket:
            tmp_pocket_path = tmp_pocket.name
        import shutil
        shutil.copy(protein_pdb, tmp_pocket_path)
        return tmp_pocket_path

    # Guardar ligando a un PDB temporal
    with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as tmp_lig:
        tmp_lig_path = tmp_lig.name
    Chem.MolToPDBFile(ligand_mol, tmp_lig_path)
    
    try:
        # Cargar proteína (cacheada por path+mtime) y ligando en MDAnalysis
        u_prot = _get_protein_universe(protein_pdb)
        u_lig = mda.Universe(tmp_lig_path)
        
        # Combinar Universos para evitar el bug de indices inter-universe en select_atoms
        u_combined = mda.Merge(u_prot.atoms, u_lig.atoms)
        n_lig_atoms = len(u_lig.atoms)
        lig_in_combined = u_combined.atoms[-n_lig_atoms:]
        
        # Seleccionar átomos de la proteína (del pocket) en el universo combinado
        pocket_in_combined = u_combined.select_atoms(
            f"byres (around {cutoff} group mylig)", 
            mylig=lig_in_combined
        )
        pocket_atoms = pocket_in_combined.select_atoms("not group mylig", mylig=lig_in_combined)
        
        # Guardar bolsillo a un PDB temporal
        with tempfile.NamedTemporaryFile(suffix=".pdb", delete=False) as tmp_pocket:
            tmp_pocket_path = tmp_pocket.name
        
        pocket_atoms.write(tmp_pocket_path)
    finally:
        # Limpieza del PDB temporal del ligando
        # [FIX] Windows: MDAnalysis puede mantener file locks en PDBs.
        # Reintentar con delay para evitar PermissionError.
        if os.path.exists(tmp_lig_path):
            for _ in range(3):
                try:
                    os.remove(tmp_lig_path)
                    break
                except PermissionError:
                    import time as _time
                    _time.sleep(0.1)
            else:
                try:
                    os.remove(tmp_lig_path)
                except PermissionError:
                    pass  # Windows file lock, will be cleaned by OS later
            
    return tmp_pocket_path

def evaluate_rtmscore(
    smiles: str,
    protein_pdb_path: str,
    pose_pdbqt_block: str,
    model_path: str = "trained_models/rtmscore_model1.pth",
    cutoff: float = 10.0,
    device: str | None = None
) -> float:
    """
    Ejecuta el pipeline de inferencia GNN RTMScore completo.
    Auto-detecta GPU si está disponible.
    """
    if device is None:
        # PyG + torch_scatter tienen CUDA nativo via pip en Windows.
        # Auto-detectar GPU y usarla directamente.
        if th.cuda.is_available():
            device = "cuda"
            log.info("gnn_device_cuda", gpu=th.cuda.get_device_name(0))
        else:
            device = "cpu"
    
    # 1. Parsear ligando de forma robusta con 3D coords
    lig_mol = parse_ligand_3d(pose_pdbqt_block, smiles)
            
    # 2. Extraer residuos del bolsillo
    pocket_pdb_path = extract_pocket_mda(protein_pdb_path, lig_mol, cutoff=cutoff)
    
    # 3. Crear SDF temporal para el ligando
    with tempfile.NamedTemporaryFile(suffix=".sdf", delete=False) as tmp_sdf:
        tmp_sdf_path = tmp_sdf.name
    
    writer = Chem.SDWriter(tmp_sdf_path)
    writer.write(lig_mol)
    writer.close()
    
    try:
        # 4. Convertir pocket e input a grafos PyG
        # [FIX] Bypass RDKit round-trip: pasar el path del PDB directamente
        # a prot_to_graph (PyG version)
        gp = prot_to_graph(pocket_pdb_path, cutoff)
        lig_mol_sdf = load_mol(tmp_sdf_path, explicit_H=False, use_chirality=True)
        gl = mol_to_graph(lig_mol_sdf, explicit_H=False, use_chirality=True)
        
        if gp is None or gl is None:
            raise ValueError("Fallo al generar grafos PyG a partir de las estructuras moleculares.")
        
        # Validate graph dimensions before inference.
        if gp.num_nodes == 0:
            raise ValueError(f"Grafo de proteina vacio (0 nodos). Pocket sin residuos en {cutoff}A de cutoff.")
        if gl.num_nodes == 0:
            raise ValueError("Grafo de ligando vacio (0 nodos).")
        if gp.num_edges == 0:
            raise ValueError("Grafo de proteina sin edges. PDB posiblemente mal formado.")
        if gl.num_edges == 0 and gl.num_nodes > 1:
            log.warning("gnn_ligand_no_edges", nodes=gl.num_nodes)
        
        if not hasattr(gp, 'x') or not hasattr(gl, 'x'):
            raise ValueError("Grafos PyG sin node features.")
            
        # 5. Cargar modelo y ejecutar inferencia
        model = load_rtmscore_from_checkpoint(model_path, device=device)
        
        # Agrupar grafos para la inferencia de un solo complejo
        bgp = Batch.from_data_list([gp]).to(device)
        bgl = Batch.from_data_list([gl]).to(device)
        
        with th.no_grad():
            pi, sigma, mu, dist, atom_types, bond_types, batch = model(bgp, bgl)
            prob = calculate_probablity(pi, sigma, mu, dist)
            
            # Sumar predicciones y normalizar por átomos pesados del ligando
            # [FIX] El score crudo escala con el número de átomos (más átomos =
            # más pares ligando-proteína = score más alto). Normalizar por heavy
            # atoms produce scores comparables entre moléculas de distinto tamaño.
            raw_score = float(prob.sum().cpu().item())
            n_heavy = sum(1 for a in lig_mol.GetAtoms() if a.GetAtomicNum() > 1)
            if n_heavy > 0:
                score = raw_score / n_heavy
            else:
                score = raw_score
            
            # XAI: Calcular atención por átomo del ligando
            try:
                contrib = prob.view(bgl.num_nodes, bgp.num_nodes).sum(1)
                # Normalizar entre 0 y 1 para el mapa de calor
                max_val = contrib.max().clamp(min=1e-6)
                attention = (contrib / max_val).cpu().detach().numpy().tolist()
                
                from rdkit.Chem import rdDepictor
                from rdkit.Chem.Draw import SimilarityMaps, rdMolDraw2D
                
                # 1. Filter heavy atoms and their attention
                # bgl graph was created with explicit_H=False, so attention corresponds 1-to-1 to heavy atoms
                lig_heavy = Chem.RemoveHs(lig_mol)
                heavy_attention = attention
                
                # 2. Perfect SMILES molecule (no explicit hydrogens by default)
                ref_mol = Chem.MolFromSmiles(smiles)
                
                # 3. Create queries for topology match ignoring bond orders and charges
                lig_query = Chem.Mol(lig_heavy)
                for bond in lig_query.GetBonds():
                    bond.SetBondType(Chem.BondType.SINGLE)
                    bond.SetIsAromatic(False)
                for atom in lig_query.GetAtoms():
                    atom.SetIsAromatic(False)
                    atom.SetFormalCharge(0)
                    
                ref_query = Chem.Mol(ref_mol)
                for bond in ref_query.GetBonds():
                    bond.SetBondType(Chem.BondType.SINGLE)
                    bond.SetIsAromatic(False)
                for atom in ref_query.GetAtoms():
                    atom.SetIsAromatic(False)
                    atom.SetFormalCharge(0)
                
                # 4. Topological match
                match = lig_query.GetSubstructMatch(ref_query)
                
                if match and len(match) == ref_mol.GetNumAtoms() and all(m < len(heavy_attention) for m in match):
                    # Reorder heavy_attention to match ref_mol exactly
                    attention_mapped = [heavy_attention[match[i]] for i in range(ref_mol.GetNumAtoms())]
                    mol_to_draw = Chem.Mol(ref_mol)
                else:
                    # Fallback: if lengths don't match, just use what we have
                    attention_mapped = heavy_attention[:lig_heavy.GetNumAtoms()]
                    if len(attention_mapped) < lig_heavy.GetNumAtoms():
                        attention_mapped += [0.0] * (lig_heavy.GetNumAtoms() - len(attention_mapped))
                    mol_to_draw = Chem.Mol(lig_heavy)
                
                rdDepictor.Compute2DCoords(mol_to_draw)
                
                d = rdMolDraw2D.MolDraw2DSVG(400, 400)
                opts = d.drawOptions()
                opts.clearBackground = False
                
                SimilarityMaps.GetSimilarityMapFromWeights(mol_to_draw, attention_mapped, draw2d=d)
                d.FinishDrawing()
                attention_svg = d.GetDrawingText()
                
                # Calcular Desglose por Farmacóforos
                pharmacophore_smarts = {
                    "Aromáticos": "[a]", 
                    "Donadores de H": "[!H0;#7,#8,#9]", 
                    "Aceptores de H": "[!$([#6,F,Cl,Br,I,o,s,nX3,#7v5,#15v5,#16v4,#16v6,*+1,*+2,*+3])]",
                    "Alifáticos": "[CX4]", 
                    "Halógenos": "[F,Cl,Br,I]",
                }
                
                gnn_pharmacophores = {k: 0.0 for k in pharmacophore_smarts}
                total_mapped_attention = 0.0
                
                for name, smarts in pharmacophore_smarts.items():
                    pattern = Chem.MolFromSmarts(smarts)
                    if pattern:
                        matches = mol_to_draw.GetSubstructMatches(pattern)
                        matched_indices = set()
                        for match_tuple in matches:
                            matched_indices.update(match_tuple)
                        
                        for atom_idx in matched_indices:
                            if atom_idx < len(attention_mapped):
                                gnn_pharmacophores[name] += attention_mapped[atom_idx]
                                total_mapped_attention += attention_mapped[atom_idx]
                
                if total_mapped_attention > 0:
                    for name in gnn_pharmacophores:
                        gnn_pharmacophores[name] = round((gnn_pharmacophores[name] / total_mapped_attention) * 100, 1)
                else:
                    gnn_pharmacophores = None
                
            except Exception as e:
                log.warning("gnn_attention_failed", error=str(e))
                attention = [0.0] * bgl.num_nodes()
                attention_svg = None
                gnn_pharmacophores = None
            
        return score, attention, attention_svg, gnn_pharmacophores
        
    finally:
        # Limpieza de archivos temporales (Windows-safe con retry)
        for _path in (pocket_pdb_path, tmp_sdf_path):
            if _path and os.path.exists(_path):
                for _ in range(3):
                    try:
                        os.remove(_path)
                        break
                    except PermissionError:
                        import time as _time
                        _time.sleep(0.1)
                else:
                    try:
                        os.remove(_path)
                    except PermissionError:
                        pass
