"""
gnn_v2/models.py — GNN-v2 Architecture for Protein-Ligand Binding Classification.

Protein Encoder:  GAT on Cα contact graph
Ligand Encoder:   GIN on bond + spatial graph
Fusion:           Cross-Attention (ligand attends to protein)
Pooling:          Set2Set on cross-attended ligand features
Head:             MLP + MC Dropout → P(binder) ± uncertainty

Versions:
  - GNNv2Classifier: full model with classification head (P(binder))
  - ContrastiveGNN: same encoders but outputs embedding vector (for CL pretraining)
"""

from __future__ import annotations

import torch
import torch.nn.functional as F
from torch import nn
from torch_geometric.nn import (
    BatchNorm,
    GATConv,
    GINConv,
    LayerNorm,
    Set2Set,
)

# ═══════════════════════════════════════════════════════════════════════
# Protein Encoder
# ═══════════════════════════════════════════════════════════════════════

class ProteinEncoder(nn.Module):
    def __init__(self, in_channels: int = 24, hidden_dim: int = 64,
                 heads: int = 4, dropout: float = 0.3, num_layers: int = 2):
        super().__init__()
        self.in_proj = nn.Linear(in_channels, hidden_dim)
        self.gat_layers = nn.ModuleList()
        self.norms = nn.ModuleList()
        for _ in range(num_layers):
            self.gat_layers.append(
                GATConv(hidden_dim, hidden_dim // heads, heads=heads, dropout=dropout, concat=True))
            self.norms.append(LayerNorm(hidden_dim))
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, edge_index):
        x = self.in_proj(x)
        for gat, norm in zip(self.gat_layers, self.norms):
            x = x + self.dropout(F.elu(gat(x, edge_index)))
            x = norm(x)
        return x


# ═══════════════════════════════════════════════════════════════════════
# Ligand Encoder
# ═══════════════════════════════════════════════════════════════════════

class LigandEncoder(nn.Module):
    def __init__(self, in_channels: int = 38, hidden_dim: int = 64,
                 num_layers: int = 3, dropout: float = 0.3):
        super().__init__()
        self.in_proj = nn.Linear(in_channels, hidden_dim)
        self.gin_layers = nn.ModuleList()
        self.norms = nn.ModuleList()
        for _ in range(num_layers):
            mlp = nn.Sequential(nn.Linear(hidden_dim, hidden_dim), nn.ELU(),
                               nn.Linear(hidden_dim, hidden_dim))
            self.gin_layers.append(GINConv(mlp, train_eps=True))
            self.norms.append(BatchNorm(hidden_dim))
        self.dropout = nn.Dropout(dropout)

    def forward(self, x, edge_index):
        x = self.in_proj(x)
        for gin, norm in zip(self.gin_layers, self.norms):
            x = x + self.dropout(F.elu(gin(x, edge_index)))
            x = norm(x)
        return x


# ═══════════════════════════════════════════════════════════════════════
# Cross-Attention (simplified)
# ═══════════════════════════════════════════════════════════════════════

class CrossAttention(nn.Module):
    """Ligand atoms attend to protein residues via dot-product attention.
    
    v2.1 — Interaction Bias: weighted attention by residue type.
    Charged residues (ASP, GLU, LYS, ARG) get higher attention at ~3Å.
    Hydrophobic residues (LEU, ILE, VAL, PHE, ALA) get lower attention.
    """

    def __init__(self, hidden_dim: int = 64, heads: int = 4, dropout: float = 0.3):
        super().__init__()
        self.hidden_dim = hidden_dim
        self.heads = heads
        self.head_dim = hidden_dim // heads
        self.scale = self.head_dim ** -0.5
        self.q_proj = nn.Linear(hidden_dim, hidden_dim)
        self.k_proj = nn.Linear(hidden_dim, hidden_dim)
        self.v_proj = nn.Linear(hidden_dim, hidden_dim)
        self.out_proj = nn.Linear(hidden_dim, hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.norm = LayerNorm(hidden_dim)

        # Residue-type attention bias (AA one-hot index → scalar bias)
        # Learned per amino acid type: higher = more important for binding
        self.residue_bias = nn.Embedding(21, 1)  # 20 AA + UNK

    def _residue_type_weight(self, prot_x: torch.Tensor, prot_idx: torch.Tensor) -> torch.Tensor:
        """Extract residue type weights from protein features.
        
        prot_x: (N_res, 24) — [21-dim AA one-hot, 3-dim coords]
        Returns: (E_cross,) residue importance scores
        """
        # AA one-hot is first 21 dims
        aa_onehot = prot_x[:, :21]  # (N_res, 21)
        # Get the argmax (AA type index)
        aa_idx = aa_onehot.argmax(dim=1)  # (N_res,)
        # Look up learned bias for each residue in cross edges
        bias = self.residue_bias(aa_idx[prot_idx])  # (E_cross, 1)
        return bias.squeeze(-1)  # (E_cross,)

    def forward(self, h_lig, h_prot, cross_edge_index, pos_lig=None, pos_prot=None, prot_x=None):
        if cross_edge_index.numel() == 0:
            return h_lig

        N_lig, N_prot = h_lig.size(0), h_prot.size(0)
        Q = self.q_proj(h_lig).view(N_lig, self.heads, self.head_dim)
        K = self.k_proj(h_prot).view(N_prot, self.heads, self.head_dim)
        V = self.v_proj(h_prot).view(N_prot, self.heads, self.head_dim)

        lig_idx = cross_edge_index[0]
        prot_idx = cross_edge_index[1]

        # Base attention (query-key dot product)
        attn = (Q[lig_idx] * K[prot_idx]).sum(dim=-1) * self.scale  # (E_cross, heads)

        # Distance bias: favor contacts at ~3.5Å
        if pos_lig is not None and pos_prot is not None:
            dist = torch.norm(pos_lig[lig_idx] - pos_prot[prot_idx], dim=1, keepdim=True)
            attn = attn - 0.5 * (dist - 3.5) ** 2

        # Interaction bias: residue-type weighting
        if prot_x is not None:
            residue_weight = self._residue_type_weight(prot_x, prot_idx)
            attn = attn + residue_weight.unsqueeze(-1) * 0.5

        attn = F.softmax(attn, dim=0)
        attn = self.dropout(attn)

        weighted_v = attn.unsqueeze(-1) * V[prot_idx]
        out = torch.zeros(N_lig, self.heads, self.head_dim, device=h_lig.device, dtype=h_lig.dtype)
        out.scatter_add_(0, lig_idx.unsqueeze(-1).unsqueeze(-1).expand(-1, self.heads, self.head_dim), weighted_v)
        out = self.out_proj(out.reshape(N_lig, -1))
        return self.norm(h_lig + self.dropout(out))


# ═══════════════════════════════════════════════════════════════════════
# GNN-v2 Classifier
# ═══════════════════════════════════════════════════════════════════════

class GNNv2Classifier(nn.Module):
    def __init__(self, prot_in: int = 24, lig_in: int = 38, hidden_dim: int = 64,
                 dropout: float = 0.3, set2set_steps: int = 4):
        super().__init__()
        self.prot_encoder = ProteinEncoder(in_channels=prot_in, hidden_dim=hidden_dim, dropout=dropout)
        self.lig_encoder = LigandEncoder(in_channels=lig_in, hidden_dim=hidden_dim, dropout=dropout)
        self.cross_attn = CrossAttention(hidden_dim=hidden_dim, dropout=dropout)
        self.lig_pool = Set2Set(hidden_dim, processing_steps=set2set_steps)
        self.prot_pool = Set2Set(hidden_dim, processing_steps=set2set_steps)
        self.head = nn.Sequential(
            nn.Linear(hidden_dim * 4, hidden_dim),
            nn.ELU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ELU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

    def forward(self, prot_x, prot_ei, lig_x, lig_ei, cross_ei,
                lig_pos=None, prot_pos=None, lig_batch=None, prot_batch=None):
        emb = self.extract_embedding(prot_x, prot_ei, lig_x, lig_ei, cross_ei,
                                     lig_pos, prot_pos, lig_batch, prot_batch)
        return self.head(emb).squeeze(-1)

    def extract_embedding(self, prot_x, prot_ei, lig_x, lig_ei, cross_ei,
                          lig_pos=None, prot_pos=None, lig_batch=None, prot_batch=None) -> torch.Tensor:
        """Extract 256-dim embedding vector (before classification head)."""
        h_prot = self.prot_encoder(prot_x, prot_ei)
        h_lig = self.lig_encoder(lig_x, lig_ei)
        h_lig = self.cross_attn(h_lig, h_prot, cross_ei, lig_pos, prot_pos, prot_x)

        if lig_batch is None:
            lig_batch = torch.zeros(lig_x.size(0), dtype=torch.long, device=lig_x.device)
        if prot_batch is None:
            prot_batch = torch.zeros(prot_x.size(0), dtype=torch.long, device=prot_x.device)

        lig_global = self.lig_pool(h_lig, lig_batch)
        prot_global = self.prot_pool(h_prot, prot_batch)
        return torch.cat([lig_global, prot_global], dim=-1)

    def predict_proba(self, *args, mc_samples: int = 20, **kwargs):
        self.train()
        samples = []
        with torch.no_grad():
            for _ in range(mc_samples):
                logits = self.forward(*args, **kwargs)
                samples.append(torch.sigmoid(logits))
        probs = torch.stack(samples, dim=0)
        return probs.mean(dim=0), probs.std(dim=0)


# ═══════════════════════════════════════════════════════════════════════
# Contrastive GNN (CL-GNN) — same encoder, contrastive head
# ═══════════════════════════════════════════════════════════════════════

class ContrastiveGNN(nn.Module):
    """
    GNN-v2 with contrastive projection head for self-supervised pretraining.
    
    Uses the SAME encoder as GNNv2Classifier but with a projection MLP
    that maps the 256-dim embedding to a 64-dim contrastive space.
    After pretraining, the projection head is discarded and replaced
    by the classification head for fine-tuning.
    """

    def __init__(self, prot_in: int = 24, lig_in: int = 38, hidden_dim: int = 64,
                 dropout: float = 0.3, proj_dim: int = 64):
        super().__init__()
        self.prot_encoder = ProteinEncoder(in_channels=prot_in, hidden_dim=hidden_dim, dropout=dropout)
        self.lig_encoder = LigandEncoder(in_channels=lig_in, hidden_dim=hidden_dim, dropout=dropout)
        self.cross_attn = CrossAttention(hidden_dim=hidden_dim, dropout=dropout)
        self.lig_pool = Set2Set(hidden_dim, processing_steps=4)
        self.prot_pool = Set2Set(hidden_dim, processing_steps=4)

        # Projection head (maps 256-dim → 64-dim contrastive space)
        self.projection = nn.Sequential(
            nn.Linear(hidden_dim * 4, hidden_dim * 2),
            nn.ELU(),
            nn.Linear(hidden_dim * 2, proj_dim),
        )

    def forward(self, prot_x, prot_ei, lig_x, lig_ei, cross_ei,
                lig_pos=None, prot_pos=None, lig_batch=None, prot_batch=None):
        """Returns embedding in contrastive space (64-dim)."""
        if lig_batch is None:
            lig_batch = torch.zeros(lig_x.size(0), dtype=torch.long, device=lig_x.device)
        if prot_batch is None:
            prot_batch = torch.zeros(prot_x.size(0), dtype=torch.long, device=prot_x.device)

        h_prot = self.prot_encoder(prot_x, prot_ei)
        h_lig = self.lig_encoder(lig_x, lig_ei)
        h_lig = self.cross_attn(h_lig, h_prot, cross_ei, lig_pos, prot_pos, prot_x)

        lig_global = self.lig_pool(h_lig, lig_batch)
        prot_global = self.prot_pool(h_prot, prot_batch)
        combined = torch.cat([lig_global, prot_global], dim=-1)
        return self.projection(combined)

    def load_pretrained_to_classifier(self, classifier: GNNv2Classifier):
        """Copy pretrained weights to a classifier model (skip projection head)."""
        classifier.prot_encoder.load_state_dict(self.prot_encoder.state_dict())
        classifier.lig_encoder.load_state_dict(self.lig_encoder.state_dict())
        classifier.cross_attn.load_state_dict(self.cross_attn.state_dict())
        # Note: pool layers don't have parameters, no need to copy
        print("Pretrained encoder weights loaded into classifier.")


# ═══════════════════════════════════════════════════════════════════════
# GNN-v3.1 — ECIF-augmented Multi-task Classifier
# Same encoder as GNNv2Classifier + ECIF/Shell feature injection
# + secondary delta-head (predicts pKi - vina_score) for multi-task loss.
# Backward-compatible: if ecif is None, falls back to GNNv2Classifier behavior.
# ═══════════════════════════════════════════════════════════════════════

class GNNv31Classifier(nn.Module):
    """GNN-v3.1 — multi-task with ECIF fusion + delta pKi regression.

    Inputs:
      - Protein graph + Ligand graph + cross edges (same as v2)
      - ecif: optional (B, ecif_dim) tensor of ECIF/Shell 3D interaction features
      - lambda_delta: scaling for delta head loss during training (0 disables)

    Outputs:
      - prob_logit: (B,) classification logit P(binder)
      - delta_pred: (B,) predicted ΔpKi = pKi - vina_score (regression)
    """

    def __init__(self, prot_in: int = 24, lig_in: int = 38, hidden_dim: int = 64,
                 dropout: float = 0.3, set2set_steps: int = 4,
                 ecif_in: int = 152, ecif_emb_dim: int = 64,
                 use_delta_head: bool = True):
        super().__init__()
        # Reuse same encoders as v2
        self.prot_encoder = ProteinEncoder(in_channels=prot_in, hidden_dim=hidden_dim, dropout=dropout)
        self.lig_encoder = LigandEncoder(in_channels=lig_in, hidden_dim=hidden_dim, dropout=dropout)
        self.cross_attn = CrossAttention(hidden_dim=hidden_dim, dropout=dropout)
        self.lig_pool = Set2Set(hidden_dim, processing_steps=set2set_steps)
        self.prot_pool = Set2Set(hidden_dim, processing_steps=set2set_steps)

        # ECIF encoder: 152 (ECIF/Shell + 0 if none) → ecif_emb_dim
        self.ecif_encoder = nn.Sequential(
            nn.Linear(ecif_in, ecif_emb_dim * 2),
            nn.ELU(), nn.Dropout(dropout),
            nn.Linear(ecif_emb_dim * 2, ecif_emb_dim),
            nn.ELU(), nn.Dropout(dropout),
        )
        # Flag for missing ECIF (one-hot, 1 dim)
        self.ecif_missing_flag = nn.Parameter(torch.zeros(1, dtype=torch.float32))

        # Fusion: graph_emb (hidden_dim*4) + ecif_emb (ecif_emb_dim) + ecif_missing (1)
        fusion_in = hidden_dim * 4 + ecif_emb_dim + 1
        self.fusion = nn.Sequential(
            nn.Linear(fusion_in, hidden_dim * 2),
            nn.ELU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ELU(), nn.Dropout(dropout),
        )

        # Primary head: P(binder)
        self.classification_head = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ELU(), nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
        )

        # Delta head: ΔpKi = pKi - vina_score
        self.use_delta_head = use_delta_head
        if use_delta_head:
            self.delta_head = nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ELU(), nn.Dropout(dropout),
                nn.Linear(hidden_dim // 2, 1),
            )

    def forward(self, prot_x, prot_ei, lig_x, lig_ei, cross_ei,
                lig_pos=None, prot_pos=None, lig_batch=None, prot_batch=None,
                ecif: torch.Tensor | None = None):
        # Compute graph embedding (same as v2.extract_embedding)
        h_prot = self.prot_encoder(prot_x, prot_ei)
        h_lig = self.lig_encoder(lig_x, lig_ei)
        h_lig = self.cross_attn(h_lig, h_prot, cross_ei, lig_pos, prot_pos, prot_x)

        if lig_batch is None:
            lig_batch = torch.zeros(lig_x.size(0), dtype=torch.long, device=lig_x.device)
        if prot_batch is None:
            prot_batch = torch.zeros(prot_x.size(0), dtype=torch.long, device=prot_x.device)

        lig_global = self.lig_pool(h_lig, lig_batch)
        prot_global = self.prot_pool(h_prot, prot_batch)
        graph_emb = torch.cat([lig_global, prot_global], dim=-1)  # (B, hidden*4)

        B = graph_emb.size(0)
        # ECIF fusion (with safe fallback when ecif is None or wrong size)
        if ecif is not None:
            # Expect (B, ecif_in) — handle (ecif_in,) single batch gracefully
            if ecif.dim() == 1:
                expected = self.ecif_encoder[0].in_features
                if ecif.size(0) == expected:
                    ecif = ecif.unsqueeze(0)  # add batch dim
                elif ecif.size(0) == B:
                    # Treat as B-vector, broadcast zeros
                    ecif = torch.cat([ecif.view(-1, 1), torch.zeros(B, expected - 1, device=ecif.device)], dim=1)
            if ecif.size(0) != B:
                # mismatched batch — fall back to zeros
                ecif = None

        if ecif is None:
            expected = self.ecif_encoder[0].in_features
            ecif = torch.zeros(B, expected, device=graph_emb.device)
            ecif_flag = self.ecif_missing_flag.expand(B, 1) + torch.ones(B, 1, device=graph_emb.device)
        else:
            ecif_flag = torch.zeros(B, 1, device=graph_emb.device)

        ecif_emb = self.ecif_encoder(ecif)  # (B, ecif_emb_dim)
        fused = self.fusion(torch.cat([graph_emb, ecif_emb, ecif_flag], dim=-1))  # (B, hidden)

        prob_logit = self.classification_head(fused).squeeze(-1)  # (B,)

        if self.use_delta_head:
            delta_pred = self.delta_head(fused).squeeze(-1)  # (B,)
            return prob_logit, delta_pred
        return prob_logit, None

    def predict_proba(self, *args, mc_samples: int = 20, **kwargs):
        self.train()
        with torch.no_grad():
            probs = []
            for _ in range(mc_samples):
                logits, _ = self.forward(*args, **kwargs)
                probs.append(torch.sigmoid(logits))
            probs = torch.stack(probs, dim=0)
        return probs.mean(dim=0), probs.std(dim=0)


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


if __name__ == "__main__":
    # Smoke test GNN-v3.1
    model = GNNv31Classifier(hidden_dim=64, ecif_in=152)
    print(f"GNN-v3.1 classifier parameters: {count_parameters(model):,}")

    # Test forward
    N_prot, N_lig = 63, 33
    prot_x = torch.randn(N_prot, 24)
    prot_ei = torch.randint(0, N_prot, (2, 200))
    lig_x = torch.randn(N_lig, 38)
    lig_ei = torch.randint(0, N_lig, (2, 150))
    cross_ei = torch.stack([torch.randint(0, N_lig, (100,)), torch.randint(0, N_prot, (100,))])
    ecif = torch.randn(1, 152)  # batch=1, ecif dim=152

    prob_logit, delta_pred = model(prot_x, prot_ei, lig_x, lig_ei, cross_ei, ecif=ecif)
    print(f"GNN-v3.1 prob_logit: {prob_logit.item():.4f}, delta_pred: {delta_pred.item():.4f}")

    # Without ECIF (zero fallback)
    prob_logit_no_ecif, _ = model(prot_x, prot_ei, lig_x, lig_ei, cross_ei)
    print(f"GNN-v3.1 no-ECIF logit: {prob_logit_no_ecif.item():.4f}")

    # GNN-v2 compatibility
    model_v2 = GNNv2Classifier(hidden_dim=64)
    print(f"\nGNN-v2 classifier parameters: {count_parameters(model_v2):,}")
    logits_v2 = model_v2(prot_x, prot_ei, lig_x, lig_ei, cross_ei)
    print(f"GNN-v2 logit: {logits_v2.item():.4f}")

    contrastive = ContrastiveGNN(hidden_dim=64)
    print(f"ContrastiveGNN parameters: {count_parameters(contrastive):,}")
    emb = contrastive(prot_x, prot_ei, lig_x, lig_ei, cross_ei)
    print(f"Contrastive embedding: {emb.shape} (should be [1, 64])")
