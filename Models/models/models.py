"""
models.py
─────────
All 9 models (A → I) with:
  - Architecture definition
  - Training configuration (what data, what label, special tricks)
  - Pre-train / fine-tune splits where applicable
  - Forward pass contract (what goes in, what comes out)

Import order matters: A and B produce embeddings that C,D,E consume.
E produces embeddings that F,G consume. H stacks all. I calibrates.
"""

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path


# ═══════════════════════════════════════════════════════════════════════════
# MODEL A — Tabular Encoder  (TabNet)
# ═══════════════════════════════════════════════════════════════════════════
"""
WHAT IT IS:
  TabNet with self-supervised pre-training then supervised fine-tuning.
  Produces a 128-dim transaction embedding + fraud logit.

TRAIN DATA:
  IEEE-CIS merged DataFrame (train split, 80%).
  Features: V1-V339 (with missingness flags) + C1-C14 + D1-D15 + M1-M9
            + TransactionAmt + card1-6 (label-encoded) + amt_zscore
            + delta_t_norm + device_match_ord + device_novelty
  Label: isFraud

SPECIAL:
  Phase 1 — self-supervised TabNet pre-training:
    Mask random feature subsets and reconstruct them.
    No labels needed. Run on FULL dataset (train + test).
    Epochs: 50, mask_ratio=0.3
  Phase 2 — supervised fine-tuning:
    Unfreeze all layers. Train with binary focal loss (gamma=2).
    Class weight: n_neg/n_pos (heavily imbalanced ~3.5% fraud).
    Epochs: 30 with early stopping on val AUC.

OUTPUT:
  embedding [B, 128]   → fed into Model E as transaction node init features
  logit     [B]        → raw fraud score (becomes one of H's inputs)
"""

class TabNetEncoder(nn.Module):
    """
    Simplified TabNet: sequential attention + feature selection.
    Full TabNet requires pytorch-tabnet library. This is a
    faithful lite implementation for embedding extraction.

    For production: use pytorch-tabnet package which has the
    full sequential multi-step attention mechanism.
    """
    def __init__(
        self,
        in_dim:     int,
        embed_dim:  int   = 128,
        n_steps:    int   = 5,
        n_shared:   int   = 2,
        dropout:    float = 0.1,
    ):
        super().__init__()
        self.n_steps   = n_steps
        self.embed_dim = embed_dim

        # Batch normalisation on raw features (key TabNet ingredient)
        self.bn_input = nn.BatchNorm1d(in_dim)

        # Shared step layers (across all steps)
        shared = []
        for i in range(n_shared):
            shared += [
                # FIX: Change `embed_dim * 2` to `embed_dim` for subsequent layers
                nn.Linear(in_dim if i == 0 else embed_dim, embed_dim * 2),
                nn.BatchNorm1d(embed_dim * 2),
            ]
        self.shared = nn.ModuleList(shared)

        # Per-step attention + transform
        self.step_attns   = nn.ModuleList([
            nn.Linear(embed_dim, in_dim) for _ in range(n_steps)
        ])
        self.step_bns     = nn.ModuleList([
            nn.BatchNorm1d(in_dim) for _ in range(n_steps)
        ])
        self.step_transforms = nn.ModuleList([
            nn.Sequential(
                nn.Linear(in_dim, embed_dim * 2),
                nn.BatchNorm1d(embed_dim * 2),
            ) for _ in range(n_steps)
        ])

        self.to_embed   = nn.Linear(embed_dim * n_steps, embed_dim)
        self.classifier = nn.Linear(embed_dim, 1)
        self.dropout    = nn.Dropout(dropout)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        x = self.bn_input(x)
        h = torch.zeros(x.shape[0], self.embed_dim, device=x.device)
        step_outputs = []
        prior_scales = torch.ones_like(x)

        for step in range(self.n_steps):
            # Attention mask over input features
            attn = F.softmax(
                self.step_bns[step](self.step_attns[step](h)) * prior_scales,
                dim=-1
            )
            prior_scales = prior_scales * (1 - attn)

            # Masked features through shared layers
            masked = x * attn
            feat = masked
            
            for i in range(0, len(self.shared), 2):
                # FIX: Apply Linear -> BatchNorm -> GLU
                z = self.shared[i](feat)           # Linear layer
                z = self.shared[i+1](z)            # BatchNorm layer (previously unused!)
                feat = F.glu(z, dim=-1)            # GLU (cuts 256 down to 128)

            # Step-specific transform
            feat = F.glu(self.step_transforms[step](masked), dim=-1)
            feat = self.dropout(feat)

            h = feat
            step_outputs.append(feat)

        # Aggregate all steps
        agg = torch.stack(step_outputs, dim=1)            # [B, n_steps, embed_dim]
        agg = agg.view(agg.shape[0], -1)                  # [B, n_steps * embed_dim]
        return F.relu(self.to_embed(agg))                  # [B, embed_dim]

    def forward(self, x):
        emb    = self.encode(x)
        logit  = self.classifier(emb).squeeze(-1)
        return {"embedding": emb, "logit": logit}


TABNET_TRAIN_CONFIG = {
    "phase": "pretrain",
    "data":  "ieee_cis_merged (all rows, no label needed)",
    "label": None,
    "loss":  "reconstruction MSE on masked features",
    "epochs": 50,
    "mask_ratio": 0.3,
    "optimizer": "Adam lr=2e-3",
    "notes": "Mask 30% of features randomly. Reconstruct. No labels.",
}
TABNET_FINETUNE_CONFIG = {
    "phase": "finetune",
    "data":  "ieee_cis_merged (train split 80%)",
    "label": "isFraud",
    "loss":  "Focal loss gamma=2, class_weight=n_neg/n_pos",
    "epochs": 30,
    "early_stop": "val AUC, patience=5",
    "optimizer": "Adam lr=5e-4 with cosine decay",
    "output": "embedding[128] + logit[1]",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL B — Device Siamese Encoder
# ═══════════════════════════════════════════════════════════════════════════
"""
WHAT IT IS:
  Siamese network with contrastive loss.
  Maps a device fingerprint tuple → 64-dim embedding.
  At inference: compute L2 distance between current device
  and user's known device cluster centroid.

TRAIN DATA:
  siamese_pairs.parquet (generated by graft_amiunique.py)
  100k pairs: positive (same user, same device), hard negative
  (same user, different device), easy negative (different users).

SPECIAL:
  Use TRIPLET LOSS (not contrastive) because you have hard negatives:
    anchor   = current transaction's device
    positive = known device from same user's history
    negative = different device (hard: from same user; easy: random)
  margin=0.5, distance=euclidean in L2-normalised space.

  Hard negatives drive the model to distinguish "new device for same user"
  (ATO signal) from "usual variation in fingerprint" (false positive).

OUTPUT:
  embedding [B, 64]    → fed into Model E as device node init features
  dist_score [B]       → distance from user's known device centroid
                          (becomes one of H's inputs)
"""

class DeviceFingerEncoder(nn.Module):
    """
    Encodes a device fingerprint (categorical + continuous features)
    into a 64-dim L2-normalised embedding.
    """
    def __init__(
        self,
        n_categorical_features: int = 5,   # id_31, id_33, DeviceType, etc.
        cat_embed_dim: int = 16,
        n_continuous: int = 2,             # device_match_ord, device_novelty
        embed_dim: int = 64,
        dropout: float = 0.1,
    ):
        super().__init__()
        # Each categorical gets its own embedding (sizes vary in practice;
        # use vocab_size determined from dataset)
        self.cat_embeds = nn.ModuleList([
            nn.Embedding(500, cat_embed_dim) for _ in range(n_categorical_features)
        ])

        in_dim = n_categorical_features * cat_embed_dim + n_continuous
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, embed_dim),
            nn.LayerNorm(embed_dim),
        )

    def forward(self, cat_feats: torch.Tensor, cont_feats: torch.Tensor) -> torch.Tensor:
        """
        cat_feats : [B, n_cat] integer indices
        cont_feats: [B, n_cont] float features
        Returns   : [B, 64] L2-normalised embedding
        """
        cat_embs = [emb(cat_feats[:, i]) for i, emb in enumerate(self.cat_embeds)]
        x = torch.cat(cat_embs + [cont_feats], dim=-1)
        return F.normalize(self.encoder(x), dim=-1)


def triplet_loss(anchor, positive, negative, margin=0.5):
    d_pos = F.pairwise_distance(anchor, positive)
    d_neg = F.pairwise_distance(anchor, negative)
    return F.relu(d_pos - d_neg + margin).mean()


SIAMESE_TRAIN_CONFIG = {
    "data":  "siamese_pairs.parquet",
    "label": "pair label (0/1) + is_hard_negative flag",
    "loss":  "Triplet loss, margin=0.5, hard negative mining",
    "epochs": 40,
    "batch_size": 512,
    "optimizer": "AdamW lr=1e-3",
    "notes": "Hard negatives (same user, different device) sampled at 2x rate."
             " After training, compute per-user device centroid in embedding space."
             " At inference: distance from centroid = device_dist_score.",
    "output": "embedding[64] + dist_score[1]",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL C — Sequence Transformer  (defined in graft_paysim.py)
# ═══════════════════════════════════════════════════════════════════════════
"""
Architecture: BehavioralSequenceTransformer (see graft_paysim.py)
  d_model=128, n_heads=4, n_layers=3, output_dim=64

TRAIN — Phase 1 (Pre-train on PaySim):
  Data:  paysim_sequences.parquet
  Label: user_is_fraud (1 if any sequence event is fraud)
  Loss:  BCE with label smoothing 0.05
  Epochs: 50
  Notes: PaySim fraud labels are noisy (isFlaggedFraud ≠ isFraud).
         Label smoothing prevents overfit on noisy positive labels.

TRAIN — Phase 2 (Fine-tune on IEEE-CIS):
  Data:  ieee_cis behavioral sequences (group by user_key, sort by TransactionDT)
         Sequence events: (ProductCD_idx, log_TransactionAmt, delta_t_norm)
  Label: max(isFraud) per user session
  Loss:  BCE focal (gamma=1.5) — IEEE-CIS sequences are shorter, less noisy
  Epochs: 20 (frozen encoder for first 5 epochs, then unfreeze)
  LR:    1e-4 (lower than pre-train to preserve PaySim knowledge)
  Notes: Replace only the classifier head. Encoder weights from PaySim transfer.
         IEEE-CIS events use ProductCD (5 types) as type_idx, not PaySim types.
         Map: {'W':1,'C':2,'R':3,'H':4,'S':5} — same vocab size ≤ PaySim's 5.

OUTPUT: seq_embedding[64] + anomaly_score[1] (log-perplexity via BCE loss value)
"""

IEEE_CIS_TYPE_MAP = {"W": 1, "C": 2, "R": 3, "H": 4, "S": 5}

SEQ_PRETRAIN_CONFIG = {
    "data":    "paysim_sequences.parquet  (PaySim corpus)",
    "label":   "user_is_fraud",
    "loss":    "BCE + label smoothing 0.05",
    "epochs":  50,
    "optimizer": "AdamW lr=3e-4, warmup 5 epochs",
    "save":    "models/seq_transformer_paysim_pretrained.pt",
}
SEQ_FINETUNE_CONFIG = {
    "data":    "ieee_cis_sequences (built from user_key groups)",
    "label":   "max isFraud per user session",
    "loss":    "Focal BCE gamma=1.5",
    "epochs":  20,
    "freeze":  "encoder frozen for epochs 1-5, then full fine-tune",
    "lr":      "1e-4",
    "output":  "seq_embedding[64] + anomaly_score[1]",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL D — Tabular Autoencoder  (Novelty Detector)
# ═══════════════════════════════════════════════════════════════════════════
"""
WHAT IT IS:
  MLP autoencoder trained ONLY on legitimate transactions (isFraud=0).
  Reconstruction error at inference = novelty score.
  High error = transaction doesn't look like any seen legitimate pattern.

TRAIN DATA:
  ieee_cis_merged WHERE isFraud == 0  (train split only — NO fraud rows).
  Features: V1-V339 + C1-C14 + D1-D15 + TransactionAmt  (~369 features)
  Label: NONE (self-supervised)

SPECIAL:
  Use contractive regularisation term: penalise sensitivity of latent
  representation to input perturbations. Makes the latent space smoother
  and reconstruction error more meaningful.
  Contractive loss: ||J_e||^2_F (Frobenius norm of encoder Jacobian)
  Total loss: MSE_reconstruction + lambda_c * contractive_term (lambda=1e-4)

OUTPUT: recon_error[1]  (scalar, becomes one of H's inputs)
"""

class TabularAutoEncoder(nn.Module):
    def __init__(
        self,
        in_dim:     int,
        latent_dim: int   = 64,
        dropout:    float = 0.1,
    ):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, 256),
            nn.LayerNorm(256),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(256, 128),
            nn.GELU(),
            nn.Linear(128, latent_dim),
        )
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 128),
            nn.GELU(),
            nn.Linear(128, 256),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(256, in_dim),
        )

    def forward(self, x):
        z     = self.encoder(x)
        x_hat = self.decoder(z)
        return {"latent": z, "reconstruction": x_hat}

    def reconstruction_error(self, x):
        with torch.no_grad():
            x_hat = self.forward(x)["reconstruction"]
            return F.mse_loss(x_hat, x, reduction="none").mean(dim=-1)


AE_TRAIN_CONFIG = {
    "data":    "ieee_cis_merged WHERE isFraud==0 (legitimate only)",
    "label":   "NONE — unsupervised",
    "loss":    "MSE reconstruction + 1e-4 * contractive regularisation",
    "epochs":  60,
    "optimizer": "Adam lr=1e-3",
    "notes":   "Threshold reconstruction error at 95th percentile of val set"
               " to define 'anomalous'. This threshold is the operational cutoff.",
    "output":  "recon_error[1]",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL E — Heterogeneous GNN  (HGT / HAN)
# ═══════════════════════════════════════════════════════════════════════════
"""
WHAT IT IS:
  Heterogeneous Graph Transformer (HGT) operating on the full 7-relation graph.
  Node features initialised from Model A (transactions) and B (devices).
  Encoder backbone initialised from DGraphFin pre-trained weights.

INIT (before training):
  Load DGraphFin encoder weights → initialise layer1, layer2, layer3.
  HGT has relation-specific projections ON TOP of the shared encoder.
  The shared encoder part loads from DGraphFin; relation projections random-init.

TRAIN DATA:
  hetero_graph.pt  (PyG HeteroData)
  Node labels: transaction.y = isFraud, user.y = max(isFraud)
  Uses mini-batch training via NeighborLoader (2-hop neighborhood).
  Batch size: 1024 seed nodes.

SPECIAL:
  - Predict on TRANSACTION nodes (primary) and USER nodes (secondary).
  - Multi-task loss: L = 0.7 * L_txn + 0.3 * L_user
  - Relation-specific dropout: edge types with few edges get higher dropout.
  - After training: extract transaction embeddings → store in node feature store
    for downstream models F, G, H.

OUTPUT:
  per-node embeddings [N_nodes, 128]
  ring_score [N_users]      (from 2nd_degree_fraud_rate propagation)
  txn_graph_embedding [N_txn, 128]  → fed to F, G, H
"""

class HGTLayer(nn.Module):
    """
    Single Heterogeneous Graph Transformer layer.
    For each edge type: separate K, Q, V projections.
    Attention aggregates neighbor messages.
    """
    def __init__(
        self,
        in_dim:     int,
        out_dim:    int,
        n_heads:    int,
        edge_types: list,
        dropout:    float = 0.2,
    ):
        super().__init__()
        self.n_heads = n_heads
        self.d_head  = out_dim // n_heads

        # Per-relation projections
        self.W_K = nn.ModuleDict({et: nn.Linear(in_dim, out_dim) for et in edge_types})
        self.W_Q = nn.ModuleDict({et: nn.Linear(in_dim, out_dim) for et in edge_types})
        self.W_V = nn.ModuleDict({et: nn.Linear(in_dim, out_dim) for et in edge_types})
        self.W_O = nn.Linear(out_dim, out_dim)

        self.norm    = nn.LayerNorm(out_dim)
        self.dropout = nn.Dropout(dropout)

    def forward(self, x_dict, edge_index_dict):
        """
        x_dict        : {node_type: tensor [N, in_dim]}
        edge_index_dict: {(src,rel,dst): [2, E]}
        Returns: {node_type: tensor [N, out_dim]}
        """
        out_dict = {nt: torch.zeros(x.shape[0], self.W_O.out_features,
                                     device=x.device)
                    for nt, x in x_dict.items()}

        for (src_type, rel, dst_type), edge_index in edge_index_dict.items():
            et_key = f"{src_type}__{rel}__{dst_type}"
            if et_key not in self.W_K:
                continue

            src_idx, dst_idx = edge_index
            src_x = x_dict[src_type][src_idx]  # [E, in_dim]
            dst_x = x_dict[dst_type][dst_idx]

            K = self.W_K[et_key](src_x)
            Q = self.W_Q[et_key](dst_x)
            V = self.W_V[et_key](src_x)

            # Scaled dot-product attention per edge
            attn = (Q * K).sum(-1) / (self.d_head ** 0.5)  # [E]
            attn = torch.sigmoid(attn).unsqueeze(-1)

            msg = attn * V   # [E, out_dim]

            # Scatter-add to destination nodes
            out_dict[dst_type].scatter_add_(
                0,
                dst_idx.unsqueeze(-1).expand_as(msg),
                msg
            )

        return {nt: self.norm(self.dropout(self.W_O(h)))
                for nt, h in out_dict.items()}


class HeteroGNN(nn.Module):
    def __init__(
        self,
        node_in_dims: dict,       # {node_type: in_feature_dim}
        hidden_dim:   int   = 256,
        embed_dim:    int   = 128,
        n_heads:      int   = 4,
        n_layers:     int   = 3,
        edge_types:   list  = None,
        dropout:      float = 0.2,
    ):
        super().__init__()
        et = edge_types or []

        # Per-type input projections (handle different feature dims)
        self.input_projs = nn.ModuleDict({
            nt: nn.Linear(dim, hidden_dim)
            for nt, dim in node_in_dims.items()
        })

        self.layers = nn.ModuleList([
            HGTLayer(hidden_dim, hidden_dim, n_heads, et, dropout)
            for _ in range(n_layers - 1)
        ] + [
            HGTLayer(hidden_dim, embed_dim, n_heads, et, dropout)
        ])

        # Classification heads
        self.txn_head  = nn.Linear(embed_dim, 1)
        self.user_head = nn.Linear(embed_dim, 1)

    def encode(self, x_dict, edge_index_dict):
        h = {nt: F.relu(proj(x_dict[nt]))
             for nt, proj in self.input_projs.items()
             if nt in x_dict}

        for layer in self.layers:
            h = layer(h, edge_index_dict)
        return h

    def forward(self, x_dict, edge_index_dict):
        h = self.encode(x_dict, edge_index_dict)
        out = {"embeddings": h}
        if "transaction" in h:
            out["txn_logits"]  = self.txn_head(h["transaction"]).squeeze(-1)
        if "user" in h:
            out["user_logits"] = self.user_head(h["user"]).squeeze(-1)
        return out

    def load_dgraphfin_weights(self, weight_dict: dict):
        """
        Transfer DGraphFin pre-trained encoder weights.
        DGraphFin used homogeneous GraphSAGE; map to first n_layers.
        Only layer linear weights transfer — relation projections are new.
        """
        for i, layer in enumerate(self.layers):
            key_prefix = f"layer{i+1}.linear"
            if key_prefix + ".weight" in weight_dict:
                # Map shared linear to per-relation K projections
                for et_key in layer.W_K:
                    layer.W_K[et_key].weight.data.copy_(
                        weight_dict[key_prefix + ".weight"][:layer.W_K[et_key].out_features]
                    )
                print(f"[HeteroGNN] DGraphFin weights transferred to layer {i+1}")


HGT_TRAIN_CONFIG = {
    "init":    "DGraphFin pre-trained encoder weights → layer1,2,3",
    "data":    "hetero_graph.pt (HeteroData, 2-hop NeighborLoader)",
    "label":   "transaction.y=isFraud + user.y=max(isFraud)",
    "loss":    "0.7 * focal_loss(txn) + 0.3 * focal_loss(user)",
    "epochs":  40,
    "batch":   "NeighborLoader, 1024 seed nodes, 2-hop sampling",
    "optimizer": "AdamW lr=5e-4, weight_decay=1e-4",
    "notes":   "Freeze DGraphFin-init layers for first 10 epochs."
               " Unfreeze and fine-tune all at 0.1x learning rate.",
    "output":  "embeddings{node_type→tensor[N,128]}, txn_logits, user_logits",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL F — Synthetic Identity Detector
# ═══════════════════════════════════════════════════════════════════════════
"""
WHAT IT IS:
  Small feed-forward classifier for synthetic identity detection.
  Combines rule-based features (M-flags, email domain, D-features)
  with graph signal (graph embedding from Model E).

TRAIN DATA:
  ieee_cis_merged with synthetic_identity_label column (derived in graft_ieee_cis).
  Features: M1-M9 + M_fail_count + M_all_fail + addr1 + addr2
            + P_emaildomain_encoded + R_emaildomain_encoded
            + card1 + card4 + card6 + D1 + D2 + D3
            + user_txn_count + txn_graph_embedding[128] from Model E
  Label: synthetic_identity_label  (~3-8% positive rate)

SPECIAL:
  Must run AFTER Model E — it consumes graph embeddings.
  Use SMOTE or class-weight oversampling (label very rare).
  Threshold calibration: set operating threshold at 90% precision
  (false positives on legit new users is expensive).

OUTPUT: synth_id_prob[1]  → one of H's inputs
"""

class SyntheticIdentityDetector(nn.Module):
    def __init__(
        self,
        tabular_dim: int   = 20,    # M-flags + email + card + D-features
        graph_dim:   int   = 128,   # from Model E
        hidden:      int   = 64,
        dropout:     float = 0.2,
    ):
        super().__init__()
        self.tab_proj   = nn.Linear(tabular_dim, hidden)
        self.graph_proj = nn.Linear(graph_dim,   hidden)
        self.classifier = nn.Sequential(
            nn.Linear(hidden * 2, 64),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
        )

    def forward(self, tab_x: torch.Tensor, graph_emb: torch.Tensor):
        tab_h   = F.relu(self.tab_proj(tab_x))
        graph_h = F.relu(self.graph_proj(graph_emb))
        combined = torch.cat([tab_h, graph_h], dim=-1)
        return {"logit": self.classifier(combined).squeeze(-1)}


SYNTH_TRAIN_CONFIG = {
    "data":       "ieee_cis_merged (synthetic_identity_label column)",
    "label":      "synthetic_identity_label (derived, ~5% positive)",
    "requires":   "Model E embeddings (txn_graph_embedding)",
    "loss":       "BCE with pos_weight=20 (imbalanced)",
    "epochs":     30,
    "optimizer":  "AdamW lr=5e-4",
    "threshold":  "Set at 90% precision on validation set",
    "output":     "synth_id_prob[1]",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL G — ATO Chain Detector
# ═══════════════════════════════════════════════════════════════════════════
"""
WHAT IT IS:
  Fusion classifier combining sequence context (Model C) + graph context
  (Model E) + temporal features (D-deltas) to detect ATO chains.

  ATO signature: anomalous login event → new device → high-value transaction.
  No single feature catches this; it requires all three signal streams.

TRAIN DATA:
  ieee_cis_merged with ATO_label derived as:
    ATO_label = isFraud AND device_match_type=='none' AND delta_t<3600 AND txn_rank<=2
  (Fraud on a new device within 1 hour of first activity = likely ATO)
  Features: seq_embedding[64] (from C) + txn_graph_embedding[128] (from E)
            + device_match_ord + device_novelty + delta_t_norm
            + txn_rank + amt_zscore + D1 + D2 + D3

SPECIAL:
  ATO_label is a derived secondary label — ~0.8% of all transactions.
  Train with heavy focal loss (gamma=3) and class weight.
  Post-training: tune decision threshold on a time-ordered val split
  (not random) because ATO patterns are time-dependent.

OUTPUT: ato_prob[1]  → one of H's inputs
"""

class ATOChainDetector(nn.Module):
    def __init__(
        self,
        seq_dim:    int   = 64,
        graph_dim:  int   = 128,
        scalar_dim: int   = 8,
        hidden:     int   = 128,
        dropout:    float = 0.2,
    ):
        super().__init__()
        self.seq_proj   = nn.Linear(seq_dim,    hidden)
        self.graph_proj = nn.Linear(graph_dim,  hidden)
        self.scalar_proj= nn.Linear(scalar_dim, hidden // 2)

        self.fusion = nn.Sequential(
            nn.Linear(hidden * 2 + hidden // 2, hidden),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden, 32),
            nn.GELU(),
            nn.Linear(32, 1),
        )

    def forward(
        self,
        seq_emb:   torch.Tensor,   # [B, 64]
        graph_emb: torch.Tensor,   # [B, 128]
        scalars:   torch.Tensor,   # [B, 8]  device + time features
    ):
        s = F.relu(self.seq_proj(seq_emb))
        g = F.relu(self.graph_proj(graph_emb))
        r = F.relu(self.scalar_proj(scalars))
        combined = torch.cat([s, g, r], dim=-1)
        return {"logit": self.fusion(combined).squeeze(-1)}


ATO_TRAIN_CONFIG = {
    "data":      "ieee_cis_merged with derived ATO_label",
    "label":     "ATO_label = isFraud & new_device & delta_t<3600 & txn_rank<=2",
    "requires":  "Model C seq_embedding + Model E graph_embedding",
    "loss":      "Focal BCE gamma=3, pos_weight=50",
    "epochs":    25,
    "val_split": "TIME-ORDERED (last 20% by TransactionDT) — NOT random",
    "threshold": "Calibrated on time-ordered val set",
    "output":    "ato_prob[1]",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL H — Ensemble Aggregator  (Stacked LightGBM)
# ═══════════════════════════════════════════════════════════════════════════
"""
WHAT IT IS:
  Gradient-boosted tree stacker consuming all upstream model outputs.
  This is NOT a neural net — LightGBM is the right tool here because:
  (1) the stacking features are a small set of calibrated scalars,
  (2) GBDT handles feature interactions without architecture choices,
  (3) fast to retrain for adaptive learning.

TRAIN DATA:
  Out-of-fold predictions from all upstream models (k=5 stratified CV).
  Using OOF predictions prevents data leakage into the meta-learner.
  Features (stacking inputs):
    tabnet_logit       (Model A)
    device_dist_score  (Model B)
    seq_anomaly_score  (Model C)
    paysim_boost       (Model C soft boost from PaySim)
    recon_error        (Model D)
    ring_score         (Model E)
    txn_graph_logit    (Model E)
    synth_id_prob      (Model F)
    ato_prob           (Model G)
    [optionally: raw tabular features top-20 by SHAP importance from A]
  Label: isFraud

SPECIAL:
  Hyperparameters:
    n_estimators=1000, learning_rate=0.05, max_depth=6,
    num_leaves=63, min_child_samples=50,
    scale_pos_weight=n_neg/n_pos (class imbalance),
    feature_fraction=0.8, bagging_fraction=0.8
  Early stopping on val AUC (patience=50 rounds).

OUTPUT: raw_fraud_score[1] ∈ [0,1]
"""

LGBM_TRAIN_CONFIG = {
    "framework": "LightGBM (not PyTorch)",
    "data":      "OOF predictions from models A-G + top-20 raw features",
    "label":     "isFraud",
    "cv":        "5-fold stratified, OOF to prevent leakage",
    "params": {
        "n_estimators":     1000,
        "learning_rate":    0.05,
        "max_depth":        6,
        "num_leaves":       63,
        "min_child_samples": 50,
        "scale_pos_weight": "n_neg/n_pos",
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "early_stopping":   50,
        "metric":           "auc",
    },
    "output":    "raw_fraud_score ∈ [0,1]",
    "explainability": "SHAP TreeExplainer on LightGBM — top-3 features per prediction",
}


# ═══════════════════════════════════════════════════════════════════════════
# MODEL I — Score Calibrator + SHAP Explainer
# ═══════════════════════════════════════════════════════════════════════════
"""
WHAT IT IS:
  Platt scaling (logistic regression on H's raw score) to convert
  raw_fraud_score → true calibrated probability (ECE < 0.02).
  SHAP TreeExplainer run on H to generate per-prediction reason codes.

WHY CALIBRATION:
  LightGBM scores are well-ranked but NOT calibrated probabilities.
  A score of 0.7 does not mean 70% fraud probability.
  Platt scaling fits: P(fraud) = sigmoid(a * raw_score + b)
  where a, b are fit on a held-out calibration set (not the training set).

SHAP REASON CODES:
  Top-3 positive SHAP values with direction and magnitude.
  Formatted as human-readable strings for the decision engine:
    "Transaction amount 4.2x above user average (↑ risk +0.23)"
    "New device fingerprint — not in user history (↑ risk +0.18)"
    "38% of 2nd-degree connections are known fraudsters (↑ risk +0.14)"

TRAIN DATA:
  Calibration set: 10% held-out from the main train split.
  NEVER use the test set for calibration.

OUTPUT:
  calibrated_prob ∈ [0,1]
  reason_codes: list of top-3 SHAP strings
  decision: 'approve' | 'mfa' | 'block'
    approve: calibrated_prob < 0.30
    mfa:     0.30 ≤ calibrated_prob < 0.70
    block:   calibrated_prob ≥ 0.70
"""

class PlattCalibrator(nn.Module):
    def __init__(self):
        super().__init__()
        self.a = nn.Parameter(torch.tensor(1.0))
        self.b = nn.Parameter(torch.tensor(0.0))

    def forward(self, raw_score: torch.Tensor) -> torch.Tensor:
        return torch.sigmoid(self.a * raw_score + self.b)

    def fit(self, raw_scores: np.ndarray, labels: np.ndarray, epochs: int = 200):
        opt = torch.optim.LBFGS(self.parameters(), lr=0.1)
        x = torch.tensor(raw_scores, dtype=torch.float32)
        y = torch.tensor(labels,     dtype=torch.float32)

        def closure():
            opt.zero_grad()
            loss = F.binary_cross_entropy(self(x), y)
            loss.backward()
            return loss

        for _ in range(epochs):
            opt.step(closure)
        print(f"[Calibrator] a={self.a.item():.4f}, b={self.b.item():.4f}")


CALIBRATION_TRAIN_CONFIG = {
    "data":      "10% held-out calibration set (never test set)",
    "method":    "Platt scaling (logistic on raw_score)",
    "loss":      "BCE",
    "optimizer": "L-BFGS",
    "output":    "calibrated_prob + decision (approve/mfa/block) + SHAP reasons",
    "thresholds": {"approve": 0.30, "mfa": 0.70},
}


# ═══════════════════════════════════════════════════════════════════════════
# TRAINING ORDER SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

TRAINING_ORDER = """
Step 0  Pre-train DGraphFin GNN  →  save dgraphfin_pretrained.pt
Step 1  Pre-train PaySim SeqTransformer  →  save seq_paysim_pretrained.pt
Step 2  Pre-train TabNet (self-supervised, no labels)  →  save tabnet_pretrained.pt
        [Steps 0,1,2 can run in parallel — no dependencies]

Step 3  Fine-tune TabNet (supervised, isFraud)  →  save tabnet_finetuned.pt
        Output: tabnet_logit column in feature store

Step 4  Train Siamese Device Encoder  →  save siamese_device.pt
        Output: device_dist_score column in feature store

Step 5  Fine-tune SeqTransformer on IEEE-CIS  →  save seq_ieee_finetuned.pt
        Output: seq_embedding + anomaly_score columns in feature store

Step 6  Train Tabular Autoencoder (legit only)  →  save tabular_ae.pt
        Output: recon_error column in feature store

Step 7  Build HeteroGraph from all above outputs + raw graph

Step 8  Train HeteroGNN (init from DGraphFin weights)  →  save hetero_gnn.pt
        Output: txn_graph_embedding + ring_score in feature store

Step 9  Train SyntheticIdentityDetector (needs Model E)  →  save synth_id.pt
        Output: synth_id_prob column

Step 10 Train ATOChainDetector (needs Models C + E)  →  save ato_detector.pt
        Output: ato_prob column

Step 11 Compute OOF predictions from Steps 3-10 (5-fold CV)
        Train LightGBM stacker on OOF  →  save lgbm_stacker.lgb

Step 12 Fit Platt calibrator on held-out set  →  save platt_calibrator.pt
        Pre-compute SHAP explainer on LightGBM

Step 13 Validate full pipeline on TEST set (never touched before).
        Report: AUC, AP, F1@0.30, F1@0.70, latency p99
"""

if __name__ == "__main__":
    print(TRAINING_ORDER)
