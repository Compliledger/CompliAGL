"""GovernanceEvaluation, Decision, ExecutionAuthorization, and
ExternalExecutionResult request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase
from app.utils.canonical_enums import (
    AuthorizationStatus,
    DecisionOutcome,
    EvaluationStatus,
    ExecutionResultStatus,
)


# --------------------------------------------------------------------------- #
# GovernanceEvaluation
# --------------------------------------------------------------------------- #
class GovernanceEvaluationCreate(BaseModel):
    """Payload creating the record that ties actor, intent, target, context."""

    organization_id: str = Field(..., min_length=1)
    actor_identity_id: str = Field(..., min_length=1)
    intent_id: str = Field(..., min_length=1)
    target_id: Optional[str] = None
    operational_context_id: Optional[str] = None


class GovernanceEvaluationResponse(CanonicalResponseBase):
    """Governance evaluation as returned by the API."""

    actor_identity_id: str
    intent_id: str
    target_id: Optional[str] = None
    operational_context_id: Optional[str] = None
    status: str
    outcome: Optional[str] = None
    reason_codes: list[Any] = Field(default_factory=list)
    evaluation_hash: Optional[str] = None


class GovernanceEvaluationResolve(BaseModel):
    """Resolve an evaluation with a deterministic outcome and reasons."""

    outcome: DecisionOutcome
    reason_codes: list[str] = Field(default_factory=list)
    status: EvaluationStatus = EvaluationStatus.EVALUATED


# --------------------------------------------------------------------------- #
# Decision
# --------------------------------------------------------------------------- #
class DecisionCreate(BaseModel):
    """Payload for recording a deterministic decision."""

    organization_id: str = Field(..., min_length=1)
    governance_evaluation_id: str = Field(..., min_length=1)
    intent_id: str = Field(..., min_length=1)
    outcome: DecisionOutcome
    reason_codes: list[str] = Field(default_factory=list)
    policy_version: Optional[str] = None


class DecisionResponse(CanonicalResponseBase):
    """Decision as returned by the API."""

    governance_evaluation_id: str
    intent_id: str
    outcome: str
    reason_codes: list[Any] = Field(default_factory=list)
    policy_version: Optional[str] = None
    decision_hash: Optional[str] = None
    decided_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# ExecutionAuthorization
# --------------------------------------------------------------------------- #
class ExecutionAuthorizationCreate(BaseModel):
    """Payload for issuing an execution authorization."""

    organization_id: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    intent_id: str = Field(..., min_length=1)
    constraints: Optional[dict[str, Any]] = None
    expires_at: Optional[datetime] = None


class ExecutionAuthorizationResponse(CanonicalResponseBase):
    """Execution authorization as returned by the API."""

    decision_id: str
    intent_id: str
    status: str
    authorization_token: Optional[str] = None
    constraints: Optional[dict[str, Any]] = None
    authorized_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class ExecutionAuthorizationStatusUpdate(BaseModel):
    """Explicit lifecycle transition request for an authorization."""

    status: AuthorizationStatus


# --------------------------------------------------------------------------- #
# ExternalExecutionResult
# --------------------------------------------------------------------------- #
class ExternalExecutionResultCreate(BaseModel):
    """Payload for recording the outcome of an external execution."""

    organization_id: str = Field(..., min_length=1)
    execution_authorization_id: str = Field(..., min_length=1)
    intent_id: str = Field(..., min_length=1)
    adapter: Optional[str] = None
    status: ExecutionResultStatus = ExecutionResultStatus.PENDING
    external_reference: Optional[str] = None
    settlement_chain: Optional[str] = None
    result_payload: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class ExternalExecutionResultResponse(CanonicalResponseBase):
    """External execution result as returned by the API."""

    execution_authorization_id: str
    intent_id: str
    adapter: Optional[str] = None
    status: str
    external_reference: Optional[str] = None
    settlement_chain: Optional[str] = None
    result_payload: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    executed_at: Optional[datetime] = None
