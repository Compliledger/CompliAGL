"""Request/response schemas for the evidence layer.

These define the wire contract for the evidence collection, validation,
normalization and packaging stages that run after Evidence Requirement
Resolution. Nested structures (tasks, checks, claims, mappings) are returned as
plain dicts already parsed from JSON text.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase


# --------------------------------------------------------------------------- #
# Requests
# --------------------------------------------------------------------------- #
class StartEvidenceCollection(BaseModel):
    """Start evidence collection for a completed policy resolution.

    ``production_mode`` gates mock connectors: when ``True`` (or when omitted and
    the operational context environment is ``PRODUCTION``) mock connectors are
    rejected and never used silently.
    """

    organization_id: str = Field(..., min_length=1)
    policy_resolution_id: str = Field(..., min_length=1)
    production_mode: Optional[bool] = None


# --------------------------------------------------------------------------- #
# Responses
# --------------------------------------------------------------------------- #
class EvidenceSourceResponse(CanonicalResponseBase):
    connector_id: str
    source_type: str
    supported_evidence_types: list[Any] = Field(default_factory=list)
    auth_config_reference: Optional[str] = None
    is_mock: bool
    trusted_issuers: list[Any] = Field(default_factory=list)
    timeout_seconds: Optional[str] = None
    retry_policy: Optional[dict[str, Any]] = None
    status: str


class EvidenceOrchestrationPlanResponse(CanonicalResponseBase):
    policy_resolution_id: str
    evidence_requirement_set_id: str
    actor_identity_id: Optional[str] = None
    intent_id: Optional[str] = None
    target_id: Optional[str] = None
    operational_context_id: Optional[str] = None
    production_mode: str
    tasks: list[Any] = Field(default_factory=list)
    unresolved: list[Any] = Field(default_factory=list)
    reason_codes: list[Any] = Field(default_factory=list)
    engine_version: str
    plan_hash: Optional[str] = None
    planned_at: Optional[datetime] = None


class EvidenceCollectionJobResponse(CanonicalResponseBase):
    policy_resolution_id: str
    evidence_requirement_set_id: str
    orchestration_plan_id: str
    production_mode: bool
    status: str
    raw_evidence_ids: list[Any] = Field(default_factory=list)
    failures: list[Any] = Field(default_factory=list)
    unresolved: list[Any] = Field(default_factory=list)
    reason_codes: list[Any] = Field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class RawEvidenceResponse(CanonicalResponseBase):
    collection_job_id: str
    evidence_requirement_id: str
    policy_resolution_id: Optional[str] = None
    source_id: str
    source_type: str
    subject_id: Optional[str] = None
    target_id: Optional[str] = None
    intent_id: Optional[str] = None
    collected_at: Optional[datetime] = None
    issued_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    payload: Optional[Any] = None
    payload_reference: Optional[str] = None
    payload_hash: Optional[str] = None
    claims: Optional[dict[str, Any]] = None
    sensitivity: str
    issuer: Optional[str] = None
    provenance: dict[str, Any] = Field(default_factory=dict)
    collection_status: str
    error: Optional[str] = None


class EvidenceValidationResultResponse(CanonicalResponseBase):
    raw_evidence_id: str
    evidence_requirement_id: str
    collection_job_id: Optional[str] = None
    policy_resolution_id: Optional[str] = None
    outcome: str
    checks: dict[str, Any] = Field(default_factory=dict)
    reason_codes: list[Any] = Field(default_factory=list)
    result_hash: Optional[str] = None


class NormalizedEvidenceResponse(CanonicalResponseBase):
    raw_evidence_id: str
    validation_result_id: str
    evidence_requirement_id: str
    collection_job_id: Optional[str] = None
    policy_resolution_id: Optional[str] = None
    evidence_type: Optional[str] = None
    subject: Optional[str] = None
    target: Optional[str] = None
    source: Optional[str] = None
    issuer: Optional[str] = None
    normalized_claims: dict[str, Any] = Field(default_factory=dict)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    validation_status: str
    source_payload_hash: Optional[str] = None
    normalized_payload_hash: Optional[str] = None
    provenance_reference: Optional[str] = None


class CanonicalEvidencePackageResponse(CanonicalResponseBase):
    evaluation_id: str
    policy_resolution_id: Optional[str] = None
    evidence_requirement_set_id: Optional[str] = None
    collection_job_id: Optional[str] = None
    normalized_evidence_references: list[Any] = Field(default_factory=list)
    requirement_mappings: list[Any] = Field(default_factory=list)
    control_mappings: list[Any] = Field(default_factory=list)
    missing_evidence: list[Any] = Field(default_factory=list)
    invalid_evidence: list[Any] = Field(default_factory=list)
    reason_codes: list[Any] = Field(default_factory=list)
    package_hash: Optional[str] = None
