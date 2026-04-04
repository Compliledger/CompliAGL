"""Transaction Pydantic schemas."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator

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
    vendor: Optional[str] = None
    chain: Optional[str] = None
    asset_symbol: Optional[str] = None
    amount: float
    destination: Optional[str] = None
    memo: Optional[str] = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    status: str
    decision_result: Optional[str] = None
    decision_reason_summary: Optional[str] = None
    submitted_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def _parse_metadata_json(cls, data: Any) -> Any:
        """Deserialise metadata_json when it arrives as a JSON string."""
        if hasattr(data, "__dict__"):
            raw = getattr(data, "metadata_json", None)
        else:
            raw = data.get("metadata_json") if isinstance(data, dict) else None
        if isinstance(raw, str):
            try:
                parsed = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                parsed = {}
            if hasattr(data, "__dict__"):
                object.__setattr__(data, "metadata_json", parsed)
            else:
                data["metadata_json"] = parsed
        return data


class EvaluationResponse(BaseModel):
    """Result returned by the evaluation endpoint."""

    transaction_id: str
    decision_result: str
    reason_codes: list[str] = []
    decision_summary: str = ""
    risk_level: str = "LOW"
    requires_approval: bool = False
    proof_bundle_summary: Optional[dict[str, Any]] = None


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
