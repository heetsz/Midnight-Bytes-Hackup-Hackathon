"""
build_hetero_graph.py
─────────────────────
Constructs the unified PyTorch Geometric HeteroData object
from all four processed datasets.

Node types:  user, transaction, device, card, email_domain, ip_cluster
Edge types:  7 relation types (see EDGE_TYPES below)

This graph is the input to Model E (HeteroGNN).
Node feature tensors also serve as initialization for Model A and B.
"""

import numpy as np
import pandas as pd
import torch
from pathlib import Path
from typing import Dict, Tuple
import sys

sys.path.append(str(Path(__file__).parent.parent))
from utils.constants import (
    V_COLS, C_COLS, D_COLS, M_COLS, CARD_COLS,
    DEVICE_FP_COLS, GNN_EMBED_DIM
)

try:
    from torch_geometric.data import HeteroData
    PYG_AVAILABLE = True
except ImportError:
    PYG_AVAILABLE = False
    print("WARNING: torch_geometric not installed. Graph will be dict-based.")

EDGE_TYPES = [
    ("user",         "initiated",    "transaction"),
    ("transaction",  "used",         "card"),
    ("transaction",  "from_device",  "device"),
    ("user",         "shares_device","user"),
    ("user",         "transferred",  "user"),
    ("transaction",  "same_email",   "email_domain"),
    ("user",         "near_ip",      "ip_cluster"),
]


# ─────────────────────────────────────────────────────────────────────────────
# NODE FEATURE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_user_features(df: pd.DataFrame) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, int]]:
    """
    User node features (one row per unique user_key).
    Features: GNN embedding [128] + user aggregate stats [8] + M_fail_count
    Total: 137 dims
    """
    user_cols = (
        [f"gnn_{i}" for i in range(GNN_EMBED_DIM)] +
        ["user_txn_count","user_amt_mean","user_amt_std","user_amt_max",
         "user_device_count","user_card_count","user_ip_count",
         "graph_risk_score","2nd_degree_fraud_rate",
         "shared_infrastructure_count","ring_signal","M_fail_count"]
    )

    user_df = df.drop_duplicates("user_key").set_index("user_key")
    user_id_map = {uid: i for i, uid in enumerate(user_df.index)}

    feat_cols = [c for c in user_cols if c in user_df.columns]
    feat = user_df[feat_cols].fillna(0.0).values.astype(np.float32)
    feat_tensor = torch.tensor(feat)

    # Labels: per-user fraud label (max isFraud across their transactions)
    user_labels = df.groupby("user_key")["isFraud"].max().reindex(user_df.index).fillna(0)
    label_tensor = torch.tensor(user_labels.values, dtype=torch.long)

    print(f"[Graph] User nodes: {feat_tensor.shape[0]:,}  feat_dim={feat_tensor.shape[1]}")
    return feat_tensor, label_tensor, user_id_map


def build_transaction_features(df: pd.DataFrame) -> Tuple[torch.Tensor, torch.Tensor, Dict[str, int]]:
    """
    Transaction node features.
    Features: V1-V339 (339) + C1-C14 (14) + D1-D15 (15) + TransactionAmt (1)
              + amt_zscore (1) + delta_t_norm (1) + txn_rank (1) = 372 dims
    """
    txn_df = df.set_index("TransactionID")
    txn_id_map = {tid: i for i, tid in enumerate(txn_df.index)}

    feat_cols = (
        [c for c in V_COLS if c in txn_df.columns] +
        [c for c in C_COLS if c in txn_df.columns] +
        [c for c in D_COLS if c in txn_df.columns] +
        ["TransactionAmt","amt_zscore","delta_t_norm","txn_rank"]
    )
    feat_cols = [c for c in feat_cols if c in txn_df.columns]
    feat = txn_df[feat_cols].fillna(0.0).values.astype(np.float32)
    feat_tensor = torch.tensor(feat)

    label_tensor = torch.tensor(
        txn_df["isFraud"].fillna(0).values.astype(np.int64)
    )

    print(f"[Graph] Transaction nodes: {feat_tensor.shape[0]:,}  feat_dim={feat_tensor.shape[1]}")
    return feat_tensor, label_tensor, txn_id_map


def build_device_features(df: pd.DataFrame) -> Tuple[torch.Tensor, Dict[str, int]]:
    """
    Device node features.
    Features: device_match_ord (1) + device_novelty (1) + device_obs_count (1)
              + device_fraud_rate (1) + device_txn_count (1) + device_user_count (1)
    Plus: encoded DEVICE_FP_COLS as label-encoded integers (7 cols)
    Total: 13 dims (lightweight — device gets most signal from graph structure)
    """
    dev_df = df.drop_duplicates("device_fp_hash").set_index("device_fp_hash")
    dev_id_map = {did: i for i, did in enumerate(dev_df.index)}

    scalar_cols = [
        "device_match_ord","device_novelty","device_obs_count",
        "device_fraud_rate","device_txn_count","device_user_count"
    ]
    scalar_cols = [c for c in scalar_cols if c in dev_df.columns]
    
    # Label encode device fingerprint columns safely
    try:
        cat_cols = [c for c in DEVICE_FP_COLS if c in dev_df.columns]
    except NameError:
        cat_cols = []
        
    non_numeric_cols = dev_df[cat_cols].select_dtypes(exclude=[np.number]).columns
    for col in non_numeric_cols:
        dev_df[col] = pd.Categorical(dev_df[col]).codes.astype(np.float32)

    all_feat_cols = scalar_cols + cat_cols
    feat = dev_df[all_feat_cols].fillna(0.0).values.astype(np.float32)
    feat_tensor = torch.tensor(feat)

    print(f"[Graph] Device nodes: {feat_tensor.shape[0]:,}  feat_dim={feat_tensor.shape[1]}")
    return feat_tensor, dev_id_map


def build_card_features(df: pd.DataFrame) -> Tuple[torch.Tensor, Dict[str, int]]:
    card_df = df.drop_duplicates("card_key").set_index("card_key")
    card_id_map = {cid: i for i, cid in enumerate(card_df.index)}

    # 1. Get all available card columns (DO NOT pop card4 or card6)
    feat_cols = [c for c in CARD_COLS if c in card_df.columns]
    
    # 2. Automatically find all non-numeric columns
    cat_cols = card_df[feat_cols].select_dtypes(exclude=[np.number]).columns
    
    # 3. Label-encode those specific categorical columns in place
    for col in cat_cols:
        card_df[col] = pd.Categorical(card_df[col]).codes.astype(np.float32)
            
    # 4. Fill NaNs and convert everything to a float32 tensor
    feat = card_df[feat_cols].fillna(-1.0).values.astype(np.float32)
    feat_tensor = torch.tensor(feat)

    print(f"[Graph] Card nodes: {feat_tensor.shape[0]:,}  feat_dim: {feat_tensor.shape[1]}")
    return feat_tensor, card_id_map


def build_email_features(df: pd.DataFrame) -> Tuple[torch.Tensor, Dict[str, int]]:
    """Email domain nodes: fraud rate + transaction count per domain."""
    email_stats = pd.concat([
        df[["P_emaildomain","isFraud","TransactionID"]].rename(columns={"P_emaildomain":"domain"}),
        df[["R_emaildomain","isFraud","TransactionID"]].rename(columns={"R_emaildomain":"domain"})
    ]).dropna(subset=["domain"])

    domain_df = email_stats.groupby("domain").agg(
        email_fraud_rate = ("isFraud","mean"),
        email_txn_count  = ("TransactionID","count"),
    )
    email_id_map = {dom: i for i, dom in enumerate(domain_df.index)}
    feat = domain_df.values.astype(np.float32)
    feat_tensor = torch.tensor(feat)

    print(f"[Graph] EmailDomain nodes: {feat_tensor.shape[0]:,}")
    return feat_tensor, email_id_map


def build_ip_features(df: pd.DataFrame) -> Tuple[torch.Tensor, Dict[str, int]]:
    ip_stats = df.groupby("ip_cluster_key").agg(
        ip_fraud_rate  = ("isFraud","mean"),
        ip_user_count  = ("user_key","nunique"),
        ip_txn_count   = ("TransactionID","count"),
    )
    ip_id_map = {ip: i for i, ip in enumerate(ip_stats.index)}
    feat = ip_stats.values.astype(np.float32)
    feat_tensor = torch.tensor(feat)

    print(f"[Graph] IPCluster nodes: {feat_tensor.shape[0]:,}")
    return feat_tensor, ip_id_map


# ─────────────────────────────────────────────────────────────────────────────
# EDGE BUILDERS
# ─────────────────────────────────────────────────────────────────────────────

def build_edges(
    df: pd.DataFrame,
    paysim_edges: pd.DataFrame,
    user_id_map:  Dict,
    txn_id_map:   Dict,
    dev_id_map:   Dict,
    card_id_map:  Dict,
    email_id_map: Dict,
    ip_id_map:    Dict,
) -> Dict:
    """
    Returns dict mapping edge_type_name → (src_tensor, dst_tensor, attr_tensor).
    """
    edges = {}

    def _ids(series, id_map):
        return torch.tensor(
            [id_map.get(v, 0) for v in series],
            dtype=torch.long
        )

    # 1. User → Transaction (INITIATED)
    valid = df[df["user_key"].isin(user_id_map) &
               df["TransactionID"].astype(str).isin(txn_id_map)]
    edges["user__initiated__transaction"] = (
        _ids(valid["user_key"], user_id_map),
        _ids(valid["TransactionID"].astype(str), txn_id_map),
        torch.tensor(np.log1p(valid["TransactionAmt"].fillna(0).values), dtype=torch.float32)
    )

    # 2. Transaction → Card (USED)
    valid = df[df["TransactionID"].astype(str).isin(txn_id_map) &
               df["card_key"].isin(card_id_map)]
    edges["transaction__used__card"] = (
        _ids(valid["TransactionID"].astype(str), txn_id_map),
        _ids(valid["card_key"], card_id_map),
        None
    )

    # 3. Transaction → Device (FROM_DEVICE)
    valid = df[df["TransactionID"].astype(str).isin(txn_id_map) &
               df["device_fp_hash"].isin(dev_id_map)]
               
    # SAFELY HANDLE MISSING device_novelty
    if "device_novelty" in valid.columns:
        device_attr = torch.tensor(valid["device_novelty"].fillna(0).values, dtype=torch.float32)
    else:
        print("[Graph] Warning: 'device_novelty' column missing. Defaulting to 0.0")
        device_attr = torch.zeros(len(valid), dtype=torch.float32)

    edges["transaction__from_device__device"] = (
        _ids(valid["TransactionID"].astype(str), txn_id_map),
        _ids(valid["device_fp_hash"], dev_id_map),
        device_attr
    )

    # 4. User → User (SHARES_DEVICE)
    # Get unique user-device pairs
    user_dev = df[["user_key", "device_fp_hash"]].drop_duplicates().dropna()

    # --- MEMORY PROTECTION BLOCK ---
    # Count how many users use each device
    dev_counts = user_dev["device_fp_hash"].value_counts()

    # Thresholds: 
    # Min 2 users (to be a 'share'), Max 50 users (to avoid generic 'hairball' devices)
    valid_devices = dev_counts[(dev_counts >= 2) & (dev_counts <= 50)].index
    
    # Filter to only 'rare' shared devices before merging
    user_dev_filtered = user_dev[user_dev["device_fp_hash"].isin(valid_devices)]
    # -------------------------------

    # Perform the self-join on the pruned set
    merged = user_dev_filtered.merge(
        user_dev_filtered, 
        on="device_fp_hash", 
        suffixes=("_a", "_b")
    )

    # Remove self-loops (User A sharing with User A)
    merged = merged[merged["user_key_a"] != merged["user_key_b"]]

    # Ensure keys exist in our map
    merged = merged[
        merged["user_key_a"].isin(user_id_map) &
        merged["user_key_b"].isin(user_id_map)
    ]

    edges["user__shares_device__user"] = (
        _ids(merged["user_key_a"], user_id_map),
        _ids(merged["user_key_b"], user_id_map),
        None
    )
    print(f"[Graph] shares_device edges (pruned): {len(merged):,}")

    # 5. User → User (TRANSFERRED)
    if paysim_edges is not None and len(paysim_edges) > 0:
        all_ps_users = pd.unique(
            paysim_edges[["src_user_id","dst_user_id"]].values.ravel()
        )
        ps_id_map = {u: i for i, u in enumerate(all_ps_users)}

        valid_ps = paysim_edges[
            paysim_edges["src_user_id"].isin(ps_id_map) &
            paysim_edges["dst_user_id"].isin(ps_id_map)
        ]
        edges["paysim_user__transferred__paysim_user"] = (
            _ids(valid_ps["src_user_id"], ps_id_map),
            _ids(valid_ps["dst_user_id"], ps_id_map),
            torch.tensor(valid_ps["log_amount"].values, dtype=torch.float32)
        )
        print(f"[Graph] PaySim transfer edges: {len(valid_ps):,}")

    # 6. Transaction → EmailDomain (SAME_EMAIL)
    for side in ["P", "R"]:
        col = f"{side}_emaildomain"
        if col in df.columns:
            valid = df[df["TransactionID"].astype(str).isin(txn_id_map) &
                       df[col].isin(email_id_map)]
            key = f"transaction__same_email_{side.lower()}__email_domain"
            edges[key] = (
                _ids(valid["TransactionID"].astype(str), txn_id_map),
                _ids(valid[col], email_id_map),
                None
            )

    # 7. User → IPCluster (NEAR_IP)
    valid = df[df["user_key"].isin(user_id_map) &
               df["ip_cluster_key"].isin(ip_id_map)]
    edges["user__near_ip__ip_cluster"] = (
        _ids(valid["user_key"], user_id_map),
        _ids(valid["ip_cluster_key"], ip_id_map),
        None
    )

    return edges


# ─────────────────────────────────────────────────────────────────────────────
# ASSEMBLE HETERODATA
# ─────────────────────────────────────────────────────────────────────────────

def build_hetero_graph(
    ieee_df:      pd.DataFrame,
    paysim_edges: pd.DataFrame,
    save_path:    str = None
):
    """
    Master function. Returns a PyG HeteroData (or dict fallback).
    """
    print("\n=== Building Heterogeneous Graph ===")

    user_feat, user_labels, user_id_map = build_user_features(ieee_df)
    txn_feat,  txn_labels,  txn_id_map  = build_transaction_features(ieee_df)
    dev_feat,               dev_id_map  = build_device_features(ieee_df)
    card_feat,              card_id_map = build_card_features(ieee_df)
    email_feat,             email_id_map= build_email_features(ieee_df)
    ip_feat,                ip_id_map   = build_ip_features(ieee_df)
    
    print("\n[Graph] Finished building node features.\n")
    
    edge_dict = build_edges(
        ieee_df, paysim_edges,
        user_id_map, txn_id_map, dev_id_map,
        card_id_map, email_id_map, ip_id_map
    )
    print("\n[Graph] Finished building edges.\n")

    if PYG_AVAILABLE:
        data = HeteroData()

        data["user"].x        = user_feat
        data["user"].y        = user_labels
        data["transaction"].x = txn_feat
        data["transaction"].y = txn_labels
        data["device"].x      = dev_feat
        data["card"].x        = card_feat
        data["email_domain"].x = email_feat
        data["ip_cluster"].x  = ip_feat

        for etype, (src, dst, attr) in edge_dict.items():
            parts = etype.split("__")
            if len(parts) == 3:
                src_type, rel, dst_type = parts
                data[src_type, rel, dst_type].edge_index = torch.stack([src, dst])
                if attr is not None:
                    data[src_type, rel, dst_type].edge_attr = attr

        if save_path:
            torch.save(data, save_path)
            print(f"[Graph] Saved HeteroData to {save_path}")

        print(f"[Graph] Node types: {data.node_types}")
        print(f"[Graph] Edge types: {data.edge_types}")
        return data

    else:
        # Dict fallback for environments without PyG
        graph = {
            "nodes": {
                "user":         {"x": user_feat,  "y": user_labels},
                "transaction":  {"x": txn_feat,   "y": txn_labels},
                "device":       {"x": dev_feat},
                "card":         {"x": card_feat},
                "email_domain": {"x": email_feat},
                "ip_cluster":   {"x": ip_feat},
            },
            "edges":    edge_dict,
            "id_maps":  {
                "user":         user_id_map,
                "transaction":  txn_id_map,
                "device":       dev_id_map,
                "card":         card_id_map,
                "email_domain": email_id_map,
                "ip_cluster":   ip_id_map,
            }
        }
        if save_path:
            torch.save(graph, save_path)
        return graph



if __name__ == "__main__":
    ieee_df      = pd.read_parquet("data/processed/ieee_cis_with_graph.parquet")
    
    # FIXED: Replaced list().filter() with list comprehension
    non_v_cols = [c for c in ieee_df.columns if not c.startswith("V")]
    print(non_v_cols)
    
    paysim_edges = pd.read_parquet("data/processed/paysim_edges.parquet") \
        if Path("data/processed/paysim_edges.parquet").exists() else None

    graph = build_hetero_graph(
        ieee_df, paysim_edges,
        save_path="data/processed/hetero_graph.pt"
    )