"""Execution schemas for CompliAGL MVP 2."""

from __future__ import annotations

from pydantic import BaseModel


class ExecuteRequest(BaseModel):
    """Request to execute an approved transaction via a chain adapter."""

    adapter: str = "mock"


class ExecuteResponse(BaseModel):
    """Response after executing a transaction on-chain."""

    transaction_id: str
    execution_status: str
    tx_hash: str | None = None
    chain: str | None = None
    outcome: str | None = None
