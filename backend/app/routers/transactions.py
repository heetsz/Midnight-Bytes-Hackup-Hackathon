import hashlib
import json
import math
import re

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db import get_db
from app.services.model_row_provider import generate_model_row_context
from app.services.model_inference import run_inference
from app.services.transaction_stream import transaction_stream
from app.schemas import TransactionProcessRequest
from app.utils.mongo import serialize_id, utc_now

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


def _hash_fingerprint(payload: TransactionProcessRequest) -> str:
    fp = payload.fingerprint.model_dump() if payload.fingerprint is not None else {
        "id_31_idx": 0,
        "id_33_idx": 0,
        "DeviceType_idx": 0,
        "DeviceInfo_idx": 0,
        "os_browser_idx": 0,
        "screen_width": 0,
        "screen_height": 0,
        "hardware_concurrency": 0,
    }
    raw = json.dumps(fp, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _derive_user_key(name: str, email: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", (name or "user").strip().lower()).strip("-")
    if not stem:
        stem = "user"
    return f"{stem}-{hashlib.sha1(email.encode('utf-8')).hexdigest()[:8]}"


def _ui_decision(decision: str) -> str:
    if decision == "block":
        return "BLOCK"
    if decision == "mfa":
        return "REVIEW"
    return "APPROVE"


def _to_live_transaction(item: dict, user: dict) -> dict:
    user_key = item.get("user_key") or ""
    frontend_payload = item.get("frontend_payload", {})
    decision = item.get("pipeline_results", {}).get("model_decision", "approve")
    fraud_score = int(item.get("pipeline_results", {}).get("calibrated_prob", 0) * 100)
    why_flagged = item.get("pipeline_results", {}).get("why_flagged")

    return {
        "txn_id": str(item.get("_id")),
        "user_id": user_key,
        "username": user.get("name", user_key),
        "email": user.get("email", ""),
        "amount": float(frontend_payload.get("transaction_amt", 0)),
        "fraud_score": fraud_score,
        "decision": _ui_decision(decision),
        "merchant_name": frontend_payload.get("merchant_name") or "",
        "timestamp": item.get("timestamp"),
        "location": frontend_payload.get("location") or user.get("city") or "",
        "why_flagged": why_flagged,
        "model_source": item.get("pipeline_results", {}).get("model_source"),
        "stacker_score": item.get("pipeline_results", {}).get("stacker_score"),
        "calibrated_prob": item.get("pipeline_results", {}).get("calibrated_prob"),
        "raw_fraud_score": item.get("pipeline_results", {}).get("raw_fraud_score"),
        "base_outputs": item.get("pipeline_results", {}).get("base_outputs", {}),
        "queue_outputs": item.get("pipeline_results", {}).get("queue_outputs", {}),
        "backend_snapshot": item.get("backend_snapshot", {}),
        "source_transaction_id": item.get("pipeline_results", {}).get("source_transaction_id", ""),
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
        user_key = item.get("user_key") or ""
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
        model_row = generate_model_row_context()

        user_key = payload.user_key
        if not user_key and payload.email:
            user_key = _derive_user_key(payload.name or "user", payload.email)

        if not user_key:
            raise HTTPException(status_code=400, detail="Provide user_key or email")

        # Trip 1: hash + lookup/insert device
        device_hash = _hash_fingerprint(payload)
        device = await db.devices.find_one({"device_hash": device_hash})
        if not device:
            await db.devices.insert_one(
                {
                    "device_hash": device_hash,
                    "created_at": now,
                    "fingerprint": payload.fingerprint.model_dump() if payload.fingerprint else {},
                }
            )

        # Trip 2: user enrichment with embedded fields
        user = await db.users.find_one({"user_key": user_key})
        if not user and payload.email:
            user = await db.users.find_one({"email": payload.email})
        if not user and payload.name and payload.email:
            user_doc = {
                "user_key": user_key,
                "name": payload.name,
                "email": payload.email,
                "phone_no": "",
                "city": "",
                "created_at": now,
                "usual_login_hour": 10,
                "user_txn_count": 0,
                "device_centroid": [],
                "known_devices": [],
                "recent_behavior_seq": [],
                "transaction_ids": [],
            }
            await db.users.insert_one(user_doc)
            user = user_doc
        if not user:
            # Keep mobile ingestion resilient: create a minimal user profile from user_key.
            user_doc = {
                "user_key": user_key,
                "name": payload.name or user_key,
                "email": payload.email or f"{user_key}@mobile.local",
                "phone_no": "",
                "city": "",
                "created_at": now,
                "usual_login_hour": 10,
                "user_txn_count": 0,
                "device_centroid": [],
                "known_devices": [],
                "recent_behavior_seq": [],
                "transaction_ids": [],
            }
            await db.users.insert_one(user_doc)
            user = user_doc

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
            {"user_key": user_key},
            sort=[("timestamp", -1)],
        )

        user_txn_count = int(user.get("user_txn_count", 0))
        txn_rank = user_txn_count + 1

        if last_txn:
            delta_t = max(0.0, (now - last_txn["timestamp"]).total_seconds())
        else:
            delta_t = 0.0

        delta_t_norm = min(1.0, delta_t / 86400.0)

        amount = float(model_row.transaction_amt)
        base_avg = float(last_txn.get("frontend_payload", {}).get("transaction_amt", amount)) if last_txn else amount
        denom = max(1.0, base_avg)
        amt_zscore = abs((amount - base_avg) / denom)

        m_fail_count = sum(1 for item in user.get("recent_behavior_seq", []) if item.get("type_idx") == 3)
        m_all_fail = 1 if m_fail_count > 0 else 0

        novelty = 1.0 if known_index is None else 0.0
        device_dist_score = min(1.0, novelty + 0.05 * max(0, min(4, m_fail_count)))

        effective_location = model_row.location or user.get("city") or ""

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
            card1=model_row.card1,
            d1=model_row.d1,
            d2=model_row.d2,
            d3=model_row.d3,
            v_cols=model_row.v_cols,
            c_cols=model_row.c_cols,
            m_cols=model_row.m_cols,
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
            "card1": model_row.card1,
            "D1": model_row.d1,
            "D2": model_row.d2,
            "D3": model_row.d3,
            "v_cols": model_row.v_cols,
            "c_cols": model_row.c_cols,
            "m_cols": model_row.m_cols,
            "source_transaction_id": model_row.source_transaction_id,
        }

        frontend_payload = {
            "transaction_amt": amount,
            "client_ip": payload.frontend_payload.client_ip or "0.0.0.0",
            "merchant_name": model_row.merchant_name,
            "location": model_row.location,
        }

        pipeline_results = {
            "model_decision": model_decision,
            "calibrated_prob": calibrated_prob,
            "stacker_score": stacker_score,
            "raw_fraud_score": model_row.raw_fraud_score,
            "model_source": inference.model_source,
            "base_outputs": inference.base_outputs,
            "queue_outputs": inference.queue_outputs,
            "why_flagged": inference.why_flagged,
            "source_transaction_id": model_row.source_transaction_id,
            "pipeline_decision": model_row.decision,
            "pipeline_calibrated_prob": model_row.calibrated_prob,
        }

        txn_doc = {
            "user_key": user_key,
            "device_hash": device_hash,
            "timestamp": now,
            "frontend_payload": frontend_payload,
            "backend_snapshot": backend_snapshot,
            "pipeline_results": pipeline_results,
            "user_identity": {
                "name": user.get("name", payload.name or ""),
                "email": user.get("email", payload.email or ""),
            },
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
            {"user_key": user_key},
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
                "user_key": user_key,
                "frontend_payload": frontend_payload,
                "timestamp": now,
                "pipeline_results": pipeline_results,
                "backend_snapshot": backend_snapshot,
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
            "user_key": user_key,
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
    except Exception as exc:  # pragma: no cover - preserve explicit backend failure
        print(f"[process_transaction] unexpected error for user {payload.user_key}: {exc!r}")
        raise HTTPException(status_code=500, detail="Transaction processing failed") from exc


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
