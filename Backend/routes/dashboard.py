from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from database.mongodb import get_db
from models.schemas import DashboardStatsResponse, FraudRingGraphResponse, FraudRingLink, FraudRingNode

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


@router.get("/dashboard/fraud-ring", response_model=FraudRingGraphResponse)
async def get_fraud_ring_graph() -> FraudRingGraphResponse:
    db = get_db()
    now = datetime.now(timezone.utc)

    try:
        ring_docs = await db.fraud_ring_links.find({}, {"_id": 0}).to_list(length=500)
        users = await db.users.find({}, {"_id": 0, "user_id": 1, "name": 1, "risk_profile": 1}).to_list(
            length=1000
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed fraud-ring query: {exc}") from exc

    user_map = {str(user.get("user_id")): user for user in users}
    node_map: dict[str, FraudRingNode] = {}
    links: list[FraudRingLink] = []

    for ring in ring_docs:
        source_id = str(ring.get("user_id", ""))
        if not source_id:
            continue

        source_user = user_map.get(source_id, {})
        source_risk = int(source_user.get("risk_profile", {}).get("risk_score", 0))

        node_map[source_id] = FraudRingNode(
            id=source_id,
            label=str(source_user.get("name", source_id)),
            node_type="user",
            risk_score=source_risk,
        )

        shared_device = str(ring.get("shared_device", "")).strip()
        confidence = float(ring.get("confidence", 0.0))

        if shared_device:
            device_id = f"device:{shared_device}"
            node_map[device_id] = FraudRingNode(
                id=device_id,
                label=shared_device,
                node_type="device",
                risk_score=max(40, int(confidence * 100)),
            )
            links.append(
                FraudRingLink(
                    source=source_id,
                    target=device_id,
                    relation="shared_device",
                    confidence=confidence,
                )
            )

        for linked_user_id in ring.get("linked_user_ids", []):
            target_id = str(linked_user_id)
            target_user = user_map.get(target_id, {})
            target_risk = int(target_user.get("risk_profile", {}).get("risk_score", 0))

            node_map[target_id] = FraudRingNode(
                id=target_id,
                label=str(target_user.get("name", target_id)),
                node_type="user",
                risk_score=target_risk,
            )

            links.append(
                FraudRingLink(
                    source=source_id,
                    target=target_id,
                    relation="ring_link",
                    confidence=confidence,
                )
            )

    return FraudRingGraphResponse(nodes=list(node_map.values()), links=links, generated_at=now)
