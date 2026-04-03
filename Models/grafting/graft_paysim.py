"""
graft_paysim.py
───────────────
PaySim simulates mobile money transactions (TRANSFER, CASH_OUT, etc.)
Its nameOrig/nameDest have NO overlap with IEEE-CIS user_id_proxy.

Three grafts:
  1. Sequence corpus — group PaySim events per originator into
     JSON behavioral sequences. Train Model C's encoder on these.
     At inference, IEEE-CIS sessions are encoded in the same space.

  2. Transfer edge table — User→User TRANSFERRED edges weighted
     by amount. These feed Model E's heterogeneous graph.

  3. Soft label boosting — if an IEEE-CIS user's behavioral sequence
     is close to a high-fraud PaySim sequence (cosine sim > 0.85),
     their anomaly score gets a multiplicative boost at inference time.
"""

import json
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from typing import List, Dict, Tuple
import sys
sys.path.append(str(Path(__file__).parent.parent))
from utils.constants import SEQUENCE_PAD, make_user_key


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: BUILD PAYSIM SEQUENCE CORPUS
# ─────────────────────────────────────────────────────────────────────────────

# PaySim transaction types
PAYSIM_TYPES = ["PAYMENT", "TRANSFER", "CASH_OUT", "DEBIT", "CASH_IN"]
TYPE2IDX = {t: i+1 for i, t in enumerate(PAYSIM_TYPES)}  # 0 = PAD
PAD_IDX  = 0

def load_paysim(paysim_path: str):
    # 1. Read only the columns we need to save RAM
    cols = ["step", "type", "amount", "nameOrig", "nameDest", "isFraud"]
    df = pd.read_csv(paysim_path, usecols=cols)
    
    # 2. SEPARATE FRAUD AND LEGIT
    fraud_df = df[df['isFraud'] == 1]
    legit_df = df[df['isFraud'] == 0]
    
    # 3. KEEP ALL FRAUD USERS
    fraud_users = fraud_df['nameOrig'].unique()
    
    # 4. SELECT SUBSET OF LEGIT USERS (To keep seq_len > 1)
    # Find users who actually have a history
    user_counts = legit_df['nameOrig'].value_counts()
    active_legit_users = user_counts[user_counts > 1].index[:]
    
    # 5. COMBINE
    keep_users = np.unique(np.concatenate([fraud_users, active_legit_users]))
    df = df[df['nameOrig'].isin(keep_users)]
    
    print(f"[PaySim] Optimized Load: {len(df):,} rows.")
    print(f"[PaySim] Fraud users preserved: {len(fraud_users)}")
    return df

def build_sequence_corpus(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group PaySim rows by nameOrig, sort by step.
    Each originator's history becomes one behavioral sequence.

    Output DataFrame (one row per originator):
      nameOrig          : originator ID
      sequence          : list of (type_idx, norm_amount, step_norm, is_fraud)
      sequence_json     : JSON string of the above (for storage)
      user_is_fraud     : 1 if ANY transaction in sequence is fraud
      fraud_step        : which step the fraud occurred (-1 if none)
      seq_length        : number of transactions

    The 4-tuple per event encodes: WHAT (type), HOW MUCH (amount),
    WHEN (relative time), and IS_FRAUD (soft label for the event).
    The sequence transformer uses the first 3 as input and the last
    as auxiliary supervision during pre-training.
    """
    df = df.sort_values(["nameOrig", "step"])

    # Normalise amount log-scale (heavy tail)
    df["log_amount"] = np.log1p(df["amount"]) / np.log1p(df["amount"].max())
    df["type_idx"]   = df["type"].map(TYPE2IDX).fillna(0).astype(int)

    def _build_seq(group):
        steps = group["step"].values
        step_norm = (steps - steps.min()) / max(steps.max() - steps.min(), 1)

        events = [
            {
                "type_idx":   int(row["type_idx"]),
                "log_amount": float(row["log_amount"]),
                "step_norm":  float(sn),
                "is_fraud":   int(row["isFraud"]),
            }
            for (_, row), sn in zip(group.iterrows(), step_norm)
        ]

        fraud_steps = group[group["isFraud"] == 1]["step"].tolist()
        return pd.Series({
            "sequence":       events,
            "sequence_json":  json.dumps(events),
            "user_is_fraud":  int(group["isFraud"].max()),
            "fraud_step":     int(fraud_steps[0]) if fraud_steps else -1,
            "seq_length":     len(events),
        })

    corpus = df.groupby("nameOrig", group_keys=False).apply(_build_seq).reset_index()
    corpus = corpus.rename(columns={"nameOrig": "paysim_user_id"})

    print(f"[PaySim] Sequence corpus: {len(corpus):,} users  "
          f"|  fraud users: {corpus['user_is_fraud'].sum():,}  "
          f"|  median seq_len: {corpus['seq_length'].median():.0f}")
    return corpus


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: COLLATE SEQUENCES INTO PADDED TENSORS (for Model C training)
# ─────────────────────────────────────────────────────────────────────────────

def collate_sequences(
    corpus: pd.DataFrame,
    max_len: int = SEQUENCE_PAD
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Convert sequence corpus to padded tensors for the transformer.

    Returns:
        x     : [N, max_len, 3]   — (type_idx_onehot_placeholder, log_amount, step_norm)
                 type_idx kept as int for embedding lookup, stored as x[:,:,0]
        mask  : [N, max_len]      — 1 = real token, 0 = pad
        labels: [N]               — user_is_fraud (binary)
    """
    N = len(corpus)
    x_arr   = np.zeros((N, max_len, 3), dtype=np.float32)
    mask    = np.zeros((N, max_len),    dtype=np.float32)
    labels  = corpus["user_is_fraud"].values.astype(np.int64)

    for i, events in enumerate(corpus["sequence"]):
        seq = events[:max_len]
        L   = len(seq)
        for t, ev in enumerate(seq):
            x_arr[i, t, 0] = ev["type_idx"]
            x_arr[i, t, 1] = ev["log_amount"]
            x_arr[i, t, 2] = ev["step_norm"]
        mask[i, :L] = 1.0

    return (
        torch.tensor(x_arr),
        torch.tensor(mask),
        torch.tensor(labels)
    )


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: SEQUENCE TRANSFORMER MODEL (Model C — defined here for pre-training)
# ─────────────────────────────────────────────────────────────────────────────

class BehavioralSequenceTransformer(nn.Module):
    """
    Transformer encoder over behavioral event sequences.

    Pre-trained on PaySim corpus (supervised: user_is_fraud label).
    Fine-tuned on IEEE-CIS behavioral sequences (same label: isFraud).

    Input per token: (type_idx, log_amount, step_norm)
      type_idx → embedding lookup [vocab_size, d_model]
      log_amount, step_norm → linear projection
    All three combined via addition before transformer.

    CLS token prepended; its output = sequence representation.
    """
    def __init__(
        self,
        vocab_size:  int   = len(PAYSIM_TYPES) + 1,   # +1 for PAD
        d_model:     int   = 128,
        n_heads:     int   = 4,
        n_layers:    int   = 3,
        d_ff:        int   = 256,
        dropout:     float = 0.1,
        max_len:     int   = SEQUENCE_PAD + 1,         # +1 for CLS
        embed_dim:   int   = 64,                        # output dim
    ):
        super().__init__()
        self.d_model    = d_model
        self.embed_dim  = embed_dim

        # Type embedding
        self.type_embed = nn.Embedding(vocab_size, d_model, padding_idx=PAD_IDX)

        # Continuous feature projection
        self.cont_proj  = nn.Linear(2, d_model)   # log_amount, step_norm

        # CLS token (learnable)
        self.cls_token  = nn.Parameter(torch.randn(1, 1, d_model))

        # Positional encoding (learnable)
        self.pos_embed  = nn.Embedding(max_len, d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=n_heads,
            dim_feedforward=d_ff, dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)

        # Project CLS output to embed_dim
        self.to_embed   = nn.Linear(d_model, embed_dim)

        # Anomaly / classification head
        self.classifier = nn.Sequential(
            nn.Linear(embed_dim, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1)
        )

    def encode(
        self,
        x:    torch.Tensor,    # [B, L, 3]: col0=type_idx, col1=log_amount, col2=step_norm
        mask: torch.Tensor     # [B, L]:    1=real, 0=pad
    ) -> torch.Tensor:
        """Returns [B, embed_dim] sequence embedding."""
        B, L, _ = x.shape

        type_idx   = x[:, :, 0].long()                    # [B, L]
        cont_feats = x[:, :, 1:]                          # [B, L, 2]

        type_emb   = self.type_embed(type_idx)             # [B, L, d_model]
        cont_emb   = self.cont_proj(cont_feats)            # [B, L, d_model]
        token_emb  = type_emb + cont_emb                  # [B, L, d_model]

        # Prepend CLS
        cls        = self.cls_token.expand(B, 1, self.d_model)
        tokens     = torch.cat([cls, token_emb], dim=1)   # [B, L+1, d_model]

        # Positional encoding
        positions  = torch.arange(L + 1, device=x.device).unsqueeze(0)
        tokens     = tokens + self.pos_embed(positions)

        # Attention mask (transformer expects True = ignore)
        cls_mask   = torch.zeros(B, 1, device=x.device)
        full_mask  = torch.cat([cls_mask, 1.0 - mask], dim=1).bool()

        encoded    = self.transformer(tokens, src_key_padding_mask=full_mask)
        cls_out    = encoded[:, 0, :]                     # [B, d_model]
        return self.to_embed(cls_out)                      # [B, embed_dim]

    def forward(self, x, mask):
        emb    = self.encode(x, mask)
        logits = self.classifier(emb).squeeze(-1)
        return {"embedding": emb, "logits": logits}

from sklearn.metrics import precision_score, recall_score, f1_score

def pretrain_sequence_transformer(
    corpus:     pd.DataFrame,
    save_path:  str,
    epochs:     int   = 50,
    batch_size: int   = 256,
    lr:         float = 3e-4,
    device:     str   = "cuda"
) -> BehavioralSequenceTransformer:
    
    dev = torch.device(device)
    x, mask, labels = collate_sequences(corpus)
    x, mask, labels = x.to(dev), mask.to(dev), labels.to(dev)

    model = BehavioralSequenceTransformer().to(dev)
    
    # CALCULATE CLASS WEIGHT: 9298 users / 28 fraud users = ~332
    # This tells the model that missing 1 fraud is as bad as 332 false alarms.
    pos_weight = torch.tensor([(len(labels) - labels.sum()) / labels.sum()], device=dev)
    
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

    N = x.shape[0]
    n_batches = (N + batch_size - 1) // batch_size

    def warmup_lr(epoch):
        return epoch / 5 if epoch < 5 else 1.0
    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, warmup_lr)

    print(f"\n{'Epoch':>5} | {'Loss':>8} | {'Prec':>7} | {'Rec':>7} | {'F1':>7}")
    print("-" * 50)

    def focal_binary_cross_entropy(logits, targets, alpha=0.75, gamma=2.0):
        p = torch.sigmoid(logits)
        bce_loss = F.binary_cross_entropy_with_logits(logits, targets, reduction='none')
        p_t = p * targets + (1 - p) * (1 - targets)
        loss = alpha * (1 - p_t)**gamma * bce_loss
        return loss.mean()

    best_f1 = 0.0
    for epoch in range(1, epochs + 1):
        model.train()
        epoch_loss = 0.0
        all_preds = []
        all_labels = []
        
        perm = torch.randperm(N, device=dev)

        for i in range(n_batches):
            idx = perm[i * batch_size: (i+1) * batch_size]
            xb, mb, lb = x[idx], mask[idx], labels[idx].float()
            xb[:, :, 0] += torch.randn_like(xb[:, :, 1]) * 0.01  # 1% jitter
            optimizer.zero_grad()
            out = model(xb, mb)
            
            # Use pos_weight in the loss function to handle the extreme imbalance
            lb_smooth = lb * 0.7 + 0.15
            # loss = F.binary_cross_entropy_with_logits(
            #     out["logits"], 
            #     lb_smooth, 
            #     pos_weight=pos_weight
            # )


            loss = focal_binary_cross_entropy(out["logits"], lb_smooth)
            
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            
            epoch_loss += loss.item()
            
            # Collect metrics
            preds = (torch.sigmoid(out["logits"]) > 0.5).int().cpu().numpy()
            all_preds.extend(preds)
            all_labels.extend(lb.cpu().numpy().astype(int))

        scheduler.step()
        
        avg_loss = epoch_loss / n_batches
        prec = precision_score(all_labels, all_preds, zero_division=0)
        rec  = recall_score(all_labels, all_preds, zero_division=0)
        f1   = f1_score(all_labels, all_preds, zero_division=0)

        print(f"{epoch:5d} | {avg_loss:8.4f} | {prec:7.2f} | {rec:7.2f} | {f1:7.2f}")

        if f1 > best_f1:
            best_f1 = f1
            torch.save(model.state_dict(), save_path)

    print(f"\n[PaySim] Pre-training done. Best F1: {best_f1:.4f}")
    return model

# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: TRANSFER EDGES (User → User TRANSFERRED)
# ─────────────────────────────────────────────────────────────────────────────

def build_transfer_edges(paysim_df: pd.DataFrame) -> pd.DataFrame:
    """
    Build the User→User TRANSFERRED edge table for the hetero graph.
    Each edge: (src_user_id, dst_user_id, total_amount, n_transfers,
                fraud_transfer_rate, edge_type='TRANSFERRED')

    For IEEE-CIS, equivalent edges come from addr1 != addr2 transactions
    (fund redirection signal). Both are combined in the graph builder.
    """
    edges = paysim_df[paysim_df["type"].isin(["TRANSFER","CASH_OUT"])]\
        .groupby(["nameOrig","nameDest"]).agg(
            total_amount        = ("amount",   "sum"),
            n_transfers         = ("amount",   "count"),
            fraud_transfer_rate = ("isFraud",  "mean"),
        ).reset_index()

    edges.columns = ["src_user_id","dst_user_id",
                     "total_amount","n_transfers","fraud_transfer_rate"]
    edges["log_amount"]  = np.log1p(edges["total_amount"])
    edges["edge_type"]   = "TRANSFERRED"

    print(f"[PaySim] Transfer edges: {len(edges):,}  "
          f"|  fraud-involved: {(edges['fraud_transfer_rate']>0).sum():,}")
    return edges


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: SOFT LABEL BOOST (similarity-based anomaly amplification)
# ─────────────────────────────────────────────────────────────────────────────

def compute_sequence_softboost(
    ieee_sequences:   List[List[Dict]],
    paysim_corpus:    pd.DataFrame,
    model:            BehavioralSequenceTransformer,
    device:           str = "cpu",
    sim_threshold:    float = 0.85,
    boost_factor:     float = 1.5,
    batch_size:       int = 512,
) -> np.ndarray:
    """
    For each IEEE-CIS user sequence, find the most similar PaySim sequence.
    If cosine similarity > threshold AND that PaySim user is fraudulent,
    return a boost multiplier (>1.0) for the anomaly score.

    This implements the cross-dataset soft label transfer described in
    the architecture spec.

    Returns: boost_factors array [N_ieee_users], values in {1.0, boost_factor}
    """
    dev = torch.device(device)
    model = model.to(dev).eval()

    def _encode_sequences(seqs: List[List[Dict]]) -> torch.Tensor:
        N   = len(seqs)
        x   = np.zeros((N, SEQUENCE_PAD, 3), dtype=np.float32)
        msk = np.zeros((N, SEQUENCE_PAD),    dtype=np.float32)
        for i, events in enumerate(seqs):
            for t, ev in enumerate(events[:SEQUENCE_PAD]):
                x[i, t, 0] = ev.get("type_idx", 0)
                x[i, t, 1] = ev.get("log_amount", 0)
                x[i, t, 2] = ev.get("step_norm", 0)
            msk[i, :min(len(events), SEQUENCE_PAD)] = 1.0
        return torch.tensor(x, device=dev), torch.tensor(msk, device=dev)

    # Encode all PaySim sequences (fraud ones only — we only boost toward fraud)
    fraud_corpus = paysim_corpus[paysim_corpus["user_is_fraud"] == 1]
    paysim_seqs  = fraud_corpus["sequence"].tolist()

    with torch.no_grad():
        px, pm  = _encode_sequences(paysim_seqs)
        paysim_embeds = []
        for i in range(0, len(paysim_seqs), batch_size):
            emb = model.encode(px[i:i+batch_size], pm[i:i+batch_size])
            paysim_embeds.append(F.normalize(emb, dim=-1).cpu())
        paysim_embeds = torch.cat(paysim_embeds, dim=0)  # [N_paysim, 64]

        # Encode IEEE-CIS sequences
        ix, im = _encode_sequences(ieee_sequences)
        ieee_embeds = []
        for i in range(0, len(ieee_sequences), batch_size):
            emb = model.encode(ix[i:i+batch_size], im[i:i+batch_size])
            ieee_embeds.append(F.normalize(emb, dim=-1).cpu())
        ieee_embeds = torch.cat(ieee_embeds, dim=0)  # [N_ieee, 64]

    # Cosine similarity matrix (chunked to avoid OOM)
    boost_factors = np.ones(len(ieee_sequences), dtype=np.float32)
    chunk = 1000
    for i in range(0, len(ieee_sequences), chunk):
        sims = torch.mm(ieee_embeds[i:i+chunk], paysim_embeds.T)  # [chunk, N_paysim]
        max_sims = sims.max(dim=1).values.numpy()
        boost_factors[i:i+chunk] = np.where(
            max_sims >= sim_threshold, boost_factor, 1.0
        )

    n_boosted = (boost_factors > 1.0).sum()
    print(f"[PaySim] Soft boost applied to {n_boosted:,} IEEE-CIS sequences "
          f"(sim > {sim_threshold})")
    return boost_factors


# ─────────────────────────────────────────────────────────────────────────────
# MASTER FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def process_paysim(
    paysim_path:    str,
    seq_save_path:  str  = None,
    model_save_path: str = None,
    pretrain:       bool = True,
    device:         str  = "cuda"
) -> Tuple[pd.DataFrame, pd.DataFrame, BehavioralSequenceTransformer]:
    """
    Returns:
        corpus       — PaySim sequence corpus DataFrame
        edges        — User→User transfer edge table
        model        — Pre-trained BehavioralSequenceTransformer
    """
    df      = load_paysim(paysim_path)
    print("Calculating Markov Chain probabilities...")
    corpus  = build_sequence_corpus(df)
    print("Grafting sequences onto IEEE master spine...")
    edges   = build_transfer_edges(df)
    print("Pre-training sequence transformer on PaySim corpus...")
    if seq_save_path:
        corpus.drop(columns=["sequence"]).to_parquet(seq_save_path, index=False)

    model = BehavioralSequenceTransformer()
    if pretrain and model_save_path:
        model = pretrain_sequence_transformer(
            corpus, model_save_path, device=device
        )
    elif model_save_path and Path(model_save_path).exists():
        model.load_state_dict(torch.load(model_save_path, map_location="cpu"))
        print(f"[PaySim] Loaded pre-trained model from {model_save_path}")

    return corpus, edges, model


if __name__ == "__main__":
    print("cuda" if torch.cuda.is_available() else "cpu")
    corpus, edges, model = process_paysim(
        paysim_path="data/PS_20174392719_1491204439457_log.csv",
        seq_save_path="data/processed/paysim_sequences.parquet",
        model_save_path="models/seq_transformer_paysim_pretrained.pt",
        pretrain=True,
        device="cuda" if torch.cuda.is_available() else "cpu"
    )
    print(corpus[["paysim_user_id","seq_length","user_is_fraud"]].describe())
    print(edges[["total_amount","n_transfers","fraud_transfer_rate"]].describe())
