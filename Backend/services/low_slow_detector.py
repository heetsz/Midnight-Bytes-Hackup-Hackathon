from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import PyMongoError


def _to_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.now(timezone.utc)


def _week_window(now: datetime) -> tuple[datetime, datetime]:
    week_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=now.weekday())
    week_end = week_start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return week_start, week_end


def _normalize_txn(txn: dict[str, Any]) -> dict[str, Any]:
    details = txn.get("details", {})
    amount = txn.get("amount", details.get("amount", 0.0))
    timestamp = txn.get("timestamp", details.get("timestamp"))
    merchant_category = txn.get("merchant_category", details.get("merchant_category", "unknown"))
    return {
        "amount": float(amount or 0.0),
        "timestamp": _to_utc(timestamp),
        "merchant_category": merchant_category,
    }


async def get_last_30_days_transactions(user_id: str, db: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    query = {
        "user_id": user_id,
        "$or": [
            {"timestamp": {"$gte": cutoff}},
            {"details.timestamp": {"$gte": cutoff}},
        ],
    }

    try:
        rows = await db.transactions.find(query).to_list(length=10000)
    except PyMongoError:
        return []

    return [_normalize_txn(row) for row in rows]


def calculate_rolling_zscore(amounts: list[float], new_amount: float) -> dict[str, Any]:
    if not amounts:
        return {
            "z_score": 0.0,
            "mean": 0.0,
            "std": 0.0,
            "risk_score": 10,
            "is_anomalous": False,
        }

    arr = np.array(amounts, dtype=float)
    mean = float(np.mean(arr))
    std = float(np.std(arr))

    if std <= 0:
        z_score = 0.0
        if new_amount > mean * 2:
            z_score = 2.1
    else:
        z_score = float((new_amount - mean) / std)

    if z_score > 3.0:
        risk_score = 90
    elif z_score > 2.0:
        risk_score = 65
    elif z_score > 1.5:
        risk_score = 40
    else:
        risk_score = 10

    return {
        "z_score": round(z_score, 2),
        "mean": round(mean, 2),
        "std": round(std, 2),
        "risk_score": risk_score,
        "is_anomalous": z_score > 1.5,
    }


async def get_weekly_stats(user_id: str, db: AsyncIOMotorDatabase) -> list[dict[str, Any]]:
    try:
        rows = await (
            db.user_weekly_stats.find({"user_id": user_id})
            .sort("week_start", -1)
            .limit(4)
            .to_list(length=4)
        )
    except PyMongoError:
        return []

    return rows


async def update_weekly_stats(user_id: str, amount: float, db: AsyncIOMotorDatabase) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    week_start, week_end = _week_window(now)

    try:
        current_week = await db.user_weekly_stats.find_one(
            {"user_id": user_id, "week_start": week_start}
        )
    except PyMongoError:
        return {"updated": False, "message": "Failed to read current weekly stats"}

    stats = {
        "avg_amount": 0.0,
        "max_amount": 0.0,
        "txn_count": 0,
        "total_amount": 0.0,
    }

    if current_week and isinstance(current_week.get("stats"), dict):
        stats.update(current_week["stats"])

    txn_count = int(stats["txn_count"]) + 1
    total_amount = float(stats["total_amount"]) + float(amount)
    avg_amount = total_amount / max(txn_count, 1)
    max_amount = max(float(stats["max_amount"]), float(amount))

    prev_avg = 0.0
    try:
        prev_week = await db.user_weekly_stats.find_one(
            {
                "user_id": user_id,
                "week_start": {"$lt": week_start},
            },
            sort=[("week_start", -1)],
        )
        if prev_week and isinstance(prev_week.get("stats"), dict):
            prev_avg = float(prev_week["stats"].get("avg_amount", 0.0))
    except PyMongoError:
        prev_avg = 0.0

    pct_change = ((avg_amount - prev_avg) / prev_avg * 100.0) if prev_avg > 0 else 0.0
    drift_score = min(max(pct_change / 100.0, 0.0), 1.0)
    is_anomalous = pct_change > 20.0

    payload = {
        "user_id": user_id,
        "week_start": week_start,
        "week_end": week_end,
        "stats": {
            "avg_amount": round(avg_amount, 2),
            "max_amount": round(max_amount, 2),
            "txn_count": txn_count,
            "total_amount": round(total_amount, 2),
        },
        "drift": {
            "drift_score": round(drift_score, 2),
            "pct_change_from_last_week": round(pct_change, 2),
            "is_anomalous": is_anomalous,
        },
        "updated_at": now,
    }

    try:
        await db.user_weekly_stats.update_one(
            {"user_id": user_id, "week_start": week_start},
            {"$set": payload},
            upsert=True,
        )
    except PyMongoError:
        return {"updated": False, "message": "Failed to update weekly stats"}

    return {"updated": True, **payload}


def detect_gradual_drift(weekly_stats: list[dict[str, Any]]) -> dict[str, Any]:
    if len(weekly_stats) < 2:
        return {
            "drift_detected": False,
            "drift_score": 0,
            "week_over_week": [],
            "consecutive_increases": 0,
            "pct_changes": [],
            "message": "Not enough weekly data",
        }

    # Ensure chronological order before change calculation.
    ordered = list(reversed(weekly_stats))
    weekly_avg = [float(row.get("stats", {}).get("avg_amount", 0.0)) for row in ordered]

    pct_changes: list[float] = []
    consecutive = 0

    for i in range(1, len(weekly_avg)):
        prev = weekly_avg[i - 1]
        curr = weekly_avg[i]
        if prev <= 0:
            pct = 0.0
        else:
            pct = ((curr - prev) / prev) * 100.0
        pct_changes.append(round(pct, 2))
        if pct >= 20.0:
            consecutive += 1

    score_map = {0: 0, 1: 25, 2: 50, 3: 100}
    drift_score = score_map.get(consecutive, 100)
    drift_detected = consecutive >= 2

    message = "No sustained drift detected"
    if drift_detected:
        message = f"Spend grew 20%+ for {consecutive} consecutive weeks"

    return {
        "drift_detected": drift_detected,
        "drift_score": drift_score,
        "week_over_week": [round(x, 2) for x in weekly_avg],
        "consecutive_increases": consecutive,
        "pct_changes": pct_changes,
        "message": message,
    }


async def velocity_check(user_id: str, new_amount: float, db: AsyncIOMotorDatabase) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    one_day_ago = now - timedelta(hours=24)

    try:
        last_1hr_count = await db.transactions.count_documents(
            {
                "user_id": user_id,
                "$or": [
                    {"timestamp": {"$gte": one_hour_ago}},
                    {"details.timestamp": {"$gte": one_hour_ago}},
                ],
            }
        )
        last_24hr_count = await db.transactions.count_documents(
            {
                "user_id": user_id,
                "$or": [
                    {"timestamp": {"$gte": one_day_ago}},
                    {"details.timestamp": {"$gte": one_day_ago}},
                ],
            }
        )

        user = await db.users.find_one({"user_id": user_id}, {"avg_txn_per_day": 1, "avg_txn_per_day_amount": 1})
    except PyMongoError:
        return {
            "velocity_risk": 0,
            "last_1hr_count": 0,
            "last_24hr_count": 0,
            "user_daily_avg": 1.0,
            "is_suspicious": False,
        }

    avg_per_day = float((user or {}).get("avg_txn_per_day", 1.0))
    avg_per_day_amount = float((user or {}).get("avg_txn_per_day_amount", 0.0))

    velocity_risk = 0
    if last_1hr_count > 5:
        velocity_risk += 40
    if last_24hr_count > avg_per_day * 3:
        velocity_risk += 35
    if avg_per_day_amount > 0 and new_amount > avg_per_day_amount * 5:
        velocity_risk += 25

    return {
        "velocity_risk": min(velocity_risk, 100),
        "last_1hr_count": int(last_1hr_count),
        "last_24hr_count": int(last_24hr_count),
        "user_daily_avg": round(avg_per_day, 2),
        "is_suspicious": velocity_risk > 0,
    }


async def run_low_slow_detection(user_id: str, new_amount: float, db: AsyncIOMotorDatabase) -> dict[str, Any]:
    txns = await get_last_30_days_transactions(user_id, db)
    amounts = [float(item["amount"]) for item in txns]
    zscore_result = calculate_rolling_zscore(amounts, new_amount)

    weekly_stats = await get_weekly_stats(user_id, db)
    drift_result = detect_gradual_drift(weekly_stats)

    velocity_result = await velocity_check(user_id, new_amount, db)

    # Keep weekly aggregate updated regardless of anomaly result.
    weekly_update = await update_weekly_stats(user_id, new_amount, db)

    final_score = int(
        round(
            zscore_result["risk_score"] * 0.40
            + drift_result["drift_score"] * 0.40
            + velocity_result["velocity_risk"] * 0.20
        )
    )

    explanation: list[str] = []
    if zscore_result["z_score"] > 2:
        explanation.append("Transaction amount is highly above recent 30-day behavior")
    if drift_result["drift_detected"]:
        explanation.append(drift_result["message"])
    if velocity_result["is_suspicious"]:
        explanation.append("Transaction velocity deviates from user baseline")
    if not explanation:
        explanation.append("No strong low-and-slow signal detected")

    is_low_slow_suspicious = final_score >= 60 or drift_result["drift_score"] >= 50

    if is_low_slow_suspicious:
        try:
            await db.fraud_alerts.insert_one(
                {
                    "user_id": user_id,
                    "fraud_type": "LOW_AND_SLOW",
                    "score": final_score,
                    "explanation": explanation,
                    "status": "PENDING",
                    "created_at": datetime.now(timezone.utc),
                }
            )
        except PyMongoError:
            pass

    return {
        "final_score": min(final_score, 100),
        "zscore_result": zscore_result,
        "drift_result": drift_result,
        "velocity_result": velocity_result,
        "weekly_update": weekly_update,
        "is_suspicious": is_low_slow_suspicious,
        "explanation": explanation,
    }


async def calculate_low_slow_score(
    db: AsyncIOMotorDatabase,
    user_id: str,
    new_amount: float | None = None,
) -> tuple[int, list[str]]:
    """Compatibility wrapper used by route flow.

    If new_amount is provided, compute a dynamic low-and-slow score using
    rolling amount anomaly + weekly drift + velocity checks.
    """
    weekly_stats = await get_weekly_stats(user_id=user_id, db=db)
    drift_result = detect_gradual_drift(weekly_stats)

    if new_amount is None:
        score = int(drift_result.get("drift_score", 0))
        message = str(drift_result.get("message", "No strong low-and-slow signal detected"))
        return score, [message]

    txns = await get_last_30_days_transactions(user_id=user_id, db=db)
    amounts = [float(item["amount"]) for item in txns]
    zscore_result = calculate_rolling_zscore(amounts, float(new_amount))
    velocity_result = await velocity_check(user_id=user_id, new_amount=float(new_amount), db=db)

    score = int(
        round(
            zscore_result["risk_score"] * 0.40
            + drift_result["drift_score"] * 0.40
            + velocity_result["velocity_risk"] * 0.20
        )
    )

    reasons: list[str] = []
    if zscore_result["z_score"] > 2:
        reasons.append("Transaction amount is highly above recent 30-day behavior")
    if drift_result["drift_detected"]:
        reasons.append(str(drift_result["message"]))
    if velocity_result["is_suspicious"]:
        reasons.append("Transaction velocity deviates from user baseline")
    if not reasons:
        reasons.append("No strong low-and-slow signal detected")

    return min(score, 100), reasons
