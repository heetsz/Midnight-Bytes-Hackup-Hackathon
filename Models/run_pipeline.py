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


def stage_5_train_models_og(cfg, ieee_df):
    """
    Train all neural models A-G in the correct dependency order.
    Returns feature_store DataFrame with all stacking columns.
    """
    import lightgbm as lgb
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score
    from models.models import (
        TabNetEncoder, DeviceFingerEncoder, TabularAutoEncoder,
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
    for col in ["TransactionAmt"] + [c for c in df.columns if c.startswith('C')]:
        if col in df.columns:
            df[col] = np.log1p(df[col])

    X = ieee_df[tab_feat_cols].fillna(0.0).values.astype(np.float32)
    y = ieee_df["isFraud"].values.astype(np.int64)
    N = len(ieee_df)

    feature_store = ieee_df[["TransactionID","user_key","isFraud"]].copy()

    # ── Model A: TabNet ──
    print("\n[Pipeline] Training Model A: TabNet...")
    tabnet = TabNetEncoder(in_dim=X.shape[1]).to(dev)

    # Phase 1: self-supervised pre-training (mask & reconstruct)
    if not Path(cfg["tabnet_pretrained"]).exists():
        opt = torch.optim.Adam(tabnet.parameters(), lr=2e-3)
        x_t = torch.tensor(X, device=dev)
        for ep in range(50):
            mask = (torch.rand_like(x_t) > 0.3).float()
            x_masked = x_t * mask
            emb = tabnet.encode(x_masked)
            # Reconstruction: project embedding back to input space
            recon = tabnet.classifier(emb)  # reuse head as projector
            loss = ((recon.unsqueeze(-1) - x_t[:, :1]) ** 2).mean()
            opt.zero_grad(); loss.backward(); opt.step()
        torch.save(tabnet.state_dict(), cfg["tabnet_pretrained"])
    else:
        tabnet.load_state_dict(torch.load(cfg["tabnet_pretrained"], map_location=dev))
        print("[Model A] Loaded pre-trained weights.")

    # Phase 2: supervised fine-tuning with OOF
    tabnet_logits_oof = np.zeros(N)
    tabnet_embeds_oof = np.zeros((N, 128), dtype=np.float32)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y)):
        print(f"  [Model A] Fold {fold+1}/5")
        model_f = TabNetEncoder(in_dim=X.shape[1]).to(dev)
        model_f.load_state_dict(tabnet.state_dict())

        opt = torch.optim.Adam(model_f.parameters(), lr=5e-4)
        xtr = torch.tensor(X[tr_idx], device=dev)
        ytr = torch.tensor(y[tr_idx], dtype=torch.float32, device=dev)
        pos_w = torch.tensor([(y == 0).sum() / max((y == 1).sum(), 1)], device=dev)

    # --- INJECT THIS INTO YOUR TRAINING LOOP ---
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

        model_f.eval()
        with torch.no_grad():
            xval = torch.tensor(X[val_idx], device=dev)
            val_out = model_f(xval)
            tabnet_logits_oof[val_idx] = val_out["logit"].cpu().numpy()
            tabnet_embeds_oof[val_idx] = val_out["embedding"].cpu().numpy()

    feature_store["tabnet_logit"] = tabnet_logits_oof
    print(f"[Model A] OOF AUC: {roc_auc_score(y, tabnet_logits_oof):.4f}")
    torch.save(tabnet.state_dict(), cfg["tabnet_finetuned"])

    # ── Model B: Siamese Device Encoder ──
    print("\n[Pipeline] Training Model B: Siamese Device Encoder...")
    # (Abbreviated — full training in graft_amiunique.py)
    # Load pairs and train; here we just store a placeholder dist_score
    # from the device_novelty + device_match_ord combination as proxy
    feature_store["device_dist_score"] = (
        ieee_df["device_novelty"].fillna(0) *
        (2 - ieee_df["device_match_ord"].fillna(0))
    ).values

    # ── Model C: Sequence Transformer (fine-tune on IEEE-CIS) ──
    print("\n[Pipeline] Fine-tuning Model C: Sequence Transformer on IEEE-CIS...")
    seq_model = BehavioralSequenceTransformer()
    if Path(cfg["seq_paysim_weights"]).exists():
        seq_model.load_state_dict(
            torch.load(cfg["seq_paysim_weights"], map_location="cpu")
        )
        print("[Model C] Loaded PaySim pre-trained weights.")
    # Anomaly score proxy from D-features (full seq training requires sequence collation)
    feature_store["seq_anomaly_score"] = (
        ieee_df["delta_t_norm"].fillna(0) *
        ieee_df["amt_zscore"].clip(-3,3).abs().fillna(0)
    ).values
    feature_store["paysim_boost"] = 1.0   # filled by compute_sequence_softboost

    # ── Model D: Tabular Autoencoder ──
    print("\n[Pipeline] Training Model D: Tabular Autoencoder...")
    legit_mask = y == 0
    ae_model   = TabularAutoEncoder(in_dim=X.shape[1]).to(dev)
    ae_opt     = torch.optim.Adam(ae_model.parameters(), lr=1e-3)
    x_legit    = torch.tensor(X[legit_mask], device=dev)

    if not Path(cfg["tabular_ae"]).exists():
        for ep in range(60):
            ae_model.train()
            perm = torch.randperm(x_legit.shape[0])[:2048]
            xb = x_legit[perm]
            out = ae_model(xb)
            loss = F.mse_loss(out["reconstruction"], xb)
            ae_opt.zero_grad(); loss.backward(); ae_opt.step()
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
    Full Neural Pipeline: Models A-I
    Handles GNN inference, Tabular AE, TabNet OOF, and LGBM Stacking.
    """
    import torch
    import torch.nn.functional as F
    import numpy as np
    import pandas as pd
    import json
    from pathlib import Path
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import roc_auc_score
    import lightgbm as lgb

    # Import custom models from your project structure
    from models.models import (
        TabNetEncoder, TabularAutoEncoder, HeteroGNN, 
        SyntheticIdentityDetector, PlattCalibrator
    )
    from utils.constants import V_COLS, C_COLS, D_COLS, M_COLS

    dev = torch.device(cfg["device"])
    N = len(ieee_df)
    feature_store = ieee_df[["TransactionID", "user_key", "isFraud"]].copy()

    # ── STEP 1: Model E - HeteroGNN Inference ──
    # We run this first so GNN features can be used by TabNet/AE
    print("\n[Stage 5] Running Model E: HeteroGNN Inference...")
    hetero_data = torch.load(cfg["hetero_graph"], map_location=dev)
    gnn_model = HeteroGNN(
        metadata=hetero_data.metadata(),
        hidden_channels=128,
        out_channels=2
    ).to(dev)

    if Path(cfg["gnn_model_path"]).exists():
        gnn_model.load_state_dict(torch.load(cfg["gnn_model_path"], map_location=dev))
    
    gnn_model.eval()
    with torch.no_grad():
        out, emb_dict = gnn_model(hetero_data.x_dict, hetero_data.edge_index_dict)
        txn_logits = out['transaction'][:, 1].cpu().numpy()
        txn_embs = emb_dict['transaction'].cpu().numpy()
    
    # Map embeddings to columns gnn_0...gnn_127
    gnn_cols = [f"gnn_{i}" for i in range(128)]
    gnn_df = pd.DataFrame(txn_embs, columns=gnn_cols, index=ieee_df.index)
    ieee_df = pd.concat([ieee_df, gnn_df], axis=1)
    feature_store["txn_graph_logit"] = txn_logits

    # ── STEP 2: Feature Matrix Prep ──
    tab_feat_cols = (
        [c for c in V_COLS + C_COLS + D_COLS + M_COLS if c in ieee_df.columns] +
        gnn_cols + 
        ["TransactionAmt", "amt_zscore", "delta_t_norm", "graph_risk_score", "ring_signal"]
    )
    
    # Log transform financial skews
    for col in ["TransactionAmt"] + [c for c in ieee_df.columns if c.startswith('C')]:
        if col in ieee_df.columns:
            ieee_df[col] = np.log1p(ieee_df[col])

    X = ieee_df[tab_feat_cols].fillna(0.0).values.astype(np.float32)
    y = ieee_df["isFraud"].values.astype(np.int64)

    # ── STEP 3: Model D - Tabular AutoEncoder ──
    print("\n[Stage 5] Training Model D: AutoEncoder...")
    ae_model = TabularAutoEncoder(in_dim=X.shape[1]).to(dev)
    ae_opt = torch.optim.Adam(ae_model.parameters(), lr=1e-3)
    x_legit = torch.tensor(X[y == 0], device=dev)

    for ep in range(30):
        ae_model.train()
        perm = torch.randperm(x_legit.size(0))
        for i in range(0, x_legit.size(0), 2048):
            xb = x_legit[perm[i:i+2048]]
            noise = torch.randn_like(xb) * 0.01
            recon = ae_model(xb + noise)["reconstruction"]
            loss = F.smooth_l1_loss(recon, xb)
            ae_opt.zero_grad(); loss.backward(); ae_opt.step()

    # Generate Recon Error feature
    ae_model.eval()
    recon_errs = []
    for i in range(0, N, 2048):
        with torch.no_grad():
            err = ae_model.reconstruction_error(torch.tensor(X[i:i+2048], device=dev))
            recon_errs.append(err.cpu().numpy())
    feature_store["recon_error"] = np.concatenate(recon_errs)

    # ── STEP 4: Model A - TabNet ──
    print("\n[Stage 5] Training Model A: TabNet (5-Fold OOF)...")
    tabnet_logits_oof = np.zeros(N)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    for fold, (tr_idx, val_idx) in enumerate(skf.split(X, y)):
        print(f"  > Fold {fold+1}")
        model_f = TabNetEncoder(in_dim=X.shape[1]).to(dev)
        opt = torch.optim.Adam(model_f.parameters(), lr=1e-3)
        xtr, ytr = torch.tensor(X[tr_idx], device=dev), torch.tensor(y[tr_idx], dtype=torch.float32, device=dev)
        
        for ep in range(25):
            model_f.train()
            perm = torch.randperm(xtr.size(0))
            for i in range(0, xtr.size(0), 2048):
                idx = perm[i:i+2048]
                loss = F.binary_cross_entropy_with_logits(model_f(xtr[idx])["logit"].view(-1), ytr[idx])
                opt.zero_grad(); loss.backward(); opt.step()
        
        model_f.eval()
        with torch.no_grad():
            tabnet_logits_oof[val_idx] = model_f(torch.tensor(X[val_idx], device=dev))["logit"].cpu().numpy()

    feature_store["tabnet_logit"] = tabnet_logits_oof

    print("[Model B] Computing Device Novelty via Siamese Triplet Distance...")
    device_model = DeviceFingerEncoder().to(dev)
    device_model.load_state_dict(torch.load(cfg["siamese_device_path"], map_location=dev))
    device_model.eval()
    
    # Extract cat/cont features as defined in Model B spec
    cat_feats = torch.tensor(ieee_df[cfg["device_cat_cols"]].values, dtype=torch.long, device=dev)
    cont_feats = torch.tensor(ieee_df[["device_match_ord", "device_novelcy"]].values, dtype=torch.float32, device=dev)
    
    with torch.no_grad():
        current_embs = device_model(cat_feats, cont_feats)
        # Assuming cfg["user_centroids"] is a pre-calculated mapping of user_key -> 64-dim mean embedding
        user_centroids = torch.tensor(np.stack(ieee_df["user_key"].map(cfg["centroid_map"]).values), device=dev)
        feature_store["device_dist_score"]

   # ── STEP 3: Model C - Sequence Transformer ──
    print("[Model C] Running Behavioral Transformer (PaySim Pre-trained)...")
    seq_model = BehavioralSequenceTransformer().to(dev)
    seq_model.load_state_dict(torch.load(cfg["seq_transformer_path"], map_location=dev))
    seq_model.eval()
    
    # Prepare sequence tensors from the ieee_df list-columns
    # x: [type_idx, log_amount, step_norm]
    seq_list = ieee_df["behavior_seq"].tolist() # List of lists of dicts
    from graft_paysim import _encode_sequences # Helper from your script
    sx, sm = _encode_sequences(seq_list) 
    
    with torch.no_grad():
        seq_out = seq_model(sx.to(dev), sm.to(dev))
        feature_store["seq_anomaly_score"] = seq_out["logits"].cpu().numpy()
        seq_embeds = seq_out["embedding"] # [N, 64]

    # Apply soft-boost from PaySim cluster similarity
    paysim_corpus = pd.read_parquet(cfg["paysim_seq_corpus"])
    boost_factors = compute_sequence_softboost(seq_list, paysim_corpus, seq_model, device=cfg["device"])
    feature_store["seq_anomaly_score"] *= boost_factors

    
   # ── STEP 6: Models F & G - Specialty Detectors ──
    print("[Models F & G] Running Synthetic & ATO Detectors...")
    # Model F: Synthetic Identity (Tabular + GNN)
    f_cols = ["M_fail_count","M_all_fail","card1","D1","D2","user_txn_count"] # as per spec
    X_f = torch.tensor(ieee_df[f_cols].fillna(0).values, dtype=torch.float32, device=dev)
    model_f = SyntheticIdentityDetector(tabular_dim=len(f_cols)).to(dev)
    model_f.load_state_dict(torch.load(cfg["synth_model_path"]))
    
    # Model G: ATO Chain (Seq + GNN + Scalars)
    g_scalars = torch.tensor(ieee_df[["device_match_ord","device_novelty","delta_t_norm",
                                      "txn_rank","amt_zscore","D1","D2","D3"]].values, dtype=torch.float32, device=dev)
    model_g = ATOChainDetector().to(dev)
    model_g.load_state_dict(torch.load(cfg["ato_model_path"]))

    model_f.eval(); model_g.eval()
    with torch.no_grad():
        feature_store["synth_id_prob"] = torch.sigmoid(model_f(X_f, txn_embs_raw)["logit"]).cpu().numpy()
        feature_store["ato_prob"] = torch.sigmoid(model_g(seq_embeds, txn_embs_raw, g_scalars)["logit"]).cpu().numpy()



    # ── STEP 6: Model H - LightGBM Stacker ──
    print("\n[Stage 5] Training Model H: LightGBM Stacker...")
    stack_cols = [
        "tabnet_logit", "txn_graph_logit", "recon_error", 
        "device_dist_score", "seq_anomaly_score", "synth_id_prob", "ato_prob", "ring_score"
    ]
    X_stack = feature_store[stack_cols].values
    lgbm_oof = np.zeros(N)
    
    for fold, (tr_idx, val_idx) in enumerate(skf.split(X_stack, y)):
        dtrain = lgb.Dataset(X_stack[tr_idx], y[tr_idx])
        params = {"objective": "binary", "metric": "auc", "verbosity": -1, "learning_rate": 0.05}
        bst = lgb.train(params, dtrain, num_boost_round=200)
        lgbm_oof[val_idx] = bst.predict(X_stack[val_idx])

    print(f"[Stacker] Final OOF AUC: {roc_auc_score(y, lgbm_oof):.4f}")

    # ── STEP 7: Model I - Platt Calibration ──
    print("\n[Stage 5] Fitting Model I: Platt Calibrator...")
    calibrator = PlattCalibrator()
    # Fit on a 10% holdout of the OOF scores
    cal_idx = int(N * 0.9)
    calibrator.fit(lgbm_oof[cal_idx:], y[cal_idx:])
    
    final_probs = calibrator(torch.tensor(lgbm_oof, dtype=torch.float32)).detach().numpy()
    feature_store["calibrated_prob"] = final_probs
    feature_store["decision"] = pd.cut(final_probs, bins=[-np.inf, 0.3, 0.7, np.inf], labels=["approve", "mfa", "block"])

    # Save and Return
    feature_store.to_parquet(cfg["feature_store"], index=False)
    return feature_store


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
    if ieee_df is None:
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
