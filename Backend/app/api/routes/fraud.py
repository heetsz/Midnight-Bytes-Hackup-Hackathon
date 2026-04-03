from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException

from app.core.database import get_database
from app.models.schemas import StatsResponse, TransactionRequest, TransactionResult
from app.services.anomaly_service import detect_anomalies
from app.services.decision_service import make_decision
from app.services.explainability_service import generate_reasons
from app.services.profile_service import get_or_create_user_profile, update_user_profile
from app.services.risk_service import calculate_risk_score
from app.utils.serializer import serialize_document

router = APIRouter(tags=["fraud"])
db = get_database()


@router.post("/transaction", response_model=TransactionResult)
def process_transaction(payload: TransactionRequest) -> TransactionResult:
    previous_profile = get_or_create_user_profile(db, payload.user_id)
    anomalies = detect_anomalies(previous_profile, payload)
    risk_score = calculate_risk_score(anomalies)
    decision = make_decision(risk_score)
    reasons = generate_reasons(anomalies, risk_score)

    update_user_profile(db, payload)

    transaction_doc: dict[str, Any] = {
        "user_id": payload.user_id,
        "amount": payload.amount,
        "location": payload.location,
        "device": payload.device,
        "timestamp": payload.timestamp,
        "risk_score": risk_score,
        "decision": decision,
        "reasons": reasons,
        "created_at": datetime.now(timezone.utc),
    }

    insert_result = db["transactions"].insert_one(transaction_doc)

    if decision in {"MFA", "BLOCK"}:
        db["alerts"].insert_one(
            {
                "transaction_id": insert_result.inserted_id,
                "user_id": payload.user_id,
                "risk_score": risk_score,
                "decision": decision,
                "reasons": reasons,
                "created_at": datetime.now(timezone.utc),
            }
        )

    return TransactionResult(risk_score=risk_score, decision=decision, reasons=reasons)


@router.get("/user/{user_id}")
def get_user_profile(user_id: str) -> dict[str, Any]:
    profile = db["users"].find_one({"user_id": user_id}, {"_id": 0})
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return serialize_document(profile)


@router.get("/transactions")
def get_transactions() -> list[dict[str, Any]]:
    transactions = list(db["transactions"].find().sort("created_at", -1))
    return serialize_document(transactions)


@router.get("/alerts")
def get_alerts() -> list[dict[str, Any]]:
    alerts = list(db["alerts"].find().sort("created_at", -1))
    return serialize_document(alerts)


@router.get("/stats", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    total_transactions = db["transactions"].count_documents({})
    fraud_count = db["transactions"].count_documents({"decision": {"$in": ["MFA", "BLOCK"]}})

    pipeline = [
        {"$group": {"_id": None, "avg_risk_score": {"$avg": "$risk_score"}}},
    ]
    aggregate_result = list(db["transactions"].aggregate(pipeline))
    average_risk_score = round(float(aggregate_result[0]["avg_risk_score"]), 2) if aggregate_result else 0.0

    return StatsResponse(
        total_transactions=total_transactions,
        fraud_count=fraud_count,
        average_risk_score=average_risk_score,
    )
