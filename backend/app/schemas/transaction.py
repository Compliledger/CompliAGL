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
    vendor: Optional[str] = None
    chain: Optional[str] = None
    asset_symbol: Optional[str] = None


class TransactionResponse(BaseModel):
    id: str
    agent_id: str
    recipient: str
    amount: float
    currency: str
    description: Optional[str] = None
    vendor: Optional[str] = None
    chain: Optional[str] = None
    asset_symbol: Optional[str] = None
    status: str
    decision_result: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ProofBundleSummary(BaseModel):
    proof_bundle_id: str
    proof_hash: str
    decision: str
    created_at: Optional[str] = None


class EvaluationResponse(BaseModel):
    transaction_id: str
    decision_result: str
    reason_codes: list[str] = []
    decision_summary: str = ""
    risk_level: str = "LOW"
    requires_approval: bool = False
    proof_bundle_summary: Optional[ProofBundleSummary] = None
