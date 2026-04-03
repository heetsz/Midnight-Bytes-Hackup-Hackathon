"""
graft_ieee_cis.py
─────────────────
Transforms raw IEEE-CIS train_transaction + train_identity into a
single enriched DataFrame that is the backbone of the whole system.

Changes made vs raw data:
  1. Join train_transaction ⋈ train_identity on TransactionID
  2. Compute stable user_key (card + addr + email hash)
  3. Compute device_fp_hash (AmIUnique join key)
  4. Compute card_key and ip_cluster_key (graph node IDs)
  5. Parse gnn_node_embedding JSON → float32 array column
  6. Add V-feature missingness indicator flags
  7. Compute per-user transaction deltas (relative time)
  8. M-feature binarisation (Y→1, N→0, nan→-1)
  9. Derive synthetic_identity_flag (for Model F labels)
 10. Build user-level aggregate stats (rolling fraud signal)
"""

import json
import hashlib
import numpy as np
import pandas as pd
from pathlib import Path
import sys
sys.path.append(str(Path(__file__).parent.parent))
from utils.constants import (
    V_COLS, C_COLS, D_COLS, M_COLS, CARD_COLS,
    make_user_key, make_device_fp_hash, make_card_key,
    make_ip_cluster_key, GNN_EMBED_DIM
)


# ─────────────────────────────────────────────────────────────────────────────
# 1. LOAD & JOIN
# ─────────────────────────────────────────────────────────────────────────────

def load_and_join(txn_path: str, identity_path: str) -> pd.DataFrame:
    """
    Left-join identity onto transaction.
    Includes normalization to ensure AmIUnique grafting works.
    """
    txn = pd.read_csv(txn_path)
    idn = pd.read_csv(identity_path)

    # Standardise column name casing
    txn.columns = txn.columns.str.strip()
    idn.columns = idn.columns.str.strip()

    # --- NEW NORMALIZATION BLOCK (IEEE Side) ---
    # We target 'id_31' (Browser) and 'DeviceType' specifically for the graft
    for col in ['id_31', 'DeviceType']:
        if col in idn.columns:
            # 1. Lowercase
            # 2. Split by space and take first word (e.g. "Chrome 62" -> "chrome")
            # 3. Replace null-like strings with empty string
            idn[col] = idn[col].astype(str).str.lower().str.split().str[0]
            idn[col] = idn[col].replace(['nan', 'null', 'none', 'unknown', '-9999^'], "")
    
    # Optional: Do the same for resolution (id_33) if you use it in the hash
    if 'id_33' in idn.columns:
        idn['id_33'] = idn['id_33'].astype(str).str.lower().replace(['nan', 'null'], "")

    df = txn.merge(idn, on="TransactionID", how="left")
    print(f"[IEEE-CIS] Joined & Normalized: {len(df):,} rows")
    return df

# ─────────────────────────────────────────────────────────────────────────────
# 2. ENTITY KEYS
# ─────────────────────────────────────────────────────────────────────────────

def add_entity_keys(df: pd.DataFrame) -> pd.DataFrame:
    """Add user_key, device_fp_hash, card_key, ip_cluster_key."""
    df_ = pd.DataFrame(index=df.index)
    df_["user_key"]       = df.apply(make_user_key,       axis=1)
    df_["device_fp_hash"] = df.apply(make_device_fp_hash, axis=1)
    df_["card_key"]       = df.apply(make_card_key,       axis=1)
    df_["ip_cluster_key"] = df.apply(make_ip_cluster_key, axis=1)

    df = pd.concat([df, df_], axis=1)

    df = df.copy() 
    
    n_users   = df["user_key"].nunique()
    n_devices = df["device_fp_hash"].nunique()
    print(f"[IEEE-CIS] Unique users: {n_users:,}  |  devices: {n_devices:,}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 3. GNN EMBEDDING PARSING
# ─────────────────────────────────────────────────────────────────────────────

def parse_gnn_embedding(df: pd.DataFrame) -> pd.DataFrame:
    """
    gnn_node_embedding is stored as a JSON string array.
    Parse to float32 and expand into GNN_EMBED_DIM named columns
    (gnn_0 … gnn_127) so standard ML libs can consume them.
    Also keep the raw column for PyG node init.
    """
    def _parse(val):
        if pd.isna(val) or val == "":
            return np.zeros(GNN_EMBED_DIM, dtype=np.float32)
        try:
            arr = np.array(json.loads(val), dtype=np.float32)
            if len(arr) < GNN_EMBED_DIM:
                arr = np.pad(arr, (0, GNN_EMBED_DIM - len(arr)))
            return arr[:GNN_EMBED_DIM]
        except Exception:
            return np.zeros(GNN_EMBED_DIM, dtype=np.float32)

    if "gnn_node_embedding" in df.columns:
        embeddings = np.vstack(df["gnn_node_embedding"].apply(_parse).values)
        gnn_cols = [f"gnn_{i}" for i in range(GNN_EMBED_DIM)]
        gnn_df = pd.DataFrame(embeddings, columns=gnn_cols, index=df.index)
        df = pd.concat([df, gnn_df], axis=1)
        df = df.copy() 
        print(f"[IEEE-CIS] GNN embedding parsed → {GNN_EMBED_DIM} columns")
    else:
        print("[IEEE-CIS] WARNING: gnn_node_embedding not found, zeroing out")
        gnn_cols = [f"gnn_{i}" for i in range(GNN_EMBED_DIM)]
        zero_data = np.zeros((len(df), GNN_EMBED_DIM), dtype=np.float32)
        gnn_df = pd.DataFrame(zero_data, columns=gnn_cols, index=df.index)
        
        df = pd.concat([df, gnn_df], axis=1)
        df = df.copy()     
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 4. MISSINGNESS INDICATOR FLAGS FOR V-FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def add_missingness_flags(df: pd.DataFrame) -> pd.DataFrame:
    """
    For V1–V339: add binary 'V{i}_missing' flag before any imputation.
    The missingness pattern itself is a fraud signal — do NOT impute silently.
    Then fill NaN with 0 (median of most V-cols is near 0 after the flag exists).
    """
    high_miss = []
    for col in V_COLS:
        if col in df.columns:
            miss_rate = df[col].isna().mean()
            df[f"{col}_missing"] = df[col].isna().astype(np.int8)
            if miss_rate > 0.5:
                high_miss.append(col)
            df[col] = df[col].fillna(0.0)
        df = df.copy()

    df = df.copy() 

    print(f"[IEEE-CIS] V-missingness flags added. High-miss (>50%): {len(high_miss)} columns")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 5. M-FEATURE BINARISATION
# ─────────────────────────────────────────────────────────────────────────────

def binarise_m_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    M1–M9 are Y/N/nan categorical.
    Encode: Y→1, N→0, nan→-1.
    -1 is meaningful: missing match flag = bank didn't validate = suspicious.
    Also compute M_fail_count = number of fields that are N or nan.
    """
    m_map = {"Y": 1, "T": 1, "F": 0, "N": 0}
    for col in M_COLS:
        if col in df.columns:
            df[col] = df[col].map(m_map).fillna(-1).astype(np.int8)

    # Count of failed / missing verifications per transaction
    df["M_fail_count"] = (df[[c for c in M_COLS if c in df.columns]] <= 0).sum(axis=1)
    df["M_all_fail"]   = (df["M_fail_count"] >= 6).astype(np.int8)
    df = df.copy()
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 6. RELATIVE TIME FEATURES
# ─────────────────────────────────────────────────────────────────────────────

def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy() 
    df = df.sort_values(["user_key", "TransactionDT"])

    # Basic ranking and delta
    df["txn_rank"]  = df.groupby("user_key").cumcount()
    df["delta_t"]   = df.groupby("user_key")["TransactionDT"].diff().fillna(0)

    # Use transform instead of apply to avoid losing columns
    group = df.groupby("user_key")["delta_t"]
    df_min = group.transform("min")
    df_max = group.transform("max")
    
    # Vectorized normalization: (x - min) / (max - min)
    # handles the div by zero case with np.where
    denom = df_max - df_min
    df["delta_t_norm"] = np.where(denom != 0, (df["delta_t"] - df_min) / denom, 0.0)

    # Final consolidation
    df = df.copy()
    print(f"[IEEE-CIS] Time features computed. Shape: {df.shape}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 6.5 DEVICE NOVELTY
# ─────────────────────────────────────────────────────────────────────────────

def engineer_device_novelty(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates how 'new' a device is based on the first time it was seen.
    High novelty (near 1.0) = First time seeing this device (high risk).
    Low novelty (near 0.0) = Device has been around for months.
    """
    df = df.copy()
    df = df.sort_values("TransactionDT")
    
    # Find the very first time each device was ever seen
    first_seen = df.groupby("device_fp_hash")["TransactionDT"].transform("min")
    
    # Calculate days since first seen (TransactionDT is in seconds)
    days_since_first_seen = (df["TransactionDT"] - first_seen) / 86400.0
    
    # Apply exponential decay (30-day half-life)
    df["device_novelty"] = np.exp(-days_since_first_seen / 30.0)
    
    # Fill NaNs with 0.0 (for transactions missing device info)
    df["device_novelty"] = df["device_novelty"].fillna(0.0).astype(np.float32)
    
    print(f"[IEEE-CIS] Device novelty engineered. Shape: {df.shape}")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 7. USER-LEVEL AGGREGATE STATS
# ─────────────────────────────────────────────────────────────────────────────

def add_user_aggregates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build rolling per-user stats that feed behavioral profile store.
    These are computed on the TRAINING split only; at inference they
    come from an online Redis store updated per transaction.
    """

    if "user_key" not in df.columns:
        if "user_key" in df.index.names:
            df = df.reset_index()
        else:
            # Debugging print if it's truly gone
            print(f"DEBUG: Current Columns: {df.columns.tolist()[:5]}")
            print(f"DEBUG: Current Index: {df.index.name}")
            raise KeyError("user_key is completely missing from columns and index.")

    df = df.copy()
    user_stats = df.groupby("user_key").agg(
        user_txn_count      = ("TransactionID",  "count"),
        user_amt_mean       = ("TransactionAmt",  "mean"),
        user_amt_std        = ("TransactionAmt",  "std"),
        user_amt_max        = ("TransactionAmt",  "max"),
        user_fraud_rate     = ("isFraud",         "mean"),   # label leakage guard: use only in offline eval
        user_device_count   = ("device_fp_hash",  "nunique"),
        user_card_count     = ("card_key",         "nunique"),
        user_ip_count       = ("ip_cluster_key",   "nunique"),
    ).reset_index()

    df = df.merge(user_stats, on="user_key", how="left")
    df = df.copy()

    # Amount z-score within user: key ATO signal (sudden large transaction)
    df["amt_zscore"] = (
        (df["TransactionAmt"] - df["user_amt_mean"]) /
        df["user_amt_std"].replace(0, 1)
    )
    print("[IEEE-CIS] User aggregate stats merged")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# 8. SYNTHETIC IDENTITY LABEL (for Model F supervision)
# ─────────────────────────────────────────────────────────────────────────────

def derive_synthetic_identity_label(df: pd.DataFrame) -> pd.DataFrame:
    """
    Heuristic label for synthetic identity detection.
    A transaction is flagged as synthetic_identity if ALL of:
      - isFraud == 1
      - M_fail_count >= 5  (most identity checks failed / missing)
      - user_txn_count <= 3  (very new account — D1 or txn_rank near 0)
      - P_emaildomain contains throwaway patterns OR is NaN
    This creates a derived label for Model F without requiring separate annotation.
    ~3-8% of fraud rows will qualify; treat as positive, rest as negative.
    """
    throwaway_domains = {
        "gmail.com", "yahoo.com", "hotmail.com", "protonmail.com",
        "guerrillamail.com", "mailinator.com", "tempmail.com", ""
    }

    email_throwaway = df["P_emaildomain"].fillna("").isin(throwaway_domains)

    df["synthetic_identity_label"] = (
        (df.get("isFraud", pd.Series(0, index=df.index)) == 1) &
        (df["M_fail_count"] >= 5) &
        (df.get("user_txn_count", pd.Series(999, index=df.index)) <= 3) &
        email_throwaway
    ).astype(np.int8)

    n_synth = df["synthetic_identity_label"].sum()
    print(f"[IEEE-CIS] Synthetic identity labels derived: {n_synth:,} positives")
    return df


# ─────────────────────────────────────────────────────────────────────────────
# MASTER FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def process_ieee_cis(
    txn_path: str,
    identity_path: str,
    out_path: str = None
) -> pd.DataFrame:
    df = load_and_join(txn_path, identity_path)
    df = df[:100000].copy()
    print(f"[IEEE-CIS] Initial shape after join: {df.shape}")
    # for col in df.columns:
        # print(f"  {col}: {df[col].isna().sum()}")
    df = add_entity_keys(df)
    print(f"[IEEE-CIS] Shape after adding entity keys: {df.shape}")
    df = parse_gnn_embedding(df)
    print(f"[IEEE-CIS] Shape after parsing GNN embeddings: {df.shape}")
    df = add_missingness_flags(df)
    print(f"[IEEE-CIS] Shape after adding missingness flags: {df.shape}")
    df = binarise_m_features(df)
    print(f"[IEEE-CIS] Shape after binarising M features: {df.shape}")
    df = add_time_features(df)
    print(f"[IEEE-CIS] Shape after adding time features: {df.shape}")
    df = engineer_device_novelty(df)
    print(f"[IEEE-CIS] Shape after engineering device novelty: {df.shape}")
    df = add_user_aggregates(df)
    print(f"[IEEE-CIS] Shape after adding user aggregates: {df.shape}")
    df = derive_synthetic_identity_label(df)
    print(f"[IEEE-CIS] Shape after deriving synthetic identity label: {df.shape}")

    if out_path:
        # Save without the wide GNN columns to keep parquet manageable
        # (gnn_0…gnn_127 stored separately as .npy for PyG)
        gnn_cols = [f"gnn_{i}" for i in range(GNN_EMBED_DIM)]
        df.drop(columns=gnn_cols).to_parquet(out_path, index=False)
        np.save(out_path.replace(".parquet", "_gnn_embeddings.npy"),
                df[gnn_cols].values.astype(np.float32))
        print(f"[IEEE-CIS] Saved to {out_path}")

    print(f"[IEEE-CIS] Final shape: {df.shape}")
    return df


if __name__ == "__main__":
    # Usage: python graft_ieee_cis.py
    df = process_ieee_cis(
        txn_path="data/train_transaction.csv",
        identity_path="data/train_identity.csv",
        out_path="data/processed/ieee_cis_processed.parquet"
    )
    print(df[["user_key","device_fp_hash","M_fail_count","synthetic_identity_label","isFraud"]].head())
