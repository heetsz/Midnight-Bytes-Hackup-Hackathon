from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pymongo.errors import PyMongoError

from database.mongodb import get_db
from models.schemas import (
    FeedbackRequest,
    LiveTransactionItem,
    LiveTransactionsResponse,
    UserSearchResponse,
    UserSummaryItem,
    TransactionAnalyzeRequest,
    TransactionAnalyzeResponse,
    UserProfileResponse,
)
from services.ato_detector import calculate_ato_score
from services.fraud_engine import (
    calculate_amount_anomaly_score,
    calculate_final_score,
    calculate_velocity_score,
    get_decision,
    infer_fraud_type,
)
from services.low_slow_detector import calculate_low_slow_score
from services.ring_detector import calculate_ring_score
from services.telegram_service import send_fraud_alert
from utils.explainability import get_risk_level, merge_explanations

router = APIRouter()


@router.get("/transactions/live", response_model=LiveTransactionsResponse)
async def get_live_transactions(
    limit: int = Query(default=15, ge=1, le=100),
) -> LiveTransactionsResponse:
    db = get_db()
    now = datetime.now(timezone.utc)

    try:
        raw_transactions = await (
            db.transactions.find(
                {},
                {
                    "_id": 0,
                    "txn_id": 1,
                    "user_id": 1,
                    "amount": 1,
                    "fraud_score": 1,
                    "merchant_name": 1,
                    "timestamp": 1,
                    "city": 1,
                },
            )
            .sort("timestamp", -1)
            .limit(limit)
            .to_list(length=limit)
        )

        user_ids = [
            str(item.get("user_id"))
            for item in raw_transactions
            if item.get("user_id") is not None
        ]

        users = await db.users.find(
            {"user_id": {"$in": user_ids}},
            {"_id": 0, "user_id": 1, "name": 1},
        ).to_list(length=500)
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed live transaction query: {exc}") from exc

    name_map = {
        str(user.get("user_id")): str(user.get("name", user.get("user_id", "Unknown")))
        for user in users
    }

    transactions = [
        LiveTransactionItem(
            txn_id=str(item.get("txn_id", "-")),
            user_id=str(item.get("user_id", "-")),
            username=name_map.get(str(item.get("user_id", "")), str(item.get("user_id", "-"))),
            amount=float(item.get("amount", 0.0)),
            fraud_score=int(item.get("fraud_score", 0)),
            merchant_name=str(item.get("merchant_name", "Unknown merchant")),
            timestamp=item.get("timestamp", now),
            location=str(item.get("city", "Unknown")),
        )
        for item in raw_transactions
    ]

    return LiveTransactionsResponse(transactions=transactions, generated_at=now)


@router.get("/users/search", response_model=UserSearchResponse)
async def search_users(
    query: str = Query(default="", min_length=0, max_length=80),
    limit: int = Query(default=20, ge=1, le=100),
) -> UserSearchResponse:
    db = get_db()
    now = datetime.now(timezone.utc)

    filter_query: dict = {}
    if query.strip():
        filter_query = {
            "$or": [
                {"user_id": {"$regex": query, "$options": "i"}},
                {"name": {"$regex": query, "$options": "i"}},
                {"city": {"$regex": query, "$options": "i"}},
            ]
        }

    try:
        users = await db.users.find(filter_query, {"_id": 0}).limit(limit).to_list(length=limit)
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed users search query: {exc}") from exc

    user_items: list[UserSummaryItem] = []

    for user in users:
        user_id = str(user.get("user_id", ""))

        try:
            first_txn = await (
                db.transactions.find({"user_id": user_id}, {"_id": 0, "timestamp": 1})
                .sort("timestamp", 1)
                .limit(1)
                .to_list(length=1)
            )
        except PyMongoError:
            first_txn = []

        member_since = (
            first_txn[0].get("timestamp") if first_txn and first_txn[0].get("timestamp") else now
        )

        risk_profile = user.get("risk_profile", {})
        risk_score = int(risk_profile.get("risk_score", 0))
        flags = risk_profile.get("flags", [])
        risk_label = (
            "HIGH RISK"
            if risk_score >= 70 or len(flags) >= 2
            else "MEDIUM RISK"
            if risk_score >= 35 or len(flags) == 1
            else "LOW RISK"
        )

        user_items.append(
            UserSummaryItem(
                user_id=user_id,
                name=str(user.get("name", user_id)),
                city=str(user.get("city", "Unknown")),
                member_since=member_since,
                risk_label=risk_label,
                avg_txn_per_day=float(user.get("avg_txn_per_day", 0.0)),
                trusted_devices=len(user.get("trusted_devices", [])),
                usual_login_hour=int(user.get("usual_login_hour", 12)),
            )
        )

    return UserSearchResponse(users=user_items, generated_at=now)


@router.post("/transaction/analyze", response_model=TransactionAnalyzeResponse)
async def analyze_transaction(payload: TransactionAnalyzeRequest) -> TransactionAnalyzeResponse:
    db = get_db()
    now = datetime.now(timezone.utc)

    try:
        user = await db.users.find_one({"user_id": payload.user_id})
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load user: {exc}") from exc

    if not user:
        user = {
            "user_id": payload.user_id,
            "name": payload.user_id,
            "trusted_devices": [payload.device_fingerprint],
            "usual_cities": [payload.city],
            "usual_login_hour": now.hour,
            "avg_txn_per_day": 1.0,
            "risk_profile": {"risk_score": 0, "flags": []},
        }
        try:
            await db.users.insert_one(user)
        except PyMongoError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to create user: {exc}") from exc

    ato_score, ato_reasons = calculate_ato_score(user, payload, now)
    amount_score, amount_reasons, _ = await calculate_amount_anomaly_score(
        db, payload.user_id, payload.amount, now
    )
    low_slow_score, low_slow_reasons = await calculate_low_slow_score(db, payload.user_id)
    velocity_score, velocity_reasons, velocity_meta = await calculate_velocity_score(
        db, user, payload.user_id, now
    )
    ring_score, ring_reasons, ring_conf = await calculate_ring_score(db, payload.user_id)

    final_score = calculate_final_score(
        ato_score=ato_score,
        amount_score=amount_score,
        low_slow_score=low_slow_score,
        velocity_score=velocity_score,
        ring_score=ring_score,
    )
    decision = get_decision(final_score)
    risk_level = get_risk_level(final_score)

    explanation = merge_explanations(
        ato_reasons,
        amount_reasons,
        low_slow_reasons,
        velocity_reasons,
        ring_reasons,
    )

    fraud_type = infer_fraud_type(
        {
            "ato": ato_score,
            "amount": amount_score,
            "low_slow": low_slow_score,
            "velocity": velocity_score,
            "ring": ring_score,
        }
    )

    txn_id = f"TXN_{uuid4().hex[:10].upper()}"
    transaction_doc = {
        "txn_id": txn_id,
        "user_id": payload.user_id,
        "amount": payload.amount,
        "merchant_name": payload.merchant_name,
        "merchant_category": payload.merchant_category,
        "payment_method": payload.payment_method,
        "device_fingerprint": payload.device_fingerprint,
        "ip_address": payload.ip_address,
        "city": payload.city,
        "timestamp": now,
        "fraud_score": final_score,
        "decision": decision,
        "risk_level": risk_level,
        "fraud_type": fraud_type,
        "signals": {
            "ato_score": ato_score,
            "amount_score": amount_score,
            "low_slow_score": low_slow_score,
            "velocity_score": velocity_score,
            "ring_score": ring_score,
            "ring_confidence": ring_conf,
            **velocity_meta,
        },
        "explanation": explanation,
        "is_fraud": None,
        "review": None,
    }

    try:
        await db.transactions.insert_one(transaction_doc)
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store transaction: {exc}") from exc

    if final_score > 70:
        alert_doc = {
            "txn_id": txn_id,
            "user_id": payload.user_id,
            "fraud_score": final_score,
            "decision": decision,
            "fraud_type": fraud_type,
            "explanation": explanation,
            "status": "PENDING",
            "created_at": now,
        }
        try:
            await db.fraud_alerts.insert_one(alert_doc)
        except PyMongoError as exc:
            raise HTTPException(status_code=500, detail=f"Failed to create alert: {exc}") from exc

        await send_fraud_alert(
            {
                "user_name": user.get("name", payload.user_id),
                "user_id": payload.user_id,
                "amount": payload.amount,
                "merchant_name": payload.merchant_name,
                "fraud_score": final_score,
                "decision": decision,
                "explanation": explanation,
                "timestamp": now.isoformat(),
            }
        )

    return TransactionAnalyzeResponse(
        txn_id=txn_id,
        fraud_score=final_score,
        risk_level=risk_level,
        decision=decision,
        explanation=explanation,
    )


@router.get("/user/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(user_id: str) -> UserProfileResponse:
    db = get_db()

    try:
        user = await db.users.find_one({"user_id": user_id}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        transactions = await (
            db.transactions.find({"user_id": user_id}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(10)
            .to_list(length=10)
        )
        weekly_stats = await (
            db.user_weekly_stats.find({"user_id": user_id}, {"_id": 0})
            .sort("week_start", -1)
            .limit(4)
            .to_list(length=4)
        )
        open_alerts = await db.fraud_alerts.find(
            {"user_id": user_id, "status": "PENDING"}, {"_id": 0}
        ).to_list(length=200)
        login_history = await (
            db.login_attempts.find({"user_id": user_id}, {"_id": 0})
            .sort("timestamp", -1)
            .limit(20)
            .to_list(length=20)
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch profile data: {exc}") from exc

    return UserProfileResponse(
        user=user,
        recent_transactions=transactions,
        weekly_stats=weekly_stats,
        open_alerts=open_alerts,
        login_history=login_history,
    )


@router.post("/feedback/{txn_id}")
async def submit_feedback(txn_id: str, payload: FeedbackRequest) -> dict:
    db = get_db()
    now = datetime.now(timezone.utc)

    try:
        txn = await db.transactions.find_one({"txn_id": txn_id})
        if not txn:
            raise HTTPException(status_code=404, detail="Transaction not found")

        await db.transactions.update_one(
            {"txn_id": txn_id},
            {
                "$set": {
                    "is_fraud": payload.is_confirmed_fraud,
                    "review": {
                        "analyst_notes": payload.analyst_notes,
                        "reviewed_at": now,
                    },
                }
            },
        )

        if payload.is_confirmed_fraud:
            await db.users.update_one(
                {"user_id": txn.get("user_id")},
                {
                    "$set": {"risk_profile.last_confirmed_fraud_at": now},
                    "$inc": {"risk_profile.confirmed_fraud_count": 1},
                    "$addToSet": {"risk_profile.flags": "CONFIRMED_FRAUD"},
                },
            )

            await db.model_retrain_queue.insert_one(
                {
                    "txn_id": txn_id,
                    "user_id": txn.get("user_id"),
                    "status": "PENDING",
                    "created_at": now,
                }
            )

        await db.fraud_alerts.update_many(
            {"txn_id": txn_id, "status": "PENDING"},
            {"$set": {"status": "RESOLVED", "resolved_at": now}},
        )

    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to store feedback: {exc}") from exc

    return {"success": True, "message": "Feedback recorded successfully"}
