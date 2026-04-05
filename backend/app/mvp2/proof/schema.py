"""Proof payload schema — canonical structure hashed for audit proofs."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class ProofPayload(BaseModel):
    """Internal representation of the data that gets hashed into a proof."""

    transaction_id: UUID
    decision_result: str
    reason_codes: list[str] = Field(default_factory=list)
    timestamp: str | None = None
    metadata: dict | None = None
