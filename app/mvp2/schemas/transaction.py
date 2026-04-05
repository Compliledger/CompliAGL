"""Transaction schemas for CompliAGL MVP 2."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TransactionRequest(BaseModel):
    """Incoming transaction to be evaluated by the governance layer."""

    transaction_id: str
    actor_id: str
    vendor: str
    chain: str
    asset_symbol: str
    amount: float
    destination: str
    metadata: dict = Field(default_factory=dict)


class ExecutionResult(BaseModel):
    """Result returned after a transaction has been executed on-chain."""

    execution_status: str
    tx_hash: str | None = None
    chain: str | None = None
    outcome: str | None = None
