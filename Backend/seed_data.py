from datetime import datetime, timedelta, timezone
from random import choice, randint

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from pymongo import MongoClient

from database.mongodb import DB_NAME, MONGO_URI

load_dotenv()


def make_demo_users() -> list[dict]:
    return [
        {
            "user_id": "USR001",
            "name": "Aarav Sharma",
            "city": "Mumbai",
            "usual_cities": ["Mumbai"],
            "trusted_devices": ["dev_mum_1", "dev_mum_2", "dev_mum_3"],
            "usual_login_hour": 10,
            "avg_txn_per_day": 4,
            "risk_profile": {"risk_score": 8, "flags": []},
        },
        {
            "user_id": "USR002",
            "name": "Ishita Verma",
            "city": "Delhi",
            "usual_cities": ["Delhi", "Noida"],
            "trusted_devices": ["dev_del_1", "dev_del_2", "dev_del_3"],
            "usual_login_hour": 11,
            "avg_txn_per_day": 3,
            "risk_profile": {"risk_score": 12, "flags": []},
        },
        {
            "user_id": "USR003",
            "name": "Rohan Iyer",
            "city": "Bangalore",
            "usual_cities": ["Bangalore"],
            "trusted_devices": ["dev_blr_1", "dev_blr_2", "dev_blr_3"],
            "usual_login_hour": 9,
            "avg_txn_per_day": 5,
            "risk_profile": {"risk_score": 10, "flags": []},
        },
        {
            "user_id": "USR004",
            "name": "Neha Kulkarni",
            "city": "Pune",
            "usual_cities": ["Pune", "Mumbai"],
            "trusted_devices": ["dev_pun_1", "dev_pun_2", "dev_pun_3"],
            "usual_login_hour": 14,
            "avg_txn_per_day": 2,
            "risk_profile": {"risk_score": 9, "flags": []},
        },
        {
            "user_id": "USR005",
            "name": "Karthik Rajan",
            "city": "Chennai",
            "usual_cities": ["Chennai"],
            "trusted_devices": ["dev_che_1", "dev_che_2", "dev_che_3"],
            "usual_login_hour": 20,
            "avg_txn_per_day": 4,
            "risk_profile": {"risk_score": 15, "flags": []},
        },
    ]


def seed() -> None:
    client = MongoClient(MONGO_URI)
    db = client[DB_NAME]

    for name in [
        "users",
        "devices",
        "sessions",
        "transactions",
        "login_attempts",
        "fraud_alerts",
        "user_weekly_stats",
        "fraud_ring_links",
        "model_retrain_queue",
    ]:
        db[name].delete_many({})

    users = make_demo_users()
    db.users.insert_many(users)

    for user in users:
        db.devices.insert_many(
            [
                {
                    "user_id": user["user_id"],
                    "device_fingerprint": dev,
                    "trusted": True,
                    "created_at": datetime.now(timezone.utc),
                }
                for dev in user["trusted_devices"]
            ]
        )

    merchant_names = ["Amazon", "Flipkart", "Swiggy", "BigBasket", "Myntra"]
    categories = ["shopping", "food", "utility", "travel"]

    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=60)

    for user in users:
        dates = pd.date_range(start=start_date, end=end_date, periods=180)
        base_amount = np.random.normal(loc=1200, scale=350, size=len(dates)).clip(min=120)

        normal_txns = []
        for i, dt in enumerate(dates):
            normal_txns.append(
                {
                    "txn_id": f"TXN_BASE_{user['user_id']}_{i}",
                    "user_id": user["user_id"],
                    "amount": float(round(base_amount[i], 2)),
                    "merchant_name": choice(merchant_names),
                    "merchant_category": choice(categories),
                    "payment_method": choice(["UPI", "CARD", "NETBANKING"]),
                    "device_fingerprint": choice(user["trusted_devices"]),
                    "ip_address": f"10.0.{randint(1, 5)}.{randint(2, 240)}",
                    "city": choice(user["usual_cities"]),
                    "timestamp": dt.to_pydatetime().replace(tzinfo=timezone.utc),
                    "fraud_score": randint(3, 18),
                    "decision": "APPROVE",
                    "risk_level": "LOW",
                    "fraud_type": "NORMAL",
                    "explanation": ["Normal transaction behavior"],
                }
            )

        db.transactions.insert_many(normal_txns)

    now = datetime.now(timezone.utc)

    # Fraud scenarios
    db.transactions.insert_one(
        {
            "txn_id": "TXN_SCN_ATO_1",
            "user_id": "USR001",
            "amount": 48000,
            "merchant_name": "CryptoXchange",
            "merchant_category": "crypto",
            "payment_method": "UPI",
            "device_fingerprint": "newdevice999",
            "ip_address": "45.33.32.156",
            "city": "Hyderabad",
            "timestamp": now.replace(hour=2, minute=15),
            "fraud_score": 94,
            "decision": "BLOCK",
            "risk_level": "CRITICAL",
            "fraud_type": "ACCOUNT_TAKEOVER",
            "explanation": ["Unknown device detected", "New city at unusual hour"],
        }
    )

    # Low and slow stats
    for idx, avg in enumerate([1000, 1250, 1550, 1950]):
        db.user_weekly_stats.insert_one(
            {
                "user_id": "USR002",
                "week_start": now - timedelta(days=(28 - idx * 7)),
                "avg_amount": avg,
                "txns": 22 + idx,
            }
        )

    # Credential stuffing from same IP
    stuffing_ip = "188.91.23.5"
    login_docs = []
    for i in range(50):
        login_docs.append(
            {
                "user_id": f"USR00{(i % 5) + 1}",
                "device_fingerprint": "bot_device",
                "ip_address": stuffing_ip,
                "success": False,
                "failure_reason": "invalid_password",
                "timestamp": now - timedelta(minutes=randint(1, 9)),
            }
        )
    db.login_attempts.insert_many(login_docs)

    # High amount anomaly
    db.transactions.insert_one(
        {
            "txn_id": "TXN_SCN_AMOUNT_1",
            "user_id": "USR003",
            "amount": 73000,
            "merchant_name": "LuxuryCars",
            "merchant_category": "luxury",
            "payment_method": "CARD",
            "device_fingerprint": "dev_blr_1",
            "ip_address": "49.42.2.9",
            "city": "Bangalore",
            "timestamp": now - timedelta(hours=4),
            "fraud_score": 88,
            "decision": "BLOCK",
            "risk_level": "CRITICAL",
            "fraud_type": "AMOUNT_ANOMALY",
            "explanation": ["Amount 73x above 30-day average"],
        }
    )

    # Fraud ring links (3 users sharing a device)
    shared_device = "ring_shared_device_01"
    for uid in ["USR003", "USR004", "USR005"]:
        db.fraud_ring_links.insert_one(
            {
                "user_id": uid,
                "linked_user_ids": [x for x in ["USR003", "USR004", "USR005"] if x != uid],
                "shared_device": shared_device,
                "confidence": 0.91,
                "created_at": now,
            }
        )

    # Velocity attack: 20 txns in 1 hour
    velocity_docs = []
    for i in range(20):
        velocity_docs.append(
            {
                "txn_id": f"TXN_SCN_VEL_{i}",
                "user_id": "USR005",
                "amount": float(randint(1200, 4200)),
                "merchant_name": "QuickPay",
                "merchant_category": "wallet",
                "payment_method": "UPI",
                "device_fingerprint": "dev_che_2",
                "ip_address": f"172.16.0.{i + 1}",
                "city": "Chennai",
                "timestamp": now - timedelta(minutes=randint(1, 59)),
                "fraud_score": 76,
                "decision": "BLOCK",
                "risk_level": "CRITICAL",
                "fraud_type": "VELOCITY_ATTACK",
                "explanation": ["High transaction velocity in 1 hour"],
            }
        )
    db.transactions.insert_many(velocity_docs)

    # Additional fraud scenarios to complete 10 pre-built cases
    additional_scenarios = [
        {
            "txn_id": "TXN_SCN_GEO_1",
            "user_id": "USR004",
            "amount": 26500,
            "merchant_name": "GlobalAir",
            "merchant_category": "travel",
            "payment_method": "CARD",
            "device_fingerprint": "dev_unknown_geo",
            "ip_address": "103.55.44.12",
            "city": "Kolkata",
            "timestamp": now - timedelta(minutes=45),
            "fraud_score": 79,
            "decision": "BLOCK",
            "risk_level": "CRITICAL",
            "fraud_type": "GEO_ANOMALY",
            "explanation": ["Rapid geo shift and unknown device"],
        },
        {
            "txn_id": "TXN_SCN_NIGHT_1",
            "user_id": "USR002",
            "amount": 19999,
            "merchant_name": "NightOutlet",
            "merchant_category": "shopping",
            "payment_method": "UPI",
            "device_fingerprint": "dev_del_3",
            "ip_address": "52.64.77.88",
            "city": "Delhi",
            "timestamp": now.replace(hour=3, minute=22),
            "fraud_score": 74,
            "decision": "BLOCK",
            "risk_level": "CRITICAL",
            "fraud_type": "UNUSUAL_TIME",
            "explanation": ["Unusual transaction hour pattern"],
        },
        {
            "txn_id": "TXN_SCN_MERCHANT_1",
            "user_id": "USR001",
            "amount": 31500,
            "merchant_name": "GiftCardHub",
            "merchant_category": "gift_cards",
            "payment_method": "NETBANKING",
            "device_fingerprint": "dev_mum_2",
            "ip_address": "91.14.36.90",
            "city": "Mumbai",
            "timestamp": now - timedelta(hours=2),
            "fraud_score": 72,
            "decision": "BLOCK",
            "risk_level": "CRITICAL",
            "fraud_type": "MERCHANT_RISK",
            "explanation": ["High-risk merchant category and unusual ticket size"],
        },
        {
            "txn_id": "TXN_SCN_CASHOUT_1",
            "user_id": "USR003",
            "amount": 54100,
            "merchant_name": "WalletDrain",
            "merchant_category": "wallet",
            "payment_method": "UPI",
            "device_fingerprint": "ring_shared_device_01",
            "ip_address": "178.21.9.23",
            "city": "Bangalore",
            "timestamp": now - timedelta(minutes=12),
            "fraud_score": 91,
            "decision": "BLOCK",
            "risk_level": "CRITICAL",
            "fraud_type": "FRAUD_RING",
            "explanation": ["Shared ring device observed with high confidence"],
        },
    ]
    db.transactions.insert_many(additional_scenarios)

    # Alerts for seeded fraud transactions
    db.fraud_alerts.insert_many(
        [
            {
                "txn_id": "TXN_SCN_ATO_1",
                "user_id": "USR001",
                "fraud_score": 94,
                "fraud_type": "ACCOUNT_TAKEOVER",
                "status": "PENDING",
                "created_at": now,
            },
            {
                "txn_id": "TXN_SCN_AMOUNT_1",
                "user_id": "USR003",
                "fraud_score": 88,
                "fraud_type": "AMOUNT_ANOMALY",
                "status": "PENDING",
                "created_at": now,
            },
            {
                "txn_id": "TXN_SCN_GEO_1",
                "user_id": "USR004",
                "fraud_score": 79,
                "fraud_type": "GEO_ANOMALY",
                "status": "PENDING",
                "created_at": now,
            },
            {
                "txn_id": "TXN_SCN_NIGHT_1",
                "user_id": "USR002",
                "fraud_score": 74,
                "fraud_type": "UNUSUAL_TIME",
                "status": "PENDING",
                "created_at": now,
            },
            {
                "txn_id": "TXN_SCN_MERCHANT_1",
                "user_id": "USR001",
                "fraud_score": 72,
                "fraud_type": "MERCHANT_RISK",
                "status": "PENDING",
                "created_at": now,
            },
            {
                "txn_id": "TXN_SCN_CASHOUT_1",
                "user_id": "USR003",
                "fraud_score": 91,
                "fraud_type": "FRAUD_RING",
                "status": "PENDING",
                "created_at": now,
            },
        ]
    )

    print("Seed complete: demo users, normal history, and fraud scenarios inserted.")


if __name__ == "__main__":
    seed()
