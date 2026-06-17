"""Compli402 schemas — public, competition-ready x402 governance API.

These models describe the request/response contracts for the Compli402
endpoints that combine CompliAGL governance with the x402 "HTTP 402
Payment Required" execution flow.  They are intentionally simple and
OpenAPI-friendly so the demo surface is easy to read in ``/docs``.
"""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class Compli402Status(str, Enum):
    """High-level outcome of a Compli402 intent."""

    DENIED = "DENIED"
    ESCALATION_REQUIRED = "ESCALATION_REQUIRED"
    PAYMENT_REQUIRED = "PAYMENT_REQUIRED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    EXECUTED = "EXECUTED"


class Compli402Intent(BaseModel):
    """An actor's intent to perform a governed, payment-gated action."""

    actor_id: UUID = Field(..., description="Identifier of the requesting actor.")
    action: str = Field(..., min_length=1, description="Action the actor wants to perform.")
    amount: float = Field(..., ge=0, description="Action amount used for policy evaluation.")
    currency: str = Field(default="USDC", max_length=16)
    transaction_id: UUID | None = Field(
        default=None,
        description="Optional client-supplied transaction id; generated when omitted.",
    )
    payment: dict | None = Field(
        default=None,
        description="Optional x402 payment payload (e.g. {'reference': '...'}).",
    )
    metadata: dict | None = None


class Compli402Decision(BaseModel):
    """Governance decision summary returned to the caller."""

    result: str
    reason_codes: list[str] = Field(default_factory=list)
    matched_policies: list[UUID] = Field(default_factory=list)


class Compli402VerifyResponse(BaseModel):
    """Result of evaluating an intent against governance policy."""

    transaction_id: UUID
    decision: Compli402Decision
    status: Compli402Status
    payment_required: bool = False
    message: str | None = None


class Compli402ExecuteResponse(BaseModel):
    """Full Compli402 execution result.

    Bundles the governance decision, x402 payment context, execution
    result, the generated AIProof, and the Algorand anchor receipt.
    """

    transaction_id: UUID
    decision: Compli402Decision
    status: Compli402Status
    payment: dict | None = None
    execution: dict | None = None
    proof: dict | None = None
    anchor: dict | None = None
    message: str | None = None
