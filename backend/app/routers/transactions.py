import hashlib
import json
import math

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.services.model_inference import run_inference
from app.services.transaction_stream import transaction_stream
from app.schemas import TransactionProcessRequest
from app.utils.mongo import serialize_id, utc_now

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _hash_fingerprint(payload: TransactionProcessRequest) -> str:
    raw = json.dumps(payload.fingerprint.model_dump(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ui_decision(decision: str) -> str:
    if decision == "block":
        return "BLOCK"
    if decision == "mfa":
        return "REVIEW"
    return "APPROVE"


def _to_live_transaction(item: dict, user: dict) -> dict:
    user_key = item.get("user_key", "unknown")
    frontend_payload = item.get("frontend_payload", {})
    decision = item.get("pipeline_results", {}).get("model_decision", "approve")
    fraud_score = int(item.get("pipeline_results", {}).get("calibrated_prob", 0) * 100)
    why_flagged = item.get("pipeline_results", {}).get("why_flagged")

    return {
        "txn_id": str(item.get("_id")),
        "user_id": user_key,
        "username": user.get("name", user_key),
        "amount": float(frontend_payload.get("transaction_amt", 0)),
        "fraud_score": fraud_score,
        "decision": _ui_decision(decision),
        "merchant_name": frontend_payload.get("merchant_name", "Unknown Merchant"),
        "timestamp": item.get("timestamp"),
        "location": frontend_payload.get("location") or user.get("city", "Unknown"),
        "why_flagged": why_flagged,
    }


@router.get("/live")
async def live_transactions(
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db.transactions.find({}).sort("timestamp", -1).limit(limit)
    rows = [item async for item in cursor]

    user_keys = list({item.get("user_key") for item in rows if item.get("user_key")})
    users_map: dict[str, dict] = {}
    if user_keys:
        users = db.users.find({"user_key": {"$in": user_keys}})
        users_map = {u["user_key"]: u async for u in users}

    transactions = []
    for item in rows:
        user_key = item.get("user_key", "unknown")
        user = users_map.get(user_key, {})
        transactions.append(_to_live_transaction(item, user))

    return {"transactions": transactions, "generated_at": utc_now()}


@router.websocket("/ws/live")
async def live_transactions_ws(websocket: WebSocket):
    await transaction_stream.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await transaction_stream.disconnect(websocket)


@router.post("/process", status_code=status.HTTP_201_CREATED)
async def process_transaction(payload: TransactionProcessRequest, db: AsyncIOMotorDatabase = Depends(get_db)):
    now = utc_now()

    try:
        # Trip 1: hash + lookup/insert device
        device_hash = _hash_fingerprint(payload)
        device = await db.devices.find_one({"device_hash": device_hash})
        if not device:
            await db.devices.insert_one(
                {
                    "device_hash": device_hash,
                    "created_at": now,
                    "fingerprint": payload.fingerprint.model_dump(),
                }
            )

        # Trip 2: user enrichment with embedded fields
        user = await db.users.find_one({"user_key": payload.user_key})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        known_devices = user.get("known_devices", [])
        known_index = next((i for i, d in enumerate(known_devices) if d.get("device_hash") == device_hash), None)

        if known_index is None:
            device_match_ord = 0
            known_devices.append(
                {
                    "device_hash": device_hash,
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "device_match_ord": 0,
                }
            )
        else:
            current_ord = known_devices[known_index].get("device_match_ord", 1)
            device_match_ord = min(2, max(1, current_ord))
            known_devices[known_index]["last_seen_at"] = now
            known_devices[known_index]["device_match_ord"] = device_match_ord

        # Trip 3: previous transaction context
        last_txn = await db.transactions.find_one(
            {"user_key": payload.user_key},
            sort=[("timestamp", -1)],
        )

        user_txn_count = int(user.get("user_txn_count", 0))
        txn_rank = user_txn_count + 1

        if last_txn:
            delta_t = max(0.0, (now - last_txn["timestamp"]).total_seconds())
        else:
            delta_t = 0.0

        delta_t_norm = min(1.0, delta_t / 86400.0)

        amount = payload.frontend_payload.transaction_amt
        base_avg = float(last_txn.get("frontend_payload", {}).get("transaction_amt", amount)) if last_txn else amount
        denom = max(1.0, base_avg)
        amt_zscore = abs((amount - base_avg) / denom)

        m_fail_count = sum(1 for item in user.get("recent_behavior_seq", []) if item.get("type_idx") == 3)
        m_all_fail = 1 if m_fail_count > 0 else 0

        novelty = 1.0 if known_index is None else 0.0
        device_dist_score = min(1.0, novelty + 0.05 * max(0, min(4, m_fail_count)))

        effective_location = (
            payload.frontend_payload.location
            or user.get("city")
            or "Unknown"
        )

        inference = run_inference(
            amount=amount,
            delta_t_norm=delta_t_norm,
            amt_zscore=amt_zscore,
            m_fail_count=m_fail_count,
            txn_rank=txn_rank,
            device_novelty=novelty,
            device_dist_score=device_dist_score,
            location=effective_location,
            known_device=known_index is not None,
            card1=payload.card1,
            d1=payload.d1,
            d2=payload.d2,
            d3=payload.d3,
            v_cols=payload.v_cols,
            c_cols=payload.c_cols,
            m_cols=payload.m_cols,
        )
        model_decision = inference.model_decision
        calibrated_prob = inference.calibrated_prob
        stacker_score = inference.stacker_score

        backend_snapshot = {
            "delta_t": round(delta_t, 4),
            "delta_t_norm": round(delta_t_norm, 4),
            "txn_rank": txn_rank,
            "amt_zscore": round(amt_zscore, 4),
            "M_fail_count": m_fail_count,
            "M_all_fail": m_all_fail,
            "card1": payload.card1,
            "D1": payload.d1,
            "D2": payload.d2,
            "D3": payload.d3,
            "v_cols": payload.v_cols,
            "c_cols": payload.c_cols,
            "m_cols": payload.m_cols,
        }

        pipeline_results = {
            "model_decision": model_decision,
            "calibrated_prob": calibrated_prob,
            "stacker_score": stacker_score,
            "model_source": inference.model_source,
            "base_outputs": inference.base_outputs,
            "queue_outputs": inference.queue_outputs,
            "why_flagged": inference.why_flagged,
        }

        txn_doc = {
            "user_key": payload.user_key,
            "device_hash": device_hash,
            "timestamp": now,
            "frontend_payload": payload.frontend_payload.model_dump(),
            "backend_snapshot": backend_snapshot,
            "pipeline_results": pipeline_results,
        }

        # Trip 4: save unified transaction + update user's behavior sequence and transaction IDs
        insert_result = await db.transactions.insert_one(txn_doc)
        txn_id = str(insert_result.inserted_id)

        behavior_event = {
            "type_idx": 3 if model_decision == "block" else 2 if model_decision == "mfa" else 1,
            "log_amount": round(math.log(max(amount, 1.0)), 6),
            "step_norm": round(min(1.0, txn_rank / 1000.0), 6),
            "timestamp": now,
        }

        await db.users.update_one(
            {"user_key": payload.user_key},
            {
                "$set": {"known_devices": known_devices},
                "$inc": {"user_txn_count": 1},
                "$push": {
                    "recent_behavior_seq": {
                        "$each": [behavior_event],
                        "$slice": -50,
                    },
                    "transaction_ids": txn_id,
                },
            },
        )

        live_payload = _to_live_transaction(
            {
                "_id": insert_result.inserted_id,
                "user_key": payload.user_key,
                "frontend_payload": payload.frontend_payload.model_dump(),
                "timestamp": now,
                "pipeline_results": pipeline_results,
            },
            user,
        )
        await transaction_stream.broadcast(
            {
                "type": "transaction.created",
                "transaction": live_payload,
                "generated_at": now.isoformat(),
            }
        )

        return {
            "transaction_id": txn_id,
            "user_key": payload.user_key,
            "device_hash": device_hash,
            "decision": model_decision,
            "calibrated_prob": calibrated_prob,
            "stacker_score": stacker_score,
            "model_source": inference.model_source,
            "why_flagged": inference.why_flagged,
            "timestamp": now,
        }
    except HTTPException:
        # Let explicit HTTP errors (like 404 User not found) propagate.
        raise
    except Exception as exc:  # pragma: no cover - defensive fallback for demo
        print(f"[process_transaction] unexpected error for user {payload.user_key}: {exc!r}")
        # Fail closed for security: treat as high risk, but still
        # record a minimal transaction and broadcast it so the
        # dashboard live feed stays in sync.
        fallback_pipeline = {
            "model_decision": "block",
            "calibrated_prob": 1.0,
            "stacker_score": 1.0,
            "model_source": "backend_fallback_error",
            "base_outputs": {},
            "queue_outputs": {},
            "why_flagged": "Backend error during fraud evaluation; transaction treated as high risk.",
        }

        try:
            user = await db.users.find_one({"user_key": payload.user_key}) or {}
            txn_doc = {
                "user_key": payload.user_key,
                "device_hash": "",
                "timestamp": now,
                "frontend_payload": payload.frontend_payload.model_dump(),
                "backend_snapshot": {},
                "pipeline_results": fallback_pipeline,
            }
            insert_result = await db.transactions.insert_one(txn_doc)
            txn_id = str(insert_result.inserted_id)

            live_payload = _to_live_transaction(
                {
                    "_id": insert_result.inserted_id,
                    "user_key": payload.user_key,
                    "frontend_payload": payload.frontend_payload.model_dump(),
                    "timestamp": now,
                    "pipeline_results": fallback_pipeline,
                },
                user,
            )
            await transaction_stream.broadcast(
                {
                    "type": "transaction.created",
                    "transaction": live_payload,
                    "generated_at": now.isoformat(),
                }
            )
        except Exception as inner_exc:
            print(f"[process_transaction] fallback insert/broadcast failed for user {payload.user_key}: {inner_exc!r}")
            txn_id = "fallback"

        return {
            "transaction_id": txn_id,
            "user_key": payload.user_key,
            "device_hash": "",
            "decision": "block",
            "calibrated_prob": 1.0,
            "stacker_score": 1.0,
            "model_source": "backend_fallback_error",
            "why_flagged": "Backend error during fraud evaluation; transaction treated as high risk.",
            "timestamp": now,
        }


@router.get("/{transaction_id}")
async def get_transaction(transaction_id: str, db: AsyncIOMotorDatabase = Depends(get_db)):
    from bson import ObjectId

    try:
        obj_id = ObjectId(transaction_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid transaction_id") from exc

    txn = await db.transactions.find_one({"_id": obj_id})
    if not txn:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return serialize_id(txn)


@router.get("/user/{user_key}")
async def get_user_transactions(
    user_key: str,
    limit: int = Query(default=20, ge=1, le=200),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db.transactions.find({"user_key": user_key}).sort("timestamp", -1).limit(limit)
    items = [serialize_id(item) async for item in cursor]
    return {"transactions": items, "count": len(items)}
