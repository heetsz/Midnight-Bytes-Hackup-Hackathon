"""
graft_amiunique.py
──────────────────
Builds a device fingerprint registry from AmIUnique and grafts it
onto the IEEE-CIS processed DataFrame.
"""

import hashlib
import itertools
import os
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Tuple, List
import sys

# Ensure your utils are discoverable
sys.path.append(str(Path(__file__).parent.parent))
from utils.constants import DEVICE_FP_COLS, make_device_fp_hash

# ─────────────────────────────────────────────────────────────────────────────
# 1. BUILD DEVICE REGISTRY FROM AMIUNIQUE
# ─────────────────────────────────────────────────────────────────────────────

def create_toy_dataset(input_path: str, output_path: str, num_rows: int = 50000):
    """Instantly extracts the header and the first N rows into a new tiny CSV."""
    print(f"Extracting {num_rows} rows to {output_path}...")
    
    with open(input_path, 'r', encoding='utf-8', errors='ignore') as f_in, \
         open(output_path, 'w', encoding='utf-8') as f_out:
        
        for i in range(num_rows + 1):
            line = f_in.readline()
            if not line: 
                break 
            f_out.write(line)
            
    print("Done! Toy dataset created.")

def build_device_registry(amiunique_path: str) -> pd.DataFrame:
    """
    Load AmIUnique and create canonical device registry.
    Uses a toy dataset for rapid testing to avoid RAM crashes.
    """
    sample_path = "data/amiunique_sample.csv"
    
    # 1. Safely create the sample if it doesn't exist
    if not os.path.exists(sample_path):
        create_toy_dataset(
            input_path=amiunique_path, 
            output_path=sample_path, 
            num_rows=250000
        )
    
    print(f"Loading {sample_path} into Pandas...")

    with open(sample_path, 'r', encoding='utf-8', errors='ignore') as f:
        header = f.readline()
        print(f"Columns in AmIUnique sample: {header}")

    df = pd.read_csv(sample_path, sep='\t', low_memory=False)

    # Clean whitespace from headers just in case
    df.columns = df.columns.str.strip()

# 🟢 Updated to match the actual headers in your TSV 🟢
    rename_map = {
        "canvastest":       "canvas_hash",      # Was canvasHash
        "fp2_webglvendoe":  "webgl_vendor",     # Was webglVendor
        "osversion":        "tcp_os_signature", # Was tcpOsSignature
        "browser":          "id_31",            # Was browserFamily
        "resolution":       "id_33",            # Was screenResolution
        "device":           "DeviceType",       # Was deviceCategory
        "agent":            "DeviceInfo",       # Was userAgent
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

# --- NORMALIZATION BLOCK (AmIUnique Side) ---
    for col in ['id_31', 'DeviceType']:
        if col in df.columns:
            # Lowercase and take the first word (e.g., "Samsung Internet" -> "samsung")
            df[col] = df[col].astype(str).str.lower().str.split().str[0]
            # Replace common AmIUnique junk
            df[col] = df[col].replace(['none', 'unknown', '-9999^'], "")

    for col in DEVICE_FP_COLS:
        if col not in df.columns:
            df[col] = ""
        else:
            df[col] = df[col].fillna("").astype(str)

    df["device_fp_hash"] = df.apply(make_device_fp_hash, axis=1)

    registry = df.drop_duplicates(subset="device_fp_hash").copy()
    registry["device_obs_count"] = df.groupby("device_fp_hash")["device_fp_hash"]\
        .transform("count").loc[registry.index]

    print(f"[AmIUnique] Registry: {len(registry):,} unique devices from {len(df):,} sessions")
    return registry

# ─────────────────────────────────────────────────────────────────────────────
# 2. PARTIAL MATCH — same browser, different resolution
# ─────────────────────────────────────────────────────────────────────────────
# ─────────────────────────────────────────────────────────────────────────────
# 3. GRAFT ONTO IEEE-CIS DATAFRAME (FIXED)
# ─────────────────────────────────────────────────────────────────────────────

def make_shared_key(row: pd.Series) -> str:
    """Creates a join key based ONLY on features present in both datasets."""
    return "|".join([
        str(row.get("id_31", "")).strip(),
        str(row.get("id_33", "")).strip(),
        str(row.get("DeviceType", "")).strip()
    ]).lower()

def graft_device_features(ieee_df: pd.DataFrame, registry: pd.DataFrame) -> pd.DataFrame:
    # 1. Create the Shared Join Key on both dataframes
    ieee_df["shared_match_key"] = ieee_df.apply(make_shared_key, axis=1)
    registry["shared_match_key"] = registry.apply(make_shared_key, axis=1)
    
    # Deduplicate AmIUnique registry on the shared key to allow a clean Left Join
    reg_unique = registry.drop_duplicates("shared_match_key").copy()
    
    # 2. Graft the rich AmIUnique features onto IEEE-CIS
    # Drop overlapping columns from registry to prevent '_x' and '_y' suffixes
    cols_to_drop = ["id_31", "id_33", "DeviceType", "DeviceInfo", "device_fp_hash", "device_obs_count"]
    reg_merge = reg_unique.drop(columns=[c for c in cols_to_drop if c in reg_unique.columns])
    
    ieee_df = ieee_df.merge(reg_merge, on="shared_match_key", how="left")
    
    # Fill any remaining missing features with a sensible default before hashing
    for col in DEVICE_FP_COLS:
        if col not in ieee_df.columns:
            ieee_df[col] = "UNKNOWN"
        else:
            ieee_df[col] = ieee_df[col].fillna("UNKNOWN").astype(str)
            
    # 3. NOW calculate the final robust device_fp_hash for the IEEE data
    ieee_df["device_fp_hash"] = ieee_df.apply(make_device_fp_hash, axis=1)
    
    # 4. CALCULATE TRUE USER DEVICE HISTORY (device_match_ord)
    # Sort chronologically to ensure cumcount represents history correctly
    if "TransactionDT" in ieee_df.columns:
        ieee_df = ieee_df.sort_values(["user_key", "TransactionDT"])
    else:
        ieee_df = ieee_df.sort_values(["user_key", "TransactionID"])
        
    # Count how many times this user has used this specific device BEFORE this transaction
    ieee_df["user_device_history_count"] = ieee_df.groupby(["user_key", "device_fp_hash"]).cumcount()
    
    def _assign_match_ord(count):
        if count == 0: return 0      # 0 = First time user is seen on this device
        elif count < 3: return 1     # 1 = Seen recently
        else: return 2               # 2 = Trusted / Regular device
        
    ieee_df["device_match_ord"] = ieee_df["user_device_history_count"].apply(_assign_match_ord)
    
    # Map back to strings for your console log
    match_map_rev = {0: "none", 1: "partial", 2: "exact"}
    ieee_df["device_match_type"] = ieee_df["device_match_ord"].map(match_map_rev)
    
    # Calculate global device novelty (how rare is this device overall?)
    ieee_df["device_obs_count"] = ieee_df.groupby("device_fp_hash")["device_fp_hash"].transform("count")
    ieee_df["device_novelty"] = 1.0 / np.log1p(ieee_df["device_obs_count"] + 1)
    
    # Cleanup
    ieee_df = ieee_df.drop(columns=["shared_match_key", "user_device_history_count"])
    
    print(f"[AmIUnique] Match types: {ieee_df['device_match_type'].value_counts().to_dict()}")
    return ieee_df
# ─────────────────────────────────────────────────────────────────────────────
# 4. DEVICE-LEVEL FRAUD RATE
# ─────────────────────────────────────────────────────────────────────────────

def add_device_fraud_rate(ieee_df: pd.DataFrame) -> pd.DataFrame:
    """
    Computes device-level fraud stats using Leave-One-Out (LOO) encoding
    to prevent the LightGBM stacker from 'cheating' on the labels.
    """
    # 1. Calculate global sums per device
    dev_grouped = ieee_df.groupby("device_fp_hash")["isFraud"].agg(['sum', 'count'])
    
    # 2. Map back to main dataframe
    ieee_df = ieee_df.merge(dev_grouped.rename(columns={'sum': 'dev_total_fraud', 'count': 'dev_total_count'}), 
                            on="device_fp_hash", how="left")
    
    # 3. Leave-One-Out calculation: (Total_Fraud - Current_Fraud) / (Total_Count - 1)
    # We use a small smoothing factor (1e-5) to avoid division by zero
    ieee_df["device_fraud_rate"] = (ieee_df["dev_total_fraud"] - ieee_df["isFraud"]) / \
                                   (ieee_df["dev_total_count"] - 1).replace(0, 1)
    
    # Fill cases where device was only seen once with global mean
    global_mean = ieee_df["isFraud"].mean()
    ieee_df["device_fraud_rate"] = ieee_df["device_fraud_rate"].fillna(global_mean)
    
    # Clean up temp columns
    ieee_df = ieee_df.drop(columns=['dev_total_fraud', 'dev_total_count'])
    
    print(f"[AmIUnique] Leak-proof Device fraud rate merged (Mean: {ieee_df['device_fraud_rate'].mean():.4f})")
    return ieee_df

# ─────────────────────────────────────────────────────────────────────────────
# 5. SIAMESE TRAINING PAIR GENERATION (for Model B)
# ─────────────────────────────────────────────────────────────────────────────

def generate_siamese_pairs(
    ieee_df: pd.DataFrame,
    n_positive: int = 50_000,
    n_negative: int = 50_000,
    seed: int = 42
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    fp_cols = DEVICE_FP_COLS

    pairs = []

    # ── Positive pairs ──
    same_dev = ieee_df.groupby(["user_key","device_fp_hash"])["TransactionID"].count()
    same_dev = same_dev[same_dev >= 2].reset_index()
    pos_sample = same_dev.sample(min(n_positive, len(same_dev)), random_state=seed)
    for _, row in pos_sample.iterrows():
        pairs.append({
            "fp_hash_a":       row["device_fp_hash"],
            "fp_hash_b":       row["device_fp_hash"],
            "label":           1,
            "is_hard_negative": 0
        })
    # ── Hard negatives: "The Account Switcher" ──
    # Same Device, Different Users. This is a massive fraud signal.
    # Label = 0 (Not the same identity, even though device is the same)
    device_users = ieee_df.groupby("device_fp_hash")["user_key"].nunique()
    shared_devices = device_users[device_users > 1].index
    
    for dev in shared_devices[:n_negative // 2]:
        pairs.append({
            "fp_hash_a": dev,
            "fp_hash_b": dev,
            "label": 0,  # "Identity mismatch" on same hardware
            "is_hard_negative": 1
        })

    pairs_df = pd.DataFrame(pairs)

    # 🟢 FIXED CARTESIAN EXPLOSION: Safe 1-to-many merge logic 🟢
    device_lookup = ieee_df.drop_duplicates("device_fp_hash")[["device_fp_hash"] + fp_cols]

    for side in ("a", "b"):
        key_col = f"fp_hash_{side}"
        
        # Rename lookup columns to append _a or _b
        rename_dict = {"device_fp_hash": key_col}
        rename_dict.update({c: f"{c}_{side}" for c in fp_cols})
        
        right_df = device_lookup.rename(columns=rename_dict)
        
        # Merge directly onto pairs_df
        pairs_df = pairs_df.merge(right_df, on=key_col, how="left")

    print(f"[AmIUnique] Siamese pairs: {len(pairs_df):,} "
          f"(pos={pairs_df['label'].sum():,}, hard_neg={pairs_df['is_hard_negative'].sum():,})")
    return pairs_df

# ─────────────────────────────────────────────────────────────────────────────
# MASTER FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def process_amiunique(
    amiunique_path: str,
    ieee_df: pd.DataFrame,
    siamese_pairs_path: str = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    
    registry = build_device_registry(amiunique_path)
    ieee_df  = graft_device_features(ieee_df, registry)
    ieee_df  = add_device_fraud_rate(ieee_df)
    pairs_df = generate_siamese_pairs(ieee_df)

    if siamese_pairs_path:
        # Ensure directory exists before saving
        Path(siamese_pairs_path).parent.mkdir(parents=True, exist_ok=True)
        pairs_df.to_parquet(siamese_pairs_path, index=False)
        print(f"[AmIUnique] Siamese pairs saved to {siamese_pairs_path}")

    return ieee_df, pairs_df

if __name__ == "__main__":
    ieee_df = pd.read_parquet("data/processed/ieee_cis_processed.parquet")
    enriched, pairs = process_amiunique(
        amiunique_path="data/amiunique.csv",
        ieee_df=ieee_df,
        siamese_pairs_path="data/processed/siamese_pairs.parquet"
    )
    print(enriched[["device_match_type","device_novelty","device_fraud_rate"]].describe())