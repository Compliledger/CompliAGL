"""Decision schemas for CompliAGL MVP 2."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class DecisionStatus(str, Enum):
    """Outcome status of a governance decision."""

    APPROVE = "APPROVE"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class DecisionResult(BaseModel):
    """Result of evaluating a transaction against governance policies."""

    decision: DecisionStatus
    reason_codes: list[str] = Field(default_factory=list)
    policy_id: str
    policy_version: str
    timestamp: str
