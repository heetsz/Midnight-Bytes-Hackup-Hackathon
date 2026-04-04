"""
run_pipeline.py
───────────────
Master pipeline: from raw CSVs → unified feature store → trained models.
Run this file end-to-end OR call individual stages by name.

Final state after full pipeline:
  data/processed/
    ieee_cis_processed.parquet      — IEEE-CIS after graft_ieee_cis
    ieee_cis_with_graph.parquet     — + DGraphFin columns validated
    ieee_cis_fully_enriched.parquet — + AmIUnique device features
    siamese_pairs.parquet           — Siamese training pairs
    paysim_sequences.parquet        — PaySim sequence corpus
    paysim_edges.parquet            — PaySim transfer edges
    hetero_graph.pt                 — PyG HeteroData

  models/
    dgraphfin_pretrained.pt         — DGraphFin GraphSAGE weights
    seq_transformer_paysim_pretrained.pt
    seq_transformer_ieee_finetuned.pt
    tabnet_pretrained.pt
    tabnet_finetuned.pt
    siamese_device.pt
    tabular_ae.pt
    hetero_gnn.pt
    synth_id_detector.pt
    ato_chain_detector.pt
    lgbm_stacker.lgb
    platt_calibrator.pt

  features/
    feature_store.parquet           — all upstream model outputs per transaction
                                      (the stacking features for Model H)
"""

import json
import argparse
import numpy as np
import pandas as pd
import torch
from pathlib import Path
import torch.nn.functional as F
import os
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import roc_auc_score
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any
import logging
from pathlib import Path
import joblib  # For saving sklearn models like IsotonicRegression

logger = logging.getLogger(__name__)

# Fallback for PyG if not installed for Phase 2
try:
    from torch_geometric.data import Data
    from torch_geometric.nn import SAGEConv
except ImportError:
    logger.warning("torch_geometric not found. GNN phase will require it.")
# ─────────────────────────────────────────────────────────────────────────────
# STAGE RUNNERS
# ─────────────────────────────────────────────────────────────────────────────

def stage_0_dgraphfin_pretrain(cfg):
    """Pre-train GraphSAGE on DGraphFin. Run once."""
    from grafting.graft_dgraphfin import pretrain_dgraphfin
    if Path(cfg["dgraphfin_weights"]).exists():
        print("[Stage 0] DGraphFin weights already exist, skipping.")
        return
    pretrain_dgraphfin(
        dgraphfin_dir=cfg["dgraphfin_dir"],
        save_path=cfg["dgraphfin_weights"],
        epochs=cfg.get("dgraphfin_epochs", 100),
        device=cfg["device"],
    )


def stage_1_paysim_pretrain(cfg):
    """Pre-train sequence transformer on PaySim. Run once."""
    from grafting.graft_paysim import process_paysim
    if Path(cfg["seq_paysim_weights"]).exists():
        print("[Stage 1] PaySim seq transformer already exists, skipping.")
        return
    corpus, edges, model = process_paysim(
        paysim_path=cfg["paysim_path"],
        seq_save_path=cfg["paysim_sequences"],
        model_save_path=cfg["seq_paysim_weights"],
        pretrain=True,
        device=cfg["device"],
    )
    edges.to_parquet(cfg["paysim_edges"], index=False)


def stage_2_ieee_cis_graft(cfg):
    """Full IEEE-CIS processing pipeline."""
    from grafting.graft_ieee_cis import process_ieee_cis
    from grafting.graft_dgraphfin import validate_graph_cols

    out = cfg["ieee_processed"]
    if Path(out).exists():
        print("[Stage 2] IEEE-CIS processed already exists, loading.")
        df = pd.read_parquet(out)
    else:
        df = process_ieee_cis(
            txn_path=cfg["ieee_txn_path"],
            identity_path=cfg["ieee_identity_path"],
            out_path=out,
        )

    df = validate_graph_cols(df)
    df.to_parquet(cfg["ieee_with_graph"], index=False)
    return df


def stage_3_amiunique_graft(cfg, ieee_df):
    """Graft AmIUnique device features + build Siamese pairs."""
    from grafting.graft_amiunique import process_amiunique

    # if Path(cfg["ieee_enriched"]).exists():
    #     print("[Stage 3] Enriched IEEE-CIS already exists, loading.")
    #     return pd.read_parquet(cfg["ieee_enriched"])

    enriched, _ = process_amiunique(
        amiunique_path=cfg["amiunique_path"],
        ieee_df=ieee_df,
        siamese_pairs_path=cfg["siamese_pairs"],
    )
    enriched.to_parquet(cfg["ieee_enriched"], index=False)
    return enriched


def stage_4_build_graph(cfg, ieee_df):
    """Build PyG HeteroData."""
    from pipeline.build_hetero_graph import build_hetero_graph

    if Path(cfg["hetero_graph"]).exists():
        print("[Stage 4] Hetero graph already exists, skipping.")
        return

    paysim_edges = None
    if Path(cfg["paysim_edges"]).exists():
        paysim_edges = pd.read_parquet(cfg["paysim_edges"])

    build_hetero_graph(ieee_df, paysim_edges, save_path=cfg["hetero_graph"])

from torch.utils.data import Dataset, DataLoader
import torch.nn as nn
import torch.nn.functional as F
from collections import defaultdict

# 2. Dynamic Triplet Dataset
class TripletDeviceDataset(Dataset):
    def __init__(self, user_keys, cat_feats, cont_feats):
        # Pre-convert EVERYTHING to tensors in memory once
        self.cat_feats = torch.tensor(cat_feats, dtype=torch.long)
        self.cont_feats = torch.tensor(cont_feats, dtype=torch.float32)
        self.n_samples = len(user_keys)
        self.user_keys = user_keys
        
        # Map users to their transaction indices
        user_to_idx = defaultdict(list)
        for idx, uk in enumerate(user_keys):
            user_to_idx[uk].append(idx)
            
        # Convert inner lists to numpy arrays for instant O(1) random access
        self.user_to_idx = {k: np.array(v, dtype=np.int32) for k, v in user_to_idx.items()}
        self.users = np.array(list(self.user_to_idx.keys()))
        self.n_users = len(self.users)

    def __len__(self):
        return self.n_samples

    def __getitem__(self, idx):
        user = self.user_keys[idx]
        user_txs = self.user_to_idx[user]
        
        # Positive: Instant O(1) random integer selection
        if len(user_txs) > 1:
            pos_idx = user_txs[np.random.randint(0, len(user_txs))]
        else:
            pos_idx = idx
        
        # Negative: Instant O(1) random integer selection
        neg_user = user
        while neg_user == user:
            neg_user = self.users[np.random.randint(0, self.n_users)]
        
        neg_txs = self.user_to_idx[neg_user]
        neg_idx = neg_txs[np.random.randint(0, len(neg_txs))]
        
        # Just slice the pre-made tensors, no torch.tensor() calls needed
        return (
            self.cat_feats[idx], self.cont_feats[idx],
            self.cat_feats[pos_idx], self.cont_feats[pos_idx],
            self.cat_feats[neg_idx], self.cont_feats[neg_idx],
        )

# 3. Define the Model Structure
class DeviceFingerEncoder(nn.Module):
    def __init__(self, vocab_sizes, cat_embed_dim=16, n_continuous=2, embed_dim=64, dropout=0.1):
        super().__init__()
        self.cat_embeds = nn.ModuleList([
            nn.Embedding(size, cat_embed_dim) for size in vocab_sizes
        ])
        in_dim = len(vocab_sizes) * cat_embed_dim + n_continuous
        self.encoder = nn.Sequential(
            nn.Linear(in_dim, 128),
            nn.LayerNorm(128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, embed_dim),
            nn.LayerNorm(embed_dim),
        )

    def forward(self, cat_feats, cont_feats):
        cat_embs = [emb(cat_feats[:, i]) for i, emb in enumerate(self.cat_embeds)]
        x = torch.cat(cat_embs + [cont_feats], dim=-1)
        return F.normalize(self.encoder(x), dim=-1) # L2 Normalization


def build_ieee_sequences(df: pd.DataFrame, max_len: int = 10):
    """
    Translates IEEE-CIS rows into the PaySim-style sequence format.
    """
    # Map IEEE ProductCD to PaySim-like Type Indices
    # W=PAYMENT, C=TRANSFER, H=CASH_OUT, R=DEBIT, S=CASH_IN (Approximate mapping)
    prod_map = {'W': 1, 'C': 2, 'H': 3, 'R': 4, 'S': 5}
    
    df = df.sort_values(['user_key', 'TransactionDT'])
    
    # Normalize globally for the batch
    df['log_amt_norm'] = np.log1p(df['TransactionAmt']) / np.log1p(df['TransactionAmt'].max())
    
    sequences = []
    # Grouping by user_key to create behavioral snippets
    for _, group in df.groupby('user_key'):
        # Normalize time within the user's own history
        t_min, t_max = group['TransactionDT'].min(), group['TransactionDT'].max()
        t_range = t_max - t_min
        
        user_seq = []
        for _, row in group.tail(max_len).iterrows():
            user_seq.append({
                "type_idx": prod_map.get(row['ProductCD'], 0),
                "log_amount": float(row['log_amt_norm']),
                "step_norm": float((row['TransactionDT'] - t_min) / t_range) if t_range > 0 else 0.0
            })
        sequences.append(user_seq)
        
    return sequences


def stage_5_train_models(cfg, ieee_df):
    """
    Train all neural models A-G in the correct dependency order.
    Returns feature_store DataFrame with all stacking columns.
    """
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score
    from models.models import (
        TabNetEncoder, TabularAutoEncoder,
        HeteroGNN, SyntheticIdentityDetector, ATOChainDetector,
        PlattCalibrator, TABNET_TRAIN_CONFIG, LGBM_TRAIN_CONFIG
    )
    from utils.constants import V_COLS, C_COLS, D_COLS, M_COLS
    from grafting.graft_paysim import BehavioralSequenceTransformer
    from grafting.graft_dgraphfin import get_transfer_weights

    dev = torch.device(cfg["device"])

    # ── Feature matrix for tabular models ──
    tab_feat_cols = (
        [c for c in V_COLS if c in ieee_df.columns] +
        [c for c in C_COLS if c in ieee_df.columns] +
        [c for c in D_COLS if c in ieee_df.columns] +
        [c for c in M_COLS if c in ieee_df.columns] +
        ["TransactionAmt","amt_zscore","delta_t_norm","txn_rank",
         "device_match_ord","device_novelty","device_fraud_rate",
         "graph_risk_score","2nd_degree_fraud_rate","ring_signal"]
    )
    tab_feat_cols = [c for c in tab_feat_cols if c in ieee_df.columns]

    # Apply this to your DataFrame before it becomes the 'X' matrix
    for col in ["TransactionAmt"] + [c for c in ieee_df.columns if c.startswith('C')]:
        if col in ieee_df.columns:
            ieee_df[col] = np.log1p(ieee_df[col])

    X = ieee_df[tab_feat_cols].fillna(0.0).values.astype(np.float32)
    y = ieee_df["isFraud"].values.astype(np.int64)
    N = len(ieee_df)

    feature_store = ieee_df[["TransactionID","user_key","isFraud"]].copy()

    # ── Model A: TabNet ──
    print("\n[Pipeline] Training Model A: TabNet (Supervised Only)...")
    
    BATCH_SIZE = 2048  
    x_all_cpu = torch.tensor(X, dtype=torch.float32) 
    
    tabnet_logits_oof = np.zeros(N)
    tabnet_embeds_oof = np.zeros((N, 128), dtype=np.float32)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    # Calculate positive weight for imbalanced fraud data
    pos_weight_val = (y == 0).sum() / max((y == 1).sum(), 1)
    pos_w = torch.tensor([pos_weight_val], dtype=torch.float32, device=dev)
    criterion = torch.nn.BCEWithLogitsLoss(pos_weight=pos_w)

    for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y)):
        print(f"  [Model A] Fold {fold+1}/5")
        
        # 1. Initialize a fresh model for this fold
        model_f = TabNetEncoder(in_dim=X.shape[1]).to(dev)
        opt = torch.optim.Adam(model_f.parameters(), lr=5e-4)

        # 2. Supervised Training Loop
        model_f.train()
        FINE_TUNE_EPOCHS = 10  # 10 epochs per fold is a good start
        
        for ep in range(FINE_TUNE_EPOCHS):
            # Shuffle training indices
            perm = torch.randperm(len(tr_idx))
            
            for i in range(0, len(tr_idx), BATCH_SIZE):
                b_idx = tr_idx[perm[i : i + BATCH_SIZE]]
                
                # Move batches to GPU
                xb = x_all_cpu[b_idx].to(dev)
                yb = torch.tensor(y[b_idx], dtype=torch.float32, device=dev)
                
                # Forward pass
                out = model_f(xb)
                
                # Squeeze the logit to match yb's shape (1D array)
                loss = criterion(out["logit"].squeeze(-1), yb)
                
                # Backward pass
                opt.zero_grad()
                loss.backward()
                opt.step()

        # 3. Validation / OOF Generation
        model_f.eval()
        with torch.no_grad():
            for i in range(0, len(val_idx), BATCH_SIZE):
                v_idx = val_idx[i:i + BATCH_SIZE]
                xval = x_all_cpu[v_idx].to(dev)
                
                val_out = model_f(xval)
                tabnet_logits_oof[v_idx] = val_out["logit"].cpu().numpy().flatten()
                tabnet_embeds_oof[v_idx] = val_out["embedding"].cpu().numpy()

    feature_store["tabnet_logit"] = tabnet_logits_oof
    print(f"[Model A] OOF AUC: {roc_auc_score(y, tabnet_logits_oof):.4f}")
    
    # Save the weights from the final fold to satisfy any downstream dependencies
    torch.save(model_f.state_dict(), cfg["tabnet_finetuned"])



    ── Model B: Siamese Device Encoder ──
    print("\n[Pipeline] Training Model B: Siamese Device Encoder...")
    (Abbreviated — full training in graft_amiunique.py)
    Load pairs and train; here we just store a placeholder dist_score
    from the device_novelty + device_match_ord combination as proxy
    feature_store["device_dist_score"] = (
        ieee_df["device_novelty"].fillna(0) *
        (2 - ieee_df["device_match_ord"].fillna(0))
    ).values
    
    # ── Model B: Siamese Device Encoder ──
    print("\n[Pipeline] Training Model B: Siamese Device Encoder...")
    
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.utils.data import Dataset, DataLoader
    from sklearn.preprocessing import LabelEncoder
    from collections import defaultdict

    # 1. Prepare Features & Vocabs
    device_cat_cols = ["id_31", "id_33", "DeviceType"] # Subset from your DEVICE_FP_COLS
    device_cont_cols = ["device_match_ord", "device_novelty"]
    
    # Encode categoricals dynamically
    cat_encoders = {}
    cat_vocab_sizes = []
    cat_features_encoded = np.zeros((N, len(device_cat_cols)), dtype=np.int64)
    
    for i, col in enumerate(device_cat_cols):
        # Fill missing before encoding
        ieee_df[col] = ieee_df[col].fillna("UNKNOWN").astype(str)
        le = LabelEncoder()
        cat_features_encoded[:, i] = le.fit_transform(ieee_df[col])
        cat_encoders[col] = le
        cat_vocab_sizes.append(len(le.classes_))
        
    cont_features = ieee_df[device_cont_cols].fillna(0).values.astype(np.float32)


    # 4. Training Loop (OPTIMIZED)
    model_b = DeviceFingerEncoder(vocab_sizes=cat_vocab_sizes).to(dev)
    opt = torch.optim.AdamW(model_b.parameters(), lr=1e-3)
    triplet_loss_fn = nn.TripletMarginLoss(margin=0.5, p=2)

    user_keys = ieee_df["user_key"].values
    dataset = TripletDeviceDataset(user_keys, cat_features_encoded, cont_features)
    
    # BUMP batch_size to 2048 to feed the RTX 3060, add num_workers and pin_memory
    loader = DataLoader(
        dataset, 
        batch_size=2048, 
        shuffle=True, 
        # drop_last=True, 
        num_workers=4,        # Use 4 CPU cores to prep data in background
        pin_memory=True       # Speeds up CPU-to-GPU transfer
    )

    print("  [Model B] Training Triplet Network...")
    model_b.train()
    for ep in range(3):  # 3 epochs is usually enough for triplet networks to converge
        total_loss = 0
        for cat_a, cont_a, cat_p, cont_p, cat_n, cont_n in loader:
            cat_a, cont_a = cat_a.to(dev), cont_a.to(dev)
            cat_p, cont_p = cat_p.to(dev), cont_p.to(dev)
            cat_n, cont_n = cat_n.to(dev), cont_n.to(dev)

            emb_a = model_b(cat_a, cont_a)
            emb_p = model_b(cat_p, cont_p)
            emb_n = model_b(cat_n, cont_n)

            loss = triplet_loss_fn(emb_a, emb_p, emb_n)
            
            opt.zero_grad()
            loss.backward()
            opt.step()
            total_loss += loss.item()
            
        print(f"    Epoch {ep+1}/3, Loss: {total_loss/len(loader):.4f}")

    # 5. Extract Embeddings & Calculate Centroid Distances
    print("  [Model B] Generating Embeddings and Distance Scores...")
    model_b.eval()
    all_embeddings = np.zeros((N, 64), dtype=np.float32)
    
    with torch.no_grad():
        for i in range(0, N, 2048):
            c_cat = torch.tensor(cat_features_encoded[i:i+2048], dtype=torch.long, device=dev)
            c_cont = torch.tensor(cont_features[i:i+2048], dtype=torch.float32, device=dev)
            all_embeddings[i:i+2048] = model_b(c_cat, c_cont).cpu().numpy()

    feature_store["device_embeds"] = list(all_embeddings)
    
    # Calculate distance from known user centroid
    temp_df = pd.DataFrame({"user_key": user_keys})
    temp_df["embeds"] = list(all_embeddings)
    
    # Calculate average embedding per user (Centroid)
    centroids = temp_df.groupby("user_key")["embeds"].apply(
        lambda x: np.mean(np.stack(x), axis=0)
    ).to_dict()

    # Distance = L2 distance between current transaction and user's historical centroid
    dist_scores = [
        np.linalg.norm(emb - centroids[user]) 
        for emb, user in zip(all_embeddings, user_keys)
    ]
    
    feature_store["device_dist_score"] = dist_scores
    print(f"  [Model B] Average Distance from User Centroid: {np.mean(dist_scores):.4f}")


    # ── Model C: Sequence Transformer (fine-tune on IEEE-CIS) ──
    # print("\n[Pipeline] Fine-tuning Model C: Sequence Transformer on IEEE-CIS...")
    # seq_model = BehavioralSequenceTransformer()
    # if Path(cfg["seq_paysim_weights"]).exists():
    #     seq_model.load_state_dict(
    #         torch.load(cfg["seq_paysim_weights"], map_location="cpu")
    #     )
    #     print("[Model C] Loaded PaySim pre-trained weights.")
    # # Anomaly score proxy from D-features (full seq training requires sequence collation)
    # feature_store["seq_anomaly_score"] = (
    #     ieee_df["delta_t_norm"].fillna(0) *
    #     ieee_df["amt_zscore"].clip(-3,3).abs().fillna(0)
    # ).values
    # feature_store["paysim_boost"] = 1.0   # filled by compute_sequence_softboost

    # Inside stage_5_train_models(cfg, ieee_df):
    
    print("\n[Pipeline] Model C: Behavioral Sequence Transformer...")
    
    # 1. Load Pre-trained PaySim Model
    seq_model = BehavioralSequenceTransformer()
    if Path(cfg["seq_paysim_weights"]).exists():
        seq_model.load_state_dict(torch.load(cfg["seq_paysim_weights"], map_location=dev))
        print("  [Model C] PaySim pre-trained weights loaded successfully.")
    
    # 2. Build sequences from current IEEE data
    print("  [Model C] Encoding IEEE-CIS behavioral sequences...")
    ieee_seqs = build_ieee_sequences(ieee_df)
    
    # 3. Apply Soft Label Boosting
    # This finds IEEE users who 'act' like PaySim fraudsters
    # We use the paysim_corpus generated during the grafting stage
    boost_factors = compute_sequence_softboost(
        ieee_sequences=ieee_seqs,
        paysim_corpus=pd.read_parquet(cfg["paysim_corpus_path"]), # Load the corpus you saved
        model=seq_model,
        device=dev,
        sim_threshold=0.85,
        boost_factor=2.0  # Double the anomaly signal for suspicious behavior
    )
    
    # 4. Store the results in the feature_store
    # Map the user-level boost back to the transaction-level dataframe
    user_boost_map = dict(zip(ieee_df['user_key'].unique(), boost_factors))
    feature_store["paysim_boost"] = ieee_df['user_key'].map(user_boost_map).values
    
    # Generate the raw anomaly score (Velocity * Magnitude)
    feature_store["seq_anomaly_score"] = (
        ieee_df["delta_t_norm"].fillna(0) * ieee_df["amt_zscore"].clip(-3,3).abs().fillna(0)
    ).values * feature_store["paysim_boost"]

    print(f"  [Model C] Max Anomaly Score after Boost: {feature_store['seq_anomaly_score'].max():.2f}")

    # ── Model D: Tabular Autoencoder ──
    print("\n[Pipeline] Training Model D: Tabular Autoencoder...")
    legit_mask = y == 0
    ae_model   = TabularAutoEncoder(in_dim=X.shape[1]).to(dev)
    ae_opt     = torch.optim.Adam(ae_model.parameters(), lr=1e-3)
    x_legit    = torch.tensor(X[legit_mask], device=dev)

    if not Path(cfg["tabular_ae"]).exists():
        
        for ep in range(60):
            ae_model.train()
            # Shuffling the entire legit set
            perm = torch.randperm(x_legit.size(0))
            
            for i in range(0, x_legit.size(0), 2048):
                xb = x_legit[perm[i:i+2048]]
                
                # Add slight Gaussian noise to force the AE to learn robust features
                noise = torch.randn_like(xb) * 0.01 
                xb_noisy = xb + noise
                
                out = ae_model(xb_noisy)
                
                # Use SmoothL1Loss (Huber Loss) instead of MSE
                # It's less sensitive to outliers than MSE
                loss = F.smooth_l1_loss(out["reconstruction"], xb)
                
                ae_opt.zero_grad()
                loss.backward()
                ae_opt.step()
        torch.save(ae_model.state_dict(), cfg["tabular_ae"])
    else:
        ae_model.load_state_dict(torch.load(cfg["tabular_ae"], map_location=dev))

    ae_model.eval()
    recon_errors = []
    bs = 2048
    x_all = torch.tensor(X, device=dev)
    for i in range(0, N, bs):
        with torch.no_grad():
            err = ae_model.reconstruction_error(x_all[i:i+bs])
        recon_errors.append(err.cpu().numpy())
    feature_store["recon_error"] = np.concatenate(recon_errors)
    print(f"[Model D] Recon error: mean={feature_store['recon_error'].mean():.4f}")

    # ── Model E: HeteroGNN ──
    print("\n[Pipeline] Training Model E: HeteroGNN...")
    # Placeholder graph embeddings (full training needs PyG + hetero_graph.pt)
    # In production: load graph, run HeteroGNN, extract per-txn embeddings
    feature_store["ring_score"]       = ieee_df["ring_signal"].fillna(0).values
    feature_store["txn_graph_logit"]  = ieee_df["graph_risk_score"].fillna(0).values
    # graph_emb would be [N, 128] — for stacker we use graph_risk_score as proxy scalar

    # ── Model F: Synthetic Identity ──
    print("\n[Pipeline] Training Model F: Synthetic Identity Detector...")
    synth_model = SyntheticIdentityDetector()
    synth_label = ieee_df["synthetic_identity_label"].values
    # Use tabular features as proxy (full model needs graph embeddings from E)
    synth_features = ieee_df[["M_fail_count","M_all_fail","graph_risk_score",
                               "device_novelty","user_txn_count"]].fillna(0).values
    feature_store["synth_id_prob"] = synth_label.astype(np.float32)  # placeholder

    # ── Model G: ATO Chain ──
    print("\n[Pipeline] Training Model G: ATO Chain Detector...")
    ato_label = (
        (ieee_df["isFraud"] == 1) &
        (ieee_df.get("device_match_ord", pd.Series(0, index=ieee_df.index)) == 0) &
        (ieee_df["delta_t"].fillna(9999) < 3600) &
        (ieee_df["txn_rank"] <= 2)
    ).astype(np.float32).values
    feature_store["ato_prob"]     = ato_label  # placeholder
    feature_store["ato_label"]    = ato_label

    # ── Model H: LightGBM Stacker ──
    print("\n[Pipeline] Training Model H: LightGBM Stacker...")
    stacking_cols = [
        "tabnet_logit","device_dist_score","seq_anomaly_score","paysim_boost",
        "recon_error","ring_score","txn_graph_logit","synth_id_prob","ato_prob"
    ]
    X_stack = feature_store[stacking_cols].fillna(0).values
    y_stack = y

    import lightgbm as lgb
    lgbm_oof = np.zeros(N)
    for fold, (tr_idx, val_idx) in enumerate(skf.split(X_stack, y_stack)):
        print(f"  [Model H] Fold {fold+1}/5")
        dtrain = lgb.Dataset(X_stack[tr_idx], y_stack[tr_idx])
        dval   = lgb.Dataset(X_stack[val_idx], y_stack[val_idx])
        params = {
            "objective":        "binary",
            "metric":           "auc",
            "n_estimators":     1000,
            "learning_rate":    0.05,
            "max_depth":        6,
            "num_leaves":       63,
            "min_child_samples": 50,
            "scale_pos_weight": (y_stack == 0).sum() / max((y_stack == 1).sum(), 1),
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq":     1,
            "verbose":          -1,
        }
        booster = lgb.train(
            params, dtrain,
            valid_sets=[dval],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(100)]
        )
        lgbm_oof[val_idx] = booster.predict(X_stack[val_idx])

    lgbm_auc = roc_auc_score(y_stack, lgbm_oof)
    print(f"[Model H] OOF AUC: {lgbm_auc:.4f}")
    feature_store["raw_fraud_score"] = lgbm_oof

    # Save final stacker (retrain on full data)
    dtrain_full = lgb.Dataset(X_stack, y_stack)
    final_stacker = lgb.train(params, dtrain_full)
    final_stacker.save_model(cfg["lgbm_stacker"])

    # ── Model I: Platt Calibration ──
    print("\n[Pipeline] Fitting Model I: Platt Calibrator...")
    cal_idx = int(N * 0.9)
    cal_x   = lgbm_oof[cal_idx:]
    cal_y   = y_stack[cal_idx:]
    calibrator = PlattCalibrator()
    calibrator.fit(cal_x, cal_y)
    torch.save(calibrator.state_dict(), cfg["platt_calibrator"])

    cal_probs = calibrator(torch.tensor(lgbm_oof, dtype=torch.float32)).detach().numpy()
    feature_store["calibrated_prob"] = cal_probs
    feature_store["decision"] = pd.cut(
        cal_probs,
        bins=[-np.inf, 0.30, 0.70, np.inf],
        labels=["approve","mfa","block"]
    )

    print(f"\n[Pipeline] Decision distribution:\n{feature_store['decision'].value_counts()}")
    feature_store.to_parquet(cfg["feature_store"], index=False)
    print(f"\n[Pipeline] Feature store saved → {cfg['feature_store']}")
    return feature_store



def stage_5_train_models(cfg, ieee_df):
    """
    3-PHASE REWRITTEN ARCHITECTURE
    Phase 1: Foundation (Embeddings & Structural Context)
    Phase 2: Sequential Queue (Grafted Tabular + Behavioral)
    Phase 3: Synthesis (Stacking & Calibration)
    """
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score
    from models.models import (
        TabNetEncoder, TabularAutoEncoder, HeteroGNN, 
        DeviceFingerEncoder, BehavioralSequenceTransformer,
        SyntheticIdentityDetector, ATOChainDetector, PlattCalibrator
    )

    dev = torch.device(cfg["device"])
    N = len(ieee_df)
    feature_store = ieee_df[["TransactionID", "user_key", "isFraud"]].copy()

    # ==========================================
    # PHASE 1: FOUNDATION (CONTEXT GENERATION)
    # ==========================================
    print("\n[Phase 1] Extracting Foundation Context...")

    # 1.1 Model E: HeteroGNN (Structural Context)
    # Goal: Get 128D embeddings to "graft" onto tabular data
    hetero_data = torch.load(cfg["hetero_graph"], map_location=dev)
    model_e = HeteroGNN(metadata=hetero_data.metadata()).to(dev)
    model_e.load_state_dict(torch.load(cfg["hetero_gnn"]))
    model_e.eval()
    
    with torch.no_grad():
        logits_e, embeds_e = model_e(hetero_data.x_dict, hetero_data.edge_index_dict)
        # Store logit for stacker, embeddings for grafting
        feature_store["txn_graph_logit"] = logits_e['transaction'][:, 1].cpu().numpy()
        gnn_embeddings = embeds_e['transaction'].cpu().numpy() # [N, 128]

    # 1.2 Model B: Siamese Device Encoder (Identity Context)
    # Goal: Get 64D embeddings to detect device anomalies
    model_b = DeviceFingerEncoder(vocab_sizes=cfg["cat_vocabs"]).to(dev)
    model_b.load_state_dict(torch.load(cfg["siamese_device"]))
    model_b.eval()
    
    cat_b, cont_b = get_device_tensors(ieee_df) # Helper to extract Siamese inputs
    with torch.no_grad():
        identity_embeddings = model_b(cat_b.to(dev), cont_b.to(dev)).cpu().numpy() # [N, 64]
        # Calculate distance to historical user centroid
        feature_store["device_dist_score"] = calculate_centroid_dist(identity_embeddings, ieee_df["user_key"])

    # ==========================================
    # PHASE 2: SEQUENTIAL QUEUE (KNOWLEDGE GRAFTING)
    # ==========================================
    print("\n[Phase 2] Training Specialist Models with Grafted Context...")

    # --- THE GRAFTING STEP ---
    # We combine Raw Tabular Data + Phase 1 GNN Embeddings
    raw_tab_cols = [c for c in (V_COLS + C_COLS + D_COLS) if c in ieee_df.columns]
    X_raw = ieee_df[raw_tab_cols].fillna(-999).values
    X_grafted = np.hstack([X_raw, gnn_embeddings]) # The "Dense Feature Matrix"

    # 2.1 Model A: TabNet (Graph-Aware Tabular)
    # Now TabNet "sees" the graph structure inside its feature matrix
    tabnet_logits = train_tabnet_oof(X_grafted, ieee_df["isFraud"], cfg)
    feature_store["tabnet_logit"] = tabnet_logits

    # 2.2 Model D: Tabular AutoEncoder (Reconstruction Specialist)
    # AE finds anomalies in the combined Tabular+Graph space
    recon_errors = train_ae_and_get_errors(X_grafted, cfg)
    feature_store["recon_error"] = recon_errors

    # 2.3 Model C: Behavioral Transformer (PaySim Fine-tuned)
    ieee_seqs = build_ieee_sequences(ieee_df)
    feature_store["seq_anomaly_score"] = run_transformer_inference(ieee_seqs, cfg)

    # 2.4 Model G: ATO Chain Detector (Hybrid Specialist)
    # Fuses Seq Anomaly (Phase 2) + Identity Embeds (Phase 1)
    X_ato = np.hstack([
        feature_store[["seq_anomaly_score", "txn_graph_logit"]].values,
        identity_embeddings 
    ])
    feature_store["ato_prob"] = train_ato_specialist(X_ato, ieee_df["isFraud"])

    # ==========================================
    # PHASE 3: SYNTHESIS (FINAL STACKING)
    # ==========================================
    print("\n[Phase 3] Final Stacking and Calibration...")

    stacking_cols = [
        "tabnet_logit", "device_dist_score", "seq_anomaly_score", 
        "recon_error", "txn_graph_logit", "ato_prob"
    ]
    
    # Model H: LightGBM Stacker
    lgbm_oof = train_lgbm_stacker(feature_store[stacking_cols], ieee_df["isFraud"])
    feature_store["raw_fraud_score"] = lgbm_oof

    # Model I: Platt Calibration
    calibrator = PlattCalibrator()
    calibrator.fit(lgbm_oof, ieee_df["isFraud"])
    feature_store["calibrated_prob"] = calibrator.predict(lgbm_oof)

    # Final Decisioning Logic
    feature_store["decision"] = pd.cut(
        feature_store["calibrated_prob"],
        bins=[-np.inf, 0.20, 0.80, np.inf],
        labels=["approve", "mfa", "block"]
    )

    feature_store.to_parquet(cfg["feature_store"], index=False)
    return feature_store



# def stage_5_train_models(cfg, ieee_df):
#     """
#     Full Neural Pipeline: Models A-I
#     Handles GNN inference, Tabular AE, TabNet OOF, and LGBM Stacking.
#     """
#     import torch
#     import torch.nn.functional as F
#     import numpy as np
#     import pandas as pd
#     import json
#     from pathlib import Path
#     from sklearn.model_selection import StratifiedKFold
#     from sklearn.metrics import roc_auc_score
#     import lightgbm as lgb

#     # Import custom models from your project structure
#     from models.models import (
#         TabNetEncoder, TabularAutoEncoder, HeteroGNN, 
#         SyntheticIdentityDetector, PlattCalibrator
#     )
#     from utils.constants import V_COLS, C_COLS, D_COLS, M_COLS

#     dev = torch.device(cfg["device"])
#     N = len(ieee_df)
#     feature_store = ieee_df[["TransactionID", "user_key", "isFraud"]].copy()

#     # ── STEP 1: Model E - HeteroGNN Inference ──
#     # We run this first so GNN features can be used by TabNet/AE
#     print("\n[Stage 5] Running Model E: HeteroGNN Inference...")
#     hetero_data = torch.load(cfg["hetero_graph"], map_location=dev)
#     gnn_model = HeteroGNN(
#         metadata=hetero_data.metadata(),
#         hidden_channels=128,
#         out_channels=2
#     ).to(dev)

#     if Path(cfg["gnn_model_path"]).exists():
#         gnn_model.load_state_dict(torch.load(cfg["gnn_model_path"], map_location=dev))
    
#     gnn_model.eval()
#     with torch.no_grad():
#         out, emb_dict = gnn_model(hetero_data.x_dict, hetero_data.edge_index_dict)
#         txn_logits = out['transaction'][:, 1].cpu().numpy()
#         txn_embs = emb_dict['transaction'].cpu().numpy()
    
#     # Map embeddings to columns gnn_0...gnn_127
#     gnn_cols = [f"gnn_{i}" for i in range(128)]
#     gnn_df = pd.DataFrame(txn_embs, columns=gnn_cols, index=ieee_df.index)
#     ieee_df = pd.concat([ieee_df, gnn_df], axis=1)
#     feature_store["txn_graph_logit"] = txn_logits

#     # ── STEP 2: Feature Matrix Prep ──
#     tab_feat_cols = (
#         [c for c in V_COLS + C_COLS + D_COLS + M_COLS if c in ieee_df.columns] +
#         gnn_cols + 
#         ["TransactionAmt", "amt_zscore", "delta_t_norm", "graph_risk_score", "ring_signal"]
#     )
    
#     # Log transform financial skews
#     for col in ["TransactionAmt"] + [c for c in ieee_df.columns if c.startswith('C')]:
#         if col in ieee_df.columns:
#             ieee_df[col] = np.log1p(ieee_df[col])

#     X = ieee_df[tab_feat_cols].fillna(0.0).values.astype(np.float32)
#     y = ieee_df["isFraud"].values.astype(np.int64)

#     # ── STEP 3: Model D - Tabular AutoEncoder ──
#     print("\n[Stage 5] Training Model D: AutoEncoder...")
#     ae_model = TabularAutoEncoder(in_dim=X.shape[1]).to(dev)
#     ae_opt = torch.optim.Adam(ae_model.parameters(), lr=1e-3)
#     x_legit = torch.tensor(X[y == 0], device=dev)

#     for ep in range(30):
#         ae_model.train()
#         perm = torch.randperm(x_legit.size(0))
#         for i in range(0, x_legit.size(0), 2048):
#             xb = x_legit[perm[i:i+2048]]
#             noise = torch.randn_like(xb) * 0.01
#             recon = ae_model(xb + noise)["reconstruction"]
#             loss = F.smooth_l1_loss(recon, xb)
#             ae_opt.zero_grad(); loss.backward(); ae_opt.step()

#     # Generate Recon Error feature
#     ae_model.eval()
#     recon_errs = []
#     for i in range(0, N, 2048):
#         with torch.no_grad():
#             err = ae_model.reconstruction_error(torch.tensor(X[i:i+2048], device=dev))
#             recon_errs.append(err.cpu().numpy())
#     feature_store["recon_error"] = np.concatenate(recon_errs)

#     # ── STEP 4: Model A - TabNet ──
#     print("\n[Stage 5] Training Model A: TabNet (5-Fold OOF)...")
#     tabnet_logits_oof = np.zeros(N)
#     skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

#     for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y)):
#         print(f"  > Fold {fold+1}")
#         model_f = TabNetEncoder(in_dim=X.shape[1]).to(dev)
#         opt = torch.optim.Adam(model_f.parameters(), lr=1e-3)
#         xtr, ytr = torch.tensor(X[tr_idx], device=dev), torch.tensor(y[tr_idx], dtype=torch.float32, device=dev)
        
#         for ep in range(25):
#             model_f.train()
#             perm = torch.randperm(xtr.size(0))
#             for i in range(0, xtr.size(0), 2048):
#                 idx = perm[i:i+2048]
#                 loss = F.binary_cross_entropy_with_logits(model_f(xtr[idx])["logit"].view(-1), ytr[idx])
#                 opt.zero_grad(); loss.backward(); opt.step()
        
#         model_f.eval()
#         with torch.no_grad():
#             tabnet_logits_oof[val_idx] = model_f(torch.tensor(X[val_idx], device=dev))["logit"].cpu().numpy()

#     feature_store["tabnet_logit"] = tabnet_logits_oof

#     print("[Model B] Computing Device Novelty via Siamese Triplet Distance...")
#     device_model = DeviceFingerEncoder().to(dev)
#     device_model.load_state_dict(torch.load(cfg["siamese_device_path"], map_location=dev))
#     device_model.eval()
    
#     # Extract cat/cont features as defined in Model B spec
#     cat_feats = torch.tensor(ieee_df[cfg["device_cat_cols"]].values, dtype=torch.long, device=dev)
#     cont_feats = torch.tensor(ieee_df[["device_match_ord", "device_novelcy"]].values, dtype=torch.float32, device=dev)
    
#     with torch.no_grad():
#         current_embs = device_model(cat_feats, cont_feats)
#         # Assuming cfg["user_centroids"] is a pre-calculated mapping of user_key -> 64-dim mean embedding
#         user_centroids = torch.tensor(np.stack(ieee_df["user_key"].map(cfg["centroid_map"]).values), device=dev)
#         feature_store["device_dist_score"]

#    # ── STEP 3: Model C - Sequence Transformer ──
#     print("[Model C] Running Behavioral Transformer (PaySim Pre-trained)...")
#     seq_model = BehavioralSequenceTransformer().to(dev)
#     seq_model.load_state_dict(torch.load(cfg["seq_transformer_path"], map_location=dev))
#     seq_model.eval()
    
#     # Prepare sequence tensors from the ieee_df list-columns
#     # x: [type_idx, log_amount, step_norm]
#     seq_list = ieee_df["behavior_seq"].tolist() # List of lists of dicts
#     from graft_paysim import _encode_sequences # Helper from your script
#     sx, sm = _encode_sequences(seq_list) 
    
#     with torch.no_grad():
#         seq_out = seq_model(sx.to(dev), sm.to(dev))
#         feature_store["seq_anomaly_score"] = seq_out["logits"].cpu().numpy()
#         seq_embeds = seq_out["embedding"] # [N, 64]

#     # Apply soft-boost from PaySim cluster similarity
#     paysim_corpus = pd.read_parquet(cfg["paysim_seq_corpus"])
#     boost_factors = compute_sequence_softboost(seq_list, paysim_corpus, seq_model, device=cfg["device"])
#     feature_store["seq_anomaly_score"] *= boost_factors

    
#    # ── STEP 6: Models F & G - Specialty Detectors ──
#     print("[Models F & G] Running Synthetic & ATO Detectors...")
#     # Model F: Synthetic Identity (Tabular + GNN)
#     f_cols = ["M_fail_count","M_all_fail","card1","D1","D2","user_txn_count"] # as per spec
#     X_f = torch.tensor(ieee_df[f_cols].fillna(0).values, dtype=torch.float32, device=dev)
#     model_f = SyntheticIdentityDetector(tabular_dim=len(f_cols)).to(dev)
#     model_f.load_state_dict(torch.load(cfg["synth_model_path"]))
    
#     # Model G: ATO Chain (Seq + GNN + Scalars)
#     g_scalars = torch.tensor(ieee_df[["device_match_ord","device_novelty","delta_t_norm",
#                                       "txn_rank","amt_zscore","D1","D2","D3"]].values, dtype=torch.float32, device=dev)
#     model_g = ATOChainDetector().to(dev)
#     model_g.load_state_dict(torch.load(cfg["ato_model_path"]))

#     model_f.eval(); model_g.eval()
#     with torch.no_grad():
#         feature_store["synth_id_prob"] = torch.sigmoid(model_f(X_f, txn_embs_raw)["logit"]).cpu().numpy()
#         feature_store["ato_prob"] = torch.sigmoid(model_g(seq_embeds, txn_embs_raw, g_scalars)["logit"]).cpu().numpy()



#     # ── STEP 6: Model H - LightGBM Stacker ──
#     print("\n[Stage 5] Training Model H: LightGBM Stacker...")
#     stack_cols = [
#         "tabnet_logit", "txn_graph_logit", "recon_error", 
#         "device_dist_score", "seq_anomaly_score", "synth_id_prob", "ato_prob", "ring_score"
#     ]
#     X_stack = feature_store[stack_cols].values
#     lgbm_oof = np.zeros(N)
    
#     for fold, (tr_idx, val_idx) in enumerate(skf.split(X_stack, y)):
#         dtrain = lgb.Dataset(X_stack[tr_idx], y[tr_idx])
#         params = {"objective": "binary", "metric": "auc", "verbosity": -1, "learning_rate": 0.05}
#         bst = lgb.train(params, dtrain, num_boost_round=200)
#         lgbm_oof[val_idx] = bst.predict(X_stack[val_idx])

#     print(f"[Stacker] Final OOF AUC: {roc_auc_score(y, lgbm_oof):.4f}")

#     # ── STEP 7: Model I - Platt Calibration ──
#     print("\n[Stage 5] Fitting Model I: Platt Calibrator...")
#     calibrator = PlattCalibrator()
#     # Fit on a 10% holdout of the OOF scores
#     cal_idx = int(N * 0.9)
#     calibrator.fit(lgbm_oof[cal_idx:], y[cal_idx:])
    
#     final_probs = calibrator(torch.tensor(lgbm_oof, dtype=torch.float32)).detach().numpy()
#     feature_store["calibrated_prob"] = final_probs
#     feature_store["decision"] = pd.cut(final_probs, bins=[-np.inf, 0.3, 0.7, np.inf], labels=["approve", "mfa", "block"])

#     # Save and Return
#     feature_store.to_parquet(cfg["feature_store"], index=False)
#     return feature_store


# ─────────────────────────────────────────────────────────────────────────────
# FINAL STATE REPORTER
# ─────────────────────────────────────────────────────────────────────────────

def report_final_state(cfg, feature_store: pd.DataFrame):
    """Print summary of the fully assembled system."""
    from sklearn.metrics import roc_auc_score, average_precision_score

    y = feature_store["isFraud"].values

    print("\n" + "="*60)
    print("  FINAL SYSTEM STATE")
    print("="*60)

    print("\n── Dataset integration ──")
    print(f"  Total transactions      : {len(feature_store):,}")
    print(f"  Fraud rate              : {y.mean():.4f}")

    print("\n── Model outputs in feature store ──")
    score_cols = [
        "tabnet_logit","device_dist_score","seq_anomaly_score",
        "recon_error","ring_score","txn_graph_logit",
        "synth_id_prob","ato_prob","raw_fraud_score","calibrated_prob"
    ]
    for col in score_cols:
        if col in feature_store.columns:
            try:
                auc = roc_auc_score(y, feature_store[col].fillna(0))
                print(f"  {col:<30} AUC={auc:.4f}")
            except Exception:
                print(f"  {col:<30} (no AUC — constant or binary)")

    print("\n── Saved artifacts ──")
    for key, path in cfg.items():
        if isinstance(path, str) and Path(path).exists():
            size_mb = Path(path).stat().st_size / 1e6
            print(f"  {path:<55} {size_mb:.1f} MB")

    print("\n── Decision distribution ──")
    if "decision" in feature_store.columns:
        print(feature_store["decision"].value_counts().to_string())
    print("="*60)


def stage_5_sequential_pipeline(cfg, ieee_df):
    """
    Full Production Neural Pipeline: Models A through I.
    Architecture: 2-Base Foundation + Sequential Queue + Synthesis.
    All scores are derived from actual neural inference.
    """
    import torch
    import torch.nn.functional as F
    import numpy as np
    import pandas as pd
    from pathlib import Path
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score
    import lightgbm as lgb

    # Custom models based on project architecture
    from models.models import (
        TabNetEncoder, TabularAutoEncoder, HeteroGNN, 
        SyntheticIdentityDetector, ATOChainDetector,
        DeviceFingerEncoder, PlattCalibrator
    )
    from grafting.graft_paysim import BehavioralSequenceTransformer, compute_sequence_softboost, _encode_sequences
    from utils.constants import V_COLS, C_COLS, D_COLS, M_COLS

    dev = torch.device(cfg["device"])
    N = len(ieee_df)
    feature_store = ieee_df[["TransactionID", "user_key", "isFraud"]].copy()
    y = ieee_df["isFraud"].values.astype(np.int64)

    # =========================================================================
    # PHASE 1: THE 2-BASE FOUNDATION
    # Extracts Structural (GNN) and Identity (Siamese) representations first.
    # =========================================================================

    # ── BASE 1: Model E (HeteroGNN) ──
    print("\n[Phase 1] Base 1/2: Running Model E (HeteroGNN)...")
    hetero_data = torch.load(cfg["hetero_graph"], map_location=dev)
    gnn_model = HeteroGNN(metadata=hetero_data.metadata(), hidden_channels=128, out_channels=2).to(dev)
    gnn_model.load_state_dict(torch.load(cfg["gnn_model_path"], map_location=dev))
    gnn_model.eval()
    
    with torch.no_grad():
        out, emb_dict = gnn_model(hetero_data.x_dict, hetero_data.edge_index_dict)
        txn_logits = out['transaction'][:, 1].cpu().numpy()
        txn_embs_raw = emb_dict['transaction']  # Keep on device for Phase 2
        txn_embs_cpu = txn_embs_raw.cpu().numpy()
    
    gnn_cols = [f"gnn_{i}" for i in range(128)]
    ieee_df = pd.concat([ieee_df, pd.DataFrame(txn_embs_cpu, columns=gnn_cols, index=ieee_df.index)], axis=1)
    feature_store["txn_graph_logit"] = txn_logits

    # ── BASE 2: Model B (Siamese Device Encoder) ──
    print("[Phase 1] Base 2/2: Computing Model B (Siamese Identity)...")
    device_model = DeviceFingerEncoder().to(dev)
    device_model.load_state_dict(torch.load(cfg["siamese_device_path"], map_location=dev))
    device_model.eval()
    
    cat_feats = torch.tensor(ieee_df[cfg.get("device_cat_cols", ["id_31", "id_33", "DeviceType", "DeviceInfo", "os_browser"])].fillna(0).values, dtype=torch.long, device=dev)
    cont_feats = torch.tensor(ieee_df[["device_match_ord", "device_novelty"]].fillna(0).values, dtype=torch.float32, device=dev)
    
    with torch.no_grad():
        device_embs = device_model(cat_feats, cont_feats)
        # Calculate distance from known user centroid
        centroid_map = cfg.get("centroid_map", {}) 
        # Fallback to zero-tensor if centroid missing for new users
        user_centroids = torch.tensor(np.stack(ieee_df["user_key"].apply(lambda k: centroid_map.get(k, np.zeros(64))).values), dtype=torch.float32, device=dev)
        feature_store["device_dist_score"] = F.pairwise_distance(device_embs, user_centroids).cpu().numpy()

    # =========================================================================
    # PHASE 2: THE SEQUENTIAL QUEUE
    # Specialized models consume the Base embeddings for richer context.
    # =========================================================================

    # ── QUEUE 1: Model C (Sequence Transformer) ──
    print("\n[Phase 2] Queue 1/4: Running Model C (Behavioral Transformer)...")
    seq_model = BehavioralSequenceTransformer().to(dev)
    seq_model.load_state_dict(torch.load(cfg["seq_transformer_path"], map_location=dev))
    seq_model.eval()
    
    seq_list = ieee_df["behavior_seq"].tolist()
    sx, sm = _encode_sequences(seq_list)
    
    with torch.no_grad():
        seq_out = seq_model(sx.to(dev), sm.to(dev))
        seq_embs = seq_out["embedding"] # [N, 64], used by Model G
        base_anomaly = seq_out["logits"].cpu().numpy()

    # Apply PaySim Soft Boost
    paysim_corpus = pd.read_parquet(cfg["paysim_seq_corpus"])
    boost_factors = compute_sequence_softboost(seq_list, paysim_corpus, seq_model, device=cfg["device"])
    feature_store["seq_anomaly_score"] = base_anomaly * boost_factors

    # ── QUEUE 2: Models F & G (Fusion Detectors) ──
    print("[Phase 2] Queue 2/4: Running Models F & G (Synthetic & ATO Detectors)...")
    # Model F: Tabular + GNN Embedded Context
    f_cols = ["M_fail_count", "M_all_fail", "card1", "D1", "D2", "user_txn_count"]
    X_f = torch.tensor(ieee_df[f_cols].fillna(0).values, dtype=torch.float32, device=dev)
    
    model_f = SyntheticIdentityDetector(tabular_dim=len(f_cols)).to(dev)
    model_f.load_state_dict(torch.load(cfg["synth_model_path"], map_location=dev))
    
    # Model G: Sequence Context + GNN Context + Scalar Temporal info
    g_scalars = torch.tensor(ieee_df[["device_match_ord", "device_novelty", "delta_t_norm", 
                                      "txn_rank", "amt_zscore", "D1", "D2", "D3"]].fillna(0).values, 
                             dtype=torch.float32, device=dev)
    model_g = ATOChainDetector().to(dev)
    model_g.load_state_dict(torch.load(cfg["ato_model_path"], map_location=dev))

    model_f.eval(); model_g.eval()
    with torch.no_grad():
        feature_store["synth_id_prob"] = torch.sigmoid(model_f(X_f, txn_embs_raw)["logit"]).cpu().numpy()
        feature_store["ato_prob"] = torch.sigmoid(model_g(seq_embs, txn_embs_raw, g_scalars)["logit"]).cpu().numpy()

    # ── Feature Prep for D & A ──
    print("[Phase 2] Preparing Dense Feature Matrix for D & A...")
    tab_feat_cols = [c for c in V_COLS + C_COLS + D_COLS + M_COLS if c in ieee_df.columns] + gnn_cols + ["TransactionAmt", "amt_zscore"]
    
    for col in ["TransactionAmt"] + [c for c in ieee_df.columns if c.startswith('C')]:
        if col in ieee_df.columns:
            ieee_df[col] = np.log1p(ieee_df[col].fillna(0))

    X = ieee_df[tab_feat_cols].fillna(0.0).values.astype(np.float32)

    # ── QUEUE 3: Model D (Tabular AutoEncoder) ──
    print("[Phase 2] Queue 3/4: Training Model D (Tabular AutoEncoder)...")
    ae_model = TabularAutoEncoder(in_dim=X.shape[1]).to(dev)
    ae_opt = torch.optim.Adam(ae_model.parameters(), lr=1e-3)
    x_legit = torch.tensor(X[y == 0], device=dev)
    
    for ep in range(25):
        ae_model.train()
        perm = torch.randperm(x_legit.size(0))
        for i in range(0, x_legit.size(0), 2048):
            xb = x_legit[perm[i:i+2048]]
            noise = torch.randn_like(xb) * 0.02
            recon = ae_model(xb + noise)["reconstruction"]
            loss = F.smooth_l1_loss(recon, xb)
            ae_opt.zero_grad(); loss.backward(); ae_opt.step()
            
    ae_model.eval()
    recon_errs = []
    for i in range(0, N, 2048):
        with torch.no_grad():
            recon_errs.append(ae_model.reconstruction_error(torch.tensor(X[i:i+2048], device=dev)).cpu().numpy())
    feature_store["recon_error"] = np.concatenate(recon_errs)

    # ── QUEUE 4: Model A (TabNet 5-Fold OOF) ──
    print("[Phase 2] Queue 4/4: Training Model A (TabNet OOF)...")
    tabnet_logits_oof = np.zeros(N)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    
    for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y)):
        print(f"  > TabNet Fold {fold+1}/5")
        model_a = TabNetEncoder(in_dim=X.shape[1]).to(dev)
        opt = torch.optim.Adam(model_a.parameters(), lr=2e-3)
        xtr = torch.tensor(X[tr_idx], device=dev)
        ytr = torch.tensor(y[tr_idx], dtype=torch.float32, device=dev)
        
        for ep in range(25):
            model_a.train()
            perm = torch.randperm(xtr.size(0))
            for i in range(0, xtr.size(0), 2048):
                idx = perm[i:i+2048]
                loss = F.binary_cross_entropy_with_logits(model_a(xtr[idx])["logit"].view(-1), ytr[idx])
                opt.zero_grad(); loss.backward(); opt.step()
                
        model_a.eval()
        with torch.no_grad():
            tabnet_logits_oof[val_idx] = model_a(torch.tensor(X[val_idx], device=dev))["logit"].cpu().numpy()
            
    feature_store["tabnet_logit"] = tabnet_logits_oof

    # =========================================================================
    # PHASE 3: THE SYNTHESIS
    # Aggregates the signals from all independent specialized models.
    # =========================================================================

    # ── Model H: LightGBM Stacker ──
    print("\n[Phase 3] Synthesis 1/2: Training Model H (LightGBM Meta-Stacker)...")
    stack_cols = [
        "tabnet_logit", "txn_graph_logit", "recon_error", 
        "device_dist_score", "seq_anomaly_score", "synth_id_prob", "ato_prob"
    ]
    X_stack = feature_store[stack_cols].values
    lgbm_oof = np.zeros(N)
    
    for fold, (tr_idx, val_idx) in enumerate(skf.split(X_stack, y)):
        dtrain = lgb.Dataset(X_stack[tr_idx], label=y[tr_idx])
        params = {"objective": "binary", "metric": "auc", "verbosity": -1, "learning_rate": 0.05, "max_depth": 5}
        bst = lgb.train(params, dtrain, num_boost_round=200)
        lgbm_oof[val_idx] = bst.predict(X_stack[val_idx])

    print(f"[Model H] Final Stacker OOF AUC: {roc_auc_score(y, lgbm_oof):.4f}")

    # ── Model I: Platt Calibration ──
    print("[Phase 3] Synthesis 2/2: Fitting Model I (Platt Calibration)...")
    calibrator = PlattCalibrator()
    # Fit on a 10% temporal/holdout ideally, but OOF scores work well here
    cal_idx = int(N * 0.9)
    calibrator.fit(lgbm_oof[cal_idx:], y[cal_idx:])
    
    final_probs = calibrator(torch.tensor(lgbm_oof, dtype=torch.float32)).detach().numpy()
    feature_store["calibrated_prob"] = final_probs
    
    # Final Business Logic Routing
    feature_store["decision"] = pd.cut(
        final_probs, 
        bins=[-np.inf, 0.25, 0.80, np.inf], 
        labels=["approve", "mfa", "block"]
    )

    feature_store.to_parquet(cfg["feature_store"], index=False)
    print("\n[Pipeline Complete] Feature store saved successfully.")
    return feature_store


# ─────────────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_CFG = {
    # Input paths
    "ieee_txn_path":    "data/train_transaction.csv",
    "ieee_identity_path":"data/train_identity.csv",
    "amiunique_path":   "data/amiunique.csv",
    "dgraphfin_dir":    "data/dgraphfin/",
    "paysim_path":      "data/PS_20174392719_1491204439457_log.csv",

    # Processed data
    "ieee_processed":   "data/processed/ieee_cis_processed.parquet",
    "ieee_with_graph":  "data/processed/ieee_cis_with_graph.parquet",
    "ieee_enriched":    "data/processed/ieee_cis_fully_enriched.parquet",
    "siamese_pairs":    "data/processed/siamese_pairs.parquet",
    "paysim_sequences": "data/processed/paysim_sequences.parquet",
    "paysim_edges":     "data/processed/paysim_edges.parquet",
    "hetero_graph":     "data/processed/hetero_graph.pt",
    "feature_store":    "features/feature_store.parquet",

    # Model weights
    "dgraphfin_weights":     "models/dgraphfin_pretrained.pt",
    "seq_paysim_weights":    "models/seq_transformer_paysim_pretrained.pt",
    "seq_ieee_weights":      "models/seq_transformer_ieee_finetuned.pt",
    "tabnet_pretrained":     "models/tabnet_pretrained.pt",
    "tabnet_finetuned":      "models/tabnet_finetuned.pt",
    "siamese_device":        "models/siamese_device.pt",
    "tabular_ae":            "models/tabular_ae.pt",
    "hetero_gnn":            "models/hetero_gnn.pt",
    "synth_id_detector":     "models/synth_id_detector.pt",
    "ato_detector":          "models/ato_chain_detector.pt",
    "lgbm_stacker":          "models/lgbm_stacker.lgb",
    "platt_calibrator":      "models/platt_calibrator.pt",

    # Runtime
    "device": "cuda" if torch.cuda.is_available() else "cpu",
    "dgraphfin_epochs": 100,
}


def run(cfg=None, stages=None):
    cfg    = cfg or DEFAULT_CFG
    print("cuda" if torch.cuda.is_available() else "cpu")
    stages = stages or ["all"]

    # Create output dirs
    for d in ["data/processed","models","features"]:
        Path(d).mkdir(parents=True, exist_ok=True)

    if "all" in stages or "0" in stages:
        stage_0_dgraphfin_pretrain(cfg)
    if "all" in stages or "1" in stages:
        stage_1_paysim_pretrain(cfg)

    ieee_df = None
    if "all" in stages or "2" in stages:
        ieee_df = stage_2_ieee_cis_graft(cfg)
    if ieee_df is None and cfg["ieee_with_graph"] and Path(cfg["ieee_with_graph"]).exists():
        ieee_df = pd.read_parquet(cfg["ieee_with_graph"])

    if "all" in stages or "3" in stages:
        ieee_df = stage_3_amiunique_graft(cfg, ieee_df)
    else:
        if Path(cfg["ieee_enriched"]).exists():
            ieee_df = pd.read_parquet(cfg["ieee_enriched"])

    if "all" in stages or "4" in stages:
        stage_4_build_graph(cfg, ieee_df)

    if "all" in stages or "5" in stages:
        feature_store = stage_5_train_models(cfg, ieee_df)
        report_final_state(cfg, feature_store)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stages", nargs="+", default=["all"],
                        help="Which stages to run: 0 1 2 3 4 5 or 'all'")
    args = parser.parse_args()
    run(stages=args.stages)
