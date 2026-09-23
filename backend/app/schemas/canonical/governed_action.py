"""Request/response schemas for ``POST /api/v1/governed-actions``.

Thin wrapper contract over ``governed_action_service.propose`` for the Circle
treasury use case: a Treasury Agent proposing a USDC transfer. No business
logic lives in these schemas or the route that uses them.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class GovernedActionProposeRequest(BaseModel):
    """Propose a governed action for a treasury transfer."""

    actor_id: str = Field(..., min_length=1)
    action: str = Field(default="USDC_TRANSFER", min_length=1)
    amount_minor: int = Field(..., gt=0)
    amount_currency: str = Field(default="USDC", min_length=1)
    asset: str = Field(default="USDC", min_length=1)
    network: str = Field(default="ARC", min_length=1)
    target_identifier: str = Field(..., min_length=1)
    rationale: Optional[str] = None
    correlation_id: Optional[str] = None


class GovernedActionResponse(BaseModel):
    """Every artifact id/outcome produced by one ``propose`` run."""

    intent_id: str
    policy_resolution_id: str
    assessment_id: Optional[str] = None
    decision_id: str
    outcome: str
    reason_codes: list[Any] = Field(default_factory=list)
    decision_conditions_triggered: list[Any] = Field(default_factory=list)
    decision_hash: Optional[str] = None
    assessment_hash: Optional[str] = None
    evidence_package_hash: Optional[str] = None
    policy_package_hash: Optional[str] = None
