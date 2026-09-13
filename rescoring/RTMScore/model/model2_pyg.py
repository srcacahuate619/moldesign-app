
import numpy as np
import torch as th
import torch.nn.functional as F
from torch import nn
from torch_geometric.utils import scatter, to_dense_batch
from torch_geometric.utils import softmax as pyg_softmax

# ── Init ────────────────────────────────────────────────────────────────

def glorot_orthogonal(tensor, scale):
    if tensor is not None:
        th.nn.init.orthogonal_(tensor.data)
        scale /= ((tensor.size(-2) + tensor.size(-1)) * tensor.var())
        tensor.data *= scale.sqrt()

# ── Multi-Head Attention (PyG) ──────────────────────────────────────────

class MultiHeadAttentionLayer(nn.Module):
    """Multi-head attention with geometric edge features for PyG graphs."""
    def __init__(self, num_input_feats, num_output_feats,
                 num_heads, using_bias=False, update_edge_feats=True):
        super().__init__()

        self.num_output_feats = num_output_feats
        self.num_heads = num_heads
        self.using_bias = using_bias
        self.update_edge_feats = update_edge_feats

        self.Q = nn.Linear(num_input_feats, self.num_output_feats * self.num_heads, bias=using_bias)
        self.K = nn.Linear(num_input_feats, self.num_output_feats * self.num_heads, bias=using_bias)
        self.V = nn.Linear(num_input_feats, self.num_output_feats * self.num_heads, bias=using_bias)
        self.edge_feats_projection = nn.Linear(num_input_feats, self.num_output_feats * self.num_heads, bias=using_bias)

        self.reset_parameters()

    def reset_parameters(self):
        scale = 2.0
        if self.using_bias:
            glorot_orthogonal(self.Q.weight, scale=scale); self.Q.bias.data.fill_(0)
            glorot_orthogonal(self.K.weight, scale=scale); self.K.bias.data.fill_(0)
            glorot_orthogonal(self.V.weight, scale=scale); self.V.bias.data.fill_(0)
            glorot_orthogonal(self.edge_feats_projection.weight, scale=scale); self.edge_feats_projection.bias.data.fill_(0)
        else:
            glorot_orthogonal(self.Q.weight, scale=scale)
            glorot_orthogonal(self.K.weight, scale=scale)
            glorot_orthogonal(self.V.weight, scale=scale)
            glorot_orthogonal(self.edge_feats_projection.weight, scale=scale)

    def forward(self, node_feats, edge_feats, edge_index):
        """PyG-style attention: node_feats [N,H], edge_feats [E,H], edge_index [2,E]"""
        N = node_feats.size(0)
        src, dst = edge_index[0], edge_index[1]

        # Linear projections
        Q_h = self.Q(node_feats).view(N, self.num_heads, self.num_output_feats)  # [N, heads, D]
        K_h = self.K(node_feats).view(N, self.num_heads, self.num_output_feats)
        V_h = self.V(node_feats).view(N, self.num_heads, self.num_output_feats)
        E_proj = self.edge_feats_projection(edge_feats).view(-1, self.num_heads, self.num_output_feats)  # [E, heads, D]

        # Compute attention scores as in DGL: (K_src * Q_dst) [E,heads,D]
        K_src = K_h[src]  # [E, heads, D]
        Q_dst = Q_h[dst]  # [E, heads, D]
        scores = (Q_dst * K_src) / np.sqrt(self.num_output_feats)  # [E, heads, D]
        scores = scores.clamp(-5.0, 5.0)
        scores = scores * E_proj  # [E, heads, D]

        # e_out keeps the full [E, heads, D] shape (matches DGL behavior)
        e_out = scores.clone() if self.update_edge_feats else None

        # Sum over feature dim for softmax: [E, heads, D] -> [E, heads]
        scores_summed = scores.sum(dim=-1).clamp(-5.0, 5.0)
        attn = pyg_softmax(th.exp(scores_summed), dst)  # [E, heads]

        # Weighted sum of values to destination nodes
        V_src = V_h[src]  # [E, heads, D]
        weighted = attn.unsqueeze(-1) * V_src  # [E, heads, D]

        # Aggregate: sum to destination nodes
        wV = scatter(weighted, dst, dim=0, reduce="sum")  # [N, heads, D]
        z = scatter(attn, dst, dim=0, reduce="sum").unsqueeze(-1) + 1e-6  # [N, heads, 1]
        h_out = wV / z  # [N, heads, D]

        return h_out, e_out

# ── Graph Transformer Module (PyG) ──────────────────────────────────────

class GraphTransformerModule(nn.Module):
    """A Graph Transformer module (1 layer of graph convolutions)."""
    def __init__(self, num_hidden_channels, activ_fn=nn.SiLU(), residual=True,
                 num_attention_heads=4, norm_to_apply='batch', dropout_rate=0.1, num_layers=4):
        super().__init__()

        self.activ_fn = activ_fn
        self.residual = residual
        self.num_attention_heads = num_attention_heads
        self.norm_to_apply = norm_to_apply
        self.dropout_rate = dropout_rate
        self.num_layers = num_layers

        self.apply_layer_norm = 'layer' in self.norm_to_apply.lower()
        self.num_hidden_channels = num_hidden_channels
        self.num_output_feats = num_hidden_channels

        if self.apply_layer_norm:
            self.layer_norm1_node_feats = nn.LayerNorm(self.num_output_feats)
            self.layer_norm1_edge_feats = nn.LayerNorm(self.num_output_feats)
        else:
            self.batch_norm1_node_feats = nn.BatchNorm1d(self.num_output_feats)
            self.batch_norm1_edge_feats = nn.BatchNorm1d(self.num_output_feats)

        self.mha_module = MultiHeadAttentionLayer(
            self.num_hidden_channels,
            self.num_output_feats // self.num_attention_heads,
            self.num_attention_heads,
            self.num_hidden_channels != self.num_output_feats,
            update_edge_feats=True
        )

        self.O_node_feats = nn.Linear(self.num_output_feats, self.num_output_feats)
        self.O_edge_feats = nn.Linear(self.num_output_feats, self.num_output_feats)

        dropout = nn.Dropout(p=self.dropout_rate) if self.dropout_rate > 0.0 else nn.Identity()
        self.node_feats_MLP = nn.ModuleList([
            nn.Linear(self.num_output_feats, self.num_output_feats * 2, bias=False),
            self.activ_fn,
            dropout,
            nn.Linear(self.num_output_feats * 2, self.num_output_feats, bias=False)
        ])

        if self.apply_layer_norm:
            self.layer_norm2_node_feats = nn.LayerNorm(self.num_output_feats)
            self.layer_norm2_edge_feats = nn.LayerNorm(self.num_output_feats)
        else:
            self.batch_norm2_node_feats = nn.BatchNorm1d(self.num_output_feats)
            self.batch_norm2_edge_feats = nn.BatchNorm1d(self.num_output_feats)

        self.edge_feats_MLP = nn.ModuleList([
            nn.Linear(self.num_output_feats, self.num_output_feats * 2, bias=False),
            self.activ_fn,
            dropout,
            nn.Linear(self.num_output_feats * 2, self.num_output_feats, bias=False)
        ])

        self.reset_parameters()

    def reset_parameters(self):
        scale = 2.0
        glorot_orthogonal(self.O_node_feats.weight, scale=scale); self.O_node_feats.bias.data.fill_(0)
        glorot_orthogonal(self.O_edge_feats.weight, scale=scale); self.O_edge_feats.bias.data.fill_(0)
        for layer in self.node_feats_MLP:
            if hasattr(layer, 'weight'): glorot_orthogonal(layer.weight, scale=scale)
        for layer in self.edge_feats_MLP:
            if hasattr(layer, 'weight'): glorot_orthogonal(layer.weight, scale=scale)

    def run_gt_layer(self, node_feats, edge_feats, edge_index):
        """Forward pass of graph attention using multi-head attention."""
        node_feats_in1 = node_feats
        edge_feats_in1 = edge_feats

        # First normalization
        if self.apply_layer_norm:
            node_feats = self.layer_norm1_node_feats(node_feats)
            edge_feats = self.layer_norm1_edge_feats(edge_feats)
        else:
            node_feats = self.batch_norm1_node_feats(node_feats)
            edge_feats = self.batch_norm1_edge_feats(edge_feats)

        # Multi-head attention
        node_attn_out, edge_attn_out = self.mha_module(node_feats, edge_feats, edge_index)
        node_feats = node_attn_out.view(-1, self.num_output_feats)
        edge_feats = edge_attn_out.view(-1, self.num_output_feats)

        node_feats = F.dropout(node_feats, self.dropout_rate, training=self.training)
        edge_feats = F.dropout(edge_feats, self.dropout_rate, training=self.training)
        node_feats = self.O_node_feats(node_feats)
        edge_feats = self.O_edge_feats(edge_feats)

        # First residual
        if self.residual:
            node_feats = node_feats_in1 + node_feats
            edge_feats = edge_feats_in1 + edge_feats

        node_feats_in2 = node_feats
        edge_feats_in2 = edge_feats

        # Second normalization
        if self.apply_layer_norm:
            node_feats = self.layer_norm2_node_feats(node_feats)
            edge_feats = self.layer_norm2_edge_feats(edge_feats)
        else:
            node_feats = self.batch_norm2_node_feats(node_feats)
            edge_feats = self.batch_norm2_edge_feats(edge_feats)

        # MLPs
        for layer in self.node_feats_MLP:
            node_feats = layer(node_feats)
        for layer in self.edge_feats_MLP:
            edge_feats = layer(edge_feats)

        # Second residual
        if self.residual:
            node_feats = node_feats_in2 + node_feats
            edge_feats = edge_feats_in2 + edge_feats

        return node_feats, edge_feats

    def forward(self, node_feats, edge_feats, edge_index):
        return self.run_gt_layer(node_feats, edge_feats, edge_index)

# ── Final Graph Transformer Module (PyG) ────────────────────────────────

class FinalGraphTransformerModule(nn.Module):
    """Final layer Graph Transformer that combines node and edge representations."""
    def __init__(self, num_hidden_channels, activ_fn=nn.SiLU(), residual=True,
                 num_attention_heads=4, norm_to_apply='batch', dropout_rate=0.1, num_layers=4):
        super().__init__()

        self.activ_fn = activ_fn
        self.residual = residual
        self.num_attention_heads = num_attention_heads
        self.norm_to_apply = norm_to_apply
        self.dropout_rate = dropout_rate
        self.num_layers = num_layers
        self.apply_layer_norm = 'layer' in self.norm_to_apply.lower()
        self.num_hidden_channels = num_hidden_channels
        self.num_output_feats = num_hidden_channels

        if self.apply_layer_norm:
            self.layer_norm1_node_feats = nn.LayerNorm(self.num_output_feats)
            self.layer_norm1_edge_feats = nn.LayerNorm(self.num_output_feats)
        else:
            self.batch_norm1_node_feats = nn.BatchNorm1d(self.num_output_feats)
            self.batch_norm1_edge_feats = nn.BatchNorm1d(self.num_output_feats)

        self.mha_module = MultiHeadAttentionLayer(
            self.num_hidden_channels,
            self.num_output_feats // self.num_attention_heads,
            self.num_attention_heads,
            self.num_hidden_channels != self.num_output_feats,
            update_edge_feats=False
        )

        self.O_node_feats = nn.Linear(self.num_output_feats, self.num_output_feats)

        dropout = nn.Dropout(p=self.dropout_rate) if self.dropout_rate > 0.0 else nn.Identity()
        self.node_feats_MLP = nn.ModuleList([
            nn.Linear(self.num_output_feats, self.num_output_feats * 2, bias=False),
            self.activ_fn,
            dropout,
            nn.Linear(self.num_output_feats * 2, self.num_output_feats, bias=False)
        ])

        if self.apply_layer_norm:
            self.layer_norm2_node_feats = nn.LayerNorm(self.num_output_feats)
        else:
            self.batch_norm2_node_feats = nn.BatchNorm1d(self.num_output_feats)

        self.reset_parameters()

    def reset_parameters(self):
        scale = 2.0
        glorot_orthogonal(self.O_node_feats.weight, scale=scale); self.O_node_feats.bias.data.fill_(0)
        for layer in self.node_feats_MLP:
            if hasattr(layer, 'weight'): glorot_orthogonal(layer.weight, scale=scale)

    def run_gt_layer(self, node_feats, edge_feats, edge_index):
        node_feats_in1 = node_feats

        if self.apply_layer_norm:
            node_feats = self.layer_norm1_node_feats(node_feats)
            edge_feats = self.layer_norm1_edge_feats(edge_feats)
        else:
            node_feats = self.batch_norm1_node_feats(node_feats)
            edge_feats = self.batch_norm1_edge_feats(edge_feats)

        node_attn_out, _ = self.mha_module(node_feats, edge_feats, edge_index)
        node_feats = node_attn_out.view(-1, self.num_output_feats)
        node_feats = F.dropout(node_feats, self.dropout_rate, training=self.training)
        node_feats = self.O_node_feats(node_feats)

        if self.residual:
            node_feats = node_feats_in1 + node_feats

        node_feats_in2 = node_feats

        if self.apply_layer_norm:
            node_feats = self.layer_norm2_node_feats(node_feats)
        else:
            node_feats = self.batch_norm2_node_feats(node_feats)

        for layer in self.node_feats_MLP:
            node_feats = layer(node_feats)

        if self.residual:
            node_feats = node_feats_in2 + node_feats

        return node_feats

    def forward(self, node_feats, edge_feats, edge_index):
        return self.run_gt_layer(node_feats, edge_feats, edge_index)

# ── DGLGraphTransformer (PyG equivalent) ────────────────────────────────

class DGLGraphTransformer(nn.Module):
    """Graph Transformer — PyG version, identical state_dict compatibility with DGL."""
    def __init__(self, in_channels, edge_features=10, num_hidden_channels=128,
                 activ_fn=nn.SiLU(), transformer_residual=True, num_attention_heads=4,
                 norm_to_apply='batch', dropout_rate=0.1, num_layers=4, **kwargs):
        super().__init__()

        self.activ_fn = activ_fn
        self.transformer_residual = transformer_residual
        self.num_attention_heads = num_attention_heads
        self.norm_to_apply = norm_to_apply
        self.dropout_rate = dropout_rate
        self.num_layers = num_layers

        self.node_encoder = nn.Linear(in_channels, num_hidden_channels)
        self.edge_encoder = nn.Linear(edge_features, num_hidden_channels)

        num_intermediate_layers = max(0, num_layers - 1)
        gt_block_modules = [GraphTransformerModule(
            num_hidden_channels=num_hidden_channels, activ_fn=activ_fn,
            residual=transformer_residual, num_attention_heads=num_attention_heads,
            norm_to_apply=norm_to_apply, dropout_rate=dropout_rate,
            num_layers=num_layers) for _ in range(num_intermediate_layers)]
        if num_layers > 0:
            gt_block_modules.extend([FinalGraphTransformerModule(
                num_hidden_channels=num_hidden_channels, activ_fn=activ_fn,
                residual=transformer_residual, num_attention_heads=num_attention_heads,
                norm_to_apply=norm_to_apply, dropout_rate=dropout_rate,
                num_layers=num_layers)])
        self.gt_block = nn.ModuleList(gt_block_modules)

    def forward(self, data):
        """data: PyG Data with x=node_feats, edge_attr=edge_feats, edge_index"""
        node_feats = self.node_encoder(data.x.float())
        edge_feats = self.edge_encoder(data.edge_attr.float())
        edge_index = data.edge_index

        for gt_layer in self.gt_block[:-1]:
            node_feats, edge_feats = gt_layer(node_feats, edge_feats, edge_index)
        node_feats = self.gt_block[-1](node_feats, edge_feats, edge_index)
        return node_feats

# ── RTMScore (PyG) ──────────────────────────────────────────────────────

class RTMScore(nn.Module):
    def __init__(self, lig_model, prot_model, in_channels, hidden_dim, n_gaussians,
                 dropout_rate=0.15, dist_threhold=1000):
        super().__init__()

        self.lig_model = lig_model
        self.prot_model = prot_model
        self.MLP = nn.Sequential(
            nn.Linear(in_channels*2, hidden_dim),
            nn.BatchNorm1d(hidden_dim),
            nn.ELU(),
            nn.Dropout(p=dropout_rate)
        )
        self.z_pi = nn.Linear(hidden_dim, n_gaussians)
        self.z_sigma = nn.Linear(hidden_dim, n_gaussians)
        self.z_mu = nn.Linear(hidden_dim, n_gaussians)
        self.atom_types = nn.Linear(in_channels, 17)
        self.bond_types = nn.Linear(in_channels*2, 4)

        self.dist_threhold = dist_threhold

    def forward(self, prot_data, lig_data):
        """
        prot_data: PyG Data for protein graph (x, edge_attr, edge_index, pos, batch)
        lig_data:  PyG Data for ligand graph (x, edge_attr, edge_index, pos, batch)
        """
        # Run transformers
        h_l = self.lig_model(lig_data)   # [N_l, hidden]
        h_p = self.prot_model(prot_data)  # [N_p, hidden]

        # Get batch info
        lig_batch = lig_data.batch
        prot_batch = prot_data.batch

        # To dense batch
        h_l_x, l_mask = to_dense_batch(h_l, lig_batch)    # [B, N_l_max, hidden]
        h_p_x, p_mask = to_dense_batch(h_p, prot_batch)    # [B, N_p_max, hidden]

        h_l_pos, _ = to_dense_batch(lig_data.pos.float(), lig_batch)   # [B, N_l_max, 3]
        h_p_pos, _ = to_dense_batch(prot_data.pos.float(), prot_batch) # [B, N_p_max, max_atoms, 3]

        B, N_l, C_out = h_l_x.size()
        N_p = h_p_x.size(1)
        self.B = B
        self.N_l = N_l
        self.N_p = N_p
        self.max_prot_atoms = h_p_pos.shape[-2] if len(h_p_pos.shape) >= 3 else 24

        # Combine ligand and protein features
        h_l_x = h_l_x.unsqueeze(-2).repeat(1, 1, N_p, 1)  # [B, N_l, N_p, C_out]
        h_p_x = h_p_x.unsqueeze(-3).repeat(1, N_l, 1, 1)  # [B, N_l, N_p, C_out]
        C = th.cat((h_l_x, h_p_x), -1)  # [B, N_l, N_p, 2*C_out]

        C_mask = l_mask.view(B, N_l, 1) & p_mask.view(B, 1, N_p)
        C = C[C_mask]  # [total_pairs, 2*C_out]

        C = self.MLP(C)

        # Batch indices
        C_batch = th.tensor(range(B), device=C.device).unsqueeze(-1).unsqueeze(-1).repeat(1, N_l, N_p)[C_mask]

        # Outputs
        pi = F.softmax(self.z_pi(C), -1)
        sigma = F.elu(self.z_sigma(C)) + 1.1
        mu = F.elu(self.z_mu(C)) + 1
        atom_types = self.atom_types(h_l)
        bond_types = self.bond_types(th.cat([h_l[lig_data.edge_index[0]], h_l[lig_data.edge_index[1]]], dim=-1))

        # Distance matrix
        dist = self._compute_distances(h_l_pos, h_p_pos)[C_mask]
        return pi, sigma, mu, dist.unsqueeze(1).detach(), atom_types, bond_types, C_batch

    def _compute_distances(self, X, Y):
        """X: [B, N_l, 3], Y: [B, N_p, max_atoms, 3] → [B, N_l, N_p]"""
        max_atoms = getattr(self, 'max_prot_atoms', 24)
        X = X.double()
        Y = Y.double()

        # Flatten protein atom positions: [B, N_p * max_atoms, 3]
        Y_flat = Y.view(self.B, -1, 3)
        dists = -2 * th.bmm(X, Y_flat.permute(0, 2, 1)) + th.sum(Y_flat**2, dim=-1).unsqueeze(1) + th.sum(X**2, dim=-1).unsqueeze(-1)
        return th.nan_to_num((dists**0.5).view(self.B, self.N_l, -1, max_atoms), 10000).min(dim=-1)[0]
