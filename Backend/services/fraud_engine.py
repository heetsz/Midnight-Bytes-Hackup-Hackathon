from datetime import datetime, timedelta, timezone

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError


async def calculate_amount_anomaly_score(
    db: AsyncIOMotorDatabase, user_id: str, amount: float, now: datetime
) -> tuple[int, list[str], float]:
    reasons: list[str] = []

    try:
        start = now - timedelta(days=30)
        cursor = db.transactions.find(
            {"user_id": user_id, "timestamp": {"$gte": start}}, {"amount": 1}
        )
        rows = await cursor.to_list(length=5000)
    except PyMongoError:
        return 0, ["Amount anomaly unavailable due to database error"], 0.0

    amounts = np.array([float(x.get("amount", 0.0)) for x in rows if x.get("amount") is not None])

    if amounts.size < 5:
        return 0, reasons, 0.0

    mean = float(np.mean(amounts))
    std = float(np.std(amounts))

    if std == 0:
        if amount > mean * 2:
            reasons.append("Amount is significantly above normal pattern")
            return 65, reasons, 0.0
        return 0, reasons, 0.0

    z_score = (amount - mean) / std

    if z_score > 3:
        ratio = round(amount / max(mean, 1.0), 2)
        reasons.append(f"Amount {ratio}x above 30-day average")
        return 90, reasons, float(z_score)
    if z_score > 2:
        reasons.append("Amount is highly unusual compared to 30-day history")
        return 65, reasons, float(z_score)
    if z_score > 1:
        reasons.append("Amount is moderately above normal behavior")
        return 30, reasons, float(z_score)

    return 0, reasons, float(z_score)


async def calculate_velocity_score(
    db: AsyncIOMotorDatabase, user: dict, user_id: str, now: datetime
) -> tuple[int, list[str], dict[str, int]]:
    reasons: list[str] = []

    try:
        one_hour_ago = now - timedelta(hours=1)
        one_day_ago = now - timedelta(hours=24)

        txns_1h = await db.transactions.count_documents(
            {"user_id": user_id, "timestamp": {"$gte": one_hour_ago}}
        )
        txns_24h = await db.transactions.count_documents(
            {"user_id": user_id, "timestamp": {"$gte": one_day_ago}}
        )
    except PyMongoError:
        return 0, ["Velocity check unavailable due to database error"], {"txns_1h": 0, "txns_24h": 0}

    avg_txn_per_day = float(user.get("avg_txn_per_day", 1.0))
    baseline = max(avg_txn_per_day, 1.0)

    score = 0
    if txns_24h > baseline * 3:
        score = max(score, 70)
        reasons.append("24h transaction count is 3x above user baseline")

    hourly_baseline = max(int(round(baseline / 24.0)), 1)
    if txns_1h > hourly_baseline * 3:
        score = max(score, 90)
        reasons.append("1h transaction burst is far above normal")

    return score, reasons, {"txns_1h": txns_1h, "txns_24h": txns_24h}


def calculate_final_score(
    ato_score: int,
    amount_score: int,
    low_slow_score: int,
    velocity_score: int,
    ring_score: int,
) -> int:
    weighted_score = (
        ato_score * 0.30
        + amount_score * 0.30
        + low_slow_score * 0.20
        + velocity_score * 0.10
        + ring_score * 0.10
    )

    return int(max(0, min(round(weighted_score), 100)))


def get_decision(score: int) -> str:
    if score >= 71:
        return "BLOCK"
    if score >= 41:
        return "MFA"
    return "APPROVE"


def infer_fraud_type(scores: dict[str, int]) -> str:
    best = max(scores, key=scores.get)
    mapping = {
        "ato": "ACCOUNT_TAKEOVER",
        "amount": "AMOUNT_ANOMALY",
        "low_slow": "LOW_AND_SLOW",
        "velocity": "VELOCITY_ATTACK",
        "ring": "FRAUD_RING",
    }
    if scores.get(best, 0) == 0:
        return "NORMAL"
    return mapping[best]
