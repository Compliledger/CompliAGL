"""Execution schemas for MVP 2."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    """Status of a transaction execution."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"


class ExecutionRequest(BaseModel):
    """Payload for requesting execution of an *authorized* action.

    ``amount`` and ``currency`` are required and passed through to the external
    execution adapter — the service never substitutes zero amounts or a default
    currency.
    """

    transaction_id: UUID
    amount: float = Field(..., ge=0)
    currency: str = Field(..., min_length=1, max_length=16)
    adapter: str = Field(default="mock", max_length=64)
    metadata: dict | None = None


class ExecutionResponse(BaseModel):
    """Result of a transaction execution."""

    transaction_id: UUID
    status: ExecutionStatus
    tx_hash: str | None = None
    adapter: str
    error: str | None = None
    metadata: dict | None = None
