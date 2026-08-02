"""Finding & remediation branch request/response schemas.

Covers the finding-and-remediation branch resources: :class:`Finding`,
:class:`RemediationPlan`, :class:`ResolutionEvidence`, the DevSync integration
payloads, review records, resolution validation and re-assessment.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase
from app.utils.canonical_enums import (
    DevSyncCallbackStatus,
    FindingStatus,
    RemediationPlanStatus,
    RemediationPriority,
    ReviewOutcome,
    ReviewType,
)


# --------------------------------------------------------------------------- #
# Finding
# --------------------------------------------------------------------------- #
class FindingGenerateRequest(BaseModel):
    """Generate findings for a decision per governance rules."""

    organization_id: str = Field(..., min_length=1)
    decision_id: str = Field(..., min_length=1)


class FindingAssignRequest(BaseModel):
    """Assign a finding to an owner and (optionally) set a due date."""

    owner: str = Field(..., min_length=1)
    due_date: Optional[datetime] = None


class FindingResponse(CanonicalResponseBase):
    finding_id: str
    evaluation_id: Optional[str] = None
    assessment_id: Optional[str] = None
    decision_id: Optional[str] = None
    intent_id: Optional[str] = None
    actor_id: Optional[str] = None
    target_id: Optional[str] = None
    requirement_ids: list[Any] = Field(default_factory=list)
    control_ids: list[Any] = Field(default_factory=list)
    evidence_gap_ids: list[Any] = Field(default_factory=list)
    title: str
    description: Optional[str] = None
    severity: str
    finding_type: str
    decision_impact: Optional[str] = None
    remediation_eligibility: str
    terminal: bool
    status: str
    owner: Optional[str] = None
    due_date: Optional[datetime] = None
    resolution_validation_outcome: Optional[str] = None
    resolved_by_decision_id: Optional[str] = None
    reason_codes: list[Any] = Field(default_factory=list)
    finding_hash: Optional[str] = None


# --------------------------------------------------------------------------- #
# RemediationPlan
# --------------------------------------------------------------------------- #
class RemediationActionModel(BaseModel):
    action_id: Optional[str] = None
    description: str
    owner: Optional[str] = None


class RequiredResolutionEvidenceModel(BaseModel):
    evidence_type: str = Field(..., min_length=1)
    mandatory: bool = True
    allowed_issuers: list[str] = Field(default_factory=list)
    freshness_threshold: Optional[str] = None
    expected_subject_id: Optional[str] = None
    expected_target_id: Optional[str] = None
    expected_intent_id: Optional[str] = None


class RemediationPlanCreate(BaseModel):
    organization_id: str = Field(..., min_length=1)
    finding_id: str = Field(..., min_length=1)
    required_corrective_state: Optional[str] = None
    remediation_actions: list[RemediationActionModel] = Field(default_factory=list)
    required_resolution_evidence: list[RequiredResolutionEvidenceModel] = Field(
        default_factory=list
    )
    owner: Optional[str] = None
    priority: RemediationPriority = RemediationPriority.MEDIUM
    due_date: Optional[datetime] = None
    dependencies: list[Any] = Field(default_factory=list)


class RemediationPlanStatusUpdate(BaseModel):
    status: RemediationPlanStatus


class RemediationPlanResponse(CanonicalResponseBase):
    remediation_plan_id: str
    finding_id: str
    required_corrective_state: Optional[str] = None
    remediation_actions: list[Any] = Field(default_factory=list)
    required_resolution_evidence: list[Any] = Field(default_factory=list)
    owner: Optional[str] = None
    priority: str
    due_date: Optional[datetime] = None
    dependencies: list[Any] = Field(default_factory=list)
    status: str
    plan_hash: Optional[str] = None


# --------------------------------------------------------------------------- #
# ResolutionEvidence
# --------------------------------------------------------------------------- #
class ResolutionEvidenceSubmit(BaseModel):
    organization_id: str = Field(..., min_length=1)
    finding_id: str = Field(..., min_length=1)
    evidence_type: str = Field(..., min_length=1)
    remediation_plan_id: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    subject_id: Optional[str] = None
    target_id: Optional[str] = None
    intent_id: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    issuer: Optional[str] = None
    signature: Optional[str] = None
    claims: Optional[dict[str, Any]] = None
    payload: Optional[dict[str, Any]] = None
    provenance: Optional[dict[str, Any]] = None
    submitted_via: Optional[str] = None


class ResolutionEvidenceResponse(CanonicalResponseBase):
    finding_id: str
    remediation_plan_id: Optional[str] = None
    evidence_type: str
    issuer: Optional[str] = None
    subject_id: Optional[str] = None
    target_id: Optional[str] = None
    intent_id: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    collection_status: str
    validation_outcome: Optional[str] = None
    validation_checks: dict[str, Any] = Field(default_factory=dict)
    normalized_claims: Optional[dict[str, Any]] = None
    reason_codes: list[Any] = Field(default_factory=list)
    submitted_via: Optional[str] = None
    result_hash: Optional[str] = None
    validated_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# DevSync
# --------------------------------------------------------------------------- #
class DevSyncDispatchRequest(BaseModel):
    organization_id: str = Field(..., min_length=1)
    finding_id: str = Field(..., min_length=1)
    remediation_plan_id: Optional[str] = None
    adapter: Optional[str] = None


class DevSyncCallbackEvidence(BaseModel):
    evidence_type: str = Field(..., min_length=1)
    issuer: Optional[str] = None
    subject_id: Optional[str] = None
    target_id: Optional[str] = None
    intent_id: Optional[str] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    signature: Optional[str] = None
    claims: Optional[dict[str, Any]] = None
    payload: Optional[dict[str, Any]] = None
    provenance: Optional[dict[str, Any]] = None


class DevSyncCallbackRequest(BaseModel):
    organization_id: str = Field(..., min_length=1)
    callback_reference: str = Field(..., min_length=1)
    status: DevSyncCallbackStatus
    note: Optional[str] = None
    external_reference: Optional[str] = None
    evidence: list[DevSyncCallbackEvidence] = Field(default_factory=list)


class DevSyncDispatchResponse(CanonicalResponseBase):
    finding_id: str
    remediation_plan_id: Optional[str] = None
    adapter: str
    external_reference: Optional[str] = None
    callback_reference: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str
    last_callback_status: Optional[str] = None
    callbacks: list[Any] = Field(default_factory=list)
    dispatched_at: Optional[datetime] = None
    last_callback_at: Optional[datetime] = None
    payload_hash: Optional[str] = None


# --------------------------------------------------------------------------- #
# Review
# --------------------------------------------------------------------------- #
class ReviewRecordCreate(BaseModel):
    organization_id: str = Field(..., min_length=1)
    finding_id: str = Field(..., min_length=1)
    reviewer_id: str = Field(..., min_length=1)
    reviewer_role: Optional[str] = None
    review_type: ReviewType = ReviewType.MANUAL_REVIEW
    outcome: ReviewOutcome
    rationale: Optional[str] = None


class ReviewRecordResponse(CanonicalResponseBase):
    finding_id: Optional[str] = None
    decision_id: Optional[str] = None
    intent_id: Optional[str] = None
    review_type: str
    reviewer_id: str
    reviewer_role: Optional[str] = None
    outcome: str
    rationale: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_hash: Optional[str] = None


# --------------------------------------------------------------------------- #
# Resolution validation + re-assessment
# --------------------------------------------------------------------------- #
class ResolutionValidationResponse(BaseModel):
    finding_id: str
    outcome: str
    sufficiency: str
    reason_codes: list[str] = Field(default_factory=list)
    evidence_results: list[dict[str, Any]] = Field(default_factory=list)
    finding_status: str


class ReassessmentResponse(BaseModel):
    finding_id: str
    reassessed: bool
    reason_codes: list[str] = Field(default_factory=list)
    prior_decision_id: Optional[str] = None
    new_decision_id: Optional[str] = None
    new_assessment_id: Optional[str] = None
    decision_outcome: Optional[str] = None
    finding_status: str


class DecisionHistoryEntry(BaseModel):
    decision_id: str
    outcome: str
    supersession_status: str
    prior_decision_id: Optional[str] = None
    superseded_by_decision_id: Optional[str] = None
    originating_finding_id: Optional[str] = None
    decision_hash: Optional[str] = None
    decided_at: Optional[datetime] = None
    reason_codes: list[Any] = Field(default_factory=list)


class DecisionHistoryResponse(BaseModel):
    intent_id: str
    decisions: list[DecisionHistoryEntry] = Field(default_factory=list)
    findings: list[FindingResponse] = Field(default_factory=list)
