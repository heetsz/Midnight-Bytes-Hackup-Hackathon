from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.utils.mongo import utc_now

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

CITY_COORDS = {
    "mumbai": {"city": "Mumbai", "lat": 19.0760, "lon": 72.8777},
    "delhi": {"city": "Delhi", "lat": 28.6139, "lon": 77.2090},
    "new delhi": {"city": "Delhi", "lat": 28.6139, "lon": 77.2090},
    "bengaluru": {"city": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    "bangalore": {"city": "Bengaluru", "lat": 12.9716, "lon": 77.5946},
    "hyderabad": {"city": "Hyderabad", "lat": 17.3850, "lon": 78.4867},
    "chennai": {"city": "Chennai", "lat": 13.0827, "lon": 80.2707},
    "kolkata": {"city": "Kolkata", "lat": 22.5726, "lon": 88.3639},
    "pune": {"city": "Pune", "lat": 18.5204, "lon": 73.8567},
    "ahmedabad": {"city": "Ahmedabad", "lat": 23.0225, "lon": 72.5714},
    "jaipur": {"city": "Jaipur", "lat": 26.9124, "lon": 75.7873},
    "lucknow": {"city": "Lucknow", "lat": 26.8467, "lon": 80.9462},
}


def _normalize_city(raw: str | None) -> str:
    if not raw:
        return "unknown"
    city = raw.split("->")[-1].split(",")[0].strip().lower()
    return city or "unknown"


@router.get("/stats")
async def dashboard_stats(db: AsyncIOMotorDatabase = Depends(get_db)):
    now = datetime.now(timezone.utc)
    start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    total_today = await db.transactions.count_documents({"timestamp": {"$gte": start_of_day}})

    # If there is no activity today, use a recent window so dashboard doesn't stay empty.
    if total_today > 0:
        active_window = {"$gte": start_of_day}
    else:
        total_last_7d = await db.transactions.count_documents({"timestamp": {"$gte": last_7d}})
        active_window = {"$gte": last_7d if total_last_7d > 0 else last_30d}

    total_for_window = await db.transactions.count_documents({"timestamp": active_window})

    blocked_cursor = db.transactions.find(
        {
            "timestamp": active_window,
            "pipeline_results.model_decision": "block",
        }
    )
    blocked_count = 0
    blocked_amount = 0.0
    fraud_by_type = {
        "ATO": 0,
        "Low & Slow": 0,
        "Velocity": 0,
        "Fraud Ring": 0,
        "Synthetic ID": 0,
        "False Positive": 0,
    }

    async for item in blocked_cursor:
        blocked_count += 1
        blocked_amount += float(item.get("frontend_payload", {}).get("transaction_amt", 0))
        q = item.get("pipeline_results", {}).get("queue_outputs", {})

        if q.get("ato_prob", 0) >= 0.5:
            fraud_by_type["ATO"] += 1
        elif q.get("seq_anomaly_score", 0) >= 0.5:
            fraud_by_type["Low & Slow"] += 1
        elif q.get("tabnet_logit", -10) >= 0.5:
            fraud_by_type["Velocity"] += 1
        elif q.get("synth_id_prob", 0) >= 0.4:
            fraud_by_type["Synthetic ID"] += 1
        else:
            fraud_by_type["Fraud Ring"] += 1

    return {
        "total_transactions_today": total_for_window,
        "fraud_blocked_today": {
            "count": blocked_count,
            "amount_sum": round(blocked_amount, 2),
        },
        "fraud_by_type": [
            {"fraud_type": name, "count": count} for name, count in fraud_by_type.items()
        ],
    }


@router.get("/fraud-ring")
async def fraud_ring_graph(db: AsyncIOMotorDatabase = Depends(get_db)):
    device_users: dict[str, set[str]] = {}

    async for txn in db.transactions.find({}, {"device_hash": 1, "user_key": 1}):
        device_hash = txn.get("device_hash")
        user_key = txn.get("user_key")
        if not device_hash or not user_key:
            continue
        device_users.setdefault(device_hash, set()).add(user_key)

    user_keys = set()
    for users in device_users.values():
        if len(users) >= 2:
            user_keys.update(users)

    users_map: dict[str, dict] = {}
    if user_keys:
        users_cursor = db.users.find({"user_key": {"$in": list(user_keys)}})
        users_map = {u["user_key"]: u async for u in users_cursor}

    nodes = []
    links = []

    for user_key in user_keys:
        user = users_map.get(user_key, {})
        risk_score = 20
        if user_key:
            txn_count = await db.transactions.count_documents({"user_key": user_key})
            risk_score = min(100, max(20, txn_count * 8))
        nodes.append(
            {
                "id": user_key,
                "label": user.get("name", user_key),
                "node_type": "user",
                "risk_score": risk_score,
            }
        )

    for device_hash, users in device_users.items():
        if len(users) < 2:
            continue
        device_id = f"device:{device_hash[:12]}"
        nodes.append(
            {
                "id": device_id,
                "label": device_id,
                "node_type": "device",
                "risk_score": 90,
            }
        )
        for user_key in users:
            links.append(
                {
                    "source": user_key,
                    "target": device_id,
                    "relation": "shared_device",
                    "confidence": 0.95,
                }
            )

    if not nodes:
        users_cursor = db.users.find({}).limit(4)
        fallback_users = [u async for u in users_cursor]
        for index, user in enumerate(fallback_users):
            nodes.append(
                {
                    "id": user["user_key"],
                    "label": user.get("name", user["user_key"]),
                    "node_type": "user",
                    "risk_score": 50 + index * 10,
                }
            )
        if len(fallback_users) >= 2:
            links.append(
                {
                    "source": fallback_users[0]["user_key"],
                    "target": fallback_users[1]["user_key"],
                    "relation": "ring_link",
                    "confidence": 0.75,
                }
            )

    return {
        "nodes": nodes,
        "links": links,
        "generated_at": utc_now(),
    }


@router.get("/location-heatmap")
async def location_heatmap(db: AsyncIOMotorDatabase = Depends(get_db)):
    pipeline = [
        {
            "$project": {
                "location": "$frontend_payload.location",
                "decision": "$pipeline_results.model_decision",
                "amount": "$frontend_payload.transaction_amt",
            }
        }
    ]

    city_stats: dict[str, dict] = {}

    async for row in db.transactions.aggregate(pipeline):
        city_key = _normalize_city(row.get("location"))
        if city_key not in CITY_COORDS:
            continue

        if city_key not in city_stats:
            city_stats[city_key] = {
                "city": CITY_COORDS[city_key]["city"],
                "location": [CITY_COORDS[city_key]["lat"], CITY_COORDS[city_key]["lon"]],
                "fraud": 0,
                "transactions": 0,
                "amount_sum": 0.0,
            }

        city_stats[city_key]["transactions"] += 1
        city_stats[city_key]["amount_sum"] += float(row.get("amount") or 0)

        # Treat block + mfa as suspicious/fraudulent activity for heatmap intensity.
        if row.get("decision") in {"block", "mfa"}:
            city_stats[city_key]["fraud"] += 1

    result = sorted(city_stats.values(), key=lambda item: item["fraud"], reverse=True)

    return {
        "cities": result,
        "generated_at": utc_now(),
    }
