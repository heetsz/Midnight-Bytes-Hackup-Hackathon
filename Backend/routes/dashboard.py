from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from database.mongodb import get_db
from models.schemas import DashboardStatsResponse

router = APIRouter()


@router.get("/dashboard/stats", response_model=DashboardStatsResponse)
async def get_dashboard_stats() -> DashboardStatsResponse:
    db = get_db()
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    try:
        total_transactions_today = await db.transactions.count_documents(
            {"timestamp": {"$gte": today_start}}
        )

        blocked_pipeline = [
            {
                "$match": {
                    "timestamp": {"$gte": today_start},
                    "decision": "BLOCK",
                }
            },
            {
                "$group": {
                    "_id": None,
                    "count": {"$sum": 1},
                    "amount_sum": {"$sum": "$amount"},
                }
            },
        ]
        blocked_result = await db.transactions.aggregate(blocked_pipeline).to_list(length=1)

        fraud_by_type_pipeline = [
            {"$match": {"timestamp": {"$gte": today_start}}},
            {
                "$group": {
                    "_id": "$fraud_type",
                    "count": {"$sum": 1},
                }
            },
            {"$sort": {"count": -1}},
        ]
        fraud_by_type = await db.transactions.aggregate(fraud_by_type_pipeline).to_list(length=100)

        top_users_pipeline = [
            {"$sort": {"fraud_score": -1}},
            {
                "$group": {
                    "_id": "$user_id",
                    "max_fraud_score": {"$max": "$fraud_score"},
                    "latest_decision": {"$first": "$decision"},
                }
            },
            {"$sort": {"max_fraud_score": -1}},
            {"$limit": 5},
        ]
        top_users = await db.transactions.aggregate(top_users_pipeline).to_list(length=5)

        alerts_pending_resolution = await db.fraud_alerts.count_documents({"status": "PENDING"})

    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed dashboard query: {exc}") from exc

    blocked = blocked_result[0] if blocked_result else {"count": 0, "amount_sum": 0.0}

    fraud_by_type_data = [
        {"fraud_type": item.get("_id", "UNKNOWN"), "count": int(item.get("count", 0))}
        for item in fraud_by_type
    ]

    top_users_data = [
        {
            "user_id": item.get("_id"),
            "max_fraud_score": int(item.get("max_fraud_score", 0)),
            "latest_decision": item.get("latest_decision", "UNKNOWN"),
        }
        for item in top_users
    ]

    return DashboardStatsResponse(
        total_transactions_today=total_transactions_today,
        fraud_blocked_today={
            "count": int(blocked.get("count", 0)),
            "amount_sum": float(blocked.get("amount_sum", 0.0)),
        },
        fraud_by_type=fraud_by_type_data,
        top_high_risk_users=top_users_data,
        alerts_pending_resolution=alerts_pending_resolution,
        generated_at=now,
    )
