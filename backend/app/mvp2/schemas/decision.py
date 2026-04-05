"""Decision schemas for MVP 2."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class DecisionResult(str, Enum):
    """Outcome of a governance decision evaluation."""

    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"


class DecisionRequest(BaseModel):
    """Payload for requesting a governance decision."""

    transaction_id: UUID
    actor_id: UUID
    action: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=16)
    metadata: dict | None = None


class DecisionResponse(BaseModel):
    """Result of a governance decision evaluation."""

    transaction_id: UUID
    result: DecisionResult
    reason_codes: list[str] = Field(default_factory=list)
    matched_policies: list[UUID] = Field(default_factory=list)
    metadata: dict | None = None
