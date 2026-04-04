from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.schemas import UserCreateRequest
from app.utils.mongo import serialize_id, utc_now

router = APIRouter(prefix="/api/users", tags=["users"])
public_router = APIRouter(tags=["users"])


def _to_aware_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_user(payload: UserCreateRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    now = payload.created_at or utc_now()
    user_doc = {
        "user_key": payload.user_key,
        "name": payload.name,
        "email": payload.email,
        "phone_no": payload.phone_no,
        "created_at": now,
        "user_txn_count": 0,
        "device_centroid": payload.device_centroid,
        "known_devices": [],
        "recent_behavior_seq": [],
        "transaction_ids": [],
    }

    try:
        await db.users.insert_one(user_doc)
    except Exception as exc:
        raise HTTPException(status_code=409, detail=f"User creation failed: {exc}") from exc

    created = await db.users.find_one({"user_key": payload.user_key})
    return serialize_id(created)


def _risk_label(avg_score: float) -> str:
    if avg_score >= 70:
        return "HIGH_RISK"
    if avg_score >= 40:
        return "MEDIUM_RISK"
    return "LOW_RISK"


@router.get("/search")
async def search_users(
    query: str = Query(default="", description="Search by user_key, name, email, phone_no"),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    mongo_query = {}
    if query.strip():
        mongo_query = {
            "$or": [
                {"user_key": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}},
                {"email": {"$regex": query, "$options": "i"}},
                {"phone_no": {"$regex": query, "$options": "i"}},
            ]
        }

    users = [item async for item in db.users.find(mongo_query).sort("created_at", -1).limit(limit)]
    user_keys = [item["user_key"] for item in users]

    txns_by_user: dict[str, list[dict]] = {key: [] for key in user_keys}
    if user_keys:
        cursor = db.transactions.find({"user_key": {"$in": user_keys}}).sort("timestamp", -1)
        async for txn in cursor:
            txns_by_user.setdefault(txn["user_key"], []).append(txn)

    mapped = []
    for user in users:
        txns = txns_by_user.get(user["user_key"], [])
        created_at = _to_aware_utc(user.get("created_at"))
        avg_score = (
            sum(item.get("pipeline_results", {}).get("calibrated_prob", 0) * 100 for item in txns)
            / max(1, len(txns))
        )
        avg_txn_per_day = user.get("user_txn_count", 0) / max(
            1,
            (datetime.now(timezone.utc) - created_at).days + 1,
        )

        mapped.append(
            {
                "user_id": user["user_key"],
                "name": user.get("name") or user["user_key"],
                "city": user.get("city", "Unknown"),
                "member_since": user.get("created_at"),
                "risk_label": _risk_label(avg_score),
                "avg_txn_per_day": round(avg_txn_per_day, 2),
                "trusted_devices": len(user.get("known_devices", [])),
                "usual_login_hour": int(user.get("usual_login_hour", 10)),
            }
        )

    return {"users": mapped, "generated_at": utc_now()}


@router.get("")
async def list_users(
    q: str = Query(default="", description="Search by user_key, name, email, phone_no"),
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return await search_users(query=q, limit=limit, db=db)


@router.get("/{user_key}")
async def get_user(user_key: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"user_key": user_key})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return serialize_id(user)


@public_router.get("/api/user/{user_key}/profile")
async def get_user_profile(user_key: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    user = await db.users.find_one({"user_key": user_key})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    txn_cursor = db.transactions.find({"user_key": user_key}).sort("timestamp", -1).limit(25)
    transactions = [item async for item in txn_cursor]

    recent_transactions = []
    for item in transactions:
        fraud_score = int(item.get("pipeline_results", {}).get("calibrated_prob", 0) * 100)
        frontend_payload = item.get("frontend_payload", {})
        recent_transactions.append(
            {
                "txn_id": str(item.get("_id")),
                "amount": float(frontend_payload.get("transaction_amt", 0)),
                "merchant_name": frontend_payload.get("merchant_name", "Unknown Merchant"),
                "fraud_score": fraud_score,
                "timestamp": item.get("timestamp"),
                "city": user.get("city", "Unknown"),
            }
        )

    login_history = []
    known_devices = user.get("known_devices", [])
    for device in known_devices[:20]:
        login_history.append(
            {
                "ip_address": "0.0.0.0",
                "success": int(device.get("device_match_ord", 0)) > 0,
                "failure_reason": None if int(device.get("device_match_ord", 0)) > 0 else "Unrecognized device",
                "timestamp": device.get("last_seen_at") or utc_now(),
            }
        )

    if not login_history:
        fallback_time = utc_now() - timedelta(hours=2)
        login_history = [
            {
                "ip_address": "0.0.0.0",
                "success": True,
                "failure_reason": None,
                "timestamp": fallback_time,
            }
        ]

    return {
        "user": {
            "user_id": user.get("user_key"),
            "name": user.get("name"),
            "city": user.get("city", "Unknown"),
            "usual_login_hour": int(user.get("usual_login_hour", 10)),
            "avg_txn_per_day": round(
                user.get("user_txn_count", 0)
                / max(1, (datetime.now(timezone.utc) - _to_aware_utc(user.get("created_at"))).days + 1),
                2,
            ),
            "trusted_devices": [item.get("device_hash", "") for item in known_devices],
        },
        "recent_transactions": recent_transactions,
        "login_history": login_history,
    }
