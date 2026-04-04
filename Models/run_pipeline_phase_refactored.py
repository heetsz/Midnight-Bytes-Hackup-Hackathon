"""
run_pipeline_phase_refactored.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4-PHASE FRAUD DETECTION ARCHITECTURE
═══════════════════════════════════════════════════════════════════════════════

PHASE 1 — FOUNDATION (Dense Compression)
  Models A & B transform raw sparse/categorical data into dense vectors.
  ├─ Model A (TabNet):  Raw tabular features        → 128D transaction embedding
  └─ Model B (Siamese): Device fingerprints        → 64D identity embedding

PHASE 2 — CONTEXT (Relational + Temporal)
  Models E & C interpret the Phase 1 embeddings within relationship structures.
  ├─ Model E (HeteroGNN):    Transaction graph       → 128D augmented embedding + ring_scores
  └─ Model C (SeqTransformer): User behavior sequence → 64D seq embedding + anomaly_score

PHASE 3 — SPECIALISTS (Pattern Detection)
  Models F, G, D look for specific fraud signatures using Phase 1 + Phase 2 context.
  ├─ Model F (SyntheticID):   Is this a fake identity? (graph + tabular)
  ├─ Model G (ATO Chain):     New device → high velocity → fraud? (seq + graph + time)
  └─ Model D (Autoencoder):   Is this transaction novel/anomalous? (tabular space)

PHASE 4 — SYNTHESIS (Decision Making)
  Final two models reconcile specialist opinions and calibrate to actionable probability.
  ├─ Model H (LightGBM Stacker): Arbitrate conflicts between all specialists
  └─ Model I (Platt Calibrator):  Convert ranking → true probability + reason codes

EXECUTION: python run_pipeline_phase_refactored.py [PHASE_1|PHASE_2|PHASE_3|PHASE_4|ALL]
INFERENCE: python run_pipeline_phase_refactored.py INFERENCE <transaction_json>

═══════════════════════════════════════════════════════════════════════════════
"""

import os
import sys
import json
import pickle
import hashlib
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split, StratifiedKFold
from sklearn.metrics import roc_auc_score
import joblib  # For saving sklearn models like IsotonicRegression

from sklearn.metrics import (
    roc_auc_score, accuracy_score, precision_score, 
    recall_score, f1_score, mean_squared_error, brier_score_loss
)

# Fallback for PyG if not installed for Phase 2
from torch_geometric.data import Data
from torch_geometric.nn import SAGEConv

import logging
logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# Import local modules
try:
    from utils.constants import (
        V_COLS, C_COLS, D_COLS, M_COLS, CARD_COLS, DEVICE_FP_COLS,
        GNN_EMBED_DIM, SEQUENCE_PAD, DEVICE_EMBED_DIM,
        make_user_key, make_device_fp_hash
    )
    from models.models import (
        TabNetEncoder, DeviceFingerEncoder, TabularAutoEncoder,
        HeteroGNN, SyntheticIdentityDetector, ATOChainDetector,
        PlattCalibrator, HGTLayer
    )
    from grafting.graft_paysim import BehavioralSequenceTransformer
except ImportError as e:
    logger.warning(f"Import error (may be acceptable in demo): {e}")


# ═══════════════════════════════════════════════════════════════════════════
# CONFIGURATION & PATHS
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class PipelineConfig:
    """Central configuration for all phases and models."""
    
    # Data paths
    data_root: Path = Path("data")
    model_root: Path = Path("models")
    feature_root: Path = Path("features")
    processed_root: Path = Path("data/processed")
    
    # Input files
    ieee_txn_path: str = "data/train_transaction.csv"
    ieee_id_path: str = "data/train_identity.csv"
    amiunique_path: str = "data/amiunique.csv"
    dgraphfin_dir: str = "data/dgraphfin/"
    paysim_path: str = "data/PS_20174392719_1491204439457_log.csv"
    
    # Model checkpoints
    tabnet_pretrained: str = "models/tabnet_pretrained.pt"
    tabnet_finetuned: str = "models/tabnet_finetuned.pt"
    siamese_device: str = "models/siamese_device.pt"
    seq_paysim_pretrained: str = "models/seq_transformer_paysim_pretrained.pt"
    seq_ieee_finetuned: str = "models/seq_transformer_ieee_finetuned.pt"
    tabular_ae: str = "models/tabular_ae.pt"
    hetero_gnn: str = "models/hetero_gnn.pt"
    dgraphfin_weights: str = "models/dgraphfin_pretrained.pt"
    synth_id_detector: str = "models/synth_id_detector.pt"
    ato_detector: str = "models/ato_chain_detector.pt"
    lgbm_stacker: str = "models/lgbm_stacker.lgb"
    platt_calibrator: str = "models/platt_calibrator.pt"
    
    # Feature store outputs
    ieee_processed: str = "data/processed/ieee_cis_processed.parquet"
    ieee_with_graph: str = "data/processed/ieee_cis_with_graph.parquet"
    ieee_enriched: str = "data/processed/ieee_cis_fully_enriched.parquet"
    hetero_graph: str = "data/processed/hetero_graph.pt"
    feature_store: str = "features/feature_store.parquet"
    
    # Compute
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
    seed: int = 42
    n_workers: int = 4
    
    def ensure_dirs(self):
        """Create all required directories."""
        for path in [self.model_root, self.feature_root, self.processed_root]:
            Path(path).mkdir(parents=True, exist_ok=True)

import shap
import torch
import numpy as np

class PyTorchShapWrapper(torch.nn.Module):
    """Wraps PyTorch models to return exactly what SHAP needs to explain."""
    def __init__(self, model, mode="logit"):
        super().__init__()
        self.model = model
        self.mode = mode

    def forward(self, x):
        if self.mode == "tabnet":
            # Extract just the logit from the TabNet dictionary
            return self.model(x)["logit"]
        elif self.mode == "dae":
            # Explain the Reconstruction Error (MSE)
            recon = self.model(x)
            # Return MSE per row
            return torch.mean((recon - x)**2, dim=1, keepdim=True)
        elif self.mode == "mlp":
            # Standard sequential MLP
            return self.model(x)

class UnifiedFraudExplainer:
    def __init__(self, models_dict, background_data, feature_names):
        """
        models_dict: dict of trained models {"tabnet": model, "dae": model, "lgbm": model, ...}
        background_data: dict of background tensors for DeepExplainer {"raw_features": tensor, "stack_features": array}
        feature_names: dict of column lists {"raw": [...], "stack": [...], "weak": [...]}
        """
        self.feature_names = feature_names
        self.explainers = {}
        
        # 1. TabNet Explainer (PyTorch)
        tabnet_wrapped = PyTorchShapWrapper(models_dict["tabnet"], mode="tabnet").eval()
        self.explainers["tabnet"] = shap.DeepExplainer(
            tabnet_wrapped, background_data["raw_features"]
        )
        
        # 2. DAE Explainer (PyTorch)
        dae_wrapped = PyTorchShapWrapper(models_dict["dae"], mode="dae").eval()
        self.explainers["dae"] = shap.DeepExplainer(
            dae_wrapped, background_data["raw_features"]
        )
        
        # 3. Weak Supervisor Explainers (PyTorch MLPs)
        synth_wrapped = PyTorchShapWrapper(models_dict["synth_id"], mode="mlp").eval()
        self.explainers["synth_id"] = shap.DeepExplainer(
            synth_wrapped, background_data["weak_features"]
        )
        
        # 4. LightGBM Stacker Explainer (Tree)
        self.explainers["lgbm"] = shap.TreeExplainer(models_dict["lgbm"])

    def _get_top_reasons(self, shap_values, feat_names, prefix="", threshold=0.05, max_reasons=2):
        """Helper to extract top positive drivers from shap values."""
        # Handle different SHAP output shapes based on model type
        vals = shap_values[1] if isinstance(shap_values, list) else shap_values
        vals = vals[0] if len(vals.shape) > 1 else vals # Ensure 1D array for single row
        
        top_indices = np.argsort(vals)[::-1]
        reasons = []
        for idx in top_indices:
            val = vals[idx]
            if val > threshold and len(reasons) < max_reasons:
                reasons.append(f"{prefix}{feat_names[idx]} (Impact: +{val:.3f})")
        return reasons

    def explain_transaction(self, raw_x, weak_x, stack_x, device):
        """Generates a combined list of reasons from multiple models."""
        combined_reasons = []
        
        # Step 1: Ask the Stacker what models are driving the fraud score
        stack_shap = self.explainers["lgbm"].shap_values(stack_x)
        stack_vals = stack_shap[1][0] if isinstance(stack_shap, list) else stack_shap[0]
        
        # Find which sub-models contributed heavily
        top_stack_idx = np.argsort(stack_vals)[::-1]
        
        for idx in top_stack_idx:
            model_driver = self.feature_names["stack"][idx]
            impact = stack_vals[idx]
            
            if impact < 0.1: # Skip if the stacker doesn't care much about this
                continue
                
            # Step 2: Dynamically query the sub-models that triggered the stacker
            raw_tensor = torch.tensor(raw_x, dtype=torch.float32).to(device)
            weak_tensor = torch.tensor(weak_x, dtype=torch.float32).to(device)
            
            if model_driver == "tabnet_logit":
                t_shap = self.explainers["tabnet"].shap_values(raw_tensor)
                combined_reasons.extend(self._get_top_reasons(t_shap, self.feature_names["raw"], "[TabNet] Anomalous "))
                
            elif model_driver == "recon_error":
                d_shap = self.explainers["dae"].shap_values(raw_tensor)
                combined_reasons.extend(self._get_top_reasons(d_shap, self.feature_names["raw"], "[DAE] Reconstruction failed on "))
                
            elif model_driver == "synth_id_prob":
                s_shap = self.explainers["synth_id"].shap_values(weak_tensor)
                combined_reasons.extend(self._get_top_reasons(s_shap, self.feature_names["weak"], "[SynthID] Flagged by "))
                
            elif model_driver == "seq_anomaly_score":
                combined_reasons.append(f"[Sequence] Abnormal transaction frequency/timing detected.")
                
            elif model_driver == "txn_graph_logit":
                combined_reasons.append(f"[Graph] Connected to known risky IP/Device clusters.")

        if not combined_reasons:
            combined_reasons.append("Low risk profile across all models.")
            
        return list(set(combined_reasons)) # Deduplicate

from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from sklearn.preprocessing import LabelEncoder

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: FOUNDATION MODELS
# ═══════════════════════════════════════════════════════════════════════════
{
    "tabnet": tabnet_model,
    "dae": dae_model,
    "synth_id": synth_model,
    "lgbm": lgbm_model,
}

tabnet_model = TabNetEncoder(in_dim=X.shape[1], embed_dim=128).to(self.device)
model.load_state_dict(torch.load(self.cfg.tabnet_finetuned))

dae_model = nn.Sequential(
    nn.Dropout(0.2),
    nn.Linear(X.shape[1], 256), nn.LeakyReLU(),
    nn.Linear(256, 128), nn.LeakyReLU(),
    nn.Linear(128, 64), nn.LeakyReLU(), 
    nn.Linear(64, 128), nn.LeakyReLU(),
    nn.Linear(128, 256), nn.LeakyReLU(),
    nn.Linear(256, X.shape[1])
).to(self.device)
dae_model.load_state_dict(torch.load(self.cfg.tabular_ae))




class Phase1Foundation:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = torch.device(cfg.device)
        
    def load_ieee_cis_merged(self) -> pd.DataFrame:
        logger.info("Loading IEEE-CIS data...")
        txn = pd.read_csv(self.cfg.ieee_txn_path)
        identity = pd.read_csv(self.cfg.ieee_id_path)
        df = txn.merge(identity, on="TransactionID", how="left")
        logger.info(f"  Loaded {len(df):,} transactions")
        return df

    def train_tabnet(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 1] Training Model A: TabNet with Early Stopping...")
        
        feat_cols = [c for c in (V_COLS + C_COLS + D_COLS) if c in ieee_df.columns]
        X = ieee_df[feat_cols].fillna(0).values.astype(np.float32)
        y = ieee_df["isFraud"].values.astype(np.float32)

        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.1, stratify=y, random_state=42)
        
        train_dataset = TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train))
        val_dataset = TensorDataset(torch.from_numpy(X_val), torch.from_numpy(y_val))

        class_sample_count = np.array([len(np.where(y_train == t)[0]) for t in np.unique(y_train)])
        weight = 1. / class_sample_count
        samples_weight = torch.from_numpy(np.array([weight[int(t)] for t in y_train]))
        sampler = WeightedRandomSampler(samples_weight, len(samples_weight))

        batch_size = 4096
        train_loader = DataLoader(train_dataset, batch_size=batch_size, sampler=sampler)
        val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

        model = TabNetEncoder(in_dim=X.shape[1], embed_dim=128).to(self.device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='max', patience=3, factor=0.5)
        criterion = nn.BCEWithLogitsLoss()

        epochs = 1
        # epochs = 50
        best_val_auc = 0.0
        patience_counter = 0
        early_stopping_patience = 7

        for epoch in range(epochs):
            model.train()
            train_loss = 0.0
            for data, target in train_loader:
                data, target = data.to(self.device), target.to(self.device)
                optimizer.zero_grad()
                out = model(data)
                
                loss = criterion(out["logit"].squeeze(), target) 
                if "sparse_loss" in out:
                    loss += 1e-4 * out["sparse_loss"]
                    
                loss.backward()
                optimizer.step()
                train_loss += loss.item()

            model.eval()
            val_preds, val_targets = [], []
            with torch.no_grad():
                for data, target in val_loader:
                    out = model(data.to(self.device))
                    val_preds.extend(torch.sigmoid(out["logit"]).cpu().numpy())
                    val_targets.extend(target.numpy())
            
            val_auc = roc_auc_score(val_targets, val_preds)
            scheduler.step(val_auc)
            
            logger.info(f"  Epoch {epoch+1}: Train Loss={train_loss/len(train_loader):.4f} | Val AUC={val_auc:.4f}")

            if val_auc > best_val_auc:
                best_val_auc = val_auc
                patience_counter = 0
                torch.save(model.state_dict(), self.cfg.tabnet_finetuned)
            else:
                patience_counter += 1
                if patience_counter >= early_stopping_patience:
                    logger.info("  Early stopping triggered!")
                    break

        # Generate Full Stats on Validation Set
        val_preds_bin = (np.array(val_preds) > 0.5).astype(int)
        logger.info("\n  === TabNet Validation Stats ===")
        logger.info(f"  AUC:       {best_val_auc:.4f}")
        logger.info(f"  Accuracy:  {accuracy_score(val_targets, val_preds_bin):.4f}")
        logger.info(f"  Precision: {precision_score(val_targets, val_preds_bin, zero_division=0):.4f}")
        logger.info(f"  Recall:    {recall_score(val_targets, val_preds_bin, zero_division=0):.4f}")
        logger.info(f"  F1 Score:  {f1_score(val_targets, val_preds_bin, zero_division=0):.4f}\n")

        model.load_state_dict(torch.load(self.cfg.tabnet_finetuned))
        model.eval()
        
        all_embeddings, all_logits = [], []
        full_loader = DataLoader(TensorDataset(torch.from_numpy(X)), batch_size=batch_size, shuffle=False)
        with torch.no_grad():
            for data in full_loader:
                out = model(data[0].to(self.device))
                all_embeddings.append(out["embedding"].cpu().numpy())
                all_logits.append(out["logit"].cpu().numpy())

        ieee_df["tabnet_embedding"] = list(np.vstack(all_embeddings))
        ieee_df["tabnet_logit"] = np.concatenate(all_logits)
        
        return model, ieee_df

    def train_siamese_device(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 1] Training Model B: Siamese Device Encoder (Triplet Loss)...")
        ieee_df = ieee_df.copy()
        
        device_cols = ["id_31", "id_33", "DeviceType", "DeviceInfo"]
        for col in device_cols:
            if col not in ieee_df.columns: ieee_df[col] = "unknown"
            ieee_df[col] = ieee_df[col].astype(str).fillna("unknown")

        cat_data, vocab_sizes = [], []
        for col in device_cols:
            encoded = LabelEncoder().fit_transform(ieee_df[col])
            cat_data.append(encoded.reshape(-1, 1))
            vocab_size = int(encoded.max()) + 1
            vocab_sizes.append(vocab_size) 

        cat_feats = torch.tensor(np.hstack(cat_data), dtype=torch.long, device=self.device)
        
        cont_cols = ["device_match_ord", "device_novelty"]
        for col in cont_cols:
            if col not in ieee_df.columns: ieee_df[col] = 0.0
            ieee_df[col] = pd.to_numeric(ieee_df[col], errors='coerce').fillna(0)
            
        cont_feats = torch.tensor(ieee_df[cont_cols].values, dtype=torch.float32, device=self.device)

        model = DeviceFingerEncoder(
            cat_dims=vocab_sizes,
            cat_embed_dim=16,
            n_continuous=cont_feats.shape[1],
            embed_dim=64
        ).to(self.device)
        
        optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
        triplet_loss = nn.TripletMarginLoss(margin=1.0, p=2)
        
        model.train()
        batch_size = 2048
        epochs = 1
        # epochs = 5
        dataset = TensorDataset(cat_feats, cont_feats)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        final_loss = 0.0
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_cat, batch_cont in loader:
                optimizer.zero_grad()
                anchor_emb = model(batch_cat, batch_cont)
                
                pos_emb = torch.roll(anchor_emb, shifts=1, dims=0)
                neg_emb = torch.roll(anchor_emb, shifts=len(anchor_emb)//2, dims=0)
                
                loss = triplet_loss(anchor_emb, pos_emb, neg_emb)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            
            final_loss = epoch_loss/len(loader)
            logger.info(f"  Epoch {epoch+1}/{epochs}: Triplet Loss = {final_loss:.4f}")

        logger.info("\n  === Siamese Device Stats ===")
        logger.info(f"  Final Triplet Loss (Separation Proxy): {final_loss:.4f}\n")

        torch.save(model.state_dict(), self.cfg.siamese_device)
        
        model.eval()
        with torch.no_grad():
            device_emb = model(cat_feats, cont_feats)
        ieee_df["device_embedding"] = list(device_emb.cpu().numpy())
        
        return model, ieee_df

    def run(self, ieee_df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        if ieee_df is None: ieee_df = self.load_ieee_cis_merged()
        model_a, ieee_df = self.train_tabnet(ieee_df)
        model_b, ieee_df = self.train_siamese_device(ieee_df)
        return ieee_df

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 2: CONTEXT TRAINING
# ═══════════════════════════════════════════════════════════════════════════

class Phase2Context:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = torch.device(cfg.device)

    def train_sequence_transformer(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 2] Training Model C: Sequence Transformer...")
        ieee_df = ieee_df.sort_values(by=["card1", "TransactionDT"]).reset_index(drop=True)
        ieee_df['delta_t'] = ieee_df.groupby('card1')['TransactionDT'].diff().fillna(0)
        
        seq_inputs = np.vstack(ieee_df["tabnet_embedding"].values)
        seq_tensor = torch.tensor(seq_inputs, dtype=torch.float32, device=self.device)
        
        transformer_layer = nn.TransformerEncoderLayer(d_model=128, nhead=4, batch_first=True).to(self.device)
        transformer = nn.TransformerEncoder(transformer_layer, num_layers=2).to(self.device)
        optimizer = torch.optim.Adam(transformer.parameters(), lr=1e-3)
        
        transformer.train()
        # epochs = 3
        epochs = 1
        seq_chunks = torch.split(seq_tensor, 1024) 
        
        final_loss = 0.0
        for epoch in range(epochs):
            epoch_loss = 0.0
            for chunk in seq_chunks:
                if chunk.shape[0] < 2: continue
                optimizer.zero_grad()
                out = transformer(chunk.unsqueeze(0)) 
                
                pred = out[:, :-1, :]
                target = chunk.unsqueeze(0)[:, 1:, :]
                loss = F.mse_loss(pred, target)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            
            final_loss = epoch_loss/len(seq_chunks)
            logger.info(f"  Epoch {epoch+1}/{epochs}: Seq Loss = {final_loss:.4f}")

        logger.info("\n  === Sequence Transformer Stats ===")
        logger.info(f"  Final Shifted-MSE Loss: {final_loss:.4f}\n")

        torch.save(transformer.state_dict(), self.cfg.seq_ieee_finetuned)

        transformer.eval()
        seq_anomaly_scores = []
        with torch.no_grad():
            for chunk in seq_chunks:
                out = transformer(chunk.unsqueeze(0))
                err = torch.mean((out.squeeze(0) - chunk)**2, dim=1).cpu().numpy()
                seq_anomaly_scores.extend(err)

        ieee_df["seq_embedding"] = list(seq_tensor.cpu().numpy())
        ieee_df["seq_anomaly_score"] = seq_anomaly_scores
        ieee_df["paysim_boost"] = ieee_df["seq_anomaly_score"] * 1.5 
        
        return ieee_df
        
    def train_hetero_gnn(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 2] Training Model E: Graph Neural Network...")
        if "tabnet_embedding" not in ieee_df.columns:
            return ieee_df

        try:
            df_graph = ieee_df.head(50000).copy() 
            ip_to_nodes = df_graph.groupby('addr1').groups
            src, dst = [], []
            for ip, nodes in ip_to_nodes.items():
                nodes = list(nodes)
                if len(nodes) > 1 and len(nodes) < 100: 
                    for i in range(len(nodes)-1):
                        src.append(nodes[i])
                        dst.append(nodes[i+1])
            
            edge_index = torch.tensor([src + dst, dst + src], dtype=torch.long).to(self.device)
            x = torch.tensor(np.vstack(df_graph["tabnet_embedding"].values), dtype=torch.float32).to(self.device)
            y = torch.tensor(df_graph["isFraud"].values, dtype=torch.float32).to(self.device)

            class SAGENet(nn.Module):
                def __init__(self, in_ch, out_ch):
                    super().__init__()
                    self.conv1 = SAGEConv(in_ch, 64)
                    self.conv2 = SAGEConv(64, out_ch)
                def forward(self, x, edge_index):
                    x = F.relu(self.conv1(x, edge_index))
                    return self.conv2(x, edge_index)

            model = SAGENet(128, 1).to(self.device)
            optimizer = torch.optim.Adam(model.parameters(), lr=0.01)
            criterion = nn.BCEWithLogitsLoss()

            model.train()
            for epoch in range(10):
                optimizer.zero_grad()
                out = model(x, edge_index).squeeze()
                loss = criterion(out, y)
                loss.backward()
                optimizer.step()
                if (epoch+1) % 2 == 0:
                    logger.info(f"  Epoch {epoch+1}/10: Graph Loss = {loss.item():.4f}")

            torch.save(model.state_dict(), self.cfg.hetero_gnn)

            model.eval()
            with torch.no_grad():
                graph_logits = model(x, edge_index).squeeze().cpu().numpy()
            
            # GNN Eval Stats
            gnn_preds = torch.sigmoid(torch.tensor(graph_logits)).numpy()
            gnn_preds_bin = (gnn_preds > 0.5).astype(int)
            y_np = y.cpu().numpy()
            
            logger.info("\n  === GNN (Transductive) Stats ===")
            logger.info(f"  AUC:       {roc_auc_score(y_np, gnn_preds):.4f}")
            logger.info(f"  Accuracy:  {accuracy_score(y_np, gnn_preds_bin):.4f}")
            logger.info(f"  Precision: {precision_score(y_np, gnn_preds_bin, zero_division=0):.4f}")
            logger.info(f"  Recall:    {recall_score(y_np, gnn_preds_bin, zero_division=0):.4f}\n")
            
            full_logits = np.zeros(len(ieee_df))
            full_logits[:len(df_graph)] = graph_logits
            ieee_df["txn_graph_logit"] = full_logits
            
        except NameError:
            logger.warning("  PyG not installed. Skipping Graph Training.")
            ieee_df["txn_graph_logit"] = ieee_df["tabnet_logit"]

        return ieee_df

    def run(self, ieee_df: pd.DataFrame) -> pd.DataFrame:
        ieee_df = self.train_sequence_transformer(ieee_df)
        ieee_df = self.train_hetero_gnn(ieee_df)
        return ieee_df

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: SPECIALISTS TRAINING
# ═══════════════════════════════════════════════════════════════════════════

class Phase3Specialists:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = torch.device(cfg.device)

    def train_tabular_autoencoder(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 3] Training Model D: Denoising Autoencoder (DAE)...")
        
        legit_df = ieee_df[ieee_df["isFraud"] == 0]
        feat_cols = [c for c in (V_COLS + C_COLS + D_COLS) if c in ieee_df.columns]
        X = legit_df[feat_cols].fillna(0).values.astype(np.float32)
        
        model = nn.Sequential(
            nn.Dropout(0.2),
            nn.Linear(X.shape[1], 256), nn.LeakyReLU(),
            nn.Linear(256, 128), nn.LeakyReLU(),
            nn.Linear(128, 64), nn.LeakyReLU(), 
            nn.Linear(64, 128), nn.LeakyReLU(),
            nn.Linear(128, 256), nn.LeakyReLU(),
            nn.Linear(256, X.shape[1])
        ).to(self.device)
        
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
        loader = DataLoader(TensorDataset(torch.from_numpy(X)), batch_size=8192, shuffle=True)

        model.train()
        epochs = 1
        # epochs = 30
        for epoch in range(epochs):
            epoch_loss = 0.0
            for (batch_x,) in loader:
                batch_x = batch_x.to(self.device)
                optimizer.zero_grad()
                recon = model(batch_x)
                loss = F.mse_loss(recon, batch_x)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
            if (epoch+1) % 5 == 0:
                logger.info(f"  Epoch {epoch+1}/{epochs}: DAE Loss={epoch_loss/len(loader):.4f}")

        torch.save(model.state_dict(), self.cfg.tabular_ae)

        model.eval()
        X_full = ieee_df[feat_cols].fillna(0).values.astype(np.float32)
        X_full_tensor = torch.tensor(X_full, device=self.device)
        
        with torch.no_grad():
            recon_full = model(X_full_tensor)
            recon_err = torch.mean((recon_full - X_full_tensor)**2, dim=1).cpu().numpy()
            
        logger.info("\n  === DAE Stats ===")
        logger.info(f"  Overall Reconstruction RMSE: {np.sqrt(np.mean(recon_err)):.4f}\n")

        ieee_df["recon_error"] = recon_err
        return ieee_df

    def _train_weak_supervisor(self, ieee_df: pd.DataFrame, target_col: str, model_path: str, model_name: str):
        features = ieee_df[["TransactionAmt", "recon_error", "tabnet_logit"]].fillna(0).values
        labels = ieee_df[target_col].values
        
        model = nn.Sequential(
            nn.Linear(3, 32), nn.ReLU(),
            nn.Linear(32, 1)
        ).to(self.device)
        
        optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
        criterion = nn.BCEWithLogitsLoss()
        X_t = torch.tensor(features, dtype=torch.float32, device=self.device)
        y_t = torch.tensor(labels, dtype=torch.float32, device=self.device).unsqueeze(1)
        
        model.train()
        for epoch in range(10):
            optimizer.zero_grad()
            loss = criterion(model(X_t), y_t)
            loss.backward()
            optimizer.step()

        torch.save(model.state_dict(), model_path)
        
        model.eval()
        with torch.no_grad():
            probs = torch.sigmoid(model(X_t)).cpu().numpy().flatten()
        ieee_df[f"{model_name}_prob"] = probs
        
        # Weak Supervision Stats
        preds_bin = (probs > 0.5).astype(int)
        logger.info(f"\n  === {model_name.upper()} Weak Supervisor Stats ===")
        logger.info(f"  Heuristic Fit AUC: {roc_auc_score(labels, probs):.4f}")
        logger.info(f"  Accuracy:          {accuracy_score(labels, preds_bin):.4f}")
        logger.info(f"  Precision:         {precision_score(labels, preds_bin, zero_division=0):.4f}")
        logger.info(f"  Recall:            {recall_score(labels, preds_bin, zero_division=0):.4f}\n")

        return ieee_df

    def train_synthetic_id_detector(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 3] Training Model F: Synthetic ID (Weak Supervision)...")
        ieee_df["weak_synth"] = ((ieee_df["P_emaildomain"].isna()) & (ieee_df["recon_error"] > np.percentile(ieee_df["recon_error"], 90))).astype(float)
        return self._train_weak_supervisor(ieee_df, "weak_synth", self.cfg.synth_id_detector, "synth_id")

    def train_ato_chain_detector(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 3] Training Model G: ATO Chain (Weak Supervision)...")
        if "delta_t" not in ieee_df.columns: ieee_df["delta_t"] = 9999
        ieee_df["weak_ato"] = ((ieee_df["delta_t"] < 60) & (ieee_df["TransactionAmt"] > 500)).astype(float)
        return self._train_weak_supervisor(ieee_df, "weak_ato", self.cfg.ato_detector, "ato")

    def run(self, ieee_df: pd.DataFrame) -> pd.DataFrame:
        ieee_df = self.train_tabular_autoencoder(ieee_df)
        ieee_df = self.train_synthetic_id_detector(ieee_df)
        ieee_df = self.train_ato_chain_detector(ieee_df)
        return ieee_df

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: SYNTHESIS TRAINING
# ═══════════════════════════════════════════════════════════════════════════

class Phase4Synthesis:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = torch.device(cfg.device)

    def train_lgbm_stacker(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 4] Training Model H: LightGBM Stacker...")
        import lightgbm as lgb
        
        stack_cols = [
            "tabnet_logit", "seq_anomaly_score", "paysim_boost",
            "recon_error", "txn_graph_logit", "synth_id_prob", "ato_prob"
        ]
        
        for col in stack_cols:
            if col not in ieee_df.columns: ieee_df[col] = 0
                
        X_stack = ieee_df[stack_cols].fillna(0).values
        y = ieee_df["isFraud"].values
        
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
        lgbm_oof = np.zeros(len(X_stack))
        
        params = {
            "objective": "binary",
            "metric": "auc",
            "learning_rate": 0.02,
            "max_depth": 6,
            "feature_fraction": 0.8, 
            "n_estimators": 1500,    
            "verbosity": -1,
            "random_state": 42
        }
        
        for fold, (tr_idx, val_idx) in enumerate(skf.split(X_stack, y)):
            logger.info(f"  Fold {fold+1}/5...")
            bst = lgb.LGBMClassifier(**params)
            
            bst.fit(
                X_stack[tr_idx], y[tr_idx],
                eval_set=[(X_stack[val_idx], y[val_idx])],
                callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
            )
            
            lgbm_oof[val_idx] = bst.predict_proba(X_stack[val_idx])[:, 1]

        logger.info("  Training final stacker on full data...")
        final_bst = lgb.LGBMClassifier(**params)
        final_bst.fit(X_stack, y)
        
        joblib.dump(final_bst, self.cfg.lgbm_stacker)

        # Comprehensive LGBM Stats
        oof_bin = (lgbm_oof > 0.5).astype(int)
        logger.info("\n  === LightGBM Stacker (OOF) Stats ===")
        logger.info(f"  AUC:       {roc_auc_score(y, lgbm_oof):.4f}")
        logger.info(f"  Accuracy:  {accuracy_score(y, oof_bin):.4f}")
        logger.info(f"  Precision: {precision_score(y, oof_bin, zero_division=0):.4f}")
        logger.info(f"  Recall:    {recall_score(y, oof_bin, zero_division=0):.4f}")
        logger.info(f"  F1 Score:  {f1_score(y, oof_bin, zero_division=0):.4f}\n")

        ieee_df["raw_fraud_score"] = lgbm_oof
        return ieee_df
        
    def train_isotonic_calibrator(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 4] Training Model I: Isotonic Calibrator...")
        from sklearn.isotonic import IsotonicRegression
        
        cal_idx = int(len(ieee_df) * 0.9)
        cal_scores = ieee_df["raw_fraud_score"].iloc[cal_idx:].values
        cal_labels = ieee_df["isFraud"].iloc[cal_idx:].values
        
        iso_reg = IsotonicRegression(out_of_bounds='clip')
        iso_reg.fit(cal_scores, cal_labels)
        
        joblib.dump(iso_reg, self.cfg.platt_calibrator)
        
        cal_probs = iso_reg.predict(ieee_df["raw_fraud_score"].values)
        
        # Calibration Stats
        pre_brier = brier_score_loss(cal_labels, cal_scores)
        post_brier = brier_score_loss(cal_labels, iso_reg.predict(cal_scores))
        
        logger.info("\n  === Isotonic Calibrator Stats ===")
        logger.info(f"  Brier Score Pre-Calibration:  {pre_brier:.4f}")
        logger.info(f"  Brier Score Post-Calibration: {post_brier:.4f}\n")

        ieee_df["calibrated_prob"] = cal_probs
        ieee_df["decision"] = pd.cut(
            cal_probs,
            bins=[-np.inf, 0.30, 0.70, np.inf],
            labels=["approve", "mfa", "block"]
        )
        logger.info(f"  ✓ Decisions generated: {ieee_df['decision'].value_counts().to_dict()}")
        return ieee_df

    def run(self, ieee_df: pd.DataFrame) -> pd.DataFrame:
        ieee_df = self.train_lgbm_stacker(ieee_df)
        ieee_df = self.train_isotonic_calibrator(ieee_df)
        return ieee_df


# ═══════════════════════════════════════════════════════════════════════════
# INFERENCE: SINGLE ROW PREDICTION
# ═══════════════════════════════════════════════════════════════════════════

class FraudDetectionInference:
    """Inference engine for single transactions."""
    
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        self.device = torch.device(cfg.device)
        self.models = {}
        self.calibrator = None
        self._load_all_models()
    
    def _load_all_models(self):
        """Load all trained models."""
        logger.info("Loading models for inference...")
        
        try:
            # Load TabNet
            if Path(self.cfg.tabnet_finetuned).exists():
                self.models["tabnet"] = TabNetEncoder(in_dim=368, embed_dim=128).to(self.device)
                self.models["tabnet"].load_state_dict(
                    torch.load(self.cfg.tabnet_finetuned, map_location=self.device)
                )
                self.models["tabnet"].eval()
                logger.info("  ✓ TabNet loaded")
        except Exception as e:
            logger.warning(f"  ⚠ Failed to load TabNet: {e}")
        
        try:
            # Load Platt Calibrator
            if Path(self.cfg.platt_calibrator).exists():
                self.calibrator = PlattCalibrator()
                self.calibrator.load_state_dict(
                    torch.load(self.cfg.platt_calibrator, map_location=self.device)
                )
                self.calibrator.eval()
                logger.info("  ✓ Platt Calibrator loaded")
        except Exception as e:
            logger.warning(f"  ⚠ Failed to load Calibrator: {e}")
    
    def preprocess_transaction(self, txn: Dict[str, Any]) -> np.ndarray:
        """
        Convert a single transaction dict to feature vector.
        
        Args:
            txn: Dictionary with keys like 'TransactionAmt', 'card1', 'V1', etc.
        
        Returns:
            Feature vector [1, n_features]
        """
        # Build feature array
        feat_cols = (
            [c for c in V_COLS if c in txn] +
            [c for c in C_COLS if c in txn] +
            [c for c in D_COLS if c in txn]
        )
        
        X = np.array([txn.get(c, 0) for c in feat_cols], dtype=np.float32).reshape(1, -1)
        return X
    
    def infer_single_row(
        self,
        txn: Dict[str, Any],
        include_reasons: bool = True
    ) -> Dict[str, Any]:
        """Predict fraud probability + decision for a single transaction."""
        
        result = {
            "TransactionID": txn.get("TransactionID", "UNKNOWN"),
            "timestamp": datetime.now().isoformat(),
        }
        
        try:
            # Phase 1: Foundation embeddings
            logger.debug("  Computing Phase 1 (Foundation) embeddings...")
            X_feat = self.preprocess_transaction(txn)
            
            # FIX 1: Add the missing batch dimension [N] -> [1, N]
            if isinstance(X_feat, np.ndarray) and X_feat.ndim == 1:
                X_feat = np.expand_dims(X_feat, axis=0)
                
            raw_score = np.random.rand()  # Placeholder
            if "tabnet" in self.models:
                self.models["tabnet"].eval()
                X_tensor = torch.tensor(X_feat, dtype=torch.float32, device=self.device)
                with torch.no_grad():
                    tabnet_out = self.models["tabnet"](X_tensor)
                    # FIX 2: Safely extract the float using .item()
                    raw_score = torch.sigmoid(tabnet_out["logit"]).item()
            
            result["raw_fraud_score"] = float(raw_score)
            
            # Phase 4: Calibration
            logger.debug("  Applying Phase 4 (Calibration)...")
            if hasattr(self, "calibrator") and self.calibrator:
                with torch.no_grad():
                    # 🔴 FIX 3: Ensure calibrator input has batch dim [[raw_score]]
                    self.calibrator.eval()
                    cal_input = torch.tensor([[raw_score]], dtype=torch.float32, device=self.device)
                    cal_prob = self.calibrator(cal_input).item()
            else:
                cal_prob = raw_score
            
            result["calibrated_prob"] = float(cal_prob)
            
            # Decision
            if cal_prob < 0.30:
                decision = "approve"
            elif cal_prob < 0.70:
                decision = "mfa"
            else:
                decision = "block"
            
            result["decision"] = decision
                     
            return result
        
        except Exception as e:
            logger.error(f"Inference error on txn {txn.get('TransactionID')}: {e}", exc_info=True)
            result["error"] = str(e)
            return result


# ═══════════════════════════════════════════════════════════════════════════
# TESTING & VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

def test_full_pipeline(ieee_df: pd.DataFrame, cfg: PipelineConfig):
    """Evaluate full pipeline on a test set."""
    logger.info("\n" + "="*80)
    logger.info("PIPELINE EVALUATION")
    logger.info("="*80)
    if "tabnet_logit" in ieee_df.columns and "raw_fraud_score" not in ieee_df.columns:
        logger.info("Generating 'raw_fraud_score' column from TabNet logits...")
        # Sigmoid: 1 / (1 + exp(-x))
        ieee_df["raw_fraud_score"] = 1 / (1 + np.exp(-ieee_df["tabnet_logit"].values))
    
    # 1. Generate calibrated probabilities (If you don't have a batch calibrator yet, mirror the raw score)
    if "calibrated_prob" not in ieee_df.columns:
        logger.info("Generating 'calibrated_prob' column...")
        ieee_df["calibrated_prob"] = ieee_df["raw_fraud_score"]
        
    # 2. Vectorize the decision logic for the entire dataframe
    if "decision" not in ieee_df.columns:
        logger.info("Generating 'decision' column based on thresholds...")
        
        # Using numpy.select is insanely fast for this
        conditions = [
            ieee_df["calibrated_prob"] < 0.30,
            ieee_df["calibrated_prob"] < 0.70
        ]
        choices = ["approve", "mfa"]
        
        # If < 0.3, approve. If < 0.7, mfa. Otherwise, default to block.
        ieee_df["decision"] = np.select(conditions, choices, default="block")
    
    try:
        from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
        y_true = ieee_df["isFraud"].values
        y_pred_raw = ieee_df["raw_fraud_score"].values
        y_pred_cal = ieee_df["calibrated_prob"].values
        
        auc = roc_auc_score(y_true, y_pred_raw)
        ap = average_precision_score(y_true, y_pred_raw)
        f1_threshold = f1_score(y_true, (y_pred_cal > 0.5).astype(int))
        
        logger.info(f"\nMetrics:")
        logger.info(f"  ROC-AUC:           {auc:.4f}")
        logger.info(f"  Average Precision: {ap:.4f}")
        logger.info(f"  F1 @ 0.5 threshold: {f1_threshold:.4f}")
        
        logger.info(f"\nDecision Distribution:")
        logger.info(ieee_df["decision"].value_counts())
        
        logger.info(f"\nFraud Rate by Decision:")
        for decision in ["approve", "mfa", "block"]:
            mask = ieee_df["decision"] == decision
            if mask.sum() > 0:
                fraud_rate = ieee_df[mask]["isFraud"].mean()
                logger.info(f"  {decision:10s}: {fraud_rate*100:5.2f}% ({mask.sum():,} txns)")
    
    except ImportError:
        logger.warning("sklearn not available, skipping detailed metrics")

import pandas as pd
import numpy as np
from datetime import datetime
import uuid

def get_random_live_transaction(ieee_df: pd.DataFrame) -> dict:
    """
    Pulls a random row from the dataframe and updates ID, Date, and Amount
    to simulate a real-time transaction based on current conditions.
    """
    # 1. Sample exactly one random row from your test set
    random_row = ieee_df.sample(n=1).iloc[0].copy()
    
    # 2. Convert the Pandas Series to a standard Python dictionary
    txn_dict = random_row.to_dict()
    
    # 3. Clean up NaNs: Neural networks hate missing values! 
    # Convert any pandas NaN/NaT into 0.0 to prevent PyTorch crashes.
    txn_dict = {k: (0.0 if pd.isna(v) else v) for k, v in txn_dict.items()}
    
    # 4. Override fields for "Current Conditions"
    # Setting time to current time: April 4, 2026, 9:32 AM IST
    current_time = datetime.now() 
    
    # Generate a unique, realistic-looking Transaction ID
    txn_dict["TransactionID"] = f"TXN_LIVE_{uuid.uuid4().hex[:8].upper()}"
    
    # Update timestamp fields
    txn_dict["timestamp"] = current_time.isoformat()
    # If your model uses TransactionDT as a numeric feature, we update it:
    txn_dict["TransactionDT"] = int(current_time.timestamp()) 
    
    # Randomize the transaction amount between $5 and $2500 for testing variety
    txn_dict["TransactionAmt"] = round(np.random.uniform(5.0, 2500.0), 2)
    
    return txn_dict


def demo_single_row_inference(ieee_df: pd.DataFrame, device, models_dict: dict):
    """Demonstrate inference on a single synthetic transaction."""
    logger.info("\n" + "="*80)
    logger.info("SINGLE-ROW INFERENCE DEMO")
    logger.info("="*80)

    # 2. Define raw features for TabNet/DAE
    feat_cols = [c for c in (V_COLS + C_COLS + D_COLS) if c in ieee_df.columns]
    X_raw = ieee_df[feat_cols].fillna(0).values.astype(np.float32)
    
    # 3. Define and safely check the weak features
    weak_cols = ["TransactionAmt", "recon_error", "tabnet_logit"]
    for col in weak_cols:
        if col not in ieee_df.columns:
            ieee_df[col] = 0.0
    X_weak = ieee_df[weak_cols].fillna(0).values.astype(np.float32)
    
    # Safely check stack cols too
    stack_cols = [
        "tabnet_logit", "seq_anomaly_score", "paysim_boost",
        "recon_error", "txn_graph_logit", "synth_id_prob", "ato_prob"
    ]
    for col in stack_cols:
        if col not in ieee_df.columns:
            ieee_df[col] = 0.0
            
    y = ieee_df["isFraud"].values.astype(np.float32)

    # 4. Split datasets 
    X_train, X_val, y_train, y_val = train_test_split(
        X_raw, y, test_size=0.1, stratify=y, random_state=42
    )
    X_weak_train, X_weak_val, _, _ = train_test_split(
        X_weak, y, test_size=0.1, stratify=y, random_state=42
    )

    # 5. Create the background tensors for SHAP 
    background_raw = torch.tensor(X_train[:100], dtype=torch.float32).to(device)
    background_weak = torch.tensor(X_weak_train[:100], dtype=torch.float32).to(device)

    bg_data = {
        "raw_features": background_raw,
        "weak_features": background_weak
    }

    feat_names = {
        "raw": [c for c in (V_COLS + C_COLS + D_COLS)],
        "stack": stack_cols,
        "weak": weak_cols
    }
    
    # 6. Initialize explainer using the passed-in models_dict
    unified_explainer = UnifiedFraudExplainer(
        models_dict=models_dict,
        background_data=bg_data,
        feature_names=feat_names
    )
    
    cfg = PipelineConfig()
    inferrer = FraudDetectionInference(cfg)
    
    # 7. Fixed Loop Logic: Just test on 3 random transactions
    for _ in range(3): 
        # Get one live transaction (assuming it returns a dict or pd.Series)
        live_txn = get_random_live_transaction(ieee_df)
        
        # Convert it to a 1-row DataFrame so we can extract features cleanly for SHAP
        if isinstance(live_txn, dict):
            row = pd.DataFrame([live_txn])
        else:
            row = live_txn.to_frame().T

        logger.info(f"\n--- Transaction {row['TransactionID'].values[0]} ---")
        
        # Run inference
        result = inferrer.infer_single_row(live_txn, include_reasons=True)
        
        # Run Explainer (using .to_frame().T for stack_x to avoid LGBM feature name warnings)
        raw_x = row[feat_names["raw"]].fillna(0).values.reshape(1, -1)
        weak_x = row[feat_names["weak"]].fillna(0).values.reshape(1, -1)
        stack_x = row[feat_names["stack"]].fillna(0).to_frame().T

        reasons = unified_explainer.explain_transaction(raw_x, weak_x, stack_x, device)

        # Print results safely
        if "error" in result:
            logger.error(f"Inference Failed: {result['error']}")
        else:
            logger.info(f"  Amount:           ${row['TransactionAmt'].values[0]:,.2f}")
            logger.info(f"  Raw Score:        {result.get('raw_fraud_score', 0):.4f}")
            logger.info(f"  Calibrated Prob:  {result.get('calibrated_prob', 0):.4f}")
            logger.info(f"  Decision:         {result.get('decision', 'UNKNOWN').upper()}")
            logger.info(f"   Reasons:")
            for r in reasons[:4]: 
                logger.info(f"     * {r}")

# ═══════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

def main():
    """Main pipeline orchestrator."""
    cfg = PipelineConfig()
    cfg.ensure_dirs()
    
    # Parse command line
    if len(sys.argv) > 1:
        phase = sys.argv[1].upper()
    else:
        phase = "ALL"
    
    logger.info("="*80)
    logger.info("FRAUD DETECTION PIPELINE — 4-PHASE ARCHITECTURE")
    logger.info("="*80)
    logger.info(f"Phase: {phase}")
    logger.info(f"Device: {cfg.device}")
    logger.info("")
    
    if phase in ["PHASE_1", "ALL"]:
        logger.info("\n>>> Starting PHASE 1: FOUNDATION (Models A & B)\n")
        phase1 = Phase1Foundation(cfg)
        ieee_df = phase1.run()
    else:
        # Load from checkpoint
        try:
            ieee_df = pd.read_parquet(cfg.ieee_enriched)
            logger.info(f"✓ Loaded checkpoint: {cfg.ieee_enriched}")
        except:
            logger.warning("Could not load checkpoint, running Phase 1...")
            phase1 = Phase1Foundation(cfg)
            ieee_df = phase1.run()
    
    if phase in ["PHASE_2", "ALL"]:
        logger.info("\n>>> Starting PHASE 2: CONTEXT (Models E & C)\n")
        phase2 = Phase2Context(cfg)
        ieee_df = phase2.run(ieee_df)
    
    if phase in ["PHASE_3", "ALL"]:
        logger.info("\n>>> Starting PHASE 3: SPECIALISTS (Models F, G & D)\n")
        phase3 = Phase3Specialists(cfg)
        ieee_df = phase3.run(ieee_df)
    
    if phase in ["PHASE_4", "ALL"]:
        logger.info("\n>>> Starting PHASE 4: SYNTHESIS (Models H & I)\n")
        phase4 = Phase4Synthesis(cfg)
        ieee_df = phase4.run(ieee_df)
    
    # Save feature store
    Path(cfg.feature_root).mkdir(parents=True, exist_ok=True)
    
    # Remove numpy arrays for parquet compatibility
    for col in ieee_df.columns:
        if isinstance(ieee_df[col].iloc[0], np.ndarray):
            ieee_df = ieee_df.drop(col, axis=1)
    
    ieee_df.to_parquet(cfg.feature_store, index=False)
    logger.info(f"\n✓ Feature store saved: {cfg.feature_store}")
    
    # Evaluation
    test_full_pipeline(ieee_df, cfg)

    mode
    
    # Demo inference
    demo_single_row_inference(ieee_df, device=cfg.device, models_dict=model_dict)
    
    logger.info("\n" + "="*80)
    logger.info("PIPELINE COMPLETE")
    logger.info("="*80)


if __name__ == "__main__":
    main()
