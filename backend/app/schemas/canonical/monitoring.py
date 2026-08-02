"""Continuous monitoring & automated re-evaluation request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase
from app.utils.canonical_enums import (
    DecisionOutcome,
    MonitoringChangeType,
    MonitoringSeverity,
)


# --------------------------------------------------------------------------- #
# Monitoring event
# --------------------------------------------------------------------------- #
class MonitoringEventSubmit(BaseModel):
    """Submit a detected change to the continuous monitor."""

    organization_id: str = Field(..., min_length=1)
    change_type: MonitoringChangeType
    source: str = Field(..., min_length=1)
    affected_object_type: str = Field(..., min_length=1)
    affected_object_id: str = Field(..., min_length=1)
    old_state_hash: Optional[str] = None
    new_state_hash: Optional[str] = None
    severity: Optional[MonitoringSeverity] = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[str] = None
    intent_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    detected_at: Optional[datetime] = None


class MonitoringEventResponse(CanonicalResponseBase):
    event_uid: str
    change_type: str
    source: str
    affected_object_type: str
    affected_object_id: str
    intent_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    old_state_hash: Optional[str] = None
    new_state_hash: Optional[str] = None
    detected_at: Optional[datetime] = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    severity: str
    correlation_id: Optional[str] = None
    event_hash: Optional[str] = None


# --------------------------------------------------------------------------- #
# Impact analysis
# --------------------------------------------------------------------------- #
class ImpactCounts(BaseModel):
    intents: int = 0
    evaluations: int = 0
    decisions: int = 0
    authorizations: int = 0
    findings: int = 0
    aiproofs: int = 0
    canonical_proof_packages: int = 0


class ImpactAnalysisResponse(BaseModel):
    monitoring_event_id: str
    change_type: str
    affected_object_type: str
    affected_object_id: str
    intent_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    intents: list[str] = Field(default_factory=list)
    evaluations: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    authorizations: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    aiproofs: list[str] = Field(default_factory=list)
    canonical_proof_packages: list[str] = Field(default_factory=list)
    counts: ImpactCounts = Field(default_factory=ImpactCounts)


# --------------------------------------------------------------------------- #
# Re-evaluation
# --------------------------------------------------------------------------- #
class ReevaluationTriggerRequest(BaseModel):
    """Trigger an automated re-evaluation for a monitoring event."""

    resulting_outcome: Optional[DecisionOutcome] = None
    reason: Optional[str] = None


class ReevaluationRunResponse(CanonicalResponseBase):
    monitoring_event_id: str
    change_type: Optional[str] = None
    correlation_id: Optional[str] = None
    status: str
    intent_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    impact: dict[str, Any] = Field(default_factory=dict)
    prior_decision_id: Optional[str] = None
    new_decision_id: Optional[str] = None
    new_assessment_id: Optional[str] = None
    prior_aiproof_id: Optional[str] = None
    new_aiproof_id: Optional[str] = None
    invalidated_authorization_ids: list[str] = Field(default_factory=list)
    resulting_outcome: Optional[str] = None
    reason_codes: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    completed_at: Optional[datetime] = None


# --------------------------------------------------------------------------- #
# Supersession chains
# --------------------------------------------------------------------------- #
class DecisionChainEntry(BaseModel):
    decision_id: str
    outcome: str
    supersession_status: Optional[str] = None
    prior_decision_id: Optional[str] = None
    superseded_by_decision_id: Optional[str] = None
    originating_finding_id: Optional[str] = None
    decision_hash: Optional[str] = None
    decided_at: Optional[datetime] = None
    reason_codes: list[str] = Field(default_factory=list)


class DecisionChainResponse(BaseModel):
    anchor_decision_id: str
    root_decision_id: str
    current_decision_id: str
    length: int
    chain: list[DecisionChainEntry] = Field(default_factory=list)


class ProofChainEntry(BaseModel):
    aiproof_id: str
    status: str
    governed_outcome: Optional[str] = None
    aiproof_hash: Optional[str] = None
    prior_aiproof_id: Optional[str] = None
    superseded_by_aiproof_id: Optional[str] = None
    decision_id: Optional[str] = None
    intent_id: Optional[str] = None
    created_at: Optional[datetime] = None


class ProofChainResponse(BaseModel):
    anchor_aiproof_id: str
    root_aiproof_id: str
    current_aiproof_id: str
    length: int
    chain: list[ProofChainEntry] = Field(default_factory=list)
