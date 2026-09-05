"""ExecutableGovernancePackage request/response schemas.

These schemas define the formal integration contract through which CompliLedger
publishes machine-readable, executable governance to CompliAGL. The nested
definitions (requirement / control / evidence-requirement / decision-condition)
are the executable structures that replace human-language interpretation at
runtime.

Monetary values in expressions and metadata must use integer minor units — never
floating-point — consistent with the rest of the canonical domain.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.canonical.base import CanonicalResponseBase
from app.utils.canonical_enums import (
    ControlFailureDisposition,
    DecisionOutcome,
    GovernanceSeverity,
    RequirementClassification,
)


# --------------------------------------------------------------------------- #
# Nested executable structures
# --------------------------------------------------------------------------- #
class RequirementDefinition(BaseModel):
    """A single normalized requirement derived from a source document.

    Every requirement must carry a ``source_reference`` so it remains traceable
    back to the human-readable policy, regulation, standard, or contract it was
    derived from.
    """

    requirement_id: str = Field(..., min_length=1)
    source_reference: str = Field(..., min_length=1)
    normalized_text: str = Field(..., min_length=1)
    requirement_type: str = Field(..., min_length=1)
    classification: RequirementClassification
    applicability_expression: Optional[str] = None
    # Structured deterministic applicability criteria consumed by the
    # Applicability Evaluation stage. ``applicability_criteria`` decides
    # APPLICABLE vs NOT_APPLICABLE (INDETERMINATE when facts are missing);
    # ``condition_criteria`` is evaluated only when applicable and yields
    # CONDITIONAL when its condition is unmet.
    applicability_criteria: Optional[dict[str, Any]] = None
    condition_criteria: Optional[dict[str, Any]] = None
    version: Optional[str] = None
    mapped_control_ids: list[str] = Field(default_factory=list)
    severity: GovernanceSeverity = GovernanceSeverity.MEDIUM
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class ControlDefinition(BaseModel):
    """A deterministic control that evaluates one or more requirements."""

    control_id: str = Field(..., min_length=1)
    requirement_ids: list[str] = Field(..., min_length=1)
    control_objective: str = Field(..., min_length=1)
    evaluation_expression: str = Field(..., min_length=1)
    expected_outcome: Optional[Any] = None
    mandatory: bool = True
    severity: GovernanceSeverity = GovernanceSeverity.MEDIUM
    failure_disposition: ControlFailureDisposition = ControlFailureDisposition.DENY
    remediation_eligible: bool = False
    evidence_requirement_ids: list[str] = Field(default_factory=list)
    decision_impact: dict[str, Any] = Field(default_factory=dict)


class EvidenceRequirementDefinition(BaseModel):
    """Evidence that must be present/validated for a control to pass."""

    evidence_requirement_id: str = Field(..., min_length=1)
    control_ids: list[str] = Field(..., min_length=1)
    evidence_type: str = Field(..., min_length=1)
    authoritative_source_type: str = Field(..., min_length=1)
    subject_binding: Optional[str] = None
    target_binding: Optional[str] = None
    freshness_requirement: Optional[str] = None
    validation_method: Optional[str] = None
    minimum_cardinality: int = Field(default=1, ge=0)
    mandatory: bool = True
    allowed_issuers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionConditionDefinition(BaseModel):
    """A deterministic, machine-readable decision condition.

    Conditions are ordered by ``priority`` (lower first). The interpreter is
    deterministic and never uses an LLM to resolve a condition.
    """

    condition_id: str = Field(..., min_length=1)
    expression: str = Field(..., min_length=1)
    resulting_decision: DecisionOutcome
    priority: int = Field(default=100, ge=0)
    reason_code: str = Field(..., min_length=1)
    terminal: bool = True


# --------------------------------------------------------------------------- #
# Package request / response
# --------------------------------------------------------------------------- #
class ExecutableGovernancePackageCreate(BaseModel):
    """Payload for ingesting a new (DRAFT) executable governance package."""

    organization_id: str = Field(..., min_length=1)
    package_name: str = Field(..., min_length=1)
    package_version: str = Field(..., min_length=1)
    content_schema_version: str = Field(default="1.0.0", min_length=1)

    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    supersedes_package_id: Optional[str] = None

    signature: Optional[str] = None
    signer_key_id: Optional[str] = None

    source_document_references: list[Any] = Field(default_factory=list)
    source_requirement_references: list[Any] = Field(default_factory=list)

    requirements: list[RequirementDefinition] = Field(default_factory=list)
    applicability_rules: list[dict[str, Any]] = Field(default_factory=list)
    control_definitions: list[ControlDefinition] = Field(default_factory=list)
    evidence_requirements: list[EvidenceRequirementDefinition] = Field(
        default_factory=list
    )
    decision_conditions: list[DecisionConditionDefinition] = Field(
        default_factory=list
    )
    conflict_resolution_rules: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Opt-in: set True only for packages whose decision conditions read
    # CompliIdentity authority-context facts (authority.reason / .sufficient
    # / .active / .current_trust_state). Packages that leave this False never
    # trigger a CompliIdentity call and are unaffected by this integration.
    requires_authority_context: bool = False


class ExecutableGovernancePackageResponse(CanonicalResponseBase):
    """Executable governance package as returned by the API."""

    package_name: str
    package_version: str
    content_schema_version: str
    status: str
    effective_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    supersedes_package_id: Optional[str] = None
    superseded_by_package_id: Optional[str] = None
    package_hash: Optional[str] = None
    signature: Optional[str] = None
    signer_key_id: Optional[str] = None
    source_document_references: list[Any] = Field(default_factory=list)
    source_requirement_references: list[Any] = Field(default_factory=list)
    requirements: list[dict[str, Any]] = Field(default_factory=list)
    applicability_rules: list[dict[str, Any]] = Field(default_factory=list)
    control_definitions: list[dict[str, Any]] = Field(default_factory=list)
    evidence_requirements: list[dict[str, Any]] = Field(default_factory=list)
    decision_conditions: list[dict[str, Any]] = Field(default_factory=list)
    conflict_resolution_rules: list[dict[str, Any]] = Field(default_factory=list)
    package_metadata: dict[str, Any] = Field(default_factory=dict)
    requires_authority_context: bool = False


class PackageApproveRequest(BaseModel):
    """Approve a validated package."""

    approved_by: str = Field(..., min_length=1)


class PackagePublishRequest(BaseModel):
    """Publish an approved package.

    ``expected_package_hash`` (optional) lets the publisher assert the hash it
    expects; publication is rejected if the recomputed hash does not match.
    """

    expected_package_hash: Optional[str] = None


class PackageSupersedeRequest(BaseModel):
    """Mark a published package as superseded by a newer published package."""

    superseded_by_package_id: str = Field(..., min_length=1)


class PackageValidationResult(BaseModel):
    """Structured result of validating a package against the contract."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    status: str
