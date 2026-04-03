"""
constants.py
Shared column definitions, entity key constructors, and type maps.
Import this everywhere — never hardcode column names inline.
"""
import hashlib
import pandas as pd
import numpy as np

# ─── Column groups (IEEE-CIS) ────────────────────────────────────────────────
V_COLS   = [f"V{i}"  for i in range(1, 340)]
C_COLS   = [f"C{i}"  for i in range(1, 15)]
D_COLS   = [f"D{i}"  for i in range(1, 16)]
M_COLS   = [f"M{i}"  for i in range(1, 10)]
CARD_COLS = [f"card{i}" for i in range(1, 7)]

DEVICE_FP_COLS = [
    "canvas_hash", "webgl_vendor", "tcp_os_signature",
    "id_31", "id_33", "DeviceType", "DeviceInfo"
]

GRAPH_COLS = [
    "shared_infrastructure_count", "2nd_degree_fraud_rate",
    "gnn_node_embedding", "graph_risk_score"
]

IDENTITY_COLS = DEVICE_FP_COLS + [
    "id_01","id_02","id_03","id_04","id_05","id_06","id_07","id_08","id_09",
    "id_10","id_11","id_12","id_13","id_14","id_15","id_16","id_17","id_18",
    "id_19","id_20","id_21","id_22","id_23","id_24","id_25","id_26","id_27",
    "id_28","id_29","id_30","id_32","id_34","id_35","id_36","id_37","id_38",
]

# ─── Entity key constructors ──────────────────────────────────────────────────
def make_user_key(row: pd.Series) -> str:
    # Use card + addr1 as the primary anchor, email as secondary
    card = str(row.get("card1", "")) + str(row.get("card2", ""))
    addr = str(row.get("addr1", "null"))
    email = str(row.get("P_emaildomain", "null"))
    
    raw = f"{card}|{addr}|{email}"
    return "U_" + hashlib.md5(raw.encode()).hexdigest()[:16]


def make_device_fp_hash(row: pd.Series) -> str:
    """
    Canonical device fingerprint hash.
    Matches IEEE-CIS identity fields to AmIUnique registry entries.
    """
    raw = "|".join([
        str(row.get("canvas_hash", "")),
        str(row.get("webgl_vendor", "")),
        str(row.get("tcp_os_signature", "")),
        str(row.get("id_31", "")),
        str(row.get("id_33", "")),
        str(row.get("DeviceType", "")),
        str(row.get("DeviceInfo", "")),
    ])
    return "D_" + hashlib.md5(raw.encode()).hexdigest()[:16]


def make_card_key(row: pd.Series) -> str:
    """Card node: BIN (card1) + card network (card6) + card type (card4)."""
    raw = "|".join([
        str(row.get("card1", "")),
        str(row.get("card4", "")),
        str(row.get("card6", "")),
    ])
    return "C_" + hashlib.md5(raw.encode()).hexdigest()[:16]


def make_ip_cluster_key(row: pd.Series) -> str:
    """
    IP cluster: bin addr1/addr2. 
    Handles NaN by returning a dedicated 'UNKNOWN' bucket.
    """
    a1_raw = row.get("addr1")
    a2_raw = row.get("addr2")
    
    # Check for NaN or None explicitly
    if pd.isna(a1_raw) or pd.isna(a2_raw):
        return "IP_UNKNOWN"
    
    # Vectorized floor division for the bucket
    a1 = int(a1_raw) // 10
    a2 = int(a2_raw) // 10
    return f"IP_{a1}_{a2}"


def normalize_time_delta(series: pd.Series) -> pd.Series:
    """Min-max normalize time deltas to [0,1] within a user's session."""
    mn, mx = series.min(), series.max()
    if mx == mn:
        return pd.Series(np.zeros(len(series)), index=series.index)
    return (series - mn) / (mx - mn)


GNN_EMBED_DIM = 128   # expected dimension of gnn_node_embedding
SEQUENCE_PAD  = 50    # max behavioral sequence length
DEVICE_EMBED_DIM = 64
TXN_EMBED_DIM    = 128
