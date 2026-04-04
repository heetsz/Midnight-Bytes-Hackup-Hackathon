"""
ARCHITECTURE_SUMMARY.md
═════════════════════════════════════════════════════════════════════════════

This document provides a high-level summary of the refactored 4-phase fraud
detection architecture and the files involved.

═════════════════════════════════════════════════════════════════════════════
"""

# 4-PHASE FRAUD DETECTION ARCHITECTURE — SUMMARY

## 🎯 What Changed

**Before:** Sequential execution of all models with no clear phase separation.

**After:** 4-phase hierarchical architecture where each phase builds on previous.

```
Phase 1: Foundation      → Dense embeddings (TabNet + Siamese)
    ↓
Phase 2: Context        → Relational understanding (GNN + SeqTransformer)
    ↓
Phase 3: Specialists    → Pattern detection (SyntheticID + ATO + Autoencoder)
    ↓
Phase 4: Synthesis      → Final decision (LightGBM Stacker + Platt Calibrator)
```

---

## 📁 New Files Created

### 1. **run_pipeline_phase_refactored.py** (Main Training Pipeline)
- **Purpose:** End-to-end training orchestrator
- **Key Classes:**
  - `PipelineConfig` — Central configuration
  - `Phase1Foundation` — Models A & B training
  - `Phase2Context` — Models E & C training
  - `Phase3Specialists` — Models F, G, D training
  - `Phase4Synthesis` — Models H & I training
  - `FraudDetectionInference` — Single/batch inference engine
- **Usage:**
  ```bash
  python run_pipeline_phase_refactored.py ALL              # Full training
  python run_pipeline_phase_refactored.py PHASE_3         # Specific phase
  ```

### 2. **test_fraud_detection_pipeline.py** (Comprehensive Testing)
- **Purpose:** Full test suite with synthetic data generation
- **Key Classes:**
  - `SyntheticDataGenerator` — Creates test transactions
  - `TestPhase1Foundation` — Unit tests for Phase 1
  - `TestPhase2Context` — Unit tests for Phase 2
  - `TestInference` — Inference tests
  - `TestPipelineEnd2End` — Full pipeline tests
- **Usage:**
  ```bash
  python test_fraud_detection_pipeline.py              # All tests
  python test_fraud_detection_pipeline.py --test-inference  # Inference only
  ```

### 3. **PIPELINE_USAGE_GUIDE.md** (Detailed Documentation)
- **Purpose:** Comprehensive guide with examples
- **Contents:**
  - Architecture overview
  - Quick start
  - Phase-by-phase breakdown
  - Training guide
  - Inference guide
  - Troubleshooting
  - Advanced topics

### 4. **ARCHITECTURE_SUMMARY.md** (This File)
- **Purpose:** High-level overview and quick reference

---

## 🧠 Model Architecture at a Glance

| Phase | Model | Input | Output | Purpose |
|-------|-------|-------|--------|---------|
| 1 | A: TabNet | Raw tabular [D369] | Embedding [128] + logit | Compress features |
| 1 | B: Siamese | Device FP [categorical] | Embedding [64] + dist | Device identity |
| 2 | E: HeteroGNN | Graph + Phase1 emb | Embedding [128] + logit | Relationship context |
| 2 | C: SeqTransformer | Sequences + Phase1 emb | Embedding [64] + score | Behavioral context |
| 3 | F: SyntheticID | Phase2 context + rules | Probability [0,1] | Detect fake accounts |
| 3 | G: ATO Chain | Phase2 context + scalars | Probability [0,1] | Detect account takeover |
| 3 | D: Autoencoder | Raw tabular [D369] | Reconstruction error | Detect novelty |
| 4 | H: LGBM Stacker | All Phase3 outputs | Score [0,1] | Ensemble arbitration |
| 4 | I: Platt Cal | H's score [0,1] | Calibrated prob [0,1] | Probability calibration |

---

## ⚡ Quick Start (Copy-Paste)

### Option 1: Train Full Pipeline

```python
from run_pipeline_phase_refactored import (
    PipelineConfig,
    Phase1Foundation, Phase2Context, Phase3Specialists, Phase4Synthesis
)

cfg = PipelineConfig()
cfg.ensure_dirs()

# Train all 4 phases
phase1 = Phase1Foundation(cfg)
df = phase1.run()

phase2 = Phase2Context(cfg)
df = phase2.run(df)

phase3 = Phase3Specialists(cfg)
df = phase3.run(df)

phase4 = Phase4Synthesis(cfg)
df = phase4.run(df)

print("✓ Training complete!")
```

### Option 2: Simple Inference

```python
from run_pipeline_phase_refactored import FraudDetectionInference, PipelineConfig

cfg = PipelineConfig()
inferrer = FraudDetectionInference(cfg)

transaction = {
    "TransactionID": "TXN_001",
    "TransactionAmt": 500,
    "card1": 1234, "card2": 123, "card3": 25,
    "device_novelty": 0.9,
    "delta_t": 300,
    # ... more fields
}

result = inferrer.infer_single_row(transaction)
print(f"Decision: {result['decision']}")  # "approve" | "mfa" | "block"
print(f"Probability: {result['calibrated_prob']:.4f}")
```

### Option 3: Test Everything

```python
from test_fraud_detection_pipeline import (
    TestInference, TestPipelineEnd2End, SyntheticDataGenerator
)

# Single inference test
TestInference.test_single_transaction_inference()

# Batch inference test
TestInference.test_batch_inference()

# Full end-to-end test
TestPipelineEnd2End.test_full_pipeline()
```

---

## 📊 Data Flow Diagram

```
IEEE-CIS Raw Data (transactions + identity + device FP)
        │
        ├─────────────────────────────────┐
        │                                  │
        ▼                                  ▼
    [PHASE 1]                        [PHASE 1]
    TabNet A                        Siamese B
    │                               │
    ├─ 128D embedding               ├─ 64D embedding
    └─ fraud logit                  └─ device distance
        │                               │
        └───────────────┬───────────────┘
                        │
                        ▼
    Graph + Sequences  ┌──────────────┐  Phase1 Embeddings
         │             │ [PHASE 2]    │
         ├──►  HGT E ──┤              ├─► 128D graph emb + ring_score
         │             │ SeqTx C ────┤─► 64D seq emb + anomaly_score
         │             └──────────────┘
         │
    Graph Emb ╭─────────────────────────────╮
    Seq Emb   │      [PHASE 3] Specialists │
    Tabular   ├─ SyntheticID F ────────────┤─► synth_id_prob
              ├─ ATO Chain G ──────────────┤─► ato_prob
              ├─ Autoencoder D ───────────┤─► recon_error
              ╰─────────────────────────────╯
                        │
                        │ stacking_cols = {
                        │   tabnet_logit, device_dist,
                        │   seq_anomaly, recon_error,
                        │   synth_id_prob, ato_prob, ...
                        │ }
                        ▼
                    [PHASE 4]
                    LGBM H ──┬─► raw_fraud_score
                    Platt I ─┴─► calibrated_prob
                             └─► decision (approve/mfa/block)
```

---

## 🔄 Dependencies Between Phases

```
Phase 1 (Foundation)
  ├─ Standalone - no dependencies
  └─ Produces: tabnet_embedding, device_embedding

Phase 2 (Context)
  ├─ Requires: Phase 1 embeddings
  └─ Produces: graph_embedding, seq_embedding

Phase 3 (Specialists)
  ├─ Requires: Phase 1 & 2 embeddings
  └─ Produces: synth_id_prob, ato_prob, recon_error

Phase 4 (Synthesis)
  ├─ Requires: Phase 1, 2, 3 outputs
  └─ Produces: calibrated_prob, decision
```

**Key Implication:** Must run phases in order (1→2→3→4). Cannot skip.

---

## 📈 Key Metrics & Thresholds

### Fraud Probability Thresholds

```
0.0 ──────────────────► 0.30 ──────────────────► 0.70 ──────────────────► 1.0
      APPROVE                    MFA                    BLOCK
     Low Risk              Medium Risk             High Risk
    Auto-approve        Require 2FA              Decline & Review
```

### Expected Performance

| Dataset | ROC-AUC | AP | F1@0.5 | Inference |
|---------|---------|----|----|-----------|
| IEEE-CIS | >0.95 | >0.85 | >0.75 | <50ms p99 |

---

## 🛠️ Configuration Reference

```python
from run_pipeline_phase_refactored import PipelineConfig

# Default config
cfg = PipelineConfig()

# Custom paths
cfg = PipelineConfig(
    data_root=Path("data"),
    model_root=Path("models"),
    feature_root=Path("features"),
)

# Custom device
cfg = PipelineConfig(device="cuda")  # GPU
cfg = PipelineConfig(device="cpu")   # CPU

# Custom data sources
cfg = PipelineConfig(
    ieee_txn_path="data/custom_txn.csv",
    ieee_id_path="data/custom_id.csv",
)

cfg.ensure_dirs()  # Create all required directories
```

---

## 📝 Model Training Checklist

- [ ] Phase 1: Run TabNet training
  - Check: `models/tabnet_finetuned.pt` exists
  - Check: DataFrame has `tabnet_logit` column
- [ ] Phase 1: Run Siamese training
  - Check: `models/siamese_device.pt` exists
  - Check: DataFrame has `device_embedding` column
- [ ] Phase 2: Run HeteroGNN training
  - Check: `models/hetero_gnn.pt` exists
  - Check: DataFrame has `txn_graph_logit` column
- [ ] Phase 2: Run SeqTransformer training
  - Check: DataFrame has `seq_anomaly_score` column
- [ ] Phase 3: Run SyntheticID training
  - Check: DataFrame has `synth_id_prob` column
- [ ] Phase 3: Run ATO Chain training
  - Check: DataFrame has `ato_prob` column
- [ ] Phase 3: Run Autoencoder training
  - Check: `models/tabular_ae.pt` exists
  - Check: DataFrame has `recon_error` column
- [ ] Phase 4: Run LightGBM stacking
  - Check: `models/lgbm_stacker.lgb` exists
  - Check: DataFrame has `raw_fraud_score` column
- [ ] Phase 4: Fit Platt calibrator
  - Check: `models/platt_calibrator.pt` exists
  - Check: DataFrame has `calibrated_prob` and `decision` columns
- [ ] Evaluation: Run metrics
  - Check: ROC-AUC > 0.85
  - Check: Calibration error < 0.02

---

## 🧪 Testing Checklist

- [ ] Run full test suite: `python test_fraud_detection_pipeline.py`
- [ ] Test single-row inference: `--test-inference`
- [ ] Test batch inference: `--test-batch`
- [ ] Test full pipeline: `--test-full`
- [ ] Generate synthetic data: `SyntheticDataGenerator.generate_mixed_dataset()`
- [ ] Check inference latency: time the `infer_single_row` call
- [ ] Validate decision distribution: Check approve/mfa/block counts

---

## 🔧 Common Operations

### Reload Trained Models (Without Retraining)

```python
from run_pipeline_phase_refactored import FraudDetectionInference, PipelineConfig

cfg = PipelineConfig()
# Models will be loaded from disk if they exist
inferrer = FraudDetectionInference(cfg)

# Ready for inference!
result = inferrer.infer_single_row(transaction)
```

### Train Only Phase 3

```python
import pandas as pd
from run_pipeline_phase_refactored import Phase3Specialists, PipelineConfig

# Load checkpoint from Phase 2
df = pd.read_parquet("data/processed/ieee_cis_with_graph.parquet")

# Train Phase 3
cfg = PipelineConfig()
phase3 = Phase3Specialists(cfg)
df = phase3.run(df)
```

### Batch Score Multiple Transactions

```python
from run_pipeline_phase_refactored import FraudDetectionInference, PipelineConfig
import pandas as pd

cfg = PipelineConfig()
inferrer = FraudDetectionInference(cfg)

# Load test transactions
df_test = pd.read_csv("test_transactions.csv")

# Score all
results = []
for _, row in df_test.iterrows():
    result = inferrer.infer_single_row(row.to_dict())
    results.append(result)

results_df = pd.DataFrame(results)
results_df.to_csv("predictions.csv", index=False)
```

---

## 🐛 Debugging Checklist

If something goes wrong:

1. **Check logs:**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Verify data:**
   ```python
   df = pd.read_csv("data/train_transaction.csv")
   print(f"Shape: {df.shape}, Fraud rate: {df['isFraud'].mean():.4f}")
   ```

3. **Test single phase:**
   ```python
   from run_pipeline_phase_refactored import Phase1Foundation, PipelineConfig
   phase1 = Phase1Foundation(PipelineConfig())
   df = phase1.run()
   ```

4. **Check model files:**
   ```python
   from pathlib import Path
   cfg = PipelineConfig()
   print(Path(cfg.tabnet_finetuned).exists())
   ```

5. **Test inference in isolation:**
   ```bash
   python test_fraud_detection_pipeline.py --test-inference
   ```

---

## 📚 Related Files

- `run_pipeline_phase_refactored.py` — Main orchestrator
- `test_fraud_detection_pipeline.py` — Test suite
- `models/models.py` — Model definitions (9 models A-I)
- `utils/constants.py` — Feature column definitions
- `PIPELINE_USAGE_GUIDE.md` — Detailed guide (this file)
- `ARCHITECTURE_SUMMARY.md` — High-level overview

---

## 🎓 Learning Path

### Beginner
1. Read this file (ARCHITECTURE_SUMMARY.md)
2. Read PIPELINE_USAGE_GUIDE.md "Quick Start" section
3. Run: `python test_fraud_detection_pipeline.py --test-inference`
4. Try: Copy-paste "Simple Inference" code above

### Intermediate
1. Follow "Training Guide" in PIPELINE_USAGE_GUIDE.md
2. Run: `python run_pipeline_phase_refactored.py PHASE_1`
3. Explore: `SyntheticDataGenerator` in test file
4. Debug: Use checklist above

### Advanced
1. Study model definitions in `models/models.py`
2. Modify Phase implementations in `run_pipeline_phase_refactored.py`
3. Add custom loss functions for specific patterns
4. Implement SHAP explainability

---

## 🚀 Next Steps

1. ✓ Implement 4-phase architecture → **DONE** ✓
2. → Train all 9 models on your IEEE-CIS data
3. → Validate metrics on test set
4. → Deploy inference API
5. → Monitor fraud detection in production
6. → Retrain monthly with new data

---

**Last Updated:** 2026-04-04
**Version:** 1.0 (4-Phase Architecture)

