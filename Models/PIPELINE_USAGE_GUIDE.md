"""
PIPELINE_USAGE_GUIDE.md
═════════════════════════════════════════════════════════════════════════════

Complete guide to the 4-Phase Fraud Detection Pipeline Architecture.

═════════════════════════════════════════════════════════════════════════════
"""

# 4-PHASE FRAUD DETECTION ARCHITECTURE
## Complete Usage Guide

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start](#quick-start)
3. [Phase-by-Phase Breakdown](#phase-by-phase-breakdown)
4. [Training Guide](#training-guide)
5. [Inference Guide](#inference-guide)
6. [Testing & Validation](#testing--validation)
7. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

The pipeline is organized into **4 sequential phases**, each with specific models:

### Phase 1: FOUNDATION (Dense Compression)
- **Model A (TabNet)**: Compresses sparse tabular features into 128D embeddings
- **Model B (Siamese)**: Encodes device fingerprints into 64D embeddings
- **Output**: Dense feature vectors capturing raw attribute patterns
- **Purpose**: Transform high-dimensional, sparse data into compact representations

### Phase 2: CONTEXT (Relational + Temporal Understanding)
- **Model E (HeteroGNN)**: Learns relationship structures (user-card-IP graphs)
- **Model C (SeqTransformer)**: Captures behavioral sequences (transaction sequences)
- **Input**: Phase 1 embeddings + raw transaction graph + user sequences
- **Output**: Augmented embeddings with relationship + temporal context
- **Purpose**: Understand HOW transactions relate to each other and their history

### Phase 3: SPECIALISTS (Pattern Detection)
- **Model F (SyntheticID)**: Detects fake identity accounts
- **Model G (ATO Chain)**: Detects account takeover patterns
- **Model D (Autoencoder)**: Detects anomalous/novel transactions
- **Input**: Phase 2 context + Phase 1 embeddings
- **Output**: Pattern-specific fraud probabilities
- **Purpose**: Look for specific fraud signatures

### Phase 4: SYNTHESIS (Final Decision)
- **Model H (LightGBM Stacker)**: Ensemble aggregator, reconciles specialist votes
- **Model I (Platt Calibrator)**: Converts raw scores to actionable probabilities
- **Input**: All upstream model outputs + reason codes (SHAP)
- **Output**: Calibrated fraud probability + decision (approve/mfa/block)
- **Purpose**: Final decision with explainability

---

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
pip install pandas numpy torch scikit-learn lightgbm

# Optional: For GPU acceleration
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Run Full Pipeline (All 4 Phases)

```bash
python run_pipeline_phase_refactored.py ALL
```

### Run Specific Phase

```bash
python run_pipeline_phase_refactored.py PHASE_1  # Foundation only
python run_pipeline_phase_refactored.py PHASE_2  # Context (requires Phase 1)
python run_pipeline_phase_refactored.py PHASE_3  # Specialists (requires Phase 1-2)
python run_pipeline_phase_refactored.py PHASE_4  # Synthesis (requires Phase 1-3)
```

### Test Inference on Single Transaction

```bash
python test_fraud_detection_pipeline.py --test-inference
```

### Run Full Test Suite

```bash
python test_fraud_detection_pipeline.py
```

---

## 📊 Phase-by-Phase Breakdown

### Phase 1: Foundation Training

**What Happens:**
1. Load IEEE-CIS transactions with all features (V, C, D, M columns)
2. Train Model A (TabNet) on raw tabular features
3. Train Model B (Siamese) on device fingerprints
4. Extract Phase 1 embeddings: 128D + 64D

**Time:** ~5-10 minutes (production on full data)
**GPU Memory:** ~2-4 GB

**Example Code:**
```python
from run_pipeline_phase_refactored import Phase1Foundation, PipelineConfig

cfg = PipelineConfig()
phase1 = Phase1Foundation(cfg)
ieee_df = phase1.run()  # Loads data and trains both models
```

**Outputs:**
- `models/tabnet_finetuned.pt` — Model A weights
- `models/siamese_device.pt` — Model B weights
- DataFrame with columns: `tabnet_embedding`, `tabnet_logit`, `device_embedding`

---

### Phase 2: Context Training

**What Happens:**
1. Load Phase 1 embeddings and raw transaction graph
2. Train Model E (HeteroGNN) on heterogeneous graph
3. Train Model C (SeqTransformer) on user behavior sequences
4. Extract Phase 2 context: graph embeddings + sequence embeddings

**Time:** ~15-20 minutes
**GPU Memory:** ~6-8 GB

**Example Code:**
```python
from run_pipeline_phase_refactored import Phase2Context

phase2 = Phase2Context(cfg)
ieee_df = phase2.run(ieee_df)
```

**Outputs:**
- `models/hetero_gnn.pt` — Model E weights
- `models/seq_transformer_ieee_finetuned.pt` — Model C weights
- DataFrame with columns: `graph_embedding`, `txn_graph_logit`, `ring_score`, `seq_embedding`, `seq_anomaly_score`

---

### Phase 3: Specialists Training

**What Happens:**
1. Train Model F (SyntheticID) using graph context from Phase 2
2. Train Model G (ATO Chain) fusing sequence + graph contexts
3. Train Model D (Autoencoder) on legitimate transactions only
4. Extract specialist outputs: fraud probabilities per pattern

**Time:** ~10-15 minutes
**GPU Memory:** ~4-6 GB

**Example Code:**
```python
from run_pipeline_phase_refactored import Phase3Specialists

phase3 = Phase3Specialists(cfg)
ieee_df = phase3.run(ieee_df)
```

**Outputs:**
- `models/synth_id_detector.pt` — Model F weights
- `models/ato_chain_detector.pt` — Model G weights
- `models/tabular_ae.pt` — Model D weights
- DataFrame with columns: `synth_id_prob`, `ato_prob`, `recon_error`

---

### Phase 4: Synthesis Training

**What Happens:**
1. Collect all upstream model outputs using OOF (Out-of-Fold) validation
2. Train Model H (LightGBM) on stacking features
3. Fit Model I (Platt Calibrator) for probability calibration
4. Generate SHAP explanations for top features

**Time:** ~5-10 minutes
**GPU Memory:** ~2-4 GB

**Example Code:**
```python
from run_pipeline_phase_refactored import Phase4Synthesis

phase4 = Phase4Synthesis(cfg)
ieee_df = phase4.run(ieee_df)
```

**Outputs:**
- `models/lgbm_stacker.lgb` — Model H (LightGBM booster)
- `models/platt_calibrator.pt` — Model I weights
- DataFrame with columns: `raw_fraud_score`, `calibrated_prob`, `decision`, `reason_codes`

---

## 🎓 Training Guide

### Full End-to-End Training

```python
from run_pipeline_phase_refactored import (
    PipelineConfig,
    Phase1Foundation, Phase2Context, Phase3Specialists, Phase4Synthesis
)

# Setup
cfg = PipelineConfig()
cfg.ensure_dirs()

# Phase 1: Foundation
phase1 = Phase1Foundation(cfg)
df = phase1.run()

# Phase 2: Context
phase2 = Phase2Context(cfg)
df = phase2.run(df)

# Phase 3: Specialists
phase3 = Phase3Specialists(cfg)
df = phase3.run(df)

# Phase 4: Synthesis
phase4 = Phase4Synthesis(cfg)
df = phase4.run(df)

print("✓ Training complete!")
```

### Custom Configuration

```python
from pathlib import Path
from run_pipeline_phase_refactored import PipelineConfig

# Override default paths
cfg = PipelineConfig(
    device="cuda",  # Force GPU
    ieee_txn_path="data/custom_transactions.csv",
    model_root=Path("custom_models"),
    feature_root=Path("custom_features"),
)

cfg.ensure_dirs()
# ... rest of training
```

### Resuming Interrupted Training

```python
from run_pipeline_phase_refactored import Phase4Synthesis, PipelineConfig
import pandas as pd

cfg = PipelineConfig()

# Load checkpoint from Phase 3
df = pd.read_parquet("data/processed/ieee_cis_fully_enriched.parquet")

# Resume from Phase 4
phase4 = Phase4Synthesis(cfg)
df = phase4.run(df)
```

---

## 🔮 Inference Guide

### Single Transaction Inference

```python
from run_pipeline_phase_refactored import FraudDetectionInference, PipelineConfig

cfg = PipelineConfig()
inferrer = FraudDetectionInference(cfg)

# Define transaction
transaction = {
    "TransactionID": "TXN_12345",
    "TransactionAmt": 500,
    "card1": 1234,
    "card2": 123,
    "card3": 25,
    "card4": 1,
    "card5": 165,
    "card6": 398,
    "addr1": 100,
    "addr2": 50,
    "P_emaildomain": "gmail.com",
    "device_novelty": 0.8,  # High: new device
    "device_match_ord": 0,  # Zero: never seen
    "delta_t": 300,  # 5 minutes since last login
    "V1": 0.5, "C1": 1, "D1": 10,  # Example features
}

# Get prediction
result = inferrer.infer_single_row(transaction, include_reasons=True)

print(f"Decision: {result['decision'].upper()}")
print(f"Fraud Probability: {result['calibrated_prob']:.4f}")
print(f"Reasons:")
for reason in result['reasons']:
    print(f"  • {reason}")
```

**Output:**
```
Decision: MFA
Fraud Probability: 0.4523
Reasons:
  • New device fingerprint detected (↑ risk +0.18)
  • High velocity: multiple txns in <1 hour (↑ risk +0.12)
```

### Batch Inference (DataFrame)

```python
from run_pipeline_phase_refactored import FraudDetectionInference, PipelineConfig
import pandas as pd

cfg = PipelineConfig()
inferrer = FraudDetectionInference(cfg)

# Load transactions
df_test = pd.read_csv("data/test_transactions.csv")

# Infer on batch
results = []
for idx, row in df_test.iterrows():
    txn = row.to_dict()
    result = inferrer.infer_single_row(txn, include_reasons=False)
    results.append(result)

results_df = pd.DataFrame(results)

# Export decisions
results_df[["TransactionID", "decision", "calibrated_prob"]].to_csv(
    "decisions_output.csv", index=False
)
```

### Decision Making Examples

```python
result = inferrer.infer_single_row(txn)
cal_prob = result['calibrated_prob']

if cal_prob < 0.30:
    decision = "APPROVE"        # Low fraud risk
    action = "Process normally"
elif cal_prob < 0.70:
    decision = "MFA"            # Medium risk
    action = "Require 2FA"
else:
    decision = "BLOCK"          # High fraud risk
    action = "Decline & investigate"
```

---

## 🧪 Testing & Validation

### Run Full Test Suite

```bash
python test_fraud_detection_pipeline.py
```

### Test Specific Phase

```bash
python test_fraud_detection_pipeline.py --test phase1
python test_fraud_detection_pipeline.py --test phase2
python test_fraud_detection_pipeline.py --test phase3
python test_fraud_detection_pipeline.py --test phase4
```

### Test Inference Functions

```bash
# Single-row inference
python test_fraud_detection_pipeline.py --test-inference

# Batch inference
python test_fraud_detection_pipeline.py --test-batch

# Full pipeline
python test_fraud_detection_pipeline.py --test-full
```

### Generate Synthetic Test Data

```python
from test_fraud_detection_pipeline import SyntheticDataGenerator

# Legitimate transactions
legit = SyntheticDataGenerator.generate_legitimate_transactions(n=1000)

# Fraudulent transactions (various patterns)
fraud = SyntheticDataGenerator.generate_fraudulent_transactions(n=100)

# Mixed balanced dataset
mixed = SyntheticDataGenerator.generate_mixed_dataset(
    legitimate_count=5000,
    fraudulent_count=500
)

print(f"Fraud rate: {mixed['isFraud'].mean()*100:.2f}%")
```

### Evaluate Pipeline

```python
from test_fraud_detection_pipeline import test_full_pipeline
from run_pipeline_phase_refactored import PipelineConfig

cfg = PipelineConfig()
test_full_pipeline(df, cfg)
```

**Output Metrics:**
```
Metrics:
  ROC-AUC:           0.8234
  Average Precision: 0.7156
  F1 @ 0.5 threshold: 0.6789

Decision Distribution:
  approve    4250
  mfa        602
  block      148

Fraud Rate by Decision:
  approve:  0.52% (22/4250 frauds)
  mfa:     15.28% (92/602 frauds)
  block:   67.57% (100/148 frauds)
```

---

## 🛠️ Troubleshooting

### Issue: Out of Memory (OOM)

**Solution 1: Reduce batch size**
```python
# In Phase 1, 2, 3, 4 training code
batch_size = 512  # Decrease from 1024
```

**Solution 2: Use CPU for Phase 1**
```python
cfg = PipelineConfig(device="cpu")
```

**Solution 3: Train on data subset**
```python
df_subset = df.sample(frac=0.5, random_state=42)
phase1 = Phase1Foundation(cfg)
df_subset = phase1.train_tabnet(df_subset)
```

### Issue: Models Not Loading

**Check model paths:**
```python
from pathlib import Path

cfg = PipelineConfig()
print(f"TabNet path: {cfg.tabnet_finetuned}")
print(f"Exists: {Path(cfg.tabnet_finetuned).exists()}")
```

**Re-train missing models:**
```python
# Train Phase 1 and save
phase1 = Phase1Foundation(cfg)
df = phase1.run()

# Now Phase 2+ can load Phase 1 outputs
```

### Issue: Low Performance (Low AUC)

**Diagnostic Checklist:**
1. ✓ Is training data loaded correctly?
   ```python
   df = pd.read_csv("data/train_transaction.csv")
   print(f"Rows: {len(df)}, Fraud Rate: {df['isFraud'].mean():.4f}")
   ```

2. ✓ Are Phase 1 embeddings reasonable?
   ```python
   import numpy as np
   embs = np.array([e for e in df["tabnet_embedding"]])
   print(f"Embedding shape: {embs.shape}, Mean norm: {np.linalg.norm(embs, axis=1).mean():.4f}")
   ```

3. ✓ Is stacking data clean?
   ```python
   stack_cols = ["tabnet_logit", "seq_anomaly_score", "recon_error", ...]
   print(f"Missing values: {df[stack_cols].isna().sum()}")
   print(f"Any NaN in scores: {df['calibrated_prob'].isna().any()}")
   ```

4. ✓ Test on small dataset first
   ```python
   df_small = df.sample(100, random_state=42)
   # ... train on small sample
   # ... if it works, scale up
   ```

### Issue: Slow Training

**Check GPU usage:**
```bash
# Terminal: Monitor GPU
watch -n 1 nvidia-smi

# Python: Check device
import torch
print(f"GPU available: {torch.cuda.is_available()}")
print(f"GPU name: {torch.cuda.get_device_name(0)}")
```

**Optimize computation:**
```python
# Reduce model complexity
model = TabNetEncoder(in_dim=380, embed_dim=64, n_steps=3)  # Smaller

# Reduce training time
n_epochs = 5  # Instead of 30

# Use mixed precision
from torch.cuda.amp import autocast
```

### Issue: Decision Distribution Unbalanced

Normal behavior if fraud rate is low. Example:
- 1% fraud in data → Expect ~99% "approve" after calibration

If suspicious:
```python
# Check calibrator is working
print(f"Calibrator params: a={calibrator.a}, b={calibrator.b}")

# Re-fit on balanced data
from sklearn.utils.class_weight import compute_class_weight
weights = compute_class_weight("balanced", classes=[0,1], y=y)
```

---

## 📈 Performance Targets

### Expected Metrics (IEEE-CIS 2019 Fraud Detection)

| Metric | Target | Current |
|--------|--------|---------|
| ROC-AUC | > 0.95 | TBD |
| Average Precision | > 0.85 | TBD |
| F1 @ 0.30 threshold | > 0.75 | TBD |
| Inference latency p99 | < 50ms | TBD |
| False positive rate @ 90% recall | < 5% | TBD |

---

## 📚 Advanced Topics

### Model Retraining with New Data

```python
# Option 1: Incremental (fine-tune)
phase1 = Phase1Foundation(cfg)
new_data = pd.read_csv("data/new_transactions.csv")
df = phase1.train_tabnet(new_data)  # Fine-tune on new data

# Option 2: Full retrain (recommended monthly)
# Delete old models
import shutil
shutil.rmtree(cfg.model_root)

# Run full pipeline on new + historical data
df = pd.concat([pd.read_parquet(cfg.ieee_enriched), new_data])
# ... run all 4 phases
```

### SHAP Feature Importance

```python
import shap
import lightgbm as lgb

# Load LightGBM model
bst = lgb.Booster(model_file=cfg.lgbm_stacker)

# Create SHAP explainer
explainer = shap.TreeExplainer(bst)

# Explain single prediction
sample_x = stack_features[0:1]
shap_values = explainer.shap_values(sample_x)
shap.force_plot(explainer.expected_value, shap_values[1], sample_x)
```

### Drift Detection

```python
# Monitor prediction distribution
from sklearn.metrics import ks_2samp

ref_scores = df_train["raw_fraud_score"]
new_scores = df_test["raw_fraud_score"]

ks_stat, p_value = ks_2samp(ref_scores, new_scores)
if p_value < 0.05:
    print(f"⚠️ Score distribution changed significantly (KS={ks_stat:.4f})")
    # Retrain models
```

---

## 📞 Support & Questions

- Check logs in `VSCODE_TARGET_SESSION_LOG`
- Review model configs in `run_pipeline_phase_refactored.py`
- Test individual phases with `test_fraud_detection_pipeline.py`
- Ask for detailed traces with `logging.basicConfig(level=logging.DEBUG)`

---

**Last Updated:** 2026-04-04
**Architecture Version:** 4-Phase Foundation-Context-Specialists-Synthesis

"""
