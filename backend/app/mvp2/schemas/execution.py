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


class ExecutionRequest(BaseModel):
    """Payload for requesting transaction execution."""

    transaction_id: UUID
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
