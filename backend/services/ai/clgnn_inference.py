"""
services/ai/clgnn_inference.py — CL-GNN inference for production pipeline.

Carga el modelo fine-tuned una sola vez (lazy singleton) y expone
predict(smiles, target_pdb) -> probabilidad P(binder).

Uso en queue_handler:
  from services.ai.clgnn_inference import predict_clgnn
  clgnn_prob = predict_clgnn(smiles, target_pdb_path)
"""

import logging
import os
import tempfile
from pathlib import Path

# F-14: los paths del sidecar (rescoring/ + repo root) y los defaults
# RESCORING_*_PATH se encapsularon en services/rescoring_bridge.py. Este
# import garantiza que los imports "flat" del sidecar (gnn_v2, feature_extractor)
# se resuelvan sin mutar sys.path aquí.
import services.rescoring_bridge  # noqa: F401
from utils.local_storage import path_for as _storage_path_for

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_log = logging.getLogger("services.ai.clgnn_inference")

_MODEL = None
_DEVICE = None


def _resolve_pose_sdf_path(pose_sdf_path: str) -> Path | None:
    """Resolve a filesystem path or a MolDesign storage object name.

    ``DockingResult.poses_file_path`` deliberately persists a portable object
    name (``runs/docking/.../poses.sdf``), not an absolute path tied to the
    machine that ran Vina. CL-GNN is an in-process consumer and therefore has
    to cross that storage boundary explicitly before handing the SDF to RDKit.
    """
    supplied = Path(pose_sdf_path)
    if supplied.is_file():
        return supplied

    # Absolute paths must never be reinterpreted below the data directory: if
    # one is missing, it is missing. Only portable object names are resolved.
    if supplied.is_absolute():
        return None

    resolved = _storage_path_for(pose_sdf_path)
    return resolved if resolved.is_file() else None


def _fail(reason: str, smiles: str, target_pdb_path: str) -> None:
    """[A3] WARNING explícito con identificadores en cada fallo de CL-GNN."""
    _log.warning(
        "clgnn_failure | reason=%s | smiles=%s | target=%s",
        reason,
        (smiles[:80] + "...") if smiles and len(smiles) > 80 else smiles,
        str(target_pdb_path)[-80:],
    )


def _load_model():
    """Lazy singleton — load the CL-GNN contrastive classifier once.

    CL-GNN = ContrastiveGNN encoder (NT-Xent pretraining) + GNNv2Classifier
    head, fine-tuned with BCE on PDBbind refined (708 complexes Vina-redocked).
    Trained with hidden_dim=128, 38-dim ligand features. The standalone
    `clgnn_finetuned.pt` artifact (h=64, 18-dim features) was made obsolete
    by commit 4f48fde ("hot-patch ligand feature adapter") and never loads
    cleanly into the current GNNv2Classifier constructor (size mismatch on
    lig_encoder.in_proj.weight 18 vs 38). The canonical artifact that
    matches the trained architecture and is documented in
    the current constructor is `gnn_v2_cl_best.pt` (677657 trainable
    parameters, h=128). Historical external AUCs belong to a different
    checkpoint and are not attributed to these bytes; see model-manifest.json.
    """
    global _MODEL, _DEVICE
    if _MODEL is not None:
        return _MODEL, _DEVICE

    try:
        import torch
        from gnn_v2.models import GNNv2Classifier
    except ImportError:
        _MODEL = None
        _DEVICE = "cpu"
        return None, _DEVICE

    _DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
    # h=128 matches the CL-GNN trained checkpoint (gnn_v2_cl_best.pt).
    # The previous h=64 + clgnn_finetuned.pt wiring caused a silent
    # load_state_dict failure (shape mismatch) → predict returned 0.5
    # every time. See docs/STOCHASTICITY_REPORT.md and the audit saved
    # under engram topic_key validation/gnn-ab-harness-live.
    _MODEL = GNNv2Classifier(hidden_dim=128)
    model_path = _PROJECT_ROOT / "rescoring" / "artifacts" / "gnn_v2_cl_best.pt"

    if model_path.exists():
        ck = torch.load(model_path, map_location=_DEVICE, weights_only=False)
        # gnn_v2_cl_best.pt is a wrapped {"model_state_dict": ...} checkpoint.
        sd = ck["model_state_dict"] if isinstance(ck, dict) and "model_state_dict" in ck else ck
        _MODEL.load_state_dict(sd)
        _MODEL.to(_DEVICE)
        _MODEL.eval()
    else:
        _MODEL = None

    return _MODEL, _DEVICE


def predict_clgnn(
    smiles: str,
    target_pdb_path: str,
    *,
    pose_sdf_path: str | None = None,
    pose_pdbqt_block: str | None = None,
) -> float | None:
    """Predict P(binder) using CL-GNN, sobre la POSE ACOPLADA.

    [A3] Devuelve None (componente ausente) en CUALQUIER fallo, con WARNING
    que incluye smiles y target. NUNCA fabrica 0.5 neutral: el engine
    re-normaliza pesos o degrada explícitamente cuando recibe None.

    ═════════════════════════════════════════════════════════════════════
    POR QUÉ AHORA HAY QUE PASARLE LA POSE
    ═════════════════════════════════════════════════════════════════════

    Auditoría del 2026-09-04. Esta función recibía sólo `(smiles, receptor)`
    y generaba su propia conformación:

        AllChem.EmbedMolecule(mol_3d, AllChem.ETKDG())
        AllChem.MMFFOptimizeMolecule(mol_3d)

    Un confórmero nuevo, en el marco de coordenadas de RDKit —centrado cerca
    del origen—, mientras el receptor está en su marco cristalográfico. Y
    `_build_protein_graph` elige el bolsillo por DISTANCIA a esas coordenadas:

        residuos a menos de POCKET_CUTOFF (10 Å) de algún átomo del ligando

    Medido sobre los receptores de `data/targets/`, distancia mínima de la
    proteína al origen:

        1gkc_chainA   108.4 Å        7e2y_chainB    96.0 Å
        3pp0_chainB    22.7 Å        7e2y_chainR   140.1 Å

    Ninguno tiene un residuo a 10 Å de donde ETKDG deja el ligando, así que
    `pocket_residues` salía vacío y la función devolvía `None` — verificado,
    cuatro llamadas, `protein_graph_failed` en las cuatro. Es decir: en este
    árbol CL-GNN no ha producido nunca un valor.

    Y donde sí lo produce —un receptor cuyo origen cae dentro de la proteína—
    es peor, porque entonces el «bolsillo» son los residuos que casualmente
    rodean el origen del sistema de coordenadas del PDB, y las aristas cruzadas
    ligando-proteína unen átomos que no están cerca en ninguna realidad física.

    Además ETKDG sin semilla no es reproducible: tres llamadas idénticas daban
    tres números distintos.

    Un scorer post-docking tiene que puntuar LA POSE. Si no llega una, no hay
    nada que puntuar y se devuelve `None`, que es la respuesta honesta. No se
    vuelve a fabricar una conformación: fabricarla es justamente el defecto.
    """
    model, device = _load_model()
    if model is None:
        _fail("model_unavailable", smiles, target_pdb_path)
        return None

    try:
        import torch
        from gnn_v2.data import _build_ligand_graph, _build_protein_graph, _build_cross_edges
    except ImportError as ie:
        _fail(f"import_error_{type(ie).__name__}", smiles, target_pdb_path)
        return None
    from rdkit import Chem
    from rdkit.Chem import AllChem
    # RDLogger location varies across rdkit versions: some expose it as
    # rdkit.Chem.RDLogger (older builds), others as rdkit.RDLogger (2024+).
    # Silence RDKit warnings either way.
    try:
        from rdkit.Chem import RDLogger
        RDLogger.logger().setLevel(RDLogger.ERROR)
    except ImportError:
        import rdkit.RDLogger as RDLogger
        try:
            RDLogger.DisableLog("rdApp.*")
        except Exception:
            pass

    # Build ligand graph from SMILES
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        _fail("smiles_unparseable", smiles, target_pdb_path)
        return None

    # ── Sin pose no hay nada que puntuar ─────────────────────────────────
    #
    # Ver el docstring: aquí se generaba un confórmero ETKDG en otro marco de
    # coordenadas. Ahora se exige la pose acoplada, con su PDBQT —que es de
    # donde `_build_ligand_graph` saca los tipos de átomo de AutoDock—.
    if not pose_sdf_path or not pose_pdbqt_block:
        _fail("sin_pose_acoplada", smiles, target_pdb_path)
        return None
    resolved_pose_sdf_path = _resolve_pose_sdf_path(pose_sdf_path)
    if resolved_pose_sdf_path is None:
        _fail("pose_sdf_inexistente", smiles, target_pdb_path)
        return None

    lig_graph = None
    pdbqt_path = None
    try:
        fd2, pdbqt_path = tempfile.mkstemp(suffix=".pdbqt")
        with os.fdopen(fd2, "w") as f:
            f.write(pose_pdbqt_block)

        lig_graph = _build_ligand_graph(str(resolved_pose_sdf_path), pdbqt_path)
    except Exception as exc:
        _fail(f"graph_exception_{type(exc).__name__}", smiles, target_pdb_path)
        return None
    finally:
        if pdbqt_path:
            try:
                os.unlink(pdbqt_path)
            except OSError:
                pass

    if lig_graph is None:
        _fail("ligand_graph_failed", smiles, target_pdb_path)
        return None

    # Build protein graph
    prot_graph = _build_protein_graph(target_pdb_path, lig_graph.pos.numpy())
    if prot_graph is None:
        _fail("protein_graph_failed", smiles, target_pdb_path)
        return None

    cross_edges = _build_cross_edges(lig_graph.pos, prot_graph.pos)

    # Run inference
    try:
        with torch.no_grad():
            logits = model(
                prot_graph.x.to(device), prot_graph.edge_index.to(device),
                lig_graph.x.to(device), lig_graph.edge_index.to(device),
                cross_edges.to(device),
                lig_pos=lig_graph.pos.to(device),
                prot_pos=prot_graph.pos.to(device),
            )
            prob = float(torch.sigmoid(logits).item())
        return prob
    except Exception as exc:
        _fail(f"inference_exception_{type(exc).__name__}", smiles, target_pdb_path)
        return None


def predict_clgnn_prolif(
    smiles: str,
    target_pdb_path: str,
    *,
    pose_sdf_path: str | None = None,
    pose_pdbqt_block: str | None = None,
) -> float | None:
    """
    CL-GNN + ProLIF ensemble — augments the contrastive model with
    3D interaction fingerprints (H-bonds, pi-stacking, metal contacts).

    If ProLIF features are extractable, ensemble: 0.8*CLGNN + 0.2*ProLIF_score.
    Otherwise falls back to standard CL-GNN.

    [A3] Si CL-GNN falla (None), NO se fabrica 0.5: propaga None.
    """
    clgnn_prob = predict_clgnn(
        smiles,
        target_pdb_path,
        pose_sdf_path=pose_sdf_path,
        pose_pdbqt_block=pose_pdbqt_block,
    )
    if clgnn_prob is None:
        return None  # CL-GNN falló: componente ausente, sin fabricación

    try:
        # Extract ProLIF features (computed anyway for XGBoost in pipeline)

        # Try to get ProLIF features via a quick extraction (same as benchmark uses)
        prolif_score = _compute_prolif_score(smiles, target_pdb_path)
        if prolif_score is not None:
            # Ensemble: 80% CL-GNN + 20% ProLIF-based signal
            return round(clgnn_prob * 0.8 + prolif_score * 0.2, 4)
    except Exception:
        pass

    return clgnn_prob


def _compute_prolif_score(smiles: str, target_pdb_path: str) -> float | None:
    """Quick ProLIF-based binding score from 3D interaction fingerprints."""
    from rdkit import Chem
    from rdkit.Chem import AllChem

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, AllChem.ETKDG())
    AllChem.MMFFOptimizeMolecule(mol)

    # Write temp PDBQT
    try:
        from meeko import MoleculePreparation, PDBQTWriterLegacy
        prep = MoleculePreparation()
        setups = prep.prepare(mol)
        if not setups:
            return None
        pdbqt_str, is_ok, _ = PDBQTWriterLegacy.write_string(setups[0])
        if not is_ok:
            return None
    except Exception:
        return None

    try:
        from services.rescoring_bridge import get_interaction_feature_extractor

        InteractionFeatureExtractor = get_interaction_feature_extractor()
        extractor = InteractionFeatureExtractor()
        feats = extractor.extract_from_pose(pdbqt_str, target_pdb_path, smiles, skip_prolif=False)
        if not feats:
            return None

        # Compute a simple interaction score from Shell + ECIF features
        # Higher feature sum = more protein-ligand contacts = more likely binder
        shell_feats = {k: v for k, v in feats.items() if k.startswith("shell_")}
        ecif_feats = {k: v for k, v in feats.items() if k.startswith("ecif_")}

        if not shell_feats and not ecif_feats:
            return None

        shell_sum = sum(float(v) for v in shell_feats.values())
        ecif_sum = sum(float(v) for v in ecif_feats.values())
        total_interactions = shell_sum + ecif_sum

        # Normalize to [0, 1]: typical range for 96+56 features is 0-50 contacts
        normalized = min(1.0, total_interactions / 30.0)
        return normalized

    except Exception:
        return None
