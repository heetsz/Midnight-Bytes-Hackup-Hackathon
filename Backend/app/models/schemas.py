from datetime import datetime

from pydantic import BaseModel, Field


class TransactionRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    amount: float = Field(..., gt=0)
    location: str = Field(..., min_length=1)
    device: str = Field(..., min_length=1)
    timestamp: datetime


class TransactionResult(BaseModel):
    risk_score: int
    decision: str
    reasons: list[str]


class StatsResponse(BaseModel):
    total_transactions: int
    fraud_count: int
    average_risk_score: float
