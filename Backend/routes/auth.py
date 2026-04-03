from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException
from pymongo.errors import PyMongoError

from database.mongodb import get_db
from models.schemas import LoginAttemptRequest, LoginAttemptResponse

router = APIRouter()


@router.post("/login/attempt", response_model=LoginAttemptResponse)
async def record_login_attempt(payload: LoginAttemptRequest) -> LoginAttemptResponse:
    db = get_db()
    now = datetime.now(timezone.utc)

    attempt_doc = {
        "user_id": payload.user_id,
        "device_fingerprint": payload.device_fingerprint,
        "ip_address": payload.ip_address,
        "success": payload.success,
        "failure_reason": payload.failure_reason,
        "timestamp": now,
    }

    try:
        await db.login_attempts.insert_one(attempt_doc)

        ten_min_ago = now - timedelta(minutes=10)

        attempts_from_ip = await db.login_attempts.count_documents(
            {
                "ip_address": payload.ip_address,
                "success": False,
                "timestamp": {"$gte": ten_min_ago},
            }
        )

        distinct_accounts = await db.login_attempts.distinct(
            "user_id",
            {
                "ip_address": payload.ip_address,
                "success": False,
                "timestamp": {"$gte": ten_min_ago},
            },
        )

        same_account_failures = await db.login_attempts.count_documents(
            {
                "user_id": payload.user_id,
                "success": False,
                "timestamp": {"$gte": ten_min_ago},
            }
        )

    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"Failed login-risk checks: {exc}") from exc

    risk_flag = False
    threat_type = "NONE"

    if attempts_from_ip > 5 or len(distinct_accounts) > 5:
        risk_flag = True
        threat_type = "CREDENTIAL_STUFFING"

    if same_account_failures > 3:
        risk_flag = True
        threat_type = "ACCOUNT_TAKEOVER"

    if risk_flag:
        try:
            await db.users.update_one(
                {"user_id": payload.user_id},
                {
                    "$addToSet": {"risk_profile.flags": threat_type},
                    "$set": {"risk_profile.last_flagged_at": now},
                    "$inc": {"risk_profile.risk_hits": 1},
                },
                upsert=True,
            )
        except PyMongoError as exc:
            raise HTTPException(status_code=500, detail=f"Failed risk profile update: {exc}") from exc

    return LoginAttemptResponse(
        risk_flag=risk_flag,
        attempts_count=int(attempts_from_ip),
        threat_type=threat_type,
    )
