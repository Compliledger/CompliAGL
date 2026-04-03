"""Transaction Pydantic schemas."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class TransactionCreate(BaseModel):
    agent_id: str
    recipient: str
    amount: float
    currency: str = "USD"
    description: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    agent_id: str
    recipient: str
    amount: float
    currency: str
    description: Optional[str] = None
    status: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OWSExecutionData(BaseModel):
    """Mocked Open Wallet Standard execution data."""
    prepare: Optional[dict[str, Any]] = None
    sign: Optional[dict[str, Any]] = None
    wallet_metadata: Optional[dict[str, Any]] = None


class EvaluationResponse(BaseModel):
    transaction_id: str
    decision: str
    results: list[dict[str, Any]]
    proof_bundle_id: Optional[str] = None
    ows_execution: Optional[OWSExecutionData] = None
