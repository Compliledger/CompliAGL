"""Transaction Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.utils.enums import TransactionStatus


class TransactionCreate(BaseModel):
    """Payload for creating a new transaction."""

    agent_id: str
    vendor: str
    chain: str
    asset_symbol: str
    amount: float = Field(..., gt=0)
    destination: str
    memo: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)


class TransactionResponse(BaseModel):
    """Single transaction detail."""

    id: str
    agent_id: str
    wallet_address: str
    vendor: str
    chain: str
    asset_symbol: str
    amount: float
    destination: str
    memo: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    status: TransactionStatus
    decision_result: Optional[str] = None
    decision_reason_summary: Optional[str] = None
    submitted_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class TransactionListResponse(BaseModel):
    """Paginated list of transactions."""

    items: list[TransactionResponse]
    count: int


class TransactionEvaluationResponse(BaseModel):
    """Result of a transaction evaluation."""

    transaction_id: str
    decision_result: Optional[str] = None
    decision_reason_summary: Optional[str] = None
    evaluated_at: Optional[datetime] = None
