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

# Import production-grade model training functions
try:
    from PRODUCTION_MODELS_UPGRADE import (
        FocalLoss, TripletLoss, ContrastiveLoss,
        train_tabnet_with_oof,
        train_siamese_device_with_hard_negatives,
        train_autoencoder_on_legitimate_only,
        train_lgbm_stacker_oof,
        EarlyStopping, CosineAnnealingWarmup,
        calculate_class_weight,
    )
except ImportError:
    logger.warning("PRODUCTION_MODELS_UPGRADE not found, will use simplified training")

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
    lgbm_stacker: str = "models/lgbm_stacker.pt"
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

class TabNetShapWrapper(nn.Module):
    def __init__(self, model):
        super().__init__()
        self.model = model
    def forward(self, x):
        # SHAP expects a single Tensor output, not the {logit: x, embedding: y} dict
        out = self.model(x)
        return out["logit"] 

class UnifiedFraudExplainer:
    def __init__(self, models_dict, background_data, feature_names):
        """Initialize SHAP explainers for all available models."""
        self.feature_names = feature_names
        self.explainers = {}
        self.models_dict = models_dict
        
        logger.info("  Initializing SHAP explainers...")
        
        if not models_dict:
            logger.error("    ❌ models_dict is empty!")
            return

        # --- 1. TabNet Explainer ---
        if "tabnet" in models_dict and models_dict["tabnet"] is not None:
            try:
                # FIX: Access from background_data dictionary
                bg = background_data.get("raw_features")
                if bg is not None:
                    # Use the wrapper to ensure we only get the 'logit' output
                    tabnet_wrapped = PyTorchShapWrapper(models_dict["tabnet"], mode="tabnet").eval()
                    self.explainers["tabnet"] = shap.DeepExplainer(tabnet_wrapped, bg)
                    logger.info("    ✓ TabNet SHAP initialized")
            except Exception as e:
                logger.warning(f"    ✗ TabNet SHAP failed: {type(e).__name__}: {str(e)[:50]}")

        # --- 2. Autoencoder Explainer ---
        if "autoencoder" in models_dict and models_dict["autoencoder"] is not None:
            try:
                bg = background_data.get("raw_features")
                if bg is not None:
                    ae_wrapped = PyTorchShapWrapper(models_dict["autoencoder"], mode="dae").eval()
                    self.explainers["autoencoder"] = shap.DeepExplainer(ae_wrapped, bg)
                    logger.info("    ✓ Autoencoder SHAP initialized")
            except Exception as e:
                logger.warning(f"    ✗ Autoencoder SHAP failed: {type(e).__name__}: {str(e)[:50]}")

        # --- 3. SyntheticID Explainer ---
        if "synth_id" in models_dict and models_dict["synth_id"] is not None:
            try:
                bg_weak = background_data.get("weak_features")
                if bg_weak is not None:
                    synth_wrapped = PyTorchShapWrapper(models_dict["synth_id"], mode="mlp").eval()
                    self.explainers["synth_id"] = shap.DeepExplainer(synth_wrapped, bg_weak)
                    logger.info("    ✓ SyntheticID SHAP initialized")
            except Exception as e:
                logger.warning(f"    ✗ SyntheticID SHAP failed: {type(e).__name__}: {str(e)[:50]}")

        # --- 4. LightGBM Stacker Explainer ---
        if "lgbm_stacker" in models_dict and models_dict["lgbm_stacker"] is not None:
            try:
                # TreeExplainer is best for GBMs
                self.explainers["lgbm_stacker"] = shap.TreeExplainer(models_dict["lgbm_stacker"])
                logger.info("    ✓ LightGBM Stacker SHAP initialized")
            except Exception as e:
                logger.warning(f"    ✗ LightGBM Stacker SHAP failed: {type(e).__name__}: {str(e)[:50]}")
        
        logger.info(f"    Summary: {len(self.explainers)} SHAP explainers ready.")

    def _get_top_reasons(self, shap_values, feature_names, prefix="", top_n=3):
        """Standardizes SHAP output and extracts top features."""
        try:
            # Handle list output (standard for binary classification)
            if isinstance(shap_values, list):
                # Class 1 is usually 'Fraud'
                vals = shap_values[1] if len(shap_values) > 1 else shap_values[0]
            else:
                vals = shap_values
            
            # Convert to numpy and flatten
            if torch.is_tensor(vals):
                vals = vals.detach().cpu().numpy()
            vals = vals.flatten()

            # Find top impactful indices
            top_indices = np.argsort(np.abs(vals))[-top_n:][::-1]
            
            reasons = []
            for idx in top_indices:
                # Lowered threshold to 1e-7 to capture small movements in low scores
                if abs(vals[idx]) > 1e-7: 
                    name = feature_names[idx]
                    direction = "↑" if vals[idx] > 0 else "↓"
                    reasons.append(f"{prefix}{name} ({direction})")
            return reasons
        except Exception as e:
            return [f"{prefix}Error analyzing: {str(e)[:30]}"]

    def explain_transaction(self, raw_x, weak_x, stack_x, device):
        """Orchestrates explanations across all active explainers."""
        combined_reasons = []
        
        # Helper to convert inputs to torch tensors safely
        def to_tensor(x):
            if torch.is_tensor(x): return x.to(device).float()
            return torch.tensor(x, dtype=torch.float32, device=device)

        # 1. TabNet
        if "tabnet" in self.explainers:
            try:
                tabnet_shap = self.explainers["tabnet"].shap_values(to_tensor(raw_x))
                combined_reasons.extend(self._get_top_reasons(tabnet_shap, self.feature_names["raw"], "[TabNet] "))
            except: pass

        # 2. Autoencoder
        if "autoencoder" in self.explainers:
            try:
                ae_shap = self.explainers["autoencoder"].shap_values(to_tensor(raw_x))
                combined_reasons.extend(self._get_top_reasons(ae_shap, self.feature_names["raw"], "[AE] "))
            except: pass

        # 3. SyntheticID
        if "synth_id" in self.explainers:
            try:
                synth_shap = self.explainers["synth_id"].shap_values(to_tensor(weak_x))
                combined_reasons.extend(self._get_top_reasons(synth_shap, self.feature_names["weak"], "[SynID] "))
            except: pass

        # 4. Stacker (Highest priority/Usually most informative)
        if "lgbm_stacker" in self.explainers:
            try:
                s_input = stack_x.values if hasattr(stack_x, 'values') else stack_x
                if s_input.ndim == 1: s_input = s_input.reshape(1, -1)
                lgbm_shap = self.explainers["lgbm_stacker"].shap_values(s_input)
                combined_reasons.extend(self._get_top_reasons(lgbm_shap, self.feature_names["stack"], "[Stacker] "))
            except: pass

        # Deduplicate and return
        if not combined_reasons:
            return ["No clear reasons available"]
        
        # Filter out duplicates while keeping order
        seen = set()
        return [x for x in combined_reasons if not (x in seen or seen.add(x))]


from torch.utils.data import DataLoader, TensorDataset, WeightedRandomSampler
from sklearn.preprocessing import LabelEncoder

# ═══════════════════════════════════════════════════════════════════════════
# GLOBAL MODELS REGISTRY (populated during pipeline execution)
# ═══════════════════════════════════════════════════════════════════════════

all_models = {}

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 1: FOUNDATION MODELS
# ═══════════════════════════════════════════════════════════════════════════ 

class Phase1Foundation:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = torch.device(cfg.device)
        self.scaler = torch.amp.GradScaler("cuda") # For Mixed Precision

    def load_ieee_cis_merged(self) -> pd.DataFrame:
        # Optimization: Use parquet if possible, otherwise use specific dtypes
        logger.info("Loading IEEE-CIS data...")
        # If you haven't yet, convert your CSVs to Parquet once for 10x faster loading
        txn = pd.read_csv(self.cfg.ieee_txn_path)
        identity = pd.read_csv(self.cfg.ieee_id_path)
        df = txn.merge(identity, on="TransactionID", how="left")
        
        # DOWNCAST: Reduce memory footprint immediately
        for col in df.select_dtypes('float64').columns:
            df[col] = pd.to_numeric(df[col], downcast='float')
        
        logger.info(f"  Loaded {len(df):,} transactions")
        return df

    def train_tabnet(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 1] Training Model A: TabNet (Fast Implementation)...")
        
        feat_cols = [c for c in (V_COLS + C_COLS + D_COLS) if c in ieee_df.columns]
        
        # Optimization: Use values directly to avoid DF overhead
        X = ieee_df[feat_cols].values.astype(np.float32)
        np.nan_to_num(X, copy=False, nan=0.0) # Faster than df.fillna(0)
        y = ieee_df["isFraud"].values.astype(np.float32)

        # 1. Split Data
        X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.1, stratify=y, random_state=42)

        # 2. Optimized DataLoader (num_workers > 0 and pin_memory=True)
        train_loader = DataLoader(
            TensorDataset(torch.from_numpy(X_train), torch.from_numpy(y_train)),
            batch_size=1024, # Increased batch size for speed
            shuffle=True,
            num_workers=4,
            pin_memory=True
        )

        model = TabNetEncoder(in_dim=X.shape[1], embed_dim=128).to(self.device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=2e-3)
        criterion = nn.BCEWithLogitsLoss()

        # 3. Training Loop with Mixed Precision
        model.train()
        for epoch in range(5):
            for data, target in train_loader:
                data, target = data.to(self.device, non_blocking=True), target.to(self.device, non_blocking=True)
                
                optimizer.zero_grad(set_to_none=True) # Faster than zero_grad()
                
                with torch.amp.autocast("cuda"): # Half-precision forward pass
                    out = model(data)
                    loss = criterion(out["logit"], target)
                
                self.scaler.scale(loss).backward()
                self.scaler.step(optimizer)
                self.scaler.update()

        # 4. Fast Inference (No Gradients, No Dropout)
        model.eval()
        all_logits, all_embeddings = [], []
        # ... (Inference code) ...
        with torch.no_grad(), torch.amp.autocast('cuda'): # Fixed warning
            inf_loader = DataLoader(TensorDataset(torch.from_numpy(X)), batch_size=2048)
            for (batch,) in inf_loader:
                out = model(batch.to(self.device))
                all_logits.append(out["logit"].cpu().numpy())
                all_embeddings.append(out["embedding"].cpu().numpy())

        # Group assignment to minimize fragmentation
        new_cols = {
            "tabnet_logit": np.concatenate(all_logits),
            "tabnet_embedding": list(np.vstack(all_embeddings))
        }
        ieee_df = pd.concat([ieee_df, pd.DataFrame(new_cols, index=ieee_df.index)], axis=1)
        
        # FINAL DE-FRAGMENTATION
        ieee_df = ieee_df.copy() 
        
        torch.save(model.state_dict(), self.cfg.tabnet_finetuned)

        model.eval()
        val_logits = []
        with torch.no_grad(), torch.amp.autocast('cuda'):
            val_loader = DataLoader(TensorDataset(torch.from_numpy(X_val)), batch_size=2048)
            for (batch,) in val_loader:
                out = model(batch.to(self.device))
                val_logits.append(out["logit"].cpu().numpy())
        
        val_probs = torch.sigmoid(torch.from_numpy(np.concatenate(val_logits))).numpy()
        auc_score = roc_auc_score(y_val, val_probs)
        
        logger.info(f"  [METRICS] TabNet Validation AUC: {auc_score:.4f}")

        return model, ieee_df

    def train_siamese_device(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 1] Training Model B: Siamese Device Encoder (Fixed for Collapse)...")
        
        # 1. DE-FRAGMENT & SORT: Crucial for finding real positives
        # We sort by card1 (User ID) so that adjacent rows are likely the same user
        ieee_df = ieee_df.sort_values(["card1", "TransactionDT"]).copy()
        
        device_cols = ["id_31", "id_33", "DeviceType", "DeviceInfo"]
        for col in device_cols:
            ieee_df[col] = ieee_df[col].astype(str).fillna("unknown")

        # Encode categorical
        cat_data, vocab_sizes = [], []
        for col in device_cols:
            le = LabelEncoder()
            encoded = le.fit_transform(ieee_df[col])
            cat_data.append(encoded.reshape(-1, 1))
            vocab_sizes.append(int(encoded.max()) + 1)

        cat_feats = torch.tensor(np.hstack(cat_data), dtype=torch.long, device=self.device)
        
        # Prepare continuous (Add scaling to prevent gradient explosion)
        cont_cols = ["device_match_ord", "device_novelty"]
        for i in cont_cols:
            if i not in ieee_df.columns:
                ieee_df[i] = 0.0
            else:
                ieee_df[i] = ieee_df[i].fillna(0)
        cont_values = ieee_df[cont_cols].values.astype(np.float32)
        # Simple z-score scaling
        cont_values = (cont_values - cont_values.mean(0)) / (cont_values.std(0) + 1e-6)
        cont_feats = torch.tensor(cont_values, dtype=torch.float32, device=self.device)

        model = DeviceFingerEncoder(
            cat_dims=vocab_sizes,
            cat_embed_dim=16,
            n_continuous=cont_feats.shape[1],
            embed_dim=64
        ).to(self.device)

        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4) # Lower LR for stability
        # Lower margin to prevent the "0.1000" trap
        triplet_loss = nn.TripletMarginLoss(margin=0.5, p=2) 
        
        model.train()
        batch_size = 1024 
        epochs = 3 # Increased epochs since it's now actually learning
        dataset = TensorDataset(cat_feats, cont_feats)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=False) # Keep sorted order
        
        for epoch in range(epochs):
            epoch_loss = 0.0
            for batch_cat, batch_cont in loader:
                optimizer.zero_grad(set_to_none=True)
                
                with torch.amp.autocast("cuda"):
                    anchor_emb = model(batch_cat, batch_cont)
                    
                    # REAL POSITIVE: Since we sorted by card1, roll(1) is often the same user
                    pos_emb = torch.roll(anchor_emb, shifts=1, dims=0)
                    # REAL NEGATIVE: A far-away index is almost certainly a different user
                    neg_emb = torch.roll(anchor_emb, shifts=batch_size // 2, dims=0)
                    
                    loss = triplet_loss(anchor_emb, pos_emb, neg_emb)
                
                self.scaler.scale(loss).backward()
                self.scaler.step(optimizer)
                self.scaler.update()
                epoch_loss += loss.item()
            
            logger.info(f"  Epoch {epoch+1}: Triplet Loss = {epoch_loss/len(loader):.4f}")

        # Save and set to eval
        torch.save(model.state_dict(), self.cfg.siamese_device)
        model.eval()
        
        # 2. BULK ASSIGNMENT (Prevents PerformanceWarning)
        with torch.no_grad(), torch.amp.autocast("cuda"):
            device_emb = model(cat_feats, cont_feats).cpu().numpy()
        
        # Add columns via a dictionary to avoid multiple inserts
        new_results = {
            "device_embedding": list(device_emb),
            "device_dist_score": np.zeros(len(ieee_df)) # Placeholder or calculate real dist
        }
        ieee_df = pd.concat([ieee_df, pd.DataFrame(new_results, index=ieee_df.index)], axis=1)
        
        return model, ieee_df.copy() # Return copy to ensure de-fragmentation
    def run(self, ieee_df: Optional[pd.DataFrame] = None) -> Tuple[Dict, pd.DataFrame]:
        if ieee_df is None: ieee_df = self.load_ieee_cis_merged()
        
        models = {}
        
        # Train or load Model A (TabNet)
        if Path(self.cfg.tabnet_finetuned).exists():
            logger.info("\n✓ Loading cached Model A (TabNet)...")
            model_a = TabNetEncoder(in_dim=len(V_COLS + C_COLS + D_COLS), embed_dim=128).to(self.device)
            model_a.load_state_dict(torch.load(self.cfg.tabnet_finetuned, map_location=self.device))
            model_a.eval()
            
            # Generate predictions using cached model
            feat_cols = [c for c in (V_COLS + C_COLS + D_COLS) if c in ieee_df.columns]
            X = ieee_df[feat_cols].fillna(0).values.astype(np.float32)
            X_tensor = torch.tensor(X, dtype=torch.float32, device=self.device)
            
            with torch.no_grad():
                model_a.eval()
                full_loader = DataLoader(TensorDataset(X_tensor), batch_size=512, shuffle=False)
                all_logits, all_embeddings = [], []
                for (batch,) in full_loader:
                    out = model_a(batch)
                    all_logits.append(out["logit"].cpu().numpy())
                    all_embeddings.append(out["embedding"].cpu().numpy())
            
            ieee_df["tabnet_logit"] = np.concatenate(all_logits)
            ieee_df["tabnet_embedding"] = list(np.vstack(all_embeddings))
        else:
            model_a, ieee_df = self.train_tabnet(ieee_df)
        
        models["tabnet"] = model_a
        
        # Train or load Model B (Siamese)
        if Path(self.cfg.siamese_device).exists():
            logger.info("\n✓ Loading cached Model B (Siamese Device)...")
            
            ieee_df_copy = ieee_df.copy()
            device_cols = ["id_31", "id_33", "DeviceType", "DeviceInfo"]
            for col in device_cols:
                if col not in ieee_df_copy.columns: 
                    ieee_df_copy[col] = "unknown"
                ieee_df_copy[col] = ieee_df_copy[col].astype(str).fillna("unknown")

            cat_data, vocab_sizes = [], []
            for col in device_cols:
                encoded = LabelEncoder().fit_transform(ieee_df_copy[col])
                cat_data.append(encoded.reshape(-1, 1))
                vocab_sizes.append(int(encoded.max()) + 1)

            cat_feats = torch.tensor(np.hstack(cat_data), dtype=torch.long, device=self.device)
            
            cont_cols = ["device_match_ord", "device_novelty"]
            for col in cont_cols:
                if col not in ieee_df_copy.columns: 
                    ieee_df_copy[col] = 0.0
                ieee_df_copy[col] = pd.to_numeric(ieee_df_copy[col], errors='coerce').fillna(0)
                
            cont_feats = torch.tensor(ieee_df_copy[cont_cols].values, dtype=torch.float32, device=self.device)
            
            model_b = DeviceFingerEncoder(
                cat_dims=vocab_sizes,
                cat_embed_dim=16,
                n_continuous=cont_feats.shape[1],
                embed_dim=64
            ).to(self.device)
            model_b.load_state_dict(torch.load(self.cfg.siamese_device, map_location=self.device))
            model_b.eval()
            
            with torch.no_grad():
                device_emb = model_b(cat_feats, cont_feats)
            ieee_df["device_embedding"] = list(device_emb.cpu().numpy())
        else:
            model_b, ieee_df = self.train_siamese_device(ieee_df)
        
        models["siamese"] = model_b
        return models, ieee_df

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
        
        return ieee_df, transformer
        
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

    def run(self, ieee_df: pd.DataFrame) -> Tuple[Dict, pd.DataFrame]:
        models = {}
        
        transformer = nn.TransformerEncoder(
            nn.TransformerEncoderLayer(d_model=128, nhead=4, batch_first=True),
            num_layers=2
        ).to(self.device)
        # Check if Model C (SeqTransformer) exists
        if Path(self.cfg.seq_ieee_finetuned).exists():
            logger.info("\n✓ Loading cached Model C (Sequence Transformer)...")
            transformer.load_state_dict(torch.load(self.cfg.seq_ieee_finetuned, map_location=self.device))
            transformer.eval()
            
            if "tabnet_embedding" in ieee_df.columns:
                seq_inputs = np.vstack(ieee_df["tabnet_embedding"].values)
                seq_tensor = torch.tensor(seq_inputs, dtype=torch.float32, device=self.device)
                
                seq_anomaly_scores = []
                with torch.no_grad():
                    seq_chunks = torch.split(seq_tensor, 1024)
                    for chunk in seq_chunks:
                        out = transformer(chunk.unsqueeze(0))
                        err = torch.mean((out.squeeze(0) - chunk)**2, dim=1).cpu().numpy()
                        seq_anomaly_scores.extend(err)
                
                ieee_df["seq_embedding"] = list(seq_tensor.cpu().numpy())
                ieee_df["seq_anomaly_score"] = seq_anomaly_scores
                ieee_df["paysim_boost"] = ieee_df["seq_anomaly_score"] * 1.5
            models["seq_transformer"] = transformer
        else:
            ieee_df, transformer = self.train_sequence_transformer(ieee_df)
            models["seq_transformer"] = transformer
        
        # Check if Model E (HeteroGNN) exists
        if Path(self.cfg.hetero_gnn).exists():
            logger.info("\n✓ Loading cached Model E (HeteroGNN)...")
            if "tabnet_embedding" in ieee_df.columns:
                logger.info("  Skipping GNN training (using cached embeddings)...")
                ieee_df["txn_graph_logit"] = ieee_df["tabnet_logit"]
            models["hetero_gnn"] = None  # Placeholder
        else:
            ieee_df = self.train_hetero_gnn(ieee_df)
            models["hetero_gnn"] = None
        
        return models, ieee_df

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 3: SPECIALISTS TRAINING
# ═══════════════════════════════════════════════════════════════════════════

class Phase3Specialists:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = torch.device(cfg.device)

    def train_tabular_autoencoder(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 3] Training Model D: Denoising Autoencoder (Production-Grade with Contractive Loss)...")
        
        legit_df = ieee_df[ieee_df["isFraud"] == 0]
        feat_cols = [c for c in (V_COLS + C_COLS + D_COLS) if c in ieee_df.columns]
        X_legit = legit_df[feat_cols].fillna(0).values.astype(np.float32)
        X_full = ieee_df[feat_cols].fillna(0).values.astype(np.float32)
        
        try:
            from PRODUCTION_MODELS_UPGRADE import train_autoencoder_on_legitimate_only
            
            recon_errors = train_autoencoder_on_legitimate_only(
                X_legit=X_legit,
                X_all=X_full,
                cfg=self.cfg,
                device=self.device,
                epochs=60,
                batch_size=512,
                lambda_contractive=1e-4,
            )
            
            ieee_df["recon_error"] = recon_errors
            
            logger.info(f"\n  === Autoencoder Results ===")
            logger.info(f"  Reconstruction errors - legitimate mean: {recon_errors[:len(legit_df)].mean():.6f}")
            logger.info(f"  Reconstruction errors - fraud mean: {recon_errors[len(legit_df):].mean():.6f}")
            logger.info(f"  Separation ratio: {recon_errors[len(legit_df):].mean() / recon_errors[:len(legit_df)].mean():.2f}x")
            logger.info(f"  Model saved to: {self.cfg.tabular_ae}\n")
            
            return ieee_df
            
        except ImportError:
            logger.warning("  ⚠️  PRODUCTION_MODELS_UPGRADE not found, falling back to basic training...")
            # Fallback to simplified autoencoder
            model = nn.Sequential(
                nn.Dropout(0.2),
                nn.Linear(X_legit.shape[1], 256), nn.LeakyReLU(),
                nn.Linear(256, 128), nn.LeakyReLU(),
                nn.Linear(128, 64), nn.LeakyReLU(), 
                nn.Linear(64, 128), nn.LeakyReLU(),
                nn.Linear(128, 256), nn.LeakyReLU(),
                nn.Linear(256, X_legit.shape[1])
            ).to(self.device)
            
            optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
            loader = DataLoader(TensorDataset(torch.from_numpy(X_legit)), batch_size=512, shuffle=True)

            model.train()
            epochs = 10
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
            X_full_tensor = torch.tensor(X_full, device=self.device)
            
            with torch.no_grad():
                recon_full = model(X_full_tensor)
                recon_err = torch.mean((recon_full - X_full_tensor)**2, dim=1).cpu().numpy()
                
            logger.info("\n  === DAE Stats ===")
            logger.info(f"  Overall Reconstruction RMSE: {np.sqrt(np.mean(recon_err)):.4f}\n")

            ieee_df["recon_error"] = recon_err
            return ieee_df, model

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

        return ieee_df, model

    def train_synthetic_id_detector(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 3] Training Model F: Synthetic ID (Weak Supervision)...")
        ieee_df["weak_synth"] = ((ieee_df["P_emaildomain"].isna()) & (ieee_df["recon_error"] > np.percentile(ieee_df["recon_error"], 90))).astype(float)
        return self._train_weak_supervisor(ieee_df, "weak_synth", self.cfg.synth_id_detector, "synth_id")

    def train_ato_chain_detector(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 3] Training Model G: ATO Chain (Weak Supervision)...")
        if "delta_t" not in ieee_df.columns: ieee_df["delta_t"] = 9999
        ieee_df["weak_ato"] = ((ieee_df["delta_t"] < 60) & (ieee_df["TransactionAmt"] > 500)).astype(float)
        return self._train_weak_supervisor(ieee_df, "weak_ato", self.cfg.ato_detector, "ato")

    def run(self, ieee_df: pd.DataFrame) -> Tuple[Dict, pd.DataFrame]:
        models = {}
        
        # Load or train Model D (Autoencoder)
        if Path(self.cfg.tabular_ae).exists():
            logger.info("\n✓ Loading cached Model D (Autoencoder)...")
            feat_cols = [c for c in (V_COLS + C_COLS + D_COLS) if c in ieee_df.columns]
            X_full = ieee_df[feat_cols].fillna(0).values.astype(np.float32)
            X_full_tensor = torch.tensor(X_full, device=self.device)
            
            model_d = nn.Sequential(
                nn.Dropout(0.2),
                nn.Linear(X_full.shape[1], 256), nn.LeakyReLU(),
                nn.Linear(256, 128), nn.LeakyReLU(),
                nn.Linear(128, 64), nn.LeakyReLU(), 
                nn.Linear(64, 128), nn.LeakyReLU(),
                nn.Linear(128, 256), nn.LeakyReLU(),
                nn.Linear(256, X_full.shape[1])
            ).to(self.device)
            model_d.load_state_dict(torch.load(self.cfg.tabular_ae, map_location=self.device))
            model_d.eval()
            
            with torch.no_grad():
                recon_full = model_d(X_full_tensor)
                recon_err = torch.mean((recon_full - X_full_tensor)**2, dim=1).cpu().numpy()
            
            ieee_df["recon_error"] = recon_err
            models["autoencoder"] = model_d
        else:
            ieee_df = self.train_tabular_autoencoder(ieee_df)
            models["autoencoder"] = None
        
        # Load or train Model F (SyntheticID)
        if Path(self.cfg.synth_id_detector).exists():
            logger.info("\n✓ Loading cached Model F (Synthetic ID Detector)...")
            features = ieee_df[["TransactionAmt", "recon_error", "tabnet_logit"]].fillna(0).values
            X_t = torch.tensor(features, dtype=torch.float32, device=self.device)
            
            model_f = nn.Sequential(
                nn.Linear(3, 32), nn.ReLU(),
                nn.Linear(32, 1)
            ).to(self.device)
            model_f.load_state_dict(torch.load(self.cfg.synth_id_detector, map_location=self.device))
            model_f.eval()
            
            with torch.no_grad():
                probs = torch.sigmoid(model_f(X_t)).cpu().numpy().flatten()
            ieee_df["synth_id_prob"] = probs
            models["synth_id"] = model_f
        else:
            ieee_df["weak_synth"] = ((ieee_df["P_emaildomain"].isna()) & (ieee_df["recon_error"] > np.percentile(ieee_df["recon_error"], 90))).astype(float)
            ieee_df = self._train_weak_supervisor(ieee_df, "weak_synth", self.cfg.synth_id_detector, "synth_id")
            models["synth_id"] = None
        
        # Load or train Model G (ATO Chain)
        if Path(self.cfg.ato_detector).exists():
            logger.info("\n✓ Loading cached Model G (ATO Chain Detector)...")
            features = ieee_df[["TransactionAmt", "recon_error", "tabnet_logit"]].fillna(0).values
            X_t = torch.tensor(features, dtype=torch.float32, device=self.device)
            
            model_g = nn.Sequential(
                nn.Linear(3, 32), nn.ReLU(),
                nn.Linear(32, 1)
            ).to(self.device)
            model_g.load_state_dict(torch.load(self.cfg.ato_detector, map_location=self.device))
            model_g.eval()
            
            with torch.no_grad():
                probs = torch.sigmoid(model_g(X_t)).cpu().numpy().flatten()
            ieee_df["ato_prob"] = probs
            models["ato_chain"] = model_g
        else:
            if "delta_t" not in ieee_df.columns: 
                ieee_df["delta_t"] = 9999
            ieee_df["weak_ato"] = ((ieee_df["delta_t"] < 60) & (ieee_df["TransactionAmt"] > 500)).astype(float)
            ieee_df = self._train_weak_supervisor(ieee_df, "weak_ato", self.cfg.ato_detector, "ato")
            models["ato_chain"] = None
        
        return models, ieee_df

# ═══════════════════════════════════════════════════════════════════════════
# PHASE 4: SYNTHESIS TRAINING
# ═══════════════════════════════════════════════════════════════════════════

class Phase4Synthesis:
    def __init__(self, cfg):
        self.cfg = cfg
        self.device = torch.device(cfg.device)

    def train_lgbm_stacker(self, ieee_df: pd.DataFrame):
        logger.info("\n[PHASE 4] Training Model H: LightGBM Stacker (Production-Grade with OOF)...")
        import lightgbm as lgb
        
        stack_cols = [
            "tabnet_logit", "seq_anomaly_score", "paysim_boost",
            "recon_error", "txn_graph_logit", "synth_id_prob", "ato_prob"
        ]
        
        for col in stack_cols:
            if col not in ieee_df.columns: 
                ieee_df[col] = 0
                
        try:
            from PRODUCTION_MODELS_UPGRADE import train_lgbm_stacker_oof
            
            lgbm_oof, stacker_model = train_lgbm_stacker_oof(
                feature_store=ieee_df,
                stacking_cols=stack_cols,
                cfg=self.cfg,
                n_splits=5,
                n_estimators=1000,
            )
            
            # Log results
            y = ieee_df["isFraud"].values
            auc = roc_auc_score(y, lgbm_oof)
            oof_bin = (lgbm_oof > 0.5).astype(int)
            
            logger.info(f"\n  === LightGBM Stacker Results ===")
            logger.info(f"  OOF AUC:       {auc:.4f} ✓")
            logger.info(f"  OOF Accuracy:  {accuracy_score(y, oof_bin):.4f}")
            logger.info(f"  OOF Precision: {precision_score(y, oof_bin, zero_division=0):.4f}")
            logger.info(f"  OOF Recall:    {recall_score(y, oof_bin, zero_division=0):.4f}")
            logger.info(f"  OOF F1 Score:  {f1_score(y, oof_bin, zero_division=0):.4f}\n")
            torch.save(stacker_model, self.cfg.lgbm_stacker)
            ieee_df["raw_fraud_score"] = lgbm_oof
            return ieee_df
            
        except ImportError:
            logger.warning("  ⚠️  PRODUCTION_MODELS_UPGRADE not found, falling back to basic stacking...")
            # Fallback to simplified stacking
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
                "n_estimators": 500,    
                "verbosity": -1,
                "random_state": 42
            }
            
            for fold, (tr_idx, val_idx) in enumerate(skf.split(X_stack, y)):
                logger.info(f"  Fold {fold+1}/5...")
                bst = lgb.LGBMClassifier(**params)
                bst.fit(
                    X_stack[tr_idx], y[tr_idx],
                    eval_set=[(X_stack[val_idx], y[val_idx])],
                    callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)]
                )
                lgbm_oof[val_idx] = bst.predict_proba(X_stack[val_idx])[:, 1]

            logger.info("  Training final stacker on full data...")
            final_bst = lgb.LGBMClassifier(**params)
            final_bst.fit(X_stack, y)
            joblib.dump(final_bst, self.cfg.lgbm_stacker)

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
        import pickle
        
        cal_idx = int(len(ieee_df) * 0.9)
        cal_scores = ieee_df["raw_fraud_score"].iloc[cal_idx:].values
        cal_labels = ieee_df["isFraud"].iloc[cal_idx:].values
        
        iso_reg = IsotonicRegression(out_of_bounds='clip')
        iso_reg.fit(cal_scores, cal_labels)
        
        # Save with pickle to preserve sklearn object
        Path(self.cfg.platt_calibrator).parent.mkdir(parents=True, exist_ok=True)
        with open(self.cfg.platt_calibrator, 'wb') as f:
            pickle.dump(iso_reg, f)
        
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

    def run(self, ieee_df: pd.DataFrame) -> Tuple[Dict, pd.DataFrame]:
        models = {}
        
        # Load or train Model H (LightGBM Stacker)
        if Path(self.cfg.lgbm_stacker).exists():
            logger.info("\n✓ Loading cached Model H (LightGBM Stacker)...")
            import lightgbm as lgb
            lgbm = lgb.Booster(model_file=self.cfg.lgbm_stacker)
            
            stack_cols = [
                "tabnet_logit", "seq_anomaly_score", "paysim_boost",
                "recon_error", "txn_graph_logit", "synth_id_prob", "ato_prob"
            ]
            for col in stack_cols:
                if col not in ieee_df.columns: 
                    ieee_df[col] = 0
            
            X_stack = ieee_df[stack_cols].fillna(0).values
            lgbm_oof = lgbm.predict(X_stack)
            ieee_df["raw_fraud_score"] = lgbm_oof
            models["lgbm_stacker"] = lgbm
        else:
            ieee_df = self.train_lgbm_stacker(ieee_df)
            try:
                import lightgbm as lgb
                models["lgbm_stacker"] = lgb.Booster(model_file=self.cfg.lgbm_stacker)
            except:
                models["lgbm_stacker"] = None
        
        # Load or train Model I (Platt Calibrator)
        if Path(self.cfg.platt_calibrator).exists():
            logger.info("\n✓ Loading cached Model I (Platt Calibrator)...")
            from sklearn.isotonic import IsotonicRegression
            import pickle
            
            with open(self.cfg.platt_calibrator, 'rb') as f:
                calibrator = pickle.load(f)
            
            cal_probs = calibrator.predict(ieee_df["raw_fraud_score"].values)
            ieee_df["calibrated_prob"] = cal_probs
            models["calibrator"] = calibrator
        else:
            ieee_df = self.train_isotonic_calibrator(ieee_df)
            try:
                import pickle
                with open(self.cfg.platt_calibrator, 'rb') as f:
                    models["calibrator"] = pickle.load(f)
            except:
                models["calibrator"] = None
        
        # Generate decision column
        if "decision" not in ieee_df.columns:
            conditions = [
                ieee_df["calibrated_prob"] < 0.30,
                ieee_df["calibrated_prob"] < 0.70
            ]
            choices = ["approve", "mfa"]
            ieee_df["decision"] = np.select(conditions, choices, default="block")
        
        return models, ieee_df


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
                    torch.load(self.cfg.platt_calibrator, map_location=self.device, weights_only=False)
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
    logger.info("SINGLE-ROW INFERENCE DEMO WITH SHAP EXPLANATIONS")
    logger.info("="*80)
    
    # Check if models_dict is empty
    if not models_dict:
        logger.error("❌ No models available in models_dict! Cannot run inference demo.")
        return
    
    logger.info(f"\nAvailable models for SHAP: {list(models_dict.keys())}\n")

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
    logger.info("\n📊 Initializing SHAP explainers...")
    unified_explainer = UnifiedFraudExplainer(
        models_dict=models_dict,
        background_data=bg_data,
        feature_names=feat_names
    )
    
    if not unified_explainer.explainers:
        logger.warning("⚠️  No SHAP explainers available! Inference will proceed without explanations.")
    else:
        logger.info(f"✓ SHAP explainers ready: {list(unified_explainer.explainers.keys())}\n")
    
    cfg = PipelineConfig()
    inferrer = FraudDetectionInference(cfg)
    
    # 7. Fixed Loop Logic: Just test on 3 random transactions
    logger.info("🔍 Running inference on sample transactions...\n")
    for txn_num in range(1, 4): 
        # Get one live transaction (assuming it returns a dict or pd.Series)
        live_txn = get_random_live_transaction(ieee_df)
        
        # Convert it to a 1-row DataFrame so we can extract features cleanly for SHAP
        if isinstance(live_txn, dict):
            row = pd.DataFrame([live_txn])
        else:
            row = live_txn.to_frame().T

        logger.info(f"\n{'='*80}")
        logger.info(f"Transaction #{txn_num}: {row['TransactionID'].values[0]}")
        logger.info(f"{'='*80}")
        
        # Run inference
        result = inferrer.infer_single_row(live_txn, include_reasons=True)
        
        # Run Explainer (using .to_frame().T for stack_x to avoid LGBM feature name warnings)
        # Ensure raw_x and weak_x are proper float32 tensors
        raw_x = torch.tensor(row[feat_names["raw"]].fillna(0).values.astype(np.float32), device=device)
        weak_x = torch.tensor(row[feat_names["weak"]].fillna(0).values.astype(np.float32), device=device)
        
        # CRITICAL: Keep as a 2D DataFrame (1 row, N columns) to maintain feature names
        stack_x = row[feat_names["stack"]].fillna(0).astype(np.float32) 

        # Now pass to explainer
        reasons = unified_explainer.explain_transaction(raw_x, weak_x, stack_x, device)

        # Print results safely
        if "error" in result:
            logger.error(f"❌ Inference Failed: {result['error']}")
        else:
            logger.info(f"\n  💱 Amount:           ${row['TransactionAmt'].values[0]:,.2f}")
            logger.info(f"  📈 Raw Score:        {result.get('raw_fraud_score', 0):.4f}")
            logger.info(f"  🎯 Calibrated Prob:  {result.get('calibrated_prob', 0):.4f}")
            logger.info(f"  ✅ Decision:         {result.get('decision', 'UNKNOWN').upper()}")
            
            if reasons:
                logger.info(f"\n  📋 SHAP Explanations:")
                for i, r in enumerate(reasons[:5], 1): 
                    logger.info(f"     {i}. {r}")
            else:
                logger.warning(f"  ⚠️  No SHAP explanations available (no explainers ready)")
    
    logger.info(f"\n{'='*80}")
    logger.info("Demo Complete")
    logger.info(f"{'='*80}\n")

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
        models_p1, ieee_df = phase1.run()
        all_models.update(models_p1)  # Add Phase 1 models
        logger.info(f"  Phase 1 models available: {list(models_p1.keys())}")
    else:
        # Load from checkpoint
        try:
            ieee_df = pd.read_parquet(cfg.ieee_enriched)
            logger.info(f"✓ Loaded checkpoint: {cfg.ieee_enriched}")
        except:
            logger.warning("Could not load checkpoint, running Phase 1...")
            phase1 = Phase1Foundation(cfg)
            models_p1, ieee_df = phase1.run()
            all_models.update(models_p1)
    
    if phase in ["PHASE_2", "ALL"]:
        logger.info("\n>>> Starting PHASE 2: CONTEXT (Models E & C)\n")
        phase2 = Phase2Context(cfg)
        models_p2, ieee_df = phase2.run(ieee_df)
        all_models.update(models_p2)  # Add Phase 2 models
        logger.info(f"  Phase 2 models available: {list(models_p2.keys())}")
    
    if phase in ["PHASE_3", "ALL"]:
        logger.info("\n>>> Starting PHASE 3: SPECIALISTS (Models F, G & D)\n")
        phase3 = Phase3Specialists(cfg)
        models_p3, ieee_df = phase3.run(ieee_df)
        all_models.update(models_p3)  # Add Phase 3 models
        logger.info(f"  Phase 3 models available: {list(models_p3.keys())}")
    
    if phase in ["PHASE_4", "ALL"]:
        logger.info("\n>>> Starting PHASE 4: SYNTHESIS (Models H & I)\n")
        phase4 = Phase4Synthesis(cfg)
        models_p4, ieee_df = phase4.run(ieee_df)
        all_models.update(models_p4)  # Add Phase 4 models
        logger.info(f"  Phase 4 models available: {list(models_p4.keys())}")
    
    logger.info(f"\n✓ All available models for SHAP: {list(all_models.keys())}")
    
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

    # Demo inference with all models (with safety check)
    if all_models:
        logger.info(f"\n✓ Starting inference demo with {len(all_models)} models...")
        demo_single_row_inference(ieee_df, device=cfg.device, models_dict=all_models)
    else:
        logger.warning("\n⚠️  No models available for inference demo (all_models is empty)")
    
    logger.info("\n" + "="*80)
    logger.info("PIPELINE COMPLETE")
    logger.info("="*80)


if __name__ == "__main__":
    main()
