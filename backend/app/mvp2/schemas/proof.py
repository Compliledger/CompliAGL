"""Proof schemas for MVP 2."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class ProofStatus(str, Enum):
    """Status of a cryptographic proof record."""

    GENERATED = "GENERATED"
    ANCHORED = "ANCHORED"
    FAILED = "FAILED"


class ProofRequest(BaseModel):
    """Payload for requesting proof generation."""

    transaction_id: UUID
    decision_result: str
    reason_codes: list[str] = Field(default_factory=list)
    metadata: dict | None = None


class ProofResponse(BaseModel):
    """Generated proof bundle."""

    transaction_id: UUID
    proof_hash: str
    status: ProofStatus = ProofStatus.GENERATED
    payload: dict = Field(default_factory=dict)
    metadata: dict | None = None
