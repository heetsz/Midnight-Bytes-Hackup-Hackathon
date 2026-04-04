from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


DecisionType = Literal["approve", "mfa", "block"]


class KnownDeviceItem(BaseModel):
    device_hash: str
    first_seen_at: datetime
    last_seen_at: datetime
    device_match_ord: int = Field(ge=0, le=2)


class BehaviorEvent(BaseModel):
    type_idx: int
    log_amount: float
    step_norm: float
    timestamp: datetime


class UserCreateRequest(BaseModel):
    user_key: str
    name: str
    email: str
    phone_no: str
    created_at: datetime | None = None
    device_centroid: list[float] = Field(default_factory=list)


class UserResponse(BaseModel):
    _id: str
    user_key: str
    name: str
    email: str
    phone_no: str
    created_at: datetime
    user_txn_count: int
    device_centroid: list[float]
    known_devices: list[KnownDeviceItem]
    recent_behavior_seq: list[BehaviorEvent]
    transaction_ids: list[str]


class DeviceFingerprint(BaseModel):
    id_31_idx: int
    id_33_idx: int
    DeviceType_idx: int
    DeviceInfo_idx: int
    os_browser_idx: int
    screen_width: int
    screen_height: int
    hardware_concurrency: int


class DeviceRegisterRequest(BaseModel):
    fingerprint: DeviceFingerprint


class FrontendPayload(BaseModel):
    transaction_amt: float = Field(gt=0)
    client_ip: str


class TransactionProcessRequest(BaseModel):
    user_key: str
    frontend_payload: FrontendPayload
    fingerprint: DeviceFingerprint
    card1: int | None = None
    d1: float | None = None
    d2: float | None = None
    d3: float | None = None
    v_cols: list[float] = Field(default_factory=list)
    c_cols: list[float] = Field(default_factory=list)
    m_cols: list[int] = Field(default_factory=list)


class ProcessedTransactionResponse(BaseModel):
    transaction_id: str
    user_key: str
    device_hash: str
    decision: DecisionType
    calibrated_prob: float
    stacker_score: float
    timestamp: datetime


class PipelineResults(BaseModel):
    model_decision: DecisionType
    calibrated_prob: float
    stacker_score: float
    base_outputs: dict[str, float]
    queue_outputs: dict[str, float]


class TransactionResponse(BaseModel):
    _id: str
    user_key: str
    device_hash: str
    timestamp: datetime
    frontend_payload: dict[str, Any]
    backend_snapshot: dict[str, Any]
    pipeline_results: PipelineResults
