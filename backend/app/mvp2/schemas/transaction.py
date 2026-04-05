"""Transaction schemas for MVP 2."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionStatus(str, Enum):
    """Lifecycle status of a transaction."""

    SUBMITTED = "SUBMITTED"
    EVALUATED = "EVALUATED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class TransactionBase(BaseModel):
    """Shared fields for transaction representations."""

    actor_id: UUID
    action: str = Field(..., min_length=1, max_length=255)
    amount: float = Field(..., ge=0)
    currency: str = Field(default="USD", max_length=16)
    metadata: dict | None = None


class TransactionCreate(TransactionBase):
    """Payload for submitting a new transaction."""


class TransactionRead(TransactionBase):
    """Transaction representation returned by the API."""

    id: UUID
    status: TransactionStatus = TransactionStatus.SUBMITTED

    model_config = {"from_attributes": True}
