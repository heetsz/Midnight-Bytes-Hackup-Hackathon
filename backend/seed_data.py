import hashlib
import json
import os
import random
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient


FIRST_NAMES = [
]

LAST_NAMES = [
]

CITY_DATA = [
]

MERCHANTS_NORMAL = [
]

MERCHANTS_RISKY = [
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def random_ip() -> str:
    return f"{random.randint(10, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


def generate_fingerprint() -> dict:
    return {
        "id_31_idx": random.randint(1, 64),
        "id_33_idx": random.randint(1, 40),
        "DeviceType_idx": random.randint(1, 5),
        "DeviceInfo_idx": random.randint(1, 60),
        "os_browser_idx": random.randint(1, 40),
        "screen_width": random.choice([720, 828, 1080, 1125, 1170, 1440, 1536, 1920]),
        "screen_height": random.choice([1280, 1334, 1920, 2160, 2340, 2400, 2532, 2560]),
        "hardware_concurrency": random.choice([2, 4, 6, 8, 12]),
    }


def hash_fingerprint(fingerprint: dict) -> str:
    raw = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def decision_from_prob(prob: float) -> str:
    if prob >= 0.78:
        return "block"
    if prob >= 0.45:
        return "mfa"
    return "approve"


def main() -> None:
    if os.getenv("ENABLE_SAMPLE_SEEDING", "0").strip() != "1":
        print("Seeding is disabled. Set ENABLE_SAMPLE_SEEDING=1 to run seed_data.py.")
        return

    load_dotenv()

    uri = os.getenv("MONGODB_URL")
    db_name = os.getenv("MONGODB_DB_NAME", "fraud_ops")

    random.seed(42)

    client = MongoClient(uri)
    db = client[db_name]

    users_col = db.users
    devices_col = db.devices
    txns_col = db.transactions

    users_col.delete_many({})
    devices_col.delete_many({})
    txns_col.delete_many({})

    users_state: dict[str, dict] = {}
    devices_map: dict[str, dict] = {}
    transactions_docs: list[dict] = []

    user_count = 140
    txn_count = 3600
    fraud_txn_count = 0

    for idx in range(user_count):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        name = f"{first} {last}"
        city_info = random.choice(CITY_DATA)

        user_key = f"usr_{99800000 + idx}_{first[:2].lower()}{last[:2].lower()}"
        created_at = utc_now() - timedelta(days=random.randint(30, 420), hours=random.randint(0, 23))

        known_devices = []
        for _ in range(random.randint(1, 3)):
            fingerprint = generate_fingerprint()
            device_hash = hash_fingerprint(fingerprint)

            devices_map.setdefault(
                device_hash,
                {
                    "_id": ObjectId(),
                    "device_hash": device_hash,
                    "created_at": created_at - timedelta(days=random.randint(1, 40)),
                    "fingerprint": fingerprint,
                },
            )

            first_seen = created_at + timedelta(days=random.randint(0, 10))
            known_devices.append(
                {
                    "device_hash": device_hash,
                    "first_seen_at": first_seen,
                    "last_seen_at": first_seen,
                    "device_match_ord": random.choice([1, 2, 2, 2]),
                }
            )

        users_state[user_key] = {
            "_id": ObjectId(),
            "user_key": user_key,
            "name": name,
            "email": f"{first.lower()}.{last.lower()}{idx}@example.in",
            "phone_no": f"+91{random.randint(6000000000, 9999999999)}",
            "city": city_info["city"],
            "created_at": created_at,
            "usual_login_hour": random.randint(7, 23),
            "user_txn_count": 0,
            "device_centroid": [round(random.uniform(-1.0, 1.0), 5) for _ in range(64)],
            "known_devices": known_devices,
            "recent_behavior_seq": [],
            "transaction_ids": [],
            "last_txn_at": None,
            "risk_bias": city_info["risk_bias"],
        }

    user_keys = list(users_state.keys())

    for i in range(txn_count):
        user_key = random.choice(user_keys)
        user = users_state[user_key]

        base_fraud_prob = user["risk_bias"]
        is_fraud = random.random() < base_fraud_prob

        if is_fraud:
            fraud_txn_count += 1

        # Device behavior: fraud has higher chance of novel/untrusted device.
        use_known_device = random.random() > (0.40 if is_fraud else 0.10)
        if use_known_device and user["known_devices"]:
            device_entry = random.choice(user["known_devices"])
            device_hash = device_entry["device_hash"]
            device_entry["device_match_ord"] = min(2, max(1, int(device_entry.get("device_match_ord", 1))))
        else:
            fingerprint = generate_fingerprint()
            device_hash = hash_fingerprint(fingerprint)
            devices_map.setdefault(
                device_hash,
                {
                    "_id": ObjectId(),
                    "device_hash": device_hash,
                    "created_at": utc_now() - timedelta(days=random.randint(0, 20)),
                    "fingerprint": fingerprint,
                },
            )
            user["known_devices"].append(
                {
                    "device_hash": device_hash,
                    "first_seen_at": utc_now(),
                    "last_seen_at": utc_now(),
                    "device_match_ord": 0,
                }
            )

        merchant_name = random.choice(MERCHANTS_RISKY if is_fraud else MERCHANTS_NORMAL)

        if is_fraud:
            amount = round(random.uniform(30000, 300000), 2)
            calibrated_prob = round(random.uniform(0.68, 0.99), 6)
            seq_anomaly = round(random.uniform(0.55, 0.98), 6)
            ato_prob = round(random.uniform(0.48, 0.96), 6)
            synth_prob = round(random.uniform(0.32, 0.90), 6)
        else:
            amount = round(random.uniform(100, 35000), 2)
            calibrated_prob = round(random.uniform(0.02, 0.39), 6)
            seq_anomaly = round(random.uniform(0.01, 0.43), 6)
            ato_prob = round(random.uniform(0.01, 0.35), 6)
            synth_prob = round(random.uniform(0.01, 0.26), 6)

        decision = decision_from_prob(calibrated_prob)

        txn_time = utc_now() - timedelta(
            days=random.randint(0, 45),
            hours=random.randint(0, 23),
            minutes=random.randint(0, 59),
            seconds=random.randint(0, 59),
        )

        last_txn_time = user["last_txn_at"]
        delta_t = (txn_time - last_txn_time).total_seconds() if last_txn_time else 0.0
        delta_t = max(0.0, delta_t)
        user["last_txn_at"] = txn_time

        user["user_txn_count"] += 1
        txn_rank = user["user_txn_count"]

        device_dist_score = round(min(1.0, 1.0 if not use_known_device else random.uniform(0.01, 0.25)), 6)
        stacker_score = round(min(1.0, 0.38 * ato_prob + 0.34 * seq_anomaly + 0.18 * synth_prob + 0.10 * device_dist_score), 6)

        city_info = next(item for item in CITY_DATA if item["city"] == user["city"])

        txn_id = ObjectId()
        user["transaction_ids"].append(str(txn_id))

        behavior_event = {
            "type_idx": 3 if decision == "block" else 2 if decision == "mfa" else 1,
            "log_amount": round(random.uniform(0.2, 1.0), 6),
            "step_norm": round(min(1.0, txn_rank / 1000.0), 6),
            "timestamp": txn_time,
        }
        user["recent_behavior_seq"].append(behavior_event)
        user["recent_behavior_seq"] = user["recent_behavior_seq"][-50:]

        # Update known device timestamps.
        for device in user["known_devices"]:
            if device["device_hash"] == device_hash:
                if txn_time > device["last_seen_at"]:
                    device["last_seen_at"] = txn_time
                break

        transactions_docs.append(
            {
                "_id": txn_id,
                "user_key": user_key,
                "device_hash": device_hash,
                "timestamp": txn_time,
                "frontend_payload": {
                    "transaction_amt": amount,
                    "client_ip": random_ip(),
                    "merchant_name": merchant_name,
                    "location": city_info["location"],
                },
                "backend_snapshot": {
                    "delta_t": round(delta_t, 4),
                    "delta_t_norm": round(min(1.0, delta_t / 86400.0), 4),
                    "txn_rank": txn_rank,
                    "amt_zscore": round(random.uniform(0.1, 4.7 if is_fraud else 2.1), 4),
                    "M_fail_count": random.randint(0, 5 if is_fraud else 2),
                    "M_all_fail": 1 if is_fraud and random.random() > 0.4 else 0,
                    "card1": random.randint(1000, 55000),
                    "D1": round(random.uniform(0.0, 20.0), 3),
                    "D2": round(random.uniform(0.0, 20.0), 3),
                    "D3": round(random.uniform(0.0, 20.0), 3),
                    "v_cols": [round(random.uniform(0, 1), 4) for _ in range(12)],
                    "c_cols": [round(random.uniform(0, 4), 4) for _ in range(8)],
                    "m_cols": [random.randint(0, 1) for _ in range(8)],
                },
                "pipeline_results": {
                    "model_decision": decision,
                    "calibrated_prob": calibrated_prob,
                    "stacker_score": stacker_score,
                    "base_outputs": {
                        "gnn_logit": round(random.uniform(-3.0, 3.8), 4),
                        "device_dist_score": device_dist_score,
                    },
                    "queue_outputs": {
                        "seq_anomaly_score": seq_anomaly,
                        "synth_id_prob": synth_prob,
                        "ato_prob": ato_prob,
                        "recon_error": round(random.uniform(0.2, 3.5 if is_fraud else 2.0), 4),
                        "tabnet_logit": round(random.uniform(-2.8, 4.4), 4),
                    },
                },
            }
        )

    user_docs = []
    for state in users_state.values():
        user_docs.append(
            {
                "_id": state["_id"],
                "user_key": state["user_key"],
                "name": state["name"],
                "email": state["email"],
                "phone_no": state["phone_no"],
                "city": state["city"],
                "created_at": state["created_at"],
                "usual_login_hour": state["usual_login_hour"],
                "user_txn_count": state["user_txn_count"],
                "device_centroid": state["device_centroid"],
                "known_devices": state["known_devices"],
                "recent_behavior_seq": state["recent_behavior_seq"],
                "transaction_ids": state["transaction_ids"],
            }
        )

    device_docs = list(devices_map.values())

    users_col.insert_many(user_docs)
    devices_col.insert_many(device_docs)
    txns_col.insert_many(transactions_docs)

    print("Seed completed")
    print(f"Database: {db_name}")
    print(f"Users inserted: {len(user_docs)}")
    print(f"Devices inserted: {len(device_docs)}")
    print(f"Transactions inserted: {len(transactions_docs)}")
    print(f"Fraud-leaning transactions generated: {fraud_txn_count}")


if __name__ == "__main__":
    main()
