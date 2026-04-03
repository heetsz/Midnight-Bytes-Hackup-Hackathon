from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TransactionAnalyzeRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    merchant_name: str
    merchant_category: str
    payment_method: str
    device_fingerprint: str
    ip_address: str
    city: str


class TransactionAnalyzeResponse(BaseModel):
    txn_id: str
    fraud_score: int
    risk_level: str
    decision: str
    explanation: list[str]


class LoginAttemptRequest(BaseModel):
    user_id: str
    device_fingerprint: str
    ip_address: str
    success: bool
    failure_reason: str | None = None


class LoginAttemptResponse(BaseModel):
    risk_flag: bool
    attempts_count: int
    threat_type: str


class FeedbackRequest(BaseModel):
    is_confirmed_fraud: bool
    analyst_notes: str | None = None


class UserProfileResponse(BaseModel):
    user: dict[str, Any]
    recent_transactions: list[dict[str, Any]]
    weekly_stats: list[dict[str, Any]]
    open_alerts: list[dict[str, Any]]
    login_history: list[dict[str, Any]]


class DashboardStatsResponse(BaseModel):
    total_transactions_today: int
    fraud_blocked_today: dict[str, Any]
    fraud_by_type: list[dict[str, Any]]
    top_high_risk_users: list[dict[str, Any]]
    alerts_pending_resolution: int
    generated_at: datetime


class LiveTransactionItem(BaseModel):
    txn_id: str
    user_id: str
    username: str
    amount: float
    fraud_score: int
    merchant_name: str
    timestamp: datetime
    location: str


class LiveTransactionsResponse(BaseModel):
    transactions: list[LiveTransactionItem]
    generated_at: datetime


class UserSummaryItem(BaseModel):
    user_id: str
    name: str
    city: str
    member_since: datetime
    risk_label: str
    avg_txn_per_day: float
    trusted_devices: int
    usual_login_hour: int


class UserSearchResponse(BaseModel):
    users: list[UserSummaryItem]
    generated_at: datetime


class FraudRingNode(BaseModel):
    id: str
    label: str
    node_type: str
    risk_score: int


class FraudRingLink(BaseModel):
    source: str
    target: str
    relation: str
    confidence: float


class FraudRingGraphResponse(BaseModel):
    nodes: list[FraudRingNode]
    links: list[FraudRingLink]
    generated_at: datetime
