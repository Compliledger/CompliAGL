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

    # Canonical deterministic-decision fields (optional for backward compat).
    evaluation_id: Optional[str] = None
    policy_resolution_id: Optional[str] = None
    assessment_id: Optional[str] = None
    decision_conditions_triggered: list[Any] = Field(default_factory=list)
    applicable_package_ids: list[Any] = Field(default_factory=list)
    applicable_requirement_ids: list[Any] = Field(default_factory=list)
    control_evaluation_ids: list[Any] = Field(default_factory=list)
    evidence_package_id: Optional[str] = None
    evidence_package_hash: Optional[str] = None
    assessment_hash: Optional[str] = None
    policy_package_hash: Optional[str] = None
    actor_hash: Optional[str] = None
    intent_hash: Optional[str] = None
    target_hash: Optional[str] = None
    context_hash: Optional[str] = None
    engine_version: Optional[str] = None
    input_hash: Optional[str] = None
    expires_at: Optional[datetime] = None
    prior_decision_id: Optional[str] = None
    superseded_by_decision_id: Optional[str] = None
    supersession_status: Optional[str] = None


class DecideFromResolutionRequest(BaseModel):
    """Run the deterministic decision engine for a resolved evaluation."""

    organization_id: str = Field(..., min_length=1)
    policy_resolution_id: str = Field(..., min_length=1)
    prior_decision_id: Optional[str] = None


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

    # Signed first-class authorization fields (optional for backward compat).
    actor_id: Optional[str] = None
    target_id: Optional[str] = None
    authorized_action: Optional[str] = None
    authorized_parameter_constraints: Optional[dict[str, Any]] = None
    max_amount_minor: Optional[int] = None
    max_amount_currency: Optional[str] = None
    permitted_execution_system: Optional[str] = None
    issued_at: Optional[datetime] = None
    nonce: Optional[str] = None
    idempotency_key: Optional[str] = None
    one_time_use: Optional[bool] = None
    consumed_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    revocation_reason: Optional[str] = None
    policy_package_hash: Optional[str] = None
    assessment_hash: Optional[str] = None
    evidence_package_hash: Optional[str] = None
    decision_hash: Optional[str] = None
    signer_key_id: Optional[str] = None
    signature: Optional[str] = None
    authorization_hash: Optional[str] = None


class ExecutionAuthorizationIssueRequest(BaseModel):
    """Issue a signed execution authorization for an APPROVED decision."""

    organization_id: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)
    permitted_execution_system: Optional[str] = None
    authorized_parameter_constraints: Optional[dict[str, Any]] = None
    max_amount_minor: Optional[int] = None
    max_amount_currency: Optional[str] = None
    expires_at: Optional[datetime] = None
    idempotency_key: Optional[str] = None
    one_time_use: bool = True


class ExecutionAuthorizationVerifyRequest(BaseModel):
    """Independently verify an authorization before accepting execution."""

    expected_fields: Optional[dict[str, Any]] = None
    activate: bool = True


class ExecutionAuthorizationVerifyResponse(BaseModel):
    """Result of verifying an authorization."""

    authorization_id: str
    valid: bool
    status: str
    reasons: list[str] = Field(default_factory=list)
    hash_valid: bool
    signature_valid: bool
    expired: bool
    mismatched_fields: list[str] = Field(default_factory=list)


class ExecutionAuthorizationRevokeRequest(BaseModel):
    """Revoke a live authorization."""

    reason: Optional[str] = None


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
