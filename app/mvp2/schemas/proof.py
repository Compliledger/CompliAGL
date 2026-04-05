"""Proof schemas for CompliAGL MVP 2."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProofBundle(BaseModel):
    """Immutable proof record for a governed transaction."""

    proof_id: str
    actor_id: str
    transaction_id: str
    decision: str
    reason_codes: list[str] = Field(default_factory=list)
    policy_id: str
    policy_version: str
    execution_tx_hash: str | None = None
    execution_chain: str | None = None
    execution_status: str | None = None
    timestamp: str
    hash: str
