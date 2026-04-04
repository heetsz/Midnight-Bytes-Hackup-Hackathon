from __future__ import annotations

import argparse
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

import numpy as np
import pandas as pd
from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parent
MODELS_ROOT = PROJECT_ROOT.parent / "Models"
PIPELINE_FILE = MODELS_ROOT / "run_pipeline_phase_refactored.py"

LOCATION_POOL = [
    "Mumbai",
    "Delhi",
    "Bengaluru",
    "Hyderabad",
    "Chennai",
    "Kolkata",
    "Pune",
    "Ahmedabad",
    "Jaipur",
    "Lucknow",
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, (float, np.floating)) and np.isnan(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        if isinstance(value, (float, np.floating)) and np.isnan(value):
            return default
        return int(value)
    except Exception:
        return default


def safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if text.lower() in {"nan", "nat", "none", ""}:
        return default
    return text


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if isinstance(value, (np.generic,)):
            value = value.item()
        if isinstance(value, float) and np.isnan(value):
            value = 0.0
        normalized[key] = value
    return normalized


def load_random_transaction_fn() -> Any:
    if not PIPELINE_FILE.exists():
        raise FileNotFoundError(f"Pipeline file not found: {PIPELINE_FILE}")

    source = PIPELINE_FILE.read_text(encoding="utf-8")
    signature = "def get_random_live_transaction(ieee_df: pd.DataFrame) -> dict:"
    start = source.find(signature)
    if start == -1:
        raise RuntimeError("get_random_live_transaction function not found in pipeline file")

    next_def = source.find("\ndef demo_single_row_inference", start)
    if next_def == -1:
        next_def = len(source)

    fn_source = source[start:next_def]
    namespace: dict[str, Any] = {
        "pd": pd,
        "np": np,
        "datetime": datetime,
        "uuid": uuid,
    }
    exec(fn_source, namespace)
    return namespace["get_random_live_transaction"]


def load_feature_store() -> pd.DataFrame:
    candidates = [
        MODELS_ROOT / "features" / "feature_store.parquet",
        MODELS_ROOT / "data" / "processed" / "ieee_cis_fully_enriched.parquet",
    ]
    for path in candidates:
        if path.exists():
            return pd.read_parquet(path)
    raise FileNotFoundError("No feature store parquet found under Models/features or Models/data/processed")


def hash_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def infer_prob_and_decision(row: dict[str, Any]) -> tuple[float, float, str]:
    raw_score = row.get("raw_fraud_score")
    if raw_score is None:
        raw_score = row.get("tabnet_logit", 0.0)
        raw_score = sigmoid(safe_float(raw_score, 0.0))
    raw_score = safe_float(raw_score, 0.0)

    calibrated = safe_float(row.get("calibrated_prob", raw_score), raw_score)
    decision = safe_str(row.get("decision"), "")
    if not decision:
        if calibrated < 0.30:
            decision = "approve"
        elif calibrated < 0.70:
            decision = "mfa"
        else:
            decision = "block"

    return raw_score, calibrated, decision.lower()


def force_risky_profile(
    raw_score: float,
    calibrated_prob: float,
    decision: str,
    approve_ratio: float,
) -> tuple[float, float, str]:
    # Keep approvals intentionally low by overriding output distribution.
    draw = random.random()
    if draw < approve_ratio:
        decision = "approve"
        calibrated_prob = random.uniform(0.03, 0.28)
    elif draw < min(0.95, approve_ratio + 0.35):
        decision = "mfa"
        calibrated_prob = random.uniform(0.33, 0.69)
    else:
        decision = "block"
        calibrated_prob = random.uniform(0.72, 0.99)

    # Keep raw score consistent with calibrated probability band.
    raw_score = max(0.0, min(1.0, calibrated_prob + random.uniform(-0.07, 0.07)))
    return raw_score, calibrated_prob, decision


def extract_cols(row: dict[str, Any], prefix: str, cast_fn) -> list[Any]:
    pairs: list[tuple[int, Any]] = []
    plen = len(prefix)
    for key, value in row.items():
        key_s = str(key)
        if not key_s.startswith(prefix):
            continue
        idx_text = key_s[plen:]
        if not idx_text.isdigit():
            continue
        idx = int(idx_text)
        pairs.append((idx, cast_fn(value)))
    pairs.sort(key=lambda item: item[0])
    return [v for _, v in pairs]


def build_fingerprint(idx: int) -> dict[str, int]:
    return {
        "id_31_idx": (idx % 63) + 1,
        "id_33_idx": (idx % 39) + 1,
        "DeviceType_idx": (idx % 5) + 1,
        "DeviceInfo_idx": (idx % 59) + 1,
        "os_browser_idx": (idx % 39) + 1,
        "screen_width": random.choice([720, 828, 1080, 1170, 1440, 1536, 1920]),
        "screen_height": random.choice([1280, 1334, 1920, 2160, 2340, 2400, 2532, 2560]),
        "hardware_concurrency": random.choice([2, 4, 6, 8, 12]),
    }


def random_location() -> str:
    return random.choice(LOCATION_POOL)


def populate(
    count: int,
    user_count: int,
    clear_existing: bool,
    approve_ratio: float,
) -> None:
    load_dotenv(PROJECT_ROOT / ".env")

    mongodb_url = str(__import__("os").getenv("MONGODB_URL", "mongodb://localhost:27017"))
    db_name = str(__import__("os").getenv("MONGODB_DB_NAME", "fraud_ops"))

    client = MongoClient(mongodb_url)
    db = client[db_name]

    users_col = db.users
    devices_col = db.devices
    txns_col = db.transactions

    if clear_existing:
        users_col.delete_many({})
        devices_col.delete_many({})
        txns_col.delete_many({})

    feature_df = load_feature_store()
    get_random_live_transaction = load_random_transaction_fn()

    users_state: dict[str, dict[str, Any]] = {}
    devices_state: dict[str, dict[str, Any]] = {}
    transactions: list[dict[str, Any]] = []

    user_keys = [f"sim_user_{i:04d}" for i in range(max(1, user_count))]

    for i in range(count):
        sampled = get_random_live_transaction(feature_df)
        if isinstance(sampled, pd.Series):
            row = sampled.to_dict()
        else:
            row = dict(sampled)
        row = normalize_row(row)

        user_key = random.choice(user_keys)
        user_name = f"Sim User {user_key.split('_')[-1]}"
        user_email = f"{user_key}@demo.local"

        fp = build_fingerprint(i)
        device_hash = hash_fingerprint(fp)

        if device_hash not in devices_state:
            devices_state[device_hash] = {
                "device_hash": device_hash,
                "created_at": utc_now(),
                "fingerprint": fp,
            }

        if user_key not in users_state:
            user_suffix = user_key.split("_")[-1]
            users_state[user_key] = {
                "user_key": user_key,
                "name": user_name,
                "email": user_email,
                "phone_no": f"+91{int(user_suffix):010d}",
                "city": safe_str(row.get("location"), random_location()),
                "created_at": utc_now(),
                "usual_login_hour": random.randint(7, 23),
                "user_txn_count": 0,
                "device_centroid": [],
                "known_devices": [],
                "recent_behavior_seq": [],
                "transaction_ids": [],
            }

        user = users_state[user_key]
        now = utc_now()

        known_hashes = {d.get("device_hash") for d in user["known_devices"]}
        if device_hash not in known_hashes:
            user["known_devices"].append(
                {
                    "device_hash": device_hash,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "device_match_ord": 0,
                }
            )

        amount = safe_float(row.get("TransactionAmt"), round(random.uniform(5.0, 2500.0), 2))
        raw_score, calibrated_prob, decision = infer_prob_and_decision(row)
        raw_score, calibrated_prob, decision = force_risky_profile(
            raw_score=raw_score,
            calibrated_prob=calibrated_prob,
            decision=decision,
            approve_ratio=approve_ratio,
        )
        if decision in {"mfa", "block"}:
            amount = max(amount, round(random.uniform(600.0, 5000.0), 2))

        merchant_name = (
            safe_str(row.get("merchant_name"))
            or safe_str(row.get("Merchant"))
            or safe_str(row.get("merchant"))
            or "Model Feed Merchant"
        )
        location = (
            safe_str(row.get("location"))
            or safe_str(row.get("addr1"))
            or safe_str(row.get("city"))
            or random_location()
        )

        if location.strip().lower() in {"model feed location", "unknown", "na", "n/a"}:
            location = random_location()

        source_txn_id = safe_str(row.get("TransactionID"), f"MODEL_TXN_{i:06d}")
        txn_time_raw = row.get("timestamp")
        txn_time = now
        if isinstance(txn_time_raw, str) and txn_time_raw:
            try:
                txn_time = datetime.fromisoformat(txn_time_raw)
                if txn_time.tzinfo is None:
                    txn_time = txn_time.replace(tzinfo=timezone.utc)
            except Exception:
                txn_time = now

        txn_doc = {
            "_id": ObjectId(),
            "user_key": user_key,
            "device_hash": device_hash,
            "timestamp": txn_time,
            "frontend_payload": {
                "transaction_amt": round(amount, 2),
                "client_ip": "0.0.0.0",
                "merchant_name": merchant_name,
                "location": location,
            },
            "backend_snapshot": {
                "delta_t": 0.0,
                "delta_t_norm": 0.0,
                "txn_rank": user["user_txn_count"] + 1,
                "amt_zscore": 0.0,
                "M_fail_count": 0,
                "M_all_fail": 0,
                "card1": safe_int(row.get("card1"), 0) or None,
                "D1": safe_float(row.get("D1"), 0.0),
                "D2": safe_float(row.get("D2"), 0.0),
                "D3": safe_float(row.get("D3"), 0.0),
                "v_cols": extract_cols(row, "V", lambda x: safe_float(x, 0.0)),
                "c_cols": extract_cols(row, "C", lambda x: safe_float(x, 0.0)),
                "m_cols": extract_cols(row, "M", lambda x: safe_int(x, 0)),
                "source_transaction_id": source_txn_id,
            },
            "pipeline_results": {
                "model_decision": decision,
                "calibrated_prob": round(calibrated_prob, 6),
                "stacker_score": round(calibrated_prob, 6),
                "raw_fraud_score": round(raw_score, 6),
                "model_source": "get_random_live_transaction",
                "base_outputs": {
                    "gnn_logit": safe_float(row.get("txn_graph_logit"), 0.0),
                    "device_dist_score": 1.0,
                },
                "queue_outputs": {
                    "seq_anomaly_score": safe_float(row.get("seq_anomaly_score"), 0.0),
                    "synth_id_prob": safe_float(row.get("synth_id_prob"), 0.0),
                    "ato_prob": safe_float(row.get("ato_prob"), 0.0),
                    "recon_error": safe_float(row.get("recon_error"), 0.0),
                    "tabnet_logit": safe_float(row.get("tabnet_logit"), 0.0),
                },
                "source_transaction_id": source_txn_id,
            },
            "user_identity": {
                "name": user_name,
                "email": user_email,
            },
        }

        transactions.append(txn_doc)
        user["user_txn_count"] += 1
        user["transaction_ids"].append(str(txn_doc["_id"]))
        user["recent_behavior_seq"].append(
            {
                "type_idx": 3 if decision == "block" else 2 if decision == "mfa" else 1,
                "log_amount": safe_float(np.log(max(amount, 1.0)), 0.0),
                "step_norm": min(1.0, user["user_txn_count"] / 1000.0),
                "timestamp": txn_time,
            }
        )
        user["recent_behavior_seq"] = user["recent_behavior_seq"][-50:]

    if transactions:
        txns_col.insert_many(transactions, ordered=False)

    for device_doc in devices_state.values():
        devices_col.update_one(
            {"device_hash": device_doc["device_hash"]},
            {"$setOnInsert": device_doc},
            upsert=True,
        )

    for user_doc in users_state.values():
        users_col.update_one(
            {"user_key": user_doc["user_key"]},
            {
                "$set": {
                    "name": user_doc["name"],
                    "email": user_doc["email"],
                    "phone_no": user_doc["phone_no"],
                    "city": user_doc["city"],
                    "usual_login_hour": user_doc["usual_login_hour"],
                    "device_centroid": user_doc["device_centroid"],
                    "known_devices": user_doc["known_devices"],
                    "recent_behavior_seq": user_doc["recent_behavior_seq"],
                    "transaction_ids": user_doc["transaction_ids"],
                    "user_txn_count": user_doc["user_txn_count"],
                },
                "$setOnInsert": {
                    "created_at": user_doc["created_at"],
                },
            },
            upsert=True,
        )

    print(f"Database: {db_name}")
    print(f"Inserted transactions: {len(transactions)}")
    print(f"Touched users: {len(users_state)}")
    print(f"Touched devices: {len(devices_state)}")
    print(f"Target approval ratio: {approve_ratio:.2f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate MongoDB with random model transactions")
    parser.add_argument("--count", type=int, default=1000, help="Number of transactions to insert")
    parser.add_argument("--users", type=int, default=120, help="Number of synthetic users to spread transactions across")
    parser.add_argument("--clear", action="store_true", help="Delete existing users/devices/transactions before inserting")
    parser.add_argument(
        "--approve-ratio",
        type=float,
        default=0.12,
        help="Fraction of transactions to keep approved (0.0 to 0.4 recommended)",
    )
    args = parser.parse_args()

    if args.count <= 0:
        raise SystemExit("--count must be > 0")
    if args.users <= 0:
        raise SystemExit("--users must be > 0")
    if args.approve_ratio < 0 or args.approve_ratio > 0.8:
        raise SystemExit("--approve-ratio must be between 0 and 0.8")

    random.seed(42)
    np.random.seed(42)

    populate(
        count=args.count,
        user_count=args.users,
        clear_existing=args.clear,
        approve_ratio=args.approve_ratio,
    )


if __name__ == "__main__":
    main()
