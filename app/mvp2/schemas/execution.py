"""Execution schemas for CompliAGL MVP 2."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.mvp2.schemas.decision import DecisionResult
from app.mvp2.schemas.proof import ProofBundle
from app.mvp2.schemas.transaction import ExecutionResult, TransactionRequest


class ExecuteRequest(BaseModel):
    """Request to execute a governed transaction end-to-end."""

    transaction: TransactionRequest
    adapter: Literal["mock", "solana"] = "mock"


class ExecuteResponse(BaseModel):
    """Combined response containing decision, execution, and proof."""

    decision: DecisionResult
    execution: ExecutionResult | None = None
    proof: ProofBundle
